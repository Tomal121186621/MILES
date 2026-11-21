#!/usr/bin/env python3
"""Activity and commute measures of the model runs and of the observed surveys, computed by one function so that every
comparison uses the same definitions (t24common).

    python3 activity/lib/reporting_2024/measures.py [--settings base,acs2024,silo2024] [--force]   -> temporal_2024/data/measures/<setting>_s<NN>.pkl,
                                                                          temporal_2024/data/measures/obs_<source>.pkl

Persons and weights
  model acs2024   persons of pop_acs2024 (every copy weight 1), age and occupation as given to MAST
  model silo2024  persons of the 5 % sample of the SILO 2024 microdata (weight 1), home county from the home zone
  model base      the RTS survey households of both halves (survey_population.py), person weight w (imputed members: the
                  household weight), the two half runs of one seed pooled
  observed RTS    the same persons and their survey trips (obs_surveys.py)
  observed NHTS   Baltimore CBSA weekday persons 5+ (obs_surveys.py)
  observed ATUS   weekday diaries of persons 15+ (bench_atus.py), pools Maryland and DC + Maryland + Virginia, two periods
Areas: Maryland (home county 24xxx), Baltimore region (six BMC jurisdictions), Baltimore CBSA (BMC + Queen Anne's).
Age floors: 5 (all-person rates, as the Roorda-style tables), 15 (comparison with ATUS), workers 16+ (comparison with ACS).
"""
import argparse, os, pickle, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import t24common as C

