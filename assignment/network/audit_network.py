#!/usr/bin/env python3
"""Link-by-link audit of the 2024 network against MDOT SHA data (the 2026 network differs only by the change list of build_networks.py).

Checks and outputs (all tables in WORKSPACE/data/):
  network_audit_links.parquet         one row per link: MDOT class match, MDOT lanes, posted speeds (OSM tag, MDOT sign), capacity per lane,
                                      study-area flag, connectivity flags
  network_audit_class_crosstab.csv    OSM highway type x MDOT functional class (links and km), study area
  network_audit_class_summary.csv     match rate and agreement by OSM class
  network_audit_lanes.csv             network lanes per direction vs MDOT lane mileage, by class
  network_audit_speeds.csv            posted speed: OSM maxspeed vs MDOT posted-speed-limit signs, and coded free speed, by class
  network_audit_speed_pairs.csv       sign-by-sign comparison (for the figure)
  network_audit_capacity.csv          capacity per lane by class (p10, median, p90) with reference ranges
  network_audit_connectivity.csv      strongly connected component share, dead ends, by class
  network_audit_i695_interchanges.csv ramps present at every I-695 interchange by exit number (OSM junction nodes vs MDOT exit and ramp inventory)
and the report NETWORK_AUDIT.md in this folder.
"""
import os, sys, json, datetime
import numpy as np, pandas as pd, geopandas as gpd, shapely, networkx as nx, osmium
from shapely import points, linestrings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netio import *

NET = f"{HERE}/network_2024.xml.gz"
TODAY = datetime.date.today().isoformat()
nodes, L = read_network(NET)
counties, area = study_area()
print(f"network: {len(nodes):,} nodes, {len(L):,} links")
mid = points(L.xm.values, L.ym.values)
L["in_area"] = shapely.contains_xy(area, L.xm.values, L.ym.values)
R = L[L.car & ~L.is_pt].copy()           # drivable road links
A = R[R.in_area].copy()                   # ... inside the six counties
print(f"car links {len(R):,}; in the six counties {len(A):,} ({A.length.sum()/1000:,.0f} km)")

# ============================================================== 1. functional class
FC = read_geojson("functional_class")
FC = FC[FC.geometry.notna()].explode(index_parts=False).reset_index(drop=True)
FC = FC[FC.geometry.geom_type == "LineString"].reset_index(drop=True)
segs = FC.geometry.values
li, gi, dist = nearest_segment(A, segs, max_dist=20, max_bearing=30)
A["mdot_fc"] = np.nan; A["mdot_dist"] = np.nan; A["mdot_route"] = ""; A["mdot_is_ramp"] = False
A.iloc[li, A.columns.get_loc("mdot_fc")] = FC.FUNCTIONAL_CLASS.values[gi].astype(float)
A.iloc[li, A.columns.get_loc("mdot_dist")] = dist
A.iloc[li, A.columns.get_loc("mdot_route")] = (FC.ID_PREFIX.astype(str) + " " + FC.ID_RTE_NO.astype(str)).values[gi]
A.iloc[li, A.columns.get_loc("mdot_is_ramp")] = (FC.ID_PREFIX.values[gi] == "RP")
A["osm_group"] = A.hwy.map(OSM_GROUP)
A["is_ramp"] = A.hwy.isin(RAMP)
def agree(r):
    if np.isnan(r.mdot_fc): return np.nan
    if r.is_ramp: return bool(r.mdot_is_ramp or r.mdot_fc <= 4)     # a ramp link agrees when MDOT also inventories a ramp or a higher-class road there
    g = r.osm_group
    if np.isnan(g): return np.nan
    if g == 5: return r.mdot_fc in (5, 6)
    if g == 1: return r.mdot_fc in (1, 2)
    if g == 2: return r.mdot_fc in (2, 3)      # OSM trunk = expressway or principal arterial without full access control
    return r.mdot_fc == g
A["fc_agree"] = A.apply(agree, axis=1)
A["fc_delta"] = np.where(A.osm_group.notna() & A.mdot_fc.notna(), A.osm_group - A.mdot_fc, np.nan)   # positive: OSM lower class than MDOT

