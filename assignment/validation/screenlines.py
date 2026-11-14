#!/usr/bin/env python3
"""Screenline validation of the MATSim 2024 assignment (validation study, 2026-11-03), against the MDOT SHA 2024 counts.

Screenlines (fixed before any model volume was read; none chosen, dropped or moved for fit).  Placement follows FHWA (2010, Sec. 9.1.2):
a screenline runs along a physical barrier or a jurisdictional line, crosses the major travel corridors and cuts the network
completely (boundary to boundary, or closed as a cordon).  Seven lines, each capturing one of the region's main movements:
  1 Baltimore City cordon        city boundary (closed): commuting to and from the core and the CBD.
  2 Patapsco River              river centreline (OpenStreetMap waterway relations 'Patapsco River' and 'South Branch Patapsco
                                River') from the Chesapeake Bay through the harbour to the Frederick County line: Anne Arundel and
                                Howard (BWI, Fort Meade, Columbia) <-> Baltimore City, Baltimore and Carroll; contains the harbour
                                crossings (I-95 and I-895 tunnels; the Key Bridge, closed in 2024, carries nothing).  Two sections are
                                reported: the tidal river (Bay to the head of tide at Elkridge, US 1 bridge) and the upper river.
  3 Beltway (I-695) cordon      radial roads crossing I-695 (closed ring through the I-695 carriageways; I-695 itself and the
                                interchange ramps are the line, not crossings): suburb <-> inner-suburb/core movements.
  4 Southern regional boundary  Patuxent River: Howard and Anne Arundel <-> Montgomery and Prince George's (the Baltimore-Washington
                                corridor: I-95, MD 295, US 1, US 29, US 50/301).
  5 Little Gunpowder Falls      Baltimore County <-> Harford County, Pennsylvania line to the Bay (north-east I-95 / US 40 / US 1 corridor).
  6 Carroll County line         Carroll <-> Baltimore County and Howard (Liberty Reservoir, North and South Branch Patapsco),
                                Pennsylvania line to the Frederick County line (north-west MD 140 / I-795, MD 26, MD 32 corridor).
  7 Other regional boundary     Frederick, Pennsylvania, Cecil (Susquehanna), Queen Anne's (Bay Bridge), Calvert: with line 4 the
                                complete regional cordon.
Crossings: car links of class motorway, trunk, primary, secondary, tertiary (mainline; *_link ramps and lower classes excluded) of
network_2024 whose two end nodes lie on different sides of the line (county lines: county of the node, from the six-county
polygons, neighbours from the SILO zone system; water nodes take the nearest county; river: the link intersects the centreline an odd
number of times; Beltway: one node inside, one outside the ring).
Counted crossing (rule of 2026-11-03, revised after a coverage check of the first preview, not of the ratios): a matched MAINLINE
count station (validate_counts.py, use == mainline) lies on the same road within 3 km along the road (6 km on motorway/trunk) with at most
one junction in between.  Road identity = MDOT route of the link (network audit, as in match_count_stations.py), else OSM name; links of
one road crossing within 400 m (1 km for one route's carriageways, e.g. express lanes) form one crossing.  Trace: from each crossing link
forward and backward over the continuing link of the same route (else name, else class, within 60 degrees).  Junction: a node where
another road of class secondary or higher or a ramp meets the road; nodes of one interchange (1 km on motorway/trunk) or intersection
(300 m) count once.  Each matched link of the station must lie on the trace of a link of the crossing (same carriageways); stations
nearest first.  Main-text table: screenlines whose counted crossings carry >= 70 % of the motorway/trunk/primary crossing capacity.
Uncounted motorway/trunk/primary crossing links with the reason: data/screenline_uncounted_major.csv.
Comparison on the counted crossings only: count (AAWDT, all vehicles; passenger = count x (1 - truck and bus share), as in
validate_counts.py) against the model at the station's own links, both directions and by direction (MDOT NE/SW split of the station);
model total over all crossings for context.  Criterion: maximum deviation of screenline totals by volume, >70,000 +-10 %, 35,000-70,000
+-15 %, <35,000 +-20 % (Wegmann and Everett 2016, after FDOT 2008); FHWA (2010, Fig. 9.9) gives the same kind of curve.
Seeds: model per seed (stations_by_seed.csv.gz for the counted totals; link_hours_s<seed>.csv.gz, final iteration x 10 + buses, for
the directional and all-crossing totals), mean = validate_counts' seed mean (link_daily_volume_mean.csv.gz).
Usage: python3 screenlines.py <validate_counts data dir> <link_hours dir> <out dir> [--article <article dir>]
       -> <out>/data/screenlines_definition.geojson, screenline_crossings.csv, screenline_table.csv, screenline_by_seed.csv;
          <article>/sections/tab_net_screenlines.tex, <article>/figures/fig_net_screenlines.pdf|png
"""
import os, sys, re, glob, json, argparse, warnings
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union
warnings.filterwarnings("ignore")
H = os.path.dirname(os.path.abspath(__file__)); V = os.path.dirname(os.path.dirname(H)); ROOT = os.path.dirname(V)
sys.path.insert(0, f"{V}/4_matsim/network"); sys.path.insert(0, f"{V}/5_reports")
import netio, paperstyle as ps

