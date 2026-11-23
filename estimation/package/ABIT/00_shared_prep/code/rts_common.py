#!/usr/bin/env python3
"""Shared definitions of the stage-3 survey side (build_targets.py, validate_abit.py): how the 2017/18 Regional Travel
Survey (ABIT/input/rts) is read, split, mapped onto the DAYMAP purposes, modes and person types, and summarised.

Survey facts that shape every definition (checked 2026-10-22):
  - rts_trips_clean.csv (163,290 trips of 41,914 persons in 21,788 households) and RTS_raw_flat_data.csv hold only persons
    with at least one trip on their travel day (trips_yesno = 1 for all), so every per-person rate is per TRAVELLER-day
    (conditional on travelling).  The household record (hhsize against the persons that appear) gives the share of
    household members without a trip, which is the only all-persons quantity the files allow.
  - all travel days are weekdays (tdate_dow 1-5), Oct 2017 - Oct 2018; weights wthhfin (household), wtperfin (person),
    wttrdfin (trip; equal to wtperfin in the cleaned file).
  - distance = driving miles between the reported addresses (-9 missing, 0.3 % above 200 mi: airport/long-distance, capped).

DAYMAP purposes (abm.data.plans.Purpose) from the survey activity codes (codebook sheet Trip, O_/D_ACTIVITY):
  WORK 2 Work | EDUCATION 4 School | SHOPPING 5 Shopping | ACCOMPANY 16 Drop off/pick up |
  RECREATION 7 Meal, 11 Socialize, 13 Exercise, 14 Recreation, 15 Entertainment |
  OTHER 3 Volunteer, 6 Meal (quick-stop), 8 Gas, 9 Health care, 10 Non-shopping errand, 12 Civic/Religious, 17 (change
  mode, 0.3 %), 18 Other.  HOME 1.
DAYMAP modes (schools README rule): 1 walk -> WALK, 2 bike -> BIKE, 3 motorcycle -> CAR_DRIVER, 4 auto driver -> CAR_DRIVER,
  5 auto passenger -> CAR_PASSENGER, 6 school bus -> CAR_PASSENGER (MATSim `ride`, no vehicle on the network), 7 rail -> TRAIN,
  8 bus -> BUS, 9 private bus -> BUS, 10 paratransit / 11 taxi / 12 rideshare -> CAR_PASSENGER; 13-15 air, water, other dropped.
Person types (the SILO occupations DAYMAP sees: 1 EMPLOYED, 3 STUDENT, 4 RETIREE, 2 UNEMPLOYED; 0 TODDLER has no tours):
  worker   employment_status 0 (worker incl. self-employed; a working student is a worker, as in SILO)
  student  student_status 1 and not a worker, by age band elementary 5-10, middle 11-13, high 14-17, postsec 18+
  retiree  employment_status 1
  nonworker  everyone else aged 5+ (homemaker, unemployed, disabled, volunteer, non-student children)
  persons under 5 are excluded (toddlers).
"""
# COPY of Validation_2026/3_abit/rts_common.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "00_shared_data"))          # provided inputs
RAW = _os_pkg.environ.get("ABIT_RAW", _os_pkg.path.join(SHARED, "raw"))                                                              # your downloads
REBUILT = _os_pkg.environ.get("ABIT_REBUILT", _os_pkg.path.join(SHARED, "rebuilt"))                  # outputs of this chain
MDATA = REBUILT
import numpy as np
import pandas as pd

ROOT = SHARED  # PATH
V = SHARED  # PATH
RTS = f"{SHARED}/rts_2017_18/raw"  # PATH
SPLIT_FILE = f"{SHARED}/rts_2017_18/split/rts_split.csv"  # PATH
MI_KM = 1.60934

