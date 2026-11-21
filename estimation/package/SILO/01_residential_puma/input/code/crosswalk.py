#!/usr/bin/env python3
"""Zone -> PUMA / migration-PUMA crosswalk with every zone (copy of the project script; paths changed, marked "# PATH (package)").  s01_geography.py links zones to PUMAs through the internal points
of 2010 tracts; 252 zones (229k SILO 2016 dwellings) contain no tract point and had no row in geo_puma_zone / geo_mig_zone (without the
correction they have no weight and no PUMA).  Here every such zone gets the 2010 PUMA containing its centroid: centroid -> 2010
TIGER tract polygon (tracts nest in 2010 PUMAs; all six states are available as tracts, the 2010 PUMA polygons only for MD) ->
Census 2010 tract-to-PUMA file; centroids outside every tract (water) -> nearest tract.  MD results are cross-checked against the
TIGER 2010 PUMA polygons.  The migration PUMA follows from the PUMA (geo_puma_mig).
Housing-unit weight of an added zone: SILO 2016 dwellings of the zone (its tracts' HU10 are already counted in the zones holding their
internal points, so no tract HU is left for it).  The 4 zones whose crosswalk HU are all 0 (80, 139, 369, 405) get the same weight.
Within a zone only the hu SHARE across PUMAs is used (two_level.geography), so the scale of hu does not matter for these single-PUMA zones.
Coverage columns (PUMA / MIGPUMA coverage of the zone system, from tracts) are not changed.
Writes 00_shared_data/resloc_work/geo_puma_zone_all.csv, geo_mig_zone_all.csv, zone_puma_added.csv.
Needs geopandas and the project's raw files: 2010 TIGER tracts (data/raw/tiger_tracts_2010), 2010 MD PUMA polygons (data/raw/tiger_puma),
the Census 2010 tract-to-PUMA file (data/raw/resloc)."""
import os, sys, zipfile
import numpy as np, pandas as pd, geopandas as gpd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rc import WORK, INP, STATES, V   # noqa: E402  (package rc: WORK, INP in 00_shared_data)
RAW = f"{V}/data/raw/resloc"   # PATH (package): project copy of the Census 2010 tract-to-PUMA file


