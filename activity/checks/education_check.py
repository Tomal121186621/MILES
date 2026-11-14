#!/usr/bin/env python3
"""Stage 2b/3 check of the EDUCATION tours in an ABIT run.  Usage: python3 -I activity/checks/education_check.py <run name> [year]

Reads 3_abit/run/<name>/output/activities_<name>.csv and legs_<name>.csv, the SILO person file of the year (ages,
occupation 3 = student; band elementary 5-10, middle 11-13, high 14-17, postsec 18+) and 3_abit/targets_education.csv.
Prints: persons and tours by purpose (tours = main activities, activity_type MANDATORY or PRIMARY, Monday-Friday),
EDUCATION tours per student per weekday by band against the survey school_day_prob, the school start-time
distribution, the mean/median home-school distance and the EDUCATION mode shares by band against the survey.
Writes the same tables to 3_abit/run/<name>/education_check.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
name = sys.argv[1]; year = int(sys.argv[2]) if len(sys.argv) > 2 else 2016
run = f"{V}/3_abit/run/{name}"
BANDS = ["elementary", "middle", "high", "postsec"]
band_of = lambda age: pd.cut(age, [-1, 10, 13, 17, 200], labels=BANDS)

act = pd.read_csv(f"{run}/output/activities_{name}.csv")
legs = pd.read_csv(f"{run}/output/legs_{name}.csv")
pp = None
for d in [f"{V}/2_silo/input/microData", f"{V}/2_silo/run/base/scenOutput/base/microData", f"{V}/2_silo/run/base/scenOutput/base/microData/futureYears"]:
    if os.path.exists(f"{d}/pp_{year}.csv"):
        pp = pd.read_csv(f"{d}/pp_{year}.csv", usecols=["id", "age", "occupation", "schoolId"]).set_index("id"); break
tg = pd.read_csv(f"{V}/3_abit/targets_education.csv").set_index(["band", "metric"]).value

persons = act.person_id.unique()
pp = pp.loc[pp.index.intersection(persons)] if pp is not None else None
# the sample: all persons of the run are in the activities file only when they travel; take the student count from the
# person file restricted to the households of the run (persons of those households may have no activity)
hh_in_run = set(act.household_id.unique())
tours = act[act.activity_type.isin(["MANDATORY", "PRIMARY"]) & act.day.between(1, 5)]
rows = []
def add(section, band, metric, model, survey=np.nan, n=np.nan):
    rows.append(dict(section=section, band=band, metric=metric, model=model, survey=survey, n=n))

print(f"run {name}: activities {len(act)}, legs {len(legs)}, persons with a plan {len(persons)}, households {len(hh_in_run)}")
tp = tours.groupby("purpose").size()
for p, n in tp.items(): add("tours", "all", f"tours_{p}_weekdays", n)
print("tours (main activities, Mon-Fri) by purpose:\n" + (tp / 5).round(0).astype(int).to_string() + "   (per weekday)")

# students of the run: persons of the sampled households with occupation 3
ppall = pd.read_csv(f"{V}/2_silo/input/microData/pp_{year}.csv" if year == 2016 else f"{V}/2_silo/run/base/scenOutput/base/microData/futureYears/pp_{year}.csv",
                    usecols=["id", "hhID", "age", "occupation", "schoolId"])
stu = ppall[(ppall.occupation == 3) & ppall.hhID.isin(hh_in_run)].copy()
stu["band"] = band_of(stu.age)
edu = tours[tours.purpose == "EDUCATION"].merge(stu[["id", "band", "age"]], left_on="person_id", right_on="id", how="left")
print(f"\nstudents in the sampled households: {len(stu)}; EDUCATION tours Mon-Fri: {len(edu)}; students with any: {edu.person_id.nunique()}")
print(f"{'band':12s} {'students':>9s} {'edu tours/student/weekday':>26s} {'survey school_day_prob':>23s} {'survey tour rate':>17s}")
for b in BANDS + ["all"]:
    s = stu if b == "all" else stu[stu.band == b]; e = edu if b == "all" else edu[edu.band == b]
    rate = len(e) / 5 / max(1, len(s))
    add("frequency", b, "edu_tours_per_student_weekday", rate, tg[(b, "school_day_prob")], len(s))
    add("frequency", b, "survey_school_tour_rate", np.nan, tg[(b, "school_tour_rate")], len(s))
    print(f"{b:12s} {len(s):9d} {rate:26.3f} {tg[(b, 'school_day_prob')]:23.3f} {tg[(b, 'school_tour_rate')]:17.3f}")

# start times (minutes of day) by band
edu["start"] = edu.start_time_min % 1440; edu["dur"] = edu.end_time_min - edu.start_time_min
print("\nschool start time (min after midnight) and duration by band:")
print(f"{'band':12s} {'p10':>6s} {'p50':>6s} {'p90':>6s} {'mean':>7s} {'survey arr p50':>15s} {'dur p50':>8s} {'survey dur p50':>15s}")
for b in BANDS:
    e = edu[edu.band == b]
    if len(e) == 0: continue
    q = e.start.quantile([.1, .5, .9]).values
    add("start", b, "start_p50_min", q[1], tg[(b, "arrival_p50_min")], len(e)); add("start", b, "start_mean_min", e.start.mean(), tg[(b, "arrival_mean_min")], len(e))
    add("start", b, "duration_p50_min", e.dur.median(), tg[(b, "school_duration_p50_min")], len(e))
    print(f"{b:12s} {q[0]:6.0f} {q[1]:6.0f} {q[2]:6.0f} {e.start.mean():7.1f} {tg[(b, 'arrival_p50_min')]:15.0f} {e.dur.median():8.0f} {tg[(b, 'school_duration_p50_min')]:15.0f}")
hist = (edu.start // 30 * 30).value_counts(normalize=True).sort_index()
print("start-time histogram (30-min bins, share of EDUCATION tours): " + ", ".join(f"{int(k)//60:02d}:{int(k)%60:02d} {v:.2f}" for k, v in hist.items() if v >= 0.01))

# school trips: legs arriving at EDUCATION from home
sl = legs[(legs.next_purpose == "EDUCATION") & (legs.previous_purpose == "HOME")].merge(stu[["id", "band"]], left_on="person_id", right_on="id", how="left")
sl["km"] = sl.distance_m / 1000.
print("\nhome-school trip distance (km, car skim) and mode shares by band:")
print(f"{'band':12s} {'n':>6s} {'mean km':>8s} {'survey':>7s} {'median':>7s} {'survey':>7s}   CAR_DRIVER CAR_PASSENGER BUS TRAIN WALK BIKE (model / survey)")
for b in BANDS + ["all"]:
    e = sl if b == "all" else sl[sl.band == b]
    if len(e) == 0: continue
    add("distance", b, "dist_mean_km", e.km.mean(), tg[(b, "dist_mean_km")], len(e)); add("distance", b, "dist_p50_km", e.km.median(), tg[(b, "dist_p50_km")], len(e))
    ms = e["mode"].value_counts(normalize=True)
    mm = []
    for m in ["CAR_DRIVER", "CAR_PASSENGER", "BUS", "TRAIN", "WALK", "BIKE"]:
        add("mode", b, f"mode_{m}", ms.get(m, 0.0), tg[(b, f"mode_abit_{m}")], len(e)); mm.append(f"{ms.get(m, 0.0):.2f}/{tg[(b, f'mode_abit_{m}')]:.2f}")
    print(f"{b:12s} {len(e):6d} {e.km.mean():8.2f} {tg[(b, 'dist_mean_km')]:7.2f} {e.km.median():7.2f} {tg[(b, 'dist_p50_km')]:7.2f}   " + "  ".join(mm))

pd.DataFrame(rows).to_csv(f"{run}/education_check.csv", index=False)
print(f"\nwrote {run}/education_check.csv")
