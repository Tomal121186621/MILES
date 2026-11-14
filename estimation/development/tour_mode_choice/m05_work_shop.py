#!/usr/bin/env python3
"""Tour mode choice, work and shopping tours: generalised cost (model of record, R) against time and cost as separate terms (TC,
km on walk and bike only; walk keeps rural home only); work also TCI (cost / (income / $50k)), same data, structure and extra terms as the models of record.
Work: choice-based sample weights (WESML) as in the model of record; t-statistics here are Biogeme's weighted robust ones, used only
for screening (the WESML sandwich is in activity/lib/mode_choice/estimate_wesml.py). Hold-out: log-likelihood of the validation half
(work: weighted with its own WESML weights).   ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice/m05_work_shop.py -> m05_fit.csv, m05_coef.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
import m03_time_cost as T3, m04_refine as R4   # noqa: E402
G = T3.G
import biogeme.database as db, biogeme.biogeme as bio
from biogeme.expressions import Variable as X

EXTRA = {"work": ["short"], "shopping": ["joint"]}
STRUCT = {"work": dict(nested=True, dest=True), "shopping": dict(nested=False, dest=False, generic=True)}
FORMS = {"work": ["R", "TC", "TCI"], "shopping": ["R", "TC"]}


def data(half, seg):
    f = T3.data(half, seg)
    if seg == "work":
        w = pd.read_parquet(f"{G.WORK}/wesml_{'est' if half == 'estimation' else 'hold'}.parquet")
        assert len(w) == len(f) and (w.choice.values == f.choice.values).all()
        f["wesml"] = w.wesml.values
    return f


def main():
    os.makedirs(f"{HERE}/bio", exist_ok=True); os.chdir(f"{HERE}/bio"); fit, coef = [], []
    num = lambda x: x.select_dtypes(include=[np.number, bool]).astype(float)
    for seg in ["work", "shopping"]:
        df, ho = data("estimation", seg), data("validation", seg)
        alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        for form in FORMS[seg]:
            ll = R4.LLF(form)(df, alts, EXTRA[seg], form, **STRUCT[seg]); llh = R4.LLF(form)(ho, alts, EXTRA[seg], form, **STRUCT[seg])
            m = bio.BIOGEME(db.Database(f"{seg}{form}", num(df)), ll if seg != "work" else {"loglike": ll, "weight": X("wesml")}, save_iterations=False, generate_html=False, generate_yaml=False)
            m.model_name = f"m05_{seg}_{form}"; r = m.estimate(); t = G.table(r); b = t.Value.to_dict()
            s = bio.BIOGEME(db.Database(f"{seg}{form}h", num(ho)), {"ll": llh}, save_iterations=False, generate_html=False, generate_yaml=False)
            lh = s.simulate(the_beta_values=b)["ll"].values
            HO = float((lh * ho.wesml.values).sum()) if seg == "work" else float(lh.sum())
            LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
            fit.append(dict(segment=seg, form=form, N=N, K=K, LL=LL, BIC=K * np.log(N) - 2 * LL, holdout_LL=HO, converged=bool(r.algorithm_has_converged),
                            gradient_norm=float(r.gradient_norm), vot_per_h=60 * b["time"] / b["cost"] if "cost" in b else np.nan))
            for n, x in t.iterrows(): coef.append(dict(segment=seg, form=form, param=n, coef=x.Value, se=x["Robust std err."], t=x["Robust t-stat."]))
            print(fit[-1], flush=True)
            print(t.loc[[k for k in t.index if k.split('_')[0] in ('gc', 'time', 'cost', 'mu')], ["Value", "Robust t-stat."]].round(4).to_string(), flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/m05_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m05_coef.csv", index=False)


if __name__ == "__main__":
    main()
