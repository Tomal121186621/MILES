#!/usr/bin/env python3
"""Car ownership, step 5: interactions, each tested alone against the step-4 model (MNL, income with bends, unweighted),
then the ones that pass are added together. Density is centred at its mean; ln income is already centred at $50k.
Pass rule: BIC lower and the implied effect plausible (checked by hand from s05_interactions.csv).
Also reports the Baltimore City car-free share predicted by each model.   Usage: python3 estimation/development/car_ownership/s05_interactions.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from mnl import fit
from s04_form import REST, pieces

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
CANDS = {"inc_x_dens": ("ln_income", "dens_c", "ln income x density"),
         "wrk_x_dens": ("workers", "dens_c", "workers x density"),
         "kids_x_sfd": ("children", "sfd", "children x single-family detached"),
         "old_x_inc": ("any_65plus", "ln_income", "member 65+ x ln income"),
         "single_x_dens": ("single_person", "dens_c", "single person x density")}


def balt(d, r):
    m = d.balt_city == 1; return 100 * r["P"][m, 0].mean()


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    for c in ["workers", "nonworking_adults", "children"]: d[c] = d[c].clip(upper=6)
    base = REST + pieces(d)
    d["dens_c"] = d.ln_density - d.ln_density.mean()
    for k, (a, b, _) in CANDS.items(): d[k] = d[a] * d[b]
    r0 = fit(d, base); rows = [dict(model="step-4 model", K=r0["K"], LL=r0["LL"], BIC=r0["BIC"], balt_nocar=balt(d, r0))]
    obs = 100 * (d[d.balt_city == 1].cars == 0).mean()
    for k, (_, _, lab) in CANDS.items():
        r = fit(d, base + [k]); row = dict(model=f"+ {lab}", K=r["K"], LL=r["LL"], BIC=r["BIC"], dLL=r["LL"] - r0["LL"], dBIC=r["BIC"] - r0["BIC"], balt_nocar=balt(d, r))
        for n, b, s in zip(r["names"], r["b"], r["se"]):
            v, alt = n.split("|")
            if v == k: row[f"coef_{alt}"] = b; row[f"t_{alt}"] = b / s
        rows.append(row); print({x: (round(y, 2) if isinstance(y, float) else y) for x, y in row.items()})
    R = pd.DataFrame(rows); passed = [k for k, (_, _, lab) in CANDS.items() if R.set_index("model").at[f"+ {lab}", "dBIC"] < 0]
    rA = fit(d, base + passed)
    R = pd.concat([R, pd.DataFrame([dict(model="all that lower the BIC: " + ", ".join(CANDS[k][2] for k in passed), K=rA["K"], LL=rA["LL"], BIC=rA["BIC"],
                                         dLL=rA["LL"] - r0["LL"], dBIC=rA["BIC"] - r0["BIC"], balt_nocar=balt(d, rA))])])
    R["balt_nocar_observed"] = obs
    R.to_csv(f"{HERE}/s05_interactions.csv", index=False)
    C = pd.DataFrame([dict(param=n, coef=b, t=b / s) for n, b, s in zip(rA["names"], rA["b"], rA["se"])]); C.to_csv(f"{HERE}/s05_final_coef.csv", index=False)
    print(R[["model", "K", "LL", "dBIC", "balt_nocar"]].round(1).to_string()); print("Baltimore City observed car-free %:", round(obs, 1))


if __name__ == "__main__":
    main()
