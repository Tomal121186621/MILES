#!/usr/bin/env python3
"""Count validation of the MATSim 2024 stage (validation study, 2026-11-02): five assignment seeds against the MDOT SHA 2024 counts.

Model   : residents of the Baltimore region only (ABIT 2024 replication closest to the median, BMR residents, no cordon gateways,
          no external-external, background or truck traffic), network 2024 (Key Bridge closed), harbor tunnel tolls, USDOT value
          of time, 10 % sample, 100 iterations, seeds 1-5.  Nothing is fitted to the counts.
          Link volume (the bus fix of I695_pricing/00_research/validation_core.py): cars = (final link stats, averaged over iterations
          96-100, minus the transit-vehicle entries of the final iteration) x 10 (sample expansion); buses x 1 (they run at their real
          number); all vehicles = cars + buses.  Weekday hours 0-24.
Counts  : MDOT SHA 2024 annual average weekday traffic (AAWDT), all vehicles, at the stations matched to network_2024 links by
          4_matsim/network/match_count_stations.py (both directions summed; matched, unambiguous, with a 2024 count = the 3,412 stations of
          data/count_stations_split.csv).  Passenger comparison: count x (1 - truck share - bus share) against model cars; shares from the
          station's own MDOT classification, else the count-weighted mean of the classified stations of its class (validation_core rule).
          Hourly permanent counters: FHWA TMAS 2023 weekday hourly means by direction (I695_pricing/data/corridor_fit/targets_v7.csv,
          kind 'hourly'; link ids valid in network_2024), scaled to 2024 by the station's MDOT AADT 2024 / 2023; GEH on these only.
Standards: FDOT 2008 %RMSE by volume group and volume/count by facility (Tennessee 2016, Tables 5 and 10); FHWA desirable deviation
          by volume (Tennessee Table 6); UK TAG M3.1: GEH < 5 for > 85 % of hourly flows.
Seeds   : every statistic per seed, then mean, s.d. and the range over the seeds (smallest to largest; the *_p5 / *_p95 columns hold the min and max).
Run     : python3 validate_counts.py   (env RUN_ROOT, IT, SEEDS for tests) -> data/*.csv, data/tables.json, figures/*.pdf|png"""
import os, sys, re, json, glob, gzip, warnings, numpy as np, pandas as pd; warnings.filterwarnings("ignore")
H = os.path.dirname(os.path.abspath(__file__)); V = os.path.dirname(os.path.dirname(H)); ROOT = os.path.dirname(V)
sys.path.insert(0, f"{V}/5_reports"); import paperstyle as ps
RUN_ROOT = os.environ.get("RUN_ROOT", f"{V}/pipeline/runs/matsim"); IT = int(os.environ.get("IT", "100"))
LH = os.environ.get("LINK_HOURS", f"{H}/data/link_hours"); OUTB = os.environ.get("OUT", H); DATA = f"{OUTB}/data"; FIG = f"{OUTB}/figures"; os.makedirs(DATA, exist_ok=True); os.makedirs(FIG, exist_ok=True)
SEEDS = [int(s) for s in os.environ["SEEDS"].split(",")] if os.environ.get("SEEDS") else sorted({int(m.group(1)) for f in glob.glob(f"{LH}/link_hours_s*.csv.gz") if (m := re.search(r"link_hours_s(\d+)\.csv\.gz$", f))})
EXP = 10; Z90 = 1.645
CLASSES = ["Interstate: I-695", "Interstate: other", "Other freeway / expressway", "Principal arterial", "Minor arterial", "Major collector", "Minor collector / local"]
FAC = {"Interstate: I-695": "freeway", "Interstate: other": "freeway", "Other freeway / expressway": "freeway", "Principal arterial": "arterial",
       "Minor arterial": "arterial", "Major collector": "collector", "Minor collector / local": "collector"}
BAND = {"freeway": (0.07, 0.06), "arterial": (0.15, 0.10), "collector": (0.25, 0.20)}
VGROUPS = [(0, 5e3, 100, 45), (5e3, 1e4, 45, 35), (1e4, 1.5e4, 35, 27), (1.5e4, 2e4, 30, 25), (2e4, 3e4, 27, 15), (3e4, 5e4, 25, 15), (5e4, 6e4, 20, 10), (6e4, 1e12, 19, 10)]
AREAWIDE = (45, 35)
FHWA_DEV = [(0, 1e3, 200), (1e3, 2.5e3, 100), (2.5e3, 5e3, 50), (5e3, 1e4, 25), (1e4, 2.5e4, 20), (2.5e4, 5e4, 15), (5e4, 1e12, 10)]
PERIODS = [("Night (0-6 h)", range(0, 6)), ("Morning peak (6-10 h)", range(6, 10)), ("Midday (10-15 h)", range(10, 15)), ("Evening peak (15-19 h)", range(15, 19)), ("Evening (19-24 h)", range(19, 24)), ("Whole day", range(24))]
geh = lambda m, c: np.sqrt(2 * (m - c) ** 2 / np.maximum(m + c, 1e-9))
HRS = [f"HRS{h}-{h+1}avg" for h in range(24)]

