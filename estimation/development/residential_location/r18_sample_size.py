#!/usr/bin/env python3
"""Sensitivity of the final two-level residential model (r17_final.py) to the sampled dwelling alternatives (2026-11-18):
J = 30 (model of record, seed 20261117), J = 30 with a second draw, J = 60 and J = 100 (the mover's dwelling + J - 1 drawn uniformly
from the PUMA's market).  The seed also redraws the 200 dwellings of the inclusive value.  Estimation half only.
Writes r18_coef.csv (coefficient, robust s.e., difference from the model of record in its s.e.) and r18_fit.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
os.environ["RACE_TEST"] = "1"
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r14_puma_two_level as R   # noqa: E402
import r17_final as F            # noqa: E402
from mnl import MNL              # noqa: E402
_full = R.dw_X


def run(J, seed, est, pool, G):
    R.J = J; R.RNG = np.random.default_rng(seed); R.dw_X = _full
    alt, av = R.sample(est, pool); X = F.dw_final(est, alt); C = np.zeros_like(av); C[:, 0] = True; m = MNL(X, F.DWF, av, C).fit()
    R.dw_X = F.dw_final
    class B: pass
    mb = B(); mb.b = m.b
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]
    X1, av1, C1, w1, n1 = R.upper_data(est, pool, mb, G); k = [R.UP.index(v) for v in F.UPF]; iv = R.UP.index("IVd")
    mu = MNL(X1[:, :, k], F.UPF, av1, C1, weights=w1, offset=X1[:, :, iv]).fit()
    rows = [dict(level="dwelling", param=a, coef=b, robust_se=s) for a, b, s in zip(F.DWF, m.b, m.rse)]
    rows += [dict(level="PUMA", param=a, coef=b, robust_se=s) for a, b, s in zip(F.UPF, mu.b, mu.rse)]
    return rows, dict(dwelling_LL=m.ll, dwelling_LL_per_mover=m.ll / len(est), PUMA_LL=mu.ll)


def main():
    mv = pd.read_parquet(f"{R.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); R.RNG = np.random.default_rng(20261117); G = R.geography()
    out, fit = [], []
    for lab, J, seed in [("J30 (model of record)", 30, 20261117), ("J30, second draw", 30, 20261118), ("J60", 60, 20261117), ("J100", 100, 20261117)]:
        rows, f = run(J, seed, est, pool, G); out += [dict(r, case=lab) for r in rows]; fit.append(dict(case=lab, J=J, seed=seed, **f)); print(lab, f, flush=True)
    c = pd.DataFrame(out); ref = c[c.case.str.startswith("J30 (")].set_index(["level", "param"])
    c["diff_in_se"] = [(r.coef - ref.coef[(r.level, r.param)]) / ref.robust_se[(r.level, r.param)] for r in c.itertuples()]
    c.to_csv(f"{HERE}/r18_coef.csv", index=False); pd.DataFrame(fit).to_csv(f"{HERE}/r18_fit.csv", index=False)
    w = c.pivot_table(index=["level", "param"], columns="case", values="diff_in_se", sort=False); print(w.round(2).to_string())


if __name__ == "__main__":
    main()
