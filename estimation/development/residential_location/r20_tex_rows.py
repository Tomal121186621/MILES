#!/usr/bin/env python3
"""Coefficient rows and fit numbers of the residential location tables (article est_resloc_*.tex, tab_est_overview, tab_resloc_race)
from r20_coef.csv / r20_fit.csv / r20_coef_norace.csv / r20_fit_norace.csv / r20_ss_coef.csv.  Prints LaTeX rows; edits nothing."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from scipy.stats import norm
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"   # HERE: results of this step (data); CODE: this folder
def num(x, d=4): s = f"{abs(x):.{d}f}"; return ("$-$" if x < 0 else "") + s
def star(p): return "$^{***}$" if p < .01 else "$^{**\\phantom{*}}$" if p < .05 else "$^{*\\phantom{**}}$" if p < .10 else "$^{\\phantom{***}}$"
def pv(p): return "$<$0.001" if p < .001 else f"{p:.3f}"
c = pd.read_csv(f"{HERE}/r20_coef.csv"); c["p"] = 2 * norm.sf(np.abs(c.coef / c.robust_se))
for r in c.itertuples(): print(f"{r.level:8s} {r.param:18s} & {num(r.coef)}{star(r.p)} & {r.robust_se:.4f} & {pv(r.p)} \\\\")
f = pd.read_csv(f"{HERE}/r20_fit.csv")
for r in f.itertuples():
    print(f"{r.level}: N {r.N} K {r.K} LL0 {r.LL0:.1f} LL {r.LL:.1f} rho2 {1 - r.LL / r.LL0:.3f} rhobar2 {1 - (r.LL - r.K) / r.LL0:.3f} AIC {2 * r.K - 2 * r.LL:.1f} "
          f"BIC {r.BIC:.1f} per mover {r.LL / r.N:.3f}; hold-out N {r.validation_N} LL {r.validation_LL:.1f} per mover {r.validation_LL / r.validation_N:.3f}")
n = pd.read_csv(f"{HERE}/r20_coef_norace.csv"); fn = pd.read_csv(f"{HERE}/r20_fit_norace.csv").iloc[0]
print("no race:", " ".join(f"{a} {num(b)} ({s:.4f})" for a, b, s in zip(n.param, n.coef, n.robust_se)))
print(f"no race: K {fn.K} LL {fn.LL:.1f} BIC {fn.BIC:.1f} hold-out {fn.validation_LL:.1f}")
s = pd.read_csv(f"{HERE}/r20_ss_coef.csv"); print(s.assign(a=s.diff_in_se.abs()).pivot_table(index="level", columns="case", values="a", aggfunc="max").round(2))
