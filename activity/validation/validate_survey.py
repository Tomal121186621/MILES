#!/usr/bin/env python3
"""Stage 3: verification and validation of DAYMAP in the design of Roorda, Miller & Habib (2008), Transportation Research Part A
42, 360-375 ("Validation of TASHA"): activity frequency and distance by activity type (their Tables 1-2), activity start-time
distributions (Figs. 2, 6), activity durations by start time (Figs. 3, 7), trips per chain (Fig. 4) and distance by start
time (Figs. 5, 8).

    python3 activity/validation/validate_survey.py [--settings verification,validation,chain] [--figures-only]

Settings (10 replications each, seeds 1-10; model = mean and standard deviation over the replications, ddof = 1)
  verification  DAYMAP on the observed population of the ESTIMATION half of the 2017/18 RTS (survey_population.py), compared
                with the observed travel of these households (the data the calibration targets were built from).
  validation    DAYMAP on the observed population of the VALIDATION half, compared with the travel of these households (never
                used by the calibration).
  chain         the chain runs 3_abit/run/val_s01..10: DAYMAP on a 5 % sample of the synthetic 2016 base population, compared with
                the validation half of the survey (error of the activity model plus the error of the synthetic population).
  validation_mnl, chain_mnl   the same with the estimated destination MNL (3_abit/destination_choice, 2026-10-22): runs
                svy_est_mnl_s01..10 (verification_mnl), svy_val_mnl_s01..10 and val_mnl_s01..10 (skims: base car, 2024 door-to-door transit, 3_abit/skims/base_transit2024).
  No parameter is adjusted in any of these comparisons.

Activities: one activity per trip, at the trip's destination (survey: rts_trips_clean.csv; model: the legs of the
representative weekday, Monday, representative_day.REP_DAY); start = arrival time of the trip; duration = departure of the person's next
trip minus the arrival (none for the last trip of the day); distance (2026-10-23: like for like) = the zone-skim (network)
distance of the trip to the activity on both sides: model: car-distance skim between the trip's zones; survey: the same skim
between the zones of the trip's origin and destination tracts (tract internal point -> zone, the measurement of the destination
choice work and of every stage-3 comparison); intrazonal 0.5 sqrt(area), activity_metrics.dist_matrix; capped at 300 km.  The
survey's reported (address-to-address driving) distance is kept as a secondary comparison (observed_km_reported,
diff_km_pct_reported; observed_reported in the distance-by-hour curves).  Types (Roorda Table 1): work, school (EDUCATION), shopping, other (RECREATION, ACCOMPANY, OTHER and
work-based subtour activities, also reported separately), return home.
Exclusions (Roorda: trips external to the region, facilitate-passenger trips, children under 11):
  base     persons under 5 (DAYMAP does not schedule activities for children under 5) and survey trips with an end outside the
           model zone system (tract point outside every zone); accompany trips are kept, since DAYMAP generates them.
  roorda   in addition persons under 11 and accompany (drop-off / pick-up) activities: the closest analogue of Roorda's rule.
Weights and scale: survey trips carry the person weight; in the survey-population runs every model person carries the weight
of the survey person it represents (imputed non-travellers: the household weight), so both sides estimate the same weighted
population, and both totals are scaled to the number of persons simulated (persons 5+, resp. 11+): total x N / sum of the
person weights.  In the chain setting the model is unweighted (N = synthetic persons in the zone counties of the survey
households) and the observed weighted total is scaled to that N.
KS tests: (i) Roorda's form, reproduced from the D and P values of their figures (D is a multiple of 1/n, P matches the
asymptotic two-sample formula with n = m = number of hours): the two-sample KS statistic between the SET of hourly values of
the model and the set of hourly values of the survey (hourly shares, Figs. 2/6; hourly mean durations, Figs. 3/7), P = Q_KS(
(sqrt(Ne) + 0.12 + 0.11/sqrt(Ne)) D), Ne = n m / (n + m) (Press et al., Numerical Recipes); this test compares the two sets of
values irrespective of the hour they belong to.  (ii) The sample-size KS: D = max |F_model - F_obs| of the weighted
distributions of the individual start times (minutes, day from 4:00) or durations, P with Ne from the Kish effective sizes
(survey: the half; model: one replication).
Outputs: data/abit_roorda_tables.csv (Table 1/2 rows), data/abit_roorda_ks.csv, data/abit_roorda_extra.csv (area, person
type, chains), data/abit_roorda_curves.parquet (figure data), 3_abit/roorda_tables.md, figures 3_abit/figures/fig_s3r_*.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, os, sys, time
import numpy as np
import pandas as pd
from scipy.special import kolmogorov
sys.path.insert(0, f"{MILES_HOME}/activity/lib"); sys.path.insert(0, f"{MILES_HOME}/activity/survey")
from rts_common import V, ROOT, RTS, ACT_PURPOSE, MI_KM, DIST_CAP_KM, ks_stat, kish_n, load_split
from activity_metrics import dist_matrix, zone_county, persons_2016
from survey_population import tract_zone, geoid, OUTD, RUNROOT

A3 = f"{V}/3_abit"; FIG = f"{A3}/figures"
TYPES = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME"]
TLAB = {"WORK": "Work", "SCHOOL": "School", "SHOPPING": "Shopping", "OTHER": "Other", "HOME": "Return home", "ALL": "All activities",
        "RECREATION": "of which recreation", "ACCOMPANY": "of which accompany", "OTHER_OTHER": "of which other errands"}
SUBS = ["RECREATION", "ACCOMPANY", "OTHER_OTHER"]
HOUR_ORDER = list(range(4, 24)) + list(range(0, 4))
SETTINGS = {"verification": ("survey", "estimation", [f"svy_est_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation": ("survey", "validation", [f"svy_val_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "chain": ("synthetic", "validation", [f"val_s{s:02d}" for s in range(1, 11)], f"{A3}/run"),
            # estimated destination MNL (2026-10-22, 3_abit/destination_choice; skims base car + 2024 door-to-door transit)
            "verification_mnl": ("survey", "estimation", [f"svy_est_mnl_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_mnl": ("survey", "validation", [f"svy_val_mnl_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "chain_mnl": ("synthetic", "validation", [f"val_mnl_s{s:02d}" for s in range(1, 11)], f"{A3}/run"),
            # TASHA-style generation and scheduling (MarylandTashaGenerator, 2026-10-22): behavioural set coef_tasha (no calibration)
            # and its calibrated variant coef_tasha_cal (estimation half only); skims base car + 2024 door-to-door transit
            "verification_tasha": ("survey", "estimation", [f"svy_est_tasha_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_tasha": ("survey", "validation", [f"svy_val_tasha_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "chain_tasha": ("synthetic", "validation", [f"val_tasha_s{s:02d}" for s in range(1, 11)], f"{A3}/run"),
            "verification_tcal": ("survey", "estimation", [f"svy_est_tcal_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_tcal": ("survey", "validation", [f"svy_val_tcal_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "chain_tcal": ("synthetic", "validation", [f"val_tcal_s{s:02d}" for s in range(1, 11)], f"{A3}/run"),
            # model of record (2026-10-29: destination models on the survey traffic zones, coef_tasha; runs *_rec1029_*; the runs
            # *_behav_* of 2026-10-26 used the tract-based destination models, coef_tasha_tract)
            # model of record (2026-10-23, ROORDA_VALIDATION.md section 10): TASHA-style generation with the estimated destination MNL,
            # estimated anchored locations and return-home logit; behavioural (coef_tasha) and calibrated (coef_tasha_cal)
            "verification_behav": ("survey", "estimation", [f"svy_est_rec1029_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_behav": ("survey", "validation", [f"svy_val_rec1029_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "chain_behav": ("synthetic", "validation", [f"val_rec1029_s{s:02d}" for s in range(1, 11)], f"{A3}/run"),
            # 2026-11-02 re-estimation (frequency by mandatory band, tour mode choice with household-structure terms, joint-stop and
            # joint-mode application fixes; coef_tasha; runs *_reest_*); the *_behav settings above are the runs before it
            "verification_reest": ("survey", "estimation", [f"svy_est_reest_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_reest": ("survey", "validation", [f"svy_val_reest_s{s:02d}" for s in range(1, 11)], RUNROOT),
            # 2026-11-03: work tour mode choice re-estimated with choice-based sample weights (WESML); coef_tasha; runs *_rail_*
            "verification_rail": ("survey", "estimation", [f"svy_est_rail_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_rail": ("survey", "validation", [f"svy_val_rail_s{s:02d}" for s in range(1, 11)], RUNROOT),
            # 2026-11-03: work-based subtours, return home re-estimated, joint common draws, accompany by licence; runs *_sched_*
            "verification_sched": ("survey", "estimation", [f"svy_est_sched_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_sched": ("survey", "validation", [f"svy_val_sched_s{s:02d}" for s in range(1, 11)], RUNROOT),
            # 2026-11-03 (evening): mode of each leg of a transit tour (estimate_transit_legs.py); coef_tasha; runs *_legmode_*
            "validation_legmode": ("survey", "validation", [f"svy_val_legmode_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "verification_cal": ("survey", "estimation", [f"svy_est_cal_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_cal": ("survey", "validation", [f"svy_val_cal_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "chain_cal": ("synthetic", "validation", [f"val_cal_s{s:02d}" for s in range(1, 11)], f"{A3}/run"),
            # 2026-11-10: re-specified models (coef_respec: TASHA car allocation, joint-tour representative with the group-level mode
            # model, joint frequency / members / start by work or school that day, licence-split frequencies); run_survey_households.py
            "verification_respec": ("survey", "estimation", [f"svy_est_respec_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "validation_respec": ("survey", "validation", [f"svy_val_respec_s{s:02d}" for s in range(1, 11)], RUNROOT),
            "chain_respec": ("synthetic", "validation", [f"val_respec_s{s:02d}" for s in range(1, 11)], f"{A3}/run")}
MAIN = ["verification", "validation", "chain", "verification_mnl", "validation_mnl", "chain_mnl", "verification_tasha", "validation_tasha", "chain_tasha",
        "verification_tcal", "validation_tcal", "chain_tcal", "verification_behav", "validation_behav", "chain_behav", "verification_reest", "validation_reest", "verification_rail", "validation_rail", "verification_sched", "validation_sched", "validation_legmode", "verification_cal", "validation_cal",
        "chain_cal"]; ALLSET = MAIN
AREA = {24510: "Baltimore City", 11001: "Washington DC"}
INNER = {24005, 24003, 24027, 24031, 24033, 51013, 51510, 51919}
AREAS = ["Baltimore City", "Washington DC", "inner suburbs", "outer counties"]
PTYPES = ["worker", "student 5-17", "student 18+", "non-worker", "retiree"]


def area_of(c):
    c = pd.Series(c).astype(int)
    return np.where(c.isin(list(AREA)), c.map(AREA), np.where(c.isin(list(INNER)), "inner suburbs", "outer counties"))


def ptype_of(occ, age):
    occ = np.asarray(occ); age = np.asarray(age)
    return np.select([occ == 1, (occ == 3) & (age < 18), occ == 3, occ == 4], ["worker", "student 5-17", "student 18+", "retiree"], "non-worker")


def atype(p):
    """DAYMAP purpose (or survey ACT_PURPOSE) -> (Roorda type, sub-type of 'other')."""
    p = pd.Series(p).astype(str)
    t = p.map({"WORK": "WORK", "EDUCATION": "SCHOOL", "SHOPPING": "SHOPPING", "HOME": "HOME"}).fillna("OTHER")
    s = np.where(t.eq("OTHER"), np.where(p.isin(["RECREATION", "ACCOMPANY"]), p, "OTHER_OTHER"), "")
    return t.values, s


def ks_values(a, b):
    """Roorda's KS: two-sample KS between the sets of values a and b; asymptotic P (Numerical Recipes kstwo)."""
    a = np.sort(np.asarray(a, float)); b = np.sort(np.asarray(b, float)); n, m = len(a), len(b)
    if n == 0 or m == 0: return np.nan, np.nan, 0
    x = np.concatenate([a, b]); d = np.max(np.abs(np.searchsorted(a, x, "right") / n - np.searchsorted(b, x, "right") / m))
    ne = n * m / (n + m); return float(d), float(kolmogorov((np.sqrt(ne) + 0.12 + 0.11 / np.sqrt(ne)) * d)), n


