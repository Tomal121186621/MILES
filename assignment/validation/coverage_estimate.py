#!/usr/bin/env python3
"""Expected coverage of the counts by a residents-only assignment (2026-11-12): an explanatory estimate, not an adjustment.

The model carries the cars of the persons of the activity model whose day touches the six counties. The counts also hold traffic the
model cannot carry: trucks and buses (removed from the passenger count with the station's classification), through trips of persons who
never stop in the region, visitors from beyond the model area, and light commercial, delivery and fleet vehicles. This script estimates,
from sources already in the project, the share of the counted passenger traffic that belongs to these groups, by facility group, and
sets it against the observed shortfall. Nothing is applied to the model or to the counts.

Sources
  through trips of the model area : the activity-model output of the replication passed to the assignment (3_abit/final_2024/run_respec/fin24_s08):
                                     car-driver trips of persons with no activity in the six counties whose straight line crosses the
                                     region (persons dropped by the population converter as external-external); 10 % sample, expanded by ten;
                                     the length of the straight line inside the region, times a detour factor, gives their vehicle miles
  observed passenger vehicle miles : SHA mileage reports 2024 converted to weekday passenger vehicles (regional_validation.py, c1_vmt_fc.csv)
  cordon mix                       : the 16 principal crossings of the regional boundary with their 2023 counts (MATSIM_HOME/network_validation_2023,
                                     gateways_2023.csv), used only to split the through traffic between freeways and arterials
  trucks, buses, light trucks      : MDOT SHA classification counts at the stations of the region (vehicle classes 2, 3, 4, 5-13)
  business driving of households  : FHWA 2022 National Household Travel Survey, trip file (data/raw/nhts/2022_csv.zip): share of the car-driver
                                     vehicle miles of weekday trips to or from a work-related meeting or trip
Not in the project: the external trip tables of the statewide model (through trips from beyond the model area, e.g. the I-95 corridor north
of Delaware), and a count of fleet and delivery vehicles; the ranges below say where this matters.
Usage: python3 assignment/validation/coverage_estimate.py   (env OUT, REGIONAL_DATA) -> data/coverage_estimate.csv, coverage_through_trips.csv, coverage_sources.json"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, json, zipfile, numpy as np, pandas as pd
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"; ROOT = f"{PROJECT_ROOT}"   # H: validation data and outputs (workspace)
WORK = f"{V}/5_reports/validation_pdfs/work/matsim_respec"
RD = os.environ.get("REGIONAL_DATA", f"{WORK}/regional/data"); OUT = os.environ.get("OUT", H); DATA = f"{OUT}/data"; os.makedirs(DATA, exist_ok=True)
ABIT_OUT = os.environ.get("ABIT_OUT", f"{V}/3_abit/final_2024/run_respec/fin24_s08/output")
EXP = 10; DETOUR = (1.1, 1.2, 1.4)        # route length / straight line inside the region: low, central, high
MI = 1609.344
GROUPS = {"Interstates and freeways": ["Interstate: I-695", "Interstate: other", "Other freeway / expressway"], "Principal arterials": ["Principal arterial"],
          "Minor arterials": ["Minor arterial"], "Collectors and local roads": ["Major collector", "Minor collector / local"]}
VMT_FC = {"Interstates and freeways": ["Interstate", "Other freeway, expressway"], "Principal arterials": ["Other principal arterial"], "Minor arterials": ["Minor arterial"], "Collectors and local roads": ["Collector", "Local"]}


def through_trips():
    import geopandas as gpd, shapely
    bmr = set(open(f"{ABIT_HOME}/input/maryland/BMR.txt").read().split())
    poly = gpd.read_file(f"{MATSIM_HOME}/data/bmr_counties.gpkg").to_crs(26985).geometry.union_all()      # activity-model coordinates: Maryland State Plane (metres)
    Lg = pd.read_parquet(f"{ABIT_OUT}/legs_full.parquet", columns=["person_id", "start_zone", "end_zone", "start_x", "start_y", "end_x", "end_y", "mode", "distance_m"])
    touch = Lg.start_zone.isin(bmr) | Lg.end_zone.isin(bmr); persons_touch = set(Lg.person_id[touch])
    ext = Lg[~Lg.person_id.isin(persons_touch)]; n_persons_ext = ext.person_id.nunique()
    ext = ext[ext["mode"] == "CAR_DRIVER"].copy()
    for c in ["start_x", "start_y", "end_x", "end_y", "distance_m"]: ext[c] = pd.to_numeric(ext[c], errors="coerce")
    ext = ext.dropna(subset=["start_x", "start_y", "end_x", "end_y"])
    x0, y0, x1, y1 = poly.bounds
    box = ~((np.maximum(ext.start_x, ext.end_x) < x0) | (np.minimum(ext.start_x, ext.end_x) > x1) | (np.maximum(ext.start_y, ext.end_y) < y0) | (np.minimum(ext.start_y, ext.end_y) > y1))
    cand = ext[box]
    lines = shapely.linestrings(np.stack([np.stack([cand.start_x, cand.start_y], 1), np.stack([cand.end_x, cand.end_y], 1)], 1))
    hit = shapely.intersects(lines, poly); T = cand[hit].copy(); inside = shapely.length(shapely.intersection(lines[hit], poly))
    T["inside_m"] = inside; T["chord_m"] = np.hypot(T.end_x - T.start_x, T.end_y - T.start_y)
    n_trips = len(T) * EXP; miles_c = T.inside_m.sum() / MI * EXP
    res = dict(persons_model_area=int(Lg.person_id.nunique()), persons_touching_region=int(len(persons_touch)), persons_external=int(n_persons_ext),
               car_driver_legs_external=int(len(ext)), through_car_trips_sample=int(len(T)), through_car_trips_day=float(n_trips),
               mean_chord_inside_km=float(T.inside_m.mean() / 1e3), median_chord_inside_km=float(T.inside_m.median() / 1e3), mean_trip_distance_km=float(T.distance_m.mean() / 1e3),
               through_vehicle_miles_day_straight=float(miles_c), through_vehicle_miles_day_low=float(miles_c * DETOUR[0]), through_vehicle_miles_day=float(miles_c * DETOUR[1]), through_vehicle_miles_day_high=float(miles_c * DETOUR[2]),
               detour_factor=DETOUR)
    # by origin side: which state / county do the through trips come from (home zone of the person: first leg start)
    hz = Lg.drop_duplicates("person_id").set_index("person_id").start_zone
    zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv", usecols=["ZoneId", "COUNTYFIPS"], dtype={"ZoneId": str}).set_index("ZoneId").COUNTYFIPS
    T["home_county"] = T.person_id.map(hz).map(zs)
    ST = {"24": "Maryland (outside the six counties)", "10": "Delaware", "11": "District of Columbia", "42": "Pennsylvania", "51": "Virginia", "54": "West Virginia"}
    T["home_state"] = T.home_county.astype(str).str[:2].map(ST).fillna("other")
    by = (T.groupby("home_state").size() * EXP).sort_values(ascending=False); res["through_trips_by_home_state"] = {k: int(v) for k, v in by.items()}
    return res


def cordon_mix():
    g = pd.read_csv(f"{MATSIM_HOME}/network_validation_2023/calibration/gateways_2023.csv")
    tot = g.cordon_aadt.sum(); fw = g[g.hwy == "motorway"].cordon_aadt.sum()
    return dict(crossings=int(len(g)), cordon_aadt_2023=float(tot), freeway_share=float(fw / tot), arterial_share=float(1 - fw / tot))


def nhts_business_share():
    z = zipfile.ZipFile(f"{V}/data/raw/nhts/2022_csv.zip")
    N = pd.read_csv(z.open("tripv2pub.csv"), usecols=["CENSUS_D", "MSASIZE", "RAIL", "TDWKND", "DRVR_FLG", "TRPTRANS", "TRPMILES", "WHYTO", "WHYFROM", "WTTRDFIN5D"])
    N = N[(N.TDWKND == 2) & (N.DRVR_FLG == 1) & N.TRPTRANS.isin([1, 2, 3, 4]) & (N.TRPMILES > 0) & (N.WTTRDFIN5D > 0)]
    biz = (N.WHYTO == 4) | (N.WHYFROM == 4)           # 4 = work-related meeting or trip
    w = N.TRPMILES * N.WTTRDFIN5D
    nat = float(w[biz].sum() / w.sum())
    S = N[(N.CENSUS_D == 5) & (N.MSASIZE == 4) & (N.RAIL == 1)]; ws = S.TRPMILES * S.WTTRDFIN5D; bs = (S.WHYTO == 4) | (S.WHYFROM == 4)
    return dict(national_vmt_share=nat, south_atlantic_large_metro_vmt_share=float(ws[bs].sum() / ws.sum()), n_trips_national=int(len(N)), n_trips_south_atlantic=int(len(S)),
                national_trip_share=float(N.WTTRDFIN5D[biz].sum() / N.WTTRDFIN5D.sum()))


def main():
    S = pd.read_csv(f"{DATA}/stations_diagnostics.csv", dtype={"LOCATION_ID": str}, low_memory=False); M = S[S.use == "mainline"]
    VF = pd.read_csv(f"{RD}/c1_vmt_fc.csv").set_index("fc")
    thr = through_trips(); cm = cordon_mix(); bz = nhts_business_share()
    print(json.dumps(thr, indent=1)); print(cm); print(bz)
    rows = []
    for grp, cls in GROUPS.items():
        d = M[M.cls.isin(cls)]; c = d[d.has_cls]
        wt = c.count_all
        trk = float((c.trk_sh * wt).sum() / wt.sum()); bus = float((c.bus_sh * wt).sum() / wt.sum()); lt = float((c.light_truck_sh * wt).sum() / wt.sum())
        vmt = float(VF.loc[[f for f in VMT_FC[grp] if f in VF.index], "wkday_pass"].sum())
        if grp == "Interstates and freeways": tv = thr["through_vehicle_miles_day"] * cm["freeway_share"]; tl = thr["through_vehicle_miles_day_low"] * cm["freeway_share"]; th = thr["through_vehicle_miles_day_high"] * cm["freeway_share"]
        elif grp == "Principal arterials": tv = thr["through_vehicle_miles_day"] * cm["arterial_share"]; tl = thr["through_vehicle_miles_day_low"] * cm["arterial_share"]; th = thr["through_vehicle_miles_day_high"] * cm["arterial_share"]
        else: tv = tl = th = 0.0
        through_c, through_l, through_h = tv / vmt, tl / vmt, th / vmt
        comm_l = bz["national_vmt_share"]; comm_h = lt            # household business driving (lower bound) to the measured class-3 share (upper bound: includes personal pickups and vans)
        comm_c = 0.5 * (comm_l + comm_h)
        obs_all = 1 - d.model_all_mean.sum() / d.count_all.sum(); obs_pass = 1 - d.model_car_mean.sum() / d.count_pass.sum()
        rows.append(dict(group=grp, stations=int(len(d)), classified_stations=int(len(c)), truck_share=trk, bus_share=bus, light_truck_share=lt, observed_pass_vmt_mday=vmt / 1e6,
                         through_vmt_mday=tv / 1e6, through_share=through_c, through_low=through_l, through_high=through_h,
                         commercial_low=comm_l, commercial_central=comm_c, commercial_high=comm_h,
                         expected_low=through_l + comm_l, expected_central=through_c + comm_c, expected_high=through_h + comm_h,
                         shortfall_all=obs_all, shortfall_pass=obs_pass, residual_central=obs_pass - (through_c + comm_c), residual_low=obs_pass - (through_h + comm_h), residual_high=obs_pass - (through_l + comm_l)))
    d = M; c = d[d.has_cls]; wt = c.count_all
    vmt = float(VF.wkday_pass.sum()); tv = thr["through_vehicle_miles_day"]
    lt = float((c.light_truck_sh * wt).sum() / wt.sum()); comm_l = bz["national_vmt_share"]; comm_c = 0.5 * (comm_l + lt)
    obs_pass = 1 - d.model_car_mean.sum() / d.count_pass.sum()
    rows.append(dict(group="All mainline stations", stations=int(len(d)), classified_stations=int(len(c)), truck_share=float((c.trk_sh * wt).sum() / wt.sum()), bus_share=float((c.bus_sh * wt).sum() / wt.sum()), light_truck_share=lt,
                     observed_pass_vmt_mday=vmt / 1e6, through_vmt_mday=tv / 1e6, through_share=tv / vmt, through_low=thr["through_vehicle_miles_day_low"] / vmt, through_high=thr["through_vehicle_miles_day_high"] / vmt,
                     commercial_low=comm_l, commercial_central=comm_c, commercial_high=lt, expected_low=thr["through_vehicle_miles_day_low"] / vmt + comm_l, expected_central=tv / vmt + comm_c, expected_high=thr["through_vehicle_miles_day_high"] / vmt + lt,
                     shortfall_all=1 - d.model_all_mean.sum() / d.count_all.sum(), shortfall_pass=obs_pass, residual_central=obs_pass - (tv / vmt + comm_c), residual_low=obs_pass - (thr["through_vehicle_miles_day_high"] / vmt + lt), residual_high=obs_pass - (thr["through_vehicle_miles_day_low"] / vmt + comm_l)))
    C = pd.DataFrame(rows); C.to_csv(f"{DATA}/coverage_estimate.csv", index=False, float_format="%.5g"); print(C.round(3).to_string())
    pd.DataFrame([thr]).to_csv(f"{DATA}/coverage_through_trips.csv", index=False)
    json.dump(dict(through=thr, cordon=cm, nhts=bz), open(f"{DATA}/coverage_sources.json", "w"), indent=1, default=float)


if __name__ == "__main__": main()