def model_seed(s):
    """car (x EXP) and bus (x 1) by link x hour 0-23 of one seed."""
    LS = pd.read_csv(f"{RUN_ROOT}/2024_s{s}/ITERS/it.{IT}/{IT}.linkstats.txt.gz", sep="\t", dtype={"LINK": str}, usecols=["LINK"] + HRS).set_index("LINK"); LS.columns = range(24)
    E = pd.read_csv(f"{LH}/link_hours_s{s}.csv.gz", dtype={"link": str}); E = E[E.hour < 24]
    pt = (E.assign(pt=E.bus + E.pt_other).pivot_table(index="link", columns="hour", values="pt", aggfunc="sum").reindex(columns=range(24)).fillna(0))
    bus = E.pivot_table(index="link", columns="hour", values="bus", aggfunc="sum").reindex(columns=range(24)).fillna(0)
    car = (LS - pt.reindex(LS.index).fillna(0)).clip(lower=0) * EXP
    return car, bus.reindex(LS.index).fillna(0)

def stations():
    M = pd.read_csv(f"{V}/data/count_stations_matched.csv", dtype={"link_NE": str, "link_SW": str})
    Sp = pd.read_csv(f"{V}/data/count_stations_split.csv")[["LOCATION_ID", "split"]]
    A = M.merge(Sp, on="LOCATION_ID")                       # matched, unambiguous, with a 2024 count
    g = json.load(open(f"{ROOT}/I695_pricing/data/mdot_aadt_statewide_2015-2024.geojson"))
    P = pd.DataFrame([f["properties"] for f in g["features"]]).drop_duplicates("LOCATION_ID").set_index("LOCATION_ID")
    A = A.join(P[["ID_PREFIX", "ID_RTE_NO", "AADT", "BUS_AADT"]].rename(columns={"AADT": "AADT_CLS"}), on="LOCATION_ID")
    A["route"] = (A.ID_PREFIX.fillna("") + " " + A.ID_RTE_NO.astype(str)).str.replace("IS ", "I-").replace({"MD 695": "I-695"})
    i695 = A.route.eq("I-695")
    A["cls"] = np.select([A.F_SYSTEM.eq(1) & i695, A.F_SYSTEM.eq(1), A.F_SYSTEM.eq(2), A.F_SYSTEM.eq(3), A.F_SYSTEM.eq(4), A.F_SYSTEM.eq(5)], CLASSES[:6], CLASSES[6])
    A["fac"] = A.cls.map(FAC)
    # links of a station (count and model must cover the same carriageways): mainline two-way station = both matched directions;
    # one-way station (MDOT split 100/0: couplets, one-way streets, single carriageways) = the link of the counted direction;
    # mainline two-way station with only one direction matched = excluded (the match misses half the count); ramp station = the
    # nearer of the two matched ramp links (a ramp is one-way; the matcher takes the nearest ramp link per bearing, so a second
    # link is a different ramp).  Ramps are reported in their own table, the facility and volume tables use mainline stations.
    ids, use = [], []
    for r in A.itertuples():
        ne = r.link_NE if isinstance(r.link_NE, str) and r.link_NE else None; sw = r.link_SW if isinstance(r.link_SW, str) and r.link_SW else None
        oneway = r.NE_SPLIT in (0, 100) or r.SW_SPLIT in (0, 100)
        if r.MAIN_LINE != 1:
            if ne and sw: ids.append([ne] if (r.dist_NE if pd.notna(r.dist_NE) else 1e9) <= (r.dist_SW if pd.notna(r.dist_SW) else 1e9) else [sw])
            else: ids.append([ne or sw])
            use.append("ramp")
        elif oneway:
            want = ne if r.NE_SPLIT == 100 else sw if r.SW_SPLIT == 100 else None
            ids.append([want] if want else [x for x in (ne, sw) if x]); use.append("mainline" if want else "excluded: counted direction not matched")
        elif ne and sw: ids.append([ne, sw]); use.append("mainline")
        else: ids.append([ne or sw]); use.append("excluded: one direction of a two-way road matched")
    A["ids"] = ids; A["use"] = use
    A["count_all"] = A.AAWDT_2024.where(A.AAWDT_2024 > 0, A.AADT_2024)
    A["counted24"] = A.AAWDT_2024 % 10 == 0                 # MDOT: last digit = years since the count; 0 = counted in 2024
    A["has_cls"] = A.CAR_AADT.notna() & A.SINGLE_UNIT_AADT.notna() & (A.AADT_CLS > 0)
    A["trk_sh"] = np.where(A.has_cls, (A.SINGLE_UNIT_AADT.fillna(0) + A.COMBINATION_UNIT_AADT.fillna(0)) / A.AADT_CLS, np.nan)
    A["bus_sh"] = np.where(A.has_cls, A.BUS_AADT.fillna(0) / A.AADT_CLS, np.nan)
    ok = A[A.has_cls]
    for c in ["trk_sh", "bus_sh"]:
        avg = ok.groupby("cls").apply(lambda d: (d[c] * d.count_all).sum() / d.count_all.sum()); A[c] = A[c].fillna(A.cls.map(avg))
    A["count_pass"] = A.count_all * (1 - A.trk_sh - A.bus_sh)
    A["fhwa_dev"] = [next(d for lo, hi, d in FHWA_DEV if lo <= c < hi) for c in A.count_all]
    A["vgroup"] = [next(i for i, (lo, hi, _, _) in enumerate(VGROUPS) if lo <= c < hi) for c in A.count_all]
    return A