def ks_sample(xo, wo, xm, wm, n_model):
    """Sample-size KS between the weighted observed and model samples; Ne from the Kish sizes (model: one replication)."""
    d = ks_stat(xo, wo, xm, wm); no = kish_n(wo); ne = no * n_model / (no + n_model)
    return float(d), float(kolmogorov((np.sqrt(ne) + 0.12 + 0.11 / np.sqrt(ne)) * d)), no, n_model


# ------------------------------------------------------------------------------------------------ populations
def survey_pop(half):
    pm = pd.read_csv(f"{OUTD}/{half}/persons_map.csv"); zc = zone_county()
    pm["zc"] = pm.home_zone.map(zc).astype(int); pm["area"] = area_of(pm.zc); pm["ptype"] = ptype_of(pm.occ, pm.age)
    return pm


def synthetic_pop(run_root, run, zcs):
    """Persons of the 5 % sample (identical in every seed) whose home zone lies in a zone county of the survey households."""
    f = f"{A3}/run_survey/chain_population.parquet"
    if os.path.exists(f): return pd.read_parquet(f)
    a = pd.read_csv(f"{run_root}/{run}/output/activities_{run}.csv", usecols=["household_id", "purpose", "zone"], engine="pyarrow")
    home = a[a.purpose == "HOME"].drop_duplicates("household_id").set_index("household_id").zone; del a
    pp = persons_2016(); pp = pp[pp.hhID.isin(home.index)].copy()
    pp["home_zone"] = pp.hhID.map(home).astype(int); pp["zc"] = pp.home_zone.map(zone_county()).astype(int); pp = pp[pp.zc.isin(zcs)]
    pp = pp.rename(columns={"occupation": "occ"}); pp["w"] = 1.0; pp["area"] = area_of(pp.zc); pp["ptype"] = ptype_of(pp.occ, pp.age)
    pp = pp[["id", "hhID", "age", "occ", "home_zone", "zc", "w", "area", "ptype"]]; pp.to_parquet(f, index=False); return pp


