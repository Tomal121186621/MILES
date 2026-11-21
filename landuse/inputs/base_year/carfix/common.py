import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
# base_v8 (2026-11-16b): copy of base_v7/carfix/common.py with v7 -> v8
# base_v8 (2026-11-15d) copy of input_build/carfix_1115/common.py: work dir base_v8/carfix/work
import os  # PROJECT_ROOT
import pandas as pd, numpy as np
OUT = (f"{WORKSPACE}/2_silo/input_build/base_v8/carfix/work")
SIX = [24003, 24005, 24013, 24025, 24027, 24510]
def acs_county():
    H = pd.read_parquet(f"{OUT}/acs1418_h.parquet"); zw = pd.read_parquet(f"{OUT}/county_puma_w.parquet")
    A = H.merge(zw, left_on="PUMA", right_on="puma"); A["w"] = A.WGTP * A.n; return A
def acl(a): return np.minimum(a, 3)          # adults class 0/1/2/3+
def summ(d, cars, adults, w):
    cars = np.asarray(cars); adults = np.asarray(adults); w = np.asarray(w, float)
    return dict(zero=np.average(cars == 0, weights=w), fewer=np.average((cars > 0) & (cars < adults), weights=w),
                cls_lt=np.average(cars < adults, weights=w), cpa=(cars * w).sum() / (adults * w).sum(), adults=np.average(adults, weights=w))
