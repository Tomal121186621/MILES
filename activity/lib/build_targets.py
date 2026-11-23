#!/usr/bin/env python3
"""Stage 3, step 1: split the 2017/18 Regional Travel Survey by household into an estimation half and a validation
half, and build the DAYMAP calibration targets from the ESTIMATION half only.

Run: python3 activity/lib/build_targets.py [--half estimation|validation]

Outputs
  Validation_2026/data/rts_split.csv              household_id, half  (seed 2026, stratified by home county x household
                                                  size 1..5+; alternate assignment inside each stratum after a seeded shuffle)
  Validation_2026/3_abit/targets_estimation.csv   section, purpose, segment, county, metric, value, n  (n = unweighted records)
  Validation_2026/3_abit/estimation_distributions/{tod_rts.csv, duration.distributions.csv, stop_purpose.csv}
                                                  the 15-min start-time and primary-activity-duration distributions by purpose
                                                  in the format of the DAYMAP coefficient files (replace tod_rts.csv and
                                                  duration.distributions.csv of the calibrated coefficient set), and the
                                                  stop-purpose split by tour purpose and position (stop_purpose_split; the
                                                  stop.purpose.file of MarylandStopModel, second pass 2026-10-22)
With --half validation the same tables are written to targets_validation.csv (used only by validate_abit.py; nothing of it
enters the calibration).

Definitions (rts_common.py): rates are per TRAVELLER-day (persons with at least one trip; the files hold no other persons)
with the person weight wtperfin; the all-persons check is tours and trips per HOUSEHOLD-day (wthhfin) and the share of
household members without a trip; trip attributes use wttrdfin; tours are the home-based closed tours of rts_tours.csv.
"""
import os, sys
import numpy as np
import pandas as pd
from rts_common import *   # noqa

OUT_DIR = f"{V}/3_abit"
SEED = 2026


def make_split(h):
    """Stratified half split of the households (county x household size 1..5+), seed 2026."""
    rng = np.random.default_rng(SEED)
    d = h[["county", "hhsize"]].copy(); d["size_cl"] = d.hhsize.clip(upper=5); d["u"] = rng.random(len(d))
    d = d.sort_values(["county", "size_cl", "u"])
    half = np.empty(len(d), dtype=object); pos = 0
    for _, g in d.groupby(["county", "size_cl"], sort=False):
        start = int(rng.integers(0, 2)); n = len(g)
        half[pos:pos + n] = np.where((np.arange(n) + start) % 2 == 0, "estimation", "validation"); pos += n
    d["half"] = half
    return d.half.reindex(h.index)


