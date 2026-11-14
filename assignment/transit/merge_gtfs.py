#!/usr/bin/env python3
"""Merge the GTFS feeds of every public transport operator in the MATSim network area into one GTFS folder for pt2matsim
(4_matsim/transit/TRANSIT_BUILD.md).  Successor of the earlier chain's `Updated MATSim/code/merge_gtfs.py` (2026-06-30, the five
MTA feeds); the first version of this file (2026-10-22 12:02, five MTA feeds, all service ids) is described in TRANSIT_BUILD.md, step 1.

Per feed (FEEDS below; downloads in Validation_2026/data/raw/<folder>/, fetched by 4_matsim/network/fetch_gtfs.sh and
4_matsim/transit/fetch_gtfs_regional.sh):
  1. service day: the representative weekday DAY (Wednesday 2026-10-21) when the feed's calendar has service on it; a feed whose
     calendar has ended ("stale": the operator publishes no current feed) uses its last Wednesday with service (the "proxy day",
     recorded in the manifest).  The active service ids of that day come from calendar.txt (date range and weekday flag) and
     calendar_dates.txt (exception 1 added, 2 removed): the intersection the operator publishes for that date.
  2. only the trips of those service ids are kept; they all get the service id <feed>:DAY, and one calendar row makes it active
     on DAY only, so pt2matsim (which takes one date for the merged feed) extracts exactly one weekday of every feed.
  3. network area: stops more than CLIP_M (250 m) from a node of a road or rail link of the MATSim network are dropped (the network is
     built from the OpenStreetMap Maryland extract: it covers Maryland around the Baltimore region and the Maryland suburbs of
     Washington, not DC or Virginia, where WMATA, MARC, Amtrak and some Ride On and MTA commuter routes also run); trips keep their
     stops inside the area (consecutive kept stops on either side of a gap stay connected by the schedule times), trips with fewer
     than two such stops are dropped.  Amtrak: rail routes only (Thruway buses dropped).
  4. ids: every identifier is prefixed with the feed key ("<key>:"), every foreign key the same way, so nothing collides.
Outputs: <out>/{agency,stops,routes,trips,stop_times,calendar,shapes,frequencies,transfers}.txt and <out>/manifest.json (per feed:
input file, sha256, feed version, calendar range, service day, rows before/after each step).
Usage: python3 -I merge_gtfs.py <raw dir (Validation_2026/data/raw)> <network.xml.gz> <out dir>"""
import sys, os, io, csv, zipfile, hashlib, json, datetime, gzip, re
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer

RAW, NET, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DAY = datetime.date(2026, 10, 21); CLIP_M = 250.0
# key: (folder/file under RAW, agency label, mode note)
FEEDS = {"bus": ("mta_gtfs/mta_local-bus.zip", "MTA local bus (CityLink, LocalLink, Express BusLink)"), "lr": ("mta_gtfs/mta_light-rail.zip", "MTA Light RailLink"),
         "mt": ("mta_gtfs/mta_metro.zip", "MTA Metro SubwayLink"), "marc": ("mta_gtfs/mta_marc.zip", "MTA MARC train"), "cb": ("mta_gtfs/mta_commuter-bus.zip", "MTA commuter bus"),
         "ccc": ("charm_city_circulator/charm_city_circulator_gtfs.zip", "Charm City Circulator (Baltimore City DOT)"), "hc": ("harbor_connector/harbor_connector_gtfs.zip", "Harbor Connector (Baltimore City DOT, ferry)"),
         "tl": ("towson_loop/towson_loop_gtfs.zip", "Towson Loop (Baltimore County)"), "rta": ("rta_central_maryland/rta_central_maryland_gtfs.zip", "RTA of Central Maryland"),
         "aact": ("anne_arundel_transit/anne_arundel_transit_gtfs.zip", "Anne Arundel County Transit"), "at": ("annapolis_transit/annapolis_transit_gtfs.zip", "Annapolis Transit"),
         "hfd": ("harford_transit_link/harford_transit_link_gtfs.zip", "Harford Transit LINK"), "cts": ("carroll_transit/carroll_transit_gtfs.zip", "Carroll Transit System"),
         "wmr": ("wmata_rail/wmata_rail_gtfs.zip", "WMATA Metrorail"), "wmb": ("wmata_bus/wmata_bus_gtfs.zip", "WMATA Metrobus"),
         "ro": ("ride_on/ride_on_gtfs.zip", "Montgomery County Ride On"), "pg": ("thebus_pg/thebus_pg_gtfs.zip", "Prince George's County TheBus"),
         "amt": ("amtrak/amtrak_gtfs.zip", "Amtrak (rail routes)")}
