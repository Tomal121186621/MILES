#!/usr/bin/env python3
"""Workplace choice: household car availability x car time on the simplified model S3 (2026-11-17).  car0 = household without a
car, car1 = fewer cars than workers... as the car segment of the estimation data (car_seg 0 / 1; 2 = enough cars, reference); centred
like the other time interactions.  Kept if BIC falls and the hold-out LL rises.   ->  w09_fit.csv, w09_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import norm
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import wdc, w07_simplify as W7   # noqa: E402
_pv = wdc.pvar
def pvar(name, P):
    if name == "car1": return (P["car_seg"] == 1).astype(float)
    return _pv(name, P)
wdc.pvar = pvar
wdc.MEAN["car1"] = float(pvar("car1", wdc._PE).mean())
f7 = pd.read_csv(f"{HERE}/w07_fit.csv"); s3 = f7[f7.step == "S3"].terms.iloc[0].split()
c7 = pd.read_csv(f"{HERE}/w07_coef.csv"); c7 = c7[c7.step == "S3"].set_index("param").coef.to_dict()
rows, coefs = [], []
for code, lab, tm in [("S3", "simplified model", s3), ("C", "+ time x no car, time x fewer cars than workers", s3 + ["t*car0_c", "t*car1_c"]), ("C0", "+ time x no car", s3 + ["t*car0_c"])]:
    m = W7.Equal(tm); m.fit(np.array([c7.get(n, 0.0) if n != "mu" else c7.get("mu", 0.86) for n in m.names])); m.robust(); ho = m.holdout_ll()
    rows.append(dict(step=code, label=lab, K=m.K, LL=m.LL, BIC=m.BIC, validation_LL=ho))
    for n, b, s, t in m.table():
        if not n.startswith("g_"): coefs.append(dict(step=code, param=n, coef=b, se=s, t=t, p=2 * norm.sf(abs(t))))
    print(f"{code} {lab}: K {m.K} LL {m.LL:.2f} BIC {m.BIC:.1f} hold-out {ho:.2f}", flush=True)
pd.DataFrame(rows).to_csv(f"{HERE}/w09_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/w09_coef.csv", index=False)
c = pd.DataFrame(coefs); print(c[c.step.isin(["C", "C0"]) & c.param.str.contains("car")].round(4).to_string(index=False))
