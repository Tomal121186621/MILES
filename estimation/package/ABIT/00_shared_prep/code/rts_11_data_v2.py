#!/usr/bin/env python3 -I
"""RTS workplace choice, version 2 records (author decision 2026-10-27): one income group per survey class, and home / work
locations from the survey's traffic zones.

Workers: as rts_01_data.py (fixed usual workplace, j1_workplace_loc = 1, 19,792 persons), same household split (data/rts_split.csv).
Income: each RTS class goes to ONE land-use group by the class midpoint in 2016 $ (CPI-U factor 0.9673, rts_01_data.DEFL):
  1 <15k (7.5k -> 7.3k), 2 15-25k (20k -> 19.3k), 3 25-35k (30k -> 29.0k)          -> <40k
  4 35-50k (42.5k -> 41.1k), 5 50-75k (62.5k -> 60.5k)                              -> 40-75k
  6 75-100k (87.5k -> 84.6k), 7 100-150k (125k -> 120.9k)                            -> 75-125k
  8 150k+ (lower bound 150k -> 145.1k; any midpoint is above 125k)                   -> >=125k
  missing income (-9): left out, as before.
Locations (home and work separately; the rule of taz_crosswalk.py, TAZ_CROSSWALK.md):
  BMC native TAZ10 (1..1387) -> BMC crosswalk; else a valid TPB TAZ -> TPB crosswalk; else a BMC COG-copy TAZ (1400..2934) -> BMC;
  homes with the housing-unit weights (weight_home), workplaces with the job weights (weight_work) of data/taz_*_to_mstm.csv.
  Without a TAZ: the 2010 tract split over zones by its census-block housing units (homes: Maryland 2010 PL 94-171 H1 by block,
  block internal point in zone; the block's tract from the PL geography) or LODES 2017 jobs (workplaces: WAC C000 at the 2020-block
  points of the LODES crosswalk, placed in the 2010 tract and the zone by point in polygon, TIGER 2010 tracts of DE, DC, MD, PA, VA,
  WV).  A tract with no housing units / jobs, or outside these files, keeps the internal-point zone (tract_zone.csv).
  Work weights on zones without 2016 base jobs (not alternatives) are dropped and the rest re-normalised; weights below 1 % are
  dropped and re-normalised (they carry < 0.3 % of the mass), at most 4 zones per location are kept.
Records are dropped when neither a TAZ nor a tract gives a zone in the zone system, or age / split is missing.
Outputs: work_rts/workers_v2.parquet (one row per record, modal zones hz / wz, income group g), work_rts/loc_home_v2.parquet and
loc_work_v2.parquet (person_id, zone, w), tables_rts/drop_log_v2.csv, tables_rts/location_v2_summary.csv.   Usage: rts_11_data_v2.py"""
# COPY of Validation_2026/2_silo/jobchoice/rts_11_data_v2.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "00_shared_data"))          # provided inputs
RAW = _os_pkg.environ.get("ABIT_RAW", _os_pkg.path.join(SHARED, "raw"))                                                              # your downloads
REBUILT = _os_pkg.environ.get("ABIT_REBUILT", _os_pkg.path.join(SHARED, "rebuilt"))                  # outputs of this chain
MDATA = REBUILT
import os, glob, numpy as np, pandas as pd, geopandas as gpd
ROOT = SHARED; V = SHARED; S = SHARED  # PATH: downloads in RAW (census2010, lodes_wac, lodes_wac_2017_extra, tiger_tracts_2010)
JC = f"{RAW}/silo_workplace_work"; W = f"{REBUILT}/taz_crosswalks"; T = f"{REBUILT}/taz_crosswalks/tables_rts"; CRS = 26918; os.makedirs(T, exist_ok=True)  # PATH
DEFL = 240.007 / ((245.120 + 251.107) / 2)
MID = {1: 7500, 2: 20000, 3: 30000, 4: 42500, 5: 62500, 6: 87500, 7: 125000, 8: 150000}
G16 = {c: int(np.digitize(m * DEFL, [40000, 75000, 125000]) + 1) for c, m in MID.items()}
assert G16 == {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3, 8: 4}, G16
cols = ["household_id", "person_id", "j1_workplace_loc", "work_state_county_fips", "work_tract_fips", "home_state_county_fips", "home_tract_fips",
        "home_bmc_taz", "home_tpb_taz", "work_bmc_taz", "work_tpb_taz", "hh_income_detailed", "numvehicle", "numworkers", "hhsize", "wtperfin", "age", "gender"]
