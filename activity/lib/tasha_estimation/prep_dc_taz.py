#!/usr/bin/env python3
"""Discretionary destination records located by the survey's traffic zones (TAZ variant, 2026-10-28; robustness check, not the
model of record).

    python3 activity/lib/tasha_estimation/prep_dc_taz.py      -> tasha_estimation/work/dc_rec_<half>_taz.parquet   one row per record (chooser attributes as
                                                                                      prep_dc_data, male recoded, modal anchors)
                                   tasha_estimation/work/dc_cand_<half>_taz.parquet  rec, zidx, b   (destination mixture weights)
                                   tasha_estimation/work/dc_cfg_<half>_taz.parquet   rec, home_idx, anchor_b, w (anchor configurations)
                                   tasha_estimation/results/dc_taz_counts.csv, dc_taz_sources.csv

Records: the same definitions as destination_choice/prep_dc_data.build (primaries of home-based tours and their intermediate
stops, purposes SHOPPING, RECREATION, ACCOMPANY, OTHER; chooser attributes of the survey population).  Only the locations change.
Locations (each trip end separately; the record rule of 2_silo/jobchoice/rts_11_data_v2.py, TAZ_CROSSWALK.md):
  BMC native TAZ10 (1..1387) -> data/taz_bmc_to_mstm.csv; else a valid TPB TAZ -> data/taz_tpb_to_mstm.csv; else a BMC COG-copy
  TAZ (1400..2934) -> BMC; else the 2010 tract split over zones by housing units (home ends; Maryland 2010 PL H1 blocks) or LODES
  2017 jobs (activity ends) (2_silo/jobchoice/work_rts/tract_split_*.parquet, read only); else the zone of the tract internal point.
  Weights: home ends (household home; a trip origin whose activity is home) weight_home (housing units); activity ends
  (shopping, recreation, other, accompany destinations, the primary destination as stop anchor, non-home stop origins)
  weight_work (LODES jobs).  The crosswalks carry no school weights, so accompany uses the job weights.
  Weights are normalised, shares < 1 % dropped, at most 4 zones kept, re-normalised (as rts_11_data_v2).  No zone is excluded
  (every zone is an alternative of the destination MNL).
Anchors: primary  origin = home (household home TAZ, housing-unit weights);
         stop     a = origin TAZ of the trip to the stop (home weights if the origin activity is home, else job weights);
                  b = the primary destination (outbound, job weights) or home (inbound, housing-unit weights).
  Anchor configurations (a, b) with weight w_a w_b; configurations below 1 % dropped, at most 4 kept, re-normalised.
Likelihood (estimate_dc_taz.py): L_n = sum_k w_nk sum_z b_nz P(z | anchors k) -- the location mixture of the workplace model.
Gender: survey_pop pp.csv carries the SILO code (1 male, 2 female) since its rebuild of 2026-10-27; male = (gender == 1).
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; A3 = os.path.dirname(HERE)
sys.path.insert(0, CODE); sys.path.insert(0, f"{ORIOLE_HOME}/activity/lib"); sys.path.insert(0, f"{ORIOLE_HOME}/activity/lib/destination_choice"); sys.path.insert(0, f"{ORIOLE_HOME}/activity/survey")
import dc_common as C                                              # noqa: E402
from rts_common import RTS, V, ACT_PURPOSE, MI_KM, load_split, load_tours   # noqa: E402
from survey_population import tract_zone, geoid                    # noqa: E402
from prep_dc_data import people, chooser_cols, tod_cls             # noqa: E402

WORK = f"{HERE}/work"; RES = f"{HERE}/results"
JW = f"{V}/2_silo/jobchoice/work_rts"
MAXZ, MINW = 4, 0.01
GENDER_RECODE = {1: 2, 2: 1}         # GENDER_CODING_AUDIT.md, fix 1: RTS code -> SILO code (1 male, 2 female)


def norm(d):
    if not d: return None
    tot = sum(d.values()); d = {z: v / tot for z, v in d.items() if v > 0}
    d = {z: v for z, v in d.items() if v >= MINW}; d = dict(sorted(d.items(), key=lambda kv: -kv[1])[:MAXZ]); tot = sum(d.values())
    return {z: v / tot for z, v in d.items()} if tot > 0 else None


class Locator:
    """zone-index distributions {zidx: weight} of a trip end from (bmc taz, tpb taz, tract geoid, side 'home' / 'work')."""
    def __init__(self):
        xb = pd.read_csv(f"{V}/data/taz_bmc_to_mstm.csv"); xt = pd.read_csv(f"{V}/data/taz_tpb_to_mstm.csv")
        TH = pd.read_parquet(f"{JW}/tract_split_home.parquet"); TW = pd.read_parquet(f"{JW}/tract_split_work.parquet")
        lk = lambda X, col, key: {k: dict(zip(g.zone, g[col])) for k, g in X[X[col] > 0].groupby(key)}
        self.L = {("bmc", "home"): lk(xb, "weight_home", "taz"), ("tpb", "home"): lk(xt, "weight_home", "taz"),
                  ("bmc", "work"): lk(xb, "weight_work", "taz"), ("tpb", "work"): lk(xt, "weight_work", "taz"),
                  ("tract", "home"): lk(TH, "n", "geoid"), ("tract", "work"): lk(TW, "n", "geoid")}
        self.bmc, self.tpb = set(xb.taz), set(xt.taz)
        self.tz = tract_zone().set_index("geoid").zone; self.m = C.id2idx(); self.cache = {}

    def pick(self, b, t):
        if b in self.bmc and b <= 1387: return "bmc", b
        if t in self.tpb: return "tpb", t
        if b in self.bmc: return "bmc", b
        return "tract", -1

    def __call__(self, b, t, g, side):
        key = (int(b), int(t), g, side)
        if key in self.cache: return self.cache[key]
        s, taz = self.pick(int(b), int(t)); d, how = None, s
        if s != "tract": d = self.L[(s, side)].get(int(taz))
        if d is None:
            d = self.L[("tract", side)].get(g); how = "tract split"
            if d is None:
                z0 = self.tz.get(g, -1); d = {int(z0): 1.0} if z0 > 0 else None; how = "tract point"
        if d is not None:
            d = {int(self.m[z]): v for z, v in d.items() if z < len(self.m) and self.m[z] >= 0}
        d = norm(d)
        out = (d, how if d else "none"); self.cache[key] = out
        return out


def modal(d): return max(d, key=d.get) if d else -1


def build(half, LOC):
    s = load_split(); tz = tract_zone().set_index("geoid"); m = C.id2idx(); P = people(half)
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", low_memory=False,
                    usecols=["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "d_tract_fips", "o_tract_fips", "travel_mode", "distance",
                             "dep_min", "arr_min", "wttrdfin", "o_tpb_taz", "o_bmc_taz", "d_tpb_taz", "d_bmc_taz", "home_tpb_taz", "home_bmc_taz"])
    t = t[t.household_id.map(s).eq(half)].copy()
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", usecols=["tripid", "d_state_county_fips", "o_state_county_fips"], low_memory=False).drop_duplicates("tripid").set_index("tripid")
    hr = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", usecols=["household_id", "home_state_county_fips", "home_tract_fips", "home_bmc_taz", "home_tpb_taz"], low_memory=False).drop_duplicates("household_id").set_index("household_id")
    hr["hgeoid"] = geoid(hr.home_state_county_fips, hr.home_tract_fips).values
    t["d_geoid"] = geoid(t.tripid.map(r.d_state_county_fips), t.d_tract_fips).values
    t["o_geoid"] = geoid(t.tripid.map(r.o_state_county_fips), t.o_tract_fips).values
    t["d_purpose"] = t.d_activity.map(ACT_PURPOSE)
    t["d_zpt"] = t.d_geoid.map(tz.zone).fillna(-1).astype(int)
    t["dzone_pt"] = np.where(t.d_zpt > 0, m[t.d_zpt.clip(lower=0).values], -1)
    t["o_zpt"] = t.o_geoid.map(tz.zone).fillna(-1).astype(int)
    t["ozone_pt"] = np.where(t.o_zpt > 0, m[t.o_zpt.clip(lower=0).values], -1)
    t["km_rep"] = np.where(t.distance >= 0, t.distance * MI_KM, np.nan)
    # destination (activity end, job weights) and origin (home weights if the origin is home) distributions of every trip
    t["dloc"] = [LOC(b, tp, g, "work") for b, tp, g in zip(t.d_bmc_taz, t.d_tpb_taz, t.d_geoid)]
    t["oloc"] = [LOC(b, tp, g, "home" if a == 1 else "work") for b, tp, g, a in zip(t.o_bmc_taz, t.o_tpb_taz, t.o_geoid, t.o_activity)]
    hr["hloc"] = [LOC(b, tp, g, "home") for b, tp, g in zip(hr.home_bmc_taz, hr.home_tpb_taz, hr.hgeoid)]
    tr = load_tours(); tr = tr[(tr.anchor == "home") & tr.household_id.map(s).eq(half)].copy()
    tr = tr[~tr.primary_act.isin([1, -9])]
    tr["tour_id"] = np.arange(len(tr))
    key = t.drop_duplicates(["person_id", "arr_min"]).set_index(["person_id", "arr_min"])
    hit = key.reindex(pd.MultiIndex.from_arrays([tr.person_id.values, tr.primary_arr.values]))
    tr["p_geoid"] = hit.d_geoid.values; tr["p_idx"] = hit.dzone_pt.values; tr["p_tripid"] = hit.tripid.values; tr["p_km"] = hit.km_rep.values
    tr["p_w"] = hit.wttrdfin.values; tr["p_loc"] = hit.dloc.values
    tr = tr[tr.p_tripid.notna()]
    tr["mode_auto"] = tr.tour_mode.isin(["autoDriver", "autoPassenger", "sr"]).astype(float)
    tr["tod"] = tod_cls(tr.primary_arr)
    pr = tr[tr.purpose_abit.isin(C.DISC)].copy()
    pr = pd.DataFrame({"tripid": pr.p_tripid.astype(np.int64).values, "person_id": pr.person_id.values, "household_id": pr.household_id.values,
                       "purpose": pr.purpose_abit.values, "kind": "primary", "tour_purpose": pr.purpose_abit.values, "position": "",
                       "geoid": pr.p_geoid.values, "dzone_pt": pr.p_idx.values, "km_rep": pr.p_km.values, "w": pr.p_w.values,
                       "tod": pr.tod.values, "mode_auto": pr.mode_auto.values, "tour_id": pr.tour_id.values, "anchor_b": -1,
                       "dloc": pr.p_loc.values, "aloc": None, "bloc": None, "a_pt": -1, "b_pt": -1})
    mm = t.merge(tr[["person_id", "start_min", "end_min", "primary_arr", "primary_dep", "purpose_abit", "p_idx", "tod", "mode_auto", "tour_id", "p_tripid", "p_loc"]], on="person_id", how="inner")
    mm = mm[(mm.dep_min >= mm.start_min) & (mm.arr_min <= mm.end_min) & (mm.d_purpose != "HOME") & (mm.tripid != mm.p_tripid)]
    mm["position"] = np.where(mm.arr_min < mm.primary_arr, "out", np.where(mm.dep_min >= mm.primary_dep, "in", ""))
    mm = mm[mm.position.ne("") & mm.d_purpose.isin(C.DISC)].drop_duplicates("tripid")
    st = pd.DataFrame({"tripid": mm.tripid.values, "person_id": mm.person_id.values, "household_id": mm.household_id.values, "purpose": mm.d_purpose.values,
                       "kind": "stop", "tour_purpose": mm.purpose_abit.values, "position": mm.position.values, "geoid": mm.d_geoid.values,
                       "dzone_pt": mm.dzone_pt.values, "km_rep": mm.km_rep.values, "w": mm.wttrdfin.values, "tod": mm.tod.values,
                       "mode_auto": mm.mode_auto.values, "tour_id": mm.tour_id.values, "anchor_b": mm.p_idx.values,
                       "dloc": mm.dloc.values, "aloc": mm.oloc.values, "bloc": mm.p_loc.values, "a_pt": mm.ozone_pt.values, "b_pt": mm.p_idx.values})
    rec = pd.concat([pr, st], ignore_index=True)
    rec = chooser_cols(rec, P)
    # pp.gender carries the SILO code since the survey population was rebuilt (2026-10-27, GENDER_CODING_AUDIT.md fix 1):
    # 1 male, 2 female; the earlier RTS -> SILO recode here flipped it a second time (fixed 2026-11-04)
    rec["gender_silo"] = P.reindex(rec.person_id.values).gender.values
    rec["male_old"] = rec.male; rec["male"] = (rec.gender_silo == 1).astype(float)
    n0 = rec.groupby(["kind", "purpose"]).size()
    rec = rec[rec.home_idx.notna() & (rec.home_idx >= 0)].copy()             # chooser in the survey population (as prep_dc_data)
    rec["home_pt"] = rec.home_idx.astype(int)                                  # survey-population home zone (tract internal point)
    hl = rec.household_id.map(hr.hloc)
    rec["hloc"] = hl.values
    # sources and distributions
    for c in ["dloc", "aloc", "bloc", "hloc"]:
        rec[f"{c}_src"] = [x[1] if isinstance(x, tuple) else "" for x in rec[c]]
        rec[c] = [x[0] if isinstance(x, tuple) else None for x in rec[c]]
    stop = rec.kind.eq("stop")
    rec.loc[stop, "bloc"] = pd.Series(np.where(rec.position[stop] == "in", rec.hloc[stop], rec.bloc[stop]), index=rec.index[stop])
    rec.loc[stop, "bloc_src"] = np.where(rec.position[stop] == "in", rec.hloc_src[stop], rec.bloc_src[stop])
    rec.loc[stop, "b_pt"] = np.where(rec.position[stop] == "in", rec.home_pt[stop], rec.b_pt[stop])
    rec.loc[~stop, "aloc"] = rec.hloc[~stop]; rec.loc[~stop, "aloc_src"] = rec.hloc_src[~stop]; rec.loc[~stop, "a_pt"] = rec.home_pt[~stop]
    ok = rec.dloc.notna() & rec.aloc.notna() & (rec.bloc.notna() | ~stop)
    rec = rec[ok].reset_index(drop=True); rec["rec"] = np.arange(len(rec))
    # anchor configurations
    cfg = []
    for r_, k, a, b in zip(rec.rec.values, rec.kind.values, rec.aloc.values, rec.bloc.values):
        if k == "primary": d = {(za, -1): wa for za, wa in a.items()}
        else: d = {(za, zb): wa * wb for za, wa in a.items() for zb, wb in b.items()}
        d = norm(d)
        for (za, zb), w_ in d.items(): cfg.append((r_, za, zb, w_))
    cfg = pd.DataFrame(cfg, columns=["rec", "home_idx", "anchor_b", "w"])
    cand = pd.DataFrame([(r_, z, v) for r_, d in zip(rec.rec.values, rec.dloc.values) for z, v in d.items()], columns=["rec", "zidx", "b"])
    top = cfg.sort_values(["rec", "w"], ascending=[True, False]).drop_duplicates("rec").set_index("rec")
    rec["home_idx"] = rec.rec.map(top.home_idx).astype(int); rec["anchor_b"] = rec.rec.map(top.anchor_b).astype(int)
    rec["dzone_taz"] = [modal(d) for d in rec.dloc]; rec["a_taz"] = [modal(d) for d in rec.aloc]
    rec["b_taz"] = [modal(d) if d else -1 for d in rec.bloc]; rec["h_taz"] = [modal(d) if d else -1 for d in rec.hloc]
    rec["n_dz"] = [len(d) for d in rec.dloc]; rec["n_cfg"] = rec.rec.map(cfg.groupby("rec").size())
    n1 = rec.groupby(["kind", "purpose"]).size()
    keep = [c for c in rec.columns if c not in ("dloc", "aloc", "bloc", "hloc")]
    rec[keep].to_parquet(f"{WORK}/dc_rec_{half}_taz.parquet", index=False)
    cand.to_parquet(f"{WORK}/dc_cand_{half}_taz.parquet", index=False); cfg.to_parquet(f"{WORK}/dc_cfg_{half}_taz.parquet", index=False)
    print(f"{half}: {len(rec)} records, {len(cand) / len(rec):.3f} destination zones, {len(cfg) / len(rec):.3f} anchor configurations per record", flush=True)
    return rec[keep], n0, n1


def compare(half, rec):
    """share of records whose zone changed against the tract-point records of the model of record."""
    old = pd.read_parquet(f"{C.WORK}/dc_records_{half}.parquet")
    o = old.set_index(["tripid", "kind"])
    out = []
    for (kind, pur), g in rec.groupby(["kind", "purpose"]):
        k = pd.MultiIndex.from_arrays([g.tripid.values, g.kind.values]); hit = o.reindex(k); inold = hit.rec.notna().values
        d = dict(half=half, kind=kind, purpose=pur, N_taz=len(g), N_tract=int(((old.kind == kind) & (old.purpose == pur)).sum()), N_both=int(inold.sum()))
        gb = g[inold]
        d["dest_changed"] = float(np.mean(gb.dzone_taz.values != gb.dzone_pt.values))
        d["dest_split"] = float(np.mean(gb.n_dz.values > 1))
        d["home_changed"] = float(np.mean(gb.h_taz.values != gb.home_pt.values))
        if kind == "stop":
            d["a_changed"] = float(np.mean(gb.a_taz.values != gb.a_pt.values)); d["b_changed"] = float(np.mean(gb.b_taz.values != gb.b_pt.values))
        d["any_changed"] = float(np.mean((gb.dzone_taz.values != gb.dzone_pt.values) | (gb.a_taz.values != gb.a_pt.values) | ((gb.b_taz.values != gb.b_pt.values) & (gb.kind.values == "stop"))))
        d["n_cfg_gt1"] = float(np.mean(g.n_cfg.values > 1))
        for c in ["dloc_src", "aloc_src"]:
            for s_, v in g[c].value_counts(normalize=True).items(): d[f"{c}:{s_}"] = float(v)
        out.append(d)
    return out


def main():
    LOC = Locator(); rows, cnt = [], []
    for h in ["estimation", "validation"]:
        rec, n0, n1 = build(h, LOC); rows += compare(h, rec)
        cnt.append(pd.DataFrame({"observed": n0, "in_zone_system_taz": n1}).fillna(0).astype(int).assign(half=h))
    pd.concat(cnt).to_csv(f"{RES}/dc_taz_counts.csv")
    D = pd.DataFrame(rows); D.to_csv(f"{RES}/dc_taz_sources.csv", index=False); print(D.round(3).T.to_string())


if __name__ == "__main__":
    main()