def targets(half_name, h, p, t, tr):
    """All target tables of one half as a long table."""
    rows = []
    def add(section, metric, value, n, purpose="all", segment="all", county="all"):
        rows.append(dict(section=section, purpose=purpose, segment=segment, county=str(county), metric=metric, value=float(value), n=int(n)))

    hh = h[h.half.eq(half_name)]; pp = p[p.household_id.isin(hh.index)]; tt = t[t.household_id.isin(hh.index)]
    trs = tr[tr.household_id.isin(hh.index)]
    counties = county_groups(h, half_name)
    cty = lambda c: c if c in counties else "other"
    pp = pp.assign(cgrp=pp.county.map(cty)); hh = hh.assign(cgrp=hh.county.map(cty)); tt = tt.assign(cgrp=tt.household_id.map(hh.cgrp))
    trs = trs.assign(cgrp=trs.household_id.map(hh.cgrp), ptype=trs.person_id.map(pp.ptype))
    tt = tt.assign(ptype=tt.person_id.map(pp.ptype))
    add("split", "households", len(hh), len(hh)); add("split", "persons_travellers", len(pp), len(pp)); add("split", "trips", len(tt), len(tt))
    add("split", "tours_home_based", (trs.purpose_abit != "SUBTOUR").sum(), (trs.purpose_abit != "SUBTOUR").sum())
    for c in counties + ["other"]:
        add("split", "households", (hh.cgrp == c).sum(), (hh.cgrp == c).sum(), county=c)

    # ---------------- traveller share (all persons, household record)
    add("travellers", "traveller_share", (hh.wthhfin * hh.n_travellers).sum() / (hh.wthhfin * hh.hhsize).sum(), len(hh))
    add("travellers", "persons_per_household", wmean(hh.hhsize, hh.wthhfin), len(hh))
    for c in counties + ["other"]:
        g = hh[hh.cgrp == c]; add("travellers", "traveller_share", (g.wthhfin * g.n_travellers).sum() / (g.wthhfin * g.hhsize).sum(), len(g), county=c)
    # traveller share by household group (second pass, 2026-10-22): the files hold no non-travellers, so the share of workers,
    # students and other members (retirees, non-workers, under-5s) that travel is estimated by a weighted least-squares fit of
    # the household's travellers on its composition (numworkers, numstudents, hhsize - numworkers - numstudents); reference
    # values for the model's shares by group, not a calibration target
    comp = np.column_stack([hh.numworkers.values, hh.numstudents.values, (hh.hhsize - hh.numworkers - hh.numstudents).clip(lower=0).values]).astype(float)
    sw = np.sqrt(hh.wthhfin.values); beta = np.linalg.lstsq(comp * sw[:, None], hh.n_travellers.values * sw, rcond=None)[0]
    for seg, b in zip(["worker", "student", "other"], beta): add("travellers", "traveller_share_group", float(np.clip(b, 0, 1)), len(hh), segment=seg)

    # ---------------- tours per traveller-day by purpose x segment, and per household-day
    pers = pp[pp.ptype != "toddler"]
    hb = trs[trs.purpose_abit != "SUBTOUR"]
    def seg_mask(df, seg):
        if seg == "all": return np.ones(len(df), bool)
        if seg in SEG_GROUPS: return df.ptype.isin(SEG_GROUPS[seg]).values
        return (df.ptype == seg).values
    segs = ["all"] + SEGMENTS + list(SEG_GROUPS) + ["toddler"]
    W_hh = hh.wthhfin.sum()
    for seg in segs:
        # the under-5 rows (segment toddler, rates per travelling under-5) are the frequency targets of the model's toddler
        # segment (second pass, 2026-10-22); they are not part of the person-type tables, whose basis stays persons 5+
        ps = (pp if seg == "toddler" else pers)[seg_mask(pp if seg == "toddler" else pers, seg)]; W = ps.wtperfin.sum()
        if len(ps) == 0: continue
        add("tours", "tours_per_traveller_day", hb[seg_mask(hb, seg)].wtperfin.sum() / W, len(ps), segment=seg)
        add("trips", "trips_per_traveller_day", tt[seg_mask(tt, seg)].wttrdfin.sum() / W, len(ps), segment=seg)
        for pur in PURPOSES:
            m = hb[seg_mask(hb, seg) & (hb.purpose_abit == pur).values]
            add("tours", "tours_per_traveller_day", m.wtperfin.sum() / W, len(ps), purpose=pur, segment=seg)
            m2 = tt[seg_mask(tt, seg) & (tt.purpose == pur).values]
            add("trips", "trips_per_traveller_day", m2.wttrdfin.sum() / W, len(ps), purpose=pur, segment=seg)
        if seg in ("all", "worker"):
            m = trs[seg_mask(trs, seg) & (trs.purpose_abit == "SUBTOUR").values]
            add("tours", "tours_per_traveller_day", m.wtperfin.sum() / W, len(ps), purpose="SUBTOUR", segment=seg)
    # share of persons with k home-based tours (all travellers)
    ntours = hb.groupby("person_id").size().reindex(pers.index).fillna(0)
    for k in range(0, 4):
        add("tours", f"share_persons_{k if k < 3 else '3plus'}_tours", wmean(ntours >= 3 if k == 3 else ntours == k, pers.wtperfin), len(pers))
    for pur in ["all"] + PURPOSES:
        m = hb if pur == "all" else hb[hb.purpose_abit == pur]; m2 = tt if pur == "all" else tt[tt.purpose == pur]
        add("tours", "tours_per_household_day", m.wtperfin.sum() / W_hh, len(hh), purpose=pur)
        add("trips", "trips_per_household_day", m2.wttrdfin.sum() / W_hh, len(hh), purpose=pur)
    # by county (all segments)
    for c in counties + ["other"]:
        ps = pers[pers.cgrp == c]; W = ps.wtperfin.sum(); g = hb[hb.cgrp == c]; g2 = tt[tt.cgrp == c]
        add("tours", "tours_per_traveller_day", g.wtperfin.sum() / W, len(ps), county=c)
        add("trips", "trips_per_traveller_day", g2.wttrdfin.sum() / W, len(ps), county=c)
        for pur in PURPOSES:
            add("tours", "tours_per_traveller_day", g[g.purpose_abit == pur].wtperfin.sum() / W, len(ps), purpose=pur, county=c)
            add("trips", "trips_per_traveller_day", g2[g2.purpose == pur].wttrdfin.sum() / W, len(ps), purpose=pur, county=c)

    # ---------------- stops per tour (out / in / total) by purpose and stop spec
    for pur in ["all"] + PURPOSES:
        m = hb if pur == "all" else hb[hb.purpose_abit == pur]
        if len(m) == 0: continue
        add("stops", "stops_out_per_tour", wmean(m.n_stops_out, m.wtperfin), len(m), purpose=pur)
        add("stops", "stops_in_per_tour", wmean(m.n_stops_in, m.wtperfin), len(m), purpose=pur)
        add("stops", "stops_per_tour", wmean(m.n_stops, m.wtperfin), len(m), purpose=pur)
        add("stops", "share_tours_with_stop", wmean(m.n_stops > 0, m.wtperfin), len(m), purpose=pur)
        add("stops", "trips_per_tour", wmean(m.n_trips, m.wtperfin), len(m), purpose=pur)
    for spec in ["HBW", "HBE", "HBS", "HBO"]:
        m = hb[hb.purpose_abit.map(STOP_SPEC) == spec]
        add("stops", "stops_out_per_tour", wmean(m.n_stops_out, m.wtperfin), len(m), purpose=spec)
        add("stops", "stops_in_per_tour", wmean(m.n_stops_in, m.wtperfin), len(m), purpose=spec)
    for c in counties + ["other"]:
        g = hb[hb.cgrp == c]; add("stops", "stops_per_tour", wmean(g.n_stops, g.wtperfin), len(g), county=c)

    # ---------------- trip length (driving km) by purpose: mean, median, bins; commute by county
    for pur in ["all"] + PURPOSES:
        m = tt if pur == "all" else tt[tt.purpose == pur]; m = m[m.km.notna()]
        add("triplength", "mean_km", wmean(m.km, m.wttrdfin), len(m), purpose=pur)
        add("triplength", "median_km", wquantile(m.km, m.wttrdfin, 0.5), len(m), purpose=pur)
        add("triplength", "p90_km", wquantile(m.km, m.wttrdfin, 0.9), len(m), purpose=pur)
        add("triplength", "kish_n", kish_n(m.wttrdfin), len(m), purpose=pur)
        for lab, s in zip(DIST_LABELS, whist(m.km, m.wttrdfin, DIST_BINS)):
            add("triplength", f"share_{lab}", s, len(m), purpose=pur)
    # home-to-main-activity distance of tours (dist_primary) by purpose
    for pur in PURPOSES:
        m = hb[(hb.purpose_abit == pur) & hb.dist_primary_km.notna()]
        add("triplength", "tour_primary_mean_km", wmean(m.dist_primary_km, m.wtperfin), len(m), purpose=pur)
        add("triplength", "tour_primary_median_km", wquantile(m.dist_primary_km, m.wtperfin, 0.5), len(m), purpose=pur)
    com = tt[(tt.o_purpose == "HOME") & (tt.d_purpose == "WORK") & tt.km.notna()]
    for c in ["all"] + counties + ["other"]:
        m = com if c == "all" else com[com.cgrp == c]
        if len(m) == 0: continue
        add("work", "commute_mean_km", wmean(m.km, m.wttrdfin), len(m), county=c)
        add("work", "commute_median_km", wquantile(m.km, m.wttrdfin, 0.5), len(m), county=c)
        add("work", "commute_kish_n", kish_n(m.wttrdfin), len(m), county=c)
        for lab, s in zip(DIST_LABELS, whist(m.km, m.wttrdfin, DIST_BINS)):
            add("work", f"commute_share_{lab}", s, len(m), county=c)
    # own-county work share: home -> work trips on the travel day whose destination county is the home county (wttrdfin)
    wk = com[com.d_county > 0]
    for c in ["all"] + counties + ["other"]:
        m = wk if c == "all" else wk[wk.cgrp == c]
        if len(m) == 0: continue
        add("work", "own_county_work_share", wmean(m.d_county == m.home_county, m.wttrdfin), len(m), county=c)
    # the usual-workplace definition (workers with a work trip that day, work_state_county_fips against home county), for reference
    wk2 = pp[(pp.ptype == "worker") & pp.index.isin(tt[tt.d_purpose == "WORK"].person_id) & (pp.work_county > 0)]
    add("work", "own_county_usual_workplace_share", wmean(wk2.work_county == wk2.county, wk2.wtperfin), len(wk2))
    # work-from-home: workers (travellers) without a work tour on the day; usual telecommute days per week / 5
    wkr = pp[pp.ptype == "worker"]
    has_work = wkr.index.isin(hb[hb.purpose_abit == "WORK"].person_id)
    add("work", "workers_no_work_tour_share", wmean(~has_work, wkr.wtperfin), len(wkr))
    add("work", "work_tours_per_worker_day", hb[hb.purpose_abit == "WORK"].wtperfin.sum() / wkr.wtperfin.sum(), len(wkr))
    tc = wkr.j1_telecommute_days.astype(str).str.replace("+", "", regex=False)
    tcn = pd.to_numeric(tc, errors="coerce"); m = tcn >= 0
    add("work", "telecommute_days_per_week", wmean(tcn[m], wkr.wtperfin[m]), int(m.sum()))
    add("work", "wfh_share_of_weekdays", wmean(tcn[m] / 5.0, wkr.wtperfin[m]), int(m.sum()))
    for c in counties + ["other"]:
        g = wkr[wkr.cgrp == c]; hw = g.index.isin(hb[hb.purpose_abit == "WORK"].person_id)
        add("work", "workers_no_work_tour_share", wmean(~hw, g.wtperfin), len(g), county=c)

    # ---------------- mode shares: trip level by purpose (and county), tour main mode by purpose
    tm = tt[tt["mode"].notna()]
    for pur in ["all"] + PURPOSES:
        m = tm if pur == "all" else tm[tm.purpose == pur]
        for md, s in wshares(m["mode"], m.wttrdfin, MODES).items():
            add("modes", f"trip_share_{md}", s, len(m), purpose=pur)
    for c in counties + ["other"]:
        m = tm[tm.cgrp == c]
        for md, s in wshares(m["mode"], m.wttrdfin, MODES).items():
            add("modes", f"trip_share_{md}", s, len(m), county=c)
    hbm = hb.assign(main_mode=tour_main_mode(hb, tt)); hbm = hbm[hbm.main_mode.notna()]
    for pur in ["all"] + PURPOSES:
        m = hbm if pur == "all" else hbm[hbm.purpose_abit == pur]
        for md, s in wshares(m.main_mode, m.wtperfin, MODES).items():
            add("modes", f"tour_share_{md}", s, len(m), purpose=pur)

    # ---------------- time of day: tour start hour by purpose, trip departure hour by purpose; primary durations
    for pur in ["all"] + PURPOSES:
        m = hb if pur == "all" else hb[hb.purpose_abit == pur]
        for hr, s in zip(HOURS, whist(m.start_hour, m.wtperfin, np.arange(25))):
            add("tod_tour", f"start_share_h{hr:02d}", s, len(m), purpose=pur)
        m2 = tt if pur == "all" else tt[tt.purpose == pur]
        for hr, s in zip(HOURS, whist(m2.dep_hour, m2.wttrdfin, np.arange(25))):
            add("tod_trip", f"dep_share_h{hr:02d}", s, len(m2), purpose=pur)
        add("tod_trip", "kish_n", kish_n(m2.wttrdfin), len(m2), purpose=pur)
        d = m[m.duration_min.between(1, 1200)]
        add("duration", "primary_duration_mean_min", wmean(d.duration_min, d.wtperfin), len(d), purpose=pur)
        add("duration", "primary_duration_median_min", wquantile(d.duration_min, d.wtperfin, 0.5), len(d), purpose=pur)
        for hr, s in zip(range(0, 20), whist(d.duration_min / 60.0, d.wtperfin, np.arange(21))):
            add("duration", f"primary_duration_share_h{hr:02d}", s, len(d), purpose=pur)
    for c in counties + ["other"]:
        m2 = tt[tt.cgrp == c]
        for hr, s in zip(HOURS, whist(m2.dep_hour, m2.wttrdfin, np.arange(25))):
            add("tod_trip", f"dep_share_h{hr:02d}", s, len(m2), county=c)
    return pd.DataFrame(rows), hb


