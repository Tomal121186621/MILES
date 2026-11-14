#!/usr/bin/env python3
"""Stage 3: the survey metrics of rts_common / build_targets computed on one ABIT run, with the same definitions.

    python3 abit_metrics.py <run name> [--targets targets_estimation.csv] [--out metrics.csv]

Model side of every definition:
  person-day      the representative weekday of the chain (pipeline/abit_to_matsim_pop.py -> ABIT/validation/abit_day.pick_day):
                  MONDAY for every person (second pass of stage 3, 2026-10-22; the weekly model concentrates discretionary travel
                  on Monday, MarylandDayOfWeekDiscretionaryAssignment); a person without legs on Monday is a non-traveller.
                  The first pass took the earliest complete home-to-home weekday of each person (REP_DAY_RULE = "best"), which
                  counted every person with a tour in the week as a traveller (traveller share 0.91 against 0.86).
                  A traveller is a person with legs on that day; the all-persons basis is every person of the sampled households.
  population      persons of the sampled households whose home county is a survey county (TPB + BMC region); county groups as
                  in the targets file (counties with >= 150 survey households in the half, the rest 'other').
  segments        SILO occupation: 1 EMPLOYED worker, 3 STUDENT (band by age), 4 RETIREE, 2 UNEMPLOYED nonworker, 0 TODDLER excluded.
  tours           home-to-home chains of the day from the activities file; main activity = the MANDATORY / PRIMARY activity
                  (WORK, EDUCATION or the discretionary primary), stops = ON_MANDATORY_TOUR activities before (out) / after (in)
                  the main activity; SUBTOUR activities are work-based subtours (counted separately, their legs are trips).
  trips           legs of the day; purpose = the non-home end (SUBTOUR -> OTHER); distance = car-distance skim between the
                  zones (network km; intrazonal = 0.5 * sqrt(zone area)); mode = leg mode; departure = leg start.
  commute         HOME -> WORK legs (skim km); own-county work share = HOME -> WORK legs whose destination zone lies in the home county.
"""
import argparse, os, sys
import numpy as np
import pandas as pd
from rts_common import (V, ROOT, PURPOSES, MODES, SEGMENTS, SEG_GROUPS, STOP_SPEC, DIST_BINS, DIST_LABELS, HOURS, DIST_CAP_KM,
                        wmean, wquantile, wshares, whist, band_of)

A3 = f"{V}/3_abit"
ZONE_ATTR = f"{ROOT}/ABIT/input/maryland/zone_attributes.csv"
SKIM_DIST = f"{A3}/skims/distance_auto.csv.gz"
PP = f"{V}/2_silo/input/microData/pp_2016.csv"
OCC_SEG = {1: "worker", 3: "student", 4: "retiree", 2: "nonworker", 0: "toddler"}
_cache = {}


def zone_county():
    if "zc" not in _cache:
        z = pd.read_csv(ZONE_ATTR, usecols=["id", "countyfips"]); _cache["zc"] = z.set_index("id").countyfips
    return _cache["zc"]


def dist_matrix():
    """Dense km matrix indexed by zone id (max id + 1).  Intrazonal: 0.5 * sqrt(zone area) km (the skim diagonal is a flat
    1.0 km; the area rule gives 0.65 / 1.5 / 5.5 km at the 10th / 50th / 90th percentile of the zones; convention of 2026-10-22,
    applied to every trip-length comparison of this stage)."""
    if "dm" not in _cache:
        s = pd.read_csv(SKIM_DIST); n = int(max(s.FROM.max(), s.TO.max())) + 1
        m = np.full((n, n), np.nan, dtype=np.float32); m[s.FROM.values, s.TO.values] = s.VALUE.values / 1000.0
        z = pd.read_csv(ZONE_ATTR, usecols=["id", "area_km2"]); m[z.id.values, z.id.values] = 0.5 * np.sqrt(z.area_km2.values)
        _cache["dm"] = m
    return _cache["dm"]


def persons_2016():
    if "pp" not in _cache:
        _cache["pp"] = pd.read_csv(PP, usecols=["id", "hhID", "age", "occupation"], dtype={"id": np.int32, "hhID": np.int32, "age": np.int16, "occupation": np.int8})
    return _cache["pp"]


