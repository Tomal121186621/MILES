#!/usr/bin/env python3
"""Vacant housing units per MSTM zone in 2016 from the Censuses (block counts, total minus occupied; 2010 and 2020 interpolated to
2016 like the occupied units in zone_weights_2016.py). The synthetic dwelling stock contains occupied dwellings only; SILO needs the
vacant stock for the moves, construction and pricing models.  Output: 1_vae/output/zone_vacancy_2016.csv (zone_id, county_fips,
vacant_2010, vacant_2020, vacant_2016, occupied_2016, vacancy_rate_2016)."""
import pandas as pd, geopandas as gpd, os
from shapely import points
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; V = f"{ROOT}/Validation_2026"; OUT = f"{V}/1_vae/output"
Z = gpd.read_file(f"{ROOT}/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(4326)[["SMZRMZ", "geometry"]].rename(columns={"SMZRMZ": "zone_id"})
def to_zone(df, lon, lat, key):
    pts = gpd.GeoDataFrame(df, geometry=points(df[lon].astype(float).values, df[lat].astype(float).values), crs=4326)
    j = gpd.sjoin(pts, Z, how="left", predicate="within").drop_duplicates(key); miss = j.zone_id.isna()
    if miss.any():
        near = gpd.sjoin_nearest(j.loc[miss, [key, "geometry"]].to_crs(26985), Z.to_crs(26985), how="left").drop_duplicates(key)
        j.loc[miss, "zone_id"] = near.set_index(key).zone_id.reindex(j.loc[miss, key]).values
    return j
# 2020
b20 = pd.read_csv(f"{V}/data/raw/census2020/md_blocks_2020_housing.csv", dtype={"GEOCODE": str}); b20["vacant"] = b20.H1_total - b20.H1_occupied
xw = pd.read_csv(f"{V}/data/raw/lodes_wac/md_xwalk.csv.gz", usecols=["tabblk2020", "blklatdd", "blklondd"], dtype={"tabblk2020": str}).dropna()
b20 = b20.merge(xw, left_on="GEOCODE", right_on="tabblk2020"); j20 = to_zone(b20, "blklondd", "blklatdd", "GEOCODE"); v20 = j20.groupby("zone_id").vacant.sum()
# 2010: re-parse segment 2 for H1 total and vacant
RAW = f"{V}/data/raw/census2010"; rows = []
with open(f"{RAW}/mdgeo2010.pl", encoding="latin-1") as f:
    for line in f:
        if line[8:11] == "750": rows.append((line[18:25], line[27:29] + line[29:32] + line[54:60] + line[61:65]))
geo = pd.DataFrame(rows, columns=["LOGRECNO", "GEOID10"]); seg2 = pd.read_csv(f"{RAW}/md000022010.pl", header=None, dtype=str, encoding="latin-1")
h = seg2.iloc[:, [4, -3, -2, -1]]; h.columns = ["LOGRECNO", "H1_total", "H1_occupied", "H1_vacant"]; h["LOGRECNO"] = h.LOGRECNO.str.zfill(7)
b10 = geo.merge(h, on="LOGRECNO"); b10["vacant"] = b10.H1_vacant.astype(int)
T = gpd.read_file(f"{RAW}/tl_2010_24_tabblock10.shp")[["GEOID10", "INTPTLAT10", "INTPTLON10"]]; b10 = b10.merge(T, on="GEOID10").dropna(subset=["INTPTLAT10"])
j10 = to_zone(b10, "INTPTLON10", "INTPTLAT10", "GEOID10"); v10 = j10.groupby("zone_id").vacant.sum()
print(f"vacant units Maryland: 2010 {b10.vacant.sum():,} (Census: 2,519,xxx total - 2,156,411 occupied), 2020 {b20.vacant.sum():,}")
w = pd.read_csv(f"{OUT}/zone_weights_2016.csv"); w["vacant_2010"] = w.zone_id.map(v10); w["vacant_2020"] = w.zone_id.map(v20)
md = w.STFIPS == 24; w.loc[md, ["vacant_2010", "vacant_2020"]] = w.loc[md, ["vacant_2010", "vacant_2020"]].fillna(0)
w["vacant_2016"] = (w.vacant_2010 + 0.6 * (w.vacant_2020 - w.vacant_2010)).round(1); w["vacancy_rate_2016"] = (w.vacant_2016 / (w.vacant_2016 + w.occupied_units_2016)).round(4)
w[["zone_id", "county_fips", "STFIPS", "occupied_units_2016", "vacant_2010", "vacant_2020", "vacant_2016", "vacancy_rate_2016"]].to_csv(f"{OUT}/zone_vacancy_2016.csv", index=False)
m = w[md]; print(f"Maryland 2016: vacant {m.vacant_2016.sum():,.0f}, occupied {m.occupied_units_2016.sum():,.0f}, vacancy rate {m.vacant_2016.sum() / (m.vacant_2016.sum() + m.occupied_units_2016.sum()):.3f}; by county min {m.groupby('county_fips').apply(lambda d: d.vacant_2016.sum() / (d.vacant_2016.sum() + d.occupied_units_2016.sum())).min():.3f} max {m.groupby('county_fips').apply(lambda d: d.vacant_2016.sum() / (d.vacant_2016.sum() + d.occupied_units_2016.sum())).max():.3f}")