def write_distribution_files(hb, out_dir):
    """tod_rts.csv (time,purpose,probability; 15-min bins of the ARRIVAL at the primary activity: MarylandTimeAssignment uses the
    sampled minute as the start of the main activity and PlanTools derives the home departure from it, so the survey's primary
    arrival is the consistent quantity; found 2026-10-22, the earlier file held the home departure) and duration.distributions.csv
    (duration_min,purpose,start_from_h,start_to_h,duration_prob) from the estimation half, in the format DAYMAP reads
    (MarylandTimeAssignment.readDist: bins of 15 min, columns found by name)."""
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for pur in PURPOSES:
        m = hb[hb.purpose_abit == pur]
        h = whist(m.primary_arr, m.wtperfin, np.arange(0, 1441, 15))
        rows += [dict(time=int(i * 15), purpose=pur, probability=round(float(v), 6)) for i, v in enumerate(h)]
    pd.DataFrame(rows).to_csv(f"{out_dir}/tod_rts.csv", index=False)
    rows = []
    for pur in PURPOSES:
        m = hb[(hb.purpose_abit == pur) & hb.duration_min.between(1, 1200)]
        h = whist(m.duration_min, m.wtperfin, np.arange(0, 1216, 15))
        rows += [dict(duration_min=int(i * 15), purpose=pur, start_from_h=0, start_to_h=24, duration_prob=round(float(v), 6)) for i, v in enumerate(h)]
    pd.DataFrame(rows).to_csv(f"{out_dir}/duration.distributions.csv", index=False)


