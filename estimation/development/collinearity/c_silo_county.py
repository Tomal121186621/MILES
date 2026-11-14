#!/usr/bin/env python3
"""Collinearity of the final county model (residential_location/r05_region_sequence.py run as 'final newiv', final step Ja after the 2026-11-09 re-run;
county_data_est.pkl of r07_county_iv.py), estimation half, all 44 counties, household weights of the estimation (D['w']).
    python3 estimation/development/collinearity/c_silo_county.py   ->  county_var_corr.png, county_est_corr.png, county_pairs.csv, county_facts.json"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; RES = os.path.join(os.path.dirname(HERE), "residential")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.argv = [os.path.join(DEV, "residential_location", "r05_region_sequence.py"), "final", "newiv"]       # as in run_residential_chain.sh
sys.path.insert(0, os.path.join(DEV, "residential_location")); sys.path.insert(0, CODE)
import c_silo_common as CC   # noqa: E402
import r05_region_sequence as R5   # noqa: E402

LAB = {"d2": "Car time to another county 20–60 min", "d3": "Car time to another county over 60 min", "same_region": "Previous county",
       "adjacent": "County bordering the previous county", "same_state": "Same state as the origin", "IV_B": "Zone × structure type, λB",
       "IV_A": "Dwelling, λA", "commute_log": "Sum over workers of ln(1+t)", "commute_log_x_inc": "Sum over workers of ln(1+t) × ln income",
       "same_x_age": "Previous county × (age − 50)/10", "d2_x_lninc": "Car time 20–60 min × ln income", "d3_x_lninc": "Car time over 60 min × ln income",
       "growth": "School learning growth (SD per grade)", "crime_x_child": "Crime index × children"}


def main():
    fitc = pd.read_csv(f"{RES}/r05_fit.csv"); fin = fitc[fitc.final].iloc[0]; co = pd.read_csv(f"{RES}/r05_coef.csv")
    step = fin.step; names = co[co.step == step].parameter.tolist(); print("final step", step, names, flush=True)
    De = R5.add_growth(pickle.load(open(f"{RES}/county_data_est.pkl", "rb")))
    fix = {"IV_A": 1.0} if "IV_A" in str(fin.fixed_at_1) else None
    vs = [v for v in ["d2", "d3", "same_region", "adjacent", "same_state", "IV_B", "IV_A", "commute_log", "commute_log_x_inc", "same_x_age", "d2_x_lninc",
                      "d3_x_lninc", "growth", "crime_x_child"] if v in names or (fix and v in fix)]
    assert set(vs) - set(fix or {}) == set(names), (vs, names)

    def run(drop=(), replace=None):
        D = dict(De); D["F"] = dict(De["F"]); D["F"].update(replace or {})
        m = R5.fit(D, [v for v in vs if v not in drop], fix=fix)
        return dict(LL=m.ll, K=m.k, N=m.n, names=list(m.names), b=m.b, se=m.rse, cov=m.cov_robust)

    base = run(); print("LL", base["LL"], "reported", fin.LL, flush=True); assert abs(base["LL"] - fin.LL) < 0.1
    order = [v for v in vs if v in base["names"]]; assert order == base["names"]
    h = De["h"]; lninc = np.log(np.maximum(h.income.values, 5000) / 50000); age = (h.age_max.values.astype(float) - 50) / 10
    X = np.stack([De["F"][v] for v in order], axis=2)
    inter = {"commute_log_x_inc": ("commute_log", lninc, None), "same_x_age": ("same_region", age, None), "d2_x_lninc": ("d2", lninc, None),
             "d3_x_lninc": ("d3", lninc, None)}
    sets = [({"d2", "d3"}, "adjacent piecewise segments"), ({"d2_x_lninc", "d3_x_lninc"}, "piecewise segments × ln income")]
    CC.run_alt_model("county", "County (residential level 1), final model", X, order, De["av"], De["w"], LAB, inter, sets, base,
                     lambda drop, replace: run(drop, replace),
                     extra_vars=[("IV_A", De["F"]["IV_A"][:, :, None])] if fix else [])   # 2026-11-10: only when IV_A is fixed (an offset); estimated now


if __name__ == "__main__":
    main()
