#!/usr/bin/env python3
"""Destination-choice records of the 2017/18 Regional Travel Survey (stage 3, 2026-10-22).

    python3 prep_dc_data.py            # both halves -> destination_choice/work/dc_records_<half>.parquet, dc_cand_<half>.parquet,
                                       #                work_records_<half>.parquet, tract_zone_overlay.parquet

One record per observed discretionary destination (purposes SHOPPING, RECREATION, ACCOMPANY, OTHER of rts_common.ACT_PURPOSE):
  primary   the primary activity of a home-based tour of the survey (rts_tours.csv, anchor home) whose MAST purpose is
            discretionary; the trip that arrives at the primary activity (person, arrival minute = primary_arr) gives the
            destination tract.  Origin = the home zone (MAST draws the primary destination from home).
  stop      every intermediate stop of a home-based tour (any tour purpose) with a discretionary activity: a trip inside the
            tour window (departure >= tour start, arrival <= tour end) that does not go home and arrives before the primary
            arrival (outbound) or departs at or after the primary departure (inbound), as build_targets.stop_purpose_split.
            Anchors = the two tour anchors MAST uses for a stop (MarylandStopModel): home and the primary destination.
Chooser attributes are those MAST sees for the same persons in the survey-population runs (3_abit/survey_pop/<half>/: hh.csv,
pp.csv, persons_map.csv): household income (midpoint of the RTS class), size, persons under 18, cars, licensed drivers; person
age, gender, licence, occupation; tour purpose and tour mode (stops), arrival hour at the primary activity (time of day).

Measurement of the destination.  The RTS geocodes trip ends to 2010 census tracts; 252 of the 1,588 zones contain no tract
internal point and could never be 'chosen' under a point rule.  The records therefore carry the set of candidate zones of the
destination tract t with weights b_zt = area(z n t) / area(z) (2010 TIGER tracts x MSTM zones, EPSG:26918): if destinations
are located uniformly within the chosen zone z, Pr(observed tract t | zone z) = b_zt, and the likelihood of the observation is
sum_z P(z) b_zt (dc_cand_<half>.parquet: rec, zone index, b; pieces below 1 % of the tract area dropped).  The zone of the tract
internal point (the convention of the other stage-3 comparisons) is kept as `dzone_pt`.

Work records (home -> usual workplace, for the work destination model of the accessibility measures): one per employed survey
traveller with a usual work location (j1_workplace_loc 1, 2, 4) and a work tract in the zone system.
"""
# COPY of Validation_2026/3_abit/destination_choice/prep_dc_data.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dc_common as C
from rts_common import RTS, ACT_PURPOSE, MI_KM, load_split, load_tours
from survey_population import tract_zone, geoid, OUTD


def overlay():
    f = f"{SHARED}/zones/tract_zone_overlay.parquet"  # PATH
    if os.path.exists(f): return pd.read_parquet(f)
    import geopandas as gpd
    tr = pd.concat([gpd.read_file(f"{C.TRACTS}/tl_2010_{s}_tract10/tl_2010_{s}_tract10.shp")[["GEOID10", "geometry"]] for s in [10, 11, 24, 42, 51, 54]])
    tr = gpd.GeoDataFrame(tr, geometry="geometry", crs="EPSG:4269").to_crs("EPSG:26918")
    z = gpd.read_file(C.ZONES_SHP)[["id", "geometry"]]
    z["zarea"] = z.geometry.area; tr["tarea"] = tr.geometry.area
    tr = tr[tr.intersects(z.union_all().envelope)]
    o = gpd.overlay(tr, z, how="intersection", keep_geom_type=True)
    o["a"] = o.geometry.area
    o = pd.DataFrame(o.drop(columns="geometry"))
    o["share_tract"] = o.a / o.tarea; o["b"] = o.a / o.zarea
    o = o[o.share_tract >= 0.01]
    m = C.id2idx(); o["zidx"] = m[o["id"].astype(int).values]
    o = o.rename(columns={"GEOID10": "geoid"})[["geoid", "zidx", "b", "share_tract"]]
    o.to_parquet(f, index=False); return o


