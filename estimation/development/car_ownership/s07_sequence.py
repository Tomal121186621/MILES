#!/usr/bin/env python3
"""Car ownership, model development for reporting: the main-effect blocks of step 3, the functional forms of step 4 (income,
age), the interaction of step 5, each against the current model on the estimation sample (LR test at 5 %, BIC, signs).
Age form compared by BIC: member 65+, householder age linear, age + age squared, bands under 30 / 45-64 / 65+ (ref. 30-44).
The hold-out 20 % is used once, for the final model (and for the model of record, for comparison).
    python3 estimation/development/car_ownership/s07_sequence.py   ->  s07_fit.csv, s07_coef.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from scipy.stats import chi2
from mnl import fit, probs, design
from s04_form import pieces
from s06_age import head_age, prep

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
COMP = ["workers", "nonworking_adults", "children", "any_65plus", "single_person"]
AGE = {"member 65+": ["any_65plus"], "householder age, linear": ["age10"], "householder age + age squared": ["age10", "age10_sq"],
       "householder age bands": ["age_u30", "age45_64", "age65"]}


def main():
    ha = head_age(); h = pd.read_parquet(f"{HERE}/hh.parquet")
    e = h[h.half == "estimation"].reset_index(drop=True); o = h[h.half == "holdout"].reset_index(drop=True)
    md = e.ln_density.mean(); e = prep(e, md, ha); o = prep(o, md, ha); inc = pieces(e); pieces(o)
    rows, coef = [], []

    def run(code, label, vs, ref):
        r = fit(e, vs); row = dict(step=code, label=label, K=r["K"], LL=r["LL"], BIC=r["BIC"], conv=r.get("conv"))
        if ref is not None and r["K"] > ref["K"]:
            lr = 2 * (r["LL"] - ref["LL"]); row.update(LR=lr, df=r["K"] - ref["K"], p=float(chi2.sf(lr, r["K"] - ref["K"])))
        for n, b, s in zip(r["names"], r["b"], r["se"]): coef.append(dict(step=code, label=label, param=n, coef=b, t=b / s))
        rows.append(row); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True); return r, row

    cur, _ = run("M1", "constants", [], None); V = []
    for code, label, add in [("M2", "+ household composition", COMP), ("M3", "+ ln income", ["ln_income"]),
                             ("M4", "+ dwelling (single-family detached, multifamily, bedrooms)", ["sfd", "multifamily", "bedrooms"]),
                             ("M5", "+ ln dwelling density", ["ln_density"]), ("M6", "+ accessibility gain from a car", ["acc_gain"])]:
        r, row = run(code, label, V + add, cur); row["kept"] = row["p"] < 0.05 and row["BIC"] < cur["BIC"]
        if row["kept"]: cur, V = r, V + add
    # functional form: income
    Vp = [v for v in V if v != "ln_income"] + inc
    r, row = run("F1", "income piecewise linear (bends $25k, $50k, $100k)", Vp, cur); row["kept"] = row["p"] < 0.05 and row["BIC"] < cur["BIC"]
    if row["kept"]: cur, V = r, Vp
    # functional form: age (non-nested forms, BIC)
    base = [v for v in V if v != "any_65plus"]; best = None
    for nm, a in AGE.items():
        if nm == "member 65+": continue
        r, row = run("F2", f"age: {nm} instead of member 65+", base + a, None); row["dBIC_vs_current"] = row["BIC"] - cur["BIC"]; row["kept"] = False
        if row["BIC"] < (best[1]["BIC"] if best else cur["BIC"]): best = (r, row, a)
    if best: best[1]["kept"] = True; cur, V = best[0], base + best[2]
    # interaction
    r, row = run("I1", "+ ln income x ln density", V + ["inc_x_dens"], cur); row["kept"] = row["p"] < 0.05 and row["BIC"] < cur["BIC"]
    if row["kept"]: cur, V = r, V + ["inc_x_dens"]
    # hold-out once
    rec = [v for v in inc] + ["workers", "nonworking_adults", "children", "any_65plus", "single_person", "sfd", "multifamily", "bedrooms", "ln_density", "acc_gain", "inc_x_dens"]
    for lab, vs in [("final model", V), ("model of record (step 5)", rec)]:
        r = fit(e, vs); ho = float(np.log(probs(r["b"], design(o, vs))[np.arange(len(o)), o.cars.values]).sum())
        rows.append(dict(step="final" if lab == "final model" else "record", label=lab, K=r["K"], LL=r["LL"], BIC=r["BIC"], holdout_LL=ho, spec=" ".join(vs)))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/s07_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/s07_coef.csv", index=False)


if __name__ == "__main__":
    main()