CRS = 26985; EXP = 10
CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary"]
MAJOR = {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
TRACE_M = 3000.0
MAJOR_COV = ["motorway", "trunk", "primary"]; COVERAGE_MIN = 0.70        # main-text table: >= 70 % of the motorway/trunk/primary crossing capacity counted
JUNCTION_M = 300.0; JUNCTION_FWY_M = 1000.0                   # one junction: an intersection (nodes within 300 m) or, on motorway/trunk, an interchange (within 1 km)
TRACE_FWY_M = 6000.0                                 # motorway/trunk: stations up to 6 km along the road (3 km on other roads)
MAX_JUNCTIONS = 1                                    # junctions allowed between crossing and station
CRIT = [(70000, 10), (35000, 15), (0, 20)]          # screenline total (vehicles/day) -> maximum deviation (%)
BMR = {24003: "Anne Arundel", 24005: "Baltimore County", 24013: "Carroll", 24025: "Harford", 24027: "Howard", 24510: "Baltimore City"}
PBF = f"{ROOT}/inputs/osm/maryland-latest.osm.pbf"
OSM_REL = {"Patapsco River": 17404909, "South Branch Patapsco River": 17405603}
SL = [  # id, name, kind, (side A, side B) for county lines; direction label from A to B, from B to A
    (1, "Baltimore City cordon", "county", ({24510}, set(BMR) - {24510} | {"out"}), ("outbound", "inbound")),
    (2, "Patapsco River", "river", None, ("northbound", "southbound")),
    (3, "Beltway (I-695) cordon", "ring", None, ("outbound", "inbound")),
    (4, "Southern regional boundary (Patuxent River)", "county", ({24027, 24003}, {24031, 24033}), ("outbound", "inbound")),
    (5, "Little Gunpowder Falls (Baltimore County / Harford)", "county", ({24005}, {24025}), ("northbound", "southbound")),
    (6, "Carroll County line", "county", ({24005, 24027}, {24013}), ("outbound", "inbound")),   # to Carroll = 'outbound' from the core
    (7, "Other regional boundary", "county", (set(BMR), {"out_other"}), ("outbound", "inbound")),
]
SHORT = {1: "Baltimore City cordon", 2: "Patapsco River", 3: "Beltway cordon", 4: "Southern boundary (Patuxent)", 5: "Little Gunpowder Falls",
         6: "Carroll County line", 7: "Other regional boundary"}


# ------------------------------------------------------------------------------------------------ geometry
def network():
    nodes, L = netio.read_network(f"{V}/4_matsim/network/network_2024.xml.gz")
    L = L[L.car & ~L.is_pt].copy()
    return nodes, L


def node_county(nodes):
    """County FIPS of every node: inside one of the six county polygons, else the nearest county (six + neighbours of the SILO zones)."""
    c6 = gpd.read_file(f"{ROOT}/Updated MATSim/data/bmr_counties.gpkg").to_crs(CRS); c6["fips"] = c6.GEOID.astype(int)
    z = gpd.read_file(f"{V}/2_silo/input/zones.shp").to_crs(CRS)[["id", "geometry"]]
    zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv", usecols=["ZoneId", "COUNTYFIPS"])
    z = z.merge(zs, left_on="id", right_on="ZoneId"); nb = z[~z.COUNTYFIPS.isin(BMR)].dissolve("COUNTYFIPS").reset_index()
    nb = nb.rename(columns={"COUNTYFIPS": "fips"})[["fips", "geometry"]]
    nb["geometry"] = nb.geometry.difference(c6.geometry.union_all())
    allc = pd.concat([c6[["fips", "geometry"]], nb], ignore_index=True)
    ids = np.array(list(nodes)); xy = np.array([nodes[i] for i in ids])
    P = gpd.GeoDataFrame({"node": ids}, geometry=gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=CRS)
    j = gpd.sjoin(P, c6[["fips", "geometry"]], predicate="within", how="left").drop_duplicates("node").set_index("node").fips
    miss = P[P.node.isin(j[j.isna()].index)]
    k = gpd.sjoin_nearest(miss, allc, how="left").drop_duplicates("node").set_index("node").fips
    j.loc[k.index] = k
    return j.astype(int), c6, nb


def osm_rivers():
    """Centrelines of the Patapsco River (main stem) and its South Branch from the OSM waterway relations, EPSG:26985, each piece
    oriented downstream (west to east)."""
    import osmium
    from pyproj import Transformer
    want = set(OSM_REL.values()); members = {}
    class R(osmium.SimpleHandler):
        def relation(self, r):
            if r.id in want: members[r.id] = [m.ref for m in r.members if m.type == "w"]
    R().apply_file(PBF)
    wid = {w: k for k, ws in members.items() for w in ws}; geo = {}
    class W(osmium.SimpleHandler):
        def way(self, w):
            if w.id in wid:
                try: geo[w.id] = [(n.lon, n.lat) for n in w.nodes]
                except osmium.InvalidLocationError: pass
    W().apply_file(PBF, locations=True)
    tr = Transformer.from_crs(4326, CRS, always_xy=True); out = {}
    for name, rid in OSM_REL.items():
        segs = [LineString(np.column_stack(tr.transform(*np.array(geo[w]).T))) for w in members[rid] if w in geo and len(geo[w]) > 1]
        m = linemerge(unary_union(segs)); parts = list(m.geoms) if m.geom_type == "MultiLineString" else [m]
        parts = [p if p.coords[0][0] <= p.coords[-1][0] else LineString(p.coords[::-1]) for p in parts if p.length >= 100]
        parts.sort(key=lambda p: p.coords[0][0])            # pieces of the mapped centreline, chained west to east (gaps of a few metres)
        out[name] = LineString([c for p in parts for c in p.coords])
    # one line, upstream (South Branch, Frederick County line) to the mouth (Chesapeake Bay)
    return LineString(list(out["South Branch Patapsco River"].coords) + list(out["Patapsco River"].coords))


def river_split(line):
    """Position (m from the upstream end) of the head of the tidal river at Elkridge: the river point nearest the Howard / Baltimore
    County / Anne Arundel tripoint (downstream of it the river is the Anne Arundel line and the harbour)."""
    c6 = gpd.read_file(f"{ROOT}/Updated MATSim/data/bmr_counties.gpkg").to_crs(CRS); c6.index = c6.GEOID.astype(int)
    t = c6.geometry[24027].buffer(50).intersection(c6.geometry[24005].buffer(50)).intersection(c6.geometry[24003].buffer(50))
    return line.project(t.centroid)


def beltway_ring(L):
    """Closed ring through the I-695 carriageways: end nodes of the 'Baltimore Beltway' motorway links ordered by angle around their centroid."""
    b = L[(L.hwy == "motorway") & (L.name == "Baltimore Beltway")]
    xy = np.vstack([b[["x0", "y0"]].values, b[["x1", "y1"]].values]); c = xy.mean(0)
    a = np.arctan2(xy[:, 1] - c[1], xy[:, 0] - c[0]); o = np.argsort(a)
    ring = Polygon(xy[o]).buffer(0)
    if ring.geom_type == "MultiPolygon": ring = max(ring.geoms, key=lambda g: g.area)
    return ring, set(b.index)


def crossings(L, cty, rivers, ring, i695):
    """All crossing links of every screenline: link id, screenline, direction label, crossing point (x, y), section."""
    C = L[L.hwy.isin(CLASSES)].copy()
    C["c0"] = C.f.map(cty).values; C["c1"] = C.t.map(cty).values
    def side(c):
        return c if c in BMR else "out"
    rows = []
    geom = gpd.GeoSeries(netio.link_geoms(C), index=C.index, crs=CRS)
    for sid, name, kind, sides, dirs in SL:
        if kind == "county":
            A, B = sides
            def grp(c):
                if c in BMR: return "A" if c in A else ("B" if c in B else None)
                if "out" in B: return "B"                       # any county outside the region (cordon 1 treats them as outside)
                if "out_other" in B: return "B" if c not in {24031, 24033} else None
                return "B" if c in B else ("A" if c in A else None)
            g0 = C.c0.map(grp); g1 = C.c1.map(grp)
            x = C[(g0.notna()) & (g1.notna()) & (g0 != g1)]
            for lid, r in x.iterrows():
                d = dirs[0] if g0[lid] == "A" else dirs[1]
                p = geom[lid].interpolate(0.5, normalized=True)
                rows.append((lid, sid, d, p.x, p.y, ""))
        elif kind == "river":
            part = rivers; split = river_split(part)
            hit = geom[geom.intersects(part)]
            for lid, g in hit.items():
                ip = g.intersection(part)
                pts = [ip] if ip.geom_type == "Point" else list(getattr(ip, "geoms", []))
                pts = [q for q in pts if q.geom_type == "Point"]
                if len(pts) % 2 == 0: continue
                q = pts[0]; s = part.project(q); a = part.interpolate(max(s - 5, 0)); b2 = part.interpolate(min(s + 5, part.length))
                r = L.loc[lid]; cr = (b2.x - a.x) * (r.y1 - r.y0) - (b2.y - a.y) * (r.x1 - r.x0)   # > 0: link heads to the left (north) bank
                rows.append((lid, sid, dirs[0] if cr > 0 else dirs[1], q.x, q.y, "lower" if s >= split else "upper"))
        elif kind == "ring":
            x = C[~C.index.isin(i695) & C.hwy.isin(CLASSES)]
            pin0 = shapely.contains_xy(ring, x.x0.values, x.y0.values); pin1 = shapely.contains_xy(ring, x.x1.values, x.y1.values)
            x = x[pin0 != pin1]; pin0 = shapely.contains_xy(ring, x.x0.values, x.y0.values)
            for (lid, r), i0 in zip(x.iterrows(), pin0):
                q = geom[lid].intersection(ring.exterior); q = q if q.geom_type == "Point" else geom[lid].interpolate(0.5, normalized=True)
                rows.append((lid, sid, dirs[0] if i0 else dirs[1], q.x, q.y, ""))
    X = pd.DataFrame(rows, columns=["link", "sl", "direction", "xc", "yc", "section"])
    return X


def link_routes(index):
    A = pd.read_parquet(f"{V}/data/network_audit_links.parquet", columns=["mdot_route"])
    return A.mdot_route.fillna("").str.replace("IS ", "I-").replace({"MD 695": "I-695"}).reindex(index).fillna("")


def clusters(X, L, gap=400.0):
    """Crossing = the links of one road crossing the same screenline within `gap` metres of each other (the two directions or the
    carriageways of one road, e.g. general and express lanes); one road = same MDOT route or same OSM name (else same class, unnamed)."""
    X = X.copy(); X["road"] = L.name.reindex(X.link).fillna("").values; X["hwy"] = L.hwy.reindex(X.link).values
    X["route"] = link_routes(X.link).values
    X["key"] = np.where(X.route != "", X.route, np.where(X.road != "", X.road, "(" + X.hwy + ")")); X["crossing"] = -1; k = 0
    anon = lambda a: X.route[a] == "" and X.road[a] == ""
    def same(a, b):
        dd = np.hypot(X.xc[a] - X.xc[b], X.yc[a] - X.yc[b])
        if X.route[a] != "" and X.route[a] == X.route[b]: return dd <= 2.5 * gap          # carriageways of one route (e.g. express lanes)
        if dd > gap: return False
        return (X.road[a] != "" and X.road[a] == X.road[b]) or ((anon(a) or anon(b)) and X.hwy[a] == X.hwy[b])
    for sl, d in X.groupby("sl"):
        idx = list(d.index); lab = {}
        for i in idx:
            if i in lab: continue
            lab[i] = k; stack = [i]
            while stack:
                a = stack.pop()
                for b in idx:
                    if b not in lab and same(a, b): lab[b] = k; stack.append(b)
            k += 1
        for i, c in lab.items(): X.loc[i, "crossing"] = c
    # a road that follows the line and crosses it back and forth (more than one link per direction, not a freeway with several
    # carriageways) is one crossing: per direction the link nearest the crossing's centre is kept
    X["fwy"] = X.hwy.isin(["motorway", "trunk"]); drop = []
    for (c, dn), d in X.groupby(["crossing", "direction"]):
        if len(d) > 1 and not d.fwy.any():
            cx, cy = X.loc[X.crossing == c, "xc"].mean(), X.loc[X.crossing == c, "yc"].mean()
            keep = np.hypot(d.xc - cx, d.yc - cy).idxmin(); drop += [i for i in d.index if i != keep]
    X["repeat_dropped"] = X.index.isin(drop)
    return X


class Graph:
    """Road traces on the car network.  Road identity = the link's MDOT route (network audit, as in the station matcher), else its OSM name."""
    def __init__(self, L):
        self.L = L; self.out = L.groupby("f").groups; self.inn = L.groupby("t").groups
        self.hwy = L.hwy.to_dict(); self.name = L.name.to_dict(); self.f = L.f.to_dict(); self.t = L.t.to_dict()
        self.len = L.length.to_dict(); self.brg = L.bearing.to_dict()
        A = pd.read_parquet(f"{V}/data/network_audit_links.parquet", columns=["mdot_route"])
        r = A.mdot_route.fillna("").str.replace("IS ", "I-").replace({"MD 695": "I-695"})
        self.route = r.reindex(L.index).fillna("").to_dict()

    def _bd(self, a, b):
        d = abs(self.brg[a] - self.brg[b]) % 360; return min(d, 360 - d)

    def _cont(self, cur, node, forward):
        """(continuing link of the same road at `node` or None, junction at `node`: another road of class secondary or higher, or a ramp, joins or leaves)."""
        back = self.f[cur] if forward else self.t[cur]
        cand = [l for l in (self.out.get(node, []) if forward else self.inn.get(node, [])) if (self.t[l] if forward else self.f[l]) != back]
        if not self.hwy[cur].endswith("_link"): cand_m = [l for l in cand if not self.hwy[l].endswith("_link")]
        else: cand_m = cand
        rt, nm = self.route[cur], self.name[cur]
        same = [l for l in cand_m if rt and self.route[l] == rt]
        if not same: same = [l for l in cand_m if nm and self.name[l] == nm]
        if not same: same = [l for l in cand_m if self.hwy[l] == self.hwy[cur]]
        same = [l for l in same if self._bd(l, cur) <= 60]
        c = min(same, key=lambda l: self._bd(l, cur)) if same else None
        twin = lambda a, b: self.f[a] in (self.f[b], self.t[b]) and self.t[a] in (self.f[b], self.t[b])
        allk = set(self.out.get(node, [])) | set(self.inn.get(node, []))
        rest = [l for l in allk if l != cur and l != c and not twin(l, cur) and (c is None or not twin(l, c))]
        junction = any(self.hwy[l] in MAJOR for l in rest)
        return c, junction

    def trace(self, lid, max_m=None, max_j=None):
        """Links of the same road within TRACE_M of the crossing (forward and backward): {link: (distance m, junctions passed)};
        the trace ends after more than MAX_JUNCTIONS junctions."""
        seen = {lid: (0.0, 0)}; fwy = self.hwy[lid] in ("motorway", "trunk")
        for forward in (True, False):
            cur, d, nj, dj = lid, self.len[lid] / 2, 0, -1e9
            while d < (max_m or (TRACE_FWY_M if fwy else TRACE_M)):
                c, jn = self._cont(cur, self.t[cur] if forward else self.f[cur], forward)
                if jn and d - dj > (JUNCTION_FWY_M if fwy else JUNCTION_M): nj += 1; dj = d   # junction nodes close to the first = one junction
                if c is None or c in seen or nj > (MAX_JUNCTIONS if max_j is None else max_j): break
                seen[c] = (d, nj); d += self.len[c]; cur = c
        return seen


def station_links(S):
    ids = []
    for r in S.itertuples():
        ne = r.link_NE if isinstance(r.link_NE, str) and r.link_NE else None; sw = r.link_SW if isinstance(r.link_SW, str) and r.link_SW else None
        if r.NE_SPLIT in (0, 100) or r.SW_SPLIT in (0, 100): ids.append([ne] if r.NE_SPLIT == 100 else [sw])
        else: ids.append([ne, sw])
    return ids


def attach_stations(X, G, S):
    """Stations of every crossing.  A station is used when each of its matched links lies on the trace of a different crossing link
    of the crossing (so the count covers the same carriageways); stations are taken nearest first; crossing links left without a
    station (e.g. express lanes beside counted general lanes) stay uncounted."""
    S = S[S["use"] == "mainline"].copy(); S["ids"] = station_links(S); sids = S.set_index("LOCATION_ID").ids
    l2s = {}
    for r in S.itertuples():
        for l in r.ids:
            if l: l2s.setdefault(l, []).append(r.LOCATION_ID)
    X = X.copy(); X["station"] = None; X["station_link"] = None; X["trace_m"] = np.nan; X["junctions"] = np.nan
    for c, d in X.groupby("crossing"):
        hits = {}                                            # station -> {crossing link index: (station link, dist, junctions)}
        for i, r in d.iterrows():
            for l, (dist, nj) in G.trace(r.link).items():
                for st in l2s.get(l, []):
                    h = hits.setdefault(st, {})
                    if i not in h or dist < h[i][1]: h[i] = (l, dist, nj)
        free = set(d.index)
        for st in sorted(hits, key=lambda st: min(v[1] for v in hits[st].values())):
            h = {i: v for i, v in hits[st].items() if i in free}
            need = [l for l in sids[st] if l]
            pick = {}
            for l in need:
                ii = [i for i, v in h.items() if v[0] == l and i not in pick]
                if not ii: break
                pick[min(ii, key=lambda i: h[i][1])] = h[min(ii, key=lambda i: h[i][1])]
            if len(pick) != len(need): continue
            for i, (l, dist, nj) in pick.items(): X.loc[i, ["station", "station_link", "trace_m", "junctions"]] = [st, l, dist, nj]; free.discard(i)
            if not free: break
    return X


def uncounted_major(X, G, S):
    """Every motorway, trunk or primary crossing link left without a station, with the nearest station of the same road found by a
    longer trace (10 km, any number of junctions) and the reason it is not used."""
    S = S[S["use"] == "mainline"].copy(); S["ids"] = station_links(S)
    l2s = {l: r.LOCATION_ID for r in S.itertuples() for l in r.ids if l}
    rows = []
    for i, r in X[X.station.isna() & X.hwy.isin(MAJOR_COV)].iterrows():
        tr = G.trace(r.link, max_m=10000, max_j=99); h = sorted(((v[0], v[1], l) for l, v in tr.items() if l in l2s))
        if h:
            dist, nj, l = h[0]; st = l2s[l]
            why = ("station beyond the distance limit" if dist > (TRACE_FWY_M if r.hwy in ("motorway", "trunk") else TRACE_M) else f"{nj} junctions between crossing and station" if nj > MAX_JUNCTIONS
                   else "station covers other carriageways of the crossing")
        else: dist, nj, st, why = np.nan, np.nan, None, "no matched mainline station on the road within 10 km"
        rows.append(dict(sl=r.sl, screenline=SHORT[r.sl], crossing=r.crossing, link=r.link, road=r.road, route=G.route.get(r.link, ""), hwy=r.hwy, direction=r.direction,
                         nearest_station=st, along_road_m=dist, junctions=nj, reason=why))
    return pd.DataFrame(rows)


def model_links(vc_dir, lh_dir, seeds):
    """Seed-mean link volumes (validate_counts: car x 10 + bus) and per-seed final-iteration volumes from the link-hour files."""
    M = pd.read_csv(f"{vc_dir}/link_daily_volume_mean.csv.gz", dtype={"link": str}).set_index("link"); M["all"] = M.car + M.bus
    per = {}
    for s in seeds:
        E = pd.read_csv(f"{lh_dir}/link_hours_s{s}.csv.gz", dtype={"link": str}, usecols=["link", "hour", "car", "bus"])
        E = E[E.hour < 24].groupby("link")[["car", "bus"]].sum(); E["car"] *= EXP; E["all"] = E.car + E.bus; per[s] = E
    return M, per


def crit(v):
    return next(d for lo, d in CRIT if v >= lo)


def summarise(X, S, M, per, PS, seeds, L):
    S = S.set_index("LOCATION_ID")
    X = X.copy(); X["capacity"] = L.capacity.reindex(X.link).values
    X["model_all_link"] = M["all"].reindex(X.link).fillna(0).values
    cnt = X[X.station.notna()].copy()
    st = S.reindex(cnt.station)
    sh = np.where(cnt.station_link.values == st.link_NE.values, st.NE_SPLIT.values, st.SW_SPLIT.values) / 100
    cnt["count_all_dir"] = st.count_all.values * sh; cnt["count_pass_dir"] = st.count_pass.values * sh
    cnt["model_all_dir"] = M["all"].reindex(cnt.station_link).fillna(0).values; cnt["model_car_dir"] = M["car"].reindex(cnt.station_link).fillna(0).values
    for s in seeds: cnt[f"model_all_dir_s{s}"] = per[s]["all"].reindex(cnt.station_link).fillna(0).values
    X = X.join(cnt[["count_all_dir", "count_pass_dir", "model_all_dir", "model_car_dir"]])
    rows = []
    secs = [(1, None), (2, None), (2, "lower"), (2, "upper")] + [(sid, None) for sid in SHORT if sid > 2]
    for sid, sec in secs:
        x = X[(X.sl == sid) & ((X.section == sec) if sec else True)]; c = cnt[(cnt.sl == sid) & ((cnt.section == sec) if sec else True)]
        stn = S.reindex(c.station.unique())
        r = dict(sl=sid, section=sec or "all", name=SHORT[sid] + ({"lower": ": harbor and tidal river", "upper": ": upper river"}[sec] if sec else ""),
                 crossings=int(x.crossing.nunique()), crossing_links=int(len(x)), counted=int(c.crossing.nunique()), stations=int(len(stn)),
                 cap_share=float(x[x.station.notna()].capacity.sum() / x.capacity.sum()),
                 cap_share_major=float(x[x.station.notna() & x.hwy.isin(MAJOR_COV)].capacity.sum() / x[x.hwy.isin(MAJOR_COV)].capacity.sum()),
                 count_all=float(stn.count_all.sum()), count_pass=float(stn.count_pass.sum()),
                 model_all=float(stn.model_all_mean.sum()), model_car=float(stn.model_car_mean.sum()),
                 model_all_crossings=float(x.model_all_link.sum()))
        r["ratio_all"] = r["model_all"] / r["count_all"] if r["count_all"] else np.nan; r["ratio_pass"] = r["model_car"] / r["count_pass"] if r["count_pass"] else np.nan
        r["pdiff_all"] = 100 * (r["ratio_all"] - 1); r["pdiff_pass"] = 100 * (r["ratio_pass"] - 1)
        r["max_dev_all"] = crit(r["count_all"]); r["max_dev_pass"] = crit(r["count_pass"])
        r["pass_all"] = bool(abs(r["pdiff_all"]) <= r["max_dev_all"]); r["pass_pass"] = bool(abs(r["pdiff_pass"]) <= r["max_dev_pass"])
        p = PS[PS.LOCATION_ID.isin(stn.index)].groupby("seed")[["m_all", "m_car"]].sum()
        ra = p.m_all / r["count_all"]; rp = p.m_car / r["count_pass"]
        r.update(ratio_all_min=float(ra.min()), ratio_all_max=float(ra.max()), ratio_pass_min=float(rp.min()), ratio_pass_max=float(rp.max()), n_seeds=int(len(p)))
        dirs = next(d for i, _, _, _, d in SL if i == sid)
        for k, dn in enumerate(dirs):
            cd = c.drop_duplicates("station_link"); cd = cd[cd.direction == dn]   # a station counted at two crossings of one road enters once
            r[f"dir{k}"] = dn; r[f"count_all_dir{k}"] = float(cd.count_all_dir.sum()); r[f"model_all_dir{k}"] = float(cd.model_all_dir.sum())
            r[f"ratio_all_dir{k}"] = r[f"model_all_dir{k}"] / r[f"count_all_dir{k}"] if r[f"count_all_dir{k}"] else np.nan
            r[f"ratio_pass_dir{k}"] = float(cd.model_car_dir.sum() / cd.count_pass_dir.sum()) if len(cd) else np.nan
            rs = [cd[f"model_all_dir_s{s}"].sum() / r[f"count_all_dir{k}"] for s in seeds] if len(cd) else [np.nan]
            r[f"ratio_all_dir{k}_final_it_min"] = float(np.min(rs)); r[f"ratio_all_dir{k}_final_it_max"] = float(np.max(rs))
            r[f"model_all_crossings_dir{k}"] = float(x[x.direction == dn].model_all_link.sum())
        tot = [per[s]["all"].reindex(x.link).fillna(0).sum() for s in seeds]
        r["model_all_crossings_final_it_min"] = float(min(tot)); r["model_all_crossings_final_it_max"] = float(max(tot))
        rows.append(r)
    return pd.DataFrame(rows), X


# ------------------------------------------------------------------------------------------------ outputs
def latex_table_dir(T, path, n_seeds):
    """Supplement: by direction, and the model total over all crossings."""
    U = "%% UPDATE AFTER FINAL MATSIM RUN"
    seedtxt = "one assignment seed" if n_seeds == 1 else f"mean of {n_seeds} assignment seeds"
    L_ = [r"\begin{table}[!htbp]", r"  \centering",
          r"  \caption{Screenline traffic by direction against the 2024 counts.}" + U + " (note: number of seeds)",
          r"  \label{tab:net_screenlines_dir}", r"  \footnotesize\setlength{\tabcolsep}{3.5pt}", r"  \begin{adjustbox}{max width=\linewidth}",
          r"\begin{tabular}{@{}llrrrrr@{}}", r"    \toprule",
          r"    & & \multicolumn{3}{c}{Counted crossings} & \multicolumn{2}{c}{Model, all crossings} \\", r"    \cmidrule(lr){3-5}\cmidrule(lr){6-7}",
          r"    Screenline & Direction & \shortstack[r]{Count, all\\vehicles (thousand)} & \shortstack[r]{Model / count,\\all vehicles} & \shortstack[r]{Model / count,\\passenger vehicles} & \shortstack[r]{Vehicles\\(thousand)} & \shortstack[r]{Share on counted\\crossings (\%)} \\",
          r"    \midrule"]
    for r in T.itertuples():
        nm = f"S{r.sl} {r.name}" if r.section == "all" else r"\quad " + r.name.split(": ")[1].capitalize()
        for k in (0, 1):
            d = getattr(r, f"dir{k}")
            L_.append(f"    {nm if k == 0 else ''} & {d} & {getattr(r, f'count_all_dir{k}') / 1e3:,.0f} & {getattr(r, f'ratio_all_dir{k}'):.2f} & {getattr(r, f'ratio_pass_dir{k}'):.2f} & "
                      f"{getattr(r, f'model_all_crossings_dir{k}') / 1e3:,.0f} & {'' if k else f'{100 * r.model_all / r.model_all_crossings:.0f}'} \\\\ {U}")
        if r.section == "all" and r.sl != 2 or r.section == "upper": L_.append(r"    \addlinespace")
    L_ += [r"    \bottomrule", r"  \end{tabular}", r"\end{adjustbox}", "",
           r"  \vspace{4pt}\noindent\parbox{\linewidth}{\footnotesize \textit{Note:} Model: " + seedtxt + r". Directions: inbound = towards Baltimore City (cordons) or into the region (boundaries), outbound the reverse; for the Patapsco River and the Little Gunpowder Falls northbound = to the north bank. Count by direction: station count $\times$ its MDOT directional split; model at the station's link of that direction. Model, all crossings: volume of residents' vehicles on every crossing link; share on counted crossings: model volume at the counted crossings' stations over the model volume on all crossings (both directions).\\\\",
           r"  \textit{Source:} \citet{MDOTAADT}; model: \matsim{} assignment.}", r"\end{table}"]
    open(path, "w").write("\n".join(L_) + "\n")


def fmt_int(v): return f"{v:,.0f}"


def latex_table(T, path, n_seeds, main=True):
    """main=True: the screenlines meeting the coverage requirement (main text); main=False: all screenlines (Supplementary Material)."""
    U = "%% UPDATE AFTER FINAL MATSIM RUN"
    seedtxt = "one assignment seed" if n_seeds == 1 else f"mean of {n_seeds} assignment seeds (range over the seeds in brackets)"
    ok = T.groupby("sl").cap_share_major.transform("first") >= COVERAGE_MIN
    D = T[ok] if main else T
    low = ", ".join(f"S{r.sl}" for r in T[~ok & (T.section == "all")].itertuples())
    if main:
        cap = r"Screenline totals against the 2024 counts."
        lab = "tab:net_screenlines"; ref = (r" Screenlines " + low + r" do not meet the coverage requirement and are not shown." if low else "")
        place = "[!tbp]"
    else:
        cap = r"Screenline totals of daily traffic against the 2024 counts, all seven screenlines."
        lab = "tab:s_net_screenlines_all"; ref = ""; place = "[!htbp]"
    lines = [r"\begin{table}" + place, r"  \centering", r"  \caption{" + cap + "}" + U + " (caption: number of seeds)",
             r"  \label{" + lab + "}", r"  \footnotesize\setlength{\tabcolsep}{3.5pt}", r"  \begin{adjustbox}{max width=\linewidth}",
             r"\begin{tabular}{@{}lrrrrrrrrrc@{}}", r"    \toprule",
             r"    & \multicolumn{2}{c}{Crossings} & \multicolumn{2}{c}{Capacity counted (\%)} & \multicolumn{2}{c}{Count (thousand)} & \multicolumn{2}{c}{Model / count} & & \\",
             r"    \cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}",
             r"    Screenline & All & Counted & \shortstack[r]{Major\\roads} & \shortstack[r]{All\\roads} & \shortstack[r]{All\\vehicles} & \shortstack[r]{Passenger\\vehicles} & \shortstack[r]{All\\vehicles} & \shortstack[r]{Passenger\\vehicles} & \shortstack[r]{Maximum\\deviation (\%)} & \shortstack[c]{Within\\(all / pass.)} \\",
             r"    \midrule"]
    yn = lambda b: "yes" if b else "no"
    for r in D.itertuples():
        nm = f"S{r.sl} {r.name}" if r.section == "all" else r"\quad " + r.name.split(": ")[1].capitalize()
        rng_a = f" ({r.ratio_all_min:.2f}--{r.ratio_all_max:.2f})" if r.n_seeds > 1 else ""
        rng_p = f" ({r.ratio_pass_min:.2f}--{r.ratio_pass_max:.2f})" if r.n_seeds > 1 else ""
        lines.append(f"    {nm} & {r.crossings} & {r.counted} & {100 * r.cap_share_major:.0f} & {100 * r.cap_share:.0f} & {r.count_all / 1e3:,.0f} & {r.count_pass / 1e3:,.0f} & {r.ratio_all:.2f}{rng_a} & {r.ratio_pass:.2f}{rng_p} & $\\pm${r.max_dev_all:.0f} & {yn(r.pass_all)} / {yn(r.pass_pass)} \\\\ {U}")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{adjustbox}", "",
              r"  \vspace{4pt}\noindent\parbox{\linewidth}{\footnotesize \textit{Note:} " + (r"Screenlines whose counted crossings carry at least " + f"{100 * COVERAGE_MIN:.0f}" + r"\% of the motorway, trunk and primary capacity crossing the line; model: residents' traffic, " + seedtxt + ". " if main else "Model: " + seedtxt + ". ") + r"Screenlines S1--S7 are mapped in Fig.~" + (r"\ref{fig:net_study_area}" if main else r"\mainref{fig:net_study_area}")
              + ("" if main else r" and defined in Section~\ref{sec:s_net_screenlines}") + "." + ref   # main text: no supplement references (2026-11-04)
              + r" Crossings: roads of class motorway to tertiary (network 2024, Key Bridge closed) cutting the line. Counted: a matched mainline count station on the same road (MDOT route, else name) within 3~km of the line (6~km on motorways and trunk roads) with at most one junction (intersection or interchange) in between. Capacity counted: share of the hourly capacity of the crossing links that lies on counted crossings, motorway, trunk and primary roads (major) and all classes. Count and model are compared on the counted crossings only, the model at the stations' own links. Counts: MDOT SHA 2024 average annual weekday traffic, both directions; passenger vehicles: count $\times$ (1 $-$ truck and bus share). Maximum deviation of a screenline total by its volume: $\pm$10\% above 70,000, $\pm$15\% for 35,000--70,000, $\pm$20\% below 35,000 vehicles per day \citep{Wegmann2016,FDOT2008}, by the counted all-vehicle total; within: the all-vehicle and the passenger total meet it. The model contains residents' travel only (no trucks, commercial vehicles or traffic of non-residents), so ratios below 1 are expected.\\",
              r"  \textit{Source:} \citet{MDOTAADT}; model: \matsim{} assignment.}", r"\end{table}"]
    open(path, "w").write("\n".join(lines) + "\n")