PURPOSES = ["WORK", "EDUCATION", "SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
ACT_PURPOSE = {2: "WORK", 4: "EDUCATION", 5: "SHOPPING", 16: "ACCOMPANY",
               7: "RECREATION", 11: "RECREATION", 13: "RECREATION", 14: "RECREATION", 15: "RECREATION",
               3: "OTHER", 6: "OTHER", 8: "OTHER", 9: "OTHER", 10: "OTHER", 12: "OTHER", 17: "OTHER", 18: "OTHER", 1: "HOME"}
MODES = ["CAR_DRIVER", "CAR_PASSENGER", "BUS", "TRAIN", "WALK", "BIKE"]
MODE_MAP = {1: "WALK", 2: "BIKE", 3: "CAR_DRIVER", 4: "CAR_DRIVER", 5: "CAR_PASSENGER", 6: "CAR_PASSENGER", 7: "TRAIN",
            8: "BUS", 9: "BUS", 10: "CAR_PASSENGER", 11: "CAR_PASSENGER", 12: "CAR_PASSENGER"}
SEGMENTS = ["worker", "student_elementary", "student_middle", "student_high", "student_postsec", "nonworker", "retiree"]
SEG_GROUPS = {"student": ["student_elementary", "student_middle", "student_high", "student_postsec"]}   # pooled segments
STOP_SPEC = {"WORK": "HBW", "EDUCATION": "HBE", "SHOPPING": "HBS", "RECREATION": "HBO", "ACCOMPANY": "HBO", "OTHER": "HBO"}
# driving-distance bins (km) of the trip-length distributions
DIST_BINS = [0, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 50, 1e9]
DIST_LABELS = ["0-1", "1-2", "2-3", "3-5", "5-7.5", "7.5-10", "10-15", "15-20", "20-30", "30-50", "50+"]
DIST_CAP_KM = 300.0
HOURS = list(range(24))
# county of residence: reported by county when the half holds at least MIN_HH_COUNTY households, else pooled as 'other'
MIN_HH_COUNTY = 150


def band_of(age):
    return pd.cut(age, [4, 10, 13, 17, 200], labels=["elementary", "middle", "high", "postsec"]).astype(str)


def person_type(emp, stu, age):
    """Vectorised person type (see module docstring); 'toddler' for age < 5 (excluded from rates)."""
    emp = np.asarray(emp); stu = np.asarray(stu); age = np.asarray(age)
    out = np.full(len(age), "nonworker", dtype=object)
    out[emp == 0] = "worker"
    is_stu = (stu == 1) & (emp != 0)
    b = band_of(pd.Series(age)).values
    out[is_stu] = np.char.add("student_", b[is_stu].astype(str))
    out[(emp == 1) & ~is_stu] = "retiree"
    out[age < 5] = "toddler"
    return out


def wmean(x, w):
    x = np.asarray(x, float); w = np.asarray(w, float); m = np.isfinite(x)
    return float((x[m] * w[m]).sum() / w[m].sum()) if w[m].sum() > 0 else float("nan")


def wquantile(x, w, q):
    x = np.asarray(x, float); w = np.asarray(w, float); m = np.isfinite(x); x, w = x[m], w[m]
    if len(x) == 0: return float("nan")
    o = np.argsort(x); x, w = x[o], w[o]; c = np.cumsum(w) / w.sum()
    return float(x[min(len(x) - 1, np.searchsorted(c, q))])


def wshares(cat, w, cats):
    """Weighted share of each category in `cats` (categories outside the list are ignored in the denominator)."""
    cat = np.asarray(cat); w = np.asarray(w, float); m = np.isin(cat, cats); tot = w[m].sum()
    return {c: float(w[m & (cat == c)].sum() / tot) if tot > 0 else float("nan") for c in cats}


def whist(x, w, bins):
    """Weighted share per bin (bins as np.histogram edges); values outside are dropped."""
    x = np.asarray(x, float); w = np.asarray(w, float); m = np.isfinite(x)
    h, _ = np.histogram(x[m], bins=bins, weights=w[m]); return h / h.sum() if h.sum() > 0 else h


def kish_n(w):
    w = np.asarray(w, float); return float(w.sum() ** 2 / (w ** 2).sum()) if len(w) else 0.0


def ks_stat(x1, w1, x2, w2):
    """Two-sample KS statistic between two weighted samples (max |F1 - F2|)."""
    x1 = np.asarray(x1, float); x2 = np.asarray(x2, float); w1 = np.asarray(w1, float); w2 = np.asarray(w2, float)
    m1, m2 = np.isfinite(x1), np.isfinite(x2); x1, w1, x2, w2 = x1[m1], w1[m1], x2[m2], w2[m2]
    if len(x1) == 0 or len(x2) == 0: return float("nan")
    xs = np.sort(np.unique(np.concatenate([x1, x2])))
    o1 = np.argsort(x1); o2 = np.argsort(x2)
    c1 = np.cumsum(w1[o1]) / w1.sum(); c2 = np.cumsum(w2[o2]) / w2.sum()
    f1 = np.interp(xs, x1[o1], c1, left=0.0); f2 = np.interp(xs, x2[o2], c2, left=0.0)
    # step functions: evaluate just at the sample points (right-continuous)
    f1 = c1[np.searchsorted(x1[o1], xs, side="right") - 1]; f2 = c2[np.searchsorted(x2[o2], xs, side="right") - 1]
    f1 = np.where(np.searchsorted(x1[o1], xs, side="right") == 0, 0.0, f1); f2 = np.where(np.searchsorted(x2[o2], xs, side="right") == 0, 0.0, f2)
    return float(np.max(np.abs(f1 - f2)))


def ks_critical(n1, n2, alpha=0.05):
    c = {0.10: 1.22, 0.05: 1.36, 0.01: 1.63}[alpha]
    return float(c * np.sqrt((n1 + n2) / (n1 * n2))) if n1 > 0 and n2 > 0 else float("nan")


def coincidence_ratio(p, q):
    """Coincidence ratio of two binned distributions (sum of bin minima / sum of bin maxima; 1 = identical)."""
    p = np.asarray(p, float); q = np.asarray(q, float)
    return float(np.minimum(p, q).sum() / np.maximum(p, q).sum()) if np.maximum(p, q).sum() > 0 else float("nan")


# ------------------------------------------------------------------------------------------------ survey loading
def load_households():
    """One record per household from the raw flat file: home county, size, workers, students, vehicles, weight,
    and the number of household members that appear with at least one trip (travellers)."""
    cols = ["household_id", "person_id", "home_state_county_fips", "hhsize", "numworkers", "numstudents", "numvehicle",
            "wthhfin", "tdate_dow", "in_tpb", "in_bmc"]
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv.gz", usecols=cols, low_memory=False)
    h = r.drop_duplicates("household_id").set_index("household_id").drop(columns="person_id")
    h["n_travellers"] = r.drop_duplicates("person_id").groupby("household_id").size().reindex(h.index).fillna(0).astype(int)
    h = h.rename(columns={"home_state_county_fips": "county"})
    return h


def load_persons():
    cols = ["household_id", "person_id", "age", "gender", "license", "employment_status", "student_status", "school_freq",
            "school_type", "wtperfin", "tdate_dow", "work_state_county_fips", "home_state_county_fips", "j1_telecommute",
            "j1_telecommute_days", "person_tripcount", "trips_yesno"]
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv.gz", usecols=cols, low_memory=False)
    p = r.drop_duplicates("person_id").set_index("person_id")
    p["ptype"] = person_type(p.employment_status, p.student_status, p.age)
    p = p.rename(columns={"home_state_county_fips": "county", "work_state_county_fips": "work_county"})
    return p


def load_trips():
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv.gz", low_memory=False,
                    usecols=["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "travel_mode",
                             "distance", "dep_min", "arr_min", "wttrdfin", "travelers_hh", "age"])
    t["o_purpose"] = t.o_activity.map(ACT_PURPOSE); t["d_purpose"] = t.d_activity.map(ACT_PURPOSE)
    # trip purpose: the non-home end (destination unless the trip goes home); home-home and unknown ends -> OTHER
    t["purpose"] = np.where(t.d_purpose.eq("HOME"), t.o_purpose, t.d_purpose)
    t["purpose"] = t.purpose.where(t.purpose.notna() & t.purpose.ne("HOME"), "OTHER")
    t["mode"] = t.travel_mode.map(MODE_MAP)           # NaN for air/water/other (dropped from mode shares)
    t["km"] = np.where(t.distance >= 0, t.distance * MI_KM, np.nan); t.loc[t.km > DIST_CAP_KM, "km"] = DIST_CAP_KM
    t["dep_hour"] = (t.dep_min // 60).clip(0, 23)
    # destination county of the trip (raw flat file, joined on tripid): own-county work share = home -> work trips whose
    # destination county is the home county (stage-3 definition, 2026-10-22; stage 1 uses the county of the assigned job)
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv.gz", usecols=["tripid", "d_state_county_fips", "home_state_county_fips"], low_memory=False).drop_duplicates("tripid")
    t = t.merge(r.rename(columns={"d_state_county_fips": "d_county", "home_state_county_fips": "home_county"}), on="tripid", how="left")
    for c in ["d_county", "home_county"]: t[c] = pd.to_numeric(t[c], errors="coerce").fillna(-9).astype(int)
    return t


def load_tours():
    """Home-based closed tours of the cleaned survey (rts_tours.csv) with the DAYMAP purpose of the primary activity.
    Work-based subtours (purpose WBO, anchor work) are kept with purpose SUBTOUR; open (incomplete) tours are dropped."""
    tr = pd.read_csv(f"{RTS}/rts_tours.csv.gz")
    tr = tr[tr.anchor.isin(["home", "work"])].copy()
    tr["purpose_abit"] = np.where(tr.anchor.eq("work"), "SUBTOUR", tr.primary_act.map(ACT_PURPOSE).fillna("OTHER"))
    tr.loc[tr.purpose_abit.eq("HOME"), "purpose_abit"] = "OTHER"
    tr["dist_primary_km"] = np.where(tr.dist_primary >= 0, tr.dist_primary * MI_KM, np.nan)
    tr["duration_min"] = tr.primary_dep - tr.primary_arr
    tr["start_hour"] = (tr.start_min // 60).clip(0, 23)
    return tr


def tour_main_mode(tours, trips):
    """Mode of the trip that arrives at the primary activity of each tour (tour-level mode for the DAYMAP re-anchor
    targets): matched on person and arrival minute; the first matching trip is taken."""
    key = trips[["person_id", "arr_min", "mode"]].drop_duplicates(["person_id", "arr_min"])
    m = tours[["person_id", "primary_arr"]].merge(key, left_on=["person_id", "primary_arr"], right_on=["person_id", "arr_min"], how="left")
    return m["mode"].values


def load_split():
    s = pd.read_csv(SPLIT_FILE).set_index("household_id").half
    return s


def county_groups(h, half):
    """Counties reported individually in the half (>= MIN_HH_COUNTY households), the rest 'other'."""
    n = h[h.half.eq(half)].groupby("county").size()
    return sorted(n[n >= MIN_HH_COUNTY].index.tolist())
