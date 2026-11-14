#!/usr/bin/env python3
"""Block-based crosswalks for the tract-level validation (no model data touched).
2020 Census blocks (PL 94-171: P1_001 population, P5_001 group-quarters population, H1_002 occupied units) for the six study
counties are located by the LODES 8 crosswalk internal point and joined to the 1,588 MSTM zone polygons (same rule as
1_vae/zone_weights_2020.py: point-in-polygon, nearest zone for coastline misses).  2010 blocks (PL 2010 H1 occupied) likewise
by the TIGER 2010 internal point (for 2010-tract ACS 2012-16 apportionment).
Outputs (out/):  blocks2020.parquet  (block, tract, county, zone, pop, gq, hhpop, hu_occ)
                 blocks2010.parquet  (block10, tract10, zone, hu_occ10)
                 lodes_block_zone.parquet (every MD 2020 block: block, tract, zone)  -- for LODES WAC/OD
"""
import pandas as pd, geopandas as gpd, numpy as np, os
from shapely import points
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; V = f"{ROOT}/Validation_2026"
RAW = f"{V}/data/raw"; OUT = f"{V}/5_reports/validation_tracts/out"; os.makedirs(OUT, exist_ok=True)
CTY = ["24003", "24005", "24013", "24025", "24027", "24510"]
Z = gpd.read_file(f"{ROOT}/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(4326)[["SMZRMZ", "geometry"]].rename(columns={"SMZRMZ": "zone"})

def locate(df, idcol, lon, lat):
    pts = gpd.GeoDataFrame(df[[idcol]].copy(), geometry=points(df[lon].astype(float).values, df[lat].astype(float).values), crs=4326)
    j = gpd.sjoin(pts, Z, how="left", predicate="within").drop_duplicates(idcol); miss = j.zone.isna()
    if miss.any():
        near = gpd.sjoin_nearest(j.loc[miss, [idcol, "geometry"]].to_crs(26985), Z.to_crs(26985), how="left").drop_duplicates(idcol)
        j.loc[miss, "zone"] = near.set_index(idcol).zone.reindex(j.loc[miss, idcol]).values
    return j.set_index(idcol).zone.astype(int)

# ---- 2020 PL blocks
P = f"{RAW}/census2020"
geo = pd.read_csv(f"{P}/mdgeo2020.pl", sep="|", header=None, usecols=[2, 7, 9], dtype=str, encoding="latin-1"); geo.columns = ["SUMLEV", "LOGRECNO", "GEOCODE"]
geo = geo[geo.SUMLEV == "750"]
s1 = pd.read_csv(f"{P}/md000012020.pl", sep="|", header=None, usecols=[4, 5], dtype={4: str}); s1.columns = ["LOGRECNO", "pop"]
s3 = pd.read_csv(f"{P}/md000032020.pl", sep="|", header=None, usecols=[4, 5], dtype={4: str}); s3.columns = ["LOGRECNO", "gq"]
s2 = pd.read_csv(f"{P}/md000022020.pl", sep="|", header=None, dtype=str)
s2 = pd.DataFrame({"LOGRECNO": s2.iloc[:, 4], "hu_occ": s2.iloc[:, -2].astype(int)}); del_ = None
b = geo.merge(s1, on="LOGRECNO").merge(s3, on="LOGRECNO").merge(s2, on="LOGRECNO")
b["block"] = b.GEOCODE; b["tract"] = b.block.str[:11]; b["county"] = b.block.str[:5]; b["hhpop"] = b["pop"] - b["gq"]
xw = pd.read_csv(f"{RAW}/lodes_wac/md_xwalk.csv.gz", usecols=["tabblk2020", "blklatdd", "blklondd"], dtype={"tabblk2020": str})
allmd = xw.rename(columns={"tabblk2020": "block"}); allmd["zone"] = locate(allmd, "block", "blklondd", "blklatdd").reindex(allmd.block).values
allmd["tract"] = allmd.block.str[:11]; allmd[["block", "tract", "zone"]].to_parquet(f"{OUT}/lodes_block_zone.parquet", index=False)
b = b[b.county.isin(CTY)].merge(allmd[["block", "zone"]], on="block", how="left")
print(f"2020 blocks in study area {len(b):,}; pop {b['pop'].sum():,}; hh pop {b.hhpop.sum():,}; occupied {b.hu_occ.sum():,}; no zone {b.zone.isna().sum()}")
b[["block", "tract", "county", "zone", "pop", "gq", "hhpop", "hu_occ"]].to_parquet(f"{OUT}/blocks2020.parquet", index=False)

# ---- 2010 PL blocks (occupied units) for 2010-tract apportionment
R10 = f"{RAW}/census2010"; rows = []
with open(f"{R10}/mdgeo2010.pl", encoding="latin-1") as f:
    for line in f:
        if line[8:11] == "750": rows.append((line[18:25], line[27:29] + line[29:32] + line[54:60] + line[61:65]))
g10 = pd.DataFrame(rows, columns=["LOGRECNO", "block10"])
s = pd.read_csv(f"{R10}/md000022010.pl", header=None, dtype=str, encoding="latin-1"); h = pd.DataFrame({"LOGRECNO": s.iloc[:, 4].str.zfill(7), "hu_occ10": s.iloc[:, -2].astype(int)})
b10 = g10.merge(h, on="LOGRECNO"); b10 = b10[b10.block10.str[:5].isin(CTY)]
T = gpd.read_file(f"{R10}/tl_2010_24_tabblock10.dbf", columns=["GEOID10", "INTPTLAT10", "INTPTLON10"], ignore_geometry=True)
b10 = b10.merge(T, left_on="block10", right_on="GEOID10")
b10["zone"] = locate(b10, "block10", "INTPTLON10", "INTPTLAT10").reindex(b10.block10).values; b10["tract10"] = b10.block10.str[:11]
print(f"2010 blocks in study area {len(b10):,}; occupied {b10.hu_occ10.sum():,}")
b10[["block10", "tract10", "zone", "hu_occ10"]].to_parquet(f"{OUT}/blocks2010.parquet", index=False)
