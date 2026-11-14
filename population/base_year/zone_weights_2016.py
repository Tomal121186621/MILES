#!/usr/bin/env python3
"""Occupied housing units per MSTM zone in 2016, interpolated between the two censuses that count every unit:
  units_2016(zone) = units_2010(zone) + 0.6 x (units_2020(zone) - units_2010(zone))
2010: PL 94-171 Maryland block counts (H1 occupied), blocks located by the TIGER 2010 internal point; 2020: from zone_weights_2020.py.
Output: 1_vae/output/zone_weights_2016.csv (zone_id, county_fips, occupied_units_2010, _2020, _2016)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, geopandas as gpd, os
from shapely import points
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; RAW = f"{V}/data/raw/census2010"; OUT = f"{V}/1_vae/output"
# 2010 geo header is fixed width: SUMLEV cols 9-11, LOGRECNO 19-25, STATE 28-29, COUNTY 30-32, TRACT 55-60, BLOCK 62-65 (1-based)
rows = []
with open(f"{RAW}/mdgeo2010.pl", encoding="latin-1") as f:
    for line in f:
        if line[8:11] == "750": rows.append((line[18:25], line[27:29] + line[29:32] + line[54:60] + line[61:65]))
geo = pd.DataFrame(rows, columns=["LOGRECNO", "GEOID10"])
seg2 = pd.read_csv(f"{RAW}/md000022010.pl", header=None, dtype=str, encoding="latin-1")     # 2010 segment 2: P3, P4, H1; 5 header fields
h = seg2.iloc[:, [4, -2]]; h.columns = ["LOGRECNO", "H1_occupied"]; h["LOGRECNO"] = h.LOGRECNO.str.zfill(7)
b = geo.merge(h, on="LOGRECNO"); b["H1_occupied"] = b.H1_occupied.astype(int)
print(f"2010 blocks {len(b):,}, occupied units {b.H1_occupied.sum():,} (Census 2010 Maryland: 2,156,411 published)")
T = gpd.read_file(f"{RAW}/tl_2010_24_tabblock10.shp")[["GEOID10", "INTPTLAT10", "INTPTLON10"]]
b = b.merge(T, on="GEOID10", how="left"); b = b.dropna(subset=["INTPTLAT10"])
Z = gpd.read_file(f"{ABIT_HOME}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(4326)[["SMZRMZ", "geometry"]].rename(columns={"SMZRMZ": "zone_id"})
pts = gpd.GeoDataFrame(b, geometry=points(b.INTPTLON10.astype(float).values, b.INTPTLAT10.astype(float).values), crs=4326)
j = gpd.sjoin(pts, Z, how="left", predicate="within").drop_duplicates("GEOID10"); miss = j.zone_id.isna()
if miss.any():
    near = gpd.sjoin_nearest(j.loc[miss, ["GEOID10", "geometry"]].to_crs(26985), Z.to_crs(26985), how="left").drop_duplicates("GEOID10")
    j.loc[miss, "zone_id"] = near.set_index("GEOID10").zone_id.reindex(j.loc[miss, "GEOID10"]).values
u10 = j.groupby("zone_id").H1_occupied.sum().rename("occupied_units_2010"); u10.index = u10.index.astype(int)
w = pd.read_csv(f"{OUT}/zone_weights_2020.csv").merge(u10.reset_index().rename(columns={"index": "zone_id"}), on="zone_id", how="left")
md = w.STFIPS == 24
w.loc[md, "occupied_units_2010"] = w.loc[md, "occupied_units_2010"].fillna(0)
w["occupied_units_2016"] = (w.occupied_units_2010 + 0.6 * (w.occupied_units_2020 - w.occupied_units_2010)).round(1)
w.to_csv(f"{OUT}/zone_weights_2016.csv", index=False)
c = w[md].groupby("county_fips")[["occupied_units_2010", "occupied_units_2020", "occupied_units_2016"]].sum()
print(f"Maryland 2010 {c.occupied_units_2010.sum():,.0f} -> 2016 {c.occupied_units_2016.sum():,.0f} -> 2020 {c.occupied_units_2020.sum():,.0f} occupied units")
print("zone shares within county, 2010 vs 2020: mean abs change of a zone's share " + f"{(w[md].groupby('county_fips').apply(lambda d: (d.occupied_units_2020 / d.occupied_units_2020.sum() - d.occupied_units_2010 / d.occupied_units_2010.sum()).abs().sum() / 2)).mean():.3f} (of 1.0)")
