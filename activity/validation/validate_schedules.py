#!/usr/bin/env python3
"""Trip-level validation of the tour formation and scheduling (3 November 2026): ABIT on the survey households (10 replications per
half) against the weighted 2017/18 RTS, before and after the work-based subtour model, the re-estimated return-home logit and the
licence cells of the accompany frequency.

    python3 activity/validation/validate_schedules.py survey --sets rail,sched          -> data/sched_validation_survey.csv, printed tables
    python3 activity/validation/validate_schedules.py y2024 --runs DIR1,DIR2 ...        -> 2024 runs (unweighted) against the weighted survey (all halves)

Measures (both sides the same definitions; trips of the representative weekday; model persons carry the weight of the survey
person they represent; distance = car-distance zone skim between the trip's zones, intrazonal 0.5 sqrt(area), on both sides;
survey zones = zone of the tract internal point):
  trips and car-driver trips per person (all persons of the half, incl. imputed non-travellers);
  car-driver trips: shares under 1, 2 and 5 miles, mean km;
  outings from the workplace: work activities followed by one or more activities other than home / work / school and a return
    to work in the same zone, per home-based tour with a work activity (subtour share);
  discretionary activities (shopping, recreation, accompany, other) by position: separate home-based tour without work, stop on
    a work tour before / after the work, inside an outing from work; by person type and whether the person worked that day;
  by trip purpose (work if either end is work, shopping if either end is shopping, else other): mean miles, share under 2 miles,
    car driver and car passenger shares.
Survey car driver = RTS modes 3 and 4 (MODE_MAP)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, glob, os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, f"{ORIOLE_HOME}/activity/lib"); sys.path.insert(0, f"{ORIOLE_HOME}/activity/survey")
HERE = f"{WORKSPACE}/3_abit"   # data (survey_pop)
from rts_common import V, RTS, ACT_PURPOSE, MODE_MAP, load_split
from activity_metrics import dist_matrix
from survey_population import tract_zone, geoid, RUNROOT

KM_MI = 1 / 1.609344
DISC = {"SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"}
OUT = f"{V}/data"


def ptype(occ, age):
    return np.select([occ == 1, (occ == 3) & (age < 18), occ == 3, occ == 4], ["worker", "student 5-17", "student 18+", "retiree"], "non-worker")


def survey_trips(half):
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", low_memory=False,
                    usecols=["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "o_tract_fips", "d_tract_fips", "travel_mode", "wttrdfin", "dep_min", "distance"])
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", usecols=["tripid", "o_state_county_fips", "d_state_county_fips"], low_memory=False).drop_duplicates("tripid").set_index("tripid")
    s = load_split(); t = t[t.household_id.map(s).eq(half)].sort_values(["person_id", "tripno"], kind="stable")
    tz = tract_zone().set_index("geoid").zone
    for e in "od": t[f"{e}z"] = geoid(t.tripid.map(r[f"{e}_state_county_fips"]), t[f"{e}_tract_fips"]).map(tz).fillna(0).astype(int).values
    pm = pd.read_csv(f"{HERE}/survey_pop/{half}/persons_map.csv")
    pmp = pm.drop_duplicates("person_id").set_index("person_id")
    out = pd.DataFrame({"pid": t.person_id.values, "t": t.dep_min.values, "prev": t.o_activity.map(ACT_PURPOSE).fillna("OTHER").values,
                        "next": t.d_activity.map(ACT_PURPOSE).fillna("OTHER").values, "oz": t.oz.values, "dz": t.dz.values,
                        "mode": t.travel_mode.map(MODE_MAP).values, "w": t.wttrdfin.values,
                        "own_mi": np.where(t.distance.values > 0, np.minimum(t.distance.values, 200.0), np.nan)})
    out["ptype"] = ptype(out.pid.map(pmp.occ).values, out.pid.map(pmp.age).values)
    lic = pd.read_csv(f"{HERE}/survey_pop/{half}/pp.csv", usecols=["id", "driversLicense"]).set_index("id").driversLicense.astype(str).eq("True")
    out["lic"] = (out.pid.map(pmp.id).map(lic).fillna(False) & (out.pid.map(pmp.age) >= 16)).values
    return out, float(pm.w.sum())


def model_trips(d, half):
    f = glob.glob(f"{d}/output/legs_*.csv")
    if os.path.exists(f"{d}/output/legs_full.parquet"):
        l = pd.read_parquet(f"{d}/output/legs_full.parquet", columns=["person_id", "start_time_min", "previous_purpose", "next_purpose", "start_zone", "end_zone", "mode", "distance_m"])
    else:
        l = pd.read_csv(f[0], usecols=["person_id", "start_time_min", "previous_purpose", "next_purpose", "start_zone", "end_zone", "mode", "distance_m"], engine="pyarrow")
    for c in ["start_time_min", "start_zone", "end_zone", "person_id"]: l[c] = pd.to_numeric(l[c])
    l = l[(l.start_time_min >= 0) & (l.start_time_min < 1440)].sort_values(["person_id", "start_time_min"], kind="stable")
    out = pd.DataFrame({"pid": l.person_id.values, "t": l.start_time_min.values, "prev": l.previous_purpose.astype(str).values, "next": l.next_purpose.astype(str).values,
                        "oz": l.start_zone.values.astype(int), "dz": l.end_zone.values.astype(int), "mode": l["mode"].astype(str).values,
                        "own_mi": pd.to_numeric(l.distance_m).values / 1609.344})
    if half is None:
        out["w"] = 1.0; out["ptype"] = "all"; return out, None
    pm = pd.read_csv(f"{HERE}/survey_pop/{half}/persons_map.csv").set_index("id")
    out["w"] = out.pid.map(pm.w).fillna(0).values; out["ptype"] = ptype(out.pid.map(pm.occ).values, out.pid.map(pm.age).values)
    lic = pd.read_csv(f"{HERE}/survey_pop/{half}/pp.csv", usecols=["id", "driversLicense"]).set_index("id").driversLicense.astype(str).eq("True")
    out["lic"] = (out.pid.map(lic).fillna(False) & (out.pid.map(pm.age) >= 16)).values
    return out, float(pm.w.sum())


def measures(x, wsum, dm, npersons=None):
    """x: trips of one source (sorted by person and time)."""
    r = {}
    W = wsum if wsum is not None else float(npersons)
    ok = (x.oz > 0) & (x.dz > 0)
    km = np.full(len(x), np.nan); km[ok.values] = dm[x.oz.values[ok.values], x.dz.values[ok.values]]
    x = x.assign(km=km, mi=km * KM_MI)
    r["trips_pp"] = x.w.sum() / W
    cd = x["mode"].eq("CAR_DRIVER"); r["cd_trips_pp"] = x.w[cd].sum() / W
    c = x[cd & x.km.notna()]
    for b in [1, 2, 5]: r[f"cd_lt{b}mi"] = 100 * c.w[c.mi < b].sum() / c.w.sum()
    r["cd_mean_km"] = np.average(c.km, weights=c.w)
    # own distance measure: survey = reported address-to-address miles; model = ABIT leg distance (micro locations)
    c2 = x[cd & np.isfinite(x.own_mi)]
    for b in [1, 2, 5]: r[f"cd_lt{b}mi_own"] = 100 * c2.w[c2.own_mi < b].sum() / c2.w.sum()
    r["cd_mean_km_own"] = np.average(c2.own_mi, weights=c2.w) / KM_MI
    # purpose table
    pur = np.select([x.prev.eq("WORK") | x.next.eq("WORK"), x.prev.eq("SHOPPING") | x.next.eq("SHOPPING")], ["work", "shopping"], "other")
    for g in ["work", "shopping", "other", "all"]:
        m = (np.ones(len(x), bool) if g == "all" else pur == g) & x.km.notna().values; s = x[m]
        r[f"{g}_mean_mi"] = np.average(s.mi, weights=s.w); r[f"{g}_lt2"] = 100 * s.w[s.mi < 2].sum() / s.w.sum()
        r[f"{g}_cd"] = 100 * s.w[s["mode"].eq("CAR_DRIVER")].sum() / s.w.sum(); r[f"{g}_cp"] = 100 * s.w[s["mode"].eq("CAR_PASSENGER")].sum() / s.w.sum()
    # accompany (drop-off / pick-up): trips to an accompany activity
    if "lic" in x:
        a = x[x.next.eq("ACCOMPANY")]
        r["acc_trips_pp"] = a.w.sum() / W; r["acc_unlic_share"] = 100 * a.w[~a.lic].sum() / a.w.sum()
        r["acc_cd"] = 100 * a.w[a["mode"].eq("CAR_DRIVER")].sum() / a.w.sum(); al = a[a.lic]; r["acc_cd_licensed"] = 100 * al.w[al["mode"].eq("CAR_DRIVER")].sum() / al.w.sum()
    # tours and positions of discretionary activities
    pid = x.pid.values; nxt = x.next.values; dz = x.dz.values; w = x.w.values; pt = x.ptype.values
    newp = np.r_[True, pid[1:] != pid[:-1]]
    tour = np.cumsum(newp | np.r_[False, nxt[:-1] == "HOME"])   # a tour starts at the person's first trip or after arriving home
    df = pd.DataFrame({"pid": pid, "tour": tour, "act": nxt, "z": dz, "w": w, "pt": pt})
    df = df[df.act.ne("HOME")]
    df["pos"] = df.groupby("tour").cumcount()
    isw = df.act.eq("WORK")
    fw = df[isw].groupby("tour").pos.min(); lw = df[isw].groupby("tour").pos.max()
    df["fw"] = df.tour.map(fw); df["lw"] = df.tour.map(lw)
    workday = df.pid.isin(df.pid[isw].unique())
    # outings: work (zone z) -> non-home/work/school activities -> work in zone z
    a = df.act.values; zz = df.z.values; tr = df.tour.values; n_out = 0.0; insub = np.zeros(len(df), bool)
    for i in range(len(df) - 1):
        if a[i] != "WORK": continue
        j = i + 1
        while j < len(df) and tr[j] == tr[i] and a[j] in DISC: j += 1
        if j < len(df) and tr[j] == tr[i] and j > i + 1 and a[j] == "WORK" and zz[j] == zz[i]:
            n_out += df.w.values[i]; insub[i + 1:j] = True
    wt = df[isw].drop_duplicates("tour")
    r["outings_per_work_tour"] = 100 * n_out / wt.w.sum()
    d = df[df.act.isin(DISC)].assign(insub=insub[df.act.isin(DISC).values], wd=workday[df.act.isin(DISC)].values)
    cls = np.select([d.fw.isna(), d.insub, d.pos < d.fw, d.pos > d.lw], ["separate", "outing", "before_work", "after_work"], "between_work")
    d["cls"] = cls
    for wd, lab in [(True, "workday"), (False, "nonworkday")]:
        s = d[d.wd == wd]
        for k in ["separate", "before_work", "after_work", "outing", "between_work"]: r[f"{lab}_{k}"] = 100 * s.w[s.cls == k].sum() / s.w.sum()
    for p_ in ["worker", "non-worker", "student 5-17", "student 18+", "retiree"]:
        s = d[(d.pt == p_)]
        if len(s): r[f"sep_{p_}"] = 100 * s.w[s.cls == "separate"].sum() / s.w.sum()
    r["disc_per_person"] = d.w.sum() / W
    return r


def survey_setting(sets, halves=("estimation", "validation")):
    dm = dist_matrix(); rows = []
    for half in halves:
        s, W = survey_trips(half); r = measures(s, W, dm); rows.append(dict(source="survey", half=half, rep=0, **r)); print(f"survey {half} done", flush=True)
        for st in sets:
            for k in range(1, 11):
                d = f"{RUNROOT}/svy_{half[:3]}_{st}_s{k:02d}"
                if not glob.glob(f"{d}/output/legs_*.csv"): continue
                m, W = model_trips(d, half); rows.append(dict(source=st, half=half, rep=k, **measures(m, W, dm)))
            print(f"{st} {half} done", flush=True)
    return pd.DataFrame(rows)


def summary(df):
    g = df.groupby(["source", "half"]).mean(numeric_only=True).drop(columns="rep").T
    return g


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["survey", "y2024"]); ap.add_argument("--sets", default="rail,sched"); ap.add_argument("--runs", default="")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if a.cmd == "survey":
        df = survey_setting(a.sets.split(",")); df.to_csv(f"{OUT}/sched_validation_survey{a.tag}.csv", index=False)
        pd.set_option("display.width", 250); print(summary(df).round(2).to_string())
    else:
        dm = dist_matrix(); rows = []
        s, W = survey_trips("estimation"); s2, W2 = survey_trips("validation")
        r = measures(pd.concat([s, s2], ignore_index=True).sort_values(["pid", "t"], kind="stable"), W + W2, dm); rows.append(dict(source="survey", run="", **r))
        for d in a.runs.split(","):
            pp = pd.read_parquet(f"{d}/output/persons.parquet").person_id.nunique()
            m, _ = model_trips(d, None); rows.append(dict(source=os.path.basename(os.path.dirname(d)) if d.endswith("/") else os.path.basename(d), run=d, **measures(m, None, dm, pp)))
            print(d, "done", flush=True)
        df = pd.DataFrame(rows); df.to_csv(f"{OUT}/sched_validation_2024{a.tag}.csv", index=False); print(df.drop(columns="run").set_index("source").T.round(2).to_string())