M = A[A.mdot_fc.notna() & ~A.is_ramp]
ct_n = pd.crosstab(M.hwy_class, M.mdot_fc.astype(int)).reindex(index=[c for c in CLASS_ORDER if c in M.hwy_class.unique()]).fillna(0).astype(int)
ct_km = pd.crosstab(M.hwy_class, M.mdot_fc.astype(int), values=M.length / 1000, aggfunc="sum").reindex(index=ct_n.index).fillna(0).round(1)
ct = pd.concat({"links": ct_n, "km": ct_km}, axis=1); ct.columns = [f"{a}_fc{b}" for a, b in ct.columns]
ct.to_csv(f"{DATA}/network_audit_class_crosstab.csv", index_label="osm_highway")
cs = A.groupby("hwy_class").agg(links=("length", "size"), km=("length", lambda s: s.sum() / 1000), matched=("mdot_fc", lambda s: s.notna().mean()),
                                agree=("fc_agree", lambda s: s.dropna().mean() if s.notna().any() else np.nan),
                                osm_lower=("fc_delta", lambda s: (s > 0).sum()), osm_higher=("fc_delta", lambda s: (s < 0).sum())).reindex([c for c in CLASS_ORDER if c in A.hwy_class.unique()])
cs.loc["all"] = [len(A), A.length.sum() / 1000, A.mdot_fc.notna().mean(), A.fc_agree.dropna().mean(), (A.fc_delta > 0).sum(), (A.fc_delta < 0).sum()]
cs.to_csv(f"{DATA}/network_audit_class_summary.csv", index_label="osm_highway", float_format="%.4f")
agree_all = A.fc_agree.dropna().mean(); agree_km = (A.length * A.fc_agree.fillna(0)).sum() / A.length[A.fc_agree.notna()].sum()
print(f"class: matched {A.mdot_fc.notna().mean():.1%} of links; agreement {agree_all:.1%} of matched links, {agree_km:.1%} of matched km")

# ============================================================== 2. lanes (MDOT lane mileage)
LM = read_geojson("lane_mileage"); LM = LM[LM.geometry.notna()].explode(index_parts=False).reset_index(drop=True)
LM = LM[LM.geometry.geom_type == "LineString"].reset_index(drop=True)
LM["len_mi"] = LM.TO_MEASURE - LM.FROM_MEASURE
LM = LM[LM.len_mi > 0.005].reset_index(drop=True)
LM["lanes_seg"] = (LM.MAINLINE_LANE_MILES / LM.len_mi).round()
LM["route_key"] = LM.ROUTEID.str[:-6]
divided = LM.groupby("route_key").CARDINALITY.nunique() > 1
LM["divided"] = LM.route_key.map(divided)
# the network's two-way roads appear as two directional links between the same node pair
pair = set(zip(A.f, A.t)); A["two_way"] = [((t, f) in pair) for f, t in zip(A.f, A.t)]
li, gi, dist = nearest_segment(A, LM.geometry.values, max_dist=20, max_bearing=30)
A["mdot_lanes_seg"] = np.nan; A["mdot_divided"] = np.nan
A.iloc[li, A.columns.get_loc("mdot_lanes_seg")] = LM.lanes_seg.values[gi]
A.iloc[li, A.columns.get_loc("mdot_divided")] = LM.divided.values[gi].astype(float)
# lanes per direction implied by MDOT: the inventory-direction segment carries the mainline lane-miles of both directions (checked on I-695:
# 2, 3 and 4 network lanes per direction meet 4, 6 and 8 inventoried lanes), so the segment value is halved for every road that has two
# directions (a counterpart link in the network, or a route inventoried with two cardinalities) and kept for one-way streets
A["mdot_lanes_dir"] = np.where(A.two_way | (A.mdot_divided == 1), A.mdot_lanes_seg / 2, A.mdot_lanes_seg)
A["lane_delta"] = A.permlanes - A.mdot_lanes_dir
ln = A[A.mdot_lanes_dir.notna() & (A.mdot_lanes_seg > 0) & ~A.is_ramp]
lt = ln.groupby("hwy_class").agg(links=("length", "size"), km=("length", lambda s: s.sum() / 1000), net_lanes_mean=("permlanes", "mean"), mdot_lanes_mean=("mdot_lanes_dir", "mean"),
                                 equal=("lane_delta", lambda s: (s == 0).mean()), net_fewer=("lane_delta", lambda s: (s < 0).mean()), net_more=("lane_delta", lambda s: (s > 0).mean()),
                                 delta_km_weighted=("lane_delta", lambda s: np.average(s, weights=ln.loc[s.index, "length"]))).reindex([c for c in CLASS_ORDER if c in ln.hwy_class.unique()])
