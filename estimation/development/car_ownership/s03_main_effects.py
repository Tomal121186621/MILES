#!/usr/bin/env python3
"""Car ownership, step 3: main effects added group by group in the order fixed in modeling_step_by_step.pdf.
Estimation sample only, unweighted (weighting is compared in step 4). The hold-out sample is not used here.
Outputs: s03_fit.csv (one row per step), s03_coef.csv (all coefficients of all steps).   Usage: python3 estimation/development/car_ownership/s03_main_effects.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from mnl import fit

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
COMP = ["workers", "nonworking_adults", "children", "any_65plus", "single_person"]
DWEL = ["sfd", "multifamily", "bedrooms"]


def effects(d, vars_, r):
    """average effect on the expected number of cars (0, 1, 2, 3 for 3+) of a change in one variable, all else as observed:
    +1 for counts and bedrooms, 0 -> 1 for dummies, doubling income (+ln 2), +1 s.d. for density and the accessibility gain."""
    from mnl import probs, design
    base = (probs(r["b"], design(d, vars_)) @ np.arange(4)).mean(); rows = []
    for v in vars_:
        e = d.copy()
        if set(np.unique(d[v])) <= {0.0, 1.0}:
            e[v] = 1.0; d0 = d.copy(); d0[v] = 0.0; lab = "0 -> 1"
            lo = (probs(r["b"], design(d0, vars_)) @ np.arange(4)).mean()
        else:
            step = np.log(2) if v == "ln_income" else (d[v].std() if v in ("ln_density", "acc_gain") else 1.0)
            e[v] = d[v] + step; lo = base
            lab = "income x 2" if v == "ln_income" else (f"+1 s.d. ({step:.2f})" if v in ("ln_density", "acc_gain") else "+1")
        hi = (probs(r["b"], design(e, vars_)) @ np.arange(4)).mean()
        rows.append(dict(variable=v, change=lab, effect_cars=hi - lo))
    return pd.DataFrame(rows)


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    d["workers"] = d.workers.clip(upper=6); d["nonworking_adults"] = d.nonworking_adults.clip(upper=6); d["children"] = d.children.clip(upper=6)
    steps = [("M1", "constants only", []),
             ("M2", "+ household composition", COMP),
             ("M3", "+ ln income", COMP + ["ln_income"]),
             ("M4", "+ dwelling", COMP + ["ln_income"] + DWEL)]
    base = COMP + ["ln_income"] + DWEL
    # location: the three duplicates are tried one at a time; the best fit is kept
    loc = {v: fit(d, base + [v]) for v in ["ln_density", "acc_car", "acc_nocar"]}
    best = max(loc, key=lambda v: loc[v]["LL"])
    for v in loc: print(f"  location candidate {v}: LL {loc[v]['LL']:.1f}")
    steps += [("M5", f"+ location: {best}", base + [best]),
              ("M6", "+ accessibility gain from a car", base + [best, "acc_gain"])]
    # Baltimore City was a candidate; dropped by decision (a place label, not a behavioural variable); see the PDF
    fits, coefs, prev = [], [], None
    for code, label, vars_ in steps:
        r = loc[best] if code == "M5" else fit(d, vars_)
        row = dict(step=code, label=label, K=r["K"], LL=r["LL"], BIC=r["BIC"], rho2_const=np.nan, conv=r["conv"], cond=r["cond"])
        if prev is not None:
            row.update(dLL=r["LL"] - prev["LL"], dK=r["K"] - prev["K"], LR=2 * (r["LL"] - prev["LL"]), dBIC=r["BIC"] - prev["BIC"])
        fits.append(row); prev = r
        for n, b, s in zip(r["names"], r["b"], r["se"]):
            v, a = n.split("|"); coefs.append(dict(step=code, variable=v, alt=a, coef=b, se=s, t=b / s))
        print(f"{code} {label}: K {r['K']} LL {r['LL']:.1f} BIC {r['BIC']:.1f} conv {r['conv']}")
    F = pd.DataFrame(fits); F["rho2_const"] = 1 - F.LL / F.LL.iloc[0]
    F.to_csv(f"{HERE}/s03_fit.csv", index=False)
    pd.DataFrame(coefs).to_csv(f"{HERE}/s03_coef.csv", index=False)
    effects(d, vars_, r).to_csv(f"{HERE}/s03_effects.csv", index=False)
    pd.DataFrame([dict(variable=v, LL=loc[v]["LL"], BIC=loc[v]["BIC"]) for v in loc]).to_csv(f"{HERE}/s03_location_choice.csv", index=False)


if __name__ == "__main__":
    main()
