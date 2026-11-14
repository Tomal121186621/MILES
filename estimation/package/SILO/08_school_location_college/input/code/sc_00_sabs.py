#!/usr/bin/env python3 -I
# Copy of 2_silo/schoolchoice/sc_00_sabs.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""SABS check and the in-boundary indicator.

Source: NCES EDGE School Attendance Boundary Survey 2015-16, school-level shapefiles (data/raw/sabs/, SOURCES.txt).  No successor
collection exists (the EDGE SABS page lists 2013-14 and 2015-16 only; checked 2026-10-29).
1 Coverage: every district (LEAID = first 7 digits of NCESSCH) with public schools in the inventory (input/schools_2016.csv) of
  MD, DC and VA (and the other states of the zone area): per band (elementary K-5, middle 6-8, high 9-12), the inventory schools and
  enrolment, the SABS polygons whose grade span covers the band's test grade (3, 7, 10), and the share of the band's inventory
  enrolment whose school (NCESSCH) has such a polygon.  A district is 'covered' for a band at >= 90 % of the enrolment.
2 Indicator: census-block housing units (MD 2010 PL H1; DC/VA/WV 2020 PL H1, the home weights of TAZ_CROSSWALK.md) are placed in
  the SABS polygons covering the band's test grade (all four layers; a block in k polygons counts 1/k for each) and in the MSTM
  zones.  For home zone h and inventory public record s of the band: a_hs = share of the zone's housing units inside s's boundary.
  cov_hb = share of the zone's housing units inside any boundary of the band whose school is in the inventory.
