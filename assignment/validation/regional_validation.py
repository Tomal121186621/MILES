#!/usr/bin/env python3
"""Regional traffic validation of the UPSTREAM models through the assignment (validation only: nothing is fitted or adjusted).

Chain CVAE -> SILO -> ABIT -> MATSim, Baltimore region (24003, 24005, 24013, 24025, 24027, 24510), 2024, 10 % sample (x 10),
one representative weekday.  Every MATSim seed under RUNS_ROOT/2024_s<N> with a .done.json is used; statistics are given per
seed and as mean, minimum and maximum over the seeds.

Checks (observed sources: see SOURCES in this file and REPORT.md):
 1 VMT        weekday passenger-vehicle VMT by county x functional class (link volumes x length) vs MDOT SHA 2024 annual VMT
              (Mileage Reports, FCAVMT-ALL) converted to weekday passenger VMT with the weekday/annual-day factor and the truck and
              bus shares of the region's 2024 count stations (both MDOT SHA data; no model quantity used).
 2 Commute    time and departure of the home->work commute of resident workers by home county vs ACS 2024 1-year B08303, B08302,
              and drivers alone vs ACS 2020-2024 5-year B08134 / B08136.
 3 Skims      MATSim congested car trip times vs the fixed AM-peak car skim read by SILO and ABIT (no feedback), by distance band.
 4 Transit    weekday boardings by MTA mode vs NTD 2024 average typical weekday, and vs its 2017/18 equivalent (x mean annual UPT
              2017-2018 / annual UPT 2024 of the mode), the period of the survey the behaviour is estimated on.
 5 Trip length car-driver trip distance and time of residents vs RTS 2017/18 (weighted) and NHTS 2022 (Baltimore MSA, weekday).
 6 Count gap  modelled volume at the count-station links by trip purpose and hour (selected plans' routes) vs counts.
 7 OD         county-to-county commuting of resident workers vs ACS 2016-2020 county flows and LODES 2022 (JT00).

Usage: python3 assignment/validation/regional_validation.py [RUNS_ROOT] [OUT_DIR] [--seeds 1,2] [--force] [--figures-only]
Per-seed intermediate results are cached in OUT_DIR/data/seeds/s<N>/ (small CSVs); --force recomputes them.
Memory: the plans file is streamed line by line; trips/legs are read column-selected (< 4 GB)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, json, glob, gzip, argparse, time, zipfile, warnings, collections
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"; ROOT = f"{PROJECT_ROOT}"   # H: validation data and outputs (workspace)
sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps  # noqa: E402
ps.RATIO_COLORS = ["#104281", "#4a7fc4", "#a9cbf2", "#e8e7e1", "#f0a09f", "#e34948", "#9c1d1c"]   # map classes kept distinct from the model blue of the bars

EXP = 10
CO = ["24510", "24005", "24003", "24027", "24025", "24013"]
CN = {"24510": "Baltimore City", "24005": "Baltimore County", "24003": "Anne Arundel", "24027": "Howard", "24025": "Harford", "24013": "Carroll"}
CSHORT = {"24510": "Balt. City", "24005": "Balt. County", "24003": "Anne Arundel", "24027": "Howard", "24025": "Harford", "24013": "Carroll"}
MDOT_NAME = {"ANNE ARUNDEL": "24003", "BALTIMORE": "24005", "CARROLL": "24013", "HARFORD": "24025", "HOWARD": "24027", "BALTIMORE CITY": "24510"}
FCG = {1: "Interstate", 2: "Other freeway, expressway", 3: "Other principal arterial", 4: "Minor arterial", 5: "Collector", 6: "Collector", 7: "Local"}
FCORDER = ["Interstate", "Other freeway, expressway", "Other principal arterial", "Minor arterial", "Collector", "Local"]
OSM_GROUP = {"motorway": 1, "trunk": 2, "primary": 3, "secondary": 4, "tertiary": 5, "residential": 7, "unclassified": 7, "living_street": 7, "service": 7,
             "motorway_link": 1, "trunk_link": 2, "primary_link": 3, "secondary_link": 4, "tertiary_link": 5}
COMMODE = ["Drove alone", "Carpool, passenger", "Public transport", "Walk", "Bicycle"]
def COMMODE_OF(m):
    if "pt" in m: return "Public transport"
    if m == {"car"}: return "Drove alone"
    if "ride" in m or "car" in m: return "Carpool, passenger"
    if "bike" in m: return "Bicycle"
    return "Walk"
SYSTEMS = ["Interstate", "US route", "MD route", "Ramp", "County, municipal, other"]
ROUTES = [("I-695", ["IS 695"]), ("I-95", ["IS 95"]), ("I-83", ["IS 83"]), ("I-97", ["IS 97"]), ("I-70", ["IS 70"]), ("I-795", ["IS 795"]), ("I-895", ["IS 895"]),
          ("I-195", ["IS 195"]), ("MD 295", ["MD 295"]), ("MD 100", ["MD 100"]), ("US 29", ["US 29"]), ("US 40", ["US 40"]), ("US 1", ["US 1"]), ("MD 2", ["MD 2"]),
          ("MD 140", ["MD 140"]), ("MD 32", ["MD 32"]), ("MD 43", ["MD 43"]), ("MD 10", ["MD 10"]), ("US 50 / I-595", ["US 50", "IS 595"])]
PURP = ["Home–work", "Home–school", "Home–shopping", "Home–other", "Not home-based"]
B08303_BINS = ["<5", "5–9", "10–14", "15–19", "20–24", "25–29", "30–34", "35–39", "40–44", "45–59", "60–89", "90+"]
B08303_EDGES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 60, 90, 1e9]
B08134_BINS = ["<10", "10–14", "15–19", "20–24", "25–29", "30–34", "35–44", "45–59", "60+"]
B08134_EDGES = [0, 10, 15, 20, 25, 30, 35, 45, 60, 1e9]
B08302_BINS = ["0–4:59", "5:00", "5:30", "6:00", "6:30", "7:00", "7:30", "8:00", "8:30", "9:00", "10:00", "11:00", "12–15:59", "16–23:59"]
B08302_EDGES = [0, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 10, 11, 12, 16, 24]
DIST_EDGES = [0, 2, 5, 10, 15, 20, 30, 40, 60, 1e9]; DIST_BINS = ["<2", "2–5", "5–10", "10–15", "15–20", "20–30", "30–40", "40–60", "60+"]
TIME_EDGES = [0, 5, 10, 15, 20, 30, 40, 60, 1e9]; TIME_BINS = ["<5", "5–10", "10–15", "15–20", "20–30", "30–40", "40–60", "60+"]
BAND_EDGES = [0, 5, 10, 20, 40, 1e9]; BAND_LABELS = ["<5", "5–10", "10–20", "20–40", "40+"]
PERIODS = {"AM peak (6–9 h)": (6, 9), "Midday (10–15 h)": (10, 15), "PM peak (15–19 h)": (15, 19)}
OD_DEST = CO + ["DCsub", "MDoth", "11001", "OTH"]
OD_LAB = {**CSHORT, "DCsub": "Montgomery, Pr. George's", "MDoth": "Other Maryland", "11001": "Washington DC", "OTH": "Other states"}
TRANSIT = {"bus": "Local bus", "cb": "Commuter bus", "lr": "Light rail", "mt": "Metro subway", "marc": "MARC train"}
NTD_MODE = {"Local bus": "MB", "Commuter bus": "CB", "Light rail": "LR", "Metro subway": "HR", "MARC train": "CR"}
NTD_2023_NAME = {"Local bus": "Local Bus", "Commuter bus": "Commuter Bus", "Light rail": "Light Rail", "Metro subway": "Metro Subway", "MARC train": "MARC"}
SOURCES = {
    "mdot_vmt": "MDOT SHA, 2024 Mileage Reports, table FCAVMT-ALL (annual VMT by functional class, all systems; updated 2025-10-17): https://www.roads.maryland.gov/OPPEN/2024_Mileage_Reports.pdf",
    "mdot_counts": "MDOT SHA Annual Average Daily Traffic 2024 (AADT, AAWDT, vehicle classification) at the region's count stations: https://geodata.md.gov/imap/rest/services/Transportation/MD_AnnualAverageDailyTraffic/MapServer",
    "acs": "U.S. Census Bureau, ACS 2024 1-year and 2020-2024 5-year detailed tables B08303, B08302, B08134, B08136, B08301 by county, via https://data.census.gov/api/access/data/table?id=ACSDT1Y2024.<table>&g=050XX00US<county>",
    "acs_flows": "U.S. Census Bureau, 2016-2020 ACS 5-year county-to-county commuting flows: https://www.census.gov/data/tables/2020/demo/metro-micro/commuting-flows-2020.html",
    "lodes": "U.S. Census Bureau LEHD LODES 8, OD JT00 2022 (md main; dc, va, pa, de, wv aux): https://lehd.ces.census.gov/data/lodes/LODES8/",
    "ntd": "FTA National Transit Database, Annual Data - Service by Mode and Time Period, MTA Maryland (NTD ID 30034), Average Typical Weekday unlinked passenger trips, report years 2023 and 2024: https://data.transportation.gov/resource/wwdp-t4re",
    "rts": "BMC/TPB 2017/18 Regional Travel Survey (trips, weighted; households of the six counties)",
    "nhts": "FHWA 2022 NHTS public trip file (South Atlantic, MSA 1-3 million with heavy rail = Baltimore MSA), weekday weights: https://nhts.ornl.gov/",
}

# ------------------------------------------------------------------------------------------------ helpers
def hms(s):
    s = s.fillna("0:0:0").astype(str); p = s.str.split(":", expand=True).astype(float)
    return p[0] * 3600 + p[1] * 60 + p[2]

def tvd(m, o):
    m = np.asarray(m, float); o = np.asarray(o, float); return 50 * np.abs(m / m.sum() - o / o.sum()).sum()

def mape(m, o):
    m = np.asarray(m, float); o = np.asarray(o, float); k = o > 0; return 100 * np.mean(np.abs(m[k] - o[k]) / o[k])

def ks(m, o):
    m = np.asarray(m, float); o = np.asarray(o, float); return 100 * np.max(np.abs(np.cumsum(m / m.sum()) - np.cumsum(o / o.sum())))

def hist(x, edges, w=None):
    return np.histogram(np.clip(x, edges[0], edges[-1] - 1e-9), bins=edges, weights=w)[0].astype(float)

def wq(x, w, q):
    i = np.argsort(x); x = np.asarray(x)[i]; c = np.cumsum(np.asarray(w)[i]); return float(np.interp(q * c[-1], c, x))

def seeds_present(root):
    out = []
    for d in glob.glob(f"{root}/2024_s*"):
        m = re.fullmatch(r"2024_s(\d+)", os.path.basename(d))
        if m and os.path.exists(f"{d}/.done.json"): out.append(int(m.group(1)))
    return sorted(out)

def agg_seeds(df, keys, val="value"):
    g = df.groupby(keys, sort=False)[val]; return g.agg(mean="mean", min="min", max="max", n_seeds="count").reset_index()

# ------------------------------------------------------------------------------------------------ static inputs
_static = {}
def links_static():
    """Car links of the six counties (network 2024): length, county (link midpoint), MDOT functional class (nearest MDOT segment,
    from the network audit; else the OSM class), free-flow time."""
    if "links" in _static: return _static["links"]
    import geopandas as gpd, shapely
    A = pd.read_parquet(f"{V}/data/network_audit_links.parquet", columns=["f", "t", "length", "freespeed", "permlanes", "xm", "ym", "x0", "y0", "x1", "y1", "mdot_fc", "mdot_route", "hwy"])
    C = gpd.read_file(f"{MATSIM_HOME}/data/bmr_counties.gpkg").to_crs("EPSG:26985")
    A["county"] = None
    for g, geom in zip(C.GEOID, C.geometry):
        k = shapely.contains_xy(geom, A.xm.values, A.ym.values); A.loc[k, "county"] = g
    A = A[A.county.notna()].copy()
    fc = A.mdot_fc.fillna(A.hwy.map(OSM_GROUP)).fillna(7).astype(int)
    A["fc"] = fc.map(FCG); A["fc_src"] = np.where(A.mdot_fc.notna(), "MDOT", "OSM")
    A["route"] = A.mdot_route.fillna("").str.strip().replace({"MD 695": "IS 695"})
    pre = A.route.str.split().str[0].fillna("")
    A["sys"] = np.select([pre.eq("IS"), pre.eq("US"), pre.eq("MD"), pre.eq("RP") | (pre.eq("") & A.hwy.str.endswith("_link"))], SYSTEMS[:4], SYSTEMS[4])
    tw = set(zip(A.f.values, A.t.values)); A["twin"] = [(t_, f_) in tw for f_, t_ in zip(A.f.values, A.t.values)]
    _static["links"] = A; return A

def zones_static():
    if "zones" in _static: return _static["zones"]
    import geopandas as gpd
    Z = gpd.read_file(f"{V}/2_silo/input/zones.shp")[["zone_id", "geometry"]].to_crs("EPSG:26985")
    zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv", usecols=["ZoneId", "COUNTYFIPS"]).set_index("ZoneId").COUNTYFIPS.astype(str)
    _static["zones"] = (Z, zs); return Z, zs

def zone_of(x, y):
    import geopandas as gpd
    Z, _ = zones_static()
    P = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), crs="EPSG:26985")
    j = gpd.sjoin(P, Z, how="left", predicate="within"); j = j[~j.index.duplicated()]
    return j.zone_id.reindex(P.index).values

def dest_class(county):
    c = pd.Series(county).astype(str)
    return np.select([c.isin(CO), c.isin(["24031", "24033"]), c.str.startswith("24"), c.eq("11001")], [c, "DCsub", "MDoth", "11001"], "OTH")

def skim_static():
    if "skim" in _static: return _static["skim"]
    t = pd.read_csv(f"{V}/3_abit/skims/traveltime_auto.csv.gz"); d = pd.read_csv(f"{V}/3_abit/skims/distance_auto.csv.gz")
    n = int(max(t.FROM.max(), t.TO.max())) + 1
    T = np.full((n, n), np.nan, np.float32); T[t.FROM.values, t.TO.values] = t.VALUE.values
    D = np.full((n, n), np.nan, np.float32); D[d.FROM.values, d.TO.values] = d.VALUE.values
    _static["skim"] = (T, D); return T, D

def stations_static():
    """Mainline count stations (validate_counts rules for the links of a station) and the hourly counters."""
    if "st" in _static: return _static["st"]
    S = pd.read_csv(f"{H}/previews/seed1_final/data/stations_model_vs_count.csv", dtype={"link_NE": str, "link_SW": str, "LOCATION_ID": str})
    ids = []
    for r in S.itertuples():
        ne = r.link_NE if isinstance(r.link_NE, str) and r.link_NE else None; sw = r.link_SW if isinstance(r.link_SW, str) and r.link_SW else None
        if r.use != "mainline": ids.append([]); continue
        if r.NE_SPLIT in (0, 100) or r.SW_SPLIT in (0, 100):
            want = ne if r.NE_SPLIT == 100 else sw if r.SW_SPLIT == 100 else None; ids.append([want] if want else [x for x in (ne, sw) if x])
        else: ids.append([x for x in (ne, sw) if x])
    S["ids"] = ids; S = S[S.use == "mainline"].copy()
    TG = pd.read_csv(f"{PRICING_HOME}/data/corridor_fit/targets_v7.csv"); TG = TG[(TG.kind == "hourly") & (TG.hour >= 0)]
    CL = TG.drop_duplicates("station")[["station", "links"]].copy(); CL["ids"] = CL.links.astype(str).str.replace("|", ";").str.split(";")
    CH = pd.read_csv(f"{H}/previews/seed1_final/data/counters_hourly.csv", dtype={"mdot_station": str})
    _static["st"] = (S, CL, CH); return S, CL, CH

# ------------------------------------------------------------------------------------------------ per seed
def seed_link_volumes(d, s):
    """Daily car volume per link (hours 0-24), x EXP: final link statistics averaged over the last 5 iterations minus transit
    vehicles of the final iteration (as validate_counts.py); fallback: final-iteration car volume of output_links."""
    it = max(int(re.search(r"it\.(\d+)", p).group(1)) for p in glob.glob(f"{d}/ITERS/it.*"))
    lsf = f"{d}/ITERS/it.{it}/{it}.linkstats.txt.gz"; lh = f"{H}/data/link_hours/link_hours_s{s}.csv.gz"
    if os.path.exists(lsf) and os.path.exists(lh):
        HRS = [f"HRS{h}-{h+1}avg" for h in range(24)]
        LS = pd.read_csv(lsf, sep="\t", dtype={"LINK": str}, usecols=["LINK"] + HRS).set_index("LINK").sum(1)
        E = pd.read_csv(lh, dtype={"link": str}); E = E[E.hour < 24]; pt = (E.bus + E.pt_other).groupby(E.link).sum()
        return ((LS - pt.reindex(LS.index).fillna(0)).clip(lower=0) * EXP), "linkstats avg it 96-100 minus transit, hours 0-24"
    L = pd.read_csv(f"{d}/output_links.csv.gz", sep=";", usecols=["link", "vol_car"], dtype={"link": str}).set_index("link").vol_car
    return L * EXP, "output_links vol_car (final iteration, whole simulation)"

def seed_vmt(d, s, C):
    A = links_static(); vol, src = seed_link_volumes(d, s)
    A = A.join(vol.rename("vol"), how="left"); A["vol"] = A.vol.fillna(0); A["vmt"] = A.vol * A.length / 1609.344
    out = A.groupby(["county", "fc"]).vmt.sum().reset_index(); out.to_csv(f"{C}/vmt_county_fc.csv", index=False)
    A.groupby(["county", "sys", "route"]).vmt.sum().reset_index().to_csv(f"{C}/vmt_county_route.csv", index=False)
    S, CL, _ = stations_static()
    st = pd.DataFrame({"LOCATION_ID": S.LOCATION_ID.values, "linkstats_car": [vol.reindex(i).fillna(0).sum() for i in S.ids]})
    st.to_csv(f"{C}/stations_linkstats.csv", index=False)
    json.dump({"volume_source": src}, open(f"{C}/meta.json", "w"))

def read_trips(d):
    T = pd.read_csv(f"{d}/output_trips.csv.gz", sep=";", usecols=["person", "trip_number", "dep_time", "trav_time", "traveled_distance", "main_mode",
                    "start_activity_type", "end_activity_type", "start_x", "start_y", "end_x", "end_y"], dtype={"person": str})
    T["dep"] = hms(T.dep_time); T["tt"] = hms(T.trav_time) / 60; T["dist_km"] = T.traveled_distance / 1000
    P = pd.read_csv(f"{d}/output_persons.csv.gz", sep=";", usecols=["person", "age", "homeCounty", "workZone", "flow", "occupation"], dtype={"person": str, "homeCounty": str})
    return T.drop(columns=["dep_time", "trav_time"]), P

def seed_trips(d, s, C):
    T, P = read_trips(d); T = T.sort_values(["person", "trip_number"]).reset_index(drop=True)
    res = P[P.homeCounty.isin(CO)].set_index("person")
    T["county"] = T.person.map(res.homeCounty)
    # ---- 5 trip length: car-driver trips of residents
    c = T[(T.main_mode == "car") & T.county.notna()]
    pd.DataFrame({"bin": DIST_BINS, "dist": hist(c.dist_km, DIST_EDGES) * EXP}).to_csv(f"{C}/car_dist_hist.csv", index=False)
    pd.DataFrame({"bin": TIME_BINS, "time": hist(c.tt, TIME_EDGES) * EXP}).to_csv(f"{C}/car_time_hist.csv", index=False)
    (c.groupby("county").dist_km.sum() * EXP / 1.609344).rename("vmt").reset_index().to_csv(f"{C}/resident_vmt.csv", index=False)
    json.dump({"n_car_trips": int(len(c) * EXP), "mean_km": float(c.dist_km.mean()), "median_km": float(c.dist_km.median()), "mean_min": float(c.tt.mean()),
               "median_min": float(c.tt.median()), "n_trips_all_modes": int(T.county.notna().sum() * EXP)}, open(f"{C}/car_trip_stats.json", "w"))
    # ---- 2 commute: last home departure before the first work arrival of the day; time = sum of the trip times in between
    w = T[T.end_activity_type == "work"].groupby("person").trip_number.min().rename("fw")
    X = T.join(w, on="person"); X = X[X.fw.notna() & (X.trip_number <= X.fw)]
    hs = X[X.start_activity_type == "home"].groupby("person").trip_number.max().rename("hs")
    X = X.join(hs, on="person"); X = X[X.hs.notna() & (X.trip_number >= X.hs)]
    g = X.groupby("person")
    K = pd.DataFrame({"tt": g.tt.sum(), "dep": g.dep.first() % 86400 / 3600, "n": g.size(), "allcar": g.main_mode.agg(lambda m: (m == "car").all()),
                      "mset": g.main_mode.agg(lambda m: frozenset(m)), "wx": g.end_x.last(), "wy": g.end_y.last()})
    K["mcls"] = [COMMODE_OF(m) for m in K.mset]
    K = K.join(res[["homeCounty", "age"]], how="inner"); K = K[K.age >= 16]
    rows = []
    for cty in CO + ["region"]:
        k = K if cty == "region" else K[K.homeCounty == cty]
        rows += [dict(county=cty, table="B08303", bin=b, value=v) for b, v in zip(B08303_BINS, hist(k.tt, B08303_EDGES) * EXP)]
        rows += [dict(county=cty, table="B08302", bin=b, value=v) for b, v in zip(B08302_BINS, hist(k.dep, B08302_EDGES) * EXP)]
        rows += [dict(county=cty, table="B08134_alone", bin=b, value=v) for b, v in zip(B08134_BINS, hist(k[k.allcar].tt, B08134_EDGES) * EXP)]
        rows += [dict(county=cty, table="B08301_mode", bin=b, value=(k.mcls == b).sum() * EXP) for b in COMMODE]
        rows += [dict(county=cty, table=f"mean_mode", bin=b, value=k[k.mcls == b].tt.mean()) for b in COMMODE]
        rows += [dict(county=cty, table="median_all", bin="median", value=k.tt.median()), dict(county=cty, table="median_alone", bin="median", value=k[k.allcar].tt.median())]
        rows += [dict(county=cty, table="mean_all", bin="mean", value=k.tt.mean()), dict(county=cty, table="mean_alone", bin="mean", value=k[k.allcar].tt.mean()),
                 dict(county=cty, table="workers", bin="n", value=len(k) * EXP), dict(county=cty, table="workers_alone", bin="n", value=k.allcar.sum() * EXP)]
    pd.DataFrame(rows).to_csv(f"{C}/commute.csv", index=False)
    # ---- 7 OD: home county -> county of the first work place of the day (all modes), resident workers 16+ with a work trip
    _, zs = zones_static()
    K["wzone"] = zone_of(K.wx.values, K.wy.values); K["wcounty"] = K.wzone.map(zs).fillna("OTH")
    K["dest"] = dest_class(K.wcounty.values)
    K.groupby(["homeCounty", "dest"]).size().mul(EXP).rename("value").reset_index().to_csv(f"{C}/od_worktrips.csv", index=False)
    # ---- 3 skim consistency: car trips (all persons) by period, origin and destination zone, distinct zones
    rows = []
    cc = T[(T.main_mode == "car") & (T.tt > 0)].copy(); cc["h"] = cc.dep % 86400 / 3600
    cc["per"] = None
    for p, (a, b) in PERIODS.items(): cc.loc[(cc.h >= a) & (cc.h < b), "per"] = p
    cc = cc[cc.per.notna()].copy()
    cc["oz"] = zone_of(cc.start_x.values, cc.start_y.values); cc["dz"] = zone_of(cc.end_x.values, cc.end_y.values)
    cc = cc[cc.oz.notna() & cc.dz.notna() & (cc.oz != cc.dz)]
    Tm, Dm = skim_static(); o = cc.oz.astype(int).values; dd = cc.dz.astype(int).values
    cc["skim_min"] = Tm[o, dd]; cc["skim_km"] = Dm[o, dd] / 1000; cc = cc[cc.skim_min > 0]
    cc[["per", "oz", "dz", "tt", "dist_km", "skim_min", "skim_km"]].astype({"oz": int, "dz": int}).round(2).to_csv(f"{C}/skim_trips.csv.gz", index=False, compression="gzip")

def seed_transit(d, s, C):
    L = pd.read_csv(f"{d}/output_legs.csv.gz", sep=";", usecols=["person", "mode", "transit_line", "transit_route"], dtype=str)
    L = L[L["mode"] == "pt"]
    L.groupby("transit_line").size().mul(EXP).rename("boardings").reset_index().to_csv(f"{C}/transit_lines.csv", index=False)

def seed_plans(d, s, C):
    """Stream the selected plans: car-leg volumes by purpose and hour at the station and counter links, and VMT by purpose,
    county and hour on the six-county links (link entry time interpolated along the route by free-flow time, scaled to the leg's
    travel time; the start link is not entered, as in the link statistics)."""
    A = links_static(); S, CL, _ = stations_static()
    net = pd.read_csv(f"{d}/output_links.csv.gz", sep=";", usecols=["link", "length", "freespeed"], dtype={"link": str})
    tt0 = dict(zip(net.link.values, (net.length / net.freespeed.clip(lower=0.5)).values))
    cidx = {c: i for i, c in enumerate(CO)}
    reg = {l: (ln / 1609.344, cidx[c]) for l, ln, c in zip(A.index.values, A.length.values, A.county.values)}
    target = set(x for i in S.ids for x in i) | set(x for i in CL.ids for x in i)
    vol = collections.Counter(); vmt = np.zeros((len(PURP), len(CO), 30)); nleg = 0
    def purpose(a, b):
        if a == "home" or b == "home":
            o = b if a == "home" else a
            return {"work": 0, "education": 1, "shopping": 2}.get(o, 3)
        return 4
    def t2s(x):
        h, m, s_ = x.split(":"); return int(h) * 3600 + int(m) * 60 + float(s_)
    rx_type = re.compile(r'type="([^"]+)"'); rx_dep = re.compile(r'dep_time="([^"]+)"'); rx_tt = re.compile(r'trav_time="([^"]+)"')
    sel = False; prev = None; pending = []; leg = None
    t0 = time.time()
    with gzip.open(f"{d}/output_plans.xml.gz", "rt") as f:
        for line in f:
            ls = line.lstrip()
            if ls.startswith("<plan "):
                sel = 'selected="yes"' in ls; prev = None; pending = []; leg = None; continue
            if not sel: continue
            if ls.startswith("<activity "):
                t = rx_type.search(ls).group(1)
                if t.endswith("interaction"): continue
                if prev is not None:
                    for dep, trv, route in pending:
                        p = purpose(prev, t); ids = route.split(); nleg += 1
                        if len(ids) < 2: continue
                        tts = np.fromiter((tt0.get(x, 1.0) for x in ids), float, len(ids)); cum = np.concatenate([[0], np.cumsum(tts)])
                        sc = (trv / cum[-1]) if cum[-1] > 0 and trv > 0 else 1.0
                        for i in range(1, len(ids)):
                            x = ids[i]; r = reg.get(x)
                            if r is None and x not in target: continue
                            hr = min(int((dep + cum[i] * sc) // 3600), 29)
                            if r is not None: vmt[p, r[1], hr] += r[0]
                            if x in target: vol[(x, p, hr)] += 1
                pending = []; prev = t
            elif ls.startswith("<leg "):
                leg = (t2s(rx_dep.search(ls).group(1)), t2s(rx_tt.search(ls).group(1))) if 'mode="car"' in ls else None
            elif leg is not None and ls.startswith("<route ") and 'type="links"' in ls:
                pending.append((leg[0], leg[1], ls[ls.index(">") + 1: ls.index("</route>")])); leg = None
            elif ls.startswith("</plan>"): sel = False
    V_ = pd.DataFrame([(l, PURP[p], h, n * EXP) for (l, p, h), n in vol.items()], columns=["link", "purpose", "hour", "vol"])
    V_.to_csv(f"{C}/plans_link_purpose_hour.csv.gz", index=False, compression="gzip")
    rows = [(PURP[p], CO[c], h, vmt[p, c, h] * EXP) for p in range(len(PURP)) for c in range(len(CO)) for h in range(30) if vmt[p, c, h] > 0]
    pd.DataFrame(rows, columns=["purpose", "county", "hour", "vmt"]).to_csv(f"{C}/plans_vmt_purpose.csv", index=False)
    print(f"  plans s{s}: {nleg:,} car legs, {time.time() - t0:.0f} s")

def run_seed(root, s, out, force):
    d = f"{root}/2024_s{s}"; C = f"{out}/data/seeds/s{s}"; os.makedirs(C, exist_ok=True)
    steps = [("vmt_county_route.csv", seed_vmt), ("resident_vmt.csv", seed_trips), ("transit_lines.csv", seed_transit), ("plans_vmt_purpose.csv", seed_plans)]
    redo_vmt = os.path.exists(f"{C}/meta.json") and json.load(open(f"{C}/meta.json"))["volume_source"].startswith("output_links") and os.path.exists(f"{H}/data/link_hours/link_hours_s{s}.csv.gz")
    for f, fn in steps:
        if force or not os.path.exists(f"{C}/{f}") or (fn is seed_vmt and redo_vmt):
            t0 = time.time(); fn(d, s, C); print(f"seed {s}: {fn.__name__} {time.time() - t0:.0f} s")

# ------------------------------------------------------------------------------------------------ observed
def obs_vmt():
    """MDOT SHA 2024 annual VMT (millions) by county x functional class (rural + urban), to weekday passenger VMT per day."""
    txt = open(f"{V}/data/raw/mdot_vmt/m24.txt").read().splitlines()
    i0 = next(i for i, l in enumerate(txt) if "FCAVMT-ALL" in l and "OFFICE OF PLANNING" in l)
    rows = []
    for l in txt[i0:]:
        m = re.match(r"^([A-Z][A-Z .']+?)\s{2,}([\d,\s]+)$", l.strip())
        if m and m.group(1).strip() in MDOT_NAME:
            v = [float(x.replace(",", "")) for x in m.group(2).split()]
            if len(v) != 17: continue
            for k in range(7): rows.append(dict(county=MDOT_NAME[m.group(1).strip()], fc_code=k + 1, annual_mvmt=v[k] + v[8 + k]))
        if l.strip().startswith("GRAND TOTAL"): break
    O = pd.DataFrame(rows); O["fc"] = O.fc_code.map(FCG)
    # weekday factor and passenger share by class from the region's 2024 count stations (MDOT SHA AADT/AAWDT, classification)
    S = pd.read_csv(f"{H}/previews/seed1_final/data/stations_model_vs_count.csv")
    S["fc"] = S.F_SYSTEM.map(FCG); S["fcg"] = S.fc.replace({"Local": "Collector"})        # few local stations: pooled with collectors
    k = (S.AADT_2024 > 0) & (S.AAWDT_2024 > 0)
    f = S[k].groupby("fcg").apply(lambda x: pd.Series({"wkday_factor": x.AAWDT_2024.sum() / x.AADT_2024.sum(), "stations": len(x)}))
    p = S[S.has_cls.astype(bool)].groupby("fcg").apply(lambda x: pd.Series({"pass_share": ((1 - x.trk_sh - x.bus_sh) * x.count_all).sum() / x.count_all.sum(), "classified": len(x)}))
    F = f.join(p); F.loc["Local"] = F.loc["Collector"]
    O = O.join(F, on="fc"); O["daily_all"] = O.annual_mvmt * 1e6 / 365
    O["wkday_all"] = O.daily_all * O.wkday_factor; O["wkday_pass"] = O.wkday_all * O.pass_share
    return O.groupby(["county", "fc"]).agg(annual_mvmt=("annual_mvmt", "sum"), daily_all=("daily_all", "sum"), wkday_all=("wkday_all", "sum"), wkday_pass=("wkday_pass", "sum"),
                                         wkday_factor=("wkday_factor", "first"), pass_share=("pass_share", "first")).reset_index(), F.reset_index()

def acs_load():
    rows = []
    for f in glob.glob(f"{V}/data/raw/acs_api/ACSDT*Y2024_*_*.json"):
        ds, t, c = re.search(r"(ACSDT\dY2024)_(B\d+)_(\d+)\.json", f).groups()
        try: d = json.load(open(f))["response"]["data"]
        except Exception: continue
        h, v = d[0], d[1]
        for k, x in zip(h, v):
            if re.fullmatch(r"B\d+_\d{3}[EM]", k):
                try: rows.append(dict(ds=ds, table=t, county=c, var=k[:-1], kind=k[-1], value=float(x)))
                except (TypeError, ValueError): pass
    A = pd.DataFrame(rows); E = A[A.kind == "E"].pivot_table(index=["ds", "county"], columns="var", values="value").reset_index()
    M = A[A.kind == "M"].pivot_table(index=["ds", "county"], columns="var", values="value").reset_index()
    return E, M

def obs_commute():
    E, M = acs_load(); out = []
    def row(ds, cty, tab, bins, vars_):
        e = E[(E.ds == ds) & (E.county == cty)]
        if not len(e) or any(v not in e for v in vars_) or e[vars_].isna().any(axis=None): return
        for b, v in zip(bins, vars_):
            m = M[(M.ds == ds) & (M.county == cty)]; out.append(dict(county=cty, table=tab, bin=b, value=float(e[v].iloc[0]), moe=float(m[v].iloc[0]) if v in m else np.nan, ds=ds))
    for cty in CO:
        row("ACSDT1Y2024", cty, "B08303", B08303_BINS, [f"B08303_{i:03d}" for i in range(2, 14)])
        row("ACSDT1Y2024", cty, "B08302", B08302_BINS, [f"B08302_{i:03d}" for i in range(2, 16)])
        row("ACSDT5Y2024", cty, "B08134_alone", B08134_BINS, [f"B08134_{i:03d}" for i in range(22, 31)])
        e = E[(E.ds == "ACSDT5Y2024") & (E.county == cty)]
        if len(e):
            e = e.iloc[0]
            for b, v in zip(COMMODE, [e.B08301_003, e.B08301_004, e.B08301_010, e.B08301_019, e.B08301_018]): out.append(dict(county=cty, table="B08301_mode", bin=b, value=float(v), ds="ACSDT5Y2024"))
        for ds in ["ACSDT5Y2024", "ACSDT1Y2024"]:
            e = E[(E.ds == ds) & (E.county == cty)]
            if len(e) and "B08136_001" in e and "B08134_001" in e and pd.notna(e.B08136_001.iloc[0]):
                out.append(dict(county=cty, table="mean_all", bin="mean", value=float(e.B08136_001.iloc[0] / e.B08134_001.iloc[0]), ds=ds))
                out.append(dict(county=cty, table="mean_alone", bin="mean", value=float(e.B08136_003.iloc[0] / e.B08134_021.iloc[0]), ds=ds))
                out.append(dict(county=cty, table="workers", bin="n", value=float(e.B08134_001.iloc[0]), ds=ds))
                out.append(dict(county=cty, table="workers_alone", bin="n", value=float(e.B08134_021.iloc[0]), ds=ds))
    O = pd.DataFrame(out)
    reg = O[O.table.isin(["B08303", "B08302", "B08134_alone", "B08301_mode", "workers", "workers_alone"])].groupby(["table", "bin", "ds"], sort=False).value.sum().reset_index().assign(county="region")
    O = pd.concat([O, reg])
    for ds in ["ACSDT5Y2024", "ACSDT1Y2024"]:
        x = E[(E.ds == ds) & E.county.isin(CO)]
        if len(x) == 6 and x[["B08136_001", "B08134_001"]].notna().all(axis=None):
            O = pd.concat([O, pd.DataFrame([dict(county="region", table="mean_all", bin="mean", value=x.B08136_001.sum() / x.B08134_001.sum(), ds=ds),
                                            dict(county="region", table="mean_alone", bin="mean", value=x.B08136_003.sum() / x.B08134_021.sum(), ds=ds)])])
    return O

def obs_transit():
    """NTD Annual Data, Service by Mode and Time Period, MTA Maryland: 'Average Typical Weekday' unlinked passenger trips, all types
    of service of the mode (directly operated and purchased), report years 2023 and 2024.  2017/18 equivalent: the 2024 typical weekday
    x mean annual UPT 2017-2018 / annual UPT 2024 of the mode (NTD Complete Monthly Ridership), i.e. the weekday share of the annual
    total held at its 2024 value; a conversion of observed data only."""
    d = pd.DataFrame(json.load(open(f"{V}/data/raw/ntd_2024/ntd_service_mode_time_30034.json")))
    d["upt"] = pd.to_numeric(d.unlinked_passenger_trips_upt, errors="coerce")
    U = pd.read_csv(f"{V}/data/raw/ntd_2024/ntd_mta_annual_upt_by_mode.csv").set_index("mode")   # NTD monthly ridership, annual sums
    rows = []
    for g, ntd in NTD_MODE.items():
        x = d[d["mode"] == ntd]; r = dict(group=g)
        for y in ["2023", "2024"]:
            r[f"awd_{y}"] = float(x[(x.report_year == y) & (x.time_period == "Average Typical Weekday")].upt.sum())
            r[f"upt_{y}"] = float(x[(x.report_year == y) & (x.time_period == "Annual Total")].upt.sum())
            r[f"flag_{y}"] = ",".join(sorted(set(x[(x.report_year == y)].unlinked_passenger_trips_questionable.dropna())))
        a = U.loc[ntd]; r["upt_ratio_1718"] = float((a["2017"] + a["2018"]) / 2 / a["2024"]); r["awd_1718"] = r["awd_2024"] * r["upt_ratio_1718"]
        rows.append(r)
    return pd.DataFrame(rows)

def obs_triplength():
    R = pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv", usecols=["tripid", "household_id", "travel_mode", "distance", "reported_travel_time", "wttrdfin"])
    HC = pd.read_csv(f"{ABIT_HOME}/input/rts/RTS_raw_flat_data.csv", usecols=["tripid", "home_state_county_fips"]).drop_duplicates("tripid")
    R = R.merge(HC, on="tripid", how="left"); R["hc"] = R.home_state_county_fips.astype("Int64").astype(str).str.zfill(5)
    R = R[R.travel_mode.isin([3, 4]) & R.hc.isin(CO) & (R.wttrdfin > 0)]
    rd = R[R.distance > 0]; rt = R[R.reported_travel_time > 0]
    out = dict(rts=dict(dist=hist(rd.distance * 1.609344, DIST_EDGES, rd.wttrdfin), time=hist(rt.reported_travel_time, TIME_EDGES, rt.wttrdfin),
                        n=int(len(R)), mean_km=float(np.average(rd.distance * 1.609344, weights=rd.wttrdfin)), median_km=wq(rd.distance * 1.609344, rd.wttrdfin, 0.5),
                        mean_min=float(np.average(rt.reported_travel_time, weights=rt.wttrdfin)), median_min=wq(rt.reported_travel_time, rt.wttrdfin, 0.5)))
    z = zipfile.ZipFile(f"{V}/data/raw/nhts/2022_csv.zip")
    N = pd.read_csv(z.open("tripv2pub.csv"), usecols=["CENSUS_D", "MSASIZE", "RAIL", "TDWKND", "DRVR_FLG", "TRPTRANS", "TRPMILES", "TRVLCMIN", "WTTRDFIN5D"])
    N = N[(N.CENSUS_D == 5) & (N.MSASIZE == 4) & (N.RAIL == 1) & (N.TDWKND == 2) & (N.DRVR_FLG == 1) & N.TRPTRANS.isin([1, 2, 3, 4]) & (N.TRPMILES > 0) & (N.TRVLCMIN > 0)]
    out["nhts"] = dict(dist=hist(N.TRPMILES * 1.609344, DIST_EDGES, N.WTTRDFIN5D), time=hist(N.TRVLCMIN, TIME_EDGES, N.WTTRDFIN5D), n=int(len(N)),
                       mean_km=float(np.average(N.TRPMILES * 1.609344, weights=N.WTTRDFIN5D)), median_km=wq(N.TRPMILES * 1.609344, N.WTTRDFIN5D, 0.5),
                       mean_min=float(np.average(N.TRVLCMIN, weights=N.WTTRDFIN5D)), median_min=wq(N.TRVLCMIN, N.WTTRDFIN5D, 0.5))
    return out

def obs_od():
    X = pd.read_excel(f"{V}/data/raw/acs_commuting_flows/table1_2016_2020.xlsx", header=None, skiprows=8, dtype=str).iloc[:, [0, 1, 4, 5, 8]]
    X.columns = ["rs", "rc", "ws", "wc", "flow"]; X = X[(X.rs == "24") & (X.rs + X.rc).isin(CO)].copy()
    X["flow"] = pd.to_numeric(X.flow, errors="coerce"); X["homeCounty"] = X.rs + X.rc
    w = X.ws.fillna("").str.strip(); ok = w.str.isdigit() & (pd.to_numeric(w, errors="coerce") <= 56)
    X["dest"] = np.where(ok, dest_class((w.str[-2:] + X.wc.fillna("").str.strip()).values), "OTH")
    A = X.groupby(["homeCounty", "dest"]).flow.sum().rename("value").reset_index().assign(src="ACS 2016–2020")
    L = []
    for f in ["md_od_main_JT00_2022", "dc_od_aux_JT00_2022", "va_od_aux_JT00_2022", "pa_od_aux_JT00_2022", "de_od_aux_JT00_2022", "wv_od_aux_JT00_2022"]:
        x = pd.read_csv(f"{V}/data/raw/lodes_od/{f}.csv.gz", usecols=["w_geocode", "h_geocode", "S000"], dtype={"w_geocode": str, "h_geocode": str})
        x["hc"] = x.h_geocode.str[:5]; x = x[x.hc.isin(CO)]; x["wc"] = x.w_geocode.str[:5]
        L.append(x.groupby(["hc", "wc"]).S000.sum().reset_index())
    L = pd.concat(L); L["dest"] = dest_class(L.wc.values)
    L = L.groupby(["hc", "dest"]).S000.sum().reset_index().rename(columns={"hc": "homeCounty", "S000": "value"}).assign(src="LODES 2022")
    return pd.concat([A, L])

# ------------------------------------------------------------------------------------------------ combine seeds
def combine(out, seeds):
    D = f"{out}/data"; R = {}
    rd = lambda s, f, **k: pd.read_csv(f"{D}/seeds/s{s}/{f}", **k).assign(seed=s)
    # 1 VMT
    ov, fac = obs_vmt(); fac.to_csv(f"{D}/vmt_factors_from_counts.csv", index=False)
    mv = pd.concat([rd(s, "vmt_county_fc.csv", dtype={"county": str}) for s in seeds])
    mv = mv.groupby(["seed", "county", "fc"]).vmt.sum().reset_index()
    ov["county"] = ov.county.astype(str)
    vc = agg_seeds(mv.rename(columns={"vmt": "value"}), ["county", "fc"]).merge(ov, on=["county", "fc"], how="outer")
    vc.to_csv(f"{D}/c1_vmt_county_fc.csv", index=False, float_format="%.6g")
    byc = agg_seeds(mv.groupby(["seed", "county"]).vmt.sum().rename("value").reset_index(), ["county"]).merge(ov.groupby("county")[["wkday_pass", "wkday_all", "daily_all"]].sum().reset_index(), on="county")
    byf = agg_seeds(mv.groupby(["seed", "fc"]).vmt.sum().rename("value").reset_index(), ["fc"]).merge(ov.groupby("fc")[["wkday_pass", "wkday_all", "daily_all"]].sum().reset_index(), on="fc")
    tot = mv.groupby("seed").vmt.sum()
    byc.to_csv(f"{D}/c1_vmt_county.csv", index=False, float_format="%.6g"); byf.to_csv(f"{D}/c1_vmt_fc.csv", index=False, float_format="%.6g")
    R["vmt"] = dict(model=float(tot.mean()), model_min=float(tot.min()), model_max=float(tot.max()), obs_pass=float(ov.wkday_pass.sum()), obs_all=float(ov.wkday_all.sum()),
                    obs_annual_daily_all=float(ov.daily_all.sum()), ratio=float(tot.mean() / ov.wkday_pass.sum()), mape_county=mape(byc["mean"], byc.wkday_pass), mape_fc=mape(byf["mean"], byf.wkday_pass))
    pv = pd.concat([rd(s, "plans_vmt_purpose.csv", dtype={"county": str}) for s in seeds])
    pvp = agg_seeds(pv.groupby(["seed", "purpose"]).vmt.sum().rename("value").reset_index(), ["purpose"]); pvp.to_csv(f"{D}/c1_vmt_purpose.csv", index=False, float_format="%.6g")
    R["vmt"]["plans_total"] = float(pv.groupby("seed").vmt.sum().mean())
    R["vmt"]["purpose_share"] = {r.purpose: float(r["mean"] / pvp["mean"].sum()) for _, r in pvp.iterrows()}
    # 2 commute
    oc = obs_commute(); oc.to_csv(f"{D}/c2_commute_observed.csv", index=False, float_format="%.6g")
    mc = pd.concat([rd(s, "commute.csv", dtype={"county": str}) for s in seeds]); mca = agg_seeds(mc, ["county", "table", "bin"])
    ocp = oc[(oc.table.isin(["B08303", "B08302", "B08134_alone", "B08301_mode"])) | ((oc.table.str.startswith("mean") | oc.table.str.startswith("workers")) & (oc.ds == "ACSDT5Y2024"))]
    C2 = mca.merge(ocp[["county", "table", "bin", "value", "moe", "ds"]].rename(columns={"value": "observed"}), on=["county", "table", "bin"], how="left")
    C2.to_csv(f"{D}/c2_commute.csv", index=False, float_format="%.6g")
    fit = []
    for cty in CO + ["region"]:
        for tab in ["B08303", "B08302", "B08134_alone", "B08301_mode"]:
            x = C2[(C2.county == cty) & (C2.table == tab)]
            if x.observed.notna().all() and len(x):
                per = [tvd(mc[(mc.seed == s) & (mc.county == cty) & (mc.table == tab)].value, x.observed) for s in seeds]
                fit.append(dict(county=cty, table=tab, tvd=tvd(x["mean"], x.observed), tvd_min=min(per), tvd_max=max(per), ks=ks(x["mean"], x.observed)))
        for tab in ["mean_all", "mean_alone"]:
            x = C2[(C2.county == cty) & (C2.table == tab)]
            if len(x) and x.observed.notna().all(): fit.append(dict(county=cty, table=tab, model=float(x["mean"].iloc[0]), model_min=float(x["min"].iloc[0]), model_max=float(x["max"].iloc[0]), observed=float(x.observed.iloc[0])))
    F2 = pd.DataFrame(fit); F2.to_csv(f"{D}/c2_commute_fit.csv", index=False, float_format="%.5g")
    m6 = F2[(F2.table == "mean_all") & F2.county.isin(CO)]
    def share(tab, bins_):
        x = C2[(C2.county == "region") & (C2.table == tab)].set_index("bin"); return float(x.loc[bins_, "mean"].sum() / x["mean"].sum()), float(x.loc[bins_, "observed"].sum() / x.observed.sum())
    dep69 = share("B08302", ["6:00", "6:30", "7:00", "7:30", "8:00", "8:30"]); pt = share("B08301_mode", ["Public transport"]); da = share("B08301_mode", ["Drove alone"])
    med = C2[(C2.county == "region") & (C2.table == "median_all")]["mean"]
    R["commute"] = dict(F2[F2.county == "region"].set_index("table").to_dict("index"), dep_6_9=dep69, pt_share=pt, drove_alone_share=da, mape_mean_all=mape(m6.model, m6.observed),
                        median_all_model=float(med.iloc[0]) if len(med) else None,
                        mape_mean_alone=mape(F2[(F2.table == "mean_alone") & F2.county.isin(CO)].model, F2[(F2.table == "mean_alone") & F2.county.isin(CO)].observed))
    # 3 skims
    sk = []
    for s in seeds:
        t = pd.read_csv(f"{D}/seeds/s{s}/skim_trips.csv.gz"); t["ratio"] = t.tt / t.skim_min
        t["band"] = pd.cut(t.skim_km, BAND_EDGES, labels=BAND_LABELS, right=False)
        for (p, b), x in t.groupby(["per", "band"], observed=True):
            sk.append(dict(seed=s, period=p, band=b, n=len(x) * EXP, q10=x.ratio.quantile(.1), q25=x.ratio.quantile(.25), median=x.ratio.median(), q75=x.ratio.quantile(.75), q90=x.ratio.quantile(.9),
                           ratio_of_sums=x.tt.sum() / x.skim_min.sum(), mean_model_min=x.tt.mean(), mean_skim_min=x.skim_min.mean(), dist_ratio=x.dist_km.sum() / x.skim_km.sum()))
        for p, x in t.groupby("per"):
            sk.append(dict(seed=s, period=p, band="all", n=len(x) * EXP, q10=x.ratio.quantile(.1), q25=x.ratio.quantile(.25), median=x.ratio.median(), q75=x.ratio.quantile(.75), q90=x.ratio.quantile(.9),
                           ratio_of_sums=x.tt.sum() / x.skim_min.sum(), mean_model_min=x.tt.mean(), mean_skim_min=x.skim_min.mean(), dist_ratio=x.dist_km.sum() / x.skim_km.sum(),
                           share_within_25=float(((x.ratio > 0.75) & (x.ratio < 1.25)).mean()), rmse_min=float(np.sqrt(((x.tt - x.skim_min) ** 2).mean()))))
    SK = pd.DataFrame(sk); SK.to_csv(f"{D}/c3_skim_by_seed.csv", index=False, float_format="%.5g")
    SKm = SK.groupby(["period", "band"], sort=False).agg(**{c: (c, "mean") for c in ["n", "q10", "q25", "median", "q75", "q90", "ratio_of_sums", "mean_model_min", "mean_skim_min", "dist_ratio", "share_within_25", "rmse_min"]},
                                                         median_min=("median", "min"), median_max=("median", "max")).reset_index()
    SKm.to_csv(f"{D}/c3_skim.csv", index=False, float_format="%.5g")
    am = SKm[(SKm.period == "AM peak (6–9 h)") & (SKm.band == "all")].iloc[0]
    R["skim"] = dict(am_median=float(am["median"]), am_ratio_of_sums=float(am.ratio_of_sums), am_within25=float(am.share_within_25), am_q10=float(am.q10), am_q90=float(am.q90),
                     am_mean_model=float(am.mean_model_min), am_mean_skim=float(am.mean_skim_min), am_dist_ratio=float(am.dist_ratio), n_am=float(am.n),
                     md_median=float(SKm[(SKm.period == "Midday (10–15 h)") & (SKm.band == "all")]["median"].iloc[0]),
                     pm_median=float(SKm[(SKm.period == "PM peak (15–19 h)") & (SKm.band == "all")]["median"].iloc[0]))
    # 4 transit
    ot = obs_transit(); tl = pd.concat([rd(s, "transit_lines.csv") for s in seeds]); tl["prefix"] = tl.transit_line.str.split(":").str[0]
    tl["group"] = tl.prefix.map(TRANSIT).fillna(tl.prefix.map(lambda p: "WMATA" if p in ("wmb", "wmr") else "Other operators"))
    tg = agg_seeds(tl.groupby(["seed", "group"]).boardings.sum().rename("value").reset_index(), ["group"]).merge(ot, on="group", how="left")
    tg.to_csv(f"{D}/c4_transit.csv", index=False, float_format="%.6g")
    tla = agg_seeds(tl.rename(columns={"boardings": "value"}), ["transit_line", "group"]); tla.to_csv(f"{D}/c4_transit_lines.csv", index=False, float_format="%.6g")
    k = tg.awd_2024.notna()
    R["transit"] = dict(mape_2024=mape(tg[k]["mean"], tg[k].awd_2024), mape_2023=mape(tg[k]["mean"], tg[k].awd_2023), model_mta=float(tg[k]["mean"].sum()), obs_mta_2024=float(tg[k].awd_2024.sum()),
                        obs_mta_2023=float(tg[k].awd_2023.sum()), obs_mta_1718=float(tg[k].awd_1718.sum()), mape_1718=mape(tg[k]["mean"], tg[k].awd_1718),
                        ratio_2024=float(tg[k]["mean"].sum() / tg[k].awd_2024.sum()), ratio_1718=float(tg[k]["mean"].sum() / tg[k].awd_1718.sum()), by_group={r["group"]: [float(r["mean"]), float(r["awd_2024"]) if pd.notna(r["awd_2024"]) else None] for _, r in tg.iterrows()})
    # 5 trip length
    otl = obs_triplength(); TLr = []
    for kind, bins, f in [("dist", DIST_BINS, "car_dist_hist.csv"), ("time", TIME_BINS, "car_time_hist.csv")]:
        m = pd.concat([rd(s, f) for s in seeds]).rename(columns={kind: "value"}); ma = agg_seeds(m, ["bin"])
        ma["rts"] = otl["rts"][kind]; ma["nhts"] = otl["nhts"][kind]; ma["kind"] = kind; TLr.append(ma)
    TL = pd.concat(TLr); TL.to_csv(f"{D}/c5_triplength.csv", index=False, float_format="%.6g")
    st = pd.DataFrame([json.load(open(f"{D}/seeds/s{s}/car_trip_stats.json")) | {"seed": s} for s in seeds])
    R["triplength"] = dict(model={c: float(st[c].mean()) for c in st if c != "seed"}, rts={k: v for k, v in otl["rts"].items() if not isinstance(v, np.ndarray)},
                           nhts={k: v for k, v in otl["nhts"].items() if not isinstance(v, np.ndarray)})
    for kind in ["dist", "time"]:
        x = TL[TL.kind == kind]
        R["triplength"][f"tvd_{kind}_rts"] = tvd(x["mean"], x.rts); R["triplength"][f"tvd_{kind}_nhts"] = tvd(x["mean"], x.nhts)
        R["triplength"][f"ks_{kind}_rts"] = ks(x["mean"], x.rts); R["triplength"][f"ks_{kind}_nhts"] = ks(x["mean"], x.nhts)
    # 6 count gap by purpose
    S, CL, CH = stations_static(); pl = pd.concat([pd.read_csv(f"{D}/seeds/s{s}/plans_link_purpose_hour.csv.gz", dtype={"link": str}).assign(seed=s) for s in seeds])
    pl24 = pl[pl.hour < 24]
    lp = pl24.groupby(["seed", "link", "purpose"]).vol.sum()
    st_rows = []
    for r in S.itertuples():
        for s in seeds:
            for p in PURP:
                v = sum(lp.get((s, l, p), 0.0) for l in r.ids); st_rows.append((r.LOCATION_ID, s, p, v))
    SP = pd.DataFrame(st_rows, columns=["LOCATION_ID", "seed", "purpose", "vol"])
    SPm = SP.groupby(["LOCATION_ID", "purpose"]).vol.mean().unstack().reindex(columns=PURP)
    St = S.set_index("LOCATION_ID")[["cls", "count_all", "count_pass", "F_SYSTEM"]].join(SPm); St["model_routes"] = St[PURP].sum(1)
    lk = pd.concat([rd(s, "stations_linkstats.csv", dtype={"LOCATION_ID": str}) for s in seeds]).groupby("LOCATION_ID").linkstats_car.mean()
    St["model_linkstats"] = lk.reindex(St.index); St.to_csv(f"{D}/c6_stations_purpose.csv", float_format="%.5g")
    cls_order = ["Interstate: I-695", "Interstate: other", "Other freeway / expressway", "Principal arterial", "Minor arterial", "Major collector", "Minor collector / local"]
    G = St.groupby("cls")[PURP + ["model_routes", "model_linkstats", "count_pass", "count_all"]].sum().reindex(cls_order); G.loc["All classes"] = G.sum()
    G["gap"] = G.count_pass - G.model_linkstats; G["gap_share"] = G.gap / G.count_pass
    G.to_csv(f"{D}/c6_class_purpose.csv", float_format="%.6g")
    # hourly counters: model by purpose and hour vs observed (all vehicles; passenger = x (1 - truck - bus share of the MDOT station))
    lph = pl24.groupby(["seed", "link", "purpose", "hour"]).vol.sum()
    sh = S.set_index("LOCATION_ID")[["trk_sh", "bus_sh", "fac"]]
    fwy = S[S.fac == "freeway"]; fwy_sh = float(((fwy.trk_sh + fwy.bus_sh) * fwy.count_all).sum() / fwy.count_all.sum())
    hrs = []
    for st_, ids in zip(CL.station, CL.ids):
        o = CH[CH.station == st_].set_index("hour")
        if not len(o): continue
        ms = o.mdot_station.dropna().iloc[0] if o.mdot_station.notna().any() else None
        nonp = float(sh.loc[ms, "trk_sh"] + sh.loc[ms, "bus_sh"]) if ms in sh.index else fwy_sh
        for h in range(24):
            row = dict(station=st_, hour=h, observed_all=float(o.observed.get(h, np.nan)), observed_pass=float(o.observed.get(h, np.nan)) * (1 - nonp), model_linkstats=float(o.model_mean.get(h, np.nan)))
            for p in PURP: row[p] = float(np.mean([sum(lph.get((s, l, p, h), 0.0) for l in ids) for s in seeds]))
            hrs.append(row)
    HR = pd.DataFrame(hrs); HR.to_csv(f"{D}/c6_counters_purpose_hour.csv", index=False, float_format="%.5g")
    HRt = HR.groupby("hour")[PURP + ["observed_all", "observed_pass", "model_linkstats"]].sum(); HRt["model_routes"] = HRt[PURP].sum(1)
    HRt.to_csv(f"{D}/c6_counters_total_hour.csv", float_format="%.6g")
    def per(hs): x = HRt.loc[list(hs)]; return dict(model=float(x.model_routes.sum()), observed_pass=float(x.observed_pass.sum()), gap=float(x.observed_pass.sum() - x.model_routes.sum()),
                                                    purpose={p: float(x[p].sum()) for p in PURP})
    R["countgap"] = dict(all=dict(model_linkstats=float(G.loc["All classes", "model_linkstats"]), model_routes=float(G.loc["All classes", "model_routes"]), count_pass=float(G.loc["All classes", "count_pass"]),
                                  gap_share=float(G.loc["All classes", "gap_share"]), purpose={p: float(G.loc["All classes", p]) for p in PURP}),
                         by_class={c: float(G.loc[c, "gap_share"]) for c in G.index},
                         counters={"night (0-6)": per(range(0, 6)), "AM (6-10)": per(range(6, 10)), "midday (10-15)": per(range(10, 15)), "PM (15-19)": per(range(15, 19)),
                                   "evening (19-24)": per(range(19, 24)), "day": per(range(24))}, n_counters=int(HR.station.nunique()), n_stations=int(len(St)))
    # 7 OD
    oo = obs_od(); oo.to_csv(f"{D}/c7_od_observed.csv", index=False)
    mo = pd.concat([rd(s, "od_worktrips.csv", dtype={"homeCounty": str, "dest": str}) for s in seeds]); moa = agg_seeds(mo, ["homeCounty", "dest"])
    OD = pd.MultiIndex.from_product([CO, OD_DEST], names=["homeCounty", "dest"]).to_frame(index=False)
    OD = OD.merge(moa, on=["homeCounty", "dest"], how="left")
    for src, lab in [("ACS 2016–2020", "acs"), ("LODES 2022", "lodes")]:
        OD = OD.merge(oo[oo.src == src][["homeCounty", "dest", "value"]].rename(columns={"value": lab}), on=["homeCounty", "dest"], how="left")
    OD = OD.fillna({"mean": 0, "min": 0, "max": 0, "acs": 0, "lodes": 0})
    for c in ["mean", "acs", "lodes"]: OD[f"{c}_sh"] = 100 * OD[c] / OD.groupby("homeCounty")[c].transform("sum")
    OD.to_csv(f"{D}/c7_od.csv", index=False, float_format="%.5g")
    fit = []
    for cty in CO:
        x = OD[OD.homeCounty == cty]; fit.append(dict(county=cty, tvd_acs=tvd(x["mean"], x.acs), tvd_lodes=tvd(x["mean"], x.lodes), own_model=float(x[x.dest == cty].mean_sh.iloc[0]),
                                                      own_acs=float(x[x.dest == cty].acs_sh.iloc[0]), own_lodes=float(x[x.dest == cty].lodes_sh.iloc[0])))
    F7 = pd.DataFrame(fit); F7.to_csv(f"{D}/c7_od_fit.csv", index=False, float_format="%.4g")
    w = OD.groupby("homeCounty")[["mean", "acs", "lodes"]].sum()
    tw = lambda c: float(sum(tvd(OD[OD.homeCounty == k]["mean"], OD[OD.homeCounty == k][c]) * w.loc[k, c] for k in CO) / w[c].sum())
    l = np.log10(OD["mean"].clip(lower=1)); la = np.log10(OD.acs.clip(lower=1)); ll = np.log10(OD.lodes.clip(lower=1)); k_ = (OD.acs > 0) & (OD["mean"] > 0)
    R["od"] = dict(tvd_acs_weighted=tw("acs"), tvd_lodes_weighted=tw("lodes"), r2_log_acs=float(np.corrcoef(l[k_], la[k_])[0, 1] ** 2),
                   r2_acs=float(np.corrcoef(OD["mean"], OD.acs)[0, 1] ** 2), r2_lodes=float(np.corrcoef(OD["mean"], OD.lodes)[0, 1] ** 2),
                   mape_flows_acs=mape(OD["mean"][OD.acs >= 1000], OD.acs[OD.acs >= 1000]), workers_model=float(OD["mean"].sum()), workers_acs=float(OD.acs.sum()), workers_lodes=float(OD.lodes.sum()),
                   own_county=F7.set_index("county")[["own_model", "own_acs", "own_lodes"]].to_dict("index"))
    R["seeds"] = seeds; R["sources"] = SOURCES
    combine_vmt_detail(D, seeds, R); combine_vmt_hex(D, seeds, R)
    R["volume_source"] = {s: json.load(open(f"{D}/seeds/s{s}/meta.json"))["volume_source"] for s in seeds}
    json.dump(R, open(f"{D}/summary.json", "w"), indent=1, default=float)
    return R

# ------------------------------------------------------------------------------------------------ check 1 in detail (vehicle miles)
CNAME_MDOT = {"ANNE ARUNDEL": "24003", "BALTIMORE": "24005", "CARROLL": "24013", "HARFORD": "24025", "HOWARD": "24027", "BALTIMORE CITY": "24510"}

def parse_fc_table(tag):
    """One county x functional-class table of the MDOT SHA 2024 Mileage Reports (rural + urban summed): FCMI-ALL (centreline miles),
    FCLM-ALL (mainline lane miles), FCAVMT-ALL / -SHA / -TOLL (annual VMT, millions)."""
    txt = open(f"{V}/data/raw/mdot_vmt/m24.txt").read().splitlines()
    i0 = next(i for i, l in enumerate(txt) if "OFFICE OF PLANNING" in l and l.strip().endswith(tag))
    rows = []
    for l in txt[i0 + 1:]:
        if l.strip().startswith("GRAND TOTAL"): break
        m = re.match(r"^([A-Z][A-Z .']+?)\s{2,}([\d,.\s]+)$", l.strip())
        if m and m.group(1).strip() in CNAME_MDOT:
            v = [float(x.replace(",", "")) for x in m.group(2).split()]
            if len(v) == 17:
                for k in range(7): rows.append(dict(county=CNAME_MDOT[m.group(1).strip()], fc_code=k + 1, value=v[k] + v[8 + k]))
    O = pd.DataFrame(rows); O["fc"] = O.fc_code.map(FCG); return O

def obs_sections(fac):
    """MDOT SHA 2024 traffic-count sections of the six counties (station points with their section limits, in miles): weekday passenger
    VMT = AAWDT 2024 x section length x (1 - truck share - bus share); shares from the station's classification, else the class mean."""
    g = json.load(open(f"{PRICING_HOME}/data/mdot_aadt_statewide_2015-2024.geojson"))
    P = pd.DataFrame([f["properties"] for f in g["features"]]); P = P[P.COUNTY_DESC.isin(CNAME_MDOT)].copy()
    P["county"] = P.COUNTY_DESC.map(CNAME_MDOT); P["len_mi"] = (P.END_SECTION - P.BEGIN_SECTION).clip(lower=0)
    P["route"] = (P.ID_PREFIX.fillna("") + " " + P.ID_RTE_NO.astype("Int64").astype(str)).replace({"MD 695": "IS 695"})
    pre = P.ID_PREFIX.fillna("")
    P["sys"] = np.select([pre.eq("IS"), pre.eq("US"), pre.eq("MD"), pre.eq("RP")], SYSTEMS[:4], SYSTEMS[4])
    P["fcg"] = P.F_SYSTEM.map(FCG).replace({"Local": "Collector"}).fillna("Collector")
    F = fac.set_index("fcg")
    wk = P.AAWDT_2024.where(P.AAWDT_2024 > 0, P.AADT_2024 * P.fcg.map(F.wkday_factor))
    cls = P.CAR_AADT.notna() & P.SINGLE_UNIT_AADT.notna() & (P.AADT > 0)
    ps_ = np.where(cls, 1 - (P.SINGLE_UNIT_AADT.fillna(0) + P.COMBINATION_UNIT_AADT.fillna(0) + P.BUS_AADT.fillna(0)) / P.AADT, np.nan)
    P["pass_share"] = pd.Series(ps_, index=P.index).fillna(P.fcg.map(F.pass_share))
    P["wkday_pass_vmt"] = wk * P.len_mi * P.pass_share
    return P[["LOCATION_ID", "county", "route", "sys", "F_SYSTEM", "MAIN_LINE", "len_mi", "AAWDT_2024", "AADT_2024", "pass_share", "wkday_pass_vmt"]]

