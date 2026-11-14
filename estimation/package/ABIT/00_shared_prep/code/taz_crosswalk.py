#!/usr/bin/env python3 -I
"""RTS TAZ -> MSTM zone crosswalk, and comparison with the tract-internal-point mapping (diagnostic only, no estimation).

TAZ layers (official MPO GIS services, saved under data/raw/taz_bmc and data/raw/taz_tpb, see SOURCES.txt there):
  BMC  'TAZ2010 for ActivityBasedModel' (Regional_Boundaries/MapServer/14, field TAZ10, 2,922 polygons, 1..2934) = the RTS
       'BMC TAZ10 Number'.  JUR 1-6 (TAZ10 1..1387) are BMC's own 2010 TIGER TAZs; JUR 7-10 (1400..2934) are copies of COG 3722 TAZs.
  TPB  'TAZ - TPB' of the 3722 system (RTDC/TAZ/MapServer/0, field TAZ, 3,669 polygons, 1..3675) = the RTS 'TPB TAZ Number'.
  For the vintage check also BMC MapServer/15 ('TAZ2010 for TravelDemandModel') and the COG layer (MapServer/1).
Weights inside a TAZ: area; homes: housing units by block internal point (MD 2010 Census PL 94-171 H1; DC/VA/WV 2020 PL H1);
workplaces: LODES8 2017 WAC jobs (C000) by 2020-block internal point (LODES xwalk).  A TAZ without housing units / jobs keeps the
area weights.
Record rule (home and work separately): BMC native TAZ (1..1387) -> BMC; else valid TPB TAZ -> TPB; else BMC TAZ 1400..2934 -> BMC;
else the tract mapping.  Outputs: data/taz_bmc_to_mstm.csv, data/taz_tpb_to_mstm.csv, jobchoice/tables_taz/*.csv.
Usage: python3 -I taz_crosswalk.py"""
# COPY of Validation_2026/2_silo/jobchoice/taz_crosswalk.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "00_shared_data"))          # provided inputs
RAW = _os_pkg.environ.get("ABIT_RAW", _os_pkg.path.join(SHARED, "raw"))                                                              # your downloads
REBUILT = _os_pkg.environ.get("ABIT_REBUILT", _os_pkg.path.join(SHARED, "rebuilt"))                  # outputs of this chain
MDATA = REBUILT
import os, glob, gzip, zipfile, io, numpy as np, pandas as pd, geopandas as gpd

ROOT = SHARED; V = SHARED; D = f"{REBUILT}/taz_crosswalks"; os.makedirs(D, exist_ok=True)  # PATH: downloads in RAW/<taz_bmc, taz_tpb, census2010, census2020_pl_dc_va_wv, lodes_wac, lodes_wac_2017_extra, tiger_tracts_2010>
JC = f"{RAW}/silo_workplace_work"; T = f"{REBUILT}/taz_crosswalks/tables_taz"; os.makedirs(T, exist_ok=True)  # PATH: workers.parquet, work/zones.parquet of the SILO workplace chain
CRS = 26918
out = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s); out.append(s)