lt.loc["all"] = [len(ln), ln.length.sum() / 1000, ln.permlanes.mean(), ln.mdot_lanes_dir.mean(), (ln.lane_delta == 0).mean(), (ln.lane_delta < 0).mean(), (ln.lane_delta > 0).mean(), np.average(ln.lane_delta, weights=ln.length)]
lt.to_csv(f"{DATA}/network_audit_lanes.csv", index_label="osm_highway", float_format="%.4f")
print(f"lanes: compared {len(ln):,} links; equal {lt.loc['all','equal']:.1%}, network fewer {lt.loc['all','net_fewer']:.1%}, network more {lt.loc['all','net_more']:.1%}")

# ============================================================== 3. posted speeds
O = osm_way_tags()
A["osm_posted"] = A.way.map(O.posted_mph); A["osm_lanes_tag"] = A.way.map(O.lanes_tag)
A["freespeed_mph"] = A.freespeed * MPH
S = read_geojson("speed_limit_signs"); S = S[S.geometry.notna() & S.SpeedLimit.between(10, 75)].reset_index(drop=True)
S = S[S.within(area)].reset_index(drop=True)
DIRB = {"NB": 90, "SB": 270, "EB": 0, "WB": 180}
# sign -> nearest car link within 30 m whose direction agrees with the sign's travel direction (within 60 degrees); signs face the traffic they regulate
tree = shapely.STRtree(link_geoms(A)); pts = S.geometry.values
si, ai = tree.query(pts, predicate="dwithin", distance=30)
cand = pd.DataFrame(dict(sign=si, link_pos=ai)); cand["dist"] = shapely.distance(pts[si], link_geoms(A)[ai])
cand["bearing"] = A.bearing.values[ai]; cand["dir"] = S.TravelDirection.values[si]
cand["dir_ok"] = [bearing_diff(b, DIRB.get(d, np.nan)) <= 60 if d in DIRB else True for b, d in zip(cand.bearing, cand.dir)]
cand = cand[cand.dir_ok].sort_values(["sign", "dist"]).drop_duplicates("sign")
SP = pd.DataFrame(dict(sign=cand.sign.values, link=A.index.values[cand.link_pos.values], dist_m=cand.dist.values.round(1), mdot_sign_mph=S.SpeedLimit.values[cand.sign.values].astype(float),
                       route=S.Route.values[cand.sign.values], direction=S.TravelDirection.values[cand.sign.values]))
SP["hwy_class"] = A.hwy_class.reindex(SP.link).values; SP["osm_posted"] = A.osm_posted.reindex(SP.link).values; SP["freespeed_mph"] = A.freespeed_mph.reindex(SP.link).values.round(1)
SP["osm_minus_mdot"] = SP.osm_posted - SP.mdot_sign_mph; SP["coded_minus_mdot"] = SP.freespeed_mph - SP.mdot_sign_mph
SP.to_csv(f"{DATA}/network_audit_speed_pairs.csv", index=False)
A["mdot_sign_mph"] = SP.groupby("link").mdot_sign_mph.median().reindex(A.index).values
def sp_stats(d):
    e = d.dropna(subset=["osm_posted"])
    return pd.Series(dict(signs=len(d), with_osm_tag=len(e), osm_equal=(e.osm_minus_mdot == 0).mean() if len(e) else np.nan, osm_within5=(e.osm_minus_mdot.abs() <= 5).mean() if len(e) else np.nan,
                          osm_minus_mdot_mean=e.osm_minus_mdot.mean() if len(e) else np.nan, osm_minus_mdot_p10=e.osm_minus_mdot.quantile(.1) if len(e) else np.nan, osm_minus_mdot_p90=e.osm_minus_mdot.quantile(.9) if len(e) else np.nan,
                          mdot_mean=d.mdot_sign_mph.mean(), coded_mean=d.freespeed_mph.mean(), coded_minus_mdot_mean=d.coded_minus_mdot.mean(), coded_minus_mdot_p10=d.coded_minus_mdot.quantile(.1), coded_minus_mdot_p90=d.coded_minus_mdot.quantile(.9)))