def main():
    pz = pd.read_csv(f"{WORK}/geo_puma_zone.csv"); mz = pd.read_csv(f"{WORK}/geo_mig_zone.csv"); pm = pd.read_csv(f"{WORK}/geo_puma_mig.csv")
    gz = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone"); zs = pd.read_csv(f"{INP}/zoneSystem.csv").set_index("ZoneId")
    zp = gpd.read_file(f"{INP}/zones.shp")[["id", "geometry"]]
    miss = sorted(set(zp.id.astype(int)) - set(pz.zone)); print(f"zones without a crosswalk row: {len(miss)}, SILO dwellings {gz.dwellings.reindex(miss).sum():,.0f}")
    tr = pd.concat([gpd.read_file(f"{V}/data/raw/tiger_tracts_2010/tl_2010_{st:02d}_tract10.zip")[["GEOID10", "geometry"]] for st in STATES.values()]).to_crs(zp.crs)
    tp = pd.read_csv(f"{RAW}/2010_Census_Tract_to_2010_PUMA.txt", dtype=str); tp["geoid"] = tp.STATEFP + tp.COUNTYFP + tp.TRACTCE
    tp["puma7"] = tp.STATEFP.astype(int) * 100000 + tp.PUMA5CE.astype(int); t2p = tp.set_index("geoid").puma7
    c = zp[zp.id.isin(miss)].copy(); c["geometry"] = c.geometry.centroid
    j = gpd.sjoin(c, tr, how="left", predicate="within").drop_duplicates("id")
    out = j[j.GEOID10.isna()][["id", "geometry"]]
    if len(out):
        jn = gpd.sjoin_nearest(gpd.GeoDataFrame(out, crs=zp.crs), tr, how="left").drop_duplicates("id").set_index("id").GEOID10
        j.loc[j.GEOID10.isna(), "GEOID10"] = j.loc[j.GEOID10.isna(), "id"].map(jn)
    j["puma7"] = j.GEOID10.map(t2p); j["nearest"] = j.id.isin(out.id)
    assert j.puma7.notna().all(), "tract without PUMA"
    a = pd.DataFrame({"zone": j.id.astype(int).values, "tract": j.GEOID10.values, "puma7": j.puma7.astype(int).values, "nearest_tract": j.nearest.values})
    a["PUMA_10_zoneSystem"] = zs.PUMA_10.reindex(a.zone).values; a["dwellings"] = gz.dwellings.reindex(a.zone).values; a["jobs"] = gz.jobs.reindex(a.zone).values
    # MD cross-check with the 2010 PUMA polygons
    pp = gpd.read_file(f"{V}/data/raw/tiger_puma/tl_2020_24_puma10.zip").to_crs(zp.crs); pp["p7"] = 2400000 + pp.PUMACE10.astype(int)
    k = gpd.sjoin(c, pp[["p7", "geometry"]], how="left", predicate="within").drop_duplicates("id").set_index("id").p7
    a["puma7_md_polygon"] = a.zone.map(k)
    md = a.puma7 // 100000 == 24
    print(f"centroid outside every tract (nearest tract): {a.nearest_tract.sum()}; MD zones {md.sum()}, polygon check agrees {(a.puma7 == a.puma7_md_polygon)[md].sum()} "
          f"(no polygon hit {a.puma7_md_polygon[md].isna().sum()}); agrees with zoneSystem PUMA_10 {(a.puma7 == a.PUMA_10_zoneSystem).sum()} of {len(a)}")
    assert a.puma7.isin(pz.puma7).all(), "added zone in a PUMA outside the model"
    a["mig7"] = a.puma7.map(pm.drop_duplicates("puma7").set_index("puma7").mig7); assert a.mig7.notna().all() and a.mig7.isin(mz.mig7).all()
    a.to_csv(f"{WORK}/zone_puma_added.csv", index=False)   # PATH (package)
    # PUMA <-> zone: add the zones; crosswalk-zero zones -> hu = SILO dwellings
    zero = pz.groupby("zone").hu.transform("sum") == 0
    print(f"crosswalk-zero zones re-weighted: {sorted(pz[zero].zone.unique())}")
    pz2 = pz.copy(); pz2.loc[zero, "hu"] = pz2.loc[zero, "zone"].map(gz.dwellings).values
    pz2 = pd.concat([pz2, pd.DataFrame({"puma7": a.puma7, "zone": a.zone, "hu": a.dwellings})]).sort_values(["puma7", "zone"])
    pz2.to_csv(f"{WORK}/geo_puma_zone_all.csv", index=False)   # PATH (package)
    # MIGPUMA <-> zone: hu as above, w_dd / w_jobs = SILO dwellings / jobs, coverage of the MIGPUMA unchanged
    cov = mz.groupby("mig7").coverage.first(); mz2 = mz.copy(); zm = mz2.zone.isin(pz[zero].zone.unique())
    mz2.loc[zm, "hu"] = mz2.loc[zm, "zone"].map(gz.dwellings).values
    add = pd.DataFrame({"mig7": a.mig7.astype(int), "zone": a.zone, "hu": a.dwellings, "w_dd": a.dwellings, "w_jobs": a.jobs, "coverage": a.mig7.map(cov)})
    mz2 = pd.concat([mz2, add]).sort_values(["mig7", "zone"]); mz2.to_csv(f"{WORK}/geo_mig_zone_all.csv", index=False)   # PATH (package)
    print(f"wrote geo_puma_zone_all.csv ({len(pz2)} rows, {pz2.zone.nunique()} zones), geo_mig_zone_all.csv ({len(mz2)} rows, {mz2.zone.nunique()} zones)")
    print(a.groupby(a.puma7 // 100000).agg(zones=("zone", "size"), dwellings=("dwellings", "sum")).to_string())


if __name__ == "__main__":
    main()
