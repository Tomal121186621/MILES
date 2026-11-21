#!/usr/bin/env python3
"""Collinearity of the simplified two-level residential model (r15_simple.py, final variants: dwelling '+inc+type', PUMA 'main' with
crime x children, inclusive value at 1).  For each level, on the estimation half:
  - within-choice-set correlation of the explanatory variables (each variable demeaned over the available alternatives of the
    record, pooled over records) and variance inflation factors of that matrix
  - correlation of the estimates (robust covariance)
Writes r16_var_corr_<level>.csv, r16_est_corr_<level>.csv, r16_vif.csv; prints pairs with |r| >= 0.6 and VIF >= 5."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
os.environ["RACE_TEST"] = "1"
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r14_puma_two_level as R   # noqa: E402
import r15_simple as S           # noqa: E402
from mnl import MNL              # noqa: E402


def within(X, av):
    av = av.astype(float); n = av.sum(1, keepdims=True); m = (X * av[..., None]).sum(1) / n
    Z = (X - m[:, None, :]) * av[..., None]; A = Z.reshape(-1, X.shape[2]); A = A[av.reshape(-1) > 0]
    C = np.corrcoef(A, rowvar=False); return C


def report(level, names, X, av, cov, rows):
    C = within(X, av); vif = np.diag(np.linalg.inv(C)); E = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
    pd.DataFrame(C, index=names, columns=names).round(3).to_csv(f"{HERE}/r16_var_corr_{level}.csv")
    pd.DataFrame(E, index=names, columns=names).round(3).to_csv(f"{HERE}/r16_est_corr_{level}.csv")
    print(f"== {level}: VIF max {vif.max():.1f} ({names[int(vif.argmax())]})")
    for k, v in zip(names, vif): rows.append(dict(level=level, variable=k, VIF=v))
    for nm, M in (("variables", C), ("estimates", E)):
        pr = [(names[i], names[j], M[i, j]) for i in range(len(names)) for j in range(i + 1, len(names)) if abs(M[i, j]) >= 0.6]
        print(f"   {nm} |r| >= 0.6: " + ("; ".join(f"{a} / {b} {r:+.2f}" for a, b, r in sorted(pr, key=lambda x: -abs(x[2]))) or "none"))
    print("   VIF >= 5: " + (", ".join(f"{k} {v:.1f}" for k, v in zip(names, vif) if v >= 5) or "none"))


def main():
    mv = pd.read_parquet(f"{R.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); G = R.geography(); rows = []
    ds = S.DSETS["+inc+type"]; R.RNG = np.random.default_rng(20261117)
    alt, av = R.sample(est, pool); X = R.dw_X(est, alt); ix = [S.ALL_DW.index(v) for v in ds]; C = np.zeros_like(av); C[:, 0] = True
    m = MNL(X[:, :, ix], ds, av, C).fit(); report("dwelling", ds, X[:, :, ix], av, m.cov_robust, rows)
    class B: pass
    mb = B(); bb = np.zeros(len(S.ALL_DW)); bb[ix] = m.b; mb.b = bb
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]
    X1, av1, C1, w1, n1 = R.upper_data(est, pool, mb, G); k = [R.UP.index(v) for v in S.UPM[1:]]
    mu = MNL(X1[:, :, k], S.UPM[1:], av1, C1, weights=w1, offset=X1[:, :, R.UP.index("IVd")]).fit()
    report("PUMA", S.UPM[1:], X1[:, :, k], av1, mu.cov_robust, rows)
    pd.DataFrame(rows).to_csv(f"{HERE}/r16_vif.csv", index=False)


if __name__ == "__main__":
    main()
