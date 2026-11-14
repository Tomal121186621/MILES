#!/usr/bin/env python3
"""Stage 2b: school inventory for SILO and the activity model (ABIT).

Builds WORKSPACE/2_silo/input/schools.csv (one record per school and grade band) from the NCES Common Core of Data
2024-25 (public K-12), the NCES Private School Survey 2023-24 (private K-12) and IPEDS 2024 (post-secondary), geocoded to the
MSTM zone system.  Writes the capacity table by zone and school type and the validation table by county.

Inputs (raw downloads, see data_sources.md):
  data/raw/nces/ccd_sch_029_2425_w_1a_073025.zip      CCD school directory 2024-25 (status, type, grade span, level)
  data/raw/nces/ccd_sch_052_2425_l_1a_073025.zip      CCD school membership 2024-25, long format (students by grade)
  data/raw/nces/ccd_sea_052_2425_l_1a_073025.zip      CCD state membership 2024-25 (state totals for the validation table)
  data/raw/nces/EDGE_GEOCODE_PUBLICSCH_2425.zip       EDGE geocodes of public schools (lat/lon, county)
  data/raw/nces/pss2324_pu_csv.zip                    PSS 2023-24 public-use file (private schools, enrollment by grade, lat/lon)
  data/raw/nces/EDGE_GEOCODE_PRIVATESCH_2324.zip      EDGE geocodes of private schools (fallback coordinates)
  data/raw/ipeds/HD2024.zip, EF2023A.zip, EFFY2024.zip IPEDS institutions, fall 2023 enrollment, 12-month 2023-24 enrollment
  2_silo/input/zoneSystem.csv, ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp   MSTM zones
  2_silo/input/microData/{pp,hh,dd}_2016.csv           synthetic population (children 5-17 by county)

Outputs:
  2_silo/input/schools.csv                             SILO/ABIT school file (column contract in README.md)
  data/schools_capacity_by_zone.csv                    enrollment capacity by zone and school type
  data/schools_validation_by_county.csv                inventory vs NCES state totals vs synthetic 5-17-year-olds
  data/schools_ccd_membership_2425_extract.csv         cached extract of the 2.3 GB membership file (MSTM states only)

Run:  python3 -I build_inventory.py
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import io
import os
import subprocess
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import points
from shapely.validation import make_valid

ROOT = f"{PROJECT_ROOT}"
V = f"{WORKSPACE}"
RAW = f"{V}/data/raw"
DATA = f"{V}/data"
SILO_INPUT = f"{V}/2_silo/input"
ZONE_SHP = f"{ABIT_HOME}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp"
CRS_SILO = 26918                      # NAD83 / UTM 18N, the CRS of 2_silo/input/zones.prj and of the ABIT zone shapefile
MSTM_STATES = {"24": "MD", "11": "DC", "10": "DE", "42": "PA", "51": "VA", "54": "WV"}   # states with MSTM zones
HOME_STATE = "24"                     # schools of this state outside every zone polygon are snapped to the nearest zone

# school day by grade band, seconds after midnight (SILO SchoolsWriter convention; ABIT divides by 60).  Typical Maryland
# bell schedules: high schools start earliest, elementary schools latest; to be calibrated against the 2023 survey in stage 3.
# school day (start, duration in s): medians of the 2017/18 Regional Travel Survey school-trip arrivals and school-activity durations
# by band (activity/lib/education_targets.py): elementary 08:35 / 7.0 h, middle 08:00 / 7.1 h, high 07:45 / 7.2 h, post-secondary 09:15 / 4.5 h
SCHOOL_DAY = {"elementary": (30900, 25200), "middle": (28800, 25560), "high": (27900, 25920), "postsec": (33300, 16200)}
SILO_TYPE = {"elementary": 1, "middle": 2, "high": 2, "postsec": 3}   # SchoolDataImpl: 1 primary (<10), 2 secondary (<18), 3 tertiary

CCD_GRADES = {"Kindergarten": "K", **{f"Grade {g}": str(g) for g in range(1, 14)}, "Pre-Kindergarten": "PK",
              "Ungraded": "UG", "Not Specified": "NS", "Adult Education": "AE"}
BAND_OF_GRADE = {"K": "elementary", **{str(g): "elementary" for g in range(1, 6)}, **{str(g): "middle" for g in range(6, 9)},
                 **{str(g): "high" for g in range(9, 14)}}
# PSS 2023-24 public-use file: enrollment counts P150 = prekindergarten, P160 = kindergarten, P170..P280 = grades 1..12,
# P290/P300 = ungraded (K-12 total NUMSTUDS = sum of P160..P300 for 94 % of schools; verified numerically, see README.md)
PSS_GRADE_COL = {"K": "P160", **{str(g): f"P{160 + 10 * g}" for g in range(1, 13)}}
PSS_UNGRADED = ["P290", "P300"]
PSS_GRADE_CODE = {1: "UG", 2: "PK", 3: "K", **{g + 3: str(g) for g in range(1, 13)}, 16: "13", 17: "UG"}


def read_zip_csv(zip_path, member_suffix=".csv", **kw):
    with zipfile.ZipFile(zip_path) as z:
        name = [n for n in z.namelist() if n.lower().endswith(member_suffix)][0]
        with z.open(name) as f:
            return pd.read_csv(f, **kw)


def strip_bom(df):
    df.columns = [c.replace("﻿", "").replace("ï»¿", "") for c in df.columns]
    return df


def clean_name(s):
    return (s.fillna("").astype(str).str.replace('"', "", regex=False).str.replace(",", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True).str.strip())


# ----------------------------------------------------------------------------------------------------------------- zones
def load_zones():
    z = gpd.read_file(ZONE_SHP)[["SMZRMZ", "STCOFIPS", "geometry"]].rename(columns={"SMZRMZ": "zone"})
    z["geometry"] = z.geometry.apply(make_valid)
    zs = pd.read_csv(f"{SILO_INPUT}/zoneSystem.csv", usecols=["SMZRMZ", "COUNTYFIPS", "JUR_NAME"]).rename(
        columns={"SMZRMZ": "zone", "COUNTYFIPS": "zone_county"})
    z = z.merge(zs, on="zone", how="left")
    z["zone_county"] = z.zone_county.fillna(z.STCOFIPS.astype(float)).astype(int).astype(str).str.zfill(5)
    assert z.zone.is_unique
    return z.to_crs(CRS_SILO)


def assign_zones(df, zones):
    """Point-in-zone (within), nearest zone for home-state schools outside every polygon, others dropped."""
    pts = gpd.GeoDataFrame(df.reset_index(drop=True), geometry=points(df.lon.astype(float).values, df.lat.astype(float).values),
                           crs=4326).to_crs(CRS_SILO)
    pts["coordX"] = pts.geometry.x.round(1)
    pts["coordY"] = pts.geometry.y.round(1)
    j = gpd.sjoin(pts, zones[["zone", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]            # a point on a shared boundary joins twice; keep the first zone
    j["zone_method"] = np.where(j.zone.notna(), "within", "")
    miss = j.zone.isna() & (j.state_fips == HOME_STATE)
    if miss.any():
        near = gpd.sjoin_nearest(j.loc[miss, ["geometry"]], zones[["zone", "geometry"]], how="left", distance_col="d")
        near = near[~near.index.duplicated()]
        j.loc[miss, "zone"] = near.zone
        j.loc[miss, "zone_method"] = "nearest_" + near.d.round(0).astype(int).astype(str) + "m"
    dropped = j[j.zone.isna()]
    j = j[j.zone.notna()].copy()
    j["zone"] = j.zone.astype(int)
    return pd.DataFrame(j.drop(columns=["geometry", "index_right"])), dropped


# ------------------------------------------------------------------------------------------------------------ CCD public
def ccd_membership_extract():
    """Rows of the 2.3 GB membership file for the MSTM states: school totals and students by grade.  Cached in data/."""
    cache = f"{DATA}/schools_ccd_membership_2425_extract.csv"
    if os.path.exists(cache):
        return pd.read_csv(cache, dtype={"NCESSCH": str, "FIPST": str})
    keep_ti = {"Education Unit Total", "Subtotal 4 - By Grade"}
    parts = []
    zip_path = f"{RAW}/nces/ccd_sch_052_2425_l_1a_073025.zip"
    with zipfile.ZipFile(zip_path) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    # the archive uses a compression method the zipfile module does not decode (Deflate64); stream it through unzip
    proc = subprocess.Popen(["unzip", "-p", zip_path, name], stdout=subprocess.PIPE)
    for chunk in pd.read_csv(io.TextIOWrapper(proc.stdout, encoding="latin-1"), dtype=str, chunksize=2_000_000,
                             usecols=["FIPST", "NCESSCH", "GRADE", "STUDENT_COUNT", "TOTAL_INDICATOR", "DMS_FLAG"]):
        sel = chunk[chunk.FIPST.isin(MSTM_STATES) & chunk.TOTAL_INDICATOR.isin(keep_ti)]
        if len(sel):
            parts.append(sel)
        print(f"  membership chunk read, kept {sum(len(p) for p in parts):,} rows", flush=True)
    proc.wait()
    ext = pd.concat(parts, ignore_index=True)
    ext.to_csv(cache, index=False)
    return ext


def build_public():
    d = strip_bom(read_zip_csv(f"{RAW}/nces/ccd_sch_029_2425_w_1a_073025.zip", dtype=str, encoding="latin-1"))
    d = d[d.FIPST.isin(MSTM_STATES)].copy()
    n_all = len(d)
    d = d[~d.SY_STATUS_TEXT.isin(["Closed", "Inactive", "Future"])]
    print(f"CCD directory 2024-25: {n_all:,} schools in MSTM states, {len(d):,} not closed; Maryland {int((d.FIPST == '24').sum()):,}")

    m = ccd_membership_extract()
    m["STUDENT_COUNT"] = pd.to_numeric(m.STUDENT_COUNT, errors="coerce")
    tot = m[m.TOTAL_INDICATOR == "Education Unit Total"].groupby("NCESSCH").STUDENT_COUNT.sum().rename("total")
    g = m[m.TOTAL_INDICATOR == "Subtotal 4 - By Grade"].copy()
    g["grade"] = g.GRADE.map(CCD_GRADES)
    byg = g.pivot_table(index="NCESSCH", columns="grade", values="STUDENT_COUNT", aggfunc="sum").fillna(0)
    for c in list(CCD_GRADES.values()):
        if c not in byg:
            byg[c] = 0.0

    geo = read_zip_csv(f"{RAW}/nces/EDGE_GEOCODE_PUBLICSCH_2425.zip", member_suffix=".txt", sep="|", header=None, dtype=str,
                       encoding="latin-1", names=["NCESSCH", "LEAID", "NAME", "OPSTFIPS", "STREET", "CITY", "STATE", "ZIP", "STFIP",
                                                 "CNTY", "NMCNTY", "LOCALE", "LAT", "LON", "CBSA", "NMCBSA", "CBSATYPE", "CSA",
                                                 "NMCSA", "CD", "SLDL", "SLDU", "SCHOOLYEAR"])
    geo = geo[["NCESSCH", "CNTY", "NMCNTY", "LAT", "LON"]]

    d = d.merge(tot, left_on="NCESSCH", right_index=True, how="left").merge(byg, left_on="NCESSCH", right_index=True, how="left")
    d = d.merge(geo, on="NCESSCH", how="left")
    no_geo = d.LAT.isna() | (pd.to_numeric(d.LAT, errors="coerce").fillna(0) == 0)
    no_enr = d.total.isna() | (d.total <= 0)
    print(f"  without coordinates {int(no_geo.sum())}, without students {int(no_enr.sum())} (dropped)")
    d = d[~no_geo & ~no_enr].copy()

    # grade bands: K-5 elementary, 6-8 middle, 9-13 high; ungraded/not-specified students follow the graded split of the school,
    # or the CCD LEVEL where a school has no graded counts; pre-kindergarten is kept apart (SILO students start at age 5)
    bands = ["elementary", "middle", "high"]
    for b in bands:
        d[b] = sum(d[gr] for gr, bb in BAND_OF_GRADE.items() if bb == b)
    d["PK"] = d["PK"].fillna(0)
    graded = d[bands].sum(axis=1)
    rest = (d.total - graded - d.PK).clip(lower=0)
    level_band = d.LEVEL.map({"Elementary": "elementary", "Middle": "middle", "High": "high", "Prekindergarten": "elementary"})
    for b in bands:
        share = np.where(graded > 0, d[b] / graded.replace(0, np.nan), np.where(level_band == b, 1.0, 0.0))
        share = np.where((graded > 0) | level_band.notna(), share, np.where(b == "elementary", 1.0, 0.0))
        d[b] = d[b] + rest * np.nan_to_num(share)
    rows = []
    for b in bands:
        s = d[d[b] >= 0.5].copy()
        s["band"] = b
        s["enrollment"] = s[b].round().astype(int)
        rows.append(s)
    out = pd.concat(rows, ignore_index=True)
    out = out.rename(columns={"FIPST": "state_fips", "LAT": "lat", "LON": "lon", "NCESSCH": "source_id", "CNTY": "county_fips",
                              "NMCNTY": "county_name", "GSLO": "grade_lo", "GSHI": "grade_hi", "LEA_NAME": "district"})
    out["name"] = clean_name(out.SCH_NAME)
    out["district"] = clean_name(out.district)
    out["level"] = out.band
    out["sector"] = "public"
    out["source"] = "CCD_2024-25"
    out["pk_enrollment"] = out.PK.round().astype(int).where(out.band == "elementary", 0)
    return out[["source", "source_id", "name", "district", "state_fips", "county_fips", "county_name", "lat", "lon", "grade_lo",
                "grade_hi", "sector", "level", "band", "enrollment", "pk_enrollment"]]


# ----------------------------------------------------------------------------------------------------------- PSS private
def build_private():
    p = read_zip_csv(f"{RAW}/nces/pss2324_pu_csv.zip", dtype=str, encoding="latin-1")
    p["state_fips"] = p.PSTANSI.str.zfill(2)
    p = p[p.state_fips.isin(MSTM_STATES)].copy()
    print(f"PSS 2023-24: {len(p):,} private schools in MSTM states; Maryland {int((p.state_fips == '24').sum()):,}")
    p["lat"] = pd.to_numeric(p.LATITUDE24, errors="coerce")
    p["lon"] = pd.to_numeric(p.LONGITUDE24, errors="coerce")
    miss = p.lat.isna() | p.lon.isna()
    if miss.any():                               # fallback: EDGE private-school geocodes 2023-24
        e = gpd.read_file(f"zip://{RAW}/nces/EDGE_GEOCODE_PRIVATESCH_2324.zip")[["PPIN", "LAT", "LON"]].set_index("PPIN")
        p.loc[miss, "lat"] = p.loc[miss, "PPIN"].map(e.LAT)
        p.loc[miss, "lon"] = p.loc[miss, "PPIN"].map(e.LON)
    miss = p.lat.isna() | p.lon.isna()
    print(f"  without coordinates {int(miss.sum())} (dropped)")
    p = p[~miss].copy()
    p["total"] = pd.to_numeric(p.NUMSTUDS, errors="coerce").fillna(0)
    p = p[p.total > 0].copy()
    for c in list(PSS_GRADE_COL.values()) + PSS_UNGRADED + ["P150"]:
        p[c] = pd.to_numeric(p[c], errors="coerce").fillna(0)
    bands = ["elementary", "middle", "high"]
    for b in bands:
        p[b] = sum(p[PSS_GRADE_COL[gr]] for gr, bb in BAND_OF_GRADE.items() if bb == b and gr in PSS_GRADE_COL)
    graded = p[bands].sum(axis=1)
    level_band = p.LEVEL.map({"1": "elementary", "2": "high", "3": "elementary"})
    for b in bands:                              # scale graded counts to the K-12 total; ungraded follow the graded split
        share = np.where(graded > 0, p[b] / graded.replace(0, np.nan), np.where(level_band == b, 1.0, 0.0))
        p[b] = p.total * np.nan_to_num(share)
    p["county_fips"] = p.state_fips + p.PCNTY24.str[:3]
    p["grade_lo"] = pd.to_numeric(p.LOGR2024, errors="coerce").map(PSS_GRADE_CODE)
    p["grade_hi"] = pd.to_numeric(p.HIGR2024, errors="coerce").map(PSS_GRADE_CODE)
    rows = []
    for b in bands:
        s = p[p[b] >= 0.5].copy()
        s["band"] = b
        s["enrollment"] = s[b].round().astype(int)
        rows.append(s)
    out = pd.concat(rows, ignore_index=True)
    out["name"] = clean_name(out.PINST)
    out["district"] = ""
    out["county_name"] = clean_name(out.PCNTNM).str.title()
    out["source_id"] = out.PPIN
    out["sector"] = "private"
    out["level"] = "private"
    out["source"] = "PSS_2023-24"
    out["pk_enrollment"] = out.P150.round().astype(int).where(out.band == "elementary", 0)
    return out[["source", "source_id", "name", "district", "state_fips", "county_fips", "county_name", "lat", "lon", "grade_lo",
                "grade_hi", "sector", "level", "band", "enrollment", "pk_enrollment"]], p


# -------------------------------------------------------------------------------------------------------- IPEDS postsec
def build_postsec():
    h = strip_bom(read_zip_csv(f"{RAW}/ipeds/HD2024.zip", dtype=str, encoding="latin-1"))
    h["state_fips"] = h.FIPS.str.zfill(2)
    h = h[h.state_fips.isin(MSTM_STATES) & (h.CYACTIVE == "1")].copy()
    ef = strip_bom(read_zip_csv(f"{RAW}/ipeds/EF2023A.zip", dtype=str, encoding="latin-1"))
    ef = ef[ef.EFALEVEL.str.strip() == "1"].set_index("UNITID").EFTOTLT.astype(float)         # fall 2023, all students
    fy = strip_bom(read_zip_csv(f"{RAW}/ipeds/EFFY2024.zip", dtype=str, encoding="latin-1"))
    fy = fy[fy.EFFYALEV.str.strip() == "1"].set_index("UNITID").EFYTOTLT.astype(float)        # 12-month 2023-24 (fallback)
    h["enrollment"] = h.UNITID.map(ef)
    h["enrollment_source"] = np.where(h.enrollment.notna(), "fall_2023", "")
    fb = h.enrollment.isna()
    h.loc[fb, "enrollment"] = h.loc[fb, "UNITID"].map(fy) * 0.8      # 12-month headcount is ~1.25x fall headcount nationally
    h.loc[fb & h.enrollment.notna(), "enrollment_source"] = "12month_2023-24_x0.8"
    print(f"IPEDS HD2024: {len(h):,} active institutions in MSTM states, {int((h.enrollment > 0).sum()):,} with enrollment; "
          f"Maryland {int(((h.state_fips == '24') & (h.enrollment > 0)).sum()):,}")
    h = h[h.enrollment.fillna(0) > 0].copy()
    h["lat"] = pd.to_numeric(h.LATITUDE, errors="coerce")
    h["lon"] = pd.to_numeric(h.LONGITUD, errors="coerce")
    h = h[h.lat.notna() & h.lon.notna()].copy()
    out = pd.DataFrame({"source": "IPEDS_" + h.enrollment_source, "source_id": h.UNITID, "name": clean_name(h.INSTNM),
                        "district": "", "state_fips": h.state_fips, "county_fips": h.COUNTYCD.str.zfill(5),
                        "county_name": clean_name(h.COUNTYNM), "lat": h.lat, "lon": h.lon, "grade_lo": "PS", "grade_hi": "PS",
                        "sector": "postsec", "level": "postsec", "band": "postsec", "enrollment": h.enrollment.round().astype(int),
                        "pk_enrollment": 0})
    return out


# ------------------------------------------------------------------------------------------------- synthetic population
def synthetic_children_by_county(zones):
    pp = pd.read_csv(f"{SILO_INPUT}/microData/pp_2016.csv", usecols=["hhID", "age", "occupation"], dtype=np.int32)
    hh = pd.read_csv(f"{SILO_INPUT}/microData/hh_2016.csv", usecols=["id", "dwelling"], dtype=np.int32)
    dd = pd.read_csv(f"{SILO_INPUT}/microData/dd_2016.csv", usecols=["id", "zone"], dtype=np.int32)
    hz = hh.merge(dd, left_on="dwelling", right_on="id", suffixes=("", "_dd"))[["id", "zone"]]
    pp = pp.merge(hz, left_on="hhID", right_on="id", how="left")
    pp["county_fips"] = pp.zone.map(zones.set_index("zone").zone_county)
    pp["age_5_17"] = pp.age.between(5, 17)
    pp["student"] = pp.occupation == 3
    g = pp.groupby("county_fips").agg(synth_persons=("age", "size"), synth_age_5_17=("age_5_17", "sum"),
                                      synth_students_5_17=("student", lambda s: int((s & pp.loc[s.index, "age_5_17"]).sum())),
                                      synth_students_18plus=("student", lambda s: int((s & (pp.loc[s.index, "age"] >= 18)).sum())))
    return g.astype(int)


# ------------------------------------------------------------------------------------------------------------------ main
def main():
    os.makedirs(DATA, exist_ok=True)
    zones = load_zones()
    pub = build_public()
    prv, pss_all = build_private()
    pse = build_postsec()
    inv = pd.concat([pub, prv, pse], ignore_index=True)
    inv, dropped = assign_zones(inv, zones)
    print(f"geocoded to zones: {len(inv):,} school records ({inv.source_id.nunique():,} schools); {len(dropped):,} records outside "
          f"the MSTM zone area dropped, by state {dropped.state_fips.map(MSTM_STATES).value_counts().to_dict() if len(dropped) else {}}")
    assert not (dropped.state_fips == HOME_STATE).any()
    print("  zone method:", inv.zone_method.str.split("_").str[0].value_counts().to_dict())

    # ---- SILO/ABIT file
    inv = inv.sort_values(["sector", "state_fips", "county_fips", "source_id", "band"]).reset_index(drop=True)
    inv.insert(0, "id", np.arange(1, len(inv) + 1))
    inv["type"] = inv.band.map(SILO_TYPE)
    inv["capacity"] = inv.enrollment
    inv["occupancy"] = 0
    inv["startTime"] = inv.band.map(lambda b: SCHOOL_DAY[b][0])
    inv["duration"] = inv.band.map(lambda b: SCHOOL_DAY[b][1])
    inv["enrollment_year"] = inv.source.map(lambda s: "2024-25" if s.startswith("CCD") else "2023-24" if s.startswith("PSS") else "2023")
    cols = ["id", "zone", "type", "capacity", "occupancy", "coordX", "coordY", "startTime", "duration", "level", "band", "sector",
            "source", "source_id", "name", "district", "state_fips", "county_fips", "county_name", "grade_lo", "grade_hi",
            "pk_enrollment", "lat", "lon", "enrollment_year", "zone_method"]
    inv = inv[cols]
    for c in ["name", "district", "county_name"]:
        assert not inv[c].str.contains(",").any()       # SILO and ABIT readers split lines on commas
    inv.to_csv(f"{SILO_INPUT}/schools.csv", index=False)
    print(f"wrote {SILO_INPUT}/schools.csv: {len(inv):,} records, capacity {inv.capacity.sum():,}")
    print(inv.groupby(["sector", "level"]).agg(records=("id", "size"), schools=("source_id", "nunique"),
                                              capacity=("capacity", "sum")).to_string())

    # ---- capacity by zone and school type
    cap = inv.pivot_table(index="zone", columns="level", values="capacity", aggfunc="sum").fillna(0).astype(int)
    for c in ["elementary", "middle", "high", "private", "postsec"]:
        if c not in cap:
            cap[c] = 0
    cap = cap[["elementary", "middle", "high", "private", "postsec"]]
    cap["k12_total"] = cap[["elementary", "middle", "high", "private"]].sum(axis=1)
    cap["schools"] = inv.groupby("zone").source_id.nunique()
    cap = cap.reset_index().merge(zones[["zone", "zone_county"]].rename(columns={"zone_county": "county_fips"}), on="zone", how="left")
    cap = cap[["zone", "county_fips", "schools", "elementary", "middle", "high", "private", "postsec", "k12_total"]]
    cap.to_csv(f"{DATA}/schools_capacity_by_zone.csv", index=False)
    print(f"wrote {DATA}/schools_capacity_by_zone.csv: {len(cap):,} zones with schools of {len(zones):,}")

    # ---- validation by county: inventory vs NCES state totals vs synthetic 5-17-year-olds
    md = inv[inv.state_fips == "24"]
    byc = inv.pivot_table(index="county_fips", columns="level", values="capacity", aggfunc="sum").fillna(0).astype(int)
    byc["public_k12"] = byc[["elementary", "middle", "high"]].sum(axis=1)
    byc = byc.rename(columns={"private": "private_k12"})
    byc["k12_total"] = byc.public_k12 + byc.private_k12
    byc["public_schools"] = inv[inv.sector == "public"].groupby("county_fips").source_id.nunique()
    byc["private_schools"] = inv[inv.sector == "private"].groupby("county_fips").source_id.nunique()
    byc["postsec_institutions"] = inv[inv.sector == "postsec"].groupby("county_fips").source_id.nunique()
    byc["district"] = inv[inv.sector == "public"].groupby("county_fips").district.agg(lambda s: " | ".join(sorted(set(s))[:3]))
    names = pd.Series(dtype=object)                      # county names: public-school geocodes first, then IPEDS, then PSS
    for sec in ["public", "postsec", "private"]:
        n = inv[inv.sector == sec].groupby("county_fips").county_name.agg(lambda s: s.mode().iloc[0])
        names = names.combine_first(n)
    syn = synthetic_children_by_county(zones)
    t = byc.join(syn, how="outer").fillna(0)
    jur = zones.drop_duplicates("zone_county").set_index("zone_county").JUR_NAME
    t["county_name"] = pd.Series(t.index.map(names), index=t.index).fillna(pd.Series(t.index.map(jur), index=t.index))
    t["state"] = t.index.str[:2].map(MSTM_STATES)
    t["k12_per_child_5_17"] = (t.k12_total / t.synth_age_5_17.replace(0, np.nan)).round(3)
    t["public_k12_per_student_5_17"] = (t.public_k12 / t.synth_students_5_17.replace(0, np.nan)).round(3)
    t = t.reset_index().rename(columns={"index": "county_fips"})
    t = t[["county_fips", "county_name", "state", "district", "public_schools", "private_schools", "postsec_institutions", "public_k12",
           "private_k12", "k12_total", "postsec", "synth_persons", "synth_age_5_17", "synth_students_5_17", "synth_students_18plus",
           "k12_per_child_5_17", "public_k12_per_student_5_17"]]
    t = t.sort_values(["state", "county_fips"], key=lambda s: s.map({"MD": 0}).fillna(1) if s.name == "state" else s)

    # state rows with the NCES reference totals
    sea = read_zip_csv(f"{RAW}/nces/ccd_sea_052_2425_l_1a_073025.zip", dtype=str, encoding="latin-1")
    sea["STUDENT_COUNT"] = pd.to_numeric(sea.STUDENT_COUNT, errors="coerce")
    state_rows = []
    for fips, st in MSTM_STATES.items():
        s = sea[sea.FIPST == fips]
        total = s[s.TOTAL_INDICATOR == "Education Unit Total"].STUDENT_COUNT.sum()
        pk = s[(s.TOTAL_INDICATOR == "Subtotal 4 - By Grade") & (s.GRADE == "Pre-Kindergarten")].STUDENT_COUNT.sum()
        ps = pss_all[pss_all.state_fips == fips]
        sub = t[t.state == st]
        state_rows.append({"county_fips": fips, "county_name": f"{st} state total (inventory)", "state": st,
                           "district": f"NCES public K-12 excl. PK {total - pk:,.0f} (CCD state file; incl. PK {total:,.0f}); "
                                       f"PSS private K-12 weighted {float((ps.total * ps.PFNLWT.astype(float)).sum()):,.0f} "
                                       f"(unweighted {ps.total.sum():,.0f})",
                           **{c: sub[c].sum() for c in t.columns if c not in ("county_fips", "county_name", "state", "district",
                                                                              "k12_per_child_5_17", "public_k12_per_student_5_17")},
                           "nces_public_k12_reference": total - pk,
                           "pss_private_k12_reference": float((ps.total * ps.PFNLWT.astype(float)).sum())})
    sr = pd.DataFrame(state_rows)
    sr["k12_per_child_5_17"] = (sr.k12_total / sr.synth_age_5_17.replace(0, np.nan)).round(3)
    sr["public_k12_per_student_5_17"] = (sr.public_k12 / sr.synth_students_5_17.replace(0, np.nan)).round(3)
    sr["inventory_over_nces_public"] = (sr.public_k12 / sr.nces_public_k12_reference.replace(0, np.nan)).round(3)
    t = pd.concat([t, sr], ignore_index=True)
    for c in ["public_schools", "private_schools", "postsec_institutions", "public_k12", "private_k12", "k12_total", "postsec",
              "synth_persons", "synth_age_5_17", "synth_students_5_17", "synth_students_18plus"]:
        t[c] = t[c].fillna(0).astype(int)
    t.to_csv(f"{DATA}/schools_validation_by_county.csv", index=False)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 200)
    show = t[t.state == "MD"].drop(columns=["district", "state"])
    print("\nMaryland counties: school inventory vs synthetic population 2016 (NCES totals in the state row)")
    print(show.to_string(index=False))
    print("\nState rows:")
    print(t[t.county_name.str.contains("state total")][["state", "public_k12", "nces_public_k12_reference", "inventory_over_nces_public",
                                                         "private_k12", "pss_private_k12_reference", "postsec", "synth_age_5_17",
                                                         "k12_per_child_5_17"]].to_string(index=False))
    print(f"wrote {DATA}/schools_validation_by_county.csv")


if __name__ == "__main__":
    main()