def add_ticks(SLG, X, L, far=1000.0, half=1500.0):
    """Short line across every crossing that lies more than `far` metres from the drawn screenline (a county line in open water)."""
    out = dict(SLG)
    for sid, d in X.groupby("sl"):
        g = SLG[sid]; extra = []
        for r in d.drop_duplicates("crossing").itertuples():
            if g.distance(Point(r.xc, r.yc)) > far:
                l = L.loc[r.link]; dx, dy = l.x1 - l.x0, l.y1 - l.y0; n = np.hypot(dx, dy) or 1; px, py = -dy / n * half, dx / n * half
                extra.append(LineString([(r.xc - px, r.yc - py), (r.xc + px, r.yc + py)]))
        if extra: out[sid] = unary_union([g] + extra)
    return out


def screenline_geoms(c6, nb, river, ring):
    c = c6.set_index(c6.fips).geometry; n = nb.set_index("fips").geometry; bmr = c.union_all()
    near = lambda geom, other, b: geom.boundary.intersection(other.buffer(b))
    return {1: c[24510].boundary, 2: river, 3: ring.exterior,
            4: near(unary_union([c[24027], c[24003]]), unary_union([n[24031], n[24033]]), 1500),
            5: near(c[24005], c[24025], 60), 6: near(unary_union([c[24005], c[24027]]), c[24013], 60),
            7: near(bmr, unary_union([g for f, g in n.items() if f not in (24031, 24033)]), 1500).difference(unary_union([n[24031], n[24033]]).buffer(1500))}


