#!/usr/bin/env python3 -I
# Copy of 2_silo/schoolchoice/sc_01_data.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""RTS school location choice: records, home / school location mixtures, zone size components, counts table.

Students (RTS_raw_flat_data.csv, one row per person after drop_duplicates('person_id')): student_status = 1 and school_type
  2 K-8 -> segment k8 (ages 5-14), 3 9th-12th -> hs (ages 13-19), 6 2-year / 7 4-year / 8 graduate -> col (age 16+; pooled);
  excluded: 1 daycare / pre-school, 4 home school, 5 vocational, 9 other (no inventory), school_freq = 8 (online only).
Income: the RTS class -> one land-use group by its midpoint in 2016 $ (rts_11_data_v2.G16); missing income dropped.
Household split: data/rts_split.csv (the workplace model's split).
Home locations: exactly rts_11_data_v2 (TAZ crosswalk weight_home, else the 2010 tract split by block housing units, else the tract
  internal point; weights >= 1 %, at most 4 zones).
School locations: BMC TAZ10 (1..1387) -> BMC; else valid TPB TAZ -> TPB; else BMC 1400..2934 -> BMC (TAZ_CROSSWALK.md rule).
  Within a TAZ the school is split over MSTM zones by the enrolment of the record's band of the inventory school points inside the
  TAZ (BMC layer14 / TPB 3722 polygons); a TAZ without a school of the band falls back to the job weights (weight_work).  Without a
  TAZ: the 2010 tract split by the band's enrolment of the school points in the tract, else the tract's LODES job split
  (jobchoice/work_rts/tract_split_work.parquet), else the tract point.  Only zones with enrolment of the band are kept (a record
  with none left is dropped); weights >= 1 %, at most 4 zones.  College only: a location whose zones have no post-secondary
  enrolment (IPEDS has one point per institution, campuses span zones) is snapped to the nearest zone with post-secondary enrolment
  if the zone centroids are within 3 km of the location's most likely zone.
Size components (work/zone_size.parquet): sc_common.COMP, enrolment (capacity column) of input/schools_2016.csv by zone and band.
Outputs work/students.parquet, loc_home.parquet, loc_school.parquet, school_points.parquet; tables/counts.csv, drop_log.csv,
location_summary.csv.   Usage: python3 -I sc_01_data.py"""
import os, sys, glob, zipfile, numpy as np, pandas as pd, geopandas as gpd
sys.path.insert(0, "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026/2_silo/schoolchoice")
import sc_common as C   # noqa: E402
ROOT, V, RAW, JC, W, T, CRS = C.ROOT, C.V, C.RAW, C.JC, C.W, C.T, C.CRS
DEFL = 240.007 / ((245.120 + 251.107) / 2)
MID = {1: 7500, 2: 20000, 3: 30000, 4: 42500, 5: 62500, 6: 87500, 7: 125000, 8: 150000}
G16 = {c: int(np.digitize(m * DEFL, [40000, 75000, 125000]) + 1) for c, m in MID.items()}
# ---- inventory: school points, components, zone size
s = pd.read_csv(f"{C.S}/input/schools_2016.csv")
z_ = zipfile.ZipFile(f"{RAW}/ipeds/HD2024.zip"); hd = pd.read_csv(z_.open("HD2024.csv"), encoding="latin1", low_memory=False)
hd.columns = [c.strip().replace("﻿", "").replace("ï»¿", "") for c in hd.columns]; sector = hd.set_index("UNITID").SECTOR
s["comp"] = np.where(s.sector == "public", "pub", np.where(s.sector == "private", "priv", ""))
ps = s.type == 3; sec = s.loc[ps, "source_id"].astype(int).map(sector)
s.loc[ps, "comp"] = np.select([sec == 1, sec.isin([2, 3])], ["pub4", "priv4"], "cc"); s["ipeds_sector"] = np.nan; s.loc[ps, "ipeds_sector"] = sec
s = s[s.capacity > 0].copy()
s[["id", "zone", "band", "comp", "sector", "capacity", "coordX", "coordY", "source_id", "district", "state_fips", "county_fips", "name", "ipeds_sector"]].to_parquet(f"{W}/school_points.parquet", index=False)
zs = s.groupby(["zone", "band", "comp"]).capacity.sum().rename("n").reset_index(); zs.to_parquet(f"{W}/zone_size.parquet", index=False)
bandz = {b: set(g.zone) for b, g in zs.groupby("band")}
# ---- school weights inside TAZ / tract by band
P = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.coordX, s.coordY), crs=CRS)
bmc = gpd.read_file(f"{RAW}/taz_bmc/layer14.geojson").to_crs(CRS).rename(columns={"TAZ10": "taz"})[["taz", "geometry"]]
tpb = pd.concat([gpd.read_file(f) for f in sorted(glob.glob(f"{RAW}/taz_tpb/rest_layer0_off*.geojson"))]).to_crs(CRS)
tpb = gpd.GeoDataFrame(tpb.rename(columns={"TAZ": "taz"})[["taz", "geometry"]], crs=CRS)
tr = pd.concat([gpd.read_file(f) for f in glob.glob(f"{RAW}/tiger_tracts_2010/tl_2010_*_tract10/*.shp")])[["GEOID10", "geometry"]].to_crs(CRS).rename(columns={"GEOID10": "taz"})
def sw(poly):
    j = gpd.sjoin(P, poly, predicate="within", how="inner"); j = j[~j.index.duplicated()]
    return {(t, b): dict(g.groupby("zone").capacity.sum()) for (t, b), g in j.groupby(["taz", "band"])}
SW = {"bmc": sw(bmc.astype({"taz": int})), "tpb": sw(tpb.astype({"taz": int})), "tract": sw(tr)}
# ---- RTS students
cols = ["household_id", "person_id", "age", "gender", "license", "student_status", "school_type", "school_freq", "school_mode", "school_state_county_fips", "school_tract_fips",
        "school_bmc_taz", "school_tpb_taz", "home_state_county_fips", "home_tract_fips", "home_bmc_taz", "home_tpb_taz", "hh_income_detailed", "numvehicle", "numdrivers",
        "numworkers", "hhsize", "wtperfin"]
r = pd.read_csv(f"{ROOT}/ABIT/input/rts/RTS_raw_flat_data.csv", usecols=cols, low_memory=False).drop_duplicates("person_id")
log = [dict(step="persons (deduplicated by person_id)", n=len(r))]
SEGMAP = {2: "k8", 3: "hs", 6: "col", 7: "col", 8: "col"}
r = r[r.student_status == 1].copy(); log.append(dict(step="student_status = 1", n=len(r)))
for st, why in ((1, "daycare / pre-school"), (4, "home school"), (5, "vocational / technical (no inventory)"), (9, "other school type"), (-9, "school type missing")):
    log.append(dict(step=f"dropped: {why}", n=-int((r.school_type == st).sum())))
p = r[r.school_type.isin(SEGMAP)].copy(); p["seg"] = p.school_type.map(SEGMAP)
def drop(m, why):
    global p
    for sg in C.SEG: log.append(dict(step=f"dropped: {why}", seg=sg, n=-int((m & (p.seg == sg)).sum())))
    p = p[~m].copy()
drop(p.school_freq == 8, "online classes only (school_freq 8)")
agebad = ((p.seg == "k8") & ~p.age.between(5, 14)) | ((p.seg == "hs") & ~p.age.between(13, 19)) | ((p.seg == "col") & (p.age < 16))
drop(agebad, "age missing or outside the segment's range (K-8 5-14, 9-12 13-19, college 16+)")
p["band"] = C.band_of("k8", p.age.values); p.loc[p.seg == "hs", "band"] = "high"; p.loc[p.seg == "col", "band"] = "postsec"
xb = pd.read_csv(f"{V}/data/taz_bmc_to_mstm.csv"); xt = pd.read_csv(f"{V}/data/taz_tpb_to_mstm.csv")
tz = pd.read_csv(f"{V}/3_abit/survey_pop/tract_zone.csv", dtype={"geoid": str}).set_index("geoid").zone
TH = pd.read_parquet(f"{JC}/work_rts/tract_split_home.parquet"); TW = pd.read_parquet(f"{JC}/work_rts/tract_split_work.parquet")
def lookup(X, col): return {k: dict(zip(g.zone, g[col])) for k, g in X[X[col] > 0].groupby(X.columns[0])}
L = {("bmc", "home"): lookup(xb, "weight_home"), ("tpb", "home"): lookup(xt, "weight_home"), ("bmc", "work"): lookup(xb, "weight_work"),
     ("tpb", "work"): lookup(xt, "weight_work"), ("tract", "home"): lookup(TH, "n"), ("tract", "work"): lookup(TW, "n")}
bmc_codes, tpb_codes = set(xb.taz), set(xt.taz)
def gid(c, t):
    ok = (c > 0) & (t > 0) & (t < 999999)
    return pd.Series(np.where(ok, c.clip(lower=0).astype(int).map("{:05d}".format) + t.clip(lower=0).astype(int).map("{:06d}".format), ""), index=c.index)
def pick(b, t):
    bv = b.isin(bmc_codes); tv = t.isin(tpb_codes)
    return np.select([bv & (b <= 1387), tv, bv], ["bmc", "tpb", "bmc"], "tract"), np.select([bv & (b <= 1387), tv, bv], [b, t, b], -1)
p["home_geoid"] = gid(p.home_state_county_fips, p.home_tract_fips); p["school_geoid"] = gid(p.school_state_county_fips, p.school_tract_fips)
rows = {"home": [], "school": []}
SNAP_M = 3000; PSZ = np.array(sorted(bandz["postsec"]))
Zc = gpd.read_file(f"{ROOT}/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(CRS); Zc["zone"] = Zc.SMZRMZ.astype(int)
CX = pd.Series(Zc.geometry.centroid.x.values, index=Zc.zone); CY = pd.Series(Zc.geometry.centroid.y.values, index=Zc.zone)
def finish(d):
    tot = sum(d.values()); d = {z: v / tot for z, v in d.items()}; d = {z: v for z, v in d.items() if v >= 0.01}
    d = dict(sorted(d.items(), key=lambda kv: -kv[1])[:4]); tot = sum(d.values()); return {z: v / tot for z, v in d.items()}
for side in ("home", "school"):
    sysn, taz = pick(p[f"{side}_bmc_taz"], p[f"{side}_tpb_taz"]); src = []
    for i, (sy, t, g, b) in enumerate(zip(sysn, taz, p[f"{side}_geoid"], p.band)):
        d, how = None, sy
        if side == "home":
            if sy != "tract": d = L[(sy, "home")].get(int(t))
            if d is None: d = L[("tract", "home")].get(g); how = "tract split (housing units)"
        else:
            if sy != "tract":
                d = SW[sy].get((int(t), b)); how = f"{sy} TAZ, school enrolment"
                if d is None: d = L[(sy, "work")].get(int(t)); how = f"{sy} TAZ, job weights (no school of the band in the TAZ)"
            if d is None: d = SW["tract"].get((g, b)); how = "tract split (school enrolment)"
            if d is None: d = L[("tract", "work")].get(g); how = "tract split (jobs)"
        if d is None:
            z0 = tz.get(g, -1); d = {int(z0): 1.0} if z0 > 0 else None; how = "tract point"
        if d is not None and side == "school":
            d0 = d; d = {z: v for z, v in d.items() if z in bandz[b]} or None
            if d is None and b == "postsec":   # college campuses span several zones; IPEDS gives one point per institution
                zm = max(d0, key=d0.get); dd = np.hypot(CX[PSZ] - CX[zm], CY[PSZ] - CY[zm]); cand = PSZ[np.argmin(dd)]
                if dd.min() <= SNAP_M: d = {int(cand): 1.0}; how += f"; snapped to the nearest zone with post-secondary enrolment (centroids <= {SNAP_M / 1000:.0f} km)"
        if d:
            for zz, v in finish(d).items(): rows[side].append((p.person_id.values[i], int(zz), v))
        else: how = "none"
        src.append(how)
    p[f"{side}_src"] = src
drop(p.home_src.eq("none"), "home: no TAZ and no tract in the zone system")
drop(p.school_src.eq("none"), "school: no location in the zone system, or no enrolment of the band in the possible zones")
split = pd.read_csv(f"{V}/data/rts_split.csv").set_index("household_id").half; p["half"] = p.household_id.map(split)
drop(p.half.isna(), "household not in the split"); drop(~p.hh_income_detailed.between(1, 8), "household income missing")
LH = pd.DataFrame(rows["home"], columns=["person_id", "zone", "w"]); LS = pd.DataFrame(rows["school"], columns=["person_id", "zone", "w"])
LH = LH[LH.person_id.isin(p.person_id)]; LS = LS[LS.person_id.isin(p.person_id)]
p["hz"] = p.person_id.map(LH.sort_values("w", ascending=False).drop_duplicates("person_id").set_index("person_id").zone)
p["sz"] = p.person_id.map(LS.sort_values("w", ascending=False).drop_duplicates("person_id").set_index("person_id").zone)
p["female"] = (p.gender == 1).astype(int); p["g"] = p.hh_income_detailed.map(G16).astype(int); p["cars"] = p.numvehicle.clip(lower=0); p["drivers"] = p.numdrivers.clip(lower=0)
p["car0"] = (p.cars == 0).astype(int); p["carlow"] = ((p.cars > 0) & (p.cars < p.drivers)).astype(int); p["lic"] = (p.license == 1).astype(int)
p["state_h"] = p.home_state_county_fips // 1000
keep = ["household_id", "person_id", "half", "seg", "band", "school_type", "hz", "sz", "home_src", "school_src", "age", "female", "lic", "g", "cars", "drivers", "car0", "carlow",
        "hhsize", "wtperfin", "state_h", "school_mode"]
p[keep].reset_index(drop=True).to_parquet(f"{W}/students.parquet", index=False); LH.to_parquet(f"{W}/loc_home.parquet", index=False); LS.to_parquet(f"{W}/loc_school.parquet", index=False)
D = pd.DataFrame(log); D.to_csv(f"{T}/drop_log.csv", index=False)
cnt = p.groupby(["seg", "school_type", "half"]).size().unstack("half", fill_value=0); cnt["total"] = cnt.sum(axis=1)
by = p.groupby(["seg", "band", "half"]).size().unstack("half", fill_value=0); by["total"] = by.sum(axis=1)
cnt = pd.concat([cnt.reset_index().assign(by="school_type"), by.reset_index().assign(by="band")]); cnt.to_csv(f"{T}/counts.csv", index=False)
summ = []
for side, Lx in (("home", LH), ("school", LS)):
    n = Lx.groupby("person_id").size()
    for (sg, sr), c in p.groupby(["seg", f"{side}_src"]).size().items(): summ.append(dict(side=side, seg=sg, item=f"source: {sr}", value=int(c)))
    summ += [dict(side=side, seg="all", item="records split over 2+ zones", value=int((n > 1).sum())), dict(side=side, seg="all", item="mean zones per record", value=float(n.mean()))]
pd.DataFrame(summ).to_csv(f"{T}/location_summary.csv", index=False)
pd.set_option("display.width", 200); print(D.to_string(index=False)); print(cnt.to_string(index=False)); print(pd.DataFrame(summ).to_string(index=False))
