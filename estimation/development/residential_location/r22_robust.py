#!/usr/bin/env python3
"""Robustness of the revised PUMA level (r22_final.py), 2026-11-19:
  norace   the r22 PUMA level without the own-race share (same data and dwelling level)  -> r22_fit_norace.csv, r22_coef_norace.csv
  ss       sampled-alternatives check as r20_sample_size.py (J30 seed 20261117, J30 second draw 20261118, J60, J100; the seed also redraws
           the 200 IV dwellings; estimation half; reference = the J30 run of this script)   -> r22_ss_coef.csv, r22_ss_fit.csv
    python3 r22_robust.py norace|ss"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
ARGS = list(sys.argv)   # r14 replaces sys.argv on import
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r22_city_bias as B   # noqa: E402
import r22_final as RF      # noqa: E402
F, R = B.F, B.R
from mnl import MNL         # noqa: E402


def norace():
    D, G = B.designs(); A = B.puma_attrs(G); S = B.split_county(G)
    up0 = list(F.UPF); F.UPF = [u for u in up0 if u != "own_race"]
    for d in D: d["X"] = d["X"][:, :, [up0.index(u) for u in F.UPF]]
    r = B.fit("r22_norace", RF.NEW, D, A, S); m = r["m"]; N = len(D[0]["w"])
    pd.DataFrame([dict(level="PUMA (inclusive value at 1), no own-race share", N=N, K=m.k, LL=m.ll, BIC=m.k * np.log(N) - 2 * m.ll, validation_N=len(D[1]["w"]),
                       validation_LL=r["vll"])]).to_csv(f"{HERE}/r22_fit_norace.csv", index=False)
    pd.DataFrame([dict(level="PUMA", param=n, coef=b, robust_se=s, t=b / s) for n, b, s in zip(r["names"], m.b, m.rse)]).to_csv(f"{HERE}/r22_coef_norace.csv", index=False)
    print(m.ll, r["vll"]); print(pd.read_csv(f"{HERE}/r22_coef_norace.csv").round(4).to_string(index=False))


def ss():
    est, val, pool, G = F.setup(); A = B.puma_attrs(G); out, fit = [], []
    k = [R.UP.index(v) for v in F.UPF]; iv = R.UP.index("IVd"); jm = F.UPF.index("lnM")
    lm = np.log(np.maximum(F.MSIZES["stock_x_turnover"].reindex(F.G_PUMAS).values, 1.0))
    for lab, J, seed in [("J30", 30, 20261117), ("J30, second draw", 30, 20261118), ("J60", 60, 20261117), ("J100", 100, 20261117)]:
        R.J = J; R.RNG = np.random.default_rng(seed); R.dw_X = F._full
        alt, av = R.sample(est, pool); X = F.F17.dw_final(est, alt); C = np.zeros_like(av); C[:, 0] = True; m = MNL(X, F.DWF, av, C).fit()
        R.dw_X = F.F17.dw_final
        if "crime" not in R.UP: R.UP = R.UP + ["crime"]
        class Bb: pass
        mb = Bb(); mb.b = m.b
        X1, av1, C1, w1, n1 = R.upper_data(est, pool, mb, G)
        Z = X1[:, :, k].copy(); Z[:, :, jm] = lm[None, :]
        ex = B.combine(RF.NEW, dict(h=est.reset_index(drop=True), av=av1, lnddens=X1[:, :, R.UP.index("lnddens")]), A)
        Zx = np.concatenate([Z] + [ex[n][:, :, None] for n in ex], 2); names = list(F.UPF) + list(ex)
        mu = MNL(Zx, names, av1, C1, weights=w1, offset=X1[:, :, iv]).fit()
        out += [dict(case=lab, level="dwelling", param=a, coef=b, robust_se=s) for a, b, s in zip(F.DWF, m.b, m.rse)]
        out += [dict(case=lab, level="PUMA", param=a, coef=b, robust_se=s) for a, b, s in zip(names, mu.b, mu.rse)]
        fit.append(dict(case=lab, J=J, seed=seed, dwelling_LL=m.ll, PUMA_LL=mu.ll)); print(fit[-1], flush=True)
    c = pd.DataFrame(out); ref = c[c.case == "J30"].set_index(["level", "param"])
    c["diff_in_se"] = [(r.coef - ref.coef[(r.level, r.param)]) / ref.robust_se[(r.level, r.param)] for r in c.itertuples()]
    c.to_csv(f"{HERE}/r22_ss_coef.csv", index=False); pd.DataFrame(fit).to_csv(f"{HERE}/r22_ss_fit.csv", index=False)
    print(c.assign(a=c.diff_in_se.abs()).pivot_table(index="level", columns="case", values="a", aggfunc="max").round(2))


if __name__ == "__main__":
    {"norace": norace, "ss": ss}[ARGS[1]]()