# ---------------- layers
Z = gpd.read_file(f"{RAW}/mstm_zone_system/SMZ_RMZ_02152011inMSTM_EPSG26918.shp")[["SMZRMZ", "geometry"]].to_crs(CRS)
Z = Z.rename(columns={"SMZRMZ": "zone"}); Z["zone"] = Z.zone.astype(int)
bmc = gpd.read_file(f"{RAW}/taz_bmc/layer14.geojson").to_crs(CRS); bmc = bmc.rename(columns={"TAZ10": "taz"})[["taz", "JUR", "COG3722TAZ", "geometry"]]
bmc["taz"] = bmc.taz.astype(int)
bmc15 = gpd.read_file(f"{RAW}/taz_bmc/layer15.geojson").to_crs(CRS).rename(columns={"TAZ10": "taz"})[["taz", "geometry"]]; bmc15["taz"] = bmc15.taz.astype(int)
tpb = pd.concat([gpd.read_file(f) for f in sorted(glob.glob(f"{RAW}/taz_tpb/rest_layer0_off*.geojson"))]).to_crs(CRS)
tpb = gpd.GeoDataFrame(tpb.rename(columns={"TAZ": "taz"})[["taz", "FIPSSTCO", "geometry"]], crs=CRS); tpb["taz"] = tpb.taz.astype(int)
cog = gpd.read_file(f"zip://{RAW}/taz_tpb/hub_layer1.zip").to_crs(CRS).rename(columns={"TAZ": "taz"})[["taz", "geometry"]]; cog["taz"] = cog.taz.astype(int)
for g in (bmc, bmc15, tpb, cog, Z): g["geometry"] = g.geometry.make_valid()
bmc = bmc.dissolve("taz", aggfunc="first").reset_index(); tpb = tpb.dissolve("taz", aggfunc="first").reset_index()
say(f"layers: MSTM {len(Z)} zones; BMC ABM {len(bmc)} TAZ ({bmc.taz.min()}..{bmc.taz.max()}); BMC TDM {bmc15.taz.nunique()}; TPB {len(tpb)} ({tpb.taz.min()}..{tpb.taz.max()}); COG {len(cog)}")

# ---------------- block points: housing units and jobs
def pts(df, x, y):
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[x], df[y]), crs=4326).to_crs(CRS)
geo = []
with open(f"{RAW}/census2010/mdgeo2010.pl", encoding="latin1") as f:
    for l in f:
        if l[8:11] == "750": geo.append((int(l[18:25]), float(l[336:347]), float(l[347:359])))
g10 = pd.DataFrame(geo, columns=["logrecno", "lat", "lon"])
s2 = pd.read_csv(f"{RAW}/census2010/md000022010.pl", header=None, usecols=[4, 149]); s2.columns = ["logrecno", "hu"]
hu = [g10.merge(s2, on="logrecno")[["lat", "lon", "hu"]].assign(src="MD 2010")]
for st in ("dc", "va", "wv"):
    zf = zipfile.ZipFile(f"{RAW}/census2020_pl_dc_va_wv/{st}2020.pl.zip")
    gg = pd.read_csv(zf.open(f"{st}geo2020.pl"), sep="|", header=None, usecols=[2, 7, 92, 93], dtype={2: str}, encoding="latin1")
    gg = gg[gg[2] == "750"]; gg.columns = ["sl", "logrecno", "lat", "lon"]
    ss = pd.read_csv(zf.open(f"{st}000022020.pl"), sep="|", header=None, usecols=[4, 149]); ss.columns = ["logrecno", "hu"]
    hu.append(gg.merge(ss, on="logrecno")[["lat", "lon", "hu"]].assign(src=f"{st.upper()} 2020"))
HU = pd.concat(hu, ignore_index=True); HU = HU[HU.hu > 0].reset_index(drop=True); HU = pts(HU, "lon", "lat")
xw = pd.concat([pd.read_csv(f"{RAW}/lodes_wac/{s}_xwalk.csv.gz", usecols=["tabblk2020", "blklatdd", "blklondd"], dtype={"tabblk2020": str}) for s in ("md", "dc", "va", "wv", "pa", "de")])
wac = [pd.read_csv(f"{RAW}/lodes_wac/md_wac_S000_JT00_2017.csv.gz", usecols=["w_geocode", "C000"], dtype={"w_geocode": str})]
wac += [pd.read_csv(f"{RAW}/lodes_wac_2017_extra/{s}_wac_S000_JT00_2017.csv.gz", usecols=["w_geocode", "C000"], dtype={"w_geocode": str}) for s in ("dc", "va", "wv", "pa", "de")]
JOB = pd.concat(wac).merge(xw, left_on="w_geocode", right_on="tabblk2020"); JOB = pts(JOB.rename(columns={"C000": "jobs"}).reset_index(drop=True), "blklondd", "blklatdd")
say(f"blocks: housing units {HU.hu.sum():,.0f} in {len(HU):,} blocks ({HU.groupby('src').hu.sum().to_dict()}); LODES 2017 jobs {JOB.jobs.sum():,.0f}")
def zone_of(P):
    j = gpd.sjoin(P, Z, predicate="within", how="left"); return j[~j.index.duplicated()].zone.reindex(P.index).values