def population():
    p24 = pd.read_csv(f"{V}/data/raw/pep/co-est2024-alldata.csv", encoding="latin-1"); p20 = pd.read_csv(f"{V}/data/raw/pep/co-est2020-alldata.csv", encoding="latin-1")
    f = lambda d, c: d[d.STATE == 24].assign(county=lambda x: "24" + x.COUNTY.astype(int).astype(str).str.zfill(3)).set_index("county")[c]
    return pd.DataFrame({"pop2024": f(p24, "POPESTIMATE2024"), "pop2018": f(p20, "POPESTIMATE2018")}).reindex(CO)

def rts_resident_vmt():
    """RTS 2017/18 weighted car-driver miles per weekday by household home county (distance = routed miles between reported addresses)."""
    R = pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv", usecols=["tripid", "travel_mode", "distance", "wttrdfin"])
    HC = pd.read_csv(f"{ABIT_HOME}/input/rts/RTS_raw_flat_data.csv", usecols=["tripid", "home_state_county_fips"]).drop_duplicates("tripid")
    R = R.merge(HC, on="tripid"); R["hc"] = R.home_state_county_fips.astype("Int64").astype(str).str.zfill(5)
    R = R[R.travel_mode.isin([3, 4]) & R.hc.isin(CO) & (R.distance > 0) & (R.wttrdfin > 0)]
    return (R.distance * R.wttrdfin).groupby(R.hc).sum().reindex(CO)