def people(half):
    """Chooser attributes of the survey-population input of the half, keyed by survey person_id (travellers)."""
    od = f"{OUTD}/{half}"
    hh = pd.read_csv(f"{od}/hh.csv").set_index("id"); pp = pd.read_csv(f"{od}/pp.csv"); pm = pd.read_csv(f"{od}/persons_map.csv")
    pp["lic"] = pp.driversLicense.astype(str).eq("True")
    pp["inc_m"] = np.floor(pp.income / 12.0)      # MAST stores int(annual / 12) per person (MarylandLosDataReader)
    g = pp.groupby("hhID").agg(children=("age", lambda a: int((a < 18).sum())), drivers=("lic", "sum"), hhsize=("age", "size"), inc_month=("inc_m", "sum"))
    pm = pm[~pm.imputed].merge(pp[["id", "gender", "lic", "occupation"]], on="id")
    pm = pm.join(g, on="hhID").join(hh[["autos", "income"]], on="hhID")
    pm["home_idx"] = C.id2idx()[pm.home_zone.values]
    return pm.set_index("person_id")


def chooser_cols(df, P):
    p = P.reindex(df.person_id.values)
    df["age"] = p.age.values; df["male"] = (p.gender.values == 1).astype(float); df["lic"] = p.lic.values.astype(float)
    df["occ"] = p.occupation.values; df["hhsize"] = p.hhsize.values; df["children"] = p.children.values
    df["autos"] = p.autos.values; df["drivers"] = p.drivers.values; df["inc_month"] = p.inc_month.values
    df["inc_year"] = df.inc_month * 12.0; df["home_idx"] = p.home_idx.values     # household income as MAST sums it
    df["inc_cls"] = np.select([df.inc_year < 50000, df.inc_year < 100000], [0, 1], 2)
    df["car_cls"] = np.select([df.autos <= 0, df.autos < df.drivers], [0, 1], 2)          # 0 cars / cars < drivers / cars >= drivers
    return df


def tod_cls(arr_min):
    h = (np.asarray(arr_min, float) % 1440) // 60
    return np.select([(h >= 6) & (h < 9), (h >= 9) & (h < 15), (h >= 15) & (h < 19)], [0, 1, 2], 3)   # AM, midday, PM, evening/night