st = SP.groupby("hwy_class").apply(sp_stats).reindex([c for c in CLASS_ORDER if c in SP.hwy_class.unique()]); st.loc["all"] = sp_stats(SP)
st.to_csv(f"{DATA}/network_audit_speeds.csv", index_label="osm_highway", float_format="%.3f")
# OSM maxspeed coverage by class (study area)
cov = A.groupby("hwy_class").agg(links=("length", "size"), osm_tag_share=("osm_posted", lambda s: s.notna().mean()), osm_posted_median=("osm_posted", "median"), coded_median_mph=("freespeed_mph", "median")).reindex([c for c in CLASS_ORDER if c in A.hwy_class.unique()])
cov.to_csv(f"{DATA}/network_audit_speed_coverage.csv", index_label="osm_highway", float_format="%.3f")
print(f"speeds: {len(S):,} MDOT signs in area, {len(SP):,} matched to a link; OSM tag on {SP.osm_posted.notna().mean():.1%} of them; equal {st.loc['all','osm_equal']:.1%}, within 5 mph {st.loc['all','osm_within5']:.1%}")

# ============================================================== 4. capacity per lane
A["cap_per_lane"] = A.capacity / A.permlanes.clip(lower=1)
REF = {"motorway": "2,000-2,400 (HCM 2016 basic freeway segments, pc/h/ln at free-flow 55-75 mph)", "motorway_link": "1,800-2,200 (HCM ramp roadways)", "trunk": "1,800-2,200 (multilane highways)", "trunk_link": "1,500-2,000",
       "primary": "800-1,200 veh/h/ln (signalised arterial: 1,900 saturation x 0.45-0.60 green)", "primary_link": "800-1,200", "secondary": "700-1,000", "secondary_link": "700-1,000", "tertiary": "500-800", "tertiary_link": "500-800",
       "residential": "300-600", "unclassified": "300-600", "living_street": "200-400", "service": "200-400"}
cp = A.groupby("hwy_class").agg(links=("length", "size"), km=("length", lambda s: s.sum() / 1000), lanes_median=("permlanes", "median"), cpl_p10=("cap_per_lane", lambda s: s.quantile(.1)), cpl_median=("cap_per_lane", "median"), cpl_p90=("cap_per_lane", lambda s: s.quantile(.9)),
                                cpl_distinct=("cap_per_lane", lambda s: s.round().nunique())).reindex([c for c in CLASS_ORDER if c in A.hwy_class.unique()])
cp["reference_range"] = [REF.get(c, "") for c in cp.index]
cp.to_csv(f"{DATA}/network_audit_capacity.csv", index_label="osm_highway", float_format="%.1f")

# ============================================================== 5. connectivity
G = nx.DiGraph(); G.add_edges_from(zip(R.f, R.t, [{"id": i} for i in R.index]))
scc = max(nx.strongly_connected_components(G), key=len)
R["in_scc"] = R.f.isin(scc) & R.t.isin(scc)
outdeg = pd.Series(dict(G.out_degree())); indeg = pd.Series(dict(G.in_degree()))
R["to_sink"] = R.t.map(outdeg).fillna(0) == 0; R["from_source"] = R.f.map(indeg).fillna(0) == 0
A = A.join(R[["in_scc", "to_sink", "from_source"]])
cn = A.groupby("hwy_class").agg(links=("length", "size"), km=("length", lambda s: s.sum() / 1000), scc_links=("in_scc", "mean"), scc_km=("in_scc", lambda s: np.average(s, weights=A.loc[s.index, "length"])),
                                dead_end_links=("to_sink", "sum"), source_only_links=("from_source", "sum")).reindex([c for c in CLASS_ORDER if c in A.hwy_class.unique()])
cn.loc["all (six counties)"] = [len(A), A.length.sum() / 1000, A.in_scc.mean(), np.average(A.in_scc, weights=A.length), A.to_sink.sum(), A.from_source.sum()]
cn.loc["all (whole network)"] = [len(R), R.length.sum() / 1000, R.in_scc.mean(), np.average(R.in_scc, weights=R.length), R.to_sink.sum(), R.from_source.sum()]
cn.to_csv(f"{DATA}/network_audit_connectivity.csv", index_label="osm_highway", float_format="%.5f")
dead_major = A[A.to_sink & A.hwy.isin(["motorway", "motorway_link", "trunk", "trunk_link", "primary", "secondary"])][["hwy", "name", "length", "xm", "ym"]]
dead_major.to_csv(f"{DATA}/network_audit_dead_ends_major.csv", index_label="link", float_format="%.1f")
print(f"connectivity: largest SCC holds {R.in_scc.mean():.2%} of car links ({np.average(R.in_scc, weights=R.length):.2%} of km); dead-end links {R.to_sink.sum():,} (major roads in area: {len(dead_major)})")