r = pd.read_csv(f"{SHARED}/rts_2017_18/raw/RTS_raw_flat_data.csv.gz", usecols=cols, low_memory=False).drop_duplicates("person_id")
p = r[(r.j1_workplace_loc == 1) & (r.work_tract_fips > 0)].copy().reset_index(drop=True)
Z = gpd.read_file(f"{RAW}/mstm_zone_system/SMZ_RMZ_02152011inMSTM_EPSG26918.shp")[["SMZRMZ", "geometry"]].to_crs(CRS).rename(columns={"SMZRMZ": "zone"})
Z["zone"] = Z.zone.astype(int)
jobs16 = pd.read_parquet(f"{JC}/work/zones.parquet").set_index("zone")[["RET", "OFF", "IND", "OTH"]].sum(axis=1)
xb = pd.read_csv(f"{REBUILT}/taz_crosswalks/taz_bmc_to_mstm.csv"); xt = pd.read_csv(f"{REBUILT}/taz_crosswalks/taz_tpb_to_mstm.csv")  # PATH
tz = pd.read_csv(f"{SHARED}/rts_2017_18/survey_pop/tract_zone.csv", dtype={"geoid": str}).set_index("geoid").zone
def gid(c, t):
    ok = (c > 0) & (t > 0) & (t < 999999)
    return pd.Series(np.where(ok, c.clip(lower=0).astype(int).map("{:05d}".format) + t.clip(lower=0).astype(int).map("{:06d}".format), ""), index=c.index)
p["home_geoid"] = gid(p.home_state_county_fips, p.home_tract_fips); p["work_geoid"] = gid(p.work_state_county_fips, p.work_tract_fips)

# ---- tract splits: homes by 2010 block housing units (Maryland), workplaces by LODES 2017 jobs
def zone_of(P):
    j = gpd.sjoin(P, Z, predicate="within", how="left"); return j[~j.index.duplicated()].zone.reindex(P.index).values
f_th = f"{W}/tract_split_home.parquet"; f_tw = f"{W}/tract_split_work.parquet"
if not os.path.exists(f_th):
    geo = []
    with open(f"{RAW}/census2010/mdgeo2010.pl", encoding="latin1") as f:
        for l in f:
            if l[8:11] == "750": geo.append((int(l[18:25]), l[27:32] + l[54:60], float(l[336:347]), float(l[347:359])))
    g = pd.DataFrame(geo, columns=["logrecno", "geoid", "lat", "lon"])
    s2 = pd.read_csv(f"{RAW}/census2010/md000022010.pl", header=None, usecols=[4, 149]); s2.columns = ["logrecno", "hu"]
    g = g.merge(s2, on="logrecno"); g = g[g.hu > 0].reset_index(drop=True)
    g["zone"] = zone_of(gpd.GeoDataFrame(g, geometry=gpd.points_from_xy(g.lon, g.lat), crs=4326).to_crs(CRS))
    g.dropna(subset=["zone"]).groupby(["geoid", "zone"]).hu.sum().rename("n").reset_index().astype({"zone": int}).to_parquet(f_th, index=False)
