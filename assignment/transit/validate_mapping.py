#!/usr/bin/env python3
"""Validate a pt2matsim-mapped schedule against the merged GTFS it came from and the network it was mapped onto (TRANSIT_BUILD.md).
Per agency (feed key = id prefix) and mode:
  - counts: lines vs GTFS routes, departures vs GTFS trips (frequency trips expanded), stop parents vs GTFS stops used
  - mapping: distance of every stop facility to its reference link (shares within 25 / 50 m), stops on artificial links, routes using
    artificial links, share of the mapped route length on artificial links
  - stop-to-stop times: network free-flow time along the mapped links between consecutive stops (the links after the stop's link up
    to and including the next stop's link) against the scheduled time (next arrivalOffset - departureOffset); median ratio and the
    share of stop pairs with ratio > 1.5 (the network cannot keep the schedule) or < 0.5
  - plausibility warnings (pt2matsim CheckMappedSchedulePlausibility csv, if given) by class
Overall: AM-peak (7-9) headways of the core MTA routes against data/transit_gtfs_headways_core.csv; the car links of the base network
must be unchanged in the mapper's output.
Usage: python3 -I assignment/transit/validate_mapping.py <schedule.xml.gz> <network_pt.xml.gz> <network_base.xml.gz> <gtfs dir> <headways_core.csv> <out.json> [plausibility.csv]"""
import sys, re, gzip, json, math, collections, os
import numpy as np, pandas as pd

