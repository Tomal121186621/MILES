#!/usr/bin/env python3
"""Stage 2b: give every 2016 synthetic student a school record (schoolId) by grade band, distance and capacity.

Run with `python3 -I assign_students.py` from this folder (about 5 minutes, most of it reading and writing the
12.5 million person records).

Inputs
  2_silo/input/microData/pp_2016.csv, hh_2016.csv, dd_2016.csv   persons (occupation 3 = STUDENT), household -> dwelling -> zone
  2_silo/input/schools.csv                                       school records by grade band (build_schools.py)
  2_silo/input/skims/auto_peak_time.csv.gz                       zone-to-zone car travel time, minutes (FROM,TO,VALUE)
  2_silo/input/zones.shp, zoneSystem.csv                         zone centroids (EPSG:26918) and county of each zone
  ABIT/input/rts/rts_trips_clean.csv                             survey trips to school (d_activity 4), distance in miles

Rule (the same as SchoolDataMd in the engine, applied offline to all students at once)
  band by age: elementary 5-10 (students younger than 5 go with elementary), middle 11-13, high 14-17, post-secondary 18+
  for a home zone and a band the school records of the band's SILO type (1 elementary, 2 middle+high, 3 post-secondary)
  are ranked by (record band matches the band wanted, zone-to-zone car time; straight-line centroid distance at 30 km/h
  where the skim has no value, larger capacity first on ties); students are drawn in random order (seed 1) and each takes
  the first school of the ranking with a free seat (occupancy < capacity), the nearest school when all are full.
  Cross-county assignment is allowed; the zone system has no state border for the search either.

Outputs
  pp_2016.csv                       the same file with a schoolId column appended (-1 for non-students)
  2_silo/input/schools.csv          occupancy column filled with the students assigned
  2_silo/input/schools_2016.csv     the file SILO reads (school.file.ascii = input/schools, start year 2016)
  Validation_2026/data/schools_assignment_validation.csv          by home county (county of the zone, zoneSystem.csv):
                                                                  students vs capacity by band, share of students in a
                                                                  school of their own county, mean distance
  Validation_2026/data/schools_assignment_validation_by_band.csv  by band: mean/median distance and car time of the
                                                                  assignment vs the survey school trips (RTS 2023)
"""
import os
import sys
import time

import numpy as np
import pandas as pd

V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"
S = f"{V}/2_silo"
PP = f"{S}/input/microData/pp_2016.csv"
HH = f"{S}/input/microData/hh_2016.csv"
DD = f"{S}/input/microData/dd_2016.csv"
SCHOOLS = f"{S}/input/schools.csv"
SCHOOLS_2016 = f"{S}/input/schools_2016.csv"
SKIM = f"{S}/input/skims/auto_peak_time.csv.gz"
ZONES_SHP = f"{S}/input/zones.shp"
ZONE_SYSTEM = f"{S}/input/zoneSystem.csv"
RTS = f"{V}/../ABIT/input/rts/rts_trips_clean.csv"
VAL_COUNTY = f"{V}/data/schools_assignment_validation.csv"
VAL_BAND = f"{V}/data/schools_assignment_validation_by_band.csv"

SEED = 1
STUDENT = 3                       # Occupation.STUDENT code (PersonReaderMstm / Occupation.java)
BANDS = {1: "elementary", 2: "middle", 3: "high", 4: "postsec"}
BAND_TYPE = {1: 1, 2: 2, 3: 2, 4: 3}   # SILO type of each band (SchoolDataMd.typeForBand)
FALLBACK_M_PER_MIN = 500.0             # 30 km/h where the skim has no value (SchoolDataMd.FALLBACK_METRES_PER_MINUTE)
MILE_KM = 1.609344

t0 = time.time()


def log(msg):
    print(f"[{time.time() - t0:6.0f} s] {msg}", flush=True)


def band_for_age(age):
    return np.select([age < 11, age < 14, age < 18], [1, 2, 3], default=4)


# ---------------------------------------------------------------- inputs
log("reading persons, households, dwellings")
pp = pd.read_csv(PP, dtype={"race": "category", "relationShip": "category"})   # categories keep the strings and the memory low
hh = pd.read_csv(HH, usecols=["id", "dwelling"])
dd = pd.read_csv(DD, usecols=["id", "zone"])
log(f"{len(pp):,} persons, {len(hh):,} households, {len(dd):,} dwellings")