PREFIX_COLS = {"agency.txt": ["agency_id"], "stops.txt": ["stop_id", "parent_station"], "routes.txt": ["route_id", "agency_id"],
               "trips.txt": ["route_id", "service_id", "trip_id", "shape_id", "block_id"], "stop_times.txt": ["trip_id", "stop_id"],
               "shapes.txt": ["shape_id"], "transfers.txt": ["from_stop_id", "to_stop_id"], "frequencies.txt": ["trip_id"]}
KEEP_COLS = {"agency.txt": ["agency_id", "agency_name", "agency_url", "agency_timezone"], "stops.txt": ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"],
             "routes.txt": ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"], "trips.txt": ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id", "block_id", "shape_id"],
             "stop_times.txt": ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"], "shapes.txt": ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
             "transfers.txt": ["from_stop_id", "to_stop_id", "transfer_type", "min_transfer_time"], "frequencies.txt": ["trip_id", "start_time", "end_time", "headway_secs", "exact_times"]}

def load(zf, name):
    names = {x.split("/")[-1]: x for x in zf.namelist()}
    if name not in names: return None
    df = pd.read_csv(io.BytesIO(zf.read(names[name])), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]; return df.apply(lambda s: s.str.strip())

def active_services(cal, cd, day):
    d = day.strftime("%Y%m%d"); wd = day.strftime("%A").lower(); act = set()
    if cal is not None and len(cal): act |= set(cal[(cal.start_date <= d) & (cal.end_date >= d) & (cal[wd] == "1")].service_id)
    if cd is not None and len(cd): e = cd[cd.date == d]; act |= set(e.service_id[e.exception_type == "1"]); act -= set(e.service_id[e.exception_type == "2"])
    return act

# network area: nodes of the MATSim network (EPSG:26985)
# the nodes of the road and rail links built from OpenStreetMap (ids without the "pt_" prefix of the artificial transit nodes of earlier mappings);
# the network is built from the Geofabrik Maryland extract, so it has no streets in DC or Virginia and the clip keeps the Maryland part of every service
xy = {}; real = set()
with gzip.open(NET, "rt") as f:
    for line in f:
        if "<node " in line: m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', line); xy[m.group(1)] = (float(m.group(2)), float(m.group(3)))
        elif "<link " in line:
            m = re.search(r'from="([^"]+)" to="([^"]+)"', line); modes = set(re.search(r'modes="([^"]*)"', line).group(1).split(","))
            if "artificial" not in modes and modes & {"car", "bus", "rail", "train", "subway", "light_rail", "tram"}: real.update(n for n in m.groups() if not n.startswith("pt_"))
tree = cKDTree(np.array([xy[n] for n in real])); to_md = Transformer.from_crs(4326, 26985, always_xy=True)