sched, net_pt, net_base, gtfs, core_csv, out = sys.argv[1:7]; plaus = sys.argv[7] if len(sys.argv) > 7 else None
def hms(s): h, m, x = s.split(":"); return int(h) * 3600 + int(m) * 60 + float(x)
stops = {}; lines = {}; cl = cr = None
with gzip.open(sched, "rt") as f:
    for line in f:
        if "<stopFacility " in line:
            m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"(?: linkRefId="([^"]+)")?', line); stops[m.group(1)] = (float(m.group(2)), float(m.group(3)), m.group(4))
        elif "<transitLine " in line: cl = re.search(r'id="([^"]+)"', line).group(1); lines[cl] = {}
        elif "<transitRoute " in line: cr = re.search(r'id="([^"]+)"', line).group(1); lines[cl][cr] = {"mode": None, "stops": [], "links": [], "deps": []}
        elif "<transportMode>" in line: lines[cl][cr]["mode"] = re.search(r"<transportMode>([^<]+)", line).group(1)
        elif "<stop refId=" in line:
            m = re.search(r'refId="([^"]+)"', line); a = re.search(r'arrivalOffset="([^"]+)"', line); d = re.search(r'departureOffset="([^"]+)"', line)
            lines[cl][cr]["stops"].append((m.group(1), hms(a.group(1)) if a else None, hms(d.group(1)) if d else None))
        elif "<link refId=" in line: lines[cl][cr]["links"].append(re.search(r'refId="([^"]+)"', line).group(1))
        elif "<departure " in line:
            m = re.search(r'id="([^"]+)" departureTime="([^"]+)"', line); lines[cl][cr]["deps"].append((m.group(1), hms(m.group(2))))
def read_net(p, want_nodes):
    nodes = {}; links = {}
    with gzip.open(p, "rt") as f:
        for line in f:
            if want_nodes and "<node " in line:
                m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', line); nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
            elif "<link " in line:
                m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" freespeed="([^"]+)" capacity="([^"]+)" permlanes="([^"]+)"', line)
                links[m.group(1)] = (m.group(2), m.group(3), float(m.group(4)), float(m.group(5)), float(m.group(6)), float(m.group(7)), re.search(r'modes="([^"]*)"', line).group(1))
    return nodes, links
nodes, links = read_net(net_pt, True); _, base_links = read_net(net_base, False); art = {l for l, v in links.items() if "artificial" in v[6]}
def dist_to_link(x, y, lid):
    (x1, y1), (x2, y2) = nodes[links[lid][0]], nodes[links[lid][1]]; dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L2)); return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
feed = lambda i: i.split(":")[0]
# stops
S = pd.DataFrame([(sid, feed(sid), dist_to_link(x, y, l) if l else np.nan, l in art) for sid, (x, y, l) in stops.items()], columns=["stop", "feed", "dist", "on_art"])
# routes, stop-pair times
rows, pairs = [], []
for lid, L in lines.items():
    for rid, r in L.items():
        ln = sum(links[l][2] for l in r["links"]); la = sum(links[l][2] for l in r["links"] if l in art)
        rows.append((feed(lid), lid, rid, r["mode"], len(r["deps"]), ln, la, any(l in art for l in r["links"])))
        # stop-to-stop: walk the link sequence
        pos = 0; seq = r["links"]
        for (s0, a0, d0), (s1, a1, d1) in zip(r["stops"][:-1], r["stops"][1:]):
            l0, l1 = stops[s0][2], stops[s1][2]
            try: i0 = seq.index(l0, pos); i1 = seq.index(l1, i0 + (1 if l1 == l0 and seq.count(l0) > 1 else 0))
            except ValueError: continue
            if i1 < i0: continue
            tnet = sum(links[l][2] / links[l][3] for l in seq[i0 + 1:i1 + 1]); tsch = (a1 if a1 is not None else d1) - (d0 if d0 is not None else a0); pos = i0
            on_art = any(l in art for l in seq[i0 + 1:i1 + 1])
            if tsch > 0: pairs.append((feed(lid), r["mode"], tnet, tsch, on_art))
Rt = pd.DataFrame(rows, columns=["feed", "line", "route", "mode", "deps", "len", "len_art", "has_art"]); Pp = pd.DataFrame(pairs, columns=["feed", "mode", "tnet", "tsch", "art"])
Pp["ratio"] = Pp.tnet / Pp.tsch
# GTFS
T = pd.read_csv(f"{gtfs}/trips.txt", dtype=str); R = pd.read_csv(f"{gtfs}/routes.txt", dtype=str); ST = pd.read_csv(f"{gtfs}/stop_times.txt", dtype=str, usecols=["trip_id", "stop_id"])
FQ = pd.read_csv(f"{gtfs}/frequencies.txt", dtype=str) if os.path.exists(f"{gtfs}/frequencies.txt") else None
T["feed"] = T.trip_id.map(feed); R["feed"] = R.route_id.map(feed)
W = None
if plaus:   # the warnings csv has the link ids as a trailing comma list: keep the first nine fields
    import csv as _csv
    rows_ = list(_csv.reader(open(plaus))); W = pd.DataFrame([r[:9] for r in rows_[1:]], columns=rows_[0][:9])
if W is not None: W["feed"] = W.TransitLine.map(feed)
by = []
for fk in sorted(Rt.feed.unique()):
    r = Rt[Rt.feed == fk]; s = S[S.feed == fk]; p = Pp[(Pp.feed == fk) & ~Pp.art]
    rec = {"feed": fk, "modes": ",".join(sorted(r["mode"].unique())), "gtfs_routes": int((R.feed == fk).sum()), "lines": int(r.line.nunique()), "routes": len(r),
           "gtfs_trips": int((T.feed == fk).sum()), "departures": int(r.deps.sum()), "frequency_trips": int((FQ.trip_id.map(feed) == fk).sum()) if FQ is not None else 0,
           "gtfs_stops_used": int(ST.stop_id[ST.trip_id.map(feed) == fk].nunique()), "stop_parents": int(s.stop.str.split(".link:").str[0].nunique()), "stop_facilities": len(s),
           "stops_within_25m": float((s.dist <= 25).mean()), "stops_within_50m": float((s.dist <= 50).mean()), "stops_on_artificial": float(s.on_art.mean()),
           "routes_with_artificial": float(r.has_art.mean()), "route_km": float(r.len.sum() / 1000), "share_length_artificial": float(r.len_art.sum() / max(r.len.sum(), 1)),
           "stop_pairs_on_network": len(p), "tt_ratio_median": float(p.ratio.median()) if len(p) else None, "tt_ratio_gt_1_5": float((p.ratio > 1.5).mean()) if len(p) else None, "tt_ratio_lt_0_5": float((p.ratio < 0.5).mean()) if len(p) else None}
    if W is not None:
        for c in ["ArtificialLinkWarning", "TravelTimeWarning", "DirectionChangeWarning", "LoopWarning"]:
            w = W[(W.feed == fk) & (W.WarningType == c)]; rec[f"warn_{c}"] = len(w); rec[f"routes_with_{c}"] = int(w.TransitRoute.nunique())
    by.append(rec)
B = pd.DataFrame(by)
# headways of the core MTA routes
short = R.set_index("route_id").route_short_name.to_dict(); dirn = T.set_index("trip_id").direction_id.to_dict(); core = pd.read_csv(core_csv).set_index("route"); hw = []
for lid, L in lines.items():
    name = short.get(lid, "")
    if not (str(name).startswith("CityLink") or name in ("LIGHT RAILLINK", "METRO SUBWAYLINK")): continue
    n = collections.Counter(); tot = 0
    for rid, r in L.items():
        for dep_id, t in r["deps"]:
            tot += 1
            if 7 * 3600 <= t < 9 * 3600: n[dirn.get(dep_id.rsplit("_", 1)[0], "?")] += 1
    h = [120 / v for v in n.values() if v]
    hw.append({"route": name, "trips_matsim": tot, "trips_gtfs": int(core.trips_weekday[name]) if name in core.index else None, "am_peak_matsim": round(float(np.mean(h)), 1) if h else None, "am_peak_gtfs": float(core.am_peak[name]) if name in core.index else None})
H = pd.DataFrame(hw).sort_values("route")
car_base = {l: v for l, v in base_links.items() if "car" in v[6].split(",")}; car_pt = {l: v for l, v in links.items() if "car" in v[6].split(",")}
changed = [l for l, v in car_base.items() if l not in car_pt or car_pt[l][:6] != v[:6]]
tot = {"lines": len(lines), "routes": len(Rt), "departures": int(Rt.deps.sum()), "stop_facilities": len(S), "stops_within_25m": float((S.dist <= 25).mean()), "stops_within_50m": float((S.dist <= 50).mean()),
       "artificial_links_in_network": len(art), "routes_with_artificial": int(Rt.has_art.sum()), "share_length_artificial": float(Rt.len_art.sum() / Rt.len.sum()),
       "tt_ratio_median_network_pairs": float(Pp[~Pp.art].ratio.median()), "route_link_refs_missing": sum(1 for r in Rt.route for _ in [0]) * 0 + sum(1 for L in lines.values() for r in L.values() for l in r["links"] if l not in links),
       "car_links_base": len(car_base), "car_links_changed_or_missing": len(changed), "car_links_modes_changed": sum(1 for l, v in car_base.items() if l in car_pt and car_pt[l][6] != v[6])}
if W is not None: tot["plausibility_warnings"] = W.WarningType.value_counts().to_dict(); tot["routes_with_warning"] = {c: int(W[W.WarningType == c].TransitRoute.nunique()) for c in W.WarningType.unique()}
by_mode = Pp[~Pp.art].groupby("mode").ratio.agg(["median", lambda x: (x > 1.5).mean(), "size"]).rename(columns={"<lambda_0>": "share_gt_1_5"}).round(3).to_dict("index")
json.dump({"schedule": sched, "network_pt": net_pt, "network_base": net_base, "total": tot, "by_feed": by, "tt_ratio_by_mode": by_mode, "headways_core": H.to_dict("records")}, open(out, "w"), indent=1)
pd.set_option("display.width", 250); print(json.dumps(tot, indent=1)); print(B.round(3).to_string(index=False)); print(by_mode); print(H.to_string(index=False)); print("written", out)
B.to_csv(out.replace(".json", "_by_feed.csv"), index=False)
