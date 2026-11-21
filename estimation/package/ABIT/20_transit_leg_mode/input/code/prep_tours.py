#!/usr/bin/env python3
"""Home-based tours of the 2017/18 RTS for the tour mode choice (both halves; data/rts_split.csv, seed 2026).

    python3 prep_tours.py        -> work/tours_<half>.parquet, results/tour_build_<half>.csv, results/parking_paid_share.csv

Tours.  The typed episodes of 3_abit/tasha_estimation (te_common.episodes: one row per trip destination with its TASHA type) are
cut into home-based chains exactly as the ABIT/TASHA generator forms them: a chain is the sequence of out-of-home episodes between
a departure from home and the next arrival at home; a return home during work (type RHW) is at home.  Chains that do not start at
home (the first chain of a day that begins away from home) or do not end at home are dropped.  The main activity is the work
episode (PW, SW, WB, WAHB, in this order), else the school episode, else the longest episode (MarylandTashaGenerator.mainOf).
The tour has stops when it has more than one episode.

Tour mode (main-mode hierarchy).  MAST gives one mode to every leg of a tour, so the survey tour gets the highest mode used on any
of its trips:  transit (rail or bus) > car driver > car passenger > bike > walk.  A transit tour is drive access when any of its
transit trips has access or egress by park and ride, kiss and ride or taxi, or the tour also has a car-driver trip; else walk
access.  Survey modes as rts_common.MODE_MAP (school bus, paratransit, taxi and ride hailing are car passenger); tours with an
air, water or other trip are dropped.

Level of service.  mc_common.tour_los on the home zone and the zone of the main episode (tract internal point), outbound period
= start of the main activity (arrival), return period = its end (departure of the next trip).
"""
# COPY of Validation_2026/3_abit/mode_choice/prep_tours.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, f"{os.path.dirname(HERE)}/tasha_estimation")
sys.path.insert(0, f"{os.path.dirname(HERE)}/destination_choice")
import mc_common as M                       # noqa: E402
import te_common as TE                      # noqa: E402
from prep_dc_data import people             # noqa: E402
from rts_common import RTS, MODE_MAP        # noqa: E402

RANK = {"PW": 0, "SW": 1, "WB": 2, "WAHB": 3, "SCH": 4}
HIER = ["TRANSIT", "CAR_DRIVER", "CAR_PASSENGER", "BIKE", "WALK"]
BMC = [24003, 24005, 24013, 24025, 24027, 24510]


def chains(e):
    """tour records from the episode rows of one half"""
    e = e.sort_values(["person_id", "tripno"], kind="stable")
    out = []
    for pid, g in e.groupby("person_id", sort=False):
        cur = []; started = False
        rows = g.to_dict("records")
        for q, r in enumerate(rows):
            if not started:
                if r["o_activity"] == 1: started = True
                else:
                    if r["is_home"]: started = True
                    continue
            if r["is_home"]:
                if cur: out.append((pid, cur + [r]))
                cur = []
            else: cur.append(r)
        # a chain left open at the end of the day is dropped
    return out