def stop_purpose_split(hb, tt):
    """Purpose of the intermediate stops by tour purpose and position (second pass, 2026-10-22): the trips of the half are
    matched to the home-based tours of rts_tours.csv by person and time window (departure >= tour start, arrival <= tour end);
    a trip that does not go home and arrives before the primary arrival is an outbound stop, one that departs at or after the
    primary departure and does not go home an inbound stop; the stop purpose is its destination activity.  Rows:
    tour_purpose, half (out / in), probabilities of WORK..OTHER (wttrdfin-weighted), n (unweighted stops).  The survey's tour
    purpose follows the hierarchy work > school > shopping > other of the primary activity, so a shopping stop occurs only on
    work, school and shopping tours; the model draws from these conditional splits (MarylandStopModel, stop.purpose.file)."""
    m = tt.merge(hb[["person_id", "start_min", "end_min", "primary_arr", "primary_dep", "purpose_abit"]], on="person_id", how="inner")
    m = m[(m.dep_min >= m.start_min) & (m.arr_min <= m.end_min) & (m.d_purpose != "HOME")]
    out = m[m.arr_min < m.primary_arr].assign(half="out"); inn = m[m.dep_min >= m.primary_dep].assign(half="in")
    rows = []
    for (pur, hf), g in pd.concat([out, inn]).groupby(["purpose_abit", "half"]):
        if pur not in PURPOSES: continue
        s = wshares(g.d_purpose, g.wttrdfin, PURPOSES)
        rows.append(dict(tour_purpose=pur, half=hf, **{k: round(v, 4) for k, v in s.items()}, n=len(g)))
    return pd.DataFrame(rows)


