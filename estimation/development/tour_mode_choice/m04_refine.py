#!/usr/bin/env python3
"""Tour mode choice, follow-up of m03_time_cost.py.
  other  R: model of record re-run with up to 5,000 iterations (it stops at the 1,000-iteration limit)
         TC with the non-motorised nest removed (walk and bike as single alternatives; its parameter is not different from 1)
  Walk: rural home and rural destination are the same variable in the sample (no walk tour leaves its area type); only rural home
  is kept on walk in TC, Tk and Ta. Optimiser: up to 5,000 iterations (bio/biogeme.toml).
  school T: car time only, generic over car driver, car passenger, bus and train, no money cost (school travel is mostly paid by
         parents or free: school bus, coded car passenger); km on walk and bike only (Tk) or on every non-reference mode (Ta)
Estimation half; log-likelihood of the validation half.   ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice/m04_refine.py -> m04_fit.csv, m04_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
import m03_time_cost as T3   # noqa: E402
G = T3.G
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
from biogeme.expressions import Beta, Variable as X
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit


def loglike(df, alts, extra, form, nested, dest, nests=G.NESTS, generic=None):
    km_modes = G.ALTS[1:] if form == "Ta" else ["WK", "BK"]
    V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}
    for a in alts:
        if a == "CD": continue
        for v in G.SOCIO + (G.DEST if dest else []) + extra:
            if a == "WK" and v == "rural_d": continue
            if df.loc[df[f"av_{a}"] > 0, v].std() > 0: V[a] = V[a] + Beta(f"{v}_{a}", 0, None, None, 0) * X(v)
        if a in km_modes: V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
    bt, bc = Beta("time", 0, None, None, 0), Beta("cost", 0, None, None, 0)
    for a in T3.MOT:
        if a in alts: V[a] = V[a] + bt * X(f"t_{a}") + (bc * X(f"c_{a}") if form == "TC" else bc * X(f"ci_{a}") if form == "TCI" else 0)
    U = {G.NUM[a]: V[a] for a in alts}; AV = {G.NUM[a]: X(f"av_{a}") for a in alts}
    if nested:
        ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0), [G.NUM[a] for a in v if a in alts], name=k) for k, v in nests.items()]
        return models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    return models.loglogit(U, AV, X("y"))


RUNS = [("other", "R", "model of record, 5,000 iterations", dict(nested=True, dest=True)),
        ("other", "TC", "TC, no non-motorised nest", dict(nested=True, dest=True, nests={k: v for k, v in G.NESTS.items() if k != "nonmot"})),
        ("school", "Tk", "car time only, km walk and bike", dict(nested=False, dest=False)),
        ("school", "Ta", "car time only, km every mode", dict(nested=False, dest=False))]


def LLF(form):
    return T3.loglike if form == "R" else loglike


def main():
    os.makedirs(f"{HERE}/bio", exist_ok=True); os.chdir(f"{HERE}/bio"); fit, coef = [], []
    num = lambda x: x.select_dtypes(include=[np.number, bool]).astype(float)
    for seg, form, lab, st in RUNS:
        df, ho = T3.data("estimation", seg), T3.data("validation", seg)
        alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        m = bio.BIOGEME(db.Database(f"{seg}{form}", num(df)), LLF(form)(df, alts, T3.EXTRA[seg], form, **st), save_iterations=False, generate_html=False, generate_yaml=False)
        m.model_name = f"m04_{seg}_{form}"; r = m.estimate(); t = G.table(r); b = t.Value.to_dict()
        s = bio.BIOGEME(db.Database(f"{seg}{form}h", num(ho)), {"ll": LLF(form)(ho, alts, T3.EXTRA[seg], form, **st)}, save_iterations=False, generate_html=False, generate_yaml=False)
        HO = float(s.simulate(the_beta_values=b)["ll"].sum()); LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
        fit.append(dict(segment=seg, form=form, label=lab, N=N, K=K, LL=LL, gradient_norm=float(r.gradient_norm), BIC=K * np.log(N) - 2 * LL, holdout_LL=HO, converged=bool(r.algorithm_has_converged),
                        vot_per_h=60 * b["time"] / b["cost"] if "cost" in b else np.nan))
        for n, x in t.iterrows(): coef.append(dict(segment=seg, form=form, param=n, coef=x.Value, se=x["Robust std err."], t=x["Robust t-stat."]))
        print(fit[-1], flush=True)
        print(t.loc[[k for k in t.index if k.split('_')[0] in ('gc', 'time', 'cost', 'mu') or k.startswith('km')], ["Value", "Robust t-stat."]].round(4).to_string(), flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/m04_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m04_coef.csv", index=False)


if __name__ == "__main__":
    main()