def build(half):
    e = TE.episodes(half)
    f = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv.gz", low_memory=False, usecols=["tripid", "travel_mode", "transit_access_mode", "transit_egress_mode", "park_pay"]).drop_duplicates("tripid")
    e = e.merge(f, on="tripid", how="left")
    recs = []; nbad = 0
    for pid, c in chains(e):
        eps, back = c[:-1], c[-1]
        main = min(eps, key=lambda r: (RANK.get(r["type"], 5), -(r["dur"] if RANK.get(r["type"], 5) == 5 and np.isfinite(r["dur"]) else 0)))
        modes = [MODE_MAP.get(int(r["travel_mode"])) if np.isfinite(r["travel_mode"]) else None for r in c]
        if any(m is None for m in modes): nbad += 1; continue
        tr = [m in ("TRAIN", "BUS") for m in modes]
        top = next(h for h in HIER if (h == "TRANSIT" and any(tr)) or h in modes)
        drive_acc = any(t and (int(r["transit_access_mode"]) in (3, 4, 5) or int(r["transit_egress_mode"]) in (3, 4, 5)) for t, r in zip(tr, c)) or (any(tr) and "CAR_DRIVER" in modes)
        alt = {"TRANSIT": "TD" if drive_acc else "TW", "CAR_DRIVER": "CD", "CAR_PASSENGER": "CP", "BIKE": "BK", "WALK": "WK"}[top]
        i = c.index(main); nxt = c[i + 1]
        recs.append(dict(person_id=pid, household_id=main["household_id"], purpose=main["purpose"], type=main["type"], n_ep=len(eps),
                         hz=main["hz"], mz=main["dz"], start=main["arr_min"], end=nxt["dep_min"], leave=c[0]["dep_min"], arrive=back["arr_min"],
                         choice=alt, rail=any(m == "TRAIN" for m in modes), joint=main["jgid"] >= 0 if np.isfinite(main["jgid"]) else False,
                         w=main["w_person"], paid_park=int(any(m == "CAR_DRIVER" and r["park_pay"] == 1 for m, r in zip(modes, c))),
                         trips=len(c), tripids=[r["tripid"] for r in c]))
    t = pd.DataFrame(recs)
    t["segment"] = t.purpose.map(M.SEG_OF)
    st = [dict(step="chains closed at home", n=len(t) + nbad), dict(step="dropped: air / water / other mode", n=nbad)]
    P = people(half); t = t[t.person_id.isin(P.index)].copy(); st.append(dict(step="persons of the survey-population input", n=len(t)))
    t = t[(t.hz >= 0) & (t.mz >= 0)].copy(); st.append(dict(step="home and main zone in the zone system", n=len(t)))
    p = P.reindex(t.person_id.values)
    for k in ["age", "male", "lic", "hhsize", "children", "autos", "drivers", "inc_month", "occ", "county"]:
        if k in p: t[k] = p[k].values
    t["male"] = (P.reindex(t.person_id.values).gender.values == 1).astype(float); t["lic"] = P.reindex(t.person_id.values).lic.values.astype(float)
    t["inc_year"] = 12.0 * t.inc_month
    t["county"] = P.reindex(t.person_id.values)["county"].values if "county" in P else -1
    z = M.C.zones(); idx = M.C.id2idx(); t["h"] = idx[t.hz.values]; t["m"] = idx[t.mz.values]
    t = t[(t.h >= 0) & (t.m >= 0)].copy()
    t["pout"] = M.period(t.start.values); t["pret"] = M.period(t.end.values)
    v = M.tour_los(t.h.values, t.m.values, t.pout.values, t.pret.values)
    for k, x in v.items(): t[k] = x
    for k, x in M.tour_los2(t.h.values, t.m.values, t.pout.values, t.pret.values).items(): t[k] = x
    # choice in the GC specification: transit tours are TRAIN when any trip of the tour is by rail, else BUS
    t["choice2"] = np.where(t.choice.isin(["TW", "TD"]), np.where(t.rail, "TRAIN", "BUS"), t.choice)
    dens = ((z["pop"] + z.jobs) / z.area_km2.clip(lower=0.05)).values
    t["lnden_h"] = np.log1p(dens[t.h.values] / 1000.0); t["lnden_m"] = np.log1p(dens[t.m.values] / 1000.0)
    t["cbd_m"] = z.cbd.values[t.m.values]; t["bc_m"] = z.bc.values[t.m.values]; t["dc_m"] = z.dcz.values[t.m.values]
    t["bmc"] = np.isin(z.countyfips.values[t.h.values], BMC).astype(float)
    t["park_area"] = park_area(z, t.m.values)
    t["stops"] = (t.n_ep > 1).astype(float)
    t.to_parquet(f"{M.WORK}/tours_{half}.parquet", index=False)
    pd.DataFrame(st).to_csv(f"{M.RES}/tour_build_{half}.csv", index=False)
    print(half, st[-1], t.choice.value_counts().to_dict(), flush=True)
    return t


def park_area(z, m):
    """destination area class of the paid-parking share: 0 CBD of Baltimore City, 1 other Baltimore City, 2 Washington DC CBD,
    3 other DC, 4 other CBD zones, 5 elsewhere"""
    cbd, bc, dc = z.cbd.values[m], z.bc.values[m], z.dcz.values[m]
    return np.select([(bc == 1) & (cbd == 1), bc == 1, (dc == 1) & (cbd == 1), dc == 1, cbd == 1], [0, 1, 2, 3, 4], 5)