Outputs tables/sabs_coverage_by_district.csv, sabs_coverage_summary.csv; work/sabs_home_school.parquet (home zone, band, school id,
school zone, a), work/sabs_zone_cov.parquet.   Usage: python3 -I sc_00_sabs.py"""
import sys, glob, zipfile, numpy as np, pandas as pd, geopandas as gpd, pyogrio
sys.path.insert(0, "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026/2_silo/schoolchoice")
import sc_common as C   # noqa: E402
RAW, W, T, CRS = C.RAW, C.W, C.T, C.CRS
SAB = glob.glob(f"{RAW}/sabs/ex/**/SABS_1516_*.shp", recursive=True)
TEST = {"elementary": 3, "middle": 7, "high": 10}
Z = gpd.read_file(f"{C.ROOT}/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp")[["SMZRMZ", "geometry"]].to_crs(CRS).rename(columns={"SMZRMZ": "zone"}); Z["zone"] = Z.zone.astype(int)
bb = tuple(Z.to_crs(3857).total_bounds)
def g(x):
    x = str(x).strip().upper(); return -1 if x == "PK" else 0 if x in ("KG", "K") else int(x) if x.isdigit() else np.nan
B = []
for f in SAB:
    d = pyogrio.read_dataframe(f, bbox=bb, columns=["ncessch", "schnam", "leaid", "gslo", "gshi", "defacto", "stAbbrev", "openEnroll", "level", "MultiBdy"])
    d["layer"] = f.split("_")[-1][:-4]; B.append(d)
B = gpd.GeoDataFrame(pd.concat(B, ignore_index=True), crs=3857).to_crs(CRS); B["lo"] = B.gslo.map(g); B["hi"] = B.gshi.map(g)
B["geometry"] = B.geometry.buffer(0)
print("SABS polygons in the zone-area box:", len(B), B.stAbbrev.value_counts().to_dict(), flush=True)
s = pd.read_csv(f"{C.S}/input/schools_2016.csv"); pub = s[(s.sector == "public") & (s.capacity > 0)].copy()
pub["ncessch"] = pub.source_id.astype(str).str.zfill(12); pub["leaid"] = pub.ncessch.str[:7]
# ---- 1 coverage by district and band
rows = []
for b, gr in TEST.items():
    Bb = B[(B.lo <= gr) & (B.hi >= gr)]; has = set(Bb.ncessch)
    for (lea, dist, stf), q in pub[pub.band == b].groupby(["leaid", "district", "state_fips"]):
        rows.append(dict(state_fips=stf, leaid=lea, district=dist, band=b, schools=len(q), enrolment=int(q.capacity.sum()),
                         sabs_polygons=int((Bb.leaid == lea).sum()), schools_with_boundary=int(q.ncessch.isin(has).sum()),
                         enrol_share_with_boundary=float(q.capacity[q.ncessch.isin(has)].sum() / q.capacity.sum()),
                         open_enrolment_flag=float(Bb.openEnroll[Bb.leaid == lea].astype(str).eq("1").mean()) if (Bb.leaid == lea).any() else np.nan))
cov = pd.DataFrame(rows); cov["covered"] = cov.enrol_share_with_boundary >= 0.9
cov.sort_values(["state_fips", "district", "band"]).to_csv(f"{T}/sabs_coverage_by_district.csv", index=False)
cs = cov.groupby(["state_fips", "band"]).apply(lambda q: pd.Series(dict(districts=len(q), districts_covered=int(q.covered.sum()), enrolment=int(q.enrolment.sum()),
                                                                        enrol_share_with_boundary=float((q.enrolment * q.enrol_share_with_boundary).sum() / q.enrolment.sum())))).reset_index()
cs.to_csv(f"{T}/sabs_coverage_summary.csv", index=False); print(cs.to_string(index=False), flush=True)
md = cov[cov.state_fips.isin([24, 11, 51])].pivot_table(index=["state_fips", "district"], columns="band", values="enrol_share_with_boundary").round(2)
pd.set_option("display.width", 200); print(md.to_string())
# ---- 2 housing units in boundaries and zones
geo = []
with open(f"{RAW}/census2010/mdgeo2010.pl", encoding="latin1") as f:
    for l in f:
        if l[8:11] == "750": geo.append((int(l[18:25]), float(l[336:347]), float(l[347:359])))
g10 = pd.DataFrame(geo, columns=["logrecno", "lat", "lon"])
s2 = pd.read_csv(f"{RAW}/census2010/md000022010.pl", header=None, usecols=[4, 149]); s2.columns = ["logrecno", "hu"]
hu = [g10.merge(s2, on="logrecno")[["lat", "lon", "hu"]]]
for st in ("dc", "va", "wv"):
    zf = zipfile.ZipFile(f"{RAW}/census2020_pl_dc_va_wv/{st}2020.pl.zip")
    gg = pd.read_csv(zf.open(f"{st}geo2020.pl"), sep="|", header=None, usecols=[2, 7, 92, 93], dtype={2: str}, encoding="latin1")
    gg = gg[gg[2] == "750"]; gg.columns = ["sl", "logrecno", "lat", "lon"]
    ss = pd.read_csv(zf.open(f"{st}000022020.pl"), sep="|", header=None, usecols=[4, 149]); ss.columns = ["logrecno", "hu"]
    hu.append(gg.merge(ss, on="logrecno")[["lat", "lon", "hu"]])
HU = pd.concat(hu, ignore_index=True); HU = HU[HU.hu > 0].reset_index(drop=True)
HU = gpd.GeoDataFrame(HU, geometry=gpd.points_from_xy(HU.lon, HU.lat), crs=4326).to_crs(CRS)
j = gpd.sjoin(HU, Z, predicate="within", how="inner"); j = j[~j.index.duplicated()]; HU = HU.loc[j.index].assign(zone=j.zone.values)
zhu = HU.groupby("zone").hu.sum()
rec = pub.set_index(["ncessch", "band"])[["id", "zone"]]
out, zc = [], []
for b, gr in TEST.items():
    Bb = B[(B.lo <= gr) & (B.hi >= gr)][["ncessch", "geometry"]]
    k = gpd.sjoin(HU[["hu", "zone", "geometry"]], Bb, predicate="within", how="inner")
    k["share"] = k.hu / k.groupby(level=0).ncessch.transform("size")
    k = k.join(rec.xs(b, level="band"), on="ncessch", how="left", rsuffix="_s")
    m = k.id.notna()
    a = k[m].groupby(["zone", "id", "zone_s"]).share.sum().reset_index(); a["a"] = a.share / a.zone.map(zhu); a["band"] = b
    out.append(a.rename(columns={"id": "school_id", "zone_s": "school_zone"})[["zone", "band", "school_id", "school_zone", "a"]])
    c1 = k[m].groupby("zone").share.sum() / zhu; c0 = k.groupby("zone").share.sum() / zhu
    zc.append(pd.DataFrame({"zone": zhu.index, "band": b, "cov_any_boundary": c0.reindex(zhu.index).fillna(0).values, "cov": c1.reindex(zhu.index).fillna(0).values}))
    print(b, "housing units in a boundary of the band:", round(float(k.share.sum() / zhu.sum()), 3), "with the school in the inventory:", round(float(k.share[m].sum() / zhu.sum()), 3), flush=True)
A = pd.concat(out, ignore_index=True); A["school_id"] = A.school_id.astype(int); A["school_zone"] = A.school_zone.astype(int); A.to_parquet(f"{W}/sabs_home_school.parquet", index=False)
pd.concat(zc).to_parquet(f"{W}/sabs_zone_cov.parquet", index=False)