hh_zone = hh.merge(dd, left_on="dwelling", right_on="id", how="left", suffixes=("", "_dd"))
hh_zone = pd.Series(hh_zone["zone"].values, index=hh_zone["id"].values)
is_student = (pp["occupation"] == STUDENT).values
students = pp.loc[is_student, ["id", "hhID", "age"]].copy()
students["zone"] = hh_zone.reindex(students["hhID"].values).values
missing_zone = students["zone"].isna().sum()
if missing_zone:
    log(f"WARNING {missing_zone:,} students without a dwelling zone are left without a school (-1)")
students = students.dropna(subset=["zone"])
students["zone"] = students["zone"].astype(int)
students["band"] = band_for_age(students["age"].values)
log(f"{len(students):,} students; by band: " + ", ".join(f"{BANDS[b]} {n:,}" for b, n in students['band'].value_counts().sort_index().items()))

log("reading zones, skim and schools")
zs = pd.read_csv(ZONE_SYSTEM, usecols=["ZoneId", "COUNTYFIPS", "JUR_NAME"])
zone_county = pd.Series(zs["COUNTYFIPS"].values, index=zs["ZoneId"].values)
county_name = zs.drop_duplicates("COUNTYFIPS").set_index("COUNTYFIPS")["JUR_NAME"]
import geopandas as gpd  # noqa: E402  (imported here so that the pandas part runs without it)
zg = gpd.read_file(ZONES_SHP)
zg["zid"] = zg["SMZRMZ"].astype(int)
cent = zg.geometry.centroid
zone_cx = pd.Series(cent.x.values, index=zg["zid"].values)
zone_cy = pd.Series(cent.y.values, index=zg["zid"].values)
NZ = int(max(zs["ZoneId"].max(), zg["zid"].max())) + 1
skim = pd.read_csv(SKIM)
T = np.full((NZ, NZ), np.nan)
T[skim["FROM"].values.astype(int), skim["TO"].values.astype(int)] = skim["VALUE"].values
log(f"skim {len(skim):,} pairs, {np.isfinite(T[1:, 1:]).mean() * 100:.1f} % of zone pairs with a value")

sch = pd.read_csv(SCHOOLS)
sch["band_code"] = sch["band"].map({v: k for k, v in BANDS.items()}).fillna(0).astype(int)
sch["capacity"] = sch["capacity"].astype(int)
log(f"{len(sch):,} school records, capacity by band: " + ", ".join(f"{BANDS[b]} {c:,}" for b, c in sch.groupby('band_code')['capacity'].sum().items()))

# ---------------------------------------------------------------- rankings per home zone and band
sch_type = sch["type"].values
sch_band = sch["band_code"].values
sch_zone = sch["zone"].values.astype(int)
sch_cap = sch["capacity"].values.astype(int)
sch_x = sch["coordX"].values
sch_y = sch["coordY"].values
sch_id = sch["id"].values.astype(int)
idx_by_type = {t: np.where(sch_type == t)[0] for t in (1, 2, 3)}
rankings = {}
no_skim_pairs = 0


def ranking(zone, band):
    """School indices ordered by (band mismatch, minutes, -capacity, id); computed once per zone and band."""
    global no_skim_pairs
    key = (zone, band)
    if key in rankings:
        return rankings[key]
    cand = idx_by_type[BAND_TYPE[band]]
    minutes = T[zone, sch_zone[cand]]
    ok = np.isfinite(minutes) & (minutes > 0)
    if not ok.all():
        dist = np.hypot(sch_x[cand] - zone_cx.get(zone, np.nan), sch_y[cand] - zone_cy.get(zone, np.nan))
        minutes = np.where(ok, minutes, dist / FALLBACK_M_PER_MIN)
        no_skim_pairs += int((~ok).sum())
    mismatch = (sch_band[cand] != 0) & (sch_band[cand] != band)
    order = np.lexsort((sch_id[cand], -sch_cap[cand], minutes, mismatch))
    r = cand[order]
    rankings[key] = (r, minutes[order], mismatch[order])
    return rankings[key]