def main():
    half = "estimation"
    if "--half" in sys.argv: half = sys.argv[sys.argv.index("--half") + 1]
    h = load_households(); p = load_persons(); t = load_trips(); tr = load_tours()
    if not os.path.exists(SPLIT_FILE):
        os.makedirs(os.path.dirname(SPLIT_FILE), exist_ok=True)
        s = make_split(h); s.rename("half").reset_index().to_csv(SPLIT_FILE, index=False)
        print(f"wrote {SPLIT_FILE}: {s.value_counts().to_dict()}")
    h["half"] = load_split().reindex(h.index)
    assert h.half.notna().all()
    # balance of the split
    for hf in ["estimation", "validation"]:
        g = h[h.half == hf]; print(f"{hf}: {len(g)} households, {int(g.n_travellers.sum())} travellers, mean size {g.hhsize.mean():.3f}, "
                                   f"weighted persons {(g.wthhfin * g.hhsize).sum():,.0f}")
    out, hb = targets(half, h, p, t, tr)
    f = f"{OUT_DIR}/targets_{half}.csv"; out.to_csv(f, index=False); print(f"wrote {f}: {len(out)} rows")
    if half == "estimation":
        write_distribution_files(hb, f"{OUT_DIR}/estimation_distributions")
        sp = stop_purpose_split(hb, t[t.household_id.isin(h[h.half.eq(half)].index)])
        sp.to_csv(f"{OUT_DIR}/estimation_distributions/stop_purpose.csv", index=False)
        print(f"wrote {OUT_DIR}/estimation_distributions/{{tod_rts.csv,duration.distributions.csv,stop_purpose.csv}}")
        print("\nstop purposes by tour purpose and position:"); print(sp.to_string(index=False))
    # summary
    x = out[(out.section == "tours") & (out.metric == "tours_per_traveller_day") & (out.county == "all")]
    print("\ntours per traveller-day (purpose x segment):")
    print(x.pivot(index="segment", columns="purpose", values="value").reindex(["all"] + SEGMENTS + ["student"]).round(3).to_string())
    x = out[(out.section == "modes") & (out.county == "all") & out.metric.str.startswith("trip_share")]
    print("\ntrip mode shares by purpose:"); print(x.pivot(index="purpose", columns="metric", values="value").round(3).to_string())
    x = out[(out.section == "triplength") & (out.county == "all") & out.metric.isin(["mean_km", "median_km"])]
    print("\ntrip length by purpose:"); print(x.pivot(index="purpose", columns="metric", values="value").round(2).to_string())
    x = out[(out.section == "stops") & (out.county == "all") & out.metric.isin(["stops_out_per_tour", "stops_in_per_tour", "stops_per_tour"])]
    print("\nstops per tour:"); print(x.pivot(index="purpose", columns="metric", values="value").round(3).to_string())
    print("\nwork:"); print(out[(out.section == "work") & (out.county == "all") & ~out.metric.str.contains("share_")].to_string(index=False))


if __name__ == "__main__":
    main()