def audited(A0):
    """The earlier audited station set of the I-695 study (I695_pricing/00_research/resident_validation_station_audit.csv, 1,410 stations
    not dropped; matched to the 2023 network, whose link ids are those of network_2024), with ITS OWN link ids (reverse links and parallel
    roadways as audited) and the MDOT 2024 AAWDT; truck and bus shares as in stations() (own classification, else the class average)."""
    B = pd.read_csv(f"{ROOT}/I695_pricing/00_research/resident_validation_station_audit.csv", dtype={"LOCATION_ID": str})
    B = B[~B.audit.str.startswith("dropped")].copy()
    g = json.load(open(f"{ROOT}/I695_pricing/data/mdot_aadt_statewide_2015-2024.geojson"))
    P = pd.DataFrame([f["properties"] for f in g["features"]]).drop_duplicates("LOCATION_ID").set_index("LOCATION_ID")
    B = B.drop(columns=["ID_PREFIX", "ID_RTE_NO", "F_SYSTEM"]).join(P[["ID_PREFIX", "ID_RTE_NO", "F_SYSTEM", "AAWDT_2024", "AADT_2024", "AADT", "CAR_AADT", "SINGLE_UNIT_AADT", "COMBINATION_UNIT_AADT", "BUS_AADT"]], on="LOCATION_ID")
    B["count_all"] = B.AAWDT_2024.where(B.AAWDT_2024 > 0, B.AADT_2024); B = B[B.count_all > 0].copy()
    B["route"] = (B.ID_PREFIX.fillna("") + " " + B.ID_RTE_NO.astype(str)).str.replace("IS ", "I-").replace({"MD 695": "I-695"}); i695 = B.route.eq("I-695")
    B["cls"] = np.select([B.F_SYSTEM.eq(1) & i695, B.F_SYSTEM.eq(1), B.F_SYSTEM.eq(2), B.F_SYSTEM.eq(3), B.F_SYSTEM.eq(4), B.F_SYSTEM.eq(5)], CLASSES[:6], CLASSES[6])
    hc = B.CAR_AADT.notna() & B.SINGLE_UNIT_AADT.notna() & (B.AADT > 0)
    avg_t = A0[A0.has_cls].groupby("cls").apply(lambda d: (d.trk_sh * d.count_all).sum() / d.count_all.sum()); avg_b = A0[A0.has_cls].groupby("cls").apply(lambda d: (d.bus_sh * d.count_all).sum() / d.count_all.sum())
    B["trk_sh"] = np.where(hc, (B.SINGLE_UNIT_AADT.fillna(0) + B.COMBINATION_UNIT_AADT.fillna(0)) / B.AADT, np.nan); B["trk_sh"] = B.trk_sh.fillna(B.cls.map(avg_t))
    B["bus_sh"] = np.where(hc, B.BUS_AADT.fillna(0) / B.AADT, np.nan); B["bus_sh"] = B.bus_sh.fillna(B.cls.map(avg_b))
    B["count_pass"] = B.count_all * (1 - B.trk_sh - B.bus_sh)
    B["fhwa_dev"] = [next(d for lo, hi, d in FHWA_DEV if lo <= c < hi) for c in B.count_all]
    B["ids"] = B.link_ids.astype(str).str.split(";"); B["in_new_set"] = B.LOCATION_ID.isin(A0.LOCATION_ID)
    return B