# ============================================================== 6. I-695 interchanges by exit number
# OSM motorway_junction nodes (exit refs) from the same extract the network was built from
jpath = f"{DATA}/osm_motorway_junctions.csv"
if not os.path.exists(jpath):
    rows = []
    for o in osmium.FileProcessor(f"{ROOT}/inputs/osm/maryland-latest.osm.pbf", osmium.osm.NODE).with_filter(osmium.filter.KeyFilter("highway")):
        if o.tags.get("highway") == "motorway_junction": rows.append((o.id, o.location.lon, o.location.lat, o.tags.get("ref", ""), o.tags.get("name", "")))
    J = pd.DataFrame(rows, columns=["node", "lon", "lat", "ref", "name"]); J = gpd.GeoDataFrame(J, geometry=gpd.points_from_xy(J.lon, J.lat), crs=4326).to_crs(CRS)
    J["x"] = J.geometry.x; J["y"] = J.geometry.y; J.drop(columns="geometry").to_csv(jpath, index=False)
J = pd.read_csv(jpath, dtype={"ref": str}); J["ref"] = J.ref.fillna("")
belt = A[(A.name == "Baltimore Beltway") & (A.hwy == "motorway")]
bt = shapely.STRtree(link_geoms(belt)); jp = points(J.x.values, J.y.values)
ji, bi = bt.query(jp, predicate="dwithin", distance=40)
JB = J.iloc[np.unique(ji)].copy(); JB = JB[JB.ref != ""]
# loop direction of the mainline link next to the junction: inner loop = clockwise (I-695 N/E on the west side) -- recorded as the link's bearing
import re as _re
def exit_num(r):
    m = _re.match(r"\s*(\d+)", str(r)); return int(m.group(1)) if m else -1
JB["exit"] = JB.ref.map(exit_num); JB = JB[JB.exit > 0]
ramps = A[A.hwy == "motorway_link"]; rt = shapely.STRtree(link_geoms(ramps))
belt_nodes = set(belt.f) | set(belt.t)
# MDOT: SHA interchange-exit points on IS 695 (SHA-maintained section) and the SHA ramp inventory of route RP 695 (all exits)
EX = read_geojson("interchange_exits"); ex695 = EX[(EX.ID_PREFIX == "IS") & (EX.ID_RTE_NO == 695)].copy()
ex695["exit"] = ex695.EXIT_NO.str.replace("EXIT #", "", regex=False).map(exit_num)
rp = FC[(FC.ID_PREFIX == "RP") & (FC.ID_RTE_NO == 695)].copy(); rp["exit"] = rp.EXIT_NUMBER.map(exit_num)
rows = []
for ex, g in JB.groupby("exit"):
    pts_ = points(g.x.values, g.y.values)
    ri = np.unique(rt.query(pts_, predicate="dwithin", distance=500)[1]); rr = ramps.iloc[ri]
    off = rr[rr.f.isin(belt_nodes)]; on = rr[rr.t.isin(belt_nodes)]
    e = ex695[ex695.exit == ex]; r = rp[rp.exit == ex]
    rows.append(dict(exit=ex, osm_refs=";".join(sorted(set(g.ref))), junction_nodes=len(g), off_ramps=len(off), on_ramps=len(on), ramp_links_500m=len(rr), ramp_km=rr.length.sum() / 1000,
                     mdot_exit_point=len(e) > 0, mdot_crossing="; ".join(sorted(set(e.INTERSECTION_ROUTE.astype(str)))) if len(e) else "; ".join(sorted(set(r.ROAD_NAME.astype(str).str.extract(r"TO (.*)$")[0].dropna())))[:80],
                     mdot_ramps_inventoried=len(r), x=g.x.mean(), y=g.y.mean()))
IC = pd.DataFrame(rows).sort_values("exit").reset_index(drop=True)
IC["ramps_both_directions"] = (IC.off_ramps > 0) & (IC.on_ramps > 0)
missing_in_osm = sorted((set(ex695.exit) | set(rp.exit[rp.exit > 0])) - set(IC.exit))
IC.to_csv(f"{DATA}/network_audit_i695_interchanges.csv", index=False, float_format="%.1f")
print(f"I-695: {len(IC)} exits with junction nodes in OSM; {IC.ramps_both_directions.sum()} with on- and off-ramps in the network; MDOT exits/ramps without OSM junction: {missing_in_osm}")