KEY_BRIDGE = (-76.5285, 39.2176)   # Francis Scott Key Bridge (I-695 over the Patapsco), collapsed 2024-03-26


def _lines(ax, L, cls, **kw):
    from matplotlib.collections import LineCollection
    d = L[L.hwy.isin(cls)]
    seg = np.stack([d[["x0", "y0"]].values, d[["x1", "y1"]].values], 1)
    ax.add_collection(LineCollection(seg, **kw))


def _poly_lines(geom):
    if geom.is_empty: return []
    gs = getattr(geom, "geoms", [geom]); out = []
    for g in gs:
        if g.geom_type in ("LineString", "LinearRing"): out.append(np.asarray(g.coords))
        elif g.geom_type in ("MultiLineString", "GeometryCollection"): out += _poly_lines(g)
        elif g.geom_type == "Polygon": out.append(np.asarray(g.exterior.coords))
    return out


def _scalebar_arrow(ax, x0, y0, km=20):
    import matplotlib.patheffects as pe
    ax.plot([x0, x0 + km * 1e3], [y0, y0], color=ps.INK, lw=1.2, solid_capstyle="butt")
    for xx in (x0, x0 + km * 1e3): ax.plot([xx, xx], [y0 - 600, y0 + 600], color=ps.INK, lw=0.8)
    ax.text(x0 + km * 5e2, y0 + 1500, f"{km} km", ha="center", va="bottom", fontsize=ps.TICK, color=ps.INK)
    ax.annotate("", xy=(x0 + km * 1.4e3, y0 + 9000), xytext=(x0 + km * 1.4e3, y0 + 1000), arrowprops=dict(arrowstyle="-|>", color=ps.INK, lw=1.0))
    ax.text(x0 + km * 1.4e3, y0 + 9800, "N", ha="center", va="bottom", fontsize=ps.FONT, color=ps.INK, fontweight="bold")