# ---------------------------------------------------------------- assignment
log("assigning students (random order, first school of the ranking with a free seat)")
rng = np.random.default_rng(SEED)
order = rng.permutation(len(students))
st_zone = students["zone"].values
st_band = students["band"].values
occ = np.zeros(len(sch), dtype=np.int64)
assigned = np.full(len(students), -1, dtype=np.int64)      # index into sch
minutes_out = np.full(len(students), np.nan)
mismatch_out = np.zeros(len(students), dtype=bool)
overflow_out = np.zeros(len(students), dtype=bool)
pointer = {}                                                # (zone, band) -> first position of the ranking that may have a seat
for n, i in enumerate(order):
    key = (st_zone[i], st_band[i])
    r, mins, mism = ranking(*key)
    p = pointer.get(key, 0)
    while p < len(r) and occ[r[p]] >= sch_cap[r[p]]:
        p += 1
    pointer[key] = p
    if p < len(r):
        j = p
    else:                                                   # every school of the band full: nearest school anyway
        j = 0
        overflow_out[i] = True
    s = r[j]
    occ[s] += 1
    assigned[i] = s
    minutes_out[i] = mins[j]
    mismatch_out[i] = mism[j]
    if n % 500000 == 0 and n:
        log(f"  {n:,} students assigned")
log(f"assigned {len(students):,} students; {overflow_out.sum():,} to a full school (band capacity exhausted), "
    f"{mismatch_out.sum():,} to a record of the other secondary band, {no_skim_pairs:,} zone-school pairs ranked by straight-line distance")

students["schoolId"] = sch_id[assigned]
students["school_zone"] = sch_zone[assigned]
students["minutes"] = minutes_out
students["km"] = np.hypot(sch_x[assigned] - zone_cx.reindex(st_zone).values, sch_y[assigned] - zone_cy.reindex(st_zone).values) / 1000.0
students["home_county"] = zone_county.reindex(st_zone).values
# the county of a school is the county of its zone (zoneSystem COUNTYFIPS), not the NCES county_fips: the zone system
# merges the Virginia independent cities into their counties (51919, 51942, 51951), the NCES codes keep them apart
sch["zone_county"] = zone_county.reindex(sch_zone).values.astype(int)
students["school_county"] = sch["zone_county"].values[assigned]
students["within_county"] = students["home_county"] == students["school_county"]
students["overflow"] = overflow_out
students["mismatch"] = mismatch_out

# ---------------------------------------------------------------- outputs: persons and schools
log("writing pp_2016.csv with the schoolId column")
school_col = np.full(len(pp), -1, dtype=np.int64)
school_col[students.index.values] = students["schoolId"].values
pp["schoolId"] = school_col
tmp = PP + ".tmp"
pp.to_csv(tmp, index=False)
os.replace(tmp, PP)
log(f"pp_2016.csv written: {len(pp):,} rows, {(pp['schoolId'] > 0).sum():,} with a school")

sch["occupancy"] = occ
sch.drop(columns=["band_code", "zone_county"]).to_csv(SCHOOLS, index=False)
sch.drop(columns=["band_code", "zone_county"]).to_csv(SCHOOLS_2016, index=False)
log(f"schools.csv and schools_2016.csv written with occupancy ({occ.sum():,} seats taken of {sch_cap.sum():,})")