if not os.path.exists(f_tw):
    xw = pd.concat([pd.read_csv(f"{RAW}/lodes_wac/{s}_xwalk.csv.gz", usecols=["tabblk2020", "blklatdd", "blklondd"], dtype={"tabblk2020": str}) for s in ("md", "dc", "va", "wv", "pa", "de")])
    wac = [pd.read_csv(f"{RAW}/lodes_wac/md_wac_S000_JT00_2017.csv.gz", usecols=["w_geocode", "C000"], dtype={"w_geocode": str})]
    wac += [pd.read_csv(f"{RAW}/lodes_wac_2017_extra/{s}_wac_S000_JT00_2017.csv.gz", usecols=["w_geocode", "C000"], dtype={"w_geocode": str}) for s in ("dc", "va", "wv", "pa", "de")]
    J = pd.concat(wac).merge(xw, left_on="w_geocode", right_on="tabblk2020").reset_index(drop=True)
    P = gpd.GeoDataFrame(J, geometry=gpd.points_from_xy(J.blklondd, J.blklatdd), crs=4326).to_crs(CRS)
    tr = pd.concat([gpd.read_file(f) for f in glob.glob(f"{RAW}/tiger_tracts_2010/tl_2010_*_tract10/*.shp")])[["GEOID10", "geometry"]].to_crs(CRS)
    jt = gpd.sjoin(P, tr, predicate="within", how="left"); J["geoid"] = jt[~jt.index.duplicated()].GEOID10.reindex(P.index).values
    J["zone"] = zone_of(P)
    J.dropna(subset=["geoid", "zone"]).groupby(["geoid", "zone"]).C000.sum().rename("n").reset_index().astype({"zone": int}).to_parquet(f_tw, index=False)
TH = pd.read_parquet(f_th); TW = pd.read_parquet(f_tw)
def lookup(X, col):
    return {k: dict(zip(g.zone, g[col])) for k, g in X[X[col] > 0].groupby(X.columns[0])}
L = {("bmc", "home"): lookup(xb, "weight_home"), ("tpb", "home"): lookup(xt, "weight_home"), ("bmc", "work"): lookup(xb, "weight_work"), ("tpb", "work"): lookup(xt, "weight_work"),
     ("tract", "home"): lookup(TH, "n"), ("tract", "work"): lookup(TW, "n")}
bmc_codes, tpb_codes = set(xb.taz), set(xt.taz)
def pick(b, t):
    bv = b.isin(bmc_codes); tv = t.isin(tpb_codes)
    return np.select([bv & (b <= 1387), tv, bv], ["bmc", "tpb", "bmc"], "tract"), np.select([bv & (b <= 1387), tv, bv], [b, t, b], -1)
rows, srcs = {"home": [], "work": []}, {}
for side in ("home", "work"):
    sysn, taz = pick(p[f"{side}_bmc_taz"], p[f"{side}_tpb_taz"]); src = []
    for i, (s, t, g) in enumerate(zip(sysn, taz, p[f"{side}_geoid"])):
        d, how = None, s
        if s != "tract": d = L[(s, side)].get(int(t))
        if d is None:
            d = L[("tract", side)].get(g); how = "tract split"
            if d is None:
                z0 = tz.get(g, -1); d = {int(z0): 1.0} if z0 > 0 else None; how = "tract point"
        if d is not None and side == "work": d = {z: v for z, v in d.items() if jobs16.get(z, 0) > 0}
        if d:
            tot = sum(d.values()); d = {z: v / tot for z, v in d.items()}
            d = {z: v for z, v in d.items() if v >= 0.01}; d = dict(sorted(d.items(), key=lambda kv: -kv[1])[:4]); tot = sum(d.values())
            for z, v in d.items(): rows[side].append((p.person_id.values[i], int(z), v / tot))
        else: how = "none"
        src.append(how)
    p[f"{side}_src"] = src
log = [dict(step="fixed usual workplace and a work tract code", n=len(p))]
def drop(m, why):
    global p; log.append(dict(step=f"dropped: {why}", n=-int(m.sum()))); p = p[~m].copy()