def _base(ax, L, c6, nb, minor=True):
    import matplotlib.patheffects as pe
    nb = nb.assign(geometry=nb.geometry.simplify(60)); c6 = c6.assign(geometry=c6.geometry.simplify(40))
    nb.plot(ax=ax, facecolor="#f4f3ef", edgecolor="#c9c7bf", lw=0.4, zorder=0, rasterized=True)
    c6.plot(ax=ax, facecolor="white", edgecolor="none", zorder=0, rasterized=True)
    if minor: _lines(ax, L, ["tertiary"], colors="#d9d7d0", linewidths=0.25, zorder=1, rasterized=True)
    _lines(ax, L, ["secondary"], colors="#bdbab2", linewidths=0.35, zorder=1, rasterized=True)
    _lines(ax, L, ["primary"], colors="#9a978f", linewidths=0.5, zorder=2, rasterized=True)
    _lines(ax, L, ["motorway", "trunk"], colors="#5f5d57", linewidths=0.9, zorder=3, rasterized=True)
    c6.boundary.plot(ax=ax, color=ps.INK, lw=0.7, zorder=4, rasterized=True)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.grid(False); ax.set_xlabel(""); ax.set_ylabel("")
    for sp in ax.spines.values(): sp.set_visible(True); sp.set_color(ps.AXIS); sp.set_linewidth(0.6)