def build(half):
    s = load_split(); tz = tract_zone().set_index("geoid"); m = C.id2idx(); ov = overlay()
    P = people(half)
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv.gz", low_memory=False,
                    usecols=["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "d_tract_fips", "o_tract_fips", "travel_mode", "distance", "dep_min", "arr_min", "wttrdfin"])
    t = t[t.household_id.map(s).eq(half)].copy()
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv.gz", usecols=["tripid", "d_state_county_fips", "o_state_county_fips"], low_memory=False).drop_duplicates("tripid").set_index("tripid")
    t["d_geoid"] = geoid(t.tripid.map(r.d_state_county_fips), t.d_tract_fips).values
    t["d_purpose"] = t.d_activity.map(ACT_PURPOSE)
    t["d_zpt"] = t.d_geoid.map(tz.zone).fillna(-1).astype(int)
    t["dzone_pt"] = np.where(t.d_zpt > 0, m[t.d_zpt.clip(lower=0).values], -1)
    t["km_rep"] = np.where(t.distance >= 0, t.distance * MI_KM, np.nan)
    tr = load_tours(); tr = tr[(tr.anchor == "home") & tr.household_id.map(s).eq(half)].copy()
    tr = tr[~tr.primary_act.isin([1, -9])]
    tr["tour_id"] = np.arange(len(tr))
    key = t.drop_duplicates(["person_id", "arr_min"]).set_index(["person_id", "arr_min"])
    pk = pd.MultiIndex.from_arrays([tr.person_id.values, tr.primary_arr.values])
    hit = key.reindex(pk)
    tr["p_geoid"] = hit.d_geoid.values; tr["p_idx"] = hit.dzone_pt.values; tr["p_tripid"] = hit.tripid.values; tr["p_km"] = hit.km_rep.values
    tr["p_w"] = hit.wttrdfin.values
    tr = tr[tr.p_tripid.notna()]
    tr["mode_auto"] = tr.tour_mode.isin(["autoDriver", "autoPassenger", "sr"]).astype(float)
    tr["tod"] = tod_cls(tr.primary_arr)
    # primaries
    pr = tr[tr.purpose_abit.isin(C.DISC)].copy()
    pr = pd.DataFrame({"tripid": pr.p_tripid.astype(np.int64).values, "person_id": pr.person_id.values, "household_id": pr.household_id.values,
                       "purpose": pr.purpose_abit.values, "kind": "primary", "tour_purpose": pr.purpose_abit.values, "position": "",
                       "geoid": pr.p_geoid.values, "dzone_pt": pr.p_idx.values, "km_rep": pr.p_km.values, "w": pr.p_w.values,
                       "tod": pr.tod.values, "mode_auto": pr.mode_auto.values, "tour_id": pr.tour_id.values, "anchor_b": -1})
    # stops
    mm = t.merge(tr[["person_id", "start_min", "end_min", "primary_arr", "primary_dep", "purpose_abit", "p_idx", "tod", "mode_auto", "tour_id", "p_tripid"]], on="person_id", how="inner")
    mm = mm[(mm.dep_min >= mm.start_min) & (mm.arr_min <= mm.end_min) & (mm.d_purpose != "HOME") & (mm.tripid != mm.p_tripid)]
    mm["position"] = np.where(mm.arr_min < mm.primary_arr, "out", np.where(mm.dep_min >= mm.primary_dep, "in", ""))
    mm = mm[mm.position.ne("") & mm.d_purpose.isin(C.DISC)].drop_duplicates("tripid")
    st = pd.DataFrame({"tripid": mm.tripid.values, "person_id": mm.person_id.values, "household_id": mm.household_id.values, "purpose": mm.d_purpose.values,
                       "kind": "stop", "tour_purpose": mm.purpose_abit.values, "position": mm.position.values, "geoid": mm.d_geoid.values,
                       "dzone_pt": mm.dzone_pt.values, "km_rep": mm.km_rep.values, "w": mm.wttrdfin.values, "tod": mm.tod.values,
                       "mode_auto": mm.mode_auto.values, "tour_id": mm.tour_id.values, "anchor_b": mm.p_idx.values})
    rec = pd.concat([pr, st], ignore_index=True)
    rec = chooser_cols(rec, P)
    n0 = rec.groupby(["kind", "purpose"]).size()
    rec = rec[rec.home_idx.notna() & (rec.home_idx >= 0)]
    rec = rec[(rec.kind == "primary") | (rec.anchor_b >= 0)]
    rec = rec[rec.geoid.isin(ov.geoid.unique())].reset_index(drop=True)
    rec["home_idx"] = rec.home_idx.astype(int); rec["anchor_b"] = rec.anchor_b.astype(int)
    rec["rec"] = np.arange(len(rec))
    cand = rec[["rec", "geoid"]].merge(ov, on="geoid")[["rec", "zidx", "b"]]
    n1 = rec.groupby(["kind", "purpose"]).size()
    log = pd.DataFrame({"observed": n0, "in_zone_system": n1}).fillna(0).astype(int)
    rec.to_parquet(f"{C.WORK}/dc_records_{half}.parquet", index=False); cand.to_parquet(f"{C.WORK}/dc_cand_{half}.parquet", index=False)
    log.to_csv(f"{C.WORK}/dc_counts_{half}.csv")
    print(f"{half}: {len(rec)} records, {len(cand)} candidate pairs ({len(cand) / len(rec):.2f} per record)\n{log}")
    work_records(half, P, tz, ov)


def work_records(half, P, tz, ov):
    s = load_split()
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv.gz", usecols=["household_id", "person_id", "employment_status", "j1_workplace_loc", "work_state_county_fips", "work_tract_fips", "wtperfin"],
                    low_memory=False).drop_duplicates("person_id")
    r = r[r.household_id.map(s).eq(half) & r.employment_status.eq(0) & r.j1_workplace_loc.isin([1, 2, 4])].copy()
    r["geoid"] = geoid(r.work_state_county_fips, r.work_tract_fips).values
    r = r[r.geoid.isin(ov.geoid.unique()) & r.person_id.isin(P.index)].copy()
    r = chooser_cols(r.rename(columns={"wtperfin": "w"}), P)
    r = r[r.home_idx >= 0].reset_index(drop=True); r["home_idx"] = r.home_idx.astype(int)
    r["dzone_pt"] = C.id2idx()[r.geoid.map(tz.zone).fillna(1).astype(int).values]
    r["purpose"] = "WORK"; r["kind"] = "primary"; r["rec"] = np.arange(len(r)); r["anchor_b"] = -1; r["tod"] = 0; r["mode_auto"] = 1.0
    cand = r[["rec", "geoid"]].merge(ov, on="geoid")[["rec", "zidx", "b"]]
    r.to_parquet(f"{C.WORK}/work_records_{half}.parquet", index=False); cand.to_parquet(f"{C.WORK}/work_cand_{half}.parquet", index=False)
    print(f"{half}: {len(r)} work records")


if __name__ == "__main__":
    for h in ["estimation", "validation"]: build(h)
