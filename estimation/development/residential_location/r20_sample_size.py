#!/usr/bin/env python3
"""Sampled-alternatives check of the r20 model (r19_sample_size.py with the corrected crosswalk r20_geo_*_zone.csv, 2026-11-18n):
J = 30 (seed 20261117), J = 30 second draw (20261118), J = 60, J = 100; the seed also redraws the 200 dwellings of the inclusive value.
Estimation half only.  The reference is the J30 run of this script (same draw sequence as r18).  Writes r20_ss_coef.csv, r20_ss_fit.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ["GEO_PZ"] = f"{HERE}/r20_geo_puma_zone.csv"; os.environ["GEO_MZ"] = f"{HERE}/r20_geo_mig_zone.csv"
import r19_final as F   # noqa: E402
from mnl import MNL     # noqa: E402
R = F.R


def run(J, seed, est, pool, G):
    R.J = J; R.RNG = np.random.default_rng(seed); R.dw_X = F._full
    alt, av = R.sample(est, pool); X = F.F17.dw_final(est, alt); C = np.zeros_like(av); C[:, 0] = True; m = MNL(X, F.DWF, av, C).fit()
    R.dw_X = F.F17.dw_final
    class B: pass
    mb = B(); mb.b = m.b
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]
    X1, av1, C1, w1, n1 = R.upper_data(est, pool, mb, G); k = [R.UP.index(v) for v in F.UPF]; iv = R.UP.index("IVd"); jm = F.UPF.index("lnM")
    Z = X1[:, :, k].copy(); Z[:, :, jm] = np.log(np.maximum(F.MSIZES[F.MDEF].reindex(F.G_PUMAS).values, 1.0))[None, :]
    mu = MNL(Z, F.UPF, av1, C1, weights=w1, offset=X1[:, :, iv]).fit()
    rows = [dict(level="dwelling", param=a, coef=b, robust_se=s) for a, b, s in zip(F.DWF, m.b, m.rse)]
    rows += [dict(level="PUMA", param=a, coef=b, robust_se=s) for a, b, s in zip(F.UPF, mu.b, mu.rse)]
    return rows, dict(dwelling_LL=m.ll, dwelling_LL_per_mover=m.ll / len(est), PUMA_N=n1, PUMA_LL=mu.ll)


def main():
    assert R.GEO_PZ.endswith("r20_geo_puma_zone.csv"); est, val, pool, G = F.setup(); out, fit = [], []
    for lab, J, seed in [("J30", 30, 20261117), ("J30, second draw", 30, 20261118), ("J60", 60, 20261117), ("J100", 100, 20261117)]:
        rows, f = run(J, seed, est, pool, G); out += [dict(r, case=lab) for r in rows]; fit.append(dict(case=lab, J=J, seed=seed, **f)); print(lab, f, flush=True)
    c = pd.DataFrame(out); ref = c[c.case == "J30"].set_index(["level", "param"])
    c["diff_in_se"] = [(r.coef - ref.coef[(r.level, r.param)]) / ref.robust_se[(r.level, r.param)] for r in c.itertuples()]
    c.to_csv(f"{HERE}/r20_ss_coef.csv", index=False); pd.DataFrame(fit).to_csv(f"{HERE}/r20_ss_fit.csv", index=False)
    w = c.pivot_table(index=["level", "param"], columns="case", values="diff_in_se", sort=False); print(w.round(2).to_string())
    print("max |diff| in s.e. by case:"); print(w.abs().max().round(2).to_string())


if __name__ == "__main__":
    main()
