# Copy of 2_silo/resloc/rc.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Common paths and helpers of the residential location choice estimation (2_silo/resloc)."""
import os, zipfile, gzip
import numpy as np
import pandas as pd

ROOT = os.environ.get("TERP_PROJECT_ROOT", "") + ""
V = f"{ROOT}/Validation_2026"
PKG = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))   # PATH (package): manual_estimation/SILO
SH = f"{PKG}/00_shared_data"   # PATH (package)
S2 = f"{V}/2_silo"
RL = f"{S2}/resloc"
WORK = f"{SH}/resloc_work"   # PATH (package)
TAB = WORK   # PATH (package): tables of the original main() functions (not used by the package)
FIG = WORK   # PATH (package)
RAW = f"{SH}/county_attributes"   # PATH (package): SEDA file; the crosswalks of s01_geography.py are not copied (see README)
INP = f"{SH}/zone_system"   # PATH (package): crimeIndex.csv, zones.shp
MICRO = f"{SH}/synthetic_population_2016"   # PATH (package)
ZONES = f"{SH}/zone_system/zoneSystem.csv"   # PATH (package)
SKIM_CAR = f"{SH}/skims/auto_peak_time.csv.gz"   # PATH (package)
SKIM_PT_BASE = f"{S2}/input/skims/transit_peak_time.csv.gz"   # PATH (package): not used by the package (original location)
SKIM_PT_D2D = f"{SH}/skims/transit_peak_time_d2d_2024.csv.gz"   # PATH (package)
GAZ = f"{ROOT}/I695_pricing/data/census/Gaz_tracts_national.txt"
TRACT_ZONE = f"{SH}/rts_2017_18/tract_zone.csv"   # PATH (package)
RTS = f"{SH}/rts_2017_18"   # PATH (package)
SPLIT = f"{SH}/rts_2017_18/rts_split.csv"   # PATH (package)
STATES = {"dc": 11, "de": 10, "md": 24, "pa": 42, "va": 51, "wv": 54}
CPI = {2014: 236.736, 2015: 237.017, 2016: 240.007, 2017: 245.120, 2018: 251.107, 2019: 255.657, 2020: 258.811, 2021: 270.970,
       2022: 292.655, 2023: 304.702}   # CPI-U annual averages (BLS CUUR0000SA0)
# SILO household types: income bounds of HouseholdType (properties income.brackets.hh.types)
INC_BOUNDS = [40000, 75000, 125000]   # 2026-10-27: rounded quartiles of 2016 Maryland household income (41,311 / 76,627 / 129,224); before 20k/40k/60k (Munich default)
INC_GROUPS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
for d in (WORK, TAB, FIG):
    os.makedirs(d, exist_ok=True)


def inc_group(inc):
    return np.array(INC_GROUPS)[np.searchsorted(INC_BOUNDS, np.asarray(inc), side="right")]


ZONE_IDS = np.sort(pd.read_csv(ZONES, usecols=["ZoneId"]).ZoneId.values)   # 1,588 ids in 1..1674 (not contiguous)
ZIDX = pd.Series(np.arange(len(ZONE_IDS)), index=ZONE_IDS)


def read_skim(path, unreachable=999.0):
    """FROM,TO,VALUE csv.gz -> dense 1588 x 1588 array in the order of ZONE_IDS, values >= unreachable -> nan."""
    d = pd.read_csv(path)
    n = len(ZONE_IDS)
    m = np.full((n, n), np.nan)
    m[ZIDX.reindex(d.FROM.values).values, ZIDX.reindex(d.TO.values).values] = d.VALUE.values
    m[m >= unreachable] = np.nan
    return m


def pums_read(year, kind, state, cols):
    """kind 'p' or 'h'; returns DataFrame with requested columns that exist."""
    z = f"{SH}/acs_pums_2014_2018_5yr/csv_{kind}{state}.zip" if year == 2018 else f"{ROOT}/inputs/pums_{year}_5yr/csv_{kind}{state}.zip"   # PATH (package): 2014-2018 file copied; others original
    with zipfile.ZipFile(z) as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        head = pd.read_csv(zf.open(n), nrows=0).columns
        use = [c for c in cols if c in head]
        return pd.read_csv(zf.open(n), usecols=use, low_memory=False, dtype={"SERIALNO": str})


def zones():
    z = pd.read_csv(ZONES)
    return z[["ZoneId", "Region", "COUNTYFIPS", "STATEFP10", "PUMA_10", "SchoolQualityIndex"]].rename(columns={"ZoneId": "zone", "Region": "region"})