def summary(d, m, c):
    if not len(d): return dict(n=0)
    r = d[m] / d[c]
    return dict(n=int(len(d)), count=float(d[c].sum()), model=float(d[m].sum()), ratio=float(d[m].sum() / d[c].sum()), median_ratio=float(r.median()),
                within25=float(r.between(0.75, 1.25).mean()), prmse=float(100 * np.sqrt(((d[m] - d[c]) ** 2).mean()) / d[c].mean()),
                within_fhwa=float(((100 * (d[m] - d[c]).abs() / d[c]) <= d.fhwa_dev).mean()))

def seed_tables(A0, B=None):
    rows = []; R = A0[A0.use == "ramp"]; A = A0[A0.use == "mainline"]
    if B is not None:
        for comp, m, c in [("all vehicles", "m_all", "count_all"), ("passenger vehicles", "m_car", "count_pass")]:
            rows.append(dict(table="audited_set", group="Earlier audited stations (own links)", comparison=comp, **summary(B, m, c)))
            for k in CLASSES: rows.append(dict(table="audited_set", group=k, comparison=comp, **summary(B[B.cls == k], m, c)))
    for comp, m, c in [("all vehicles", "m_all", "count_all"), ("passenger vehicles", "m_car", "count_pass")]:
        rows.append(dict(table="ramps", group="All ramp stations", comparison=comp, **summary(R, m, c)))
        for k in CLASSES:
            if (R.cls == k).sum(): rows.append(dict(table="ramps", group=k, comparison=comp, **summary(R[R.cls == k], m, c)))
    for k in CLASSES + ["All classes"]:
        d = A if k == "All classes" else A[A.cls == k]
        for comp, m, c in [("all vehicles", "m_all", "count_all"), ("passenger vehicles", "m_car", "count_pass")]:
            rows.append(dict(table="facility", group=k, comparison=comp, **summary(d, m, c)))
            if comp == "all vehicles": rows.append(dict(table="facility_counted2024", group=k, comparison=comp, **summary(d[d.counted24], m, c)))
    for i, (lo, hi, acc, pref) in enumerate(VGROUPS):
        d = A[A.vgroup == i]; lab = f"{lo/1e3:.0f}-{hi/1e3:.0f} thousand" if hi < 1e11 else f"over {lo/1e3:.0f} thousand"
        for comp, m, c in [("all vehicles", "m_all", "count_all"), ("passenger vehicles", "m_car", "count_pass")]:
            rows.append(dict(table="volume_group", group=lab, comparison=comp, acceptable=acc, preferable=pref, **summary(d, m, c)))
    for comp, m, c in [("all vehicles", "m_all", "count_all"), ("passenger vehicles", "m_car", "count_pass")]:
        rows.append(dict(table="areawide", group="All stations", comparison=comp, acceptable=AREAWIDE[0], preferable=AREAWIDE[1], **summary(A, m, c)))
        for sp, lab in [("calibration_check", "Check half"), ("held_out", "Held-out half")]:
            rows.append(dict(table="split_half", group=lab, comparison=comp, **summary(A[A.split == sp], m, c)))
    return pd.DataFrame(rows)

def counters(car, bus):
    TG = pd.read_csv(f"{ROOT}/I695_pricing/data/corridor_fit/targets_v7.csv"); TG = TG[(TG.kind == "hourly") & (TG.hour >= 0)].copy()
    TG["lk"] = TG.links.astype(str).str.replace("|", ";").str.split(";")
    M = pd.read_csv(f"{V}/data/count_stations_matched.csv", dtype={"link_NE": str, "link_SW": str})
    l2s = {}
    for r in M.itertuples():
        for l in (r.link_NE, r.link_SW):
            if isinstance(l, str) and pd.notna(r.AADT_2024) and pd.notna(r.AADT_2023) and r.AADT_2023 > 0 and r.MAIN_LINE == 1: l2s.setdefault(l, (r.LOCATION_ID, r.AADT_2024 / r.AADT_2023))
    TG["mdot_station"] = [next((l2s[l][0] for l in lk if l in l2s), None) for lk in TG.lk]
    TG["scale_2024"] = [next((l2s[l][1] for l in lk if l in l2s), 1.0) for lk in TG.lk]
    TG["observed_2023"] = TG.target; TG["observed"] = TG.target * TG.scale_2024
    TG["model"] = [car.reindex(l).fillna(0)[int(h)].sum() + bus.reindex(l).fillna(0)[int(h)].sum() for l, h in zip(TG.lk, TG.hour)]
    return TG

def band(x):
    x = np.asarray(x, float); m = np.nanmean(x); s = np.nanstd(x, ddof=1) if np.isfinite(x).sum() > 1 else 0.0
    return m, s, float(np.nanmin(x)), float(np.nanmax(x))          # spread: smallest to largest run (columns *_p5 / *_p95 hold the min and max)