os.makedirs(OUT, exist_ok=True); merged = {k: [] for k in KEEP_COLS}; man = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "day": DAY.isoformat(), "clip_m": CLIP_M, "network": NET, "feeds": []}
for key, (rel, label) in FEEDS.items():
    p = f"{RAW}/{rel}"; zf = zipfile.ZipFile(p); T = {n: load(zf, n) for n in list(KEEP_COLS) + ["calendar.txt", "calendar_dates.txt", "feed_info.txt"]}
    cal, cd, fi = T["calendar.txt"], T["calendar_dates.txt"], T["feed_info.txt"]
    rec = {"key": key, "agency": label, "file": p, "bytes": os.path.getsize(p), "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()[:16],
           "feed_version": fi.feed_version.iloc[0] if fi is not None and "feed_version" in fi and len(fi) else None,
           "calendar_from": min([x for x in [cal.start_date.min() if cal is not None and len(cal) else None, cd.date.min() if cd is not None and len(cd) else None] if x]),
           "calendar_to": max([x for x in [cal.end_date.max() if cal is not None and len(cal) else None, cd.date.max() if cd is not None and len(cd) else None] if x]),
           "routes_in_feed": len(T["routes.txt"]), "trips_in_feed": len(T["trips.txt"]), "stops_in_feed": len(T["stops.txt"])}
    day = DAY; sv = active_services(cal, cd, day); rec["stale"] = False
    if not T["trips.txt"].service_id.isin(sv).any():   # no service on DAY: the feed has ended -> its last Wednesday with service
        end = datetime.datetime.strptime(rec["calendar_to"], "%Y%m%d").date(); day = end - datetime.timedelta(days=(end.weekday() - 2) % 7)
        while not T["trips.txt"].service_id.isin(active_services(cal, cd, day)).any(): day -= datetime.timedelta(days=7)
        sv = active_services(cal, cd, day); rec["stale"] = True
    rec["service_day"] = day.isoformat(); rec["service_ids"] = sorted(sv)
    trips = T["trips.txt"][T["trips.txt"].service_id.isin(sv)].copy(); routes = T["routes.txt"]
    if key == "amt": rail = set(routes.route_id[routes.route_type == "2"]); trips = trips[trips.route_id.isin(rail)]
    rec["trips_on_day"] = len(trips); rec["routes_on_day"] = trips.route_id.nunique()
    # clip to the network area
    st = T["stops.txt"].copy()
    for col in ["parent_station", "location_type"]:
        if col not in st: st[col] = ""
    x, y = to_md.transform(st.stop_lon.astype(float).values, st.stop_lat.astype(float).values); dist, _ = tree.query(np.c_[x, y]); st["inside"] = dist <= CLIP_M
    stt = T["stop_times.txt"]; stt = stt[stt.trip_id.isin(set(trips.trip_id))]; stt = stt[stt.stop_id.isin(set(st.stop_id[st.inside]))]
    n_in = stt.groupby("trip_id").size(); keep_trips = set(n_in.index[n_in >= 2]); stt = stt[stt.trip_id.isin(keep_trips)]
    rec["trips_dropped_outside"] = int(len(trips) - len(keep_trips)); trips = trips[trips.trip_id.isin(keep_trips)]
    trips["service_id"] = "DAY"; used_stops = set(stt.stop_id); par = set(st.parent_station[st.stop_id.isin(used_stops)]) - {""}
    st = st[st.stop_id.isin(used_stops | par)].drop(columns="inside")
    routes = routes[routes.route_id.isin(set(trips.route_id))].copy()
    if "agency_id" not in routes or (routes.agency_id == "").all(): routes["agency_id"] = T["agency.txt"].agency_id.iloc[0] if "agency_id" in T["agency.txt"] and T["agency.txt"].agency_id.iloc[0] else "1"
    ag = T["agency.txt"].copy()
    if "agency_id" not in ag or (ag.agency_id == "").all(): ag["agency_id"] = routes.agency_id.iloc[0] if len(routes) else "1"
    ag = ag[ag.agency_id.isin(set(routes.agency_id))]
    tabs = {"agency.txt": ag, "stops.txt": st, "routes.txt": routes, "trips.txt": trips, "stop_times.txt": stt,
            "shapes.txt": T["shapes.txt"][T["shapes.txt"].shape_id.isin(set(trips.get("shape_id", [])))] if T["shapes.txt"] is not None and "shape_id" in trips else None,
            "transfers.txt": T["transfers.txt"][T["transfers.txt"].from_stop_id.isin(used_stops) & T["transfers.txt"].to_stop_id.isin(used_stops)] if T["transfers.txt"] is not None else None,
            "frequencies.txt": T["frequencies.txt"][T["frequencies.txt"].trip_id.isin(keep_trips)] if T["frequencies.txt"] is not None else None}
    for name, df in tabs.items():
        if df is None or not len(df): continue
        df = df.copy()
        for col in KEEP_COLS[name]:
            if col not in df.columns: df[col] = ""
        df = df[KEEP_COLS[name]]
        for col in PREFIX_COLS[name]: df[col] = df[col].map(lambda v: f"{key}:{v}" if v != "" else v)
        merged[name].append(df)
    rec.update({"routes_kept": len(routes), "trips_kept": len(trips), "stops_kept": int(len(set(stt.stop_id))), "stop_times_kept": len(stt),
                "frequencies_kept": len(tabs["frequencies.txt"]) if tabs["frequencies.txt"] is not None else 0, "route_types": routes.route_type.value_counts().to_dict()})
    man["feeds"].append(rec)
    print(f"{key:5s} {label[:44]:44s} day {rec['service_day']}{' (STALE: calendar ended ' + rec['calendar_to'] + ')' if rec['stale'] else ''}: routes {rec['routes_on_day']}/{rec['routes_in_feed']} -> {rec['routes_kept']}, trips {rec['trips_on_day']:,} -> {rec['trips_kept']:,} (outside the network {rec['trips_dropped_outside']:,}), stops {rec['stops_kept']:,}/{rec['stops_in_feed']:,}")
for name, parts in merged.items():
    if parts: pd.concat(parts, ignore_index=True).to_csv(f"{OUT}/{name}", index=False, quoting=csv.QUOTE_MINIMAL)
pd.DataFrame([{"service_id": f"{f['key']}:DAY", "monday": 0, "tuesday": 0, "wednesday": 1, "thursday": 0, "friday": 0, "saturday": 0, "sunday": 0, "start_date": DAY.strftime("%Y%m%d"), "end_date": DAY.strftime("%Y%m%d")} for f in man["feeds"]]).to_csv(f"{OUT}/calendar.txt", index=False)
for name in ["calendar_dates.txt"]:
    if os.path.exists(f"{OUT}/{name}"): os.remove(f"{OUT}/{name}")
json.dump(man, open(f"{OUT}/manifest.json", "w"), indent=1); print("written", OUT)