HU["zone"] = zone_of(HU); JOB["zone"] = zone_of(JOB)


def crosswalk(taz, name):
    ov = gpd.overlay(taz[["taz", "geometry"]], Z, how="intersection", keep_geom_type=True)
    ov["a"] = ov.area; ov = ov.groupby(["taz", "zone"]).a.sum().reset_index()
    ov["weight"] = ov.a / ov.groupby("taz").a.transform("sum")
    ov = ov[ov.weight >= 1e-4].copy(); ov["weight"] = ov.weight / ov.groupby("taz").weight.transform("sum")
    for var, P, col in (("hu", HU, "weight_home"), ("jobs", JOB, "weight_work")):
        j = gpd.sjoin(P[[var, "zone", "geometry"]], taz[["taz", "geometry"]], predicate="within", how="inner")
        j = j[~j.index.duplicated()]
        c = j.dropna(subset=["zone"]).groupby(["taz", "zone"])[var].sum().reset_index(); c["zone"] = c.zone.astype(int)
        c[col] = c[var] / c.groupby("taz")[var].transform("sum")
        ov = ov.merge(c[["taz", "zone", col]], on=["taz", "zone"], how="outer")
        has = ov.taz.isin(c.taz)
        ov.loc[~has, col] = ov.loc[~has, "weight"]; ov[col] = ov[col].fillna(0.0)
        ov.loc[has, col] = ov.loc[has, col] / ov[has].groupby("taz")[col].transform("sum")
    ov["weight"] = ov.weight.fillna(0.0); ov = ov[["taz", "zone", "weight", "weight_home", "weight_work"]].sort_values(["taz", "zone"])
    ov = ov[(ov[["weight", "weight_home", "weight_work"]] > 0).any(axis=1)]
    ov.to_csv(f"{D}/taz_{name}_to_mstm.csv", index=False, float_format="%.6f")
    rows = []
    for col in ("weight", "weight_home", "weight_work"):
        m = ov.groupby("taz")[col].max(); n = (ov[ov[col] > 0.0].groupby("taz").size())
        rows.append(dict(system=name, basis=col, taz=len(m), whole_95=(m >= 0.95).mean(), whole_99=(m >= 0.99).mean(), mean_zones=n.mean(),
                         max_share_median=m.median()))
    # nesting the other way: TAZs per MSTM zone (by largest-area zone)
    best = ov.loc[ov.groupby("taz").weight.idxmax()]
    rows[0]["taz_per_zone_median"] = best.groupby("zone").size().median(); rows[0]["zones_touched"] = best.zone.nunique()
    return ov, pd.DataFrame(rows)

xb, nb = crosswalk(bmc, "bmc"); xt, nt = crosswalk(tpb, "tpb")
nest = pd.concat([nb, nt]); nest.to_csv(f"{T}/nesting.csv", index=False)
say("nesting (share of TAZ with >=95% / >=99% of area | housing units | jobs in one MSTM zone):"); say(nest.round(3).to_string(index=False))
# BMC native vs COG-copy part
for part, m in (("BMC native 1..1387", xb.taz <= 1387), ("BMC COG copies 1400..2934", xb.taz > 1387)):
    for col in ("weight", "weight_home", "weight_work"):
        mx = xb[m].groupby("taz")[col].max(); say(f"  {part} {col}: whole>=95% {(mx >= 0.95).mean():.3f} (n={len(mx)})")

# ---------------- RTS records
rcols = ["person_id", "home_bmc_taz", "home_tpb_taz", "work_bmc_taz", "work_tpb_taz", "home_tract_fips", "work_tract_fips",
         "home_state_county_fips", "work_state_county_fips"]