def main():
    print(f"seeds {SEEDS}, iteration {IT}, runs {RUN_ROOT}")
    A0 = stations(); B0 = audited(A0); per_station = []; T = []; C = []; links_all = {}
    for s in SEEDS:
        car, bus = model_seed(s); A = A0.copy()
        A["m_car"] = [car.reindex(i).fillna(0).values.sum() for i in A.ids]; A["m_bus"] = [bus.reindex(i).fillna(0).values.sum() for i in A.ids]; A["m_all"] = A.m_car + A.m_bus
        B = B0.copy(); B["m_car"] = [car.reindex(i).fillna(0).values.sum() for i in B.ids]; B["m_bus"] = [bus.reindex(i).fillna(0).values.sum() for i in B.ids]; B["m_all"] = B.m_car + B.m_bus
        per_station.append(A[["LOCATION_ID", "m_car", "m_bus", "m_all"]].assign(seed=s)); T.append(seed_tables(A, B).assign(seed=s))
        tg = counters(car, bus); C.append(tg.assign(seed=s))
        links_all[s] = pd.DataFrame({"car": car.sum(1), "bus": bus.sum(1)})
        ML = A[A.use == "mainline"]; print(f"seed {s}: mainline stations {len(ML)}: all-vehicle model/count {ML.m_all.sum() / ML.count_all.sum():.3f}, passenger {ML.m_car.sum() / ML.count_pass.sum():.3f}, bus share {ML.m_bus.sum() / ML.m_all.sum():.2%}")
    PS = pd.concat(per_station); T = pd.concat(T); C = pd.concat(C)
    # ---- per station: seed mean, s.d., 90 % band
    g = PS.groupby("LOCATION_ID")
    St = A0.drop(columns=["ids"]).set_index("LOCATION_ID").join(pd.DataFrame({
        "model_all_mean": g.m_all.mean(), "model_all_sd": g.m_all.std(ddof=1), "model_car_mean": g.m_car.mean(), "model_car_sd": g.m_car.std(ddof=1), "model_bus_mean": g.m_bus.mean()}))
    St["model_all_p5"] = g.m_all.min(); St["model_all_p95"] = g.m_all.max()
    St["ratio_all"] = St.model_all_mean / St.count_all; St["ratio_pass"] = St.model_car_mean / St.count_pass
    St["within_fhwa"] = (100 * (St.model_all_mean - St.count_all).abs() / St.count_all) <= St.fhwa_dev
    St.reset_index().to_csv(f"{DATA}/stations_model_vs_count.csv", index=False, float_format="%.4g")
    PS.to_csv(f"{DATA}/stations_by_seed.csv.gz", index=False, float_format="%.1f", compression="gzip")
    T.to_csv(f"{DATA}/tables_by_seed.csv", index=False, float_format="%.5g")
    # ---- tables over seeds
    key = ["table", "group", "comparison"]; agg = []
    for k, d in T.groupby(key, sort=False):
        rec = dict(zip(key, k)); rec["n"] = int(d.n.iloc[0]); rec["count"] = float(d["count"].iloc[0]) if "count" in d and d.n.iloc[0] else np.nan
        for c in ["acceptable", "preferable"]:
            if c in d and d[c].notna().any(): rec[c] = float(d[c].iloc[0])
        for c in ["ratio", "prmse", "median_ratio", "within25", "within_fhwa", "model"]:
            if c in d and d.n.iloc[0]: m, s, lo, hi = band(d[c]); rec.update({f"{c}_mean": m, f"{c}_sd": s, f"{c}_p5": lo, f"{c}_p95": hi, f"{c}_min": float(d[c].min()), f"{c}_max": float(d[c].max())})
        if rec["table"] in ("facility",) and FAC.get(rec["group"]): rec["band_acceptable"], rec["band_preferable"] = BAND[FAC[rec["group"]]]
        agg.append(rec)
    TS = pd.DataFrame(agg); TS.to_csv(f"{DATA}/tables_over_seeds.csv", index=False, float_format="%.5g")
    # ---- hourly counters: GEH per seed and on the seed mean
    C["geh"] = geh(C.model, C.observed); C["geh_2023"] = geh(C.model, C.observed_2023)
    Cm = C.groupby(["station", "grp", "hour"]).agg(observed=("observed", "first"), observed_2023=("observed_2023", "first"), scale_2024=("scale_2024", "first"), mdot_station=("mdot_station", "first"),
                                                   model_mean=("model", "mean"), model_sd=("model", "std"), model_lo=("model", "min"), model_hi=("model", "max")).reset_index()
    Cm["model_p5"] = Cm.pop("model_lo"); Cm["model_p95"] = Cm.pop("model_hi"); Cm["geh_mean_model"] = geh(Cm.model_mean, Cm.observed)
    Cm.to_csv(f"{DATA}/counters_hourly.csv", index=False, float_format="%.4g")
    crow = []
    for grp, lab in [("i695_ctr", "Baltimore Beltway (I-695)"), ("reg_ctr", "Other freeways"), (None, "All counters")]:
        for p, hs in PERIODS:
            d = C[(C.grp == grp) if grp else C.index == C.index]; d = d[d.hour.isin(list(hs))]
            per = d.groupby("seed").apply(lambda x: pd.Series({"ratio": x.model.sum() / x.observed.sum(), "geh5": (x.geh < 5).mean(), "geh5_2023": (x.geh_2023 < 5).mean()}))
            rec = dict(group=lab, period=p, stations=int(d.station.str.split("_").str[0].nunique()), directions=int(d.station.nunique()), hours=int(len(d) / max(1, len(SEEDS))))
            for c in per.columns: m, s, lo, hi = band(per[c]); rec.update({f"{c}_mean": m, f"{c}_sd": s, f"{c}_p5": lo, f"{c}_p95": hi})
            crow.append(rec)
    CT = pd.DataFrame(crow); CT.to_csv(f"{DATA}/counters_summary.csv", index=False, float_format="%.4g")
    # ---- links (seed mean) and convergence
    L = pd.concat({s: d for s, d in links_all.items()}, names=["seed", "link"]).groupby("link").mean(); L.to_csv(f"{DATA}/link_daily_volume_mean.csv.gz", compression="gzip", float_format="%.1f")
    conv = []
    for s in SEEDS:
        d = f"{RUN_ROOT}/2024_s{s}"
        sc = pd.read_csv(f"{d}/scorestats.csv", sep=";"); sc.columns = [c.strip().lower() for c in sc.columns]
        ph = pd.read_csv(f"{d}/ph_modestats.csv", sep=";"); ph.columns = [c.strip().lower() for c in ph.columns]
        tdist = pd.read_csv(f"{d}/traveldistancestats.csv", sep=";"); tdist.columns = [c.strip().lower() for c in tdist.columns]
        x = sc.merge(ph, on="iteration", how="left", suffixes=("", "_ph")).merge(tdist, on="iteration", how="left", suffixes=("", "_dist")); x["seed"] = s; conv.append(x)
    CV = pd.concat(conv); CV.to_csv(f"{DATA}/convergence_by_iteration.csv", index=False, float_format="%.5g")
    json.dump({"seeds": SEEDS, "iteration": IT, "n_stations": int(len(A0)), "use": A0.use.value_counts().to_dict(), "audited_set": int(len(B0)), "audited_in_new_set": int(B0.in_new_set.sum()),
               "audited_in_new_mainline": int(B0.LOCATION_ID.isin(A0[A0.use == "mainline"].LOCATION_ID).sum()), "n_classified": int(A0.has_cls.sum()),
               "counters_scaled_to_2024": int(Cm.drop_duplicates("station").scale_2024.ne(1.0).sum()), "n_counter_directions": int(Cm.station.nunique())},
              open(f"{DATA}/meta.json", "w"), indent=1)
    figures(St, TS, Cm, CV)
    pr = TS[(TS.table == "facility")]
    for r in pr.itertuples(): print(f"{r.group:28s} {r.comparison:18s} n={r.n:4d} model/count {r.ratio_mean:.3f} ({r.ratio_p5:.3f}-{r.ratio_p95:.3f})  %RMSE {r.prmse_mean:.1f}")
    print(CT[CT.period == "Whole day"].to_string())

