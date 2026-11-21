# base_v8 (2026-11-16b): copy of base_v7/carfix/s07_write.py with v7 -> v8
# base_v8 (2026-11-15d) copy of input_build/carfix_1115/s07_write.py: hh source hh_2016_v8c, dd link dd_2016_v8a; run as s07_write.py pp_2016_v8d jj_2016_v8d v8
"""Write the corrected base as NEW files (the record files are only read): input/microData/hh_2016_v6carfix.csv (hh_2016_v2 with the
re-assigned cars) and pp_2016_v6carfix.csv (pp_2016_v5respec with the corrected licences); every other field is copied as text.
run/base_v6carfix/microData links hh/pp to these files and dd/jj to the record dd_2016.csv / jj_2016_v5respec.csv.
Usage: s07_write.py [pp_source=pp_2016_v5respec] [jj_source=jj_2016_v5respec] [tag=v6carfix]"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys, os, pandas as pd, numpy as np
from common import OUT
V = WORKSPACE; md = f"{V}/2_silo/input/microData"
PPS = sys.argv[1] if len(sys.argv) > 1 else "pp_2016_v5respec"; JJS = sys.argv[2] if len(sys.argv) > 2 else "jj_2016_v5respec"; TAG = sys.argv[3] if len(sys.argv) > 3 else "v6carfix"
cars = pd.read_parquet(f"{OUT}/cars_new.parquet").set_index("id").cars_new; lic = pd.read_parquet(f"{OUT}/lic_new.parquet").set_index("id").lic_new
def rewrite(src, dst, col, newvals, conv):
    assert not os.path.exists(dst), f"{dst} exists, not overwritten"
    first = True; n = ch = 0
    for c in pd.read_csv(src, dtype=str, chunksize=1_000_000, keep_default_na=False):
        ids = c["id"].astype(np.int64); nv = newvals.reindex(ids).values; assert not pd.isna(nv).any()
        new = conv(nv); ch += int((new != c[col].values).sum()); c[col] = new; n += len(c)
        c.to_csv(dst, mode="w" if first else "a", header=first, index=False); first = False
    print(f"{dst}: {n:,} rows, {col} changed in {ch:,}")
rewrite(f"{md}/hh_2016_v8c.csv", f"{md}/hh_2016_{TAG}.csv", "autos", cars, lambda v: v.astype(int).astype(str))
rewrite(f"{md}/{PPS}.csv", f"{md}/pp_2016_{TAG}.csv", "driversLicense", lic, lambda v: np.where(v.astype(bool), "True", "False"))
B = f"{V}/2_silo/run/base_{TAG}/microData"; os.makedirs(B, exist_ok=True)
for k, f in [("hh", f"hh_2016_{TAG}"), ("pp", f"pp_2016_{TAG}"), ("dd", "dd_2016_v8a"), ("jj", JJS)]:
    if not os.path.lexists(f"{B}/{k}_2016.csv"): os.symlink(f"{md}/{f}.csv", f"{B}/{k}_2016.csv")
print("links in", B, sorted(os.listdir(B)))
