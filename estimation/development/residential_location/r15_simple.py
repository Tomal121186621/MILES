#!/usr/bin/env python3
"""Simplified two-level residential model (2026-11-17, user: no unnecessary interactions, simplify).  Variants on the data and code of
r14_puma_two_level.py (imported; race in, dynamic share in application):
  dwelling  main    cost share (3 slopes), ln cost, bedroom shortfall / excess, built last 5 years, 4 type constants      (11)
            +inc    main + the income interactions of cost share, ln cost, bedrooms, new dwelling                          (17)
            +type   main + type x ln income                                                                                  (15)
  PUMA      main    ln market size, car time 20-60 / > 60 min, same migration PUMA, bordering, same state, commute, crime,
                    density, own-race share                                                                                  (11)
Writes r15_fit.csv, r15_coef.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
os.environ["RACE_TEST"] = "1"
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r14_puma_two_level as R   # noqa: E402
from mnl import MNL              # noqa: E402
MAIN = ["bur_lo", "bur_mid", "bur_hi", "lncost", "bed_short", "bed_extra", "new5"] + R.TYPES
DSETS = {"+inc+type": MAIN + R.INC + [f"{t}_x_lninc" for t in R.TYPES]}   # v2 (v1: main, +inc, +type in r15_fit_v1.csv)
UPM = ["IVd", "lnM", "d2", "d3", "same", "adjacent", "same_state", "commute_log", "crime_x_child", "lnddens", "own_race"]   # v2: crime only x children (main effect +0.60, central job-rich PUMAs)
ALL_DW = R.DW


def main():
    mv = pd.read_parquet(f"{R.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    G = R.geography(); fit, coef = [], []
    for dn, ds in DSETS.items():
        R.DW = ALL_DW   # full design, then select columns
        R.RNG = np.random.default_rng(20261117)
        alt, av = R.sample(est, pool); X = R.dw_X(est, alt); ix = [ALL_DW.index(v) for v in ds]
        C = np.zeros_like(av); C[:, 0] = True; m = MNL(X[:, :, ix], ds, av, C).fit()
        altv, avv = R.sample(val, pool); Xv = R.dw_X(val, altv); Cv = np.zeros_like(avv); Cv[:, 0] = True
        vll = float(MNL(Xv[:, :, ix], ds, avv, Cv).loglik_obs(m.b).sum())
        print(f"dwelling {dn}: K {m.k} LL {m.ll:.2f} BIC {m.k * np.log(len(est)) - 2 * m.ll:.1f} validation {vll:.2f}", flush=True)
        fit.append(dict(level="dwelling", variant=dn, K=m.k, LL=m.ll, BIC=m.k * np.log(len(est)) - 2 * m.ll, validation_LL=vll))
        coef += [dict(level="dwelling", variant=dn, param=a, coef=b, se=s, t=b / s) for a, b, s in zip(ds, m.b, m.rse)]
        if dn not in ("+inc+type",): continue
        class B: pass
        mb = B(); bb = np.zeros(len(ALL_DW)); bb[ix] = m.b; mb.b = bb
        R.UP = R.UP + (["crime"] if "crime" not in R.UP else [])
        X1, av1, C1, w1, n1 = R.upper_data(est, pool, mb, G); Xv1, avv1, Cv1, wv1, nv1 = R.upper_data(val, pool, mb, G)
        k = [R.UP.index(v) for v in UPM[1:]]; off = X1[:, :, R.UP.index("IVd")]
        mu = MNL(X1[:, :, k], UPM[1:], av1, C1, weights=w1, offset=off).fit()
        vu = float(MNL(Xv1[:, :, k], UPM[1:], avv1, Cv1, offset=Xv1[:, :, R.UP.index("IVd")]).loglik_obs(mu.b).sum())
        print(f"  PUMA main (inclusive value at 1), dwelling {dn}: K {mu.k} LL {mu.ll:.2f} BIC {mu.k * np.log(n1) - 2 * mu.ll:.1f} validation {vu:.2f}", flush=True)
        fit.append(dict(level="PUMA", variant=f"main, dwelling {dn}", K=mu.k, LL=mu.ll, BIC=mu.k * np.log(n1) - 2 * mu.ll, validation_LL=vu))
        coef += [dict(level="PUMA", variant=f"main, dwelling {dn}", param=a, coef=b, se=s, t=b / s) for a, b, s in zip(UPM[1:], mu.b, mu.rse)]
        for a, b, s in zip(UPM[1:], mu.b, mu.rse): print(f"    {a:14s} {b: .4f} t {b / s: .1f}")
        pd.DataFrame(fit).to_csv(f"{HERE}/r15_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/r15_coef.csv", index=False)


if __name__ == "__main__":
    main()