def biodata():
    """work/bio_<segment>.parquet (estimation half) and work/hold_<segment>.parquet (validation half): the model variables,
    the choice y (1..6 in mc_common.ALTS order), the normalised weight wn; tours whose chosen alternative is unavailable are
    dropped and counted (results/chosen_unavailable.csv)."""
    rows = []
    for half, tag in [("estimation", "bio"), ("validation", "hold")]:
        t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet"); f = M.features(t)
        f["choice"] = t.choice.values; f["y"] = t.choice.map({a: i + 1 for i, a in enumerate(M.ALTS)}).values
        f["segment"] = t.segment.values; f["purpose"] = t.purpose.values; f["w"] = t.w.values; f["person_id"] = t.person_id.values
        f["county"] = t.county.values; f["bmc"] = t.bmc.values; f["rail"] = t.rail.values
        ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(f.choice.values)])
        for seg in M.SEGMENTS:
            s = f.segment.eq(seg)
            for a in M.ALTS: rows.append(dict(half=half, segment=seg, alt=a, chosen=int((s & f.choice.eq(a)).sum()), chosen_unavailable=int((s & f.choice.eq(a) & ~ok).sum())))
            g = f[s & ok].copy(); g["wn"] = 1.0   # no survey weights in estimation (exogenous sampling of households)
            g.reset_index(drop=True).to_parquet(f"{M.WORK}/{tag}_{seg}.parquet", index=False)
    pd.DataFrame(rows).to_csv(f"{M.RES}/chosen_unavailable.csv", index=False); print(pd.DataFrame(rows).groupby(["half", "alt"])[["chosen", "chosen_unavailable"]].sum())


def biodata2():
    """GC specification: work/gc_<tag>_<segment>_s<VOT share x 100>.parquet for the estimation (bio) and validation (hold) halves
    and the VOT shares 0.35, 0.50, 0.70; chosen-unavailable tours dropped and counted (results/gc_chosen_unavailable.csv)"""
    rows = []
    for half, tag in [("estimation", "bio"), ("validation", "hold")]:
        t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet")
        for vs in [0.35, 0.50, 0.70]:
            f = M.features2(t, vs)
            f["choice"] = t.choice2.values; f["y"] = t.choice2.map({a: i + 1 for i, a in enumerate(M.ALTS2)}).values
            for k in ["segment", "purpose", "w", "person_id", "household_id", "county", "inc_year", "drivers", "pout", "h", "m", "stops", "joint"]: f[k] = t[k].values
            ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(f.choice.values)])
            for seg in M.SEGMENTS:
                sm = f.segment.eq(seg)
                if vs == 0.50:
                    for a in M.ALTS2: rows.append(dict(half=half, segment=seg, alt=a, chosen=int((sm & f.choice.eq(a)).sum()), chosen_unavailable=int((sm & f.choice.eq(a) & ~ok).sum())))
                g = f[sm & ok].copy(); g["wn"] = 1.0   # no survey weights in estimation (exogenous sampling of households)
                g.reset_index(drop=True).to_parquet(f"{M.WORK}/gc_{tag}_{seg}_s{int(round(vs * 100))}.parquet", index=False)
    r = pd.DataFrame(rows); r.to_csv(f"{M.RES}/gc_chosen_unavailable.csv", index=False)
    print(r.groupby(["half", "alt"])[["chosen", "chosen_unavailable"]].sum())


if __name__ == "__main__":
    if sys.argv[-1] == "biodata": biodata(); sys.exit()
    if sys.argv[-1] == "biodata2": biodata2(); sys.exit()
    te = build("estimation"); build("validation")
    # paid-parking share of car-driver tours by destination area (estimation half): the parking variable of the car-driver utility
    cd = te[te.choice.eq("CD")]
    s = cd.groupby("park_area").apply(lambda g: pd.Series(dict(share=np.average(g.paid_park, weights=g.w), n=len(g))), include_groups=False).reset_index()
    s.to_csv(f"{M.RES}/parking_paid_share.csv", index=False); print(s)
