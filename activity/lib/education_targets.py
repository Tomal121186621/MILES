#!/usr/bin/env python3
"""Stage 2b/3: survey targets for the DAYMAP EDUCATION tours (school tours of students), by age band.

Run with `python3 -I activity/lib/education_targets.py [--split estimation|validation] [--out FILE]` from the repository root. Writes `targets_education.csv` (read by
DAYMAP `models/maryland/MarylandFrequencyGenerator` through the property `education.targets.file`) and, with
`--write-mode-targets`, replaces the EDUCATION rows of `ABIT/input/maryland/coef/rt_mode_by_purpose.csv`
(the ASC re-anchor targets of `MarylandFullModeChoice`).

Source: the cleaned regional household travel survey in `ABIT/input/rts/` (see `2_silo/data_sources.md`):
`RTS_raw_flat_data.csv` for the person records (age, student_status, school_freq, school_type, wtperfin,
tdate_dow) and `rts_trips_clean.csv` for the trips (d_activity 4 = School, travel_mode codes of the codebook
sheet Trip, distance = driving miles, arr_min/dep_min minutes after midnight, wttrdfin). Both files hold only
persons who reported at least one trip on the travel day (`trips_yesno` = 1 for all 41,914 persons,
`person_tripcount` >= 1), so every per-student rate below is conditional on travelling that day; all
travel days are weekdays (`tdate_dow` 1-5).

Band = traveller's age: elementary 5-10, middle 11-13, high 14-17, postsec 18+ (the SILO bands of
`2_silo/schools/assign_base_students.py`); students = `student_status` 1 and age >= 5 and not a worker (employment_status 0:
a working student is EMPLOYED in SILO and makes work tours in DAYMAP, so the school-day probability is that of the
non-working students; stage 3, 2026-10-22).
Stage 3 (2026-10-22): `--split estimation` restricts persons and trips to the households of that half of
`Validation_2026/data/rts_split.csv` (the calibration targets come from the estimation half only); `--out` sets the
output file (the calibrated coefficient set keeps its own copy); `--write-mode-targets` writes into the file named by
the environment variable ABIT_COEF_DIR (default the pristine coef folder).
Metrics per band (person weight wtperfin for per-student rates, trip weight wttrdfin for trip attributes):
  school_tour_rate        arrivals at school (d_activity 4 from a non-school origin) per student per weekday
  school_day_prob         share of students with at least one such arrival on the travel day
                          (= attendance probability per weekday used by DAYMAP; 1 - share without a school trip)
  no_school_trip_share    1 - school_day_prob
  attend_days_per_week    cross-check from the person question school_freq (5/4/3/2/1 weekdays, weekends only,
                          < 4 weekdays a month, online only), mean over students who answered
  mode_<M>                share of school trips by survey mode (codebook travel_mode) and by DAYMAP mode after the
                          rule: school bus (6), paratransit (10), taxi (11), rideshare (12) -> CAR_PASSENGER
                          (MATSim `ride`: a passenger leg that puts no vehicle on the network, as the school-bus
                          fleet is not part of the network supply and not in the GTFS schedule); private bus (9)
                          -> BUS; motorcycle (3) -> CAR_DRIVER; air, water, other (13-15) dropped
  arrival_mean_min, arrival_p10/p50/p90   arrival time at school, minutes after midnight
  school_duration_p50_min                 time at school = next departure from school (o_activity 4) - arrival
  dist_mean_km, dist_p50_km               driving distance of school trips (miles x 1.60934), weighted
  escort_share_under14    share of school trips of students under 14 made as auto passenger with another
                          household member on the trip (travelers_hh > 1): drop-off by a household adult
  dropoff_trips_per_adult drop-off/pick-up trips (d_activity 16) per adult (18+) per travel day, for the open
                          ACCOMPANY item
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd

ROOT = f"{PROJECT_ROOT}"
RTS = f"{ABIT_HOME}/input/rts"
OUT = f"{WORKSPACE}/3_abit/targets_education.csv"
MODE_FILE = (os.environ.get("ABIT_COEF_DIR") or f"{ABIT_HOME}/input/maryland/coef") + "/rt_mode_by_purpose.csv"
SPLIT_FILE = f"{WORKSPACE}/data/rts_split.csv"
BANDS = ["elementary", "middle", "high", "postsec"]
MI_KM = 1.60934


def band_of(age):
    return pd.cut(age, [4, 10, 13, 17, 200], labels=BANDS)


# survey mode code -> (survey label, DAYMAP mode)
MODE = {1: ("walk", "WALK"), 2: ("bike", "BIKE"), 3: ("motorcycle", "CAR_DRIVER"), 4: ("auto_driver", "CAR_DRIVER"),
        5: ("auto_passenger", "CAR_PASSENGER"), 6: ("school_bus", "CAR_PASSENGER"), 7: ("rail", "TRAIN"),
        8: ("bus", "BUS"), 9: ("private_bus", "BUS"), 10: ("paratransit", "CAR_PASSENGER"),
        11: ("taxi", "CAR_PASSENGER"), 12: ("rideshare", "CAR_PASSENGER")}
ABIT_MODES = ["CAR_DRIVER", "CAR_PASSENGER", "TRAIN", "TRAM_METRO", "BUS", "BIKE", "WALK"]


def wmean(x, w):
    w = np.asarray(w, float); x = np.asarray(x, float)
    return float((x * w).sum() / w.sum()) if w.sum() > 0 else float("nan")


def wquantile(x, w, q):
    x = np.asarray(x, float); w = np.asarray(w, float)
    o = np.argsort(x); x, w = x[o], w[o]
    c = np.cumsum(w) / w.sum()
    return float(x[np.searchsorted(c, q)])


def main():
    write_modes = "--write-mode-targets" in sys.argv
    half = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else None
    out_file = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT
    raw = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", low_memory=False,
                      usecols=["person_id", "household_id", "age", "student_status", "school_freq", "school_type",
                               "wtperfin", "tdate_dow", "trips_yesno", "person_tripcount", "employment_status"])
    persons = raw.drop_duplicates("person_id").set_index("person_id")
    assert (persons.trips_yesno == 1).all() and persons.tdate_dow.between(1, 5).all()
    trips = pd.read_csv(f"{RTS}/rts_trips_clean.csv",
                        usecols=["person_id", "household_id", "tripno", "o_activity", "d_activity", "travel_mode", "age",
                                 "student_status", "distance", "travelers_hh", "arr_min", "dep_min", "wttrdfin"])
    if half:
        keep = set(pd.read_csv(SPLIT_FILE).query("half == @half").household_id)
        persons = persons[persons.household_id.isin(keep)]; trips = trips[trips.household_id.isin(keep)]
        print(f"split {half}: {len(keep)} households, {len(persons)} persons, {len(trips)} trips")
    working = persons.employment_status == 0
    trips_all = trips
    trips = trips[~trips.person_id.isin(persons.index[working])]   # trips of working students are not school-tour trips of STUDENTs
    students = persons[(persons.student_status == 1) & (persons.age >= 5) & ~working].copy()
    students["band"] = band_of(students.age)

    # school arrivals per student (tours to school)
    sch = trips[(trips.d_activity == 4) & (trips.o_activity != 4)]
    n_arr = sch.groupby("person_id").size()
    students["n_school"] = n_arr.reindex(students.index).fillna(0).astype(int)
    # time at school: next departure from school after each arrival
    t = trips.sort_values(["person_id", "tripno"])
    t["next_o"] = t.groupby("person_id").o_activity.shift(-1)
    t["next_dep"] = t.groupby("person_id").dep_min.shift(-1)
    t["school_dur"] = np.where((t.d_activity == 4) & (t.next_o == 4), t.next_dep - t.arr_min, np.nan)
    sch_trips = t[(t.d_activity == 4) & (t.o_activity != 4) & (t.student_status == 1) & (t.age >= 5)].copy()   # working students removed above
    sch_trips["band"] = band_of(sch_trips.age)
    sch_trips["km"] = sch_trips.distance * MI_KM
    freq_days = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 0, 7: 0.5, 8: 0}

    rows = []
    def add(band, metric, value, n, note=""):
        rows.append(dict(band=band, metric=metric, value=round(float(value), 4), n_unweighted=int(n), note=note))

    for b in BANDS + ["all"]:
        s = students if b == "all" else students[students.band == b]
        st = sch_trips if b == "all" else sch_trips[sch_trips.band == b]
        w = s.wtperfin
        add(b, "students_n", len(s), len(s), "survey students (travellers only), unweighted count")
        add(b, "school_tour_rate", wmean(s.n_school, w), len(s), "school arrivals per student per weekday, wtperfin")
        add(b, "school_day_prob", wmean(s.n_school >= 1, w), len(s), "share of students with a school trip on the travel day")
        add(b, "no_school_trip_share", wmean(s.n_school == 0, w), len(s), "1 - school_day_prob")
        sf = s[s.school_freq.isin(freq_days)]
        add(b, "attend_days_per_week", wmean(sf.school_freq.map(freq_days), sf.wtperfin), len(sf),
            "school_freq question, mean weekdays per week; /5 = attendance probability")
        # modes
        mt = st[st.travel_mode.isin(MODE)]
        tw = mt.wttrdfin
        for code, (lab, _) in MODE.items():
            add(b, f"mode_survey_{lab}", wmean(mt.travel_mode == code, tw), (mt.travel_mode == code).sum(), "share of school trips, wttrdfin")
        abit = mt.travel_mode.map(lambda c: MODE[c][1])
        for m in ABIT_MODES:
            add(b, f"mode_abit_{m}", wmean(abit == m, tw), (abit == m).sum(), "school bus -> CAR_PASSENGER rule")
        if b in ("elementary", "middle"):
            add(b, "escort_share_under14", wmean((st.travel_mode == 5) & (st.travelers_hh > 1), st.wttrdfin),
                len(st), "school trips as auto passenger with another household member on the trip")
        # times
        at = st[st.arr_min.between(0, 1440)]
        add(b, "arrival_mean_min", wmean(at.arr_min, at.wttrdfin), len(at), "arrival at school, min after midnight")
        for q in (0.1, 0.5, 0.9):
            add(b, f"arrival_p{int(q*100)}_min", wquantile(at.arr_min, at.wttrdfin, q), len(at), "")
        du = st[st.school_dur.between(30, 900)]
        add(b, "school_duration_p50_min", wquantile(du.school_dur, du.wttrdfin, 0.5), len(du), "arrival to next departure from school")
        add(b, "school_duration_mean_min", wmean(du.school_dur, du.wttrdfin), len(du), "")
        di = st[st.km.between(0, 300)]
        add(b, "dist_mean_km", wmean(di.km, di.wttrdfin), len(di), "driving distance of school trips, wttrdfin")
        add(b, "dist_p50_km", wquantile(di.km, di.wttrdfin, 0.5), len(di), "")
        add(b, "dist_mean_km_unweighted", di.km.mean(), len(di), "")

    adults = persons[persons.age >= 18]
    drop = trips_all[trips_all.d_activity == 16].groupby("person_id").size().reindex(adults.index).fillna(0)
    add("all", "dropoff_trips_per_adult", wmean(drop, adults.wtperfin), len(adults), "d_activity 16 trips per adult 18+ per travel day (travellers only)")
    u14 = sch_trips[sch_trips.age < 14]
    add("all", "escort_share_under14", wmean((u14.travel_mode == 5) & (u14.travelers_hh > 1), u14.wttrdfin), len(u14),
        "school trips of students under 14 as auto passenger with a household member")

    out = pd.DataFrame(rows)
    out.to_csv(out_file, index=False)
    print(f"wrote {out_file}: {len(out)} rows")
    show = out[out.metric.isin(["students_n", "school_tour_rate", "school_day_prob", "attend_days_per_week", "mode_survey_school_bus",
                                "mode_abit_CAR_PASSENGER", "mode_abit_CAR_DRIVER", "mode_abit_BUS", "mode_abit_WALK",
                                "arrival_p50_min", "school_duration_p50_min", "dist_mean_km", "dist_p50_km", "escort_share_under14"])]
    print(show.pivot(index="metric", columns="band", values="value").reindex(columns=BANDS + ["all"]).to_string())

    if write_modes:
        allrow = out[(out.band == "all") & out.metric.str.startswith("mode_abit_")].set_index("metric").value
        mf = pd.read_csv(MODE_FILE)
        for m in ABIT_MODES:
            mf.loc[(mf.purpose == "EDUCATION") & (mf["mode"] == m), "share"] = round(float(allrow[f"mode_abit_{m}"]), 6)
        mf.to_csv(MODE_FILE, index=False)
        print(f"EDUCATION rows of {MODE_FILE} replaced:\n" + mf[mf.purpose == "EDUCATION"].to_string(index=False))


if __name__ == "__main__":
    main()