def survey_counties(tg):
    """Counties reported individually in the targets (county groups) and the set of all survey counties."""
    groups = sorted(c for c in tg.county.unique() if c not in ("all", "other"))
    allc = pd.read_csv(f"{V}/data/rts_split.csv").household_id
    if "survey_counties" not in _cache:
        r = pd.read_csv(f"{ROOT}/ABIT/input/rts/RTS_raw_flat_data.csv", usecols=["household_id", "home_state_county_fips"]).drop_duplicates("household_id")
        _cache["survey_counties"] = set(r.home_state_county_fips.astype(int))
    return [int(c) for c in groups], _cache["survey_counties"]


REP_DAY_RULE = "monday"   # "monday": the fixed representative weekday of the chain (abit_day.REP_DAY); "best": the first-pass rule


def representative_day(legs, rule=None):
    """pick_day of abit_day.py, vectorised.  rule "monday" (the chain's rule since the second pass, 2026-10-22): day 0 for
    every person, so a person without legs on Monday has no legs on the representative day; rule "best" (first pass): per
    person the earliest complete (HOME ... HOME) weekday with legs, weekdays first."""
    rule = rule or REP_DAY_RULE
    legs = legs.sort_values(["person_id", "start_time_min"], kind="stable")
    legs["day"] = (legs.start_time_min // 1440).astype(np.int16)
    if rule == "monday":
        return pd.Series(0, index=pd.Index(legs.person_id.unique(), name="person_id"), dtype=np.int16), legs
    g = legs.groupby(["person_id", "day"], sort=False)
    first = g.previous_purpose.first(); last = g.next_purpose.last()
    d = pd.DataFrame({"complete": (first == "HOME") & (last == "HOME")}).reset_index()
    d["weekday"] = d.day < 5
    d["score"] = d.weekday.astype(int) * 1000 + d.complete.astype(int) * 100 - d.day
    best = d.sort_values("score", ascending=False).drop_duplicates("person_id").set_index("person_id").day
    return best, legs


def run_metrics(name, tg, run_root=f"{A3}/run"):
    """Long table (section, purpose, segment, county, metric, value, n) of one run, definitions as in build_targets.py."""
    d = f"{run_root}/{name}"
    legs = pd.read_csv(f"{d}/output/legs_{name}.csv", usecols=["person_id", "previous_purpose", "start_time_min", "start_zone", "next_purpose", "end_time", "end_zone", "mode"],
                       dtype={"person_id": np.int32, "previous_purpose": "category", "start_time_min": np.int32, "start_zone": np.int16, "next_purpose": "category", "end_time": np.int32, "end_zone": np.int16, "mode": "category"})
    acts = pd.read_csv(f"{d}/output/activities_{name}.csv", usecols=["person_id", "household_id", "day", "start_time_min", "end_time_min", "purpose", "zone", "activity_type"],
                       dtype={"person_id": np.int32, "household_id": np.int32, "day": np.int8, "start_time_min": np.int32, "end_time_min": np.int32, "purpose": "category", "zone": np.int16, "activity_type": "category"})
    legs = legs[legs.start_time_min >= 0]
    zc = zone_county(); dm = dist_matrix()
    groups, allc = survey_counties(tg)
    # ---- population: sampled households (home zone from the HOME activities) in survey counties
    home = acts[acts.purpose == "HOME"].drop_duplicates("household_id").set_index("household_id").zone
    hh_cty = home.map(zc)
    pp = persons_2016(); pp = pp[pp.hhID.isin(home.index)].copy()
    pp["county"] = pp.hhID.map(hh_cty); pp = pp[pp.county.isin(allc)]
    pp["cgrp"] = np.where(pp.county.isin(groups), pp.county.astype(str), "other")
    pp["seg"] = pp.occupation.map(OCC_SEG)
    stu = pp.seg == "student"; pp.loc[stu, "seg"] = "student_" + band_of(pp.age[stu]).values
    pp = pp.set_index("id")
    hh_n = pp.hhID.nunique(); hh_grp = pp.drop_duplicates("hhID").set_index("hhID").cgrp
    # ---- representative day per person, legs and activities of that day
    best, legs = representative_day(legs)
    legs = legs[legs.person_id.isin(pp.index)]
    legs["rep"] = legs.person_id.map(best); dl = legs[legs.day == legs.rep].copy()
    acts = acts[acts.person_id.isin(pp.index)].copy(); acts["rep"] = acts.person_id.map(best)
    da = acts[(acts.day - 1) == acts.rep].sort_values(["person_id", "start_time_min"], kind="stable").copy()
    # trips
    dl["purpose"] = np.where(dl.next_purpose.astype(str) == "HOME", dl.previous_purpose.astype(str), dl.next_purpose.astype(str))
    dl.loc[dl.purpose == "SUBTOUR", "purpose"] = "OTHER"
    dl["km"] = np.minimum(dm[dl.start_zone.values, dl.end_zone.values], DIST_CAP_KM)
    dl["dep_hour"] = ((dl.start_time_min % 1440) // 60).clip(0, 23)
    dl["seg"] = dl.person_id.map(pp.seg); dl["cgrp"] = dl.person_id.map(pp.cgrp); dl["w"] = 1.0
    dl["o_purpose"] = dl.previous_purpose.astype(str); dl["d_purpose"] = dl.next_purpose.astype(str); dl["mode"] = dl["mode"].astype(str)
    # tours from the activities of the day: tour id = number of HOME activities seen so far
    da["is_home"] = (da.purpose == "HOME").values
    da["tour"] = da.groupby("person_id").is_home.cumsum()
    na = da[~da.is_home].copy(); na["purpose"] = na.purpose.astype(str); na["atype"] = na.activity_type.astype(str)
    na["is_main"] = na.atype.isin(["MANDATORY", "PRIMARY"]) & (na.purpose != "SUBTOUR")
    na["is_sub"] = na.purpose == "SUBTOUR"; na["is_stop"] = na.atype == "ON_MANDATORY_TOUR"
    key = ["person_id", "tour"]
    main = na[na.is_main].drop_duplicates(key).set_index(key)
    tours = main[["purpose", "start_time_min", "end_time_min", "zone"]].rename(columns={"purpose": "purpose_abit", "zone": "main_zone"})
    na = na.join(tours[["start_time_min"]].rename(columns={"start_time_min": "main_start"}), on=key)
    st = na[na.is_stop]
    tours["n_stops_out"] = (st[st.start_time_min < st.main_start]).groupby(key).size().reindex(tours.index).fillna(0)
    tours["n_stops_in"] = (st[st.start_time_min >= st.main_start]).groupby(key).size().reindex(tours.index).fillna(0)
    tours["n_stops"] = tours.n_stops_out + tours.n_stops_in
    tours["n_sub"] = na[na.is_sub].groupby(key).size().reindex(tours.index).fillna(0)
    tours = tours.reset_index()
    tours["seg"] = tours.person_id.map(pp.seg); tours["cgrp"] = tours.person_id.map(pp.cgrp); tours["w"] = 1.0
    tours["home_zone"] = tours.person_id.map(pp.hhID).map(home)
    tours["dist_primary_km"] = np.minimum(dm[tours.home_zone.values, tours.main_zone.values], DIST_CAP_KM)
    tours["duration_min"] = tours.end_time_min - tours.start_time_min
    tours["start_hour"] = ((tours.start_time_min % 1440) // 60).clip(0, 23)   # main-activity start; the tour start comes from the first leg
    # tour start = first leg of the tour, tour main mode = mode of the leg arriving at the main activity
    dl = dl.sort_values(["person_id", "start_time_min"], kind="stable")
    dl["tour"] = (dl.o_purpose == "HOME").groupby(dl.person_id).cumsum()
    first_leg = dl.groupby(key).start_time_min.first()
    tours = tours.join(first_leg.rename("tour_start_min"), on=key)
    tours["start_hour"] = ((tours.tour_start_min % 1440) // 60).clip(0, 23)
    arr = dl.drop_duplicates(["person_id", "end_time"]).set_index(["person_id", "end_time"])["mode"]
    tours["main_mode"] = arr.reindex(pd.MultiIndex.from_arrays([tours.person_id, tours.start_time_min])).values
    tours["n_trips"] = dl.groupby(key).size().reindex(pd.MultiIndex.from_arrays([tours.person_id, tours.tour])).values
    # subtour tours per worker-day
    nsub = int(tours.n_sub.sum())

    rows = []
    def add(section, metric, value, n, purpose="all", segment="all", county="all"):
        rows.append(dict(section=section, purpose=purpose, segment=segment, county=str(county), metric=metric, value=float(value), n=int(n)))
    pers = pp[pp.seg != "toddler"]
    trav = pers.index.isin(dl.person_id.unique())
    add("split", "households", hh_n, hh_n); add("split", "persons_all", len(pp), len(pp)); add("split", "persons_travellers", int(trav.sum()), int(trav.sum()))
    add("split", "trips", len(dl), len(dl)); add("split", "tours_home_based", len(tours), len(tours))
    for c in groups + ["other"]:
        add("split", "households", int((hh_grp == str(c)).sum()), int((hh_grp == str(c)).sum()), county=c)
    # travellers (all persons incl. toddlers, household basis as in the survey)
    add("travellers", "traveller_share", pp.index.isin(dl.person_id.unique()).mean(), len(pp))
    add("travellers", "traveller_share_monday", pp.index.isin(legs[legs.day == 0].person_id.unique()).mean(), len(pp))
    add("travellers", "traveller_share_5plus", pers.index.isin(dl.person_id.unique()).mean(), len(pers))
    add("travellers", "persons_per_household", len(pp) / hh_n, hh_n)
    for c in groups + ["other"]:
        g = pp[pp.cgrp == str(c)]; add("travellers", "traveller_share", g.index.isin(dl.person_id.unique()).mean(), len(g), county=c)
    # traveller share by household group (the survey's regression estimate; here the exact shares): workers, students, others
    for seg, m in [("worker", pp.seg == "worker"), ("student", pp.seg.str.startswith("student")), ("other", ~(pp.seg == "worker") & ~pp.seg.str.startswith("student"))]:
        add("travellers", "traveller_share_group", pp.index[m].isin(dl.person_id.unique()).mean(), int(m.sum()), segment=seg)
    # tours and trips per traveller-day
    def seg_mask(df, seg):
        if seg == "all": return np.ones(len(df), bool)
        if seg in SEG_GROUPS: return df.seg.isin(SEG_GROUPS[seg]).values
        return (df.seg == seg).values
    travp = pers[trav]; travall = pp[pp.index.isin(dl.person_id.unique())]
    for seg in ["all"] + SEGMENTS + list(SEG_GROUPS) + ["toddler"]:
        ps = (travall if seg == "toddler" else travp)[seg_mask(travall if seg == "toddler" else travp, seg)]; W = len(ps)
        if W == 0: continue
        add("tours", "tours_per_traveller_day", seg_mask(tours, seg).sum() / W, W, segment=seg)
        add("trips", "trips_per_traveller_day", seg_mask(dl, seg).sum() / W, W, segment=seg)
        for pur in PURPOSES:
            add("tours", "tours_per_traveller_day", (seg_mask(tours, seg) & (tours.purpose_abit == pur).values).sum() / W, W, purpose=pur, segment=seg)
            add("trips", "trips_per_traveller_day", (seg_mask(dl, seg) & (dl.purpose == pur).values).sum() / W, W, purpose=pur, segment=seg)
        if seg in ("all", "worker"):
            add("tours", "tours_per_traveller_day", tours[seg_mask(tours, seg)].n_sub.sum() / W, W, purpose="SUBTOUR", segment=seg)
    ntours = tours.groupby("person_id").size().reindex(travp.index).fillna(0)
    for k in range(0, 4):
        add("tours", f"share_persons_{k if k < 3 else '3plus'}_tours", float((ntours >= 3).mean() if k == 3 else (ntours == k).mean()), len(travp))
    for pur in ["all"] + PURPOSES:
        m = tours if pur == "all" else tours[tours.purpose_abit == pur]; m2 = dl if pur == "all" else dl[dl.purpose == pur]
        add("tours", "tours_per_household_day", len(m) / hh_n, hh_n, purpose=pur); add("trips", "trips_per_household_day", len(m2) / hh_n, hh_n, purpose=pur)
    for c in groups + ["other"]:
        ps = travp[travp.cgrp == str(c)]; W = len(ps); g = tours[tours.cgrp == str(c)]; g2 = dl[dl.cgrp == str(c)]
        if W == 0: continue
        add("tours", "tours_per_traveller_day", len(g) / W, W, county=c); add("trips", "trips_per_traveller_day", len(g2) / W, W, county=c)
        for pur in PURPOSES:
            add("tours", "tours_per_traveller_day", (g.purpose_abit == pur).sum() / W, W, purpose=pur, county=c)
            add("trips", "trips_per_traveller_day", (g2.purpose == pur).sum() / W, W, purpose=pur, county=c)
    # stops
    for pur in ["all"] + PURPOSES:
        m = tours if pur == "all" else tours[tours.purpose_abit == pur]
        if len(m) == 0: continue
        add("stops", "stops_out_per_tour", m.n_stops_out.mean(), len(m), purpose=pur); add("stops", "stops_in_per_tour", m.n_stops_in.mean(), len(m), purpose=pur)
        add("stops", "stops_per_tour", m.n_stops.mean(), len(m), purpose=pur); add("stops", "share_tours_with_stop", (m.n_stops > 0).mean(), len(m), purpose=pur)
        add("stops", "trips_per_tour", m.n_trips.mean(), len(m), purpose=pur)
    for spec in ["HBW", "HBE", "HBS", "HBO"]:
        m = tours[tours.purpose_abit.map(STOP_SPEC) == spec]
        if len(m): add("stops", "stops_out_per_tour", m.n_stops_out.mean(), len(m), purpose=spec); add("stops", "stops_in_per_tour", m.n_stops_in.mean(), len(m), purpose=spec)
    for c in groups + ["other"]:
        g = tours[tours.cgrp == str(c)]
        if len(g): add("stops", "stops_per_tour", g.n_stops.mean(), len(g), county=c)
    # trip length
    for pur in ["all"] + PURPOSES:
        m = dl if pur == "all" else dl[dl.purpose == pur]; m = m[m.km.notna()]
        if len(m) == 0: continue
        add("triplength", "mean_km", m.km.mean(), len(m), purpose=pur); add("triplength", "median_km", m.km.median(), len(m), purpose=pur)
        add("triplength", "p90_km", m.km.quantile(0.9), len(m), purpose=pur); add("triplength", "kish_n", len(m), len(m), purpose=pur)
        for lab, s in zip(DIST_LABELS, whist(m.km, m.w, DIST_BINS)): add("triplength", f"share_{lab}", s, len(m), purpose=pur)
    for pur in PURPOSES:
        m = tours[(tours.purpose_abit == pur) & tours.dist_primary_km.notna()]
        if len(m): add("triplength", "tour_primary_mean_km", m.dist_primary_km.mean(), len(m), purpose=pur); add("triplength", "tour_primary_median_km", m.dist_primary_km.median(), len(m), purpose=pur)
    com = dl[(dl.o_purpose == "HOME") & (dl.d_purpose == "WORK") & dl.km.notna()]
    for c in ["all"] + groups + ["other"]:
        m = com if c == "all" else com[com.cgrp == str(c)]
        if len(m) == 0: continue
        add("work", "commute_mean_km", m.km.mean(), len(m), county=c); add("work", "commute_median_km", m.km.median(), len(m), county=c); add("work", "commute_kish_n", len(m), len(m), county=c)
        for lab, s in zip(DIST_LABELS, whist(m.km, m.w, DIST_BINS)): add("work", f"commute_share_{lab}", s, len(m), county=c)
    # own-county work share: HOME -> WORK legs of the day whose destination zone lies in the home county (survey: destination county of the trip)
    wt = com.copy(); wt["home_cty"] = wt.start_zone.map(zc); wt["work_cty"] = wt.end_zone.map(zc)
    for c in ["all"] + groups + ["other"]:
        m = wt if c == "all" else wt[wt.cgrp == str(c)]
        if len(m): add("work", "own_county_work_share", (m.home_cty == m.work_cty).mean(), len(m), county=c)
    wkr = travp[travp.seg == "worker"]; has_work = wkr.index.isin(tours[tours.purpose_abit == "WORK"].person_id)
    add("work", "workers_no_work_tour_share", (~has_work).mean(), len(wkr)); add("work", "work_tours_per_worker_day", (tours.purpose_abit == "WORK").sum() / max(1, len(wkr)), len(wkr))
    allw = pers[pers.seg == "worker"]
    add("work", "workers_no_work_tour_share_allworkers", 1 - allw.index.isin(tours[tours.purpose_abit == "WORK"].person_id).mean(), len(allw))
    for c in groups + ["other"]:
        g = wkr[wkr.cgrp == str(c)]; hw = g.index.isin(tours[tours.purpose_abit == "WORK"].person_id)
        if len(g): add("work", "workers_no_work_tour_share", (~hw).mean(), len(g), county=c)
    # modes
    for pur in ["all"] + PURPOSES:
        m = dl if pur == "all" else dl[dl.purpose == pur]
        for md, s in wshares(m["mode"], m.w, MODES).items(): add("modes", f"trip_share_{md}", s, len(m), purpose=pur)
    for c in groups + ["other"]:
        m = dl[dl.cgrp == str(c)]
        for md, s in wshares(m["mode"], m.w, MODES).items(): add("modes", f"trip_share_{md}", s, len(m), county=c)
    tm = tours[tours.main_mode.notna()]
    for pur in ["all"] + PURPOSES:
        m = tm if pur == "all" else tm[tm.purpose_abit == pur]
        for md, s in wshares(m.main_mode.astype(str), m.w, MODES).items(): add("modes", f"tour_share_{md}", s, len(m), purpose=pur)
    # time of day and durations
    for pur in ["all"] + PURPOSES:
        m = tours if pur == "all" else tours[tours.purpose_abit == pur]
        for hr, s in zip(HOURS, whist(m.start_hour, m.w, np.arange(25))): add("tod_tour", f"start_share_h{hr:02d}", s, len(m), purpose=pur)
        m2 = dl if pur == "all" else dl[dl.purpose == pur]
        for hr, s in zip(HOURS, whist(m2.dep_hour, m2.w, np.arange(25))): add("tod_trip", f"dep_share_h{hr:02d}", s, len(m2), purpose=pur)
        add("tod_trip", "kish_n", len(m2), len(m2), purpose=pur)
        dd = m[m.duration_min.between(1, 1200)]
        if len(dd):
            add("duration", "primary_duration_mean_min", dd.duration_min.mean(), len(dd), purpose=pur); add("duration", "primary_duration_median_min", dd.duration_min.median(), len(dd), purpose=pur)
            for hr, s in zip(range(0, 20), whist(dd.duration_min / 60.0, dd.w, np.arange(21))): add("duration", f"primary_duration_share_h{hr:02d}", s, len(dd), purpose=pur)
    for c in groups + ["other"]:
        m2 = dl[dl.cgrp == str(c)]
        for hr, s in zip(HOURS, whist(m2.dep_hour, m2.w, np.arange(25))): add("tod_trip", f"dep_share_h{hr:02d}", s, len(m2), county=c)
    # intrazonal share (model diagnostic)
    add("triplength", "intrazonal_share", (dl.start_zone == dl.end_zone).mean(), len(dl))
    out = pd.DataFrame(rows)
    # keep the raw samples needed by the distribution tests (KS) of validate_abit.py
    samples = {"trip_km": dl[["purpose", "cgrp", "km"]].dropna(), "commute_km": com[["cgrp", "km"]], "trip_dep": dl[["purpose", "cgrp", "start_time_min"]].assign(dep_min=lambda x: x.start_time_min % 1440)[["purpose", "cgrp", "dep_min"]],
               "tour_dur": tours[["purpose_abit", "duration_min"]], "tour_start": tours[["purpose_abit", "tour_start_min"]].assign(start_min=lambda x: x.tour_start_min % 1440)[["purpose_abit", "start_min"]]}
    return out, samples


def compare(model, tg):
    """Model against target on the common keys: ratio and difference."""
    k = ["section", "purpose", "segment", "county", "metric"]
    m = tg.merge(model, on=k, suffixes=("_obs", "_model"), how="inner")
    m["ratio"] = m.value_model / m.value_obs; m["diff"] = m.value_model - m.value_obs
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("name"); ap.add_argument("--targets", default=f"{A3}/targets_estimation.csv"); ap.add_argument("--out")
    a = ap.parse_args(); tg = pd.read_csv(a.targets, dtype={"county": str})
    out, _ = run_metrics(a.name, tg); f = a.out or f"{A3}/run/{a.name}/metrics.csv"; out.to_csv(f, index=False); print(f"wrote {f}: {len(out)} rows")
    c = compare(out, tg)
    pd.set_option("display.width", 200)
    print(c[(c.section == "tours") & (c.metric == "tours_per_traveller_day") & (c.county == "all")].pivot(index="segment", columns="purpose", values="ratio").round(3).to_string())
    print(c[(c.section == "modes") & (c.county == "all") & c.metric.str.startswith("trip_share")].pivot(index="purpose", columns="metric", values="diff").round(3).to_string())
    print(c[(c.section == "triplength") & (c.county == "all") & c.metric.isin(["mean_km", "median_km"])].pivot(index="purpose", columns="metric", values="ratio").round(3).to_string())
    print(c[(c.section == "stops") & (c.county == "all") & c.metric.isin(["stops_out_per_tour", "stops_in_per_tour"])].pivot(index="purpose", columns="metric", values="ratio").round(3).to_string())
    print(c[(c.section == "work") & (c.county == "all")][["metric", "value_obs", "value_model", "ratio"]].to_string(index=False))
    print(c[(c.section == "travellers") & (c.county == "all")][["metric", "value_obs", "value_model", "ratio"]].to_string(index=False))