r = pd.read_csv(f"{SHARED}/rts_2017_18/raw/RTS_raw_flat_data.csv.gz", usecols=rcols, low_memory=False).drop_duplicates("person_id")
w = pd.read_parquet(f"{JC}/work_rts/workers.parquet").merge(r, on="person_id", how="left", validate="1:1")
say(f"workplace-model records: {len(w)}")

# vintage check: does the reported TAZ overlap the reported 2010 tract?
tr = pd.concat([gpd.read_file(f) for f in glob.glob(f"{RAW}/tiger_tracts_2010/tl_2010_*_tract10/*.shp")])[["GEOID10", "geometry"]].to_crs(CRS)
tr["geometry"] = tr.geometry.make_valid(); tr = tr.set_index("GEOID10").geometry
def gid(c, t): return c.astype(int).map("{:05d}".format) + t.astype(int).map("{:06d}".format)
w["home_geoid"] = gid(w.home_state_county_fips, w.home_tract_fips); w["work_geoid"] = gid(w.work_state_county_fips, w.work_tract_fips)
vin = []
for side in ("home", "work"):
    for sysn, lay, fld in (("bmc", bmc, "bmc"), ("bmc_TDM15", bmc15.dissolve("taz").reset_index(), "bmc"), ("tpb", tpb, "tpb"), ("cog", cog.dissolve("taz").reset_index(), "tpb")):
        v = w[w[f"{side}_{fld}_taz"] > 0]; L = lay.set_index("taz").geometry
        ok = v[f"{side}_{fld}_taz"].isin(L.index) & v[f"{side}_geoid"].isin(tr.index)
        v = v[ok]; a = gpd.GeoSeries(L.loc[v[f"{side}_{fld}_taz"]].values, crs=CRS); b = gpd.GeoSeries(tr.loc[v[f"{side}_geoid"]].values, crs=CRS)
        inter = a.intersection(b, align=False).area.values; share = inter / np.maximum(a.area.values, 1)
        vin.append(dict(side=side, layer=sysn, records=int((w[f"{side}_{fld}_taz"] > 0).sum()), code_in_layer=int(ok.sum()), overlaps_tract=(inter > 0).mean(),
                        taz_share_in_tract_ge50=(share >= 0.5).mean()))
vin = pd.DataFrame(vin); vin.to_csv(f"{T}/vintage_check.csv", index=False); say("vintage check (reported TAZ vs reported 2010 tract):"); say(vin.round(3).to_string(index=False))

# record rule
def pick(b, t):
    bv = b.isin(xb.taz.unique()); tv = t.isin(xt.taz.unique())
    return np.select([bv & (b <= 1387), tv, bv], ["bmc", "tpb", "bmc"], "tract"), np.select([bv & (b <= 1387), tv, bv], [b, t, b], -1)
for side in ("home", "work"):
    w[f"{side}_sys"], w[f"{side}_taz"] = pick(w[f"{side}_bmc_taz"], w[f"{side}_tpb_taz"])
XW = {"bmc": xb, "tpb": xt}
def dist(side):
    """per record: dict zone -> prob (tract records: point mass at the tract zone)"""
    col = "weight_home" if side == "home" else "weight_work"; zc = "hz" if side == "home" else "wz"; res = []
    lk = {s: {k: dict(zip(g.zone, g[col])) for k, g in X[X[col] > 0].groupby("taz")} for s, X in XW.items()}
    for s, t, z0 in zip(w[f"{side}_sys"], w[f"{side}_taz"], w[zc]):
        res.append({int(z0): 1.0} if s == "tract" else lk[s].get(int(t), {int(z0): 1.0}))
    return res