def route_coverage(A):
    """Share of the length of each route (MDOT SHA functional-class segments in the six counties, sampled every 100 m) that has a network
    link carrying the same MDOT route identifier within 30 m."""
    import geopandas as gpd, shapely
    FC = gpd.read_file(f"{V}/data/raw/mdot_sha/functional_class.geojson", columns=["COUNTY_NAME", "ID_PREFIX", "ID_RTE_NO"])
    FC = FC[FC.COUNTY_NAME.isin(CNAME_MDOT) & FC.geometry.notna()].copy()
    FC["route"] = (FC.ID_PREFIX.fillna("") + " " + FC.ID_RTE_NO.astype("Int64").astype(str)).replace({"MD 695": "IS 695"})
    out = []
    for lab, keys in ROUTES:
        segs = FC[FC.route.isin(keys)].geometry.explode(index_parts=False).values
        L = A[A.route.isin(keys)]
        if not len(segs) or not len(L): out.append(dict(route=lab, coverage=np.nan, mdot_km=np.nan)); continue
        pts = []
        for g_ in segs:
            n = max(1, int(g_.length // 100)); pts += list(shapely.line_interpolate_point(g_, (np.arange(n) + 0.5) / n, normalized=True))
        geoms = shapely.linestrings(np.stack([np.stack([L.x0.values, L.y0.values], 1), np.stack([L.x1.values, L.y1.values], 1)], 1))
        tree = shapely.STRtree(geoms); idx = tree.query_nearest(np.array(pts), max_distance=30)
        out.append(dict(route=lab, coverage=len(set(idx[0].tolist())) / len(pts), mdot_km=float(sum(g_.length for g_ in segs)) / 1000))
    return pd.DataFrame(out)

def combine_vmt_detail(D, seeds, R):
    rd = lambda s, f, **k: pd.read_csv(f"{D}/seeds/s{s}/{f}", **k).assign(seed=s)
    ov, fac = obs_vmt(); A = links_static()
    mv = pd.concat([rd(s, "vmt_county_fc.csv", dtype={"county": str}) for s in seeds])
    # (a) county x class matrix with margins
    M = agg_seeds(mv.rename(columns={"vmt": "value"}), ["county", "fc"]).merge(ov[["county", "fc", "wkday_pass"]], on=["county", "fc"], how="outer").fillna({"mean": 0})
    M["ratio"] = M["mean"] / M.wkday_pass.replace(0, np.nan)
    M.to_csv(f"{D}/c1a_vmt_matrix.csv", index=False, float_format="%.6g")
    k = M.wkday_pass > 0; R["vmt"]["mape_matrix"] = mape(M[k]["mean"], M[k].wkday_pass)
    # (b) road system: observed Interstate / US / MD from the 2024 count sections; county, municipal and other = FCAVMT-ALL total minus those
    sec = obs_sections(fac); sec.to_csv(f"{D}/c1_obs_sections.csv", index=False, float_format="%.5g")
    mr = pd.concat([rd(s, "vmt_county_route.csv", dtype={"county": str}).fillna({"route": ""}) for s in seeds])
    ms = agg_seeds(mr.groupby(["seed", "county", "sys"]).vmt.sum().rename("value").reset_index(), ["county", "sys"])
    os_ = sec[sec["sys"].isin(SYSTEMS[:4])].groupby(["county", "sys"]).wkday_pass_vmt.sum().rename("observed").reset_index()
    tot = ov.groupby("county").wkday_pass.sum()
    loc = (tot - os_[os_["sys"].isin(SYSTEMS[:3])].groupby("county")["observed"].sum().reindex(tot.index).fillna(0)).rename("observed").reset_index().assign(sys=SYSTEMS[4])
    SY = ms.merge(pd.concat([os_, loc]), on=["county", "sys"], how="outer"); SY["ratio"] = SY["mean"] / SY.observed
    SY.to_csv(f"{D}/c1b_vmt_system.csv", index=False, float_format="%.6g")
    sr = SY.groupby("sys")[["mean", "observed"]].sum().reindex(SYSTEMS); sr["ratio"] = sr["mean"] / sr.observed
    gap = (sr.observed - sr["mean"]).drop("Ramp")
    R["vmt"]["system"] = {k_: dict(model=float(r["mean"]), observed=float(r.observed), ratio=float(r.ratio)) for k_, r in sr.iterrows()}
    R["vmt"]["gap_share_local"] = float(gap[SYSTEMS[4]] / gap.sum()); R["vmt"]["gap_share_state"] = float(gap[SYSTEMS[:3]].sum() / gap.sum())
    sha = {}
    for l in open(f"{V}/data/raw/mdot_vmt/m24.txt").read().splitlines():      # DSD-9: SHA-maintained system, annual VMT (reference)
        m = re.match(r"^\s*([A-Z][A-Z .']+?)\s{2,}[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d,]{9,})\s", l)
        if m and m.group(1).strip() in CNAME_MDOT: sha[CNAME_MDOT[m.group(1).strip()]] = float(m.group(2).replace(",", ""))
    R["vmt"]["sha_maintained_annual_vmt"] = sha
    # (c) routes
    cov = route_coverage(A); rows = []
    for lab, keys in ROUTES:
        m_ = mr[mr.route.isin(keys)].groupby("seed").vmt.sum().reindex(seeds).fillna(0)
        o_ = sec[sec.route.isin(keys) & (sec.MAIN_LINE == 1)]
        rows.append(dict(route=lab, model=float(m_.mean()), model_min=float(m_.min()), model_max=float(m_.max()), observed=float(o_.wkday_pass_vmt.sum()), obs_section_mi=float(o_.len_mi.sum()),
                         n_sections=int(len(o_))))
    RT = pd.DataFrame(rows).merge(cov, on="route"); RT["ratio"] = RT.model / RT.observed; RT = RT.sort_values("observed", ascending=False)
    RT.to_csv(f"{D}/c1c_vmt_routes.csv", index=False, float_format="%.5g")
    R["vmt"]["routes"] = dict(ratio_all=float(RT.model.sum() / RT.observed.sum()), mape=mape(RT.model, RT.observed), share_of_obs_vmt=float(RT.observed.sum() / tot.sum()))
    # (d) network coverage: lane miles and centreline miles by county x class (model without ramp links) vs FCLM-ALL / FCMI-ALL
    B = A[A["sys"] != "Ramp"].copy(); B["lane_mi"] = B.length * B.permlanes / 1609.344; B["cl_mi"] = B.length / np.where(B.twin, 2, 1) / 1609.344
    NC = B.groupby(["county", "fc"])[["lane_mi", "cl_mi"]].sum().reset_index()
    NC = NC.merge(parse_fc_table("FCLM-ALL").groupby(["county", "fc"]).value.sum().rename("mdot_lane_mi").reset_index(), on=["county", "fc"], how="outer")
    NC = NC.merge(parse_fc_table("FCMI-ALL").groupby(["county", "fc"]).value.sum().rename("mdot_cl_mi").reset_index(), on=["county", "fc"], how="outer")
    NC.to_csv(f"{D}/c1d_network_coverage.csv", index=False, float_format="%.5g")
    nf = NC.groupby("fc")[["lane_mi", "cl_mi", "mdot_lane_mi", "mdot_cl_mi"]].sum().reindex(FCORDER)
    R["vmt"]["network"] = {k_: dict(lane_ratio=float(r.lane_mi / r.mdot_lane_mi), cl_ratio=float(r.cl_mi / r.mdot_cl_mi)) for k_, r in nf.iterrows()}
    R["vmt"]["network_total"] = dict(lane_ratio=float(nf.lane_mi.sum() / nf.mdot_lane_mi.sum()), cl_ratio=float(nf.cl_mi.sum() / nf.mdot_cl_mi.sum()))
    # (e) per capita: located (link VMT in the county) and generated (residents' car-driver miles, any location)
    pop = population(); rv_ = pd.concat([rd(s, "resident_vmt.csv", dtype={"county": str}) for s in seeds]).groupby("county").vmt.agg(["mean", "min", "max"]).reindex(CO)
    lc = mv.groupby(["seed", "county"]).vmt.sum().groupby("county").agg(["mean", "min", "max"]).reindex(CO)
    rts = rts_resident_vmt()
    PC = pd.DataFrame({"pop2024": pop.pop2024, "pop2018": pop.pop2018, "located_model": lc["mean"], "located_obs": tot.reindex(CO), "generated_model": rv_["mean"],
                       "generated_model_min": rv_["min"], "generated_model_max": rv_["max"], "generated_rts": rts})
    PC["located_model_pc"] = PC.located_model / PC.pop2024; PC["located_obs_pc"] = PC.located_obs / PC.pop2024
    PC["generated_model_pc"] = PC.generated_model / PC.pop2024; PC["generated_rts_pc"] = PC.generated_rts / PC.pop2018
    PC.loc["region"] = PC.sum(); 
    for a_, b_, p_ in [("located_model_pc", "located_model", "pop2024"), ("located_obs_pc", "located_obs", "pop2024"), ("generated_model_pc", "generated_model", "pop2024"), ("generated_rts_pc", "generated_rts", "pop2018")]:
        PC.loc["region", a_] = PC.loc["region", b_] / PC.loc["region", p_]
    PC.to_csv(f"{D}/c1e_vmt_per_capita.csv", float_format="%.5g")
    R["vmt"]["per_capita"] = {c_: {k_: float(PC.loc[c_, k_]) for k_ in ["located_model_pc", "located_obs_pc", "generated_model_pc", "generated_rts_pc"]} for c_ in PC.index}
    # (f) by hour: model (selected plans, route-interpolated) vs the hourly shape of the permanent counters x observed weekday passenger VMT
    pv = pd.concat([rd(s, "plans_vmt_purpose.csv", dtype={"county": str}) for s in seeds])
    pv["h24"] = pv.hour % 24
    HV = pv.groupby(["seed", "h24", "purpose"]).vmt.sum().groupby(["h24", "purpose"]).mean().unstack().reindex(columns=PURP).fillna(0)
    HRt = pd.read_csv(f"{D}/c6_counters_total_hour.csv").set_index("hour")
    HV["model"] = HV[PURP].sum(1); HV["obs_shape"] = HRt.observed_pass / HRt.observed_pass.sum(); HV["observed_implied"] = HV.obs_shape * tot.sum()
    HV.index.name = "hour"; HV.to_csv(f"{D}/c1f_vmt_hour.csv", float_format="%.6g")
    per = lambda hs: dict(model=float(HV.loc[list(hs), "model"].sum()), observed=float(HV.loc[list(hs), "observed_implied"].sum()))
    R["vmt"]["by_period"] = {"night 0-6": per(range(6)), "AM 6-10": per(range(6, 10)), "midday 10-15": per(range(10, 15)), "PM 15-19": per(range(15, 19)), "evening 19-24": per(range(19, 24))}
    R["vmt"]["model_after_midnight_share"] = float(pv[pv.hour >= 24].vmt.sum() / pv.vmt.sum())

# ------------------------------------------------------------------------------------------------ figures
def figures(out, R):
    import matplotlib.pyplot as plt, geopandas as gpd
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    import matplotlib.patheffects as pe
    D = f"{out}/data"; FG = f"{out}/figures"; os.makedirs(FG, exist_ok=True)
    LIGHT = "#86b6ef"; OUTC = ps.VARIANT; GAPC = "#f6c9b3"
    halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    def fitlab(ax, txt, low=False, left=False): ax.text(0.02 if left else 0.98, 0.03 if low else 0.97, txt, transform=ax.transAxes, ha="left" if left else "right", va="bottom" if low else "top", fontsize=ps.TICK, color=ps.INK2, path_effects=halo)
    def bars(ax, cats, m, o, lo=None, hi=None, o2=None, w=0.38, rot=False):
        x = np.arange(len(cats)); off = w / 2 if o2 is None else w * 0.67
        ww = w if o2 is None else w * 0.66
        ax.bar(x - off if o2 is None else x - off, m, ww, color=ps.MODEL, zorder=2)
        if lo is not None: ax.errorbar(x - off, m, yerr=[np.clip(np.asarray(m) - lo, 0, None), np.clip(np.asarray(hi) - m, 0, None)], fmt="none", ecolor=ps.INK, elinewidth=0.6, capsize=1.2, zorder=3)
        ax.bar(x + (off if o2 is None else 0), o, ww, color=ps.OBSERVED, zorder=2)
        if o2 is not None: ax.bar(x + off, o2, ww, facecolor="white", edgecolor=ps.OBSERVED, hatch="////", lw=0.6, zorder=2)
        ax.set_xticks(x); ax.set_xlim(-0.6, len(cats) - 0.4); ax.grid(axis="x", visible=False)
        if rot: ax.set_xticklabels(cats, rotation=45, ha="right", rotation_mode="anchor")
        else: ax.set_xticklabels(cats)
    hM = Patch(color=ps.MODEL, label="Model"); hO = Patch(color=ps.OBSERVED, label="Observed"); hE = Line2D([], [], color=ps.INK, lw=0.6, marker="_", ms=4, label="Range of the runs")
    C = gpd.read_file(f"{MATSIM_HOME}/data/bmr_counties.gpkg").to_crs("EPSG:26985"); C["GEOID"] = C.GEOID.astype(str); C = C.set_index("GEOID")
    figs = []

    # ---------------- 1 VMT
    byc = pd.read_csv(f"{D}/c1_vmt_county.csv", dtype={"county": str}).set_index("county").reindex(CO)
    byf = pd.read_csv(f"{D}/c1_vmt_fc.csv").set_index("fc").reindex(FCORDER)
    fig = ps.new_figure(3.3); gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0])
    ax0 = fig.add_subplot(gs[0]); ps.choropleth(ax0, C, byc["mean"] / byc.wkday_pass)
    for g, r in C.iterrows():
        p = r.geometry.representative_point(); ax0.text(p.x, p.y, f"{byc.loc[g, 'mean'] / byc.loc[g, 'wkday_pass']:.2f}", ha="center", va="center", fontsize=ps.TICK, color=ps.INK, path_effects=halo)
    ax0.set_title("(a)", loc="left", fontsize=ps.PANEL, fontweight="bold", color=ps.INK)
    ax1 = fig.add_subplot(gs[1]); y = np.arange(len(CO))[::-1]
    ax1.barh(y + 0.2, byc["mean"] / 1e6, 0.38, color=ps.MODEL, xerr=[(byc["mean"] - byc["min"]) / 1e6, (byc["max"] - byc["mean"]) / 1e6], error_kw=dict(elinewidth=0.6, capsize=1.2, ecolor=ps.INK))
    ax1.barh(y - 0.2, byc.wkday_pass / 1e6, 0.38, color=ps.OBSERVED); ax1.set_yticks(y); ax1.set_yticklabels([CSHORT[c] for c in CO]); ax1.grid(axis="y", visible=False)
    ax1.set_xlabel("Car miles per weekday\n(million)"); fitlab(ax1, f"MAPE {R['vmt']['mape_county']:.0f} %", low=True); ax1.set_title("(b)", loc="left", fontsize=ps.PANEL, fontweight="bold", color=ps.INK)
    ax2 = fig.add_subplot(gs[2]); y = np.arange(len(FCORDER))[::-1]
    ax2.barh(y + 0.2, byf["mean"] / 1e6, 0.38, color=ps.MODEL, xerr=[(byf["mean"] - byf["min"]) / 1e6, (byf["max"] - byf["mean"]) / 1e6], error_kw=dict(elinewidth=0.6, capsize=1.2, ecolor=ps.INK))
    ax2.barh(y - 0.2, byf.wkday_pass / 1e6, 0.38, color=ps.OBSERVED); ax2.set_yticks(y)
    ax2.set_yticklabels(["Interstate", "Other freeway", "Principal arterial", "Minor arterial", "Collector", "Local"]); ax2.grid(axis="y", visible=False)
    ax2.set_xlabel("Car miles per weekday\n(million)"); fitlab(ax2, f"MAPE {R['vmt']['mape_fc']:.0f} %", low=True); ax2.set_title("(c)", loc="left", fontsize=ps.PANEL, fontweight="bold", color=ps.INK)
    used = sorted(set(int(np.digitize(r, ps.RATIO_BINS[1:-1])) for r in (byc["mean"] / byc.wkday_pass)))
    hs = [Patch(facecolor=ps.RATIO_COLORS[i], edgecolor=ps.AXIS, lw=0.3, label=f"Model ÷ observed {ps.RATIO_LABELS[i]}") for i in used]
    fig.legend(handles=[hM, hO, hE] + hs, loc="outside upper center", ncol=3, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt"))

    # ---------------- 2 commute
    C2 = pd.read_csv(f"{D}/c2_commute.csv", dtype={"county": str}); F2 = pd.read_csv(f"{D}/c2_commute_fit.csv", dtype={"county": str})
    for tab, bins, name, xl in [("B08303", B08303_BINS, "fig_reg_commute_time", "Travel time to work (min)"), ("B08302", B08302_BINS, "fig_reg_commute_departure", "Time leaving home for work (h)"),
                                ("B08134_alone", B08134_BINS, "fig_reg_commute_time_alone", "Travel time to work, drivers alone (min)"),
                                ("B08301_mode", COMMODE, "fig_reg_commute_mode", "Means of transport to work")]:
        fig = ps.new_figure(5.6); axs = fig.subplots(3, 2, sharex=True).ravel()
        for ax, cty in zip(axs, CO):
            x = C2[(C2.county == cty) & (C2.table == tab)].set_index("bin").reindex(bins)
            sm = x["mean"].sum(); so = x.observed.sum()
            if tab == "B08302":      # bins of unequal width: share per hour of the bin
                wd = np.diff(B08302_EDGES); sm, so = sm * wd, so * wd
            bars(ax, bins, 100 * x["mean"] / sm, 100 * x.observed / so, 100 * x["min"] / sm, 100 * x["max"] / sm, rot=True)
            f = F2[(F2.county == cty) & (F2.table == tab)]
            if len(f): fitlab(ax, f"TVD {f.tvd.iloc[0]:.1f} pp")
            ax.set_title(CN[cty], loc="left", fontsize=ps.FONT, fontweight="bold", color=ps.INK)
            ax.set_ylim(0, max(float((100 * x["max"] / sm).max()), float((100 * x.observed / so).max())) * 1.22)
        for ax in axs[::2]: ax.set_ylabel("Share of workers per hour (%)" if tab == "B08302" else "Share of workers (%)")
        for ax in axs[-2:]: ax.set_xlabel(xl)
        fig.legend(handles=[hM, hO, hE], loc="outside upper center", ncol=3)
        figs.append(ps.finish(fig, f"{FG}/{name}"))
    # mean commute time by county
    fig, axs = ps.figure(2.6, ncols=2, sharey=True)
    for ax, tab, ttl in zip(axs, ["mean_all", "mean_alone"], ["All modes", "Drivers alone"]):
        f = F2[F2.table == tab].set_index("county").reindex(CO + ["region"]); y = np.arange(len(f))[::-1]
        ax.errorbar(f.model, y, xerr=[f.model - f.model_min, f.model_max - f.model], fmt="none", ecolor=ps.MODEL, elinewidth=0.7, capsize=1.5, zorder=3)
        ax.scatter(f.model, y, s=18, color=ps.MODEL, zorder=4); ax.scatter(f.observed, y, s=16, marker="s", color=ps.OBSERVED, zorder=4)
        ax.set_yticks(y); ax.set_yticklabels([CSHORT.get(c, "Region") for c in f.index]); ax.grid(axis="y", visible=False)
        ax.set_xlabel("Mean travel time to work (min)"); ax.set_title(ttl, loc="right", fontsize=ps.FONT, fontweight="normal")
        m6 = f.loc[CO]; fitlab(ax, f"MAPE {mape(m6.model, m6.observed):.0f} %", low=True, left=True); ax.set_xlim(15, max(45, float(f.model_max.max()) + 3))
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=ps.MODEL, label="Model"), Line2D([], [], marker="s", ls="", color=ps.OBSERVED, label="Observed"),
                        Line2D([], [], color=ps.MODEL, lw=0.7, label="Range of the runs")], loc="outside upper center", ncol=3)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_commute_mean", panel_labels="ab"))

    # ---------------- 3 skims
    SKm = pd.read_csv(f"{D}/c3_skim.csv"); s0 = R["seeds"][0]
    t = pd.read_csv(f"{D}/seeds/s{s0}/skim_trips.csv.gz"); t = t[t.per == "AM peak (6–9 h)"]
    fig, axs = ps.figure(3.0, ncols=2)
    hb = axs[0].hexbin(t.skim_min, t.tt, gridsize=45, extent=(0, 90, 0, 90), mincnt=1, bins="log", cmap=ps.SEQ, lw=0.1)
    axs[0].plot([0, 90], [0, 90], color=ps.OBSERVED, lw=0.9); axs[0].set_xlim(0, 90); axs[0].set_ylim(0, 90)
    axs[0].set_xlabel("Upstream car skim time (min)"); axs[0].set_ylabel("Assigned car travel time (min)")
    cb = fig.colorbar(hb, ax=axs[0], shrink=0.8, pad=0.02); cb.set_label("Trips in the sample (log)"); cb.ax.tick_params(labelsize=ps.TICK)
    ax = axs[1]; pos = np.arange(len(BAND_LABELS))
    for j, (p, col, dx) in enumerate([("AM peak (6–9 h)", ps.MODEL, -0.22), ("Midday (10–15 h)", LIGHT, 0.0), ("PM peak (15–19 h)", "#1c5cab", 0.22)]):
        x = SKm[(SKm.period == p)].set_index("band").reindex(BAND_LABELS)
        for i, r in enumerate(x.itertuples()):
            ax.add_patch(plt.Rectangle((i + dx - 0.09, r.q25), 0.18, r.q75 - r.q25, facecolor=col, edgecolor=col, lw=0.6, zorder=2))
            ax.plot([i + dx, i + dx], [r.q10, r.q25], color=col, lw=0.7, zorder=2); ax.plot([i + dx, i + dx], [r.q75, r.q90], color=col, lw=0.7, zorder=2)
            ax.plot([i + dx - 0.09, i + dx + 0.09], [r.median, r.median], color="white", lw=1.0, zorder=3)
    ax.axhline(1, color=ps.OBSERVED, lw=0.8, zorder=1); ax.set_xticks(pos); ax.set_xticklabels(BAND_LABELS); ax.set_xlim(-0.6, len(pos) - 0.4); ax.grid(axis="x", visible=False)
    ax.set_xlabel("Skim distance (km)"); ax.set_ylabel("Assigned ÷ skim car time (–)"); ax.set_ylim(0, max(2.0, SKm.q90.max() * 1.05))
    fig.legend(handles=[Line2D([], [], color=ps.OBSERVED, lw=0.9, label="Equal times"), Patch(color=ps.MODEL, label="Morning peak"), Patch(color=LIGHT, label="Midday"), Patch(color="#1c5cab", label="Evening peak")],
               loc="outside upper center", ncol=4)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_skim", panel_labels="ab"))

    # ---------------- 4 transit
    TG = pd.read_csv(f"{D}/c4_transit.csv"); order = list(TRANSIT.values()); T4 = TG.set_index("group").reindex(order)
    fig, axs = ps.figure(2.7, ncols=2)
    ax = axs[0]; x = np.arange(len(order))
    ax.bar(x - 0.27, T4["mean"] / 1e3, 0.26, color=ps.MODEL, yerr=[(T4["mean"] - T4["min"]) / 1e3, (T4["max"] - T4["mean"]) / 1e3], error_kw=dict(elinewidth=0.6, capsize=1.2, ecolor=ps.INK), zorder=2)
    ax.bar(x, T4.awd_2024 / 1e3, 0.26, color=ps.OBSERVED, zorder=2); ax.bar(x + 0.27, T4.awd_1718 / 1e3, 0.26, facecolor="white", edgecolor=ps.OBSERVED, hatch="////", lw=0.6, zorder=2)
    ax.set_yscale("log"); ax.set_ylim(1, 1500); ax.set_xticks(x); ax.set_xticklabels(["Local\nbus", "Commuter\nbus", "Light\nrail", "Metro\nsubway", "MARC\ntrain"]); ax.grid(axis="x", visible=False)
    ax.set_ylabel("Boardings per weekday (thousand)"); fitlab(ax, f"MAPE {R['transit']['mape_2024']:.0f} % (2024), {R['transit']['mape_1718']:.0f} % (2017/18)")
    ax = axs[1]; r = T4["mean"] / T4.awd_2024; ax.axhspan(0.75, 1.25, color=ps.TOL_BAND, lw=0, zorder=0); ax.axhline(1, color=ps.OBSERVED, lw=0.8)
    ax.errorbar(x, r, yerr=[r - T4["min"] / T4.awd_2024, T4["max"] / T4.awd_2024 - r], fmt="none", ecolor=ps.MODEL, elinewidth=0.7, capsize=1.5)
    ax.scatter(x, r, s=20, color=[ps.MODEL if 0.75 <= v <= 1.25 else OUTC for v in r], zorder=3)
    r2 = T4["mean"] / T4.awd_1718; ax.scatter(x + 0.18, r2, s=20, facecolor="white", edgecolor=[ps.MODEL if 0.75 <= v <= 1.25 else OUTC for v in r2], lw=0.9, zorder=3)
    ax.set_xticks(x); ax.set_xticklabels(["Local\nbus", "Commuter\nbus", "Light\nrail", "Metro\nsubway", "MARC\ntrain"]); ax.grid(axis="x", visible=False)
    ax.set_ylabel(ps.RATIO_LABEL); ax.set_ylim(0, max(2.0, float(max(r.max(), r2.max())) * 1.15))
    fig.legend(handles=[hM, Patch(color=ps.OBSERVED, label="Observed 2024"), Patch(facecolor="white", edgecolor=ps.OBSERVED, hatch="////", label="Observed, 2017/18 equivalent"), hE,
                        Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=ps.MODEL, label="Model ÷ 2017/18 equivalent"),
                        Patch(color=ps.TOL_BAND, label="±25 %"), Line2D([], [], marker="o", ls="", color=OUTC, label=ps.LEG["outside"])], loc="outside upper center", ncol=3)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_transit", panel_labels="ab"))
    # line-load map
    try:
        figs.append(transit_map(out, R, C, FG))
    except Exception as e:
        print("transit map skipped:", e)

    # ---------------- 5 trip length
    TL = pd.read_csv(f"{D}/c5_triplength.csv"); tl = R["triplength"]
    fig, axs = ps.figure(2.9, ncols=2)
    for ax, kind, bins, xl in [(axs[0], "dist", DIST_BINS, "Car-driver trip distance (km)"), (axs[1], "time", TIME_BINS, "Car-driver trip time (min)")]:
        x = TL[TL.kind == kind].set_index("bin").reindex(bins); sm = x["mean"].sum()
        bars(ax, bins, 100 * x["mean"] / sm, 100 * x.rts / x.rts.sum(), 100 * x["min"] / sm, 100 * x["max"] / sm, o2=100 * x.nhts / x.nhts.sum(), rot=True)
        ax.set_xlabel(xl); ax.set_ylabel("Share of trips (%)")
        fitlab(ax, f"TVD {tl[f'tvd_{kind}_rts']:.1f} pp (survey 2017/18)\nTVD {tl[f'tvd_{kind}_nhts']:.1f} pp (national survey 2022)")
        ax.set_ylim(0, 100 * max((x["max"] / sm).max(), (x.rts / x.rts.sum()).max(), (x.nhts / x.nhts.sum()).max()) * 1.45)
    fig.legend(handles=[hM, Patch(color=ps.OBSERVED, label="Regional survey 2017/18"), Patch(facecolor="white", edgecolor=ps.OBSERVED, hatch="////", label="National survey 2022"), hE], loc="outside upper center", ncol=4, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_triplength", panel_labels="ab"))

    # ---------------- 6 count gap by purpose
    HRt = pd.read_csv(f"{D}/c6_counters_total_hour.csv").set_index("hour"); G = pd.read_csv(f"{D}/c6_class_purpose.csv", index_col=0)
    PC = ["#0d366b", "#1c5cab", "#3987e5", "#86b6ef", "#cde2fb"]
    fig, axs = ps.figure(3.0, ncols=2)
    ax = axs[0]; hh = np.arange(24) + 0.5; base = np.zeros(24)
    for p, c in zip(PURP, PC):
        v = HRt[p].values / 1e3; ax.fill_between(hh, base, base + v, step=None, color=c, lw=0, zorder=2); base = base + v
    ax.fill_between(hh, base, np.maximum(base, HRt.observed_pass.values / 1e3), facecolor=GAPC, lw=0, zorder=1)
    ax.plot(hh, HRt.observed_pass.values / 1e3, color=ps.OBSERVED, lw=1.3, zorder=3); ax.plot(hh, HRt.observed_all.values / 1e3, color=ps.OBSERVED, lw=0.8, ls=(0, (3, 2)), zorder=3)
    ax.set_xlim(0, 24); ax.set_xticks([0, 6, 12, 18, 24]); ax.set_xlabel("Hour of the day"); ax.set_ylabel("Vehicles per hour at the\npermanent counters (thousand)")
    ax.set_ylim(0, HRt.observed_all.max() / 1e3 * 1.12)
    ax = axs[1]; cls = ["Interstate: I-695", "Interstate: other", "Other freeway / expressway", "Principal arterial", "Minor arterial", "Major collector", "Minor collector / local", "All classes"]
    labs = ["I-695", "Other interstate", "Other freeway", "Principal arterial", "Minor arterial", "Major collector", "Minor collector, local", "All classes"]
    Gx = G.reindex(cls); x = np.arange(len(cls)); base = np.zeros(len(cls))
    tot = Gx.count_pass.values
    for p, c in zip(PURP, PC):
        v = 100 * Gx[p].values / tot; ax.bar(x, v, 0.62, bottom=base, color=c, zorder=2); base = base + v
    ax.bar(x, np.clip(100 - base, 0, None), 0.62, bottom=base, facecolor=GAPC, lw=0, zorder=2)
    ax.axhline(100, color=ps.OBSERVED, lw=1.0, zorder=3); ax.set_xticks(x); ax.set_xticklabels(labs, rotation=45, ha="right", rotation_mode="anchor"); ax.set_xlim(-0.6, len(x) - 0.4); ax.grid(axis="x", visible=False)
    ax.set_ylabel("Share of the passenger count (%)"); ax.set_ylim(0, max(110, base.max() * 1.08))
    fig.legend(handles=[Patch(color=c, label=p) for p, c in zip(PURP, PC)] + [Patch(facecolor=GAPC, label="Count not reproduced (gap)"),
               Line2D([], [], color=ps.OBSERVED, lw=1.3, label="Observed, passenger vehicles"), Line2D([], [], color=ps.OBSERVED, lw=0.8, ls=(0, (3, 2)), label="Observed, all vehicles")],
               loc="outside upper center", ncol=3, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_countgap", panel_labels="ab"))

    # ---------------- 7 OD
    OD = pd.read_csv(f"{D}/c7_od.csv", dtype={"homeCounty": str, "dest": str}); F7 = pd.read_csv(f"{D}/c7_od_fit.csv", dtype={"county": str}).set_index("county")
    fig, axs = ps.figure(3.4, ncols=2, gridspec_kw=dict(width_ratios=[1.35, 1]))
    ax = axs[0]; M = OD.pivot(index="homeCounty", columns="dest", values="mean_sh").reindex(index=CO, columns=OD_DEST) - OD.pivot(index="homeCounty", columns="dest", values="acs_sh").reindex(index=CO, columns=OD_DEST)
    im = ax.imshow(M.values, cmap=ps.DIV, vmin=-ps.PP_LIM, vmax=ps.PP_LIM, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]): ax.text(j, i, f"{M.values[i, j]:+.0f}", ha="center", va="center", fontsize=ps.TICK, color=ps.INK if abs(M.values[i, j]) < 6 else "white")
    ax.set_yticks(range(len(CO))); ax.set_yticklabels([f"{CSHORT[c]} ({F7.loc[c, 'tvd_acs']:.0f})" for c in CO]); ax.set_xticks(range(len(OD_DEST)))
    ax.set_xticklabels([OD_LAB[d].replace("Montgomery, Pr. George's", "Montg., Pr. G.") for d in OD_DEST], rotation=45, ha="right", rotation_mode="anchor"); ax.grid(False)
    ax.set_xlabel("Work county"); ax.set_ylabel("Home county (TVD, pp)")
    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02); cb.set_label(ps.PP_LABEL); cb.ax.tick_params(labelsize=ps.TICK)
    ax = axs[1]; k = OD.acs > 0
    ax.scatter(OD.acs[k] / 1e3, OD["mean"][k] / 1e3, s=10, color=ps.MODEL, lw=0, zorder=3, label="Model vs ACS")
    ax.scatter(OD.lodes[k] / 1e3, OD["mean"][k] / 1e3, s=10, facecolor="white", edgecolor=ps.MODEL, lw=0.6, zorder=2, label="Model vs LODES")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.plot([0.05, 500], [0.05, 500], color=ps.OBSERVED, lw=0.8, zorder=1); ax.set_xlim(0.05, 500); ax.set_ylim(0.05, 500)
    ax.set_xlabel("Observed workers\n(thousand)"); ax.set_ylabel("Modelled workers (thousand)"); fitlab(ax, f"R² {R['od']['r2_acs']:.2f} (ACS)\nR² {R['od']['r2_lodes']:.2f} (LODES)", low=True)
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=ps.MODEL, ms=4, label="Model against ACS 2016–2020"), Line2D([], [], marker="o", ls="", mfc="white", mec=ps.MODEL, ms=4, label="Model against LODES 2022"),
                        Line2D([], [], color=ps.OBSERVED, lw=0.8, label="Model = observed")], loc="outside upper center", ncol=3, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_od", panel_labels="ab"))
    # flow map
    cen = {g: (r.geometry.representative_point().x, r.geometry.representative_point().y) for g, r in C.iterrows()}
    fig, axs = ps.figure(3.1, ncols=2)
    pairs = [(a, b) for i, a in enumerate(CO) for b in CO[i + 1:]]
    TOTW = {c: float(OD[c].sum()) for c in ["mean", "acs"]}
    val = lambda col, a, b: 100 * float(OD[(OD.homeCounty == a) & (OD.dest == b)][col].sum() + OD[(OD.homeCounty == b) & (OD.dest == a)][col].sum()) / TOTW[col]
    vmax = max(max(val(c, a, b) for a, b in pairs) for c in ["mean", "acs"])
    for ax, col, ttl, colr in [(axs[0], "mean", "Model", ps.MODEL), (axs[1], "acs", "Observed (ACS 2016–2020)", ps.OBSERVED)]:
        C.plot(ax=ax, facecolor="#f4f4f1", edgecolor=ps.AXIS, lw=0.5); ax.set_axis_off(); ax.set_aspect("equal")
        for a, b in sorted(pairs, key=lambda p: val(col, *p)):
            v = val(col, a, b); ax.plot([cen[a][0], cen[b][0]], [cen[a][1], cen[b][1]], color=colr, lw=0.3 + 6 * v / vmax, solid_capstyle="round", alpha=0.85, zorder=2)
        for g in CO:
            own = 100 * float(OD[(OD.homeCounty == g) & (OD.dest == g)][col].sum()) / TOTW[col]; ax.scatter(*cen[g], s=6 * own, color=colr, zorder=3, lw=0.5, edgecolor="white")
        ax.set_title(ttl, loc="right", fontsize=ps.FONT, fontweight="normal")
    fig.legend(handles=[Line2D([], [], color=ps.INK2, lw=0.3 + 6 * 2 / vmax, label="2 % of the resident workers commute between the two counties"),
                        Line2D([], [], marker="o", ls="", color=ps.INK2, ms=np.sqrt(6 * 10), label="10 % of the resident workers live and work in the county")], loc="outside lower center", ncol=1, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_od_map", panel_labels="ab"))

    # ---------------- overview (main text)
    def coarse(x, groups):
        return pd.DataFrame({c: [x.loc[g, c].sum() for g in groups.values()] for c in ["mean", "min", "max", "observed"] if c in x}, index=list(groups.keys()))
    fig = ps.new_figure(5.6); axs = fig.subplots(2, 3).ravel()
    ax = axs[0]; r = byc["mean"] / byc.wkday_pass; y = np.arange(len(CO))[::-1]
    ax.axvline(1, color=ps.OBSERVED, lw=0.8); ax.errorbar(r, y, xerr=[r - byc["min"] / byc.wkday_pass, byc["max"] / byc.wkday_pass - r], fmt="none", ecolor=ps.MODEL, elinewidth=0.7)
    ax.scatter(r, y, s=16, color=ps.MODEL, zorder=3); ax.set_yticks(y); ax.set_yticklabels([CSHORT[c] for c in CO]); ax.grid(axis="y", visible=False); ax.set_xlim(0, 1.2)
    ax.set_xlabel("Model ÷ observed\nweekday car miles (–)"); ax.set_title("(a) Car miles", loc="left")
    ax = axs[1]; x = C2[(C2.county == "region") & (C2.table == "B08134_alone")].set_index("bin")   # drivers alone: all-mode times carry transit-routing artefacts
    g = {"<10": ["<10"], "10–19": ["10–14", "15–19"], "20–29": ["20–24", "25–29"], "30–44": ["30–34", "35–44"], "45–59": ["45–59"], "60+": ["60+"]}
    x = coarse(x, g); sm = x["mean"].sum()
    bars(ax, list(g), 100 * x["mean"] / sm, 100 * x.observed / x.observed.sum(), 100 * x["min"] / sm, 100 * x["max"] / sm, rot=True)
    ax.set_xlabel("Time to work (min)"); ax.set_ylabel("Share of workers (%)"); ax.set_title("(b) Commute, drove alone", loc="left")
    ax.set_ylim(0, 100 * max((x["max"] / sm).max(), (x.observed / x.observed.sum()).max()) * 1.3); fitlab(ax, f"TVD {tvd(x['mean'], x.observed):.1f} pp")
    ax = axs[2]; xx = SKm[(SKm.period == "AM peak (6–9 h)")].set_index("band").reindex(BAND_LABELS)
    for i, r_ in enumerate(xx.itertuples()):
        ax.add_patch(plt.Rectangle((i - 0.25, r_.q25), 0.5, r_.q75 - r_.q25, facecolor=ps.MODEL, lw=0, zorder=2)); ax.plot([i, i], [r_.q10, r_.q90], color=ps.MODEL, lw=0.7, zorder=1)
        ax.plot([i - 0.25, i + 0.25], [r_.median, r_.median], color="white", lw=1.0, zorder=3)
    ax.axhline(1, color=ps.OBSERVED, lw=0.8); ax.set_xticks(range(len(BAND_LABELS))); ax.set_xticklabels(BAND_LABELS, rotation=45, ha="right", rotation_mode="anchor"); ax.set_xlim(-0.6, len(BAND_LABELS) - 0.4); ax.grid(axis="x", visible=False)
    ax.set_ylim(0, 1.6); ax.set_xlabel("Skim distance (km)"); ax.set_ylabel("Assigned ÷ skim time (–)"); ax.set_title("(c) Skim time", loc="left")
    ax = axs[3]; r = T4["mean"] / T4.awd_2024; x = np.arange(len(order)); ax.axhline(1, color=ps.OBSERVED, lw=0.8)
    ax.scatter(x, r, s=16, color=ps.MODEL, zorder=3); ax.errorbar(x, r, yerr=[r - T4["min"] / T4.awd_2024, T4["max"] / T4.awd_2024 - r], fmt="none", ecolor=ps.MODEL, elinewidth=0.7)
    ax.set_xticks(x); ax.set_xticklabels(["Local bus", "Commuter bus", "Light rail", "Metro", "MARC"], rotation=45, ha="right", rotation_mode="anchor"); ax.grid(axis="x", visible=False); ax.set_ylim(0, max(2.0, float(r.max()) * 1.15))
    ax.set_ylabel("Model ÷ observed\nweekday boardings (–)"); ax.set_title("(d) Transit", loc="left")
    ax = axs[4]; x = TL[TL.kind == "dist"].set_index("bin").reindex(DIST_BINS).rename(columns={"rts": "observed"})
    g = {"<5": ["<2", "2–5"], "5–10": ["5–10"], "10–20": ["10–15", "15–20"], "20–40": ["20–30", "30–40"], "40+": ["40–60", "60+"]}
    x = coarse(x, g); sm = x["mean"].sum()
    bars(ax, list(g), 100 * x["mean"] / sm, 100 * x.observed / x.observed.sum(), 100 * x["min"] / sm, 100 * x["max"] / sm, rot=True)
    fitlab(ax, f"TVD {tvd(x['mean'], x.observed):.1f} pp"); ax.set_xlabel("Car trip distance (km)"); ax.set_ylabel("Share of trips (%)"); ax.set_title("(e) Trip length", loc="left")
    ax.set_ylim(0, 100 * max((x["max"] / sm).max(), (x.observed / x.observed.sum()).max()) * 1.3)
    ax = axs[5]; base = np.zeros(24)
    for p, c in zip(PURP, PC):
        v = HRt[p].values / 1e3; ax.fill_between(hh, base, base + v, color=c, lw=0, zorder=2); base = base + v
    ax.fill_between(hh, base, np.maximum(base, HRt.observed_pass.values / 1e3), facecolor=GAPC, lw=0, zorder=1)
    ax.plot(hh, HRt.observed_pass.values / 1e3, color=ps.OBSERVED, lw=1.2, zorder=3); ax.set_xlim(0, 24); ax.set_xticks([0, 6, 12, 18, 24])
    ax.set_xlabel("Hour of the day"); ax.set_ylabel("Vehicles per hour\n(thousand)"); ax.set_title("(f) Counters", loc="left"); ax.set_ylim(0, HRt[PURP].sum(1).max() / 1e3 * 1.12)
    fig.legend(handles=[hM, hO, hE] + [Patch(color=c, label=p) for p, c in zip(PURP, PC)] + [Patch(color=GAPC, label="Count gap")], loc="outside upper center", ncol=3, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_overview"))
    return figs

def figures_vmt_detail(out, R):
    """Check 1 in detail: county x class matrix, road system, routes, network coverage, per capita, hour; and the composite."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    from matplotlib.colors import ListedColormap, BoundaryNorm
    import matplotlib.patheffects as pe
    D = f"{out}/data"; FG = f"{out}/figures"; halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    GAPC = "#f6c9b3"; PC_ = ["#0d366b", "#1c5cab", "#3987e5", "#86b6ef", "#cde2fb"]
    cmap = ListedColormap(ps.RATIO_COLORS); norm = BoundaryNorm([0, .5, .75, .9, 1.1, 1.25, 1.5, 100], cmap.N)
    hM = Patch(color=ps.MODEL, label="Model"); hO = Patch(color=ps.OBSERVED, label="Observed")
    def fitlab(ax, txt, x=0.98, y=0.97, ha="right", va="top"): ax.text(x, y, txt, transform=ax.transAxes, ha=ha, va=va, fontsize=ps.TICK, color=ps.INK2, path_effects=halo)
    def heat(ax, Mr, rows, cols, rlab, clab, fs=ps.TICK, fmt="{:.2f}"):
        v = Mr.reindex(index=rows, columns=cols).values.astype(float)
        ax.imshow(np.where(np.isfinite(v), v, np.nan), cmap=cmap, norm=norm, aspect="auto")
        for i in range(v.shape[0]):
            for j in range(v.shape[1]):
                if np.isfinite(v[i, j]):
                    k = int(np.digitize(v[i, j], ps.RATIO_BINS[1:-1])); ax.text(j, i, fmt.format(v[i, j]), ha="center", va="center", fontsize=fs, color="white" if k in (0, 1, 5, 6) else ps.INK)
                else: ax.text(j, i, "–", ha="center", va="center", fontsize=fs, color=ps.MUTED)
        ax.set_yticks(range(len(rows))); ax.set_yticklabels(rlab); ax.set_xticks(range(len(cols))); ax.set_xticklabels(clab, rotation=45, ha="right", rotation_mode="anchor"); ax.grid(False)
        for sp in ax.spines.values(): sp.set_visible(False)
        ax.tick_params(length=0)
    used_h = lambda vals: [Patch(facecolor=ps.RATIO_COLORS[i], edgecolor=ps.AXIS, lw=0.3, label=ps.RATIO_LABELS[i]) for i in sorted(set(int(np.digitize(x, ps.RATIO_BINS[1:-1])) for x in np.ravel(vals) if np.isfinite(x)))]
    FCL = ["Interstate", "Other freeway", "Principal arterial", "Minor arterial", "Collector", "Local"]
    # ---- data
    M = pd.read_csv(f"{D}/c1a_vmt_matrix.csv", dtype={"county": str})
    Mr = M.pivot(index="county", columns="fc", values="ratio")
    Mr["All classes"] = M.groupby("county")["mean"].sum() / M.groupby("county").wkday_pass.sum()
    tot_fc = M.groupby("fc")["mean"].sum() / M.groupby("fc").wkday_pass.sum(); tot_fc["All classes"] = M["mean"].sum() / M.wkday_pass.sum(); Mr.loc["region"] = tot_fc
    Mr = Mr.replace([np.inf], np.nan)
    rows_ = CO + ["region"]; rl = [CSHORT[c] for c in CO] + ["Six counties"]; cols_ = FCORDER + ["All classes"]; cl = FCL + ["All classes"]
    SY = pd.read_csv(f"{D}/c1b_vmt_system.csv", dtype={"county": str}); S4 = ["Interstate", "US route", "MD route", "County, municipal, other"]
    sr = SY.groupby("sys")[["mean", "observed"]].sum().reindex(S4)
    RT = pd.read_csv(f"{D}/c1c_vmt_routes.csv")
    NC = pd.read_csv(f"{D}/c1d_network_coverage.csv", dtype={"county": str}); nf = NC.groupby("fc")[["lane_mi", "mdot_lane_mi"]].sum().reindex(FCORDER)
    PCt = pd.read_csv(f"{D}/c1e_vmt_per_capita.csv", index_col=0, dtype={0: str}); PCt.index = PCt.index.astype(str)
    HV = pd.read_csv(f"{D}/c1f_vmt_hour.csv").set_index("hour")
    v = R["vmt"]; figs = []
    # ---- (a) matrix
    fig, ax = ps.figure(3.0); heat(ax, Mr, rows_, cols_, rl, cl)
    ax.axhline(len(CO) - 0.5, color="white", lw=2); ax.axvline(len(FCORDER) - 0.5, color="white", lw=2)
    fig.legend(handles=used_h(Mr.values), title="Model ÷ observed weekday passenger-vehicle miles", loc="outside lower center", ncol=5, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt_matrix"))
    # ---- (b) road system
    fig, axs = ps.figure(2.8, ncols=2, gridspec_kw=dict(width_ratios=[1, 1.15]))
    ax = axs[0]; x = np.arange(len(S4))
    ax.bar(x - 0.2, sr["mean"] / 1e6, 0.38, color=ps.MODEL, zorder=2); ax.bar(x + 0.2, sr.observed / 1e6, 0.38, color=ps.OBSERVED, zorder=2)
    for i, (m_, o_) in enumerate(zip(sr["mean"], sr.observed)): ax.text(i, max(m_, o_) / 1e6 + 0.4, f"{m_ / o_:.2f}", ha="center", va="bottom", fontsize=ps.TICK, color=ps.INK2)
    ax.set_xticks(x); ax.set_xticklabels(["Interstate", "US route", "MD route", "County,\nmunicipal"]); ax.grid(axis="x", visible=False)
    ax.set_ylabel("Passenger-vehicle miles\nper weekday (million)"); ax.set_ylim(0, sr.max().max() / 1e6 * 1.2)
    ax = axs[1]; Sr = SY.pivot(index="county", columns="sys", values="ratio"); heat(ax, Sr, CO, S4, [CSHORT[c] for c in CO], ["Interstate", "US route", "MD route", "County, municipal"])
    fig.legend(handles=[hM, hO] + used_h(Sr[S4].values), loc="outside upper center", ncol=4, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt_system", panel_labels="ab"))
    # ---- (c) routes
    fig, ax = ps.figure(4.4); y = np.arange(len(RT))[::-1]
    ax.barh(y + 0.2, RT.model / 1e6, 0.38, color=ps.MODEL, xerr=[(RT.model - RT.model_min) / 1e6, (RT.model_max - RT.model) / 1e6], error_kw=dict(elinewidth=0.6, capsize=1.2, ecolor=ps.INK), zorder=2)
    ax.barh(y - 0.2, RT.observed / 1e6, 0.38, color=ps.OBSERVED, zorder=2)
    for yy, r in zip(y, RT.itertuples()): ax.text(max(r.model, r.observed) / 1e6 + 0.08, yy, f"{r.ratio:.2f}", va="center", ha="left", fontsize=ps.TICK, color=ps.INK if 0.75 <= r.ratio <= 1.25 else ps.VARIANT)
    ax.set_yticks(y); ax.set_yticklabels([f"{r.route} ({100 * r.coverage:.0f} %)" for r in RT.itertuples()]); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Passenger-vehicle miles per weekday in the six counties (million)"); ax.set_xlim(0, RT[["model", "observed"]].max().max() / 1e6 * 1.15)
    fig.legend(handles=[hM, hO, Line2D([], [], color=ps.INK, lw=0.6, label="Range of the runs"), Patch(color="white", label="Label: model ÷ observed; in brackets: route length in the network")], loc="outside upper center", ncol=2, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt_routes"))
    # ---- (d) network coverage
    fig, axs = ps.figure(2.8, ncols=2, gridspec_kw=dict(width_ratios=[1, 1.25]))
    ax = axs[0]; x = np.arange(len(FCORDER))
    ax.bar(x - 0.2, nf.lane_mi / 1e3, 0.38, color=ps.MODEL, zorder=2); ax.bar(x + 0.2, nf.mdot_lane_mi / 1e3, 0.38, color=ps.OBSERVED, zorder=2)
    ax.set_xticks(x); ax.set_xticklabels(FCL, rotation=45, ha="right", rotation_mode="anchor"); ax.grid(axis="x", visible=False); ax.set_ylabel("Lane miles (thousand)")
    fitlab(ax, f"All classes: model ÷ observed {v['network_total']['lane_ratio']:.2f}", x=0.02, ha="left")
    ax.set_ylim(0, max(nf.lane_mi.max(), nf.mdot_lane_mi.max()) / 1e3 * 1.18)
    ax = axs[1]; Nr = NC.assign(r=NC.lane_mi / NC.mdot_lane_mi).pivot(index="county", columns="fc", values="r").replace([np.inf], np.nan)
    heat(ax, Nr, CO, FCORDER, [CSHORT[c] for c in CO], FCL)
    fig.legend(handles=[Patch(color=ps.MODEL, label="Network"), Patch(color=ps.OBSERVED, label="Observed")] + used_h(Nr.values), loc="outside upper center", ncol=4, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt_network", panel_labels="ab"))
    # ---- (e) per capita
    fig, axs = ps.figure(2.8, ncols=2, sharey=True); idx = CO + ["region"]; x = np.arange(len(idx)); P = PCt.reindex(idx)
    for ax, (m_, o_, ttl) in zip(axs, [("located_model_pc", "located_obs_pc", "Driven in the county (all drivers)"), ("generated_model_pc", "generated_rts_pc", "Driven by the county's residents (anywhere)")]):
        ax.bar(x - 0.2, P[m_], 0.38, color=ps.MODEL, zorder=2); ax.bar(x + 0.2, P[o_], 0.38, color=ps.OBSERVED, zorder=2)
        ax.set_xticks(x); ax.set_xticklabels([CSHORT.get(c, "Six counties") for c in idx], rotation=45, ha="right", rotation_mode="anchor"); ax.grid(axis="x", visible=False)
        ax.set_title(ttl, loc="right", fontsize=ps.TICK, fontweight="normal"); k = P.index != "region"; fitlab(ax, f"MAPE {mape(P[k][m_], P[k][o_]):.0f} %", x=0.02, ha="left")
    axs[0].set_ylabel("Car-driver miles per resident\nper weekday"); axs[0].set_ylim(0, P[["located_obs_pc", "generated_model_pc", "generated_rts_pc", "located_model_pc"]].max().max() * 1.2)
    fig.legend(handles=[hM, Patch(color=ps.OBSERVED, label="Observed: (a) MDOT SHA 2024, (b) RTS 2017/18")], loc="outside upper center", ncol=2, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt_percapita", panel_labels="ab"))
    # ---- (f) hour
    def hour_panel(ax):
        hh = np.arange(24) + 0.5; base = np.zeros(24)
        for p_, c_ in zip(PURP, PC_):
            vv = HV[p_].values / 1e6; ax.fill_between(hh, base, base + vv, color=c_, lw=0, zorder=2); base = base + vv
        ax.fill_between(hh, base, np.maximum(base, HV.observed_implied.values / 1e6), facecolor=GAPC, lw=0, zorder=1)
        ax.plot(hh, HV.observed_implied.values / 1e6, color=ps.OBSERVED, lw=1.2, zorder=3); ax.set_xlim(0, 24); ax.set_xticks([0, 6, 12, 18, 24])
        ax.set_xlabel("Hour of the day"); ax.set_ylim(0, max(base.max(), HV.observed_implied.max() / 1e6) * 1.12)
    fig, ax = ps.figure(2.8); hour_panel(ax); ax.set_ylabel("Passenger-vehicle miles\nper hour (million)")
    fig.legend(handles=[Patch(color=c_, label=p_) for p_, c_ in zip(PURP, PC_)] + [Patch(color=GAPC, label="Gap"), Line2D([], [], color=ps.OBSERVED, lw=1.2, label="Observed (counter profile)")], loc="outside right center", fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt_hour"))
    # ---- composite: vehicle miles in detail
    fig = ps.new_figure(6.6); axs = fig.subplots(3, 2, gridspec_kw=dict(hspace=0.12)).ravel()
    ax = axs[0]; heat(ax, Mr, rows_, cols_, [CSHORT[c] for c in CO] + ["Six counties"], ["Interstate", "Oth. freeway", "Princ. arterial", "Minor arterial", "Collector", "Local", "All"], fmt="{:.1f}")
    ax.set_title("(a) Model ÷ observed by class", loc="left")
    ax = axs[1]; x = np.arange(len(S4))
    ax.bar(x - 0.2, sr["mean"] / 1e6, 0.38, color=ps.MODEL, zorder=2); ax.bar(x + 0.2, sr.observed / 1e6, 0.38, color=ps.OBSERVED, zorder=2)
    for i, (m_, o_) in enumerate(zip(sr["mean"], sr.observed)): ax.text(i, max(m_, o_) / 1e6 + 0.4, f"{m_ / o_:.2f}", ha="center", va="bottom", fontsize=ps.TICK, color=ps.INK2)
    ax.set_xticks(x); ax.set_xticklabels(["Interstate", "US route", "MD route", "Local"]); ax.grid(axis="x", visible=False); ax.set_ylim(0, sr.max().max() / 1e6 * 1.25)
    ax.set_ylabel("Million miles per weekday"); ax.set_title("(b) Road system", loc="left")
    ax = axs[2]; ax.axhspan(0.75, 1.25, color=ps.TOL_BAND, lw=0, zorder=0); ax.axhline(1, color=ps.OBSERVED, lw=0.8)
    ax.scatter(RT.observed / 1e6, RT.ratio, s=14, color=[ps.MODEL if 0.75 <= r <= 1.25 else ps.VARIANT for r in RT.ratio], zorder=3)
    for r in RT.itertuples():
        if r.route in ("I-95", "I-695", "I-83", "MD 295", "US 50 / I-595"): ax.text(r.observed / 1e6 + 0.12, r.ratio, r.route, fontsize=ps.TICK, va="center", color=ps.INK2, path_effects=halo)
    ax.set_xlabel("Observed miles per weekday (million)"); ax.set_ylabel("Model ÷ observed (–)"); ax.set_ylim(0, 1.5); ax.set_xlim(0, RT.observed.max() / 1e6 * 1.3); ax.set_title("(c) Main routes", loc="left")
    ax = axs[3]; x = np.arange(len(FCORDER)); r_ = nf.lane_mi / nf.mdot_lane_mi
    ax.bar(x, r_, 0.6, color=ps.MODEL, zorder=2); ax.axhline(1, color=ps.OBSERVED, lw=0.8, zorder=3)
    ax.set_xticks(x); ax.set_xticklabels(["Interstate", "Oth. freeway", "Princ. art.", "Minor art.", "Collector", "Local"], rotation=45, ha="right", rotation_mode="anchor"); ax.grid(axis="x", visible=False)
    ax.set_ylabel("Network ÷ observed\nlane miles (–)"); ax.set_ylim(0, 1.5); ax.set_title("(d) Network coverage", loc="left")
    ax = axs[4]; x = np.arange(len(idx))
    ax.axhline(1, color=ps.OBSERVED, lw=0.8)
    ax.scatter(x - 0.12, P.located_model_pc / P.located_obs_pc, s=16, color=ps.MODEL, zorder=3, label="Driven in the county")
    ax.scatter(x + 0.12, P.generated_model_pc / P.generated_rts_pc, s=16, marker="D", facecolor="white", edgecolor=ps.MODEL, zorder=3, label="Driven by its residents")
    ax.set_xticks(x); ax.set_xticklabels([CSHORT.get(c, "Six counties") for c in idx], rotation=45, ha="right", rotation_mode="anchor"); ax.grid(axis="x", visible=False)
    ax.set_ylim(0, 1.5); ax.set_ylabel("Model ÷ observed\nmiles per resident (–)"); ax.set_title("(e) Location and generation", loc="left")
    ax = axs[5]; hour_panel(ax); ax.set_ylabel("Million miles per hour"); ax.set_title("(f) By hour", loc="left")
    fig.legend(handles=[hM, hO, Line2D([], [], marker="o", ls="", color=ps.MODEL, ms=4, label="Miles driven in the county"), Line2D([], [], marker="D", ls="", mfc="white", mec=ps.MODEL, ms=4, label="Miles driven by its residents"),
                        Line2D([], [], marker="o", ls="", color=ps.VARIANT, ms=4, label=ps.LEG["outside"] + " (±25 %)")] + [Patch(color=c_, label=p_) for p_, c_ in zip(PURP, PC_)] + [Patch(color=GAPC, label="Gap to observed")],
               loc="outside upper center", ncol=3, fontsize=ps.TICK)
    figs.append(ps.finish(fig, f"{FG}/fig_reg_vmt_detail"))
    return figs

# ------------------------------------------------------------------------------------------------ check 1: spatial VMT heat map (count sections)
HEX_R = 3500          # hexagon circumradius (m): 6.1 km across the flats, 31.8 km2 per cell
HEX_MIN = 3           # cells with fewer counted sections are not coloured
def hex_axial(x, y, R=HEX_R):
    q = (np.sqrt(3) / 3 * x - y / 3) / R; r = (2 / 3 * y) / R; X, Z = q, r; Y = -X - Z
    rx, ry, rz = np.round(X), np.round(Y), np.round(Z); dx, dy, dz = abs(rx - X), abs(ry - Y), abs(rz - Z)
    m1 = (dx > dy) & (dx > dz); rx[m1] = -ry[m1] - rz[m1]; m2 = ~m1 & (dy > dz); ry[m2] = -rx[m2] - rz[m2]; m3 = ~m1 & ~m2; rz[m3] = -rx[m3] - ry[m3]
    return rx.astype(int), rz.astype(int)

def hex_poly(q, r, R=HEX_R):
    from shapely.geometry import Polygon
    cx, cy = R * np.sqrt(3) * (q + r / 2), R * 1.5 * r; a = np.radians(30 + 60 * np.arange(6))
    return Polygon(np.c_[cx + R * np.cos(a), cy + R * np.sin(a)])

def combine_vmt_hex(D, seeds, R):
    """Count-section VMT: each mainline count station of the count validation represents its MDOT SHA traffic section (milepoint limits).
    Observed = passenger count (AAWDT 2024, else AADT 2024, x (1 - truck - bus share)) x section length; model = car volume on the station's
    matched links (seed mean; link statistics as in validate_counts) x the same length. Sections are summed by hexagon of the station point."""
    S, _, _ = stations_static()
    g = json.load(open(f"{PRICING_HOME}/data/mdot_aadt_statewide_2015-2024.geojson"))
    P = pd.DataFrame([dict(LOCATION_ID=f["properties"]["LOCATION_ID"], BEGIN=f["properties"]["BEGIN_SECTION"], END=f["properties"]["END_SECTION"],
                           gx=f["geometry"]["coordinates"][0], gy=f["geometry"]["coordinates"][1]) for f in g["features"]]).drop_duplicates("LOCATION_ID").set_index("LOCATION_ID")
    lk = pd.concat([pd.read_csv(f"{D}/seeds/s{s}/stations_linkstats.csv", dtype={"LOCATION_ID": str}).assign(seed=s) for s in seeds])
    X = S[["LOCATION_ID", "COUNTY", "cls", "count_pass", "count_all"]].join(P, on="LOCATION_ID")
    X["len_mi"] = (X.END - X.BEGIN).clip(lower=0)
    X = X.merge(lk.pivot(index="LOCATION_ID", columns="seed", values="linkstats_car").add_prefix("m_s").reset_index(), on="LOCATION_ID")
    mc = [c for c in X if c.startswith("m_s")]
    X["obs_vmt"] = X.count_pass * X.len_mi
    for c in mc: X[f"vmt_{c}"] = X[c] * X.len_mi
    X["model_vmt"] = X[[f"vmt_{c}" for c in mc]].mean(1)
    X["q"], X["r"] = hex_axial(X.gx.values, X.gy.values)
    X.to_csv(f"{D}/c1_vmt_sections.csv", index=False, float_format="%.5g")
    Hx = X.groupby(["q", "r"]).agg(n=("LOCATION_ID", "size"), obs=("obs_vmt", "sum"), model=("model_vmt", "sum"), **{f"model_{c}": (f"vmt_{c}", "sum") for c in mc}).reset_index()
    Hx["ratio"] = Hx.model / Hx.obs; Hx["ratio_min"] = Hx[[f"model_{c}" for c in mc]].min(1) / Hx.obs; Hx["ratio_max"] = Hx[[f"model_{c}" for c in mc]].max(1) / Hx.obs
    Hx["shown"] = Hx.n >= HEX_MIN; Hx.to_csv(f"{D}/c1_vmt_hex.csv", index=False, float_format="%.5g")
    sh = Hx[Hx.shown]; w = sh.obs / sh.obs.sum()
    cls_ = np.digitize(sh.ratio, ps.RATIO_BINS[1:-1])
    R["vmt"]["hex"] = dict(circumradius_m=HEX_R, cell_km2=1.5 * np.sqrt(3) * HEX_R ** 2 / 1e6, min_sections=HEX_MIN, n_sections=int(len(X)), section_miles=float(X.len_mi.sum()),
                          cells=int(len(Hx)), cells_shown=int(len(sh)), sections_in_shown=float(sh.n.sum() / Hx.n.sum()),
                          sections_per_cell={k: float(v) for k, v in Hx.n.describe(percentiles=[.1, .25, .5, .75, .9]).items()},
                          ratio_all_sections=float(X.model_vmt.sum() / X.obs_vmt.sum()), obs_section_vmt=float(X.obs_vmt.sum()), model_section_vmt=float(X.model_vmt.sum()),
                          vmt_weighted_within25=float(w[(sh.ratio >= 0.75) & (sh.ratio <= 1.25)].sum()), vmt_weighted_within10=float(w[(sh.ratio >= 0.9) & (sh.ratio <= 1.1)].sum()),
                          cells_within25=float(((sh.ratio >= 0.75) & (sh.ratio <= 1.25)).mean()), vmt_weighted_below075=float(w[sh.ratio < 0.75].sum()), vmt_weighted_above125=float(w[sh.ratio > 1.25].sum()),
                          cells_by_class={ps.RATIO_LABELS[i]: int((cls_ == i).sum()) for i in range(len(ps.RATIO_LABELS))}, median_cell_ratio=float(sh.ratio.median()))

def figure_vmt_heatmap(out, R):
    import matplotlib.pyplot as plt, geopandas as gpd
    from matplotlib.patches import Patch, FancyArrow
    from matplotlib.colors import ListedColormap, BoundaryNorm
    import matplotlib.patheffects as pe
    D = f"{out}/data"; FG = f"{out}/figures"; halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    Hx = pd.read_csv(f"{D}/c1_vmt_hex.csv"); Hx["geometry"] = [hex_poly(q, r) for q, r in zip(Hx.q, Hx.r)]
    G = gpd.GeoDataFrame(Hx, geometry="geometry", crs="EPSG:26985")
    C = gpd.read_file(f"{MATSIM_HOME}/data/bmr_counties.gpkg").to_crs("EPSG:26985"); C["GEOID"] = C.GEOID.astype(str)
    A = links_static(); main = [("IS 695", "I-695"), ("IS 95", "I-95"), ("IS 83", "I-83"), ("IS 97", "I-97"), ("IS 70", "I-70"), ("MD 295", "MD 295")]
    fig = ps.new_figure(6.4); gs = fig.add_gridspec(2, 1, height_ratios=[2.25, 1.0])
    ax = fig.add_subplot(gs[0]); ax.set_aspect("equal"); ax.set_axis_off()
    C.plot(ax=ax, facecolor="#f7f7f4", edgecolor="none")
    sh = G[G.shown]; G[~G.shown].plot(ax=ax, facecolor="white", edgecolor=ps.AXIS, hatch="//////", linewidth=0.3)
    sh.plot(ax=ax, color=[ps.ratio_color(v) for v in sh.ratio], edgecolor="white", linewidth=0.4)
    C.boundary.plot(ax=ax, color=ps.INK2, linewidth=0.6)
    for key, lab in main:
        L = A[(A.route == key) & ~A.hwy.str.endswith("_link")]
        for x0, y0, x1, y1 in zip(L.x0, L.y0, L.x1, L.y1): ax.plot([x0, x1], [y0, y1], color=ps.INK, lw=0.45, alpha=0.55, solid_capstyle="round", zorder=4)
    lab_xy = {"I-695": (452500, 196500), "I-95": (468000, 205500), "I-83": (437000, 221500), "I-97": (440500, 143500), "I-70": (395500, 180500), "MD 295": (418500, 151000)}
    for lab, (x_, y_) in lab_xy.items(): ax.text(x_, y_, lab, fontsize=ps.TICK, color=ps.INK, path_effects=halo, zorder=6, ha="center", va="center")
    c = C[C.GEOID == "24510"].geometry.iloc[0].centroid; ax.text(c.x + 9000, c.y - 4500, "Baltimore\nCity", fontsize=ps.TICK, color=ps.INK, fontweight="bold", path_effects=halo, zorder=6, ha="left", va="center")
    for g_, nm in [("24013", "Carroll"), ("24025", "Harford"), ("24027", "Howard"), ("24003", "Anne Arundel"), ("24005", "Baltimore\nCounty")]:
        p = C[C.GEOID == g_].geometry.iloc[0].representative_point(); off = {"24005": (-13000, 12000), "24013": (-8000, 9000), "24025": (2000, 9000), "24027": (-6000, -4000), "24003": (3000, -14000)}[g_]
        ax.text(p.x + off[0], p.y + off[1], nm, fontsize=ps.TICK, color=ps.INK2, style="italic", path_effects=halo, zorder=6, ha="center", va="center")
    b = C.total_bounds; x0_, y0_ = b[0] + 2000, b[1] + 4000
    ax.plot([x0_, x0_ + 20000], [y0_, y0_], color=ps.INK, lw=1.6, solid_capstyle="butt"); ax.text(x0_ + 10000, y0_ + 2200, "20 km", ha="center", va="bottom", fontsize=ps.TICK, color=ps.INK)
    ax.annotate("", xy=(b[0] + 6000, b[3] - 2000), xytext=(b[0] + 6000, b[3] - 14000), arrowprops=dict(arrowstyle="-|>", color=ps.INK, lw=1.0))
    ax.text(b[0] + 6000, b[3] - 17500, "N", ha="center", va="center", fontsize=ps.FONT, color=ps.INK)
    bh = G.total_bounds; ax.set_xlim(min(b[0], bh[0]) - 500, max(b[2], bh[2]) + 500); ax.set_ylim(min(b[1], bh[1]) - 500, max(b[3], bh[3]) + 500)
    ax.set_title("(a)", loc="left", fontsize=ps.PANEL, fontweight="bold", color=ps.INK)
    # (b) county x class matrix (Mileage Reports ground truth)
    ax2 = fig.add_subplot(gs[1])
    M = pd.read_csv(f"{D}/c1a_vmt_matrix.csv", dtype={"county": str}); Mr = M.pivot(index="county", columns="fc", values="ratio")
    Mr["All classes"] = M.groupby("county")["mean"].sum() / M.groupby("county").wkday_pass.sum()
    tf = M.groupby("fc")["mean"].sum() / M.groupby("fc").wkday_pass.sum(); tf["All classes"] = M["mean"].sum() / M.wkday_pass.sum(); Mr.loc["region"] = tf; Mr = Mr.replace([np.inf], np.nan)
    rows_ = CO + ["region"]; cols_ = FCORDER + ["All classes"]; v = Mr.reindex(index=rows_, columns=cols_).values.astype(float)
    cmap = ListedColormap(ps.RATIO_COLORS); norm = BoundaryNorm([0, .5, .75, .9, 1.1, 1.25, 1.5, 100], cmap.N)
    ax2.imshow(v, cmap=cmap, norm=norm, aspect="auto")
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            if np.isfinite(v[i, j]):
                k = int(np.digitize(v[i, j], ps.RATIO_BINS[1:-1])); ax2.text(j, i, f"{v[i, j]:.2f}", ha="center", va="center", fontsize=ps.TICK, color="white" if k in (0, 1, 5, 6) else ps.INK)
            else: ax2.text(j, i, "–", ha="center", va="center", fontsize=ps.TICK, color=ps.MUTED)
    ax2.set_yticks(range(len(rows_))); ax2.set_yticklabels([CSHORT[c] for c in CO] + ["Six counties"]); ax2.set_xticks(range(len(cols_)))
    ax2.set_xticklabels(["Interstate", "Other\nfreeway", "Principal\narterial", "Minor\narterial", "Collector", "Local", "All\nclasses"]); ax2.tick_params(length=0, axis="both"); ax2.grid(False)
    for sp in ax2.spines.values(): sp.set_visible(False)
    ax2.axhline(len(CO) - 0.5, color="white", lw=2.5); ax2.axvline(len(FCORDER) - 0.5, color="white", lw=2.5)
    ax2.set_title("(b)", loc="left", fontsize=ps.PANEL, fontweight="bold", color=ps.INK)
    vals = list(sh.ratio) + list(v[np.isfinite(v)])
    used = sorted(set(int(np.digitize(x, ps.RATIO_BINS[1:-1])) for x in vals))
    hs = [Patch(facecolor=ps.RATIO_COLORS[i], edgecolor=ps.AXIS, lw=0.3, label=ps.RATIO_LABELS[i]) for i in used] + [Patch(facecolor="white", edgecolor=ps.AXIS, hatch="//////", lw=0.4, label=f"Fewer than {HEX_MIN} counted sections")]
    fig.legend(handles=hs, title="Model ÷ observed weekday passenger-vehicle miles", loc="outside upper center", ncol=4, fontsize=ps.TICK)
    return ps.finish(fig, f"{FG}/fig_reg_vmt_heatmap")

def transit_map(out, R, C, FG):
    import matplotlib.pyplot as plt, xml.etree.ElementTree as ET
    from matplotlib.lines import Line2D
    D = f"{out}/data"; s0 = R["seeds"][0]
    sched = f"{RUNS}/2024_s{s0}/output_transitSchedule.xml.gz"
    stops, lines = {}, {}
    for ev, el in ET.iterparse(gzip.open(sched), events=("end",)):
        if el.tag == "stopFacility": stops[el.get("id")] = (float(el.get("x")), float(el.get("y")))
        elif el.tag == "transitLine":
            best = []
            for rt in el.iter("transitRoute"):
                seq = [s.get("refId") for s in rt.iter("stop")]
                if len(seq) > len(best): best = seq
            lines[el.get("id")] = best; el.clear()
    TL = pd.read_csv(f"{D}/c4_transit_lines.csv"); TL = TL[TL.group.isin(TRANSIT.values())]
    fig, axs = ps.figure(3.0, ncols=2)
    for ax, grp, ttl in [(axs[0], ["Light rail", "Metro subway", "MARC train"], "Rail"), (axs[1], ["Local bus", "Commuter bus"], "Bus")]:
        C.plot(ax=ax, facecolor="#f4f4f1", edgecolor=ps.AXIS, lw=0.5); ax.set_axis_off(); ax.set_aspect("equal")
        x = TL[TL.group.isin(grp)].sort_values("mean"); vmax = x["mean"].max()
        for r in x.itertuples():
            pts = [stops[s] for s in lines.get(r.transit_line, []) if s in stops]
            if len(pts) < 2: continue
            xy = np.array(pts); ax.plot(xy[:, 0], xy[:, 1], color=ps.MODEL, lw=0.2 + 4.5 * r.mean / vmax, alpha=0.8, solid_capstyle="round", zorder=2)
        b = C.total_bounds if ttl == "Rail" else C.loc[["24510"]].buffer(9000).total_bounds; ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3])
        ax.set_title(f"{ttl}; widest line {vmax / 1e3:.1f} thousand boardings", loc="right", fontsize=ps.TICK, fontweight="normal")
    fig.legend(handles=[Line2D([], [], color=ps.MODEL, lw=2.5, label="Modelled weekday boardings of a line (width proportional, per panel)")], loc="outside lower center", fontsize=ps.TICK)
    return ps.finish(fig, f"{FG}/fig_reg_transit_map", panel_labels="ab")

# ------------------------------------------------------------------------------------------------ LaTeX table
def latex(out, R):
    n = len(R["seeds"]); seedtxt = f"mean of {n} assignment seeds" if n > 1 else "one assignment seed"
    v = R["vmt"]; c = R["commute"]; sk = R["skim"]; t = R["transit"]; tl = R["triplength"]; cg = R["countgap"]; od = R["od"]
    rg = c.get("mean_all", {}); ra = c.get("mean_alone", {})
    rows = [
        ("Weekday passenger-vehicle miles, six counties (million)", f"{v['model']/1e6:.1f}", f"{v['obs_pass']/1e6:.1f}", f"ratio {v['ratio']:.2f}; MAPE {v['mape_matrix']:.0f}\\,\\% (county $\\times$ class)", "SILO + ABIT: amount and location of car travel"),
        ("Car-driver miles per resident per weekday: driven by the residents / driven on the six counties' roads", f"{v['per_capita']['region']['generated_model_pc']:.1f} / {v['per_capita']['region']['located_model_pc']:.1f}", f"{v['per_capita']['region']['generated_rts_pc']:.1f} / {v['per_capita']['region']['located_obs_pc']:.1f}", f"ratio {v['per_capita']['region']['generated_model_pc']/v['per_capita']['region']['generated_rts_pc']:.2f} / {v['per_capita']['region']['located_model_pc']/v['per_capita']['region']['located_obs_pc']:.2f}", "Generation by residents (RTS 2017/18) vs.\\ traffic on the roads (MDOT SHA)"),
        ("Travel time to work, all modes (distribution)", f"{rg.get('model', np.nan):.1f}\\,min", f"{rg.get('observed', np.nan):.1f}\\,min", f"TVD {c['B08303']['tvd']:.1f}\\,pp", "SILO workplaces, ABIT mode and timing"),
        ("Travel time to work, drivers alone (distribution)", f"{ra.get('model', np.nan):.1f}\\,min", f"{ra.get('observed', np.nan):.1f}\\,min", f"TVD {c['B08134_alone']['tvd']:.1f}\\,pp", "SILO workplaces through the network"),
        ("Time leaving home for work, share 6:00--8:59 (distribution)", f"{100*c['dep_6_9'][0]:.0f}\\,\\%", f"{100*c['dep_6_9'][1]:.0f}\\,\\%", f"TVD {c['B08302']['tvd']:.1f}\\,pp", "ABIT activity timing"),
        ("Means of transport to work, public transport share (5 classes)", f"{100*c['pt_share'][0]:.1f}\\,\\%", f"{100*c['pt_share'][1]:.1f}\\,\\%", f"TVD {c['B08301_mode']['tvd']:.1f}\\,pp", "ABIT mode choice"),
        ("Morning-peak car time, assigned vs.\\ upstream skim (mean)", f"{sk['am_mean_model']:.1f}\\,min", f"{sk['am_mean_skim']:.1f}\\,min", f"median ratio {sk['am_median']:.2f}; {100*sk['am_within25']:.0f}\\,\\% within $\\pm$25\\,\\%", "No feedback from assignment to SILO, ABIT"),
        ("Weekday boardings, five MTA modes (thousand): 2024 / 2017/18 equivalent", f"{t['model_mta']/1e3:.0f}", f"{t['obs_mta_2024']/1e3:.0f} / {t['obs_mta_1718']/1e3:.0f}", f"ratio {t['ratio_2024']:.2f} / {t['ratio_1718']:.2f}", "ABIT mode choice (2017/18 behaviour), transit routing"),
        ("Car-driver trip distance (distribution)", f"{tl['model']['mean_km']:.1f}\\,km", f"{tl['rts']['mean_km']:.1f}\\,km", f"TVD {tl['tvd_dist_rts']:.1f}\\,pp", "ABIT destination choice"),
        ("Car-driver trip time (distribution)", f"{tl['model']['mean_min']:.1f}\\,min", f"{tl['rts']['mean_min']:.1f}\\,min", f"TVD {tl['tvd_time_rts']:.1f}\\,pp", "ABIT destination choice, network"),
        (f"Passenger vehicles at {cg['n_stations']:,} mainline count stations (sum, million)", f"{cg['all']['model_linkstats']/1e6:.1f}", f"{cg['all']['count_pass']/1e6:.1f}", f"gap {100*cg['all']['gap_share']:.0f}\\,\\%", "Purpose and hour of the missing traffic"),
        ("Home-to-work county flows (shares by home county)", f"{od['workers_model']/1e3:.0f}\\,k", f"{od['workers_acs']/1e3:.0f}\\,k", f"TVD {od['tvd_acs_weighted']:.1f}\\,pp; $R^2$ {od['r2_acs']:.2f}", "SILO workplace choice"),
    ]
    L = ["\\begin{table}[t]", "  \\centering",
         f"  \\caption{{Regional traffic validation of the upstream models through the assignment, Baltimore region, 2024 weekday. Model: residents of Maryland with a tour touching the region, {seedtxt}; nothing is fitted to these data. Observed: MDOT SHA 2024 vehicle miles converted to weekday passenger vehicles with the region's count stations; ACS 2024 1-year (B08303, B08302) and 2020--2024 5-year (B08134, B08136); the fixed morning-peak car skim of SILO and ABIT; NTD 2024 average typical weekday boardings and their 2017/18 equivalent (scaled by the mode's annual boardings 2017--2018 / 2024); RTS 2017/18 (weighted); MDOT SHA 2024 counts; ACS 2016--2020 county-to-county commuting flows. TVD: total variation distance (percentage points); MAPE: mean absolute percentage error.}}",
         "  \\label{tab:net_regional}", "  \\small\\setlength{\\tabcolsep}{4pt}", "\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{4.6cm}rr>{\\raggedright\\arraybackslash}p{2.7cm}>{\\raggedright\\arraybackslash}p{3.3cm}@{}}", "    \\toprule",
         "    Measure & Model & Observed & Fit & Tests \\\\", "    \\midrule"]
    for r in rows: L.append("    " + " & ".join(r) + " \\\\")
    L += ["    \\bottomrule", "\\end{tabular}", "\\end{table}"]
    open(f"{out}/tab_net_regional.tex", "w").write(("\n".join(L) + "\n").replace("÷", "$\\div$"))
    caps = {
        "fig_reg_vmt": "Weekday passenger-vehicle miles of residents against MDOT SHA 2024 vehicle miles converted to weekday passenger vehicles: (a) model ÷ observed by county, (b) by county, (c) by functional class (six counties). Observed: annual vehicle miles of all public roads $\\div$ 365 $\\times$ weekday factor $\\times$ passenger share, both from the region's 2024 count stations by class.",
        "fig_reg_vmt_detail": "Weekday passenger-vehicle miles in detail, six counties: (a) model ÷ observed by county and functional class, (b) by road system (Interstate, US and MD routes from the MDOT SHA 2024 count sections, county and municipal roads as the remainder of the Mileage Reports total; ramps excluded), (c) main routes, model ÷ observed against the observed miles (grey band ±25 \\%), (d) network lane miles ÷ MDOT SHA 2024 mainline lane miles by class (ramps excluded), (e) miles per resident driven in the county (model ÷ MDOT SHA 2024) and driven by the county's residents anywhere (model ÷ RTS 2017/18, weighted car-driver trips, population 2018), (f) miles by hour by trip purpose against the hourly profile of the permanent counters scaled to the observed daily total.",
        "fig_reg_vmt_matrix": "Model ÷ observed weekday passenger-vehicle miles by county and functional class, with the totals of the six counties and of all classes. Observed: MDOT SHA 2024 Mileage Reports (FCAVMT-ALL), converted to weekday passenger vehicles with the region's 2024 count stations.",
        "fig_reg_vmt_system": "Weekday passenger-vehicle miles by road system: (a) six counties, label model ÷ observed, (b) model ÷ observed by county. Observed Interstate, US and MD routes: MDOT SHA 2024 count sections (AAWDT × section length × passenger share of the station); county, municipal and other roads: Mileage Reports total minus these.",
        "fig_reg_vmt_routes": "Weekday passenger-vehicle miles on the main routes within the six counties, model against the MDOT SHA 2024 count sections (AAWDT × section length × passenger share). Label: model ÷ observed (orange outside ±25 \\%); in brackets: share of the route's length (MDOT SHA functional-class segments, sampled every 100 m) with a network link of the same route within 30 m.",
        "fig_reg_vmt_network": "Network coverage: (a) lane miles of the assignment network (ramps excluded) and MDOT SHA 2024 mainline lane miles (FCLM-ALL) by functional class, six counties, (b) ratio by county and class.",
        "fig_reg_vmt_percapita": "Car-driver miles per resident per weekday by county: (a) driven on the roads of the county, model against MDOT SHA 2024 (population 2024), (b) driven by the county's residents anywhere, model (network distance of their car-driver trips) against the RTS 2017/18 (weighted car-driver trips, routed distance, population 2018).",
        "fig_reg_vmt_hour": "Weekday passenger-vehicle miles per hour by trip purpose (selected plans, link entry times interpolated along the routes) against the hourly profile of the permanent counters scaled to the observed daily passenger-vehicle miles.",
        "fig_reg_commute_time": "Travel time to work by home county, all modes, against the ACS 2024 1-year (B08303).",
        "fig_reg_commute_time_alone": "Travel time to work of drivers alone by home county against the ACS 2020--2024 5-year (B08134).",
        "fig_reg_commute_departure": "Time leaving home for work by home county against the ACS 2024 1-year (B08302).",
        "fig_reg_commute_mode": "Means of transport to work by home county against the ACS 2020--2024 5-year (B08301).",
        "fig_reg_commute_mean": "Mean travel time to work by home county: (a) all modes; (b) drivers alone. Observed: ACS 2020--2024 5-year aggregate time (B08136) per worker not working at home (B08134).",
        "fig_reg_skim": "Assigned car travel time against the fixed morning-peak car skim of the upstream models: (a) morning-peak trips; (b) ratio by skim distance and period. Box: 25--75\\%; whiskers: 10--90\\%; white line: median.",
        "fig_reg_transit": "Weekday boardings of the MTA modes against the NTD: (a) boardings; (b) model ÷ observed, 2024 (filled) and 2017/18 equivalent (open).",
        "fig_reg_transit_map": "Modelled weekday boardings by transit line: (a) light rail, Metro subway and MARC; (b) MTA local and commuter bus. Line width proportional to boardings within a panel.",
        "fig_reg_triplength": "Car-driver trips of residents against the RTS 2017/18 and the NHTS 2022: (a) network distance; (b) travel time.",
        "fig_reg_countgap": "Modelled traffic by trip purpose at the count stations: (a) hourly volume at the permanent counters against the hourly counts; (b) share of the 2024 passenger count reproduced, by road class.",
        "fig_reg_od": "Home-to-work county flows: (a) model minus ACS 2016--2020 share of the home county's workers (percentage points; TVD in brackets); (b) model flows against the ACS and LODES 2022.",
        "fig_reg_od_map": "Commuting between the six counties: (a) model; (b) ACS 2016--2020. Line width: workers in both directions; circle size: workers living and working in the county.",
        "fig_reg_overview": "Regional traffic validation of the upstream models: (a) weekday car miles by county, (b) travel time to work, (c) assigned ÷ skim car time, (d) MTA boardings, (e) car-driver trip distance, (f) hourly traffic at the permanent counters by trip purpose against the passenger counts.",
    }
    for k in ["fig_reg_vmt", "fig_reg_vmt_detail", "fig_reg_vmt_matrix", "fig_reg_vmt_system", "fig_reg_vmt_routes", "fig_reg_vmt_network", "fig_reg_vmt_percapita", "fig_reg_vmt_hour"]: caps.pop(k, None)
    hx = v["hex"]
    caps = {"fig_reg_vmt_heatmap": (f"Weekday passenger-vehicle miles, model ÷ observed: (a) by hexagon ({hx['cell_km2']:.0f}\\,km$^2$) on the {hx['n_sections']:,} matched MDOT SHA 2024 count sections, "
            f"hatched where fewer than {hx['min_sections']} sections; lines: Interstates and MD 295; (b) by county and functional class, all public roads, against the MDOT SHA 2024 Mileage Reports."), **caps}
    S = ["% Supplementary figures of the regional traffic validation (generated by assignment/validation/regional_validation.py)"]
    ebar = f" Error bars: range over the {n} seeds." if n > 1 else ""   # one seed: stated once in the section text
    for k, cap in caps.items():
        S += ["\\begin{figure}[p]", "  \\centering", f"  \\includegraphics[width=\\textwidth]{{figures/{k}.pdf}}", f"  \\caption{{{cap}{ebar}}}", f"  \\label{{fig:s_{k[4:]}}}", "\\end{figure}", ""]
    tex = lambda t: t.replace("÷", "$\\div$").replace("×", "$\\times$").replace("±", "$\\pm$").replace("−", "$-$")
    open(f"{out}/supp_regional.tex", "w").write(tex("\n".join(S)))

# ------------------------------------------------------------------------------------------------ main
RUNS = None
def main():
    global RUNS
    ap = argparse.ArgumentParser(); ap.add_argument("runs", nargs="?", default=f"{V}/pipeline/runs/matsim"); ap.add_argument("out", nargs="?", default=f"{H}/previews/seed1_final/regional")
    ap.add_argument("--seeds"); ap.add_argument("--force", action="store_true"); ap.add_argument("--figures-only", action="store_true")
    a = ap.parse_args(); RUNS = a.runs; t0 = time.time()
    seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else seeds_present(a.runs)
    print(f"seeds {seeds} from {a.runs} -> {a.out}"); os.makedirs(f"{a.out}/data", exist_ok=True)
    if not a.figures_only:
        for s in seeds: run_seed(a.runs, s, a.out, a.force)
        R = combine(a.out, seeds)
    else: R = json.load(open(f"{a.out}/data/summary.json"))
    figures(a.out, R); figures_vmt_detail(a.out, R); figure_vmt_heatmap(a.out, R); latex(a.out, R)
    print(f"done in {time.time() - t0:.0f} s"); print(json.dumps({k: R[k] for k in ["vmt", "skim", "transit", "od"]}, indent=1, default=float)[:4000])

if __name__ == "__main__": main()
