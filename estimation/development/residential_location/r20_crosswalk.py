#!/usr/bin/env python3
"""Corrected zone -> PUMA / migration-PUMA crosswalk (2026-11-18m).  s01_geography.py links zones to PUMAs through the internal points
of 2010 tracts; 252 zones (229k SILO 2016 dwellings) contain no tract point and had no row in geo_puma_zone / geo_mig_zone (in r14 they
had weight 0 and 'first PUMA' index 0 = 1000101).  Here every such zone gets the 2010 PUMA containing its centroid: centroid -> 2010
TIGER tract polygon (tracts nest in 2010 PUMAs; all six states are available as tracts, the 2010 PUMA polygons only for MD) ->
Census 2010 tract-to-PUMA file; centroids outside every tract (water) -> nearest tract.  MD results are cross-checked against the
TIGER 2010 PUMA polygons.  The migration PUMA follows from the PUMA (geo_puma_mig).
Housing-unit weight of an added zone: SILO 2016 dwellings of the zone (its tracts' HU10 are already counted in the zones holding their
internal points, so no tract HU is left for it).  The 4 zones whose crosswalk HU are all 0 (80, 139, 369, 405) get the same weight.
Within a zone only the hu SHARE across PUMAs is used (r14.geography), so the scale of hu does not matter for these single-PUMA zones.
Coverage columns (PUMA / MIGPUMA coverage of the zone system, from tracts) are not changed.
Writes r20_geo_puma_zone.csv, r20_geo_mig_zone.csv, r20_zone_puma_added.csv (this folder; work/ files untouched)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, zipfile
import numpy as np, pandas as pd, geopandas as gpd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; V = WORKSPACE   # HERE: results of this step (data); CODE: this folder
sys.path.insert(0, f"{MILES_HOME}/landuse/lib/residential")
from rc import WORK, RAW, INP, STATES   # noqa: E402


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
    a.to_csv(f"{HERE}/r20_zone_puma_added.csv", index=False)
    # PUMA <-> zone: add the zones; crosswalk-zero zones -> hu = SILO dwellings
    zero = pz.groupby("zone").hu.transform("sum") == 0
    print(f"crosswalk-zero zones re-weighted: {sorted(pz[zero].zone.unique())}")
    pz2 = pz.copy(); pz2.loc[zero, "hu"] = pz2.loc[zero, "zone"].map(gz.dwellings).values
    pz2 = pd.concat([pz2, pd.DataFrame({"puma7": a.puma7, "zone": a.zone, "hu": a.dwellings})]).sort_values(["puma7", "zone"])
    pz2.to_csv(f"{HERE}/r20_geo_puma_zone.csv", index=False)
    # MIGPUMA <-> zone: hu as above, w_dd / w_jobs = SILO dwellings / jobs, coverage of the MIGPUMA unchanged
    cov = mz.groupby("mig7").coverage.first(); mz2 = mz.copy(); zm = mz2.zone.isin(pz[zero].zone.unique())
    mz2.loc[zm, "hu"] = mz2.loc[zm, "zone"].map(gz.dwellings).values
    add = pd.DataFrame({"mig7": a.mig7.astype(int), "zone": a.zone, "hu": a.dwellings, "w_dd": a.dwellings, "w_jobs": a.jobs, "coverage": a.mig7.map(cov)})
    mz2 = pd.concat([mz2, add]).sort_values(["mig7", "zone"]); mz2.to_csv(f"{HERE}/r20_geo_mig_zone.csv", index=False)
    print(f"wrote r20_geo_puma_zone.csv ({len(pz2)} rows, {pz2.zone.nunique()} zones), r20_geo_mig_zone.csv ({len(mz2)} rows, {mz2.zone.nunique()} zones)")
    print(a.groupby(a.puma7 // 100000).agg(zones=("zone", "size"), dwellings=("dwellings", "sum")).to_string())


if __name__ == "__main__":
    main()
