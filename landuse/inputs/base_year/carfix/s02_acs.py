# base_v8 (2026-11-16b): copy of base_v7/carfix/s02_acs.py with v7 -> v8
# base_v8 (2026-11-15d) copy of input_build/carfix_1115/s02_acs.py: unchanged (ACS PUMS 2014-18), new work dir
"""ACS PUMS 2014-18 Maryland households (non-GQ) with persons 16+, workers, income (2016 $), cars (clipped at 3), and the county weights
of validate_silo.py (each county's PUMAs weighted by the county's zone count in the PUMA)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os  # PROJECT_ROOT
import pandas as pd, numpy as np, zipfile
ROOT = PROJECT_ROOT; V = f"{WORKSPACE}"
OUT = (f"{WORKSPACE}/2_silo/input_build/base_v8/carfix/work")
with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_pmd.zip") as zf:
    n = [x for x in zf.namelist() if x.endswith(".csv")][0]; P = pd.read_csv(zf.open(n), usecols=["SERIALNO", "PUMA", "RELP", "AGEP", "ESR"], dtype={"SERIALNO": str})
with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_hmd.zip") as zf:
    H = pd.read_csv(zf.open("psam_h24.csv"), usecols=["SERIALNO", "PUMA", "WGTP", "NP", "TYPE", "VEH", "HINCP", "ADJINC"], dtype={"SERIALNO": str})
P = P[~P.RELP.isin([16, 17])]; H = H[(H.TYPE == 1) & (H.NP > 0)].copy()
H["adults"] = H.SERIALNO.map(P[P.AGEP >= 16].groupby("SERIALNO").size()).fillna(0).astype(int)
H["workers"] = H.SERIALNO.map(P[P.ESR.isin([1, 2, 4, 5])].groupby("SERIALNO").size()).fillna(0).astype(int)
H["inc16"] = H.HINCP.fillna(0) * H.ADJINC / 1e6 / 1.046; H["cars"] = H.VEH.fillna(0).clip(upper=3).astype(int); H["veh"] = H.VEH.fillna(0)
z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv"); z = z[z.STFIPS == 24]
zw = z.groupby(["COUNTYFIPS", z.PUMA_10 % 100000]).size().rename("n").reset_index(); zw.columns = ["county", "puma", "n"]
H.to_parquet(f"{OUT}/acs1418_h.parquet", index=False); zw.to_parquet(f"{OUT}/county_puma_w.parquet", index=False)
print(len(H), H.adults.value_counts().sort_index().to_dict())
