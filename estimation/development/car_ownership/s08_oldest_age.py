#!/usr/bin/env python3
"""Car ownership, final model re-estimated with the age of the OLDEST member of the household instead of the PUMS householder
(2026-11-09, so that estimation and engine agree: SILO stores no householder).  Same specification as the s07 final model
(no reselection), same estimation sample and hold-out 20 %.  Writes s08_fit.csv / s08_coef.csv and replaces the 'final' row of
s07_fit.csv and the 'final' coefficient rows of s07_coef.csv (the householder-age final is kept as step 'final_householder';
backups *_pre1109x).
    python3 estimation/development/car_ownership/s08_oldest_age.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from mnl import fit, probs, design
from s04_form import pieces
from s06_age import head_age, oldest_age, prep

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder


def main():
    h = pd.read_parquet(f"{HERE}/hh.parquet"); F = pd.read_csv(f"{HERE}/s07_fit.csv"); V = F[F.step == "final"].spec.iloc[0].split()
    rows, coefs = [], []
    for step, lab, ages in [("final_householder", "final model, householder age (PUMS RELP 0)", head_age()), ("final", "final model, age of the oldest member", oldest_age())]:
        e = h[h.half == "estimation"].reset_index(drop=True); o = h[h.half == "holdout"].reset_index(drop=True)
        md = e.ln_density.mean(); e = prep(e, md, ages); o = prep(o, md, ages); pieces(e); pieces(o)
        r = fit(e, V); ho = float(np.log(probs(r["b"], design(o, V))[np.arange(len(o)), o.cars.values]).sum())
        rows.append(dict(step=step, label=lab, K=r["K"], LL=r["LL"], BIC=r["BIC"], holdout_LL=ho, spec=" ".join(V), N=r["N"], conv=r["conv"]))
        for n, b, s in zip(r["names"], r["b"], r["se"]): coefs.append(dict(step=step, label=lab, param=n, coef=b, t=b / s, se=s))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/s08_fit.csv", index=False); C = pd.DataFrame(coefs); C.to_csv(f"{HERE}/s08_coef.csv", index=False)
    F = F[F.step != "final"]; R = pd.DataFrame(rows); F = pd.concat([F, R[R.step == "final"].drop(columns=["N"]), R[R.step == "final_householder"].drop(columns=["N"])])
    F.to_csv(f"{HERE}/s07_fit.csv", index=False)
    S = pd.read_csv(f"{HERE}/s07_coef.csv"); S = S[~S.step.isin(["final", "final_householder"])]
    pd.concat([S, C.drop(columns=["se"])]).to_csv(f"{HERE}/s07_coef.csv", index=False)
    print(C[C.param.str.startswith("age10")].to_string(index=False))


if __name__ == "__main__":
    main()
