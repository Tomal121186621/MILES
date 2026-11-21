# base_v8 (2026-11-16b): copy of base_v7/carfix/s09_lic_check.py with v7 -> v8
"""base_v8 (2026-11-15d) copy of carfix_1115/s09_lic_check.py: 2016 files of run/base_v8."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
"""Licence rate 16+ by age band x area in a SILO run (pp/hh/dd of each year) against the targets of input/drivers_license_targets_md.csv.
    python3 s09_lic_check.py <scenario> <years...>"""
import sys, os, pandas as pd, numpy as np
V = WORKSPACE; S = f"{V}/2_silo"
name, years = sys.argv[1], [int(y) for y in sys.argv[2:]]; O = f"{S}/run/base/scenOutput/{name}/microData"
z = pd.read_csv(f"{S}/input/zoneSystem.csv", usecols=["ZoneId", "COUNTYFIPS"]).set_index("ZoneId").COUNTYFIPS
T = pd.read_csv(f"{S}/input/drivers_license_targets_md.csv")
BANDS = [16, 18, 20, 25, 35, 45, 55, 65, 75, 200]; BL = ["16-17", "18-19", "20-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
T["band"] = BL * (len(T) // len(BL))
def f(kind, y):   # state at the start of year y (validate_silo.yfile): base files for 2016, else the files labelled y-1
    if y == 2016: return f"{S}/run/base_v8/microData/{kind}_2016.csv"
    for p in [f"{O}/{kind}_{y - 1}.csv", f"{O}/{kind}_{y - 1}.csv.gz", f"{O}/futureYears/{kind}_{y - 1}.csv"]:
        if os.path.exists(p): return p
    raise FileNotFoundError(f"{kind}_{y - 1}")
res = []
for y in years:
    pp = pd.read_csv(f("pp", y), usecols=lambda c: c in ("hhID", "hhid", "age", "driversLicense")).rename(columns={"hhid": "hhID"})
    hh = pd.read_csv(f("hh", y), usecols=["id", "dwelling"]); dd = pd.read_csv(f("dd", y), usecols=["id", "zone"])
    c = hh.dwelling.map(dd.set_index("id").zone).map(z); pp["cty"] = pp.hhID.map(pd.Series(c.values, index=hh.id))
    pp = pp[pp.age >= 16]; pp["lic"] = pp.driversLicense.astype(str).str.lower().eq("true")
    pp["area"] = np.where(pp.cty == 24510, "city", np.where(pp.cty.isin([24003, 24005, 24013, 24025, 24027]), "study", np.where(pp.cty // 1000 == 24, "rest", "outside")))
    pp["band"] = pd.cut(pp.age, BANDS, right=False, labels=BL).astype(str)
    g = pp.groupby(["area", "band"]).lic.mean().rename(y); res.append(g)
    a = pp.assign(a=pp.age.clip(upper=19))[pp.age <= 19].groupby(["area", "a"]).lic.mean().unstack().round(3)
    print(y, "single ages 16-19:\n", a.to_string()); print(y, "Maryland 16+:", round(pp[pp.area != "outside"].lic.mean(), 4), "outside:", round(pp[pp.area == "outside"].lic.mean(), 4))
R = T.set_index(["area", "band"])[["target"]].join(pd.concat(res, axis=1)).round(3)
R["max_dev_pp"] = ((R[years].sub(R.target, axis=0)).abs().max(axis=1) * 100).round(1); print(R.to_string())
R.to_csv(f"{S}/input_build/base_v8/carfix/licence_check_{name}.csv")
