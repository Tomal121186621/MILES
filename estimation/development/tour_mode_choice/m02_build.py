#!/usr/bin/env python3
"""Tour mode choice, other and school tours: GC coefficient as the blocks of the model of record are added one at a time
(MNL, generic GC, estimation half).   ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice/m02_build.py  ->  m02_build.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
sys.path.insert(0, f"{TERP_HOME}/activity/lib/mode_choice")
import estimate_gc as G, estimate_hh as H   # noqa: E402
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
from biogeme.expressions import Beta, Variable as X

STEPS = [("B1 constants + GC", [], []), ("B2 + km walk, bike", [], ["WK", "BK"]), ("B3 + km car passenger, bus, train", [], G.ALTS[1:]),
         ("B4 + cars, licence", ["autos", "lic"], G.ALTS[1:]), ("B5 + age, sex, household size", ["autos", "lic", "age", "male", "hhsize"], G.ALTS[1:]),
         ("B6 + home area type", ["autos", "lic", "age", "male", "hhsize", "core_o", "rural_o"], G.ALTS[1:]),
         ("B7 + destination area type", ["autos", "lic", "age", "male", "hhsize", "core_o", "rural_o", "core_d", "rural_d"], G.ALTS[1:])]


def main():
    os.makedirs(f"{HERE}/bio", exist_ok=True); os.chdir(f"{HERE}/bio"); rows = []
    for seg in ["other", "school"]:
        df = H.prep(G.load(seg)); alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        for lab, vs, km in STEPS:
            V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}; bg = Beta("gc", 0, None, None, 0)
            for a in alts:
                if a != "CD":
                    for v in vs:
                        if df.loc[df[f"av_{a}"] > 0, v].std() > 0: V[a] = V[a] + Beta(f"{v}_{a}", 0, None, None, 0) * X(v)
                    if a in km: V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
                if a in G.GC_ALTS: V[a] = V[a] + bg * X(f"gc_{a}")
            ll = models.loglogit({G.NUM[a]: V[a] for a in alts}, {G.NUM[a]: X(f"av_{a}") for a in alts}, X("y"))
            m = bio.BIOGEME(db.Database(f"{seg}", df.select_dtypes(include=[np.number, bool]).astype(float)), ll, save_iterations=False, generate_html=False, generate_yaml=False)
            m.model_name = "m02"; r = m.estimate(); t = G.table(r)
            rows.append(dict(segment=seg, step=lab, K=int(r.number_of_free_parameters), LL=float(r.final_loglikelihood), gc=t.Value["gc"], t=t["Robust t-stat."]["gc"]))
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/m02_build.csv", index=False)


if __name__ == "__main__":
    main()
