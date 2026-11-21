#!/usr/bin/env python3
"""Workplace choice: own-race share re-tested with the corrected RTS race coding (2026-11-18).
w08_candidates.py coded race as {4 white, 2 Black, 1 Hispanic} for every person, but the RTS flat file mixes two codings:
BMC-region households (1 white, 2 Black, Hispanic origin only in race_ethnicity_hispanic) and TPB-region households (1 Hispanic,
2 Black, 4 white).  The coding is identified by home county as in ../locations/l09_school_data.py.  Final model C0 of w09_cars.py
with and without the own-race share of the workplace zone's workers (2016 synthetic population).   ->  w10_fit.csv, w10_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import norm
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import w08_candidates as W8   # noqa: E402  (sets the own-race share variable; its main() is not run)
import wdc, w07_simplify as W7   # noqa: E402
r = pd.read_csv(f"{ABIT_HOME}/input/rts/RTS_raw_flat_data.csv", usecols=["person_id", "race_ethnicity", "race_ethnicity_hispanic", "home_state_county_fips"],
                low_memory=False).drop_duplicates("person_id")
nh = r[r.race_ethnicity_hispanic != 1]
cc = nh.groupby("home_state_county_fips").race_ethnicity.agg(c4=lambda x: (x == 4).sum(), c1=lambda x: (x == 1).sum())
tpb = r.home_state_county_fips.isin(set(cc.index[cc.c4 > cc.c1])).values
code, hf = r.race_ethnicity.values, r.race_ethnicity_hispanic.values
hisp = (hf == 1) | (tpb & (code == 1)); white = ~hisp & ((~tpb & (code == 1)) | (tpb & (code == 4))); black = ~hisp & (code == 2)
race = pd.Series(np.select([white, black, hisp], [0, 1, 2], 3), index=r.person_id.values)
old = wdc.D["p_race"].copy(); wdc.D["p_race"] = W8.P.person_id.map(race).fillna(3).astype(int).values
print("workers by race (old coding -> corrected):\n", pd.crosstab(old, wdc.D["p_race"], rownames=["old"], colnames=["new"]))
_pv = wdc.pvar
def pvar(name, P):
    if name == "car1": return (P["car_seg"] == 1).astype(float)
    return _pv(name, P)
wdc.pvar = pvar
f7 = pd.read_csv(f"{HERE}/w07_fit.csv"); s3 = f7[f7.step == "S3"].terms.iloc[0].split()
c9 = pd.read_csv(f"{HERE}/w09_coef.csv"); c9 = c9[c9.step == "C0"].set_index("param").coef.to_dict()
rows, coefs = [], []
for code_, lab, tm in [("C0", "final model", s3 + ["t*car0_c"]), ("C0R", "+ own-race share (corrected race coding)", s3 + ["t*car0_c", "ownrace"])]:
    m = W7.Equal(tm); m.fit(np.array([c9.get(n, 0.0) if n != "mu" else c9.get("mu", 0.84) for n in m.names])); m.robust(); ho = m.holdout_ll()
    rows.append(dict(step=code_, label=lab, K=m.K, LL=m.LL, BIC=m.BIC, validation_LL=ho))
    for n, b, s, t in m.table():
        if not n.startswith("g_"): coefs.append(dict(step=code_, param=n, coef=b, se=s, t=t, p=2 * norm.sf(abs(t))))
    print(f"{code_} {lab}: K {m.K} LL {m.LL:.2f} BIC {m.BIC:.1f} hold-out {ho:.2f}", flush=True)
pd.DataFrame(rows).to_csv(f"{HERE}/w10_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/w10_coef.csv", index=False)
c = pd.DataFrame(coefs); w = c.pivot(index="param", columns="step", values="coef"); w["shift_in_se"] = (w.C0R - w.C0) / c[c.step == "C0"].set_index("param").se
print(c[c.param == "ownrace"].round(4).to_string(index=False)); print(w.round(3).to_string())