MD = f"{C.OUT}/measures"; os.makedirs(MD, exist_ok=True)
RUN = f"{C.T24}/run"; SCEN = os.environ.get("T24_SILO", "oos_s1_pass3")
AREAS = {"Maryland": lambda c: c // 1000 == 24, "Baltimore region": lambda c: np.isin(c, C.BALTIMORE), "Baltimore CBSA": lambda c: np.isin(c, C.BALT_CBSA)}
AGE_FLOORS = [5, 15]


def measure(P, A, with_commute=True, with_flows=False):
    """P: pid, w, age, occ, county; A: pid, type, start_min, dur, dep, o_home, mode, tt, km (zone).  Returns tidy tables."""
    S, H, F = [], [], []
    zc = C.zone_county() if with_flows else None; cg = C.county_group() if with_flows else None
    for area, fa in AREAS.items():
        Pa = P[fa(P.county.values)]
        if len(Pa) == 0: continue
        for amin in AGE_FLOORS:
            p = Pa[Pa.age >= amin]; a = A[A.pid.isin(p.pid.values)].copy(); wmap = p.set_index("pid").w; a["w"] = a.pid.map(wmap).values
            W = p.w.sum(); key = f"{area}|{amin}+"
            S.append(dict(key=key, metric="persons", type="ALL", value=len(p))); S.append(dict(key=key, metric="persons_weighted", type="ALL", value=W))
            for t in C.TYPES + ["ALL"]:
                at = a if t == "ALL" else a[a.type == t]
                S.append(dict(key=key, metric="acts_per_person", type=t, value=at.w.sum() / W))
                S.append(dict(key=key, metric="participation", type=t, value=p.w[p.pid.isin(at.pid.unique())].sum() / W))
                km = at[np.isfinite(at.km)]
                if len(km): S.append(dict(key=key, metric="mean_km", type=t, value=float(np.average(km.km, weights=km.w))))
                if len(at):
                    hs = C.hourly_shares(at.start_min, at.w); d = at[(at.dur >= 1) & (at.dur <= 1439)]
                    hd = C.hourly_mean(d.start_min, d.dur, d.w); hn = pd.Series((d.start_min // 60).astype(int) % 24).value_counts().reindex(range(24), fill_value=0)
                    for h in range(24): H.append(dict(key=key, metric="start_share", type=t, hour=h, value=hs[h])); H.append(dict(key=key, metric="dur_mean", type=t, hour=h, value=hd[h]))
                    for h in range(24): H.append(dict(key=key, metric="dur_n", type=t, hour=h, value=hn[h]))
                    if len(d): S.append(dict(key=key, metric="mean_dur", type=t, value=float(np.average(d.dur, weights=d.w))))
            # trips per complete home-based chain
            if "o_home" in a:
                a = a.sort_values(["pid", "dep"], kind="stable"); a["chain"] = C.chain_ids(a.pid.values, a.o_home.values)
                g = a.groupby("chain").agg(n=("type", "size"), first_home=("o_home", "first"), last=("type", "last"), w=("w", "first"))
                g = g[g.first_home & (g["last"] == "HOME")]
                if len(g):
                    k = g.n.clip(upper=8); s = g.w.groupby(k).sum().reindex(range(1, 9), fill_value=0.0); s /= s.sum()
                    for i in range(1, 9): H.append(dict(key=key, metric="chain_share", type="ALL", hour=i, value=s[i]))
                    S.append(dict(key=key, metric="trips_per_chain", type="ALL", value=float(np.average(g.n, weights=g.w))))
        if not with_commute: continue
        # workers 16+: work activity on the day, commute
        key = f"{area}|workers"; wk = Pa[(Pa.occ == 1) & (Pa.age >= 16)]; a = A[A.pid.isin(wk.pid.values)]
        S.append(dict(key=key, metric="workers", type="ALL", value=len(wk)))
        S.append(dict(key=key, metric="work_share", type="WORK", value=wk.w[wk.pid.isin(a.pid[a.type == "WORK"].unique())].sum() / wk.w.sum()))
        cm = C.commute_from_acts(a); cm["w"] = cm.pid.map(wk.set_index("pid").w).values
        if len(cm) == 0: continue
        S.append(dict(key=key, metric="commute_dep_mean", type="WORK", value=float(np.average(cm.dep, weights=cm.w))))
        S.append(dict(key=key, metric="commute_dep_6_9", type="WORK", value=C.wshare((cm.dep >= 360) & (cm.dep < 540), cm.w)))
        S.append(dict(key=key, metric="commute_tt_mean", type="WORK", value=float(np.average(cm.tt, weights=cm.w))))
        o = np.argsort(cm.tt.values); cw = np.cumsum(cm.w.values[o]) / cm.w.sum()
        S.append(dict(key=key, metric="commute_tt_median", type="WORK", value=float(cm.tt.values[o][np.searchsorted(cw, 0.5)])))
        S.append(dict(key=key, metric="commute_direct_share", type="WORK", value=C.wshare(cm.n_trips == 1, cm.w)))
        hs = C.hourly_shares(cm.dep, cm.w)
        for h in range(24): H.append(dict(key=key, metric="commute_dep_share", type="WORK", hour=h, value=hs[h]))
        b = pd.cut(cm.tt, C.TT_BINS, right=False, labels=C.TT_LABELS); ts = cm.w.groupby(b, observed=False).sum() / cm.w.sum()
        for i, l in enumerate(C.TT_LABELS): H.append(dict(key=key, metric="commute_tt_share", type=l, hour=i, value=ts[l]))
        ms = cm.w.groupby(cm["mode"].map(C.MODEL_MODE).fillna(cm["mode"])).sum() / cm.w.sum()
        for m in C.COMMUTE_MODES: S.append(dict(key=key, metric="commute_mode", type=m, value=float(ms.get(m, 0.0))))
        if with_flows and "zone" in A:
            fw = a[a.type == "WORK"].drop_duplicates("pid").set_index("pid").zone
            hu = wk.set_index("pid").county.map(cg.unit); wu = fw.map(zc).map(cg.unit)
            df = pd.DataFrame({"home_unit": hu.reindex(fw.index).values, "work_unit": wu.values, "w": wk.set_index("pid").w.reindex(fw.index).values})
            for (h_, w_), v in df.groupby(["home_unit", "work_unit"]).w.sum().items(): F.append(dict(key=key, home_unit=h_, work_unit=w_, value=v))
    return pd.DataFrame(S), pd.DataFrame(H), pd.DataFrame(F)


# ------------------------------------------------------------------------------------------------ populations
def persons(setting):
    setting = setting.replace("_tw", "")          # the telework-input variant runs on the same population
    f = f"{MD}/persons_{setting}.parquet" if (setting != "silo2024" or SCEN == "oos_s1_pass3") else f"{MD}/persons_{setting}_{SCEN}.parquet"   # the SILO population of the scenario
    if os.path.exists(f): return pd.read_parquet(f)
    if setting == "acs2024":
        pm = pd.read_csv(f"{C.T24}/pop_acs2024/persons_map.csv")
        P = pd.DataFrame({"pid": pm.id, "w": 1.0, "age": pm.AGEP, "occ": pm.occ, "county": pm.county.astype(int)})
    elif setting == "silo2024":
        r = pd.read_parquet(f"{RUN}/{C.PFX}silo2024_s01/output/persons.parquet")
        sd = f"{C.V}/2_silo/run/base/scenOutput/{SCEN}/microData/futureYears"
        pp = pd.read_csv(f"{sd}/pp_2024.csv", usecols=["id", "hhid", "age", "occupation"], engine="pyarrow"); pp = pp[pp.id.isin(r.person_id)]
        hz = r.dropna(subset=["home_zone"]).groupby("household_id").home_zone.first()
        P = pd.DataFrame({"pid": pp.id.values, "w": 1.0, "age": pp.age.values, "occ": pp.occupation.values})
        P["county"] = pp.hhid.map(hz).map(C.zone_county()).fillna(-1).astype(int).values
    elif setting in ("base", "rts"):
        pm = pd.read_parquet(f"{C.OUT}/rts_persons.parquet"); off = np.where(pm.half == "validation", 100_000_000, 0)
        P = pd.DataFrame({"pid": pm.id.values + off, "w": pm.w.values, "age": pm.age.values, "occ": pm.occ.values, "county": pm.county.astype(int).values,
                          "survey_pid": pm.person_id.values, "imputed": pm.imputed.values})
    P.to_parquet(f, index=False); return P


def model_acts(setting, seed):
    if setting.startswith("base"):
        parts = []
        for h, off in [("est", 0), ("val", 100_000_000)]:
            a = C.acts_from_legs(pd.read_parquet(f"{RUN}/{C.PFX}{setting}_{h}_s{seed:02d}/output/legs.parquet")); a["pid"] += off; parts.append(a)
        return pd.concat(parts, ignore_index=True)
    return C.acts_from_legs(pd.read_parquet(f"{RUN}/{C.PFX}{setting}_s{seed:02d}/output/legs.parquet"))


def done(setting, seed):
    return all(os.path.exists(f"{RUN}/{C.PFX}{setting}_{h}_s{seed:02d}/output/legs.parquet") for h in ["est", "val"]) if setting.startswith("base") else \
        os.path.exists(f"{RUN}/{C.PFX}{setting}_s{seed:02d}/output/legs.parquet")


def observed():
    out = {}
    P = persons("rts"); pm = pd.read_parquet(f"{C.OUT}/rts_persons.parquet")
    a = pd.read_parquet(f"{C.OUT}/rts_acts.parquet"); m = pd.Series(P.pid.values, index=P.survey_pid.values); m = m[~m.index.duplicated()]
    a["pid"] = a.pid.map(m); a = a.dropna(subset=["pid"]); a["pid"] = a.pid.astype(np.int64)
    out["rts"] = measure(P, a)
    wk = pm[(pm.occ == 1) & (pm.age >= 16) & pm.wfh_known & (pm.county // 1000 == 24)]
    out["rts_usual_wfh"] = C.wshare(wk.usual_wfh, wk.w)
    p = pd.read_parquet(f"{C.OUT}/nhts_persons.parquet"); b = pd.read_parquet(f"{C.OUT}/nhts_acts.parquet")
    P2 = pd.DataFrame({"pid": p.pid, "w": p.WTPERFIN, "age": p.R_AGE, "occ": np.where(p.WORKER == 1, 1, 2), "county": 24510})   # CBSA: all areas = Baltimore
    out["nhts"] = measure(P2, b, with_commute=False)
    r = pd.read_parquet(f"{C.OUT}/atus_persons.parquet"); g = pd.read_parquet(f"{C.OUT}/atus_acts.parquet")
    for pool, st in [("md", [24]), ("dmv", [11, 24, 51])]:
        for per in ["2017-2019", "2021-2024"]:
            q = r[r.GESTFIPS.isin(st) & (r.period == per)]
            P3 = pd.DataFrame({"pid": q.TUCASEID, "w": q.TUFNWGTP, "age": q.TEAGE, "occ": np.where(q.employed, 1, 2), "county": 24001})
            A3 = pd.DataFrame({"pid": g.cid, "type": g.type, "start_min": g.start_min, "dur": g.dur, "dep": g.dep, "mode": g["mode"], "tt": g.trip_tt, "km": np.nan})
            A3 = A3[A3.pid.isin(P3.pid)]
            out[f"atus_{pool}_{per}"] = measure(P3, A3, with_commute=False)
            e = q[q.employed]; c = e[e.tt.notna()]
            out[f"atus_{pool}_{per}_commute"] = dict(n_employed=len(e), work_share=C.wshare(e.work_away, e.TUFNWGTP), n_commutes=len(c),
                                                     dep_mean=float(np.average(c.dep, weights=c.TUFNWGTP)), tt_mean=float(np.average(c.tt, weights=c.TUFNWGTP)),
                                                     dep_hourly=C.hourly_shares(c.dep, c.TUFNWGTP).values)
    pickle.dump(out, open(f"{MD}/obs.pkl", "wb")); return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--settings", default="base,acs2024,silo2024,base_tw,acs2024_tw,silo2024_tw"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--obs", action="store_true"); a = ap.parse_args()
    if a.obs or not os.path.exists(f"{MD}/obs.pkl"): observed(); print("observed measures written")
    for s in a.settings.split(","):
        for seed in range(1, 11):
            f = f"{MD}/{C.PFX}{s}_s{seed:02d}.pkl"
            if (os.path.exists(f) and not a.force) or not done(s, seed): continue
            P = persons(s); A = model_acts(s, seed)
            pickle.dump(measure(P, A, with_flows=True), open(f, "wb")); print(f"{s} seed {seed}: measures written", flush=True)