# ---------------------------------------------------------------- validation by county
log("validation tables")
rows = []
cap_by_county_band = sch.groupby(["zone_county", "band_code"])["capacity"].sum().unstack(fill_value=0)
st_by_county_band = students.groupby(["home_county", "band"]).size().unstack(fill_value=0)
occ_by_county_band = sch.assign(occ=occ).groupby(["zone_county", "band_code"])["occ"].sum().unstack(fill_value=0)
counties = sorted(set(cap_by_county_band.index) | set(st_by_county_band.index))
for c in counties:
    r = {"county_fips": c, "county_name": county_name.get(c, ""), "state": {11: "DC", 10: "DE", 24: "MD", 42: "PA", 51: "VA", 54: "WV"}.get(c // 1000, "")}
    sub = students[students["home_county"] == c]
    k12 = sub[sub["band"] <= 3]
    for b, name in BANDS.items():
        r[f"students_{name}"] = int(st_by_county_band.get(b, pd.Series(dtype=int)).get(c, 0))
        r[f"capacity_{name}"] = int(cap_by_county_band.get(b, pd.Series(dtype=int)).get(c, 0))
        r[f"assigned_in_county_{name}"] = int(occ_by_county_band.get(b, pd.Series(dtype=int)).get(c, 0))
    r["students_k12"] = int(k12.shape[0])
    r["capacity_k12"] = sum(r[f"capacity_{BANDS[b]}"] for b in (1, 2, 3))
    r["capacity_per_student_k12"] = round(r["capacity_k12"] / r["students_k12"], 3) if r["students_k12"] else np.nan
    r["assigned_in_county_k12"] = sum(r[f"assigned_in_county_{BANDS[b]}"] for b in (1, 2, 3))
    r["share_within_own_county_k12"] = round(k12["within_county"].mean(), 3) if len(k12) else np.nan
    r["share_within_own_county_postsec"] = round(sub.loc[sub["band"] == 4, "within_county"].mean(), 3) if (sub["band"] == 4).any() else np.nan
    r["mean_km_k12"] = round(k12["km"].mean(), 2) if len(k12) else np.nan
    r["mean_minutes_k12"] = round(k12["minutes"].mean(), 1) if len(k12) else np.nan
    r["mean_km_postsec"] = round(sub.loc[sub["band"] == 4, "km"].mean(), 2) if (sub["band"] == 4).any() else np.nan
    r["students_in_full_school"] = int(sub["overflow"].sum())
    rows.append(r)
tot = {"county_fips": "ALL", "county_name": "zone area total", "state": ""}
for k in rows[0]:
    if k in ("county_fips", "county_name", "state"):
        continue
    if k.startswith(("students_", "capacity_", "assigned_")) and not k.startswith("capacity_per"):
        tot[k] = sum(r[k] for r in rows)
k12 = students[students["band"] <= 3]
tot["capacity_per_student_k12"] = round(tot["capacity_k12"] / tot["students_k12"], 3)
tot["share_within_own_county_k12"] = round(k12["within_county"].mean(), 3)
tot["share_within_own_county_postsec"] = round(students.loc[students["band"] == 4, "within_county"].mean(), 3)
tot["mean_km_k12"] = round(k12["km"].mean(), 2)
tot["mean_minutes_k12"] = round(k12["minutes"].mean(), 1)
tot["mean_km_postsec"] = round(students.loc[students["band"] == 4, "km"].mean(), 2)
tot["students_in_full_school"] = int(students["overflow"].sum())
rows.append(tot)
val = pd.DataFrame(rows)
val.to_csv(VAL_COUNTY, index=False)

# ---------------------------------------------------------------- validation by band, with the survey
rts = pd.read_csv(RTS, usecols=["d_activity", "age", "distance", "wtperfin", "student_status"])
rts = rts[(rts["d_activity"] == 4) & (rts["distance"] > 0) & (rts["age"] >= 0)].copy()
rts["band"] = band_for_age(rts["age"].values)
rts["km"] = rts["distance"] * MILE_KM
band_rows = []
for b, name in BANDS.items():
    sub = students[students["band"] == b]
    sv = rts[rts["band"] == b]
    w = sv["wtperfin"].clip(lower=0)
    band_rows.append({
        "band": name, "ages": {1: "5-10", 2: "11-13", 3: "14-17", 4: "18+"}[b],
        "students": len(sub), "capacity": int(sch.loc[sch["band_code"] == b, "capacity"].sum()),
        "capacity_per_student": round(sch.loc[sch["band_code"] == b, "capacity"].sum() / len(sub), 3),
        "share_within_own_county": round(sub["within_county"].mean(), 3),
        "share_in_full_school": round(sub["overflow"].mean(), 4),
        "share_other_secondary_band": round(sub["mismatch"].mean(), 4),
        "mean_km_straight_line": round(sub["km"].mean(), 2), "median_km_straight_line": round(sub["km"].median(), 2),
        "mean_car_minutes": round(sub["minutes"].mean(), 1), "median_car_minutes": round(sub["minutes"].median(), 1),
        "share_same_zone": round((sub["zone"] == sub["school_zone"]).mean(), 3),
        "rts_school_trips": len(sv),
        "rts_mean_km_driving": round(sv["km"].mean(), 2) if len(sv) else np.nan,
        "rts_median_km_driving": round(sv["km"].median(), 2) if len(sv) else np.nan,
        "rts_weighted_mean_km_driving": round(np.average(sv["km"], weights=w), 2) if len(sv) and w.sum() > 0 else np.nan,
    })
pd.DataFrame(band_rows).to_csv(VAL_BAND, index=False)

print()
print(val[["county_fips", "county_name", "students_k12", "capacity_k12", "capacity_per_student_k12", "share_within_own_county_k12",
           "mean_km_k12", "students_postsec", "capacity_postsec", "share_within_own_county_postsec", "students_in_full_school"]].to_string(index=False))
print()
print(pd.DataFrame(band_rows).to_string(index=False))
log("done")
