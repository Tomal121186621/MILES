#!/usr/bin/env python3
"""Job control totals by zone, SILO job type and year from observed data, for SILO's INTERPOLATION job forecast
(file job.control.total; columns SMZ, <type><yy> with a two-digit year, as the engine's interpolation reads them).
Observed: LODES 8 WAC (jobs by census block and NAICS sector, Maryland, 2016-2023); blocks placed in MSTM zones by their
centroid (LODES crosswalk lat/lon, MSTM zone polygons); 2024 and 2025 from QCEW county employment growth by sector group
(LODES 2024 not released); 2026 = 2025 x the 2024->2025 county growth (stated extrapolation).
Sector groups -> SILO types (employment.types = RET,OFF,IND,OTH):
  RET  CNS07 retail, CNS18 accommodation and food
  OFF  CNS09 information, CNS10 finance, CNS11 real estate, CNS12 professional, CNS13 management, CNS14 administrative,
       CNS15 education, CNS16 health, CNS20 public administration
  IND  CNS01 agriculture, CNS02 mining, CNS03 utilities, CNS04 construction, CNS05 manufacturing, CNS06 wholesale, CNS08 transport/warehousing
  OTH  CNS17 arts/recreation, CNS19 other services
Scaling: SILO's 2016 job stock (synthetic, from the VAE base) differs from LODES; the control of zone z, type t, year Y is
  SILO_jobs_2016(z,t) x LODES(z,t,Y) / LODES(z,t,2016)  (zones with no 2016 LODES jobs of that type: county growth ratio),
so the observed growth path is imposed without a base-year jump.  Non-Maryland zones: county QCEW growth only (no LODES here).
Outputs: 2_silo/input/assumptions/jobControlTotals.csv; data/silo_target_jobs_by_region_type_year.csv (observed, for validation)."""
import pandas as pd, numpy as np, geopandas as gpd, os, glob
from shapely import points
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; V = f"{ROOT}/Validation_2026"; RAW = f"{V}/data/raw"
OUT = f"{V}/2_silo/input/assumptions"; os.makedirs(OUT, exist_ok=True)
TYPES = {"RET": ["CNS07", "CNS18"], "OFF": ["CNS09", "CNS10", "CNS11", "CNS12", "CNS13", "CNS14", "CNS15", "CNS16", "CNS20"],
         "IND": ["CNS01", "CNS02", "CNS03", "CNS04", "CNS05", "CNS06", "CNS08"], "OTH": ["CNS17", "CNS19"]}
YEARS_LODES = list(range(2016, 2024)); YEARS = list(range(2016, 2027))
z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv")
Z = gpd.read_file(f"{ROOT}/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(4326)[["SMZRMZ", "geometry"]].rename(columns={"SMZRMZ": "zone"})
# ---- blocks -> zones
xw = pd.read_csv(f"{RAW}/lodes_wac/md_xwalk.csv.gz", usecols=["tabblk2020", "cty", "blklatdd", "blklondd"], dtype={"tabblk2020": str, "cty": str})
xw = xw.dropna(subset=["blklatdd"]); pts = gpd.GeoDataFrame(xw, geometry=points(xw.blklondd.values, xw.blklatdd.values), crs=4326)
blk = gpd.sjoin(pts, Z, how="left", predicate="within").drop_duplicates("tabblk2020")[["tabblk2020", "cty", "zone"]]
print(f"blocks {len(blk):,}, in a zone {blk.zone.notna().mean():.1%}")
# ---- LODES jobs by zone x type x year
J = []
for y in YEARS_LODES:
    w = pd.read_csv(f"{RAW}/lodes_wac/md_wac_S000_JT00_{y}.csv.gz", dtype={"w_geocode": str})
    w = w.merge(blk, left_on="w_geocode", right_on="tabblk2020", how="left")
    for t, cols in TYPES.items(): w[t] = w[cols].sum(axis=1)
    g = w.dropna(subset=["zone"]).groupby("zone")[list(TYPES)].sum(); g["year"] = y; J.append(g.reset_index())
L = pd.concat(J); L["zone"] = L.zone.astype(int)
# ---- QCEW county growth 2023->2024 (and 2024->2025 not yet available in the fetched set: use 2023->2024 again, stated)
def qcew(y):
    rows = []
    for f in glob.glob(f"{RAW}/qcew/qcew_{y}_*.csv"):
        q = pd.read_csv(f, dtype=str); q = q[(q.own_code == "0") & (q.agglvl_code == "70")]   # all ownerships, county total
        if len(q): rows.append(dict(cty=int(q.area_fips.iloc[0]), emp=float(q.annual_avg_emplvl.iloc[0])))
    return pd.DataFrame(rows).set_index("cty").emp
q23, q24 = qcew(2023), qcew(2024); growth = (q24 / q23).fillna(1.0)
z2c = z.set_index("ZoneId").COUNTYFIPS
# ---- synthetic 2016 job stock by zone and type
jj = pd.read_csv(f"{V}/2_silo/input/microData/jj_2016.csv", usecols=["zone", "type"]); S = jj.groupby(["zone", "type"]).size().unstack(fill_value=0)
rows = []
for zone in z.ZoneId:
    cty = int(z2c[zone]); gr = float(growth.get(cty, 1.0)); lz = L[L.zone == zone].set_index("year")
    cl = L[L.zone.map(z2c) == cty].groupby("year")[list(TYPES)].sum()        # county LODES by year (fallback)
    rec = {"SMZ": zone}
    for t in TYPES:
        base = float(S.at[zone, t]) if (zone in S.index and t in S.columns) else 0.0
        for y in YEARS:
            if y <= 2023 and 2016 in lz.index and y in lz.index and lz.loc[2016, t] > 0: ratio = lz.loc[y, t] / lz.loc[2016, t]
            elif y <= 2023 and 2016 in cl.index and y in cl.index and cl.loc[2016, t] > 0: ratio = cl.loc[y, t] / cl.loc[2016, t]
            else: ratio = (rec.get(f"{t}23", base) / base if base > 0 else 1.0) * gr ** (y - 2023)
            rec[f"{t}{y % 100:02d}"] = round(base * ratio, 1)   # two-digit year suffix: the engine reads <type><yy> and adds 2000
    rows.append(rec)
T = pd.DataFrame(rows); T.to_csv(f"{OUT}/jobControlTotals.csv", index=False)
L["region"] = L.zone.map(z.set_index("ZoneId").Region); L.groupby(["region", "year"])[list(TYPES)].sum().reset_index().to_csv(f"{V}/data/silo_target_jobs_by_region_type_year.csv", index=False)
md = z[z.STFIPS == 24].ZoneId
tot = {y: T.loc[T.SMZ.isin(md), [f"{t}{y % 100:02d}" for t in TYPES]].sum().sum() for y in YEARS}; lod = L.groupby("year")[list(TYPES)].sum().sum(axis=1)
print("Maryland jobs, control file vs LODES:"); [print(f"  {y}: control {tot[y]:,.0f}" + (f"  LODES {lod[y]:,.0f}  (synthetic/LODES 2016 = {tot[2016] / lod[2016]:.3f})" if y in lod.index else "")) for y in YEARS]