def figure_study_area(L, c6, nb, SLG, St, path):
    """Main-text map: study area, MATSim 2024 network by class, screenlines S1-S7, mainline count stations, closed Key Bridge; core inset."""
    import matplotlib.pyplot as plt, matplotlib.patheffects as pe
    from matplotlib.lines import Line2D
    from pyproj import Transformer
    halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    kb = Transformer.from_crs(4326, CRS, always_xy=True).transform(*KEY_BRIDGE)
    fig = ps.new_figure(5.75); ax = fig.add_axes([0.0, 0.135, 1.0, 0.865])
    _base(ax, L, c6, nb)
    cols = {k: ps.CAT[k] for k in range(1, 8)}   # CAT[0] (blue) is the model colour
    for sid, g in SLG.items():
        for a in _poly_lines(g): ax.plot(a[:, 0], a[:, 1], color=cols[sid], lw=2.0, zorder=6, solid_capstyle="round")
    ax.scatter(St.x, St.y, s=1.2, color=ps.INK2, lw=0, zorder=7, rasterized=True)
    ax.scatter([kb[0]], [kb[1]], marker="X", s=40, color=ps.INK, edgecolor="white", lw=0.5, zorder=9)
    x0, x1, y0, y1 = 365000, 492000, 104000, 235000; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    lab = {24013: ("Carroll", 392000, 207000), 24005: ("Baltimore\nCounty", 430000, 211000), 24025: ("Harford", 458000, 213000),
           24027: ("Howard", 400000, 177000), 24003: ("Anne\nArundel", 438000, 140000)}
    for f, (t, x, y) in lab.items(): ax.text(x, y, t, ha="center", va="center", fontsize=ps.FONT, color=ps.INK, fontweight="bold", path_effects=halo, zorder=10)
    for t, x, y in [("Pennsylvania", 410000, 231000), ("Frederick", 371500, 196000), ("Montgomery", 381000, 158000), ("Prince\nGeorge's", 410000, 128000),
                    ("Chesapeake\nBay", 449000, 124000)]:
        ax.text(x, y, t, ha="center", va="center", fontsize=ps.TICK, color=ps.MUTED, style="italic", path_effects=halo, zorder=10)
    slab = {2: (402000, 191500), 4: (393000, 168000), 5: (452000, 204500), 6: (418500, 216000), 7: (380500, 223000), 1: (414000, 186000), 3: (443000, 196500)}
    for sid, (x, y) in slab.items():
        ax.text(x, y, f"S{sid}", ha="center", va="center", fontsize=ps.FONT, color=cols[sid], fontweight="bold", path_effects=halo, zorder=11)
    # inset: Baltimore core
    bx0, bx1, by0, by1 = 415000, 450000, 163000, 198000
    ax.plot([bx0, bx1, bx1, bx0, bx0], [by0, by0, by1, by1, by0], color=ps.INK2, lw=0.6, zorder=8)
    fig.canvas.draw()                                       # inset over open water and the Eastern Shore (outside the study area)
    (fx0, fy0), (fx1, fy1) = fig.transFigure.inverted().transform(ax.transData.transform([(453500, 149500), (492000, 188000)]))
    ia = fig.add_axes([fx0, fy0, fx1 - fx0, fy1 - fy0]); _base(ia, L, c6, nb, minor=True)
    for sid, g in SLG.items():
        for a in _poly_lines(g): ia.plot(a[:, 0], a[:, 1], color=cols[sid], lw=2.0, zorder=6, solid_capstyle="round")
    s2 = St[St.x.between(bx0, bx1) & St.y.between(by0, by1)]
    ia.scatter(s2.x, s2.y, s=2.0, color=ps.INK2, lw=0, zorder=7, rasterized=True)
    ia.scatter([kb[0]], [kb[1]], marker="X", s=55, color=ps.INK, edgecolor="white", lw=0.6, zorder=9)
    ia.set_xlim(bx0, bx1); ia.set_ylim(by0, by1)
    ia.text(431500, 184000, "Baltimore\nCity", ha="center", va="center", fontsize=ps.FONT, fontweight="bold", color=ps.INK, path_effects=halo, zorder=10)
    for sid, (x, y) in {1: (420500, 188500), 3: (419500, 194500), 2: (423500, 175000)}.items():
        ia.text(x, y, f"S{sid}", ha="center", va="center", fontsize=ps.FONT, color=cols[sid], fontweight="bold", path_effects=halo, zorder=11)
    ia.text(kb[0] - 1200, kb[1] - 1800, "Key Bridge\n(closed 2024)", ha="right", va="top", fontsize=ps.TICK, color=ps.INK, path_effects=halo, zorder=11)
    _scalebar_arrow(ax, 369000, 108000)
    hs = [Line2D([], [], color=cols[k], lw=2.0, label=f"S{k} {SHORT[k]}") for k in SHORT]
    hs += [Line2D([], [], color="#5f5d57", lw=0.9, label="Motorway, trunk road"), Line2D([], [], color="#9a978f", lw=0.5, label="Primary road"),
           Line2D([], [], color="#bdbab2", lw=0.6, label="Secondary, tertiary road"),
           Line2D([], [], marker="o", ls="", color=ps.INK2, ms=2, label="Count station (mainline)"),
           Line2D([], [], marker="X", ls="", color=ps.INK, ms=5, label="Key Bridge, closed in 2024")]
    fig.legend(handles=hs, loc="lower center", bbox_to_anchor=(0.5, 0.0), fontsize=ps.TICK, frameon=False, ncol=3)
    return ps.finish(fig, path)


