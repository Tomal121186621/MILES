#!/usr/bin/env python3
"""FINAL two-level residential location model (2026-11-17, user-approved simplifications; ACS PUMS 2014-2018 movers, estimation half,
validation half once; the validation half had been used before in model development).
  dwelling within the PUMA (18): cost above 30 % of income (one slope) and ln monthly cost, each x ln income; bedroom shortfall
     and excess, each x ln income; built in the last 5 years, x ln income; type constants SFA, MF 2-4, MF 5+, mobile home (SFD
     reference), each x ln income.  ln income = ln(max(income, 5000) / 50000).
  PUMA (10), inclusive value of the dwelling level held at 1: ln market size, car time 20-60 and > 60 min from the previous home,
     destination inside the previous migration area (PUMA group), destination bordering it, same state, commute sum ln(1 + t),
     crime x children, ln dwelling density, own-race share (dynamic in application).
Writes r17_fit.csv, r17_coef.csv (with robust s.e.), r17_vif.csv, r17_est_corr_<level>.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
os.environ["RACE_TEST"] = "1"
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r14_puma_two_level as R   # noqa: E402
import r16_collinearity as Q     # noqa: E402
from mnl import MNL              # noqa: E402
DWF = ["over30", "over30_x_lninc", "lncost", "lncost_x_lninc", "bed_short", "bed_short_x_lninc", "bed_extra", "bed_extra_x_lninc",
       "new5", "new5_x_lninc"] + [v for t in R.TYPES for v in (t, f"{t}_x_lninc")]
UPF = ["lnM", "d2", "d3", "same", "adjacent", "same_state", "commute_log", "crime_x_child", "lnddens", "own_race"]
NORACE = os.environ.get("NO_RACE") == "1"   # robustness: the final model without the own-race share
if NORACE: UPF = [u for u in UPF if u != "own_race"]
SUF = "_norace" if NORACE else ""
LABEL = {"over30": "cost above 30 % of income (share)", "lncost": "ln monthly housing cost", "bed_short": "bedroom shortfall", "bed_extra": "bedroom excess",
         "new5": "built in the last 5 years", "SFA": "single-family attached", "MF234": "multi-family 2-4 units", "MF5plus": "multi-family 5+ units", "MH": "mobile home",
         "lnM": "ln market size of the PUMA", "d2": "car time 20-60 min from the previous home (min)", "d3": "car time over 60 min (min)",
         "same": "destination inside the previous migration area (PUMA group)", "adjacent": "destination bordering the previous migration area",
         "same_state": "same state", "commute_log": "commute, sum over workers of ln(1 + min)", "crime_x_child": "crime index x children",
         "lnddens": "ln dwelling density", "own_race": "own-race share of the PUMA's households"}
_full = R.dw_X


def dw_final(h, alt):
    """design of the final dwelling level (the inclusive value of upper_data uses this too)"""
    X = _full(h, alt); F = {n: X[:, :, k] for k, n in enumerate(R.DW)}
    inc = np.maximum(h.income.values, 5000.0)[:, None]; lninc = np.log(inc / 50000.0); b = np.minimum(12 * alt["cost"] / inc, 3.0)
    F["over30"] = np.maximum(b - .3, 0); F["over30_x_lninc"] = F["over30"] * lninc
    return np.stack([F[n] for n in DWF], 2)


def main():
    mv = pd.read_parquet(f"{R.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    R.RNG = np.random.default_rng(20261117); G = R.geography(); fit, coef, vif = [], [], []
    alt, av = R.sample(est, pool); X = dw_final(est, alt); C = np.zeros_like(av); C[:, 0] = True; m = MNL(X, DWF, av, C).fit()
    altv, avv = R.sample(val, pool); Xv = dw_final(val, altv); Cv = np.zeros_like(avv); Cv[:, 0] = True
    vll = float(MNL(Xv, DWF, avv, Cv).loglik_obs(m.b).sum()); ll0 = float(np.log(1.0 / av.sum(1)).sum())
    fit.append(dict(level="dwelling within PUMA", N=len(est), K=m.k, LL0=ll0, LL=m.ll, BIC=m.k * np.log(len(est)) - 2 * m.ll, validation_N=len(val), validation_LL=vll))
    coef += [dict(level="dwelling", param=a, coef=b, robust_se=s, t=b / s) for a, b, s in zip(DWF, m.b, m.rse)]
    Q.report("dwelling", DWF, X, av, m.cov_robust, vif)
    pd.DataFrame(m.cov_robust / np.sqrt(np.outer(np.diag(m.cov_robust), np.diag(m.cov_robust))), index=DWF, columns=DWF).round(3).to_csv(f"{HERE}/r17_est_corr_dwelling{SUF}.csv")
    R.dw_X = dw_final
    class B: pass
    mb = B(); mb.b = m.b
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]
    X1, av1, C1, w1, n1 = R.upper_data(est, pool, mb, G); Xv1, avv1, Cv1, wv1, nv1 = R.upper_data(val, pool, mb, G)
    k = [R.UP.index(v) for v in UPF]; iv = R.UP.index("IVd")
    mu = MNL(X1[:, :, k], UPF, av1, C1, weights=w1, offset=X1[:, :, iv]).fit()
    vu = float(MNL(Xv1[:, :, k], UPF, avv1, Cv1, offset=Xv1[:, :, iv]).loglik_obs(mu.b).sum()); ll0u = float(np.log(1.0 / av1.sum(1)).sum())
    fit.append(dict(level="PUMA (inclusive value at 1)", N=n1, K=mu.k, LL0=ll0u, LL=mu.ll, BIC=mu.k * np.log(n1) - 2 * mu.ll, validation_N=nv1, validation_LL=vu))
    coef += [dict(level="PUMA", param=a, coef=b, robust_se=s, t=b / s) for a, b, s in zip(UPF, mu.b, mu.rse)]
    Q.report("PUMA", UPF, X1[:, :, k], av1, mu.cov_robust, vif)
    pd.DataFrame(mu.cov_robust / np.sqrt(np.outer(np.diag(mu.cov_robust), np.diag(mu.cov_robust))), index=UPF, columns=UPF).round(3).to_csv(f"{HERE}/r17_est_corr_PUMA{SUF}.csv")
    c = pd.DataFrame(coef); c["label"] = [LABEL.get(p, LABEL.get(p.replace("_x_lninc", ""), p) + (" x ln income" if p.endswith("_x_lninc") else "")) for p in c.param]
    pd.DataFrame(fit).to_csv(f"{HERE}/r17_fit{SUF}.csv", index=False); c.to_csv(f"{HERE}/r17_coef{SUF}.csv", index=False); pd.DataFrame(vif).to_csv(f"{HERE}/r17_vif{SUF}.csv", index=False)
    print(pd.DataFrame(fit).round(2).to_string(index=False)); print(c[["level", "label", "coef", "robust_se", "t"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