# ============================================================== link table
A[["f", "t", "length", "freespeed", "capacity", "permlanes", "hwy", "hwy_class", "name", "way", "osm_lanes_tag", "osm_posted", "freespeed_mph", "cap_per_lane", "two_way", "x0", "y0", "x1", "y1", "xm", "ym", "bearing",
   "mdot_fc", "mdot_dist", "mdot_route", "mdot_is_ramp", "osm_group", "is_ramp", "fc_agree", "fc_delta", "mdot_lanes_seg", "mdot_divided", "mdot_lanes_dir", "lane_delta", "mdot_sign_mph", "in_scc", "to_sink", "from_source"]].to_parquet(f"{DATA}/network_audit_links.parquet")

# ============================================================== report
def pct(x): return f"{100*x:.1f} %"
K = A.hwy.isin(["motorway", "trunk"]); km_fw = A.length[K].sum() / 1000
by_group = M.groupby("osm_group").apply(lambda d: pd.Series(dict(n=len(d), agree=d.fc_agree.mean(), lower=(d.fc_delta > 0).mean(), higher=(d.fc_delta < 0).mean())))
rep = f"""# Network audit: 2024 road network against MDOT SHA inventories

Audit date {TODAY}. Network: `network_2024.xml.gz` (built by `build_networks.py` from the OpenStreetMap extract of Maryland with
replication timestamp 2026-06-11, converted with pt2matsim in EPSG:26985; freeway capacities from HCM bottleneck analysis; non-freeway
classes reconciled with the MDOT functional classification; posted speeds from the OSM `maxspeed` tag). The 2026 network differs by
the change list in `changes_2024_2026.csv` only. MDOT layers: `fetch_mdot.py`, downloaded {TODAY} into `data/raw/mdot_sha/`.
Study area: the six Baltimore-region counties (Anne Arundel, Baltimore, Baltimore City, Carroll, Harford, Howard).

## Size

| | nodes | links | car links | car links in the six counties | km of car links in the six counties |
|---|---|---|---|---|---|
| network_2024 | {len(nodes):,} | {len(L):,} | {len(R):,} | {len(A):,} | {A.length.sum()/1000:,.0f} |

Freeways and expressways (motorway, trunk) in the six counties: {K.sum():,} links, {km_fw:,.0f} km; ramps: {A.is_ramp.sum():,} links.

## 1 Functional class (MDOT SHA Roadway Functional Classification)

Method: the nearest MDOT centreline segment within 20 m of the link midpoint with a bearing within 30 degrees of the link. OSM classes map to
MDOT groups as motorway = 1 or 2, trunk = 2 or 3 (an OSM trunk road is an expressway or a principal arterial without full access control), primary = 3,
secondary = 4, tertiary = 5 or 6, residential/unclassified/living_street/service = 7. Ramps agree when MDOT inventories a ramp or a class 1-4 road there.

- Matched: {pct(A.mdot_fc.notna().mean())} of car links in the area ({pct(np.average(A.mdot_fc.notna(), weights=A.length))} of km). Unmatched links are mostly service roads,
  driveways and private roads that MDOT does not inventory, and links farther than 20 m from the inventoried centreline (dual carriageways with wide medians).
- Agreement: {pct(agree_all)} of matched links, {pct(agree_km)} of matched km. OSM lower than MDOT (e.g. OSM residential, MDOT collector): {int((A.fc_delta > 0).sum()):,} links;
  OSM higher than MDOT: {int((A.fc_delta < 0).sum()):,} links.
- By OSM group (non-ramp links): {"; ".join(f"group {int(g)}: n={int(r.n):,}, agree {pct(r.agree)}, OSM lower {pct(r.lower)}, OSM higher {pct(r.higher)}" for g, r in by_group.iterrows())}.

Crosstab (links and km): `data/network_audit_class_crosstab.csv`; summary by class: `data/network_audit_class_summary.csv`; figure `fig_net_class_matrix`.

Resolution: the supply network already carries the capacity and base speed of the MDOT class wherever MDOT rates a road higher than OSM
(links were upgraded, never downgraded, in `build_network_v8.py`); the residual "OSM lower" cells are links whose MDOT match failed the 20 m / 30 degree
test in that step or whose MDOT class is 1-2 while OSM has primary/secondary (expressway sections of US 40, MD 295, MD 10 and similar, where
OSM tags the road trunk/primary). These links keep their OSM-class capacity; their count and km are stated above and in the crosstab. The
"OSM higher" cells (OSM primary, MDOT minor arterial or collector) are left as in OSM: MDOT's classification is a federal-aid category, OSM's
is a traffic-role tag, and for assignment the higher capacity is the conservative choice on a road that carries arterial traffic. Both groups
are flagged per link in `network_audit_links.parquet` (`fc_delta`) so count-station comparisons can be stratified by agreement.

## 2 Lanes (MDOT SHA Roadway Lane Mileage)

Method: mainline lane-miles divided by segment length gives the inventoried through lanes of both directions (the inventory-direction segment
carries the total; verified on I-695 where 2, 3 and 4 network lanes per direction meet 4, 6 and 8 inventoried lanes); the total is halved for
every road with two directions and kept for one-way streets. Compared with the network's `permlanes` for {len(ln):,} non-ramp links matched within 20 m.

- Equal lanes: {pct(lt.loc['all','equal'])}; network fewer: {pct(lt.loc['all','net_fewer'])}; network more: {pct(lt.loc['all','net_more'])}; km-weighted mean difference (network minus MDOT) {lt.loc['all','delta_km_weighted']:+.2f} lanes.
- By class: {"; ".join(f"{c}: equal {pct(r.equal)}, fewer {pct(r.net_fewer)}, more {pct(r.net_more)} (n={int(r.links):,})" for c, r in lt.drop('all').iterrows())}.

Table: `data/network_audit_lanes.csv`. The freeway lane counts were set from MDOT lane counts at the HCM capacity step (I-695) and from the
OSM `lanes` tag elsewhere; differences on arterials are dominated by turn lanes at intersections (MDOT counts through lanes only) and by
OSM ways tagged with the two-way total on one-way pairs. Resolution: lanes are left as coded; capacity on arterials is governed by the per-lane
value of the class (section 4), and the lane difference is reported per link (`lane_delta`) for the count comparison.

## 3 Posted speeds (OSM maxspeed vs MDOT SHA posted-speed-limit signs)

Method: each of the {len(S):,} MDOT sign records in the area is attached to the nearest car link within 30 m whose direction agrees with the sign's
travel direction; {len(SP):,} signs attach. The sign's limit is compared with the OSM `maxspeed` tag of the link's way (available for {pct(SP.osm_posted.notna().mean())} of
attached signs) and with the coded free speed.

- OSM tag equals the MDOT sign: {pct(st.loc['all','osm_equal'])}; within 5 mph: {pct(st.loc['all','osm_within5'])}; mean difference (OSM minus MDOT) {st.loc['all','osm_minus_mdot_mean']:+.1f} mph (p10 {st.loc['all','osm_minus_mdot_p10']:+.0f}, p90 {st.loc['all','osm_minus_mdot_p90']:+.0f}).
- Coded free speed minus MDOT sign: mean {st.loc['all','coded_minus_mdot_mean']:+.1f} mph (p10 {st.loc['all','coded_minus_mdot_p10']:+.0f}, p90 {st.loc['all','coded_minus_mdot_p90']:+.0f}). On non-freeway classes the coded speed is
  below the posted limit by construction (class base speed scaled by posted / class median, so that signal delay and stops are carried by the link speed).
- OSM `maxspeed` coverage in the area: {"; ".join(f"{c} {pct(r.osm_tag_share)}" for c, r in cov.iterrows() if c in ('motorway','trunk','primary','secondary','tertiary','residential'))}.
- By class: {"; ".join(f"{c}: n={int(r.signs)}, equal {pct(r.osm_equal)}, within 5 mph {pct(r.osm_within5)}" for c, r in st.drop('all').iterrows() if r.with_osm_tag >= 10)}.

Tables: `data/network_audit_speeds.csv`, `data/network_audit_speed_pairs.csv`, coverage `data/network_audit_speed_coverage.csv`; figure `fig_net_speed_osm_mdot`.
Resolution: the signs cover state routes only (MDOT SHA inventory) and give the limit at the sign, which changes between signs; a difference of
5 mph within a tagged way is the resolution of the comparison. Links where the OSM tag and the sign differ by more than 5 mph are listed in the
pairs table with the sign's route and milepost; they are not corrected here because the sign inventory has no segment extent and a one-sided change would
mix two sources on one road. The NPMRDS free-flow and congested speed check is open (section 7).

## 4 Capacity per lane by class

| class | links | km | lanes (median) | capacity per lane p10 | median | p90 | reference |
|---|---|---|---|---|---|---|---|
""" + "\n".join(f"| {c} | {int(r.links):,} | {r.km:,.0f} | {r.lanes_median:.0f} | {r.cpl_p10:,.0f} | {r.cpl_median:,.0f} | {r.cpl_p90:,.0f} | {r.reference_range} |" for c, r in cp.iterrows()) + f"""

Table: `data/network_audit_capacity.csv`. Freeway and ramp capacities on I-695 are HCM bottleneck values (merge, diverge, weave and lane-drop
segments), the remaining freeways carry 2,000 veh/h/lane; arterials carry one value per class from the converter, scaled by the MDOT class where
a link was upgraded. The arterial values sit at the top of or above the signalised reference range; they are stated here and tested by the count
comparison at arterial stations (stage 4 report), not changed before that test.

## 5 Connectivity

- Largest strongly connected component: {100*R.in_scc.mean():.3f} % of car links in the whole network ({100*np.average(R.in_scc, weights=R.length):.3f} % of km); in the six counties {100*A.in_scc.mean():.3f} % of links
  ({int((~A.in_scc).sum()):,} links outside it).
- Dead-end links (no outgoing car link at the end node): {int(R.to_sink.sum()):,} in the whole network, {int(A.to_sink.sum()):,} in the six counties, of which {len(dead_major)} on
  motorway/trunk/primary/secondary links (`data/network_audit_dead_ends_major.csv`{': ' + '; '.join(f'{r.hwy} {r["name"] or "(unnamed)"} at ({r.xm/1000:.1f}, {r.ym/1000:.1f}) km' for _, r in dead_major.iterrows()) if len(dead_major) else ''}).
  Two-way streets end in a node that still has the return link, so cul-de-sacs are not dead ends; at the closed Key Bridge the I-695 mainline is cut at the
  exit 44 and exit 1 junction nodes, whose ramps carry the traffic back.
- Source-only links (no incoming car link at the start node): {int(A.from_source.sum()):,} in the six counties.

Table: `data/network_audit_connectivity.csv`. Agents can only be routed inside the strongly connected component; the count-station matching
step verifies that every matched link is inside it.

## 6 I-695 interchanges by exit number

Method: OSM `motorway_junction` nodes within 40 m of an I-695 mainline link give the exit numbers (`data/osm_motorway_junctions.csv`; the letter
suffixes A/B/C of split exits are grouped under the exit number); for each exit, motorway_link links within 500 m are classified as off-ramps
(leaving a Beltway node) or on-ramps (joining one). MDOT: SHA interchange-exit points (exits 4-32, the SHA-maintained section) and the SHA ramp
inventory of route RP 695 (all exits, including the MDTA-maintained section, exits 1-3 and 33-44; I-695 has no exit 37).

- Exits with junction nodes in OSM: {len(IC)} ({IC.exit.min()}-{IC.exit.max()}); with both on- and off-ramps in the network: {int(IC.ramps_both_directions.sum())}.
- Exits in the MDOT inventories without an OSM junction node: {missing_in_osm if missing_in_osm else 'none'}.
- Exits without ramps in one direction: {", ".join(f"{r.exit} (off {r.off_ramps}, on {r.on_ramps})" for _, r in IC[~IC.ramps_both_directions].iterrows()) or 'none'}.

| exit | OSM refs | crossing road (MDOT) | off-ramps | on-ramps | MDOT ramps inventoried |
|---|---|---|---|---|---|
""" + "\n".join(f"| {r.exit} | {r.osm_refs} | {r.mdot_crossing} | {r.off_ramps} | {r.on_ramps} | {r.mdot_ramps_inventoried} |" for _, r in IC.iterrows()) + """

Table: `data/network_audit_i695_interchanges.csv`. Between exit 44 (MD 695A, Hawkins Point) and exit 1 (MD 173, Quarantine Road) the mainline
is cut at the closed Key Bridge in both loops; the ramps of these two exits are the ends of the Beltway in the 2024 and 2026 networks. Ramp capacities and gore geometry on I-695 were set from HCM and MDOT lane
counts in the supply network (`PRICING_HOME/12_corridor_fit/fix_ramps.py`); this audit checks presence, not capacity.

## 7 Open items

- NPMRDS travel times (free-flow and congested speeds by segment, 2024) are not available: the RITIS portal requires an account and a data
  request (`MATSIM_HOME/data/npmrds_2023/README_ACCESS.md`). The free-flow and congested speed check stays open until the extract is obtained.
- MDOT posted speeds exist only as a sign inventory on state routes; county and city roads are checked against the OSM tag alone.
- The 2026 network has no observed counterpart yet; its only difference from 2024 is the change list.
"""
open(f"{HERE}/NETWORK_AUDIT.md", "w").write(rep)
print("written NETWORK_AUDIT.md")
