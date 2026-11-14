#!/usr/bin/env python3
"""Occupied housing units per MSTM zone from the 2020 Census (PL 94-171 block counts, H1 occupied), for placing synthetic
households inside their PUMA.  Blocks are located by the LODES crosswalk centroid and joined to the zone polygons.
Replaces the earlier weights (MSTM 2016 household file with area-based guesses for zones without a count), which misplaced
households within the Eastern Shore PUMAs.  Output: WORKSPACE/1_vae/output/zone_weights_2020.csv (zone_id, county_fips,
occupied_units_2020); a check against the Census county totals is printed."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, geopandas as gpd, os
from shapely import points
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; OUT = f"{V}/1_vae/output"; os.makedirs(OUT, exist_ok=True)
b = pd.read_csv(f"{V}/data/raw/census2020/md_blocks_2020_housing.csv", dtype={"GEOCODE": str})
xw = pd.read_csv(f"{V}/data/raw/lodes_wac/md_xwalk.csv.gz", usecols=["tabblk2020", "blklatdd", "blklondd"], dtype={"tabblk2020": str}).dropna()
b = b.merge(xw, left_on="GEOCODE", right_on="tabblk2020", how="left"); print(f"blocks {len(b):,}, with a centroid {b.blklatdd.notna().mean():.1%}, occupied units in those {b.loc[b.blklatdd.notna(), 'H1_occupied'].sum():,}")
b = b.dropna(subset=["blklatdd"])
Z = gpd.read_file(f"{ABIT_HOME}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(4326)[["SMZRMZ", "geometry"]].rename(columns={"SMZRMZ": "zone_id"})
pts = gpd.GeoDataFrame(b, geometry=points(b.blklondd.values, b.blklatdd.values), crs=4326)
j = gpd.sjoin(pts, Z, how="left", predicate="within").drop_duplicates("GEOCODE"); miss = j.zone_id.isna()
if miss.any():   # blocks whose centroid falls outside every polygon (coastline): nearest zone
    near = gpd.sjoin_nearest(j.loc[miss, ["GEOCODE", "geometry"]].to_crs(26985), Z.to_crs(26985), how="left").drop_duplicates("GEOCODE")
    j.loc[miss, "zone_id"] = near.set_index("GEOCODE").zone_id.reindex(j.loc[miss, "GEOCODE"]).values
print(f"blocks without a zone after nearest-join: {j.zone_id.isna().sum()}")
w = j.groupby("zone_id").H1_occupied.sum().astype(int).rename("occupied_units_2020").reset_index(); w["zone_id"] = w.zone_id.astype(int)
zs = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv")[["ZoneId", "COUNTYFIPS", "STFIPS"]].rename(columns={"ZoneId": "zone_id", "COUNTYFIPS": "county_fips"})
w = zs.merge(w, on="zone_id", how="left"); w.loc[w.STFIPS != 24, "occupied_units_2020"] = pd.NA     # non-Maryland zones keep the old weights
w.to_csv(f"{OUT}/zone_weights_2020.csv", index=False)
cty = w[w.STFIPS == 24].groupby("county_fips").occupied_units_2020.sum(); cb = b.assign(cty=b.GEOCODE.str[:5].astype(int)).groupby("cty").H1_occupied.sum()
chk = pd.DataFrame({"by_zone": cty, "by_block_county": cb}).dropna(); chk["ratio"] = (chk.by_zone / chk.by_block_county).round(3)
print("zone-aggregated vs block county totals (should be 1.00 everywhere):"); print(chk[(chk.ratio < 0.98) | (chk.ratio > 1.02)].to_string() if ((chk.ratio < 0.98) | (chk.ratio > 1.02)).any() else "  all counties within 2 %")
print(f"Maryland zones with units: {(w[w.STFIPS == 24].occupied_units_2020 > 0).sum()} of {(w.STFIPS == 24).sum()}")