drop(p.home_src.eq("none"), "home: no TAZ and no tract in the zone system")
drop(p.work_src.eq("none"), "work: no TAZ and no tract in the zone system (or only zones without jobs)")
split = pd.read_csv(f"{SHARED}/rts_2017_18/split/rts_split.csv").set_index("household_id").half; p["half"] = p.household_id.map(split)
drop(p.half.isna(), "household not in the split"); drop(p.age < 0, "age missing")
drop(~p.hh_income_detailed.between(1, 8), "household income missing")
log.append(dict(step="kept", n=len(p))); log += [dict(step=f"kept, {h}", n=int((p.half == h).sum())) for h in ("estimation", "validation")]
LH = pd.DataFrame(rows["home"], columns=["person_id", "zone", "w"]); LW = pd.DataFrame(rows["work"], columns=["person_id", "zone", "w"])
LH = LH[LH.person_id.isin(p.person_id)]; LW = LW[LW.person_id.isin(p.person_id)]
p["hz"] = p.person_id.map(LH.sort_values("w", ascending=False).drop_duplicates("person_id").set_index("person_id").zone)
p["wz"] = p.person_id.map(LW.sort_values("w", ascending=False).drop_duplicates("person_id").set_index("person_id").zone)
p["female"] = (p.gender == 1).astype(int); p["workers"] = p.numworkers.clip(lower=1); p["cars"] = p.numvehicle.clip(lower=0)
p["car_seg"] = np.select([p.cars == 0, p.cars < p.workers], [0, 1], 2); p["g"] = p.hh_income_detailed.map(G16).astype(int)
for g in range(4): p[f"pg{g + 1}"] = (p.g == g + 1).astype(float)
p["inc_known"] = 1; p["state_h"] = p.home_state_county_fips // 1000
ch = []
for half in ("estimation", "validation"):
    pp = pd.read_csv(f"{SHARED}/rts_2017_18/survey_pop/{half}/pp.csv", usecols=["hhID", "age"]); pm = pd.read_csv(f"{SHARED}/rts_2017_18/survey_pop/{half}/persons_map.csv", usecols=["hhID", "household_id"]).drop_duplicates("hhID")
    ch.append(pd.Series(pm.hhID.map((pp.age < 18).groupby(pp.hhID).sum()).values, index=pm.household_id.values))
ch = pd.concat(ch); ch = ch[~ch.index.duplicated()]; p["children"] = p.household_id.map(ch).fillna(0).astype(int)
keep = ["household_id", "person_id", "half", "hz", "wz", "home_src", "work_src", "female", "age", "workers", "cars", "car_seg", "children", "hhsize", "hh_income_detailed", "g",
        "inc_known", "pg1", "pg2", "pg3", "pg4", "wtperfin", "state_h"]
p[keep].reset_index(drop=True).to_parquet(f"{W}/workers_v2.parquet", index=False); LH.to_parquet(f"{W}/loc_home_v2.parquet", index=False); LW.to_parquet(f"{W}/loc_work_v2.parquet", index=False)
D = pd.DataFrame(log); D.to_csv(f"{T}/drop_log_v2.csv", index=False); print(D.to_string(index=False))
nh = LH.groupby("person_id").size(); nw = LW.groupby("person_id").size()
summ = []
for side, Lx in (("home", LH), ("work", LW)):
    n = Lx.groupby("person_id").size(); mx = Lx.groupby("person_id").w.max()
    for s, c in p[f"{side}_src"].value_counts().items(): summ.append(dict(side=side, item=f"source: {s}", value=int(c)))
    summ += [dict(side=side, item="records split over 2+ zones", value=int((n > 1).sum())), dict(side=side, item="mean zones per record", value=float(n.mean())),
             dict(side=side, item="mean largest weight", value=float(mx.mean()))]
old = pd.read_parquet(f"{JC}/work_rts/workers.parquet").set_index("person_id")
q = p.set_index("person_id").join(old[["hz", "wz"]], rsuffix="_v1", how="left")
summ += [dict(side="home", item="modal zone differs from v1 (records in both)", value=float((q.hz != q.hz_v1)[q.hz_v1.notna()].mean())),
         dict(side="work", item="modal zone differs from v1 (records in both)", value=float((q.wz != q.wz_v1)[q.wz_v1.notna()].mean())),
         dict(side="both", item="records not in v1", value=int(q.hz_v1.isna().sum()))]
pd.DataFrame(summ).to_csv(f"{T}/location_v2_summary.csv", index=False); print(pd.DataFrame(summ).to_string(index=False))
print("income groups by midpoint (2016 $):", {c: (round(m * DEFL), G16[c]) for c, m in MID.items()}, p.g.value_counts().sort_index().to_dict())