# ------------------------------------------------------------------------------------------------ figures
def figures(St, TS, Cm, CV):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    out_col = ps.VARIANT   # outside tolerance = orange
    St = St[St.use == "mainline"]
    # 1. scatter model vs count (all vehicles), seed mean with 90 % band; outside the FHWA desirable deviation in orange
    fig, axs = ps.figure(3.0, ncols=2)
    for ax, (m, c, lo_, hi_, ttl) in zip(axs, [("model_all_mean", "count_all", "model_all_p5", "model_all_p95", "All vehicles"), ("model_car_mean", "count_pass", None, None, "Passenger vehicles")]):
        x = St[c].values / 1e3; y = St[m].values / 1e3
        dev = 100 * np.abs(St[m] - St[c]) / St[c]; inside = (dev <= St.fhwa_dev).values
        if lo_:
            ax.vlines(x, St[lo_].clip(lower=0).values / 1e3, St[hi_].values / 1e3, color=ps.SEED_BAND, lw=0.6, zorder=1)
        ax.scatter(x[inside], y[inside], s=3, color=ps.MODEL, lw=0, zorder=2); ax.scatter(x[~inside], y[~inside], s=3, color=out_col, lw=0, zorder=2)
        hi = max(x.max(), y.max()) * 1.05; ax.plot([0, hi], [0, hi], color=ps.OBSERVED, lw=0.8, zorder=3); ax.set_xlim(0, hi); ax.set_ylim(0, hi)
        ax.set_xlabel("Observed (thousand vehicles per day)"); ax.set_ylabel("Model (thousand vehicles per day)"); ax.set_title(ttl, loc="right", fontsize=ps.FONT, fontweight="normal")
    axs[0].legend(handles=[Line2D([], [], marker="o", ls="", color=ps.MODEL, ms=3, label="Model, within tolerance"), Line2D([], [], marker="o", ls="", color=out_col, ms=3, label=ps.LEG["outside"]),
                           Line2D([], [], color=ps.SEED_BAND, lw=2, label="Range of the runs"), Line2D([], [], color=ps.OBSERVED, lw=0.8, label="Model = observed")], loc="upper left", fontsize=ps.TICK)
    ps.finish(fig, f"{FIG}/fig_counts_scatter", panel_labels="ab")
    # 2. model/count by facility class (all and passenger), seed mean with 90 % band; tolerance band grey; outside orange
    F = TS[TS.table == "facility"]; groups = CLASSES + ["All classes"]
    fig, ax = ps.figure(3.0); w = 0.38; xx = np.arange(len(groups))
    for j, (comp, lab, off) in enumerate([("all vehicles", "All vehicles", -w / 2), ("passenger vehicles", "Passenger vehicles", w / 2)]):
        d = F[F.comparison == comp].set_index("group").reindex(groups)
        for i, g_ in enumerate(groups):
            b = BAND.get(FAC.get(g_), (0.15, 0.10))[0]
            if j == 0: ax.add_patch(plt.Rectangle((i - 0.45, 1 - b), 0.9, 2 * b, color=ps.TOL_BAND, lw=0, zorder=0))
            r = d.loc[g_]; col = ps.MODEL if abs(r.ratio_mean - 1) <= b else out_col
            ax.bar(i + off, r.ratio_mean, w * 0.9, color=col if j == 0 else "white", edgecolor=col, hatch=None if j == 0 else "////", lw=0.8, zorder=2)
            ax.errorbar(i + off, r.ratio_mean, yerr=[[r.ratio_mean - r.ratio_p5], [r.ratio_p95 - r.ratio_mean]], color=ps.INK2, lw=0.8, capsize=1.5, zorder=3)
    ax.axhline(1, color=ps.OBSERVED, lw=0.8, zorder=1); ax.set_xticks(xx); ax.set_xticklabels(["Interstate\nI-695", "Other\ninterstate", "Other\nfreeway", "Principal\narterial", "Minor\narterial", "Major\ncollector", "Minor\ncollector,\nlocal", "All\nclasses"], fontsize=ps.TICK)
    ax.set_ylabel(ps.RATIO_LABEL); ax.set_ylim(0, max(1.4, F.ratio_p95.max() * 1.1))
    ax.legend(handles=[Patch(facecolor=ps.INK2, edgecolor=ps.INK2, label="All vehicles (solid)"), Patch(facecolor="white", edgecolor=ps.INK2, hatch="////", label="Passenger vehicles (hatched)"),
                       Patch(color=ps.MODEL, label="Within tolerance"), Patch(color=out_col, label=ps.LEG["outside"]),
                       Patch(color=ps.TOL_BAND, label=ps.LEG["tol"]), Line2D([], [], color=ps.INK2, lw=0.8, label="Range of the runs")], ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.36), fontsize=ps.TICK)
    ps.finish(fig, f"{FIG}/fig_counts_by_facility")
    # 3. %RMSE by volume group against the FDOT acceptable value
    G = TS[(TS.table == "volume_group") & (TS.comparison == "all vehicles")].reset_index(drop=True)
    fig, ax = ps.figure(2.6); xx = np.arange(len(G))
    cols = [ps.MODEL if r.prmse_mean <= r.acceptable else out_col for r in G.itertuples()]
    ax.bar(xx, G.prmse_mean, 0.6, color=cols, zorder=2)
    ax.errorbar(xx, G.prmse_mean, yerr=[G.prmse_mean - G.prmse_p5, G.prmse_p95 - G.prmse_mean], color=ps.INK2, lw=0.8, capsize=2, ls="", zorder=3)
    ax.scatter(xx, G.acceptable, marker="_", s=250, color=ps.OBSERVED, zorder=4, lw=1.4)
    ax.set_xticks(xx); ax.set_xticklabels([f"{g_}\nn = {n}" for g_, n in zip(G.group.str.replace(" thousand", "").str.replace("over ", "> "), G.n)], fontsize=ps.TICK)
    ax.set_xlabel("Observed weekday volume (thousand vehicles)"); ax.set_ylabel("Root mean square error\n(% of the mean count)")
    ax.set_ylim(0, max(G.prmse_p95.max(), G.acceptable.max()) * 1.12)
    ax.legend(handles=[Patch(color=ps.MODEL, label="Model, within the standard"), Patch(color=out_col, label=ps.LEG["outside"]), Line2D([], [], color=ps.OBSERVED, lw=1.4, label="Acceptable maximum"),
                       Line2D([], [], color=ps.INK2, lw=0.8, label="Range of the runs")], ncol=2, loc="upper right", fontsize=ps.TICK)
    ps.finish(fig, f"{FIG}/fig_rmse_by_volume")
    # 4. hourly counters: 24-h profiles, observed grey, model blue with 90 % band; hours with GEH >= 5 in orange
    sts = list(dict.fromkeys(Cm.sort_values(["grp", "station"]).station)); n = len(sts); nc = 4; nr = int(np.ceil(n / nc))
    fig, axs = ps.figure(min(ps.MAX_HEIGHT, 1.05 * nr + 0.5), nrows=nr, ncols=nc, sharex=True); axs = np.atleast_1d(axs).ravel()
    names = pd.read_csv(f"{ROOT}/I695_pricing/data/corridor_fit/targets_v7.csv").drop_duplicates("station").set_index("station")
    for ax, s_ in zip(axs, sts):
        d = Cm[Cm.station == s_].sort_values("hour")
        ax.fill_between(d.hour, d.model_p5.clip(lower=0) / 1e3, d.model_p95 / 1e3, color=ps.SEED_BAND, lw=0)
        ax.plot(d.hour, d.observed / 1e3, color=ps.OBSERVED, lw=1.0); ax.plot(d.hour, d.model_mean / 1e3, color=ps.MODEL, lw=1.0)
        bad = d[d.geh_mean_model >= 5]; ax.scatter(bad.hour, bad.model_mean / 1e3, s=4, color=out_col, zorder=3, lw=0)
        num = s_.split("_")[0][1:].lstrip("0"); road = {"76": "I-83", "52": "I-83", "71": "I-95", "51": "I-95", "39": "I-95", "53": "I-70", "25": "MD 295"}.get(num, "I-695")
        dirn = {"N": "northbound", "S": "southbound", "E": "eastbound", "W": "westbound"}.get(s_.split("_")[1], "")
        ax.set_title(f"{road}, site {num}\n{dirn}", fontsize=ps.TICK, fontweight="normal", loc="left"); ax.set_xticks([0, 6, 12, 18, 24]); ax.set_xlim(0, 23)
        ax.grid(True)
    for ax in axs[n:]: ax.set_visible(False)
    fig.supxlabel("Hour of the day", fontsize=ps.FONT); fig.supylabel("Vehicles per hour (thousand)", fontsize=ps.FONT)
    fig.legend(handles=[Line2D([], [], color=ps.OBSERVED, label=ps.LEG["observed"]), Line2D([], [], color=ps.MODEL, label=ps.LEG["model"]), Patch(color=ps.SEED_BAND, label="Range of the runs"),
                        Line2D([], [], marker="o", ls="", color=out_col, ms=3, label="Hourly difference too large")], ncol=4, loc="outside upper center", fontsize=ps.TICK)
    ps.finish(fig, f"{FIG}/fig_counters_hourly")
    # 5. convergence: average executed score and car person-hours by iteration, mean over seeds with 90 % band
    fig, axs = ps.figure(2.4, ncols=2)
    scol = "avg_executed"
    for ax, (c, lab, f) in zip(axs, [(scol, "Average score of the executed plans (–)", 1.0), ("car_travel", "Car travel time of all residents\n(thousand hours per weekday)", EXP * 1e-3)]):
        if c not in CV: continue
        g_ = CV.groupby("iteration")[c]; m = g_.mean() * f; lo, hi = g_.min() * f, g_.max() * f
        ax.fill_between(m.index, lo, hi, color=ps.MODEL, alpha=0.35, lw=0); ax.plot(m.index, m, color=ps.MODEL, lw=1.0)
        ax.axvline(90, color=ps.INK2, lw=0.7, ls="--"); ax.text(89, ax.get_ylim()[0], "innovation off ", ha="right", va="bottom", fontsize=ps.TICK, color=ps.INK2)
        ax.set_xlabel("Iteration"); ax.set_ylabel(lab)
    axs[0].legend(handles=[Line2D([], [], color=ps.MODEL, label="Mean over the seeds"), Patch(color=ps.MODEL, alpha=0.35, label="Range of the runs")], loc="lower right", fontsize=ps.TICK)
    ps.finish(fig, f"{FIG}/fig_convergence", panel_labels="ab")

if __name__ == "__main__": main()
