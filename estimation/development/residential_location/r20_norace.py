#!/usr/bin/env python3
"""Robustness of r20_final.py: PUMA level without the own-race share (same data, dwelling level, seed and market size).
Writes r20_fit_norace.csv, r20_coef_norace.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ["GEO_PZ"] = f"{HERE}/r20_geo_puma_zone.csv"; os.environ["GEO_MZ"] = f"{HERE}/r20_geo_mig_zone.csv"
import r19_final as F   # noqa: E402

F.UPF = [u for u in F.UPF if u != "own_race"]


def main():
    assert F.R.GEO_PZ.endswith("r20_geo_puma_zone.csv")
    est, val, pool, G = F.setup(); m, X, av, vll, ll0 = F.dwelling(est, val, pool)
    D, Dv = F.upper_designs(est, val, pool, m.b, G); mu, X1, av1, vu, ll0u, n1, nv1 = F.upper_fit(D, Dv, F.MSIZES["stock_x_turnover"])
    pd.DataFrame([dict(level="PUMA (inclusive value at 1), no own-race share", N=n1, K=mu.k, LL0=ll0u, LL=mu.ll, BIC=mu.k * np.log(n1) - 2 * mu.ll,
                       validation_N=nv1, validation_LL=vu)]).to_csv(f"{HERE}/r20_fit_norace.csv", index=False)
    c = pd.DataFrame([dict(level="PUMA", param=a, coef=b, robust_se=s, t=b / s) for a, b, s in zip(F.UPF, mu.b, mu.rse)]); c.to_csv(f"{HERE}/r20_coef_norace.csv", index=False)
    print(mu.ll, vu); print(c.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