H = dist("home"); Wd = dist("work")
zs = pd.read_csv(f"{RAW}/mstm_zone_system/zoneSystem.csv").set_index("ZoneId").COUNTYFIPS
Zj = pd.read_parquet(f"{JC}/work/zones.parquet").set_index("zone"); jobs16 = Zj[["RET", "OFF", "IND", "OTH"]].sum(axis=1)
# the zone system codes some Virginia counties and independent cities jointly (e.g. 51919 = Fairfax + cities): harmonise reported codes
codes = set(zs.unique())
for c in ("county_h", "county_w"):
    zc_ = "zcounty_h" if c == "county_h" else "zcounty_w"
    hm = w[~w[c].isin(codes)].groupby(c)[zc_].agg(lambda s: s.value_counts().index[0])
    w[c + "_hm"] = w[c].map(lambda x: hm.get(x, x))
say("harmonised reported county codes:", dict(w[~w.county_h.isin(codes)].groupby("county_h").county_h_hm.first()))
for side, P, zc, cc in (("home", H, "hz", "county_h_hm"), ("work", Wd, "wz", "county_w_hm")):
    w[f"{side}_modal"] = [max(d, key=d.get) for d in P]; w[f"{side}_pmax"] = [max(d.values()) for d in P]
    w[f"{side}_p_tractzone"] = [d.get(int(z), 0.0) for d, z in zip(P, w[zc])]
    w[f"{side}_p_county_ok"] = [sum(p for z, p in d.items() if zs.get(z) == c) for d, c in zip(P, w[cc])]
w["work_p_nojobs"] = [sum(p for z, p in d.items() if not jobs16.get(z, 0) > 0) for d in Wd]
w["own_tract"] = (w.hz == w.wz).astype(float)
w["own_taz"] = [sum(p * h.get(z, 0.0) for z, p in d.items()) for h, d in zip(H, Wd)]
w["own_taz_modal"] = (w.home_modal == w.work_modal).astype(float)
w["xc_tract"] = (w.zcounty_h != w.zcounty_w).astype(float)
def pc(d):
    s = {}
    for z, p in d.items(): c = zs.get(z); s[c] = s.get(c, 0) + p
    return s
w["xc_taz"] = [1 - sum(p * pc(h).get(c, 0.0) for c, p in pc(d).items()) for h, d in zip(H, Wd)]
w["xc_reported"] = (w.county_h_hm != w.county_w_hm).astype(float)

def wavg(x, m=None):
    m = np.ones(len(w), bool) if m is None else m; return np.average(x[m], weights=w.wtperfin[m]) if m.sum() else np.nan
rows = []
for side in ("home", "work"):
    cov = w[f"{side}_sys"] != "tract"
    rows += [dict(side=side, measure="records with a usable TAZ", value=cov.mean(), weighted=wavg(cov.astype(float))),
             dict(side=side, measure="  of which BMC", value=(w[f"{side}_sys"] == "bmc").mean(), weighted=wavg((w[f"{side}_sys"] == "bmc").astype(float))),
             dict(side=side, measure="  of which TPB", value=(w[f"{side}_sys"] == "tpb").mean(), weighted=wavg((w[f"{side}_sys"] == "tpb").astype(float))),
             dict(side=side, measure="modal TAZ zone != tract zone (all records)", value=((w[f"{side}_modal"] != w["hz" if side == "home" else "wz"]) & cov).mean()),
             dict(side=side, measure="modal TAZ zone != tract zone (TAZ records)", value=(w[f"{side}_modal"] != w["hz" if side == "home" else "wz"])[cov].mean()),
             dict(side=side, measure="TAZ split (largest share < 95%) (TAZ records)", value=(w[f"{side}_pmax"] < 0.95)[cov].mean()),
             dict(side=side, measure="probability mass moved off the tract zone (TAZ records)", value=(1 - w[f"{side}_p_tractzone"])[cov].mean()),
             dict(side=side, measure="P(zone county = reported county), tract map (TAZ records)", value=(w["zcounty_h" if side == "home" else "zcounty_w"] == w["county_h_hm" if side == "home" else "county_w_hm"])[cov].mean()),
             dict(side=side, measure="P(zone county = reported county), TAZ map (TAZ records)", value=w[f"{side}_p_county_ok"][cov].mean())]