# ------------------------------------------------------------------------------------------------ activities
def survey_activities(pm):
    """Observed activities (one per trip) of the households in the population map."""
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", low_memory=False,
                    usecols=["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "o_tract_fips", "d_tract_fips", "distance", "dep_min", "arr_min", "wttrdfin", "age"])
    t = t[t.household_id.isin(pm.household_id.unique())].copy()
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", usecols=["tripid", "o_state_county_fips", "d_state_county_fips"], low_memory=False).drop_duplicates("tripid").set_index("tripid")
    tz = tract_zone().set_index("geoid").zone
    for e in ["o", "d"]:
        g = geoid(t.tripid.map(r[f"{e}_state_county_fips"]), t[f"{e}_tract_fips"]); t[f"{e}_zone"] = g.map(tz).fillna(0).astype(int)
        t[f"{e}_known"] = g.ne("") & g.isin(tz.index)
    t["external"] = (t.o_known & (t.o_zone < 0)) | (t.d_known & (t.d_zone < 0))
    t = t.sort_values(["person_id", "tripno"], kind="stable")
    t["type"], t["sub"] = atype(t.d_activity.map(ACT_PURPOSE).fillna("OTHER"))
    o_home = t.o_activity.map(ACT_PURPOSE).eq("HOME").values
    t["start_min"] = t.arr_min.astype(float) % 1440
    nxt = t.groupby("person_id").dep_min.shift(-1); dur = nxt - t.arr_min; t["dur"] = np.where(dur < 0, dur + 1440, dur)
    t["km"] = np.where(t.distance >= 0, np.minimum(t.distance * MI_KM, DIST_CAP_KM), np.nan)
    dm = dist_matrix(); ok = (t.o_zone > 0) & (t.d_zone > 0)
    t["km_skim"] = np.nan; t.loc[ok, "km_skim"] = np.minimum(dm[t.o_zone[ok].values, t.d_zone[ok].values], DIST_CAP_KM)
    t["w"] = t.wttrdfin.astype(float); t["pid"] = t.person_id
    t["chain"] = _chain_ids(t.person_id.values, o_home)
    return t[["pid", "household_id", "age", "type", "sub", "start_min", "dur", "km", "km_skim", "w", "external", "chain"]].assign(o_home=o_home)


def _chain_ids(pid, o_home):
    """Chain index per trip: a new chain starts at every trip that leaves home (per person)."""
    new = o_home | np.r_[True, pid[1:] != pid[:-1]]
    return np.cumsum(new)


def model_activities(run_root, run, pop):
    f = f"{run_root}/{run}/roorda_monday.parquet"; lf = f"{run_root}/{run}/output/legs_{run}.csv"
    if os.path.exists(f) and os.path.exists(lf) and os.path.getmtime(f) < os.path.getmtime(lf): os.remove(f)   # stale cache of an earlier run
    if os.path.exists(f):
        a = pd.read_parquet(f)
    else:
        legs = pd.read_csv(f"{run_root}/{run}/output/legs_{run}.csv", usecols=["person_id", "previous_purpose", "start_time_min", "start_zone", "next_purpose", "end_time", "end_zone"],
                           engine="pyarrow")
        legs = legs[(legs.start_time_min >= 0) & (legs.start_time_min < 1440)]   # Monday, the representative weekday (representative_day.REP_DAY)
        legs = legs[legs.person_id.isin(pop.id.values)].sort_values(["person_id", "start_time_min"], kind="stable")
        dm = dist_matrix()
        a = pd.DataFrame({"pid": legs.person_id.values.astype(np.int64), "o_home": (legs.previous_purpose.astype(str) == "HOME").values,
                          "next": legs.next_purpose.astype(str).values, "start_min": legs.end_time.values.astype(float),
                          "dep": legs.start_time_min.values.astype(float),
                          "km": np.minimum(dm[legs.start_zone.values, legs.end_zone.values], DIST_CAP_KM)})
        a.to_parquet(f, index=False)
    a["type"], a["sub"] = atype(a.next)
    nxt = a.groupby("pid").dep.shift(-1); a["dur"] = nxt - a.start_min
    a["start_min"] = a.start_min % 1440
    a["chain"] = _chain_ids(a.pid.values, a.o_home.values)
    p = pop.set_index("id"); a["w"] = a.pid.map(p.w).values; a["age"] = a.pid.map(p.age).values; a["external"] = False
    return a


# ------------------------------------------------------------------------------------------------ measures
def keep(df, variant):
    m = (df.age >= (11 if variant == "roorda" else 5)) & ~df.external
    if variant == "roorda": m &= df["sub"] != "ACCOMPANY"
    return df[m]


def scale(pop, variant):
    p = pop[pop.age >= (11 if variant == "roorda" else 5)]
    return len(p), p.w.sum()


def hour_shift(m):
    """Minutes of the day on the 4:00-3:59 axis (0 = 4:00)."""
    return (np.asarray(m, float) - 240) % 1440


def hourly(df, val=None, min_n=0):
    h = ((df.start_min // 60) % 24).astype(int)
    if val is None:
        s = df.w.groupby(h).sum().reindex(range(24), fill_value=0.0); return s / s.sum()
    x = df[val]; m = x.notna(); g = (x[m] * df.w[m]).groupby(h[m]).sum() / df.w[m].groupby(h[m]).sum(); n = h[m].value_counts()
    return g.reindex(range(24)).where(n.reindex(range(24), fill_value=0) >= min_n)


def chain_dist(df):
    """Share of complete home-to-home chains by number of trips (1..8+), weighted; chains of persons 5+ without an external trip."""
    g = df.groupby("chain").agg(n=("type", "size"), first_home=("o_home", "first"), last=("type", "last"), w=("w", "first"), ext=("external", "any"), age=("age", "first"))
    g = g[g.first_home & (g["last"] == "HOME") & ~g.ext & (g.age >= 5)]
    k = g.n.clip(upper=8); s = g.w.groupby(k).sum().reindex(range(1, 9), fill_value=0.0)
    return s / s.sum(), float((g.n * g.w).sum() / g.w.sum())


def run_setting(name, variant_list=("base", "roorda")):
    kind, half, runs, root = SETTINGS[name]
    vpop = survey_pop(half)
    pop = vpop if kind == "survey" else synthetic_pop(root, runs[0], sorted(vpop.zc.unique()))
    obs = survey_activities(vpop)
    rows, ks_rows, extra, curves = [], [], [], []
    mod_all = []
    for i, r in enumerate(runs):
        t0 = time.time(); a = model_activities(root, r, pop); a["rep"] = i + 1; mod_all.append(a)
        print(f"  {name} {r}: {len(a)} model activities ({time.time() - t0:.0f} s)", flush=True)
    mods = pd.concat(mod_all, ignore_index=True); del mod_all
    for variant in variant_list:
        N, Wm = scale(pop, variant); Nv, Wv = scale(vpop, variant)
        Fm = N / Wm; Fo = N / Wv if kind == "synthetic" else Fm
        o = keep(obs, variant); m = keep(mods, variant)
        def block(key, om, mm):
            tot = mm.groupby("rep").w.sum().reindex(range(1, 11), fill_value=0) * Fm
            mk = mm[mm.km.notna()]; dist = (mk.km * mk.w).groupby(mk.rep).sum() / mk.w.groupby(mk.rep).sum() if len(mk) else pd.Series([np.nan] * 2)
            ok = om.km.notna(); oks = om.km_skim.notna()
            if len(om) == 0 and len(mm) == 0: return
            ob = om.w.sum() * Fo; od = np.average(om.km[ok], weights=om.w[ok]) if ok.any() else np.nan
            ods = np.average(om.km_skim[oks], weights=om.w[oks]) if oks.any() else np.nan
            # observed_km = the zone-skim distance (like for like with the model's skim distances); the reported distance is secondary
            rows.append(dict(setting=name, variant=variant, type=key, model_total=tot.mean(), model_total_sd=tot.std(ddof=1), observed_total=ob,
                             diff=tot.mean() - ob, diff_pct=100 * (tot.mean() - ob) / ob, model_km=dist.mean(), model_km_sd=dist.std(ddof=1), observed_km=ods,
                             diff_km=dist.mean() - ods, diff_km_pct=100 * (dist.mean() - ods) / ods, observed_km_zone_skim=ods, observed_km_reported=od,
                             diff_km_reported=dist.mean() - od, diff_km_pct_reported=100 * (dist.mean() - od) / od, persons=N,
                             n_obs_activities=len(om), n_obs_activities_skim=int(oks.sum()), n_model_activities_per_rep=len(mm) / 10))
        for ty in TYPES: block(ty, o[o.type == ty], m[m.type == ty])
        for sb in SUBS: block(sb, o[o["sub"] == sb], m[m["sub"] == sb])
        block("ALL", o, m)
        if variant != "base": continue
        # Figs. 2/6: start-time distribution; Figs. 3/7: duration by start hour; Fig. 5/8: distance by start hour
        for ty in TYPES + ["ALL"]:
            om = o if ty == "ALL" else o[o.type == ty]; mm = m if ty == "ALL" else m[m.type == ty]
            ho = hourly(om); hm = pd.concat([hourly(g) for _, g in mm.groupby("rep")], axis=1)
            hm_mean = hm.mean(axis=1); nonzero = (ho > 0) | (hm_mean > 0)
            D, P, n = ks_values(100 * hm_mean[nonzero], 100 * ho[nonzero])
            mrep = mm[mm.rep == 1]
            Ds, Ps, no, nm = ks_sample(hour_shift(om.start_min), om.w, hour_shift(mm.start_min), mm.w, kish_n(mrep.w))
            within = int((np.abs(hm_mean - ho) <= 0.02).sum()); maxdev = float(100 * np.abs(hm_mean - ho).max())
            ks_rows.append(dict(setting=name, figure="start_time", type=ty, D_hourly=D, P_hourly=P, n_hours=n, D_sample=Ds, P_sample=Ps, n_obs_eff=no, n_model_eff=nm,
                                hours_within_2pp=within, max_dev_pp=maxdev))
            for h in range(24): curves.append(dict(setting=name, figure="start_time", type=ty, hour=h, model=100 * hm_mean[h], model_sd=100 * hm.loc[h].std(ddof=1), observed=100 * ho[h]))
            if ty in ("WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME", "ALL"):
                od_ = om[om.dur.between(1, 1439)]; md_ = mm[mm.dur.between(1, 1439)]
                do = hourly(od_, "dur", 10); dmn = hourly(md_, "dur", 10 * 10)
                both = do.notna() & dmn.notna()
                D2, P2, n2 = ks_values(dmn[both], do[both])
                Ds2, Ps2, no2, nm2 = ks_sample(od_.dur, od_.w, md_.dur, md_.w, kish_n(md_[md_.rep == 1].w))
                q = [np.nan, np.nan]
                if len(om):
                    x = hour_shift(om.start_min); oo = np.argsort(x); cw = np.cumsum(om.w.values[oo]) / om.w.sum()
                    q = [float(x[oo][np.searchsorted(cw, 0.05)]), float(x[oo][min(len(oo) - 1, np.searchsorted(cw, 0.95))])]
                band = [(int(q[0] // 60) + 4) % 24, (int(q[1] // 60) + 4) % 24]
                in_band = [h for h in HOUR_ORDER[int(q[0] // 60): int(q[1] // 60) + 1]]
                fails = [h for h in in_band if both[h] and not (abs(dmn[h] - do[h]) <= 10 or abs(dmn[h] - do[h]) <= 0.1 * do[h])]
                ks_rows.append(dict(setting=name, figure="duration", type=ty, D_hourly=D2, P_hourly=P2, n_hours=n2, D_sample=Ds2, P_sample=Ps2, n_obs_eff=no2, n_model_eff=nm2,
                                    band_from_h=band[0], band_to_h=band[1], band_hours=len(in_band), band_hours_compared=int(sum(both[h] for h in in_band)),
                                    band_hours_outside_10min_10pct=len(fails), band_fail_hours=" ".join(f"{h}" for h in fails),
                                    mean_dur_model=float(np.average(md_.dur, weights=md_.w)), mean_dur_obs=float(np.average(od_.dur, weights=od_.w))))
                for h in range(24): curves.append(dict(setting=name, figure="duration", type=ty, hour=h, model=dmn[h], observed=do[h], band_lo=q[0], band_hi=q[1]))
            if ty == "ALL":
                ko = hourly(om[om.km_skim.notna()], "km_skim", 30); km_ = hourly(mm[mm.km.notna()], "km", 300); kr = hourly(om[om.km.notna()], "km", 30)
                D3, P3, n3 = ks_values(km_[ko.notna() & km_.notna()], ko[ko.notna() & km_.notna()])
                D3r, P3r, n3r = ks_values(km_[kr.notna() & km_.notna()], kr[kr.notna() & km_.notna()])
                ks_rows.append(dict(setting=name, figure="distance_by_hour", type=ty, D_hourly=D3, P_hourly=P3, n_hours=n3, D_hourly_reported=D3r, P_hourly_reported=P3r))
                for h in range(24): curves.append(dict(setting=name, figure="distance_by_hour", type=ty, hour=h, model=km_[h], observed=ko[h], observed_reported=kr[h]))
        # Fig. 4: trips per chain (complete home-based chains)
        so, mo = chain_dist(obs); per = [chain_dist(g) for _, g in mods.groupby("rep")]
        sm = pd.concat([p[0] for p in per], axis=1)
        for k in range(1, 9): curves.append(dict(setting=name, figure="chains", type="ALL", hour=k, model=100 * sm.loc[k].mean(), model_sd=100 * sm.loc[k].std(ddof=1), observed=100 * so[k]))
        extra.append(dict(setting=name, table="chains", group="all", metric="trips_per_chain", model=np.mean([p[1] for p in per]), model_sd=np.std([p[1] for p in per], ddof=1), observed=mo))
        D4, P4, n4 = ks_values(100 * sm.mean(axis=1), 100 * so)
        ks_rows.append(dict(setting=name, figure="chains", type="ALL", D_hourly=D4, P_hourly=P4, n_hours=n4))
        # additional tests: activities per person and distance by area of residence and by person type
        pmap = pop.set_index("id"); vmap = vpop.set_index("person_id")
        m2 = m.assign(area=m.pid.map(pmap.area).values, ptype=m.pid.map(pmap.ptype).values)
        o2 = o.assign(area=o.pid.map(vmap.area).values, ptype=o.pid.map(vmap.ptype).values)
        for col, groups in [("area", AREAS), ("ptype", PTYPES)]:
            for gname in groups:
                pg = pop[(pop[col] == gname) & (pop.age >= 5)]; vg = vpop[(vpop[col] == gname) & (vpop.age >= 5)]
                if len(pg) == 0 or len(vg) == 0: continue
                mg = m2[m2[col] == gname]; og = o2[o2[col] == gname]
                for ty in ["ALL"] + TYPES:
                    mt = mg if ty == "ALL" else mg[mg.type == ty]; ot = og if ty == "ALL" else og[og.type == ty]
                    rate = mt.groupby("rep").w.sum().reindex(range(1, 11), fill_value=0) / pg.w.sum()
                    extra.append(dict(setting=name, table=col, group=gname, metric=f"activities_per_person_{ty}", model=rate.mean(), model_sd=rate.std(ddof=1),
                                      observed=ot.w.sum() / vg.w.sum(), persons_model=len(pg), persons_obs=len(vg)))
                    if ty == "ALL":
                        dk = mt[mt.km.notna()].groupby("rep").apply(lambda x: np.average(x.km, weights=x.w), include_groups=False); ok = ot.km.notna(); oks = ot.km_skim.notna()
                        extra.append(dict(setting=name, table=col, group=gname, metric="avg_km", model=dk.mean(), model_sd=dk.std(ddof=1),
                                          observed=np.average(ot.km_skim[oks], weights=ot.w[oks]), observed_reported=np.average(ot.km[ok], weights=ot.w[ok]),
                                          persons_model=len(pg), persons_obs=len(vg)))
    return pd.DataFrame(rows), pd.DataFrame(ks_rows), pd.DataFrame(extra), pd.DataFrame(curves)


# ------------------------------------------------------------------------------------------------ tables
def md_tables(T, K, E):
    L = []; f0 = lambda v: f"{v:,.0f}"; f1 = lambda v: f"{v:,.1f}"; f2 = lambda v: f"{v:.2f}"
    names = {"verification": "Table R1. Activity frequency and distance, ABIT on the observed population of the estimation half (verification)",
             "validation": "Table R2. Activity frequency and distance, ABIT on the observed population of the validation half (validation)",
             "chain": "Table R3. Activity frequency and distance, ABIT on the synthetic population of the chain against the validation half (chain test)",
             "verification_mnl": "Table R1-MNL. Verification (estimation half), estimated destination MNL (after)",
             "validation_mnl": "Table R2-MNL. Validation half, estimated destination MNL (after)",
             "chain_mnl": "Table R3-MNL. Chain test, estimated destination MNL (after)",
             "verification_tasha": "Table R1-T. Verification (estimation half), TASHA-style generation, behavioural (no calibration)",
             "validation_tasha": "Table R2-T. Validation half, TASHA-style generation, behavioural (no calibration)",
             "chain_tasha": "Table R3-T. Chain test, TASHA-style generation, behavioural (no calibration)",
             "verification_tcal": "Table R1-TC. Verification (estimation half), TASHA-style generation, calibrated on the estimation half",
             "validation_tcal": "Table R2-TC. Validation half, TASHA-style generation, calibrated on the estimation half",
             "chain_tcal": "Table R3-TC. Chain test, TASHA-style generation, calibrated on the estimation half",
             "verification_reest": "Table R1-R. Verification (estimation half), after the re-estimation of 2 November 2026",
             "validation_reest": "Table R2-R. Validation (validation half), after the re-estimation of 2 November 2026",
             "verification_rail": "Table R1-W. Verification (estimation half), work tour mode choice re-estimated with choice-based weights",
             "validation_rail": "Table R2-W. Validation (validation half), work tour mode choice re-estimated with choice-based weights",
             "verification_sched": "Table R1-S. Verification (estimation half), work-based subtours and re-estimated tour formation",
             "validation_sched": "Table R2-S. Validation (validation half), work-based subtours and re-estimated tour formation",
             "validation_legmode": "Table R2-L. Validation (validation half), mode of each leg of a transit tour",
             "verification_respec": "Table R1-X. Verification (estimation half), re-specified models",
             "validation_respec": "Table R2-X. Validation (validation half), re-specified models",
             "chain_respec": "Table R3-X. Chain test, re-specified models",
             "verification_behav": "Table R1-F. Verification (estimation half), model of record, behavioural (no calibration)",
             "validation_behav": "Table R2-F. Validation half, model of record, behavioural (no calibration)",
             "chain_behav": "Table R3-F. Chain test, model of record, behavioural (no calibration)",
             "verification_cal": "Table R1-FC. Verification (estimation half), model of record, calibrated on the estimation half",
             "validation_cal": "Table R2-FC. Validation half, model of record, calibrated on the estimation half",
             "chain_cal": "Table R3-FC. Chain test, model of record, calibrated on the estimation half"}
    for s in ALLSET:
        t = T[(T.setting == s) & (T.variant == "base")]
        if len(t) == 0: continue
        L.append(f"### {names[s]}\n")
        L.append("| Activity type | Model average total activities | Model s.d. total activities | Observed total activities | Model ± activities (#) | Model ± activities (%) | Model average distance (km) | Model s.d. distance (km) | Observed average distance (km, zone skim) | Model ± distance (km) | Model ± distance (%) | Observed reported distance (km)ᵃ | Model ± reported (%)ᵃ |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for ty in TYPES[:4] + SUBS + ["HOME", "ALL"]:
            r = t[t.type == ty].iloc[0]; lab = "Total" if ty == "ALL" else TLAB[ty]
            L.append(f"| {lab} | {f0(r.model_total)} | {f0(r.model_total_sd)} | {f0(r.observed_total)} | {r['diff']:+,.0f} | {r.diff_pct:+.1f} | {f2(r.model_km)} | {f2(r.model_km_sd)} | {f2(r.observed_km)} | {r.diff_km:+.2f} | {r.diff_km_pct:+.1f} | {f2(r.observed_km_reported)} | {r.diff_km_pct_reported:+.1f} |")
        n = int(t.persons.iloc[0])
        L.append(f"\nPersons 5+ simulated: {n:,}; observed totals are the weighted survey activities scaled to this population. Model: mean and standard deviation of 10 replications. "
                 "Distance: car-distance skim between the zones of the trip ends on both sides (survey: the zones of the origin and destination tract points). "
                 "ᵃ The survey's reported address-to-address driving distance, a different measure from the model's zone-to-zone skim distance; shown for reference.\n")
    L.append("### Table R4. Sensitivity: exclusion rule and distance measure (totals over all activity types)\n")
    L.append("| Setting | Exclusion | Persons | Model total | Observed total | ± % | Model km | Observed km (zone skim) | ± % | Observed km (reported) | ± % vs reported |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in ALLSET:
        for v in ["base", "roorda"]:
            r = T[(T.setting == s) & (T.variant == v) & (T.type == "ALL")]
            if len(r) == 0: continue
            r = r.iloc[0]
            L.append(f"| {s} | {'persons 5+, internal trips' if v == 'base' else 'persons 11+, internal, no accompany'} | {int(r.persons):,} | {f0(r.model_total)} | {f0(r.observed_total)} | {r.diff_pct:+.1f} | {f2(r.model_km)} | {f2(r.observed_km)} | {r.diff_km_pct:+.1f} | {f2(r.observed_km_reported)} | {r.diff_km_pct_reported:+.1f} |")
    L.append("\n### Table R5. Kolmogorov-Smirnov tests of the start-time distributions (Figs. R2) and of the durations (Figs. R3)\n")
    L.append("| Setting | Figure | Activity type | Roorda D (hourly values) | P | hours | Sample D | P | n obs (Kish) | n model (Kish, one replication) | hours within 2 pp of 24 | max hourly deviation (pp) |")
    L.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in K[K.figure.isin(["start_time", "duration"])].iterrows():
        ps = lambda p: "< 0.001" if p < 0.001 else f"{p:.3f}"
        L.append(f"| {r.setting} | {r.figure.replace('_', ' ')} | {TLAB[r.type]} | {r.D_hourly:.3f} | {ps(r.P_hourly)} | {int(r.n_hours)} | {r.D_sample:.3f} | {ps(r.P_sample)} | {r.n_obs_eff:,.0f} | {r.n_model_eff:,.0f} | "
                 f"{'' if pd.isna(r.get('hours_within_2pp')) else int(r.hours_within_2pp)} | {'' if pd.isna(r.get('max_dev_pp')) else f'{r.max_dev_pp:.1f}'} |")
    L.append("\n### Table R6. Durations inside the band of the 90 % of activity starts (Figs. R3): hours where the model is not within 10 min or 10 % of the observed mean\n")
    L.append("| Setting | Activity type | 90 % band (start hour) | hours in band with both curves | hours outside 10 min / 10 % | those hours | mean duration model (min) | observed (min) |")
    L.append("|---|---|---|---:|---:|---|---:|---:|")
    for _, r in K[K.figure == "duration"].iterrows():
        L.append(f"| {r.setting} | {TLAB[r.type]} | {int(r.band_from_h)}:00–{int(r.band_to_h)}:59 | {int(r.band_hours_compared)} | {int(r.band_hours_outside_10min_10pct)} | {r.band_fail_hours if isinstance(r.band_fail_hours, str) else ''} | {r.mean_dur_model:.0f} | {r.mean_dur_obs:.0f} |")
    L.append("\n### Table R7. Trips per home-based chain and distance by start hour (Figs. R4, R5)\n")
    L.append("| Setting | trips per chain model | s.d. | observed | KS (chain shares) D | P | KS (hourly mean distance) D | P |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in ALLSET:
        e = E[(E.setting == s) & (E.table == "chains")]
        if len(e) == 0: continue
        e = e.iloc[0]; kc = K[(K.setting == s) & (K.figure == "chains")].iloc[0]; kd = K[(K.setting == s) & (K.figure == "distance_by_hour")].iloc[0]
        L.append(f"| {s} | {e.model:.3f} | {e.model_sd:.4f} | {e.observed:.3f} | {kc.D_hourly:.3f} | {kc.P_hourly:.3f} | {kd.D_hourly:.3f} | {kd.P_hourly:.3f} |")
    for col, title in [("area", "area of residence"), ("ptype", "person type")]:
        L.append(f"\n### Table R8{'a' if col == 'area' else 'b'}. Activities per person (persons 5+, all types) and average distance by {title}\n")
        L.append("| Setting | Group | persons model | activities/person model | s.d. | observed | ± % | work | school | shopping | other | return home | avg km model | observed (zone skim) | ± % |")
        L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for s in ALLSET:
            for g in (AREAS if col == "area" else PTYPES):
                e = E[(E.setting == s) & (E.table == col) & (E.group == g)].set_index("metric")
                if len(e) == 0: continue
                a = e.loc["activities_per_person_ALL"]; k = e.loc["avg_km"]
                per = " | ".join(f"{100 * (e.loc[f'activities_per_person_{ty}'].model / e.loc[f'activities_per_person_{ty}'].observed - 1):+.0f} %" for ty in TYPES)
                L.append(f"| {s} | {g} | {int(a.persons_model):,} | {a.model:.3f} | {a.model_sd:.3f} | {a.observed:.3f} | {100 * (a.model / a.observed - 1):+.1f} | {per} | {k.model:.2f} | {k.observed:.2f} | {100 * (k.model / k.observed - 1):+.1f} |")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------------ figures
def figures(C, K):
    """Figures R2-R5 per setting, paperstyle strict rules (no statistics inside plots: the KS values are in Tables R5-R7;
    fonts >= 7.5 pt; height <= 0.85 textheight).  Revised 2026-10-22."""
    sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps; import matplotlib.pyplot as plt
    ps.use(); out = []
    hl = [f"{h}" for h in HOUR_ORDER]; x = np.arange(24); tk = x[::4]
    for s in [x_ for x_ in MAIN if x_ in set(C.setting)]:
        c = C[C.setting == s]
        # Fig. R2: start-time distributions
        ps.use(); fig, axes = plt.subplots(3, 2, figsize=(ps.WIDTH, 6.3), sharex=True)
        for ax, ty in zip(axes.flat, TYPES + ["ALL"]):
            d = c[(c.figure == "start_time") & (c.type == ty)].set_index("hour").loc[HOUR_ORDER]; w = 0.4
            ax.bar(x - w / 2, d.model, w, color=ps.MODEL, label=ps.LEG["model"]); ax.bar(x + w / 2, d.observed, w, color=ps.OBSERVED, label=ps.LEG["observed"])
            ax.set_ylim(0, max(d.model.max(), d.observed.max()) * 1.12); ax.set_title(TLAB[ty], loc="right", fontsize=8, fontweight="normal", color=ps.INK2)
            ax.set_xticks(tk); ax.set_xticklabels([hl[i] for i in tk]); ax.set_ylabel("Share of activities (%)")
        for ax in axes[-1]: ax.set_xlabel("Activity start (hour of day)")
        h_, l_ = axes[0, 0].get_legend_handles_labels(); fig.legend(h_, l_, loc="outside lower center", ncol=2)
        out.append(ps.finish(fig, f"{FIG}/fig_s3r_start_{s}", list("abcdef")))
        # Fig. R3: durations by start time with the 90 % band
        ps.use(); fig, axes = plt.subplots(2, 2, figsize=(ps.WIDTH, 4.6), sharex=True)
        for ax, ty in zip(axes.flat, ["WORK", "SCHOOL", "SHOPPING", "OTHER"]):
            d = c[(c.figure == "duration") & (c.type == ty)].set_index("hour").loc[HOUR_ORDER]
            lo, hi = d.band_lo.iloc[0] / 60, d.band_hi.iloc[0] / 60
            ax.axvspan(lo, hi, color=ps.GRID, alpha=0.6, lw=0, label="90 % of observed starts")
            ax.plot(x + 0.5, d.model, color=ps.MODEL, label=ps.LEG["model"]); ax.plot(x + 0.5, d.observed, color=ps.OBSERVED, ls="--", label=ps.LEG["observed"])
            ax.set_ylim(0, np.nanmax([d.model.max(), d.observed.max()]) * 1.12); ax.set_title(TLAB[ty], loc="right", fontsize=8, fontweight="normal", color=ps.INK2)
            ax.set_xticks(tk); ax.set_xticklabels([hl[i] for i in tk]); ax.set_xlim(0, 24); ax.set_ylabel("Mean duration (min)")
        for ax in axes[-1]: ax.set_xlabel("Activity start (hour of day)")
        h_, l_ = axes[0, 0].get_legend_handles_labels(); fig.legend(h_, l_, loc="outside lower center", ncol=3)
        out.append(ps.finish(fig, f"{FIG}/fig_s3r_duration_{s}", list("abcd")))
        # Fig. R4: trips per chain
        ps.use(); fig, ax = plt.subplots(figsize=(ps.WIDTH, 2.6)); d = c[c.figure == "chains"].set_index("hour"); xx = np.arange(1, 9); w = 0.4
        ax.bar(xx - w / 2, d.model, w, color=ps.MODEL, label=ps.LEG["model"]); ax.bar(xx + w / 2, d.observed, w, color=ps.OBSERVED, label=ps.LEG["observed"])
        ax.set_xticks(xx); ax.set_xticklabels([str(i) for i in range(1, 8)] + ["8+"]); ax.set_xlabel("Trips per home-based chain"); ax.set_ylabel("Share of chains (%)")
        ax.set_ylim(0, max(d.model.max(), d.observed.max()) * 1.1); fig.legend(loc="outside lower center", ncol=2)
        out.append(ps.finish(fig, f"{FIG}/fig_s3r_chains_{s}"))
        # Fig. R5: average distance by start hour, all types
        ps.use(); fig, ax = plt.subplots(figsize=(ps.WIDTH, 2.6)); d = c[c.figure == "distance_by_hour"].set_index("hour").loc[HOUR_ORDER]; w = 0.4
        ax.bar(x - w / 2, d.model, w, color=ps.MODEL, label=ps.LEG["model"]); ax.bar(x + w / 2, d.observed, w, color=ps.OBSERVED, label=ps.LEG["observed"])
        ax.set_xticks(tk); ax.set_xticklabels([hl[i] for i in tk]); ax.set_xlabel("Activity start (hour of day)"); ax.set_ylabel("Average distance (km)")
        ax.set_ylim(0, np.nanmax([d.model.max(), d.observed.max()]) * 1.1); fig.legend(loc="outside lower center", ncol=2)
        out.append(ps.finish(fig, f"{FIG}/fig_s3r_distance_{s}"))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--settings", default=",".join(s for s in ALLSET if os.path.exists(f"{SETTINGS[s][3]}/{SETTINGS[s][2][-1]}")))
    ap.add_argument("--figures-only", action="store_true")
    a = ap.parse_args()
    fT, fK, fE, fC = f"{V}/data/abit_roorda_tables.csv", f"{V}/data/abit_roorda_ks.csv", f"{V}/data/abit_roorda_extra.csv", f"{V}/data/abit_roorda_curves.parquet"
    if not a.figures_only:
        res = [run_setting(s) for s in a.settings.split(",")]
        T, K, E, C = (pd.concat([r[i] for r in res], ignore_index=True) for i in range(4))
        if set(a.settings.split(",")) != set(SETTINGS) and os.path.exists(fT):   # keep the settings not recomputed
            old = [pd.read_csv(fT), pd.read_csv(fK), pd.read_csv(fE), pd.read_parquet(fC)]
            T, K, E, C = (pd.concat([o[~o.setting.isin(a.settings.split(","))], n], ignore_index=True) for o, n in zip(old, [T, K, E, C]))
        T.to_csv(fT, index=False); K.to_csv(fK, index=False); E.to_csv(fE, index=False); C.to_parquet(fC, index=False)
        open(f"{A3}/roorda_tables.md", "w").write(md_tables(T, K, E)); print(f"wrote {fT}, {fK}, {fE}, {fC}, {A3}/roorda_tables.md")
    K = pd.read_csv(fK); C = pd.read_parquet(fC)
    for f in figures(C, K): print("figure", f)


if __name__ == "__main__":
    main()
