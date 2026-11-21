# base_v8 (2026-11-16b): copy of base_v7/carfix/s01_extract.py with v7 -> v8
# base_v8 (2026-11-15d) copy of input_build/carfix_1115/s01_extract.py: base = hh_2016_v8c, pp_2016_v8d, dd_2016_v8a
"""Extract the record base (hh_2016_v2, pp_2016_v5respec, dd_2016) into compact parquet: households and persons."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os  # PROJECT_ROOT
import pandas as pd, numpy as np
V = WORKSPACE; md = f"{V}/2_silo/input/microData"
OUT = (f"{WORKSPACE}/2_silo/input_build/base_v8/carfix/work")
z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").set_index("ZoneId")
hh = pd.read_csv(f"{md}/hh_2016_v8c.csv"); dd = pd.read_csv(f"{md}/dd_2016_v8a.csv", usecols=["id", "zone", "type"]).set_index("id")
pp = pd.read_csv(f"{md}/pp_2016_v8d.csv", usecols=["id", "hhID", "age", "gender", "occupation", "driversLicense", "income"])
pp["lic"] = pp.driversLicense.astype(str).str.lower().eq("true"); pp = pp.drop(columns="driversLicense")
hh["zone"] = dd.zone.reindex(hh.dwelling).values; hh["dtype"] = dd.type.reindex(hh.dwelling).values
hh["county"] = hh.zone.map(z.COUNTYFIPS); hh["st"] = hh.zone.map(z.STFIPS); hh["puma"] = hh.zone.map(z.PUMA_10 % 100000)
g = pp.assign(a16=pp.age >= 16, wk=pp.occupation == 1).groupby("hhID").agg(n=("id", "size"), adults=("a16", "sum"), workers=("wk", "sum"), drivers=("lic", "sum"), pinc=("income", "sum"))
hh = hh.join(g, on="id")
print(len(hh), len(pp), "hhSize==n", (hh.hhSize == hh.n).mean(), "income==pinc", (hh.income == hh.pinc).mean())
hh.to_parquet(f"{OUT}/hh_base.parquet", index=False); pp.to_parquet(f"{OUT}/pp_base.parquet", index=False)
o = pd.read_csv(f"{md}/hh_2016_v8a.csv", usecols=["id", "autos"]).set_index("id").autos
print("autos same as hh_2016:", (o.reindex(hh.id).values == hh.autos.values).mean())
print(hh.st.value_counts().to_dict()); print(hh.autos.value_counts().sort_index().to_dict())