def figure_screenlines(L, c6, nb, SLG, X, T, path):
    """Supplement map: crossing links, counted (filled) or not (open), and the model/count ratio of each screenline."""
    import matplotlib.pyplot as plt, matplotlib.patheffects as pe
    from matplotlib.lines import Line2D
    halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    cols = {k: ps.CAT[k] for k in range(1, 8)}   # CAT[0] (blue) is the model colour
    fig = ps.new_figure(3.55)
    axs = [fig.add_axes([0.0, 0.1, 0.495, 0.83]), fig.add_axes([0.505, 0.1, 0.495, 0.83])]
    ext = [(365000, 492000, 104000, 235000), (415000, 450000, 163000, 198000)]
    C = X.groupby("crossing").agg(sl=("sl", "first"), x=("xc", "mean"), y=("yc", "mean"), counted=("station", lambda s: s.notna().any()))
    R = T[T.section == "all"].set_index("sl")
    for k, (ax, (x0, x1, y0, y1)) in enumerate(zip(axs, ext)):
        _base(ax, L, c6, nb, minor=(k == 1))
        for sid, g in SLG.items():
            for a in _poly_lines(g): ax.plot(a[:, 0], a[:, 1], color=cols[sid], lw=1.6, zorder=6)
        c = C[C.x.between(x0, x1) & C.y.between(y0, y1)]
        ax.scatter(c[c.counted].x, c[c.counted].y, s=10 if k else 6, color=ps.INK, lw=0, zorder=8)
        ax.scatter(c[~c.counted].x, c[~c.counted].y, s=10 if k else 6, facecolor="white", edgecolor=ps.INK, lw=0.6, zorder=8)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    pos0 = {2: (398000, 195000), 4: (390000, 163000), 5: (462000, 202000), 6: (420000, 219000), 7: (389000, 225000)}
    pos1 = {1: (424000, 187500), 2: (438000, 166000), 3: (419000, 196000)}
    axs[0].text(441000, 152000, "(b)", ha="center", va="center", fontsize=ps.TICK, color=ps.INK2, path_effects=halo, zorder=11)
    for ax, pos in ((axs[0], pos0), (axs[1], pos1)):
        for sid, (x, y) in pos.items():
            r = R.loc[sid]
            ax.text(x, y, f"S{sid}  {r.ratio_all:.2f} / {r.ratio_pass:.2f}", ha="center", va="center", fontsize=ps.TICK, color=cols[sid], fontweight="bold", path_effects=halo, zorder=11)
    axs[0].plot([415000, 450000, 450000, 415000, 415000], [163000, 163000, 198000, 198000, 163000], color=ps.INK2, lw=0.6, zorder=7)
    _scalebar_arrow(axs[0], 369000, 108000)
    hs = [Line2D([], [], marker="o", ls="", color=ps.INK, ms=3.5, label="Counted crossing"),
          Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=ps.INK, ms=3.5, label="Crossing without a count")]
    fig.legend(handles=hs, loc="lower center", ncol=2, fontsize=ps.TICK, frameon=False, bbox_to_anchor=(0.5, 0.0))
    return ps.finish(fig, path, panel_labels="ab")


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("vc_dir"); ap.add_argument("lh_dir"); ap.add_argument("out_dir")
    ap.add_argument("--article", default=f"{V}/5_reports/article"); a = ap.parse_args()
    D = f"{a.out_dir}/data"; os.makedirs(D, exist_ok=True)
    St = pd.read_csv(f"{a.vc_dir}/stations_model_vs_count.csv", low_memory=False, dtype={"link_NE": str, "link_SW": str})
    PS = pd.read_csv(f"{a.vc_dir}/stations_by_seed.csv.gz")
    seeds = sorted(set(PS.seed) & {int(re.search(r"_s(\d+)\.csv\.gz$", f).group(1)) for f in glob.glob(f"{a.lh_dir}/link_hours_s*.csv.gz") if re.search(r"_s(\d+)\.csv\.gz$", f)})
    if not seeds: sys.exit("no seed with both stations_by_seed and link_hours_s<seed>.csv.gz")
    print("seeds", seeds)
    cache = os.environ.get("SL_CACHE")                     # development only: pickle of the geometry step
    if cache and os.path.exists(cache):
        import pickle; L, c6, nb, river, ring, X, nrep = pickle.load(open(cache, "rb"))
    else:
        nodes, L = network(); cty, c6, nb = node_county(nodes); river = osm_rivers(); ring, i695 = beltway_ring(L)
        X = clusters(crossings(L, cty, river, ring, i695), L); nrep = int(X.repeat_dropped.sum()); X = X[~X.repeat_dropped].copy()
        if cache: import pickle; pickle.dump((L, c6, nb, river, ring, X, nrep), open(cache, "wb"))
    G = Graph(L); X = attach_stations(X, G, St)
    U = uncounted_major(X, G, St); U.to_csv(f"{D}/screenline_uncounted_major.csv", index=False, float_format="%.0f")
    M, per = model_links(a.vc_dir, a.lh_dir, seeds)
    T, X = summarise(X, St, M, per, PS, seeds, L)
    T.to_csv(f"{D}/screenline_table.csv", index=False, float_format="%.4g")
    X.assign(screenline=X.sl.map(SHORT)).drop(columns=["fwy", "repeat_dropped"]).to_csv(f"{D}/screenline_crossings.csv", index=False, float_format="%.6g")
    SLG = {k: shapely.simplify(g, 30) for k, g in add_ticks(screenline_geoms(c6, nb, river, ring), X, L).items()}
    feats = [dict(type="Feature", properties=dict(kind="screenline", sl=k, name=SHORT[k]), geometry=shapely.geometry.mapping(shapely.simplify(g, 20))) for k, g in SLG.items()]
    for r in X.itertuples():
        l = L.loc[r.link]
        feats.append(dict(type="Feature", properties=dict(kind="crossing_link", sl=int(r.sl), link=r.link, crossing=int(r.crossing), road=r.road, hwy=r.hwy, direction=r.direction,
                                                          section=r.section, counted=r.station is not None and r.station == r.station, station=r.station),
                          geometry=dict(type="LineString", coordinates=[[round(l.x0, 1), round(l.y0, 1)], [round(l.x1, 1), round(l.y1, 1)]])))
    json.dump(dict(type="FeatureCollection", crs=dict(type="name", properties=dict(name="urn:ogc:def:crs:EPSG::26985")), features=feats), open(f"{D}/screenlines_definition.geojson", "w"))
    meta = dict(seeds=seeds, repeated_crossing_links_dropped=nrep, river_split_m=float(river_split(river)), trace_m=TRACE_M, classes=CLASSES)
    json.dump(meta, open(f"{D}/screenlines_meta.json", "w"), indent=1)
    latex_table(T, f"{a.article}/sections/tab_net_screenlines.tex", len(seeds))
    latex_table(T, f"{a.article}/sections/supp/tab_net_screenlines_all.tex", len(seeds), main=False)
    latex_table_dir(T, f"{a.article}/sections/supp/tab_net_screenlines_dir.tex", len(seeds))
    stm = St[St["use"] == "mainline"]
    import map_study_area; map_study_area.draw(*map_study_area.counties(), SLG, f"{a.article}/figures/fig_net_study_area")   # clean map: OSM roads, no stations
    figure_screenlines(L, c6, nb, SLG, X, T, f"{a.article}/figures/fig_net_screenlines")
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(T[["name", "crossings", "counted", "cap_share", "count_all", "count_pass", "ratio_all", "ratio_pass", "max_dev_all", "pass_all", "pass_pass",
                 "ratio_all_dir0", "ratio_all_dir1", "model_all_crossings"]].round(3).to_string())


if __name__ == "__main__": main()
