#!/usr/bin/env python3
"""Job inventory by zone for the VAE workplace step, from observed data: LODES 2016 WAC jobs by block (NAICS sectors mapped to
the four SILO types) placed in MSTM zones, for all Maryland zones; the other states keep the MSTM forecast values (no LODES
file for them here).  Replaces inputs/employmentForecast_ron_orig.csv as the 2016 inventory (same columns, so the step runs
unchanged).  Vacancies: the inventory is filled jobs / (1 - JOLTS job-openings rate), the rate read from vacancy_rate.json
(Maryland, BLS JOLTS Table 12; see 2_silo/data_sources.md).  Output: 1_vae/output/employment_2016_lodes.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, geopandas as gpd, json, os
from shapely import points
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; RAW = f"{V}/data/raw"
TYPES = {"RET": ["CNS07", "CNS18"], "OFF": ["CNS09", "CNS10", "CNS11", "CNS12", "CNS13", "CNS14", "CNS15", "CNS16", "CNS20"],
         "IND": ["CNS01", "CNS02", "CNS03", "CNS04", "CNS05", "CNS06", "CNS08"], "OTH": ["CNS17", "CNS19"]}
rate = json.load(open(f"{V}/1_vae/vacancy_rate.json"))["job_openings_rate_2016"]
F = pd.read_csv(f"{ROOT}/inputs/employmentForecast_ron_orig.csv")
Z = gpd.read_file(f"{ABIT_HOME}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(4326)[["SMZRMZ", "geometry"]].rename(columns={"SMZRMZ": "zone"})
xw = pd.read_csv(f"{RAW}/lodes_wac/md_xwalk.csv.gz", usecols=["tabblk2020", "blklatdd", "blklondd"], dtype={"tabblk2020": str}).dropna()
pts = gpd.GeoDataFrame(xw, geometry=points(xw.blklondd.values, xw.blklatdd.values), crs=4326)
blk = gpd.sjoin(pts, Z, how="left", predicate="within").drop_duplicates("tabblk2020"); miss = blk.zone.isna()
if miss.any():
    near = gpd.sjoin_nearest(blk.loc[miss, ["tabblk2020", "geometry"]].to_crs(26985), Z.to_crs(26985), how="left").drop_duplicates("tabblk2020")
    blk.loc[miss, "zone"] = near.set_index("tabblk2020").zone.reindex(blk.loc[miss, "tabblk2020"]).values
w = pd.read_csv(f"{RAW}/lodes_wac/md_wac_S000_JT00_2016.csv.gz", dtype={"w_geocode": str}).merge(blk[["tabblk2020", "zone"]], left_on="w_geocode", right_on="tabblk2020", how="left")
for t, cols in TYPES.items(): w[t] = w[cols].sum(axis=1)
g = w.dropna(subset=["zone"]).groupby(w.zone.astype("Int64"))[list(TYPES)].sum(); g.index = g.index.astype(int)
md = F.State == 24; before = F.loc[md, [f"{t}16" for t in TYPES]].sum().sum()
for t in TYPES: F.loc[md, f"{t}16"] = (g[t].reindex(F.loc[md, "SMZ"]).fillna(0).values / (1 - rate)).round().astype(int)
# the VAE loader takes the column that contains "2016", otherwise the LAST column; the MSTM file's last column is TOT2040, so the
# original pipeline placed 2016 jobs by the 2040 forecast. Keep only the 2016 columns and end with an explicit 2016 total.
F = F[["SMZ", "FIPS", "aggFips", "State"] + [f"{t}16" for t in TYPES]].copy(); F["TOT2016"] = F[[f"{t}16" for t in TYPES]].sum(axis=1)
F.to_csv(f"{V}/1_vae/output/employment_2016_lodes.csv", index=False)
after = F.loc[md, [f"{t}16" for t in TYPES]].sum().sum()
print(f"Maryland 2016 job inventory: MSTM forecast {before:,.0f} -> LODES {g.sum().sum():,.0f} filled / (1 - {rate}) = {after:,.0f}; blocks placed {blk.zone.notna().mean():.1%}")
print("LODES 2016 by type:", g.sum().astype(int).to_dict())