rows.append(dict(side="work", measure="TAZ-mapped work probability on zones without 2016 jobs", value=w.work_p_nojobs.mean()))
both = (w.home_sys != "tract") & (w.work_sys != "tract")
for lab, m in (("all records", np.ones(len(w), bool)), ("home and work both TAZ", both.values)):
    rows += [dict(side=lab, measure="own-zone share, tract map", value=w.own_tract[m].mean(), weighted=wavg(w.own_tract, m)),
             dict(side=lab, measure="own-zone share, TAZ map (expected, mixing)", value=w.own_taz[m].mean(), weighted=wavg(w.own_taz, m)),
             dict(side=lab, measure="own-zone share, TAZ map (modal zone)", value=w.own_taz_modal[m].mean(), weighted=wavg(w.own_taz_modal, m)),
             dict(side=lab, measure="county-crossing share, tract map", value=w.xc_tract[m].mean(), weighted=wavg(w.xc_tract, m)),
             dict(side=lab, measure="county-crossing share, TAZ map (expected)", value=w.xc_taz[m].mean(), weighted=wavg(w.xc_taz, m)),
             dict(side=lab, measure="county-crossing share, reported counties (harmonised codes)", value=w.xc_reported[m].mean(), weighted=wavg(w.xc_reported, m))]
cmp_ = pd.DataFrame(rows); cmp_.to_csv(f"{T}/comparison.csv", index=False); say("comparison:"); say(cmp_.round(4).to_string(index=False))
# distance of the change (zone centroids)
cen = Z.set_index("zone").geometry.centroid
for side, zc in (("home", "hz"), ("work", "wz")):
    ch = w[(w[f"{side}_modal"] != w[zc]) & (w[f"{side}_sys"] != "tract")]
    dd = cen.loc[ch[f"{side}_modal"]].distance(cen.loc[ch[zc]], align=False).values / 1000
    say(f"{side}: changed modal zone {len(ch)} records; centroid distance km median {np.median(dd):.2f}, p90 {np.percentile(dd, 90):.2f}; adjacent-scale (<3 km) {(dd < 3).mean():.3f}")
# coverage by home state / county
w["state_w"] = w.county_w // 1000
covt = []
for side, stc, cc in (("home", "state_h", "county_h"), ("work", "state_w", "county_w")):
    g = w.groupby([stc, cc]).agg(n=("person_id", "size"), bmc=(f"{side}_sys", lambda s: (s == "bmc").sum()), tpb=(f"{side}_sys", lambda s: (s == "tpb").sum()),
                                 tract=(f"{side}_sys", lambda s: (s == "tract").sum())).reset_index().rename(columns={stc: "state", cc: "county"})
    g.insert(0, "side", side); covt.append(g)
covt = pd.concat(covt); covt.to_csv(f"{T}/coverage_by_county.csv", index=False)
cs = covt.groupby(["side", "state"])[["n", "bmc", "tpb", "tract"]].sum(); say("coverage by state:"); say(cs.to_string())
say("tract-only home counties (>=20 records):"); say(covt[(covt.side == "home") & (covt.tract >= 20)].sort_values("tract", ascending=False).head(25).to_string(index=False))
say("tract-only work counties (>=20 records):"); say(covt[(covt.side == "work") & (covt.tract >= 20)].sort_values("tract", ascending=False).head(25).to_string(index=False))
w[["person_id", "half", "hz", "wz", "home_sys", "home_taz", "home_modal", "home_pmax", "work_sys", "work_taz", "work_modal", "work_pmax", "own_tract", "own_taz",
   "xc_tract", "xc_taz"]].to_csv(f"{T}/records_taz_vs_tract.csv", index=False)
open(f"{T}/taz_crosswalk_log.txt", "w").write("\n".join(out) + "\n")
