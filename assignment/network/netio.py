"""Shared readers for the network step: MATSim network (streaming parser), study-area polygon, MDOT layers, OSM way tags."""
import os, re, gzip, json
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely import linestrings, points

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
V26 = f"{ROOT}/Validation_2026"
RAW = f"{V26}/data/raw/mdot_sha"
DATA = f"{V26}/data"
CRS = 26985
FREEWAY = {"motorway", "trunk"}; RAMP = {"motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
# OSM highway class -> MDOT functional-class group (1 interstate, 2 freeway/expressway, 3 principal arterial, 4 minor arterial, 5/6 collector, 7 local)
OSM_GROUP = {"motorway": 1, "trunk": 2, "primary": 3, "secondary": 4, "tertiary": 5, "residential": 7, "unclassified": 7, "living_street": 7, "service": 7}
CLASS_ORDER = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "residential", "unclassified", "living_street", "service", "other"]
MDOT_FC = {1: "1 interstate", 2: "2 freeway, expressway", 3: "3 principal arterial", 4: "4 minor arterial", 5: "5 major collector", 6: "6 minor collector", 7: "7 local"}
MPH = 2.23694

def read_network(path):
    """Return (nodes: dict id->(x,y), links: DataFrame indexed by link id with from/to, length, freespeed, capacity, permlanes, modes,
    hwy, name, way, osm_lanes, osm_oneway, and node coordinates x0,y0,x1,y1, midpoint xm,ym, bearing (degrees, east = 0, north = 90))."""
    nodes, rows, cur = {}, [], None
    with gzip.open(path, "rt") as f:
        for line in f:
            if "<node " in line:
                m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', line); nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
            elif "<link " in line:
                m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" freespeed="([^"]+)" capacity="([^"]+)" permlanes="([^"]+)"[^>]*modes="([^"]*)"', line)
                cur = [m.group(1), m.group(2), m.group(3), float(m.group(4)), float(m.group(5)), float(m.group(6)), float(m.group(7)), m.group(8), "", "", "", "", ""]
                if "</link>" in line: rows.append(cur); cur = None
            elif cur is not None:
                if "<attribute " in line:
                    k = re.search(r'name="([^"]+)"', line).group(1); v = re.search(r">([^<]*)<", line); v = v.group(1) if v else ""
                    if k == "osm:way:highway": cur[8] = v
                    elif k == "osm:way:name": cur[9] = v
                    elif k == "osm:way:id": cur[10] = v
                    elif k == "osm:way:lanes": cur[11] = v
                    elif k == "osm:way:oneway": cur[12] = v
                if "</link>" in line: rows.append(cur); cur = None
    L = pd.DataFrame(rows, columns=["link", "f", "t", "length", "freespeed", "capacity", "permlanes", "modes", "hwy", "name", "way", "osm_lanes", "osm_oneway"]).set_index("link")
    L["x0"] = L.f.map(lambda n: nodes[n][0]); L["y0"] = L.f.map(lambda n: nodes[n][1]); L["x1"] = L.t.map(lambda n: nodes[n][0]); L["y1"] = L.t.map(lambda n: nodes[n][1])
    L["xm"] = (L.x0 + L.x1) / 2; L["ym"] = (L.y0 + L.y1) / 2
    L["bearing"] = np.degrees(np.arctan2(L.y1 - L.y0, L.x1 - L.x0)) % 360
    L["car"] = L.modes.str.contains("car"); L["is_pt"] = L.index.str.startswith("pt_")
    L["hwy_class"] = L.hwy.where(L.hwy.isin(CLASS_ORDER), "other")
    return nodes, L

def study_area():
    """Union of the six Baltimore-region counties (EPSG:26985) and the county frame."""
    c = gpd.read_file(f"{ROOT}/Updated MATSim/data/bmr_counties.gpkg").to_crs(CRS)
    return c, c.geometry.union_all()

def link_geoms(L):
    return linestrings(np.stack([np.stack([L.x0.values, L.y0.values], 1), np.stack([L.x1.values, L.y1.values], 1)], 1))

def read_geojson(name):
    G = json.load(open(f"{RAW}/{name}.geojson"))
    return gpd.GeoDataFrame.from_features(G["features"], crs=CRS)

def osm_way_tags():
    O = pd.read_csv(f"{ROOT}/I695_pricing/data/network_v8/osm_way_tags.csv", dtype={"way": str, "maxspeed": str, "lanes": str})
    mph = O.maxspeed.str.extract(r"^\s*(\d+)\s*(mph)?\s*$")[0].astype(float); O["posted_mph"] = mph.where(mph.between(10, 75))
    kmh = O.maxspeed.str.extract(r"^\s*(\d+)\s*km/h\s*$")[0].astype(float); O.loc[O.posted_mph.isna() & kmh.notna(), "posted_mph"] = (kmh / 1.609).round()
    O["lanes_tag"] = pd.to_numeric(O.lanes, errors="coerce")
    return O.set_index("way")

def bearing_diff(a, b):
    """Smallest angle between two directions (0-180)."""
    return np.abs((a - b + 180) % 360 - 180)

def nearest_segment(L_sub, segs, max_dist=20, max_bearing=30, all_matches=True):
    """For each link in L_sub, the nearest segment (shapely linestrings array) within max_dist of the link midpoint whose local bearing
    differs from the link bearing by at most max_bearing degrees (direction-agnostic).  Returns (link positional index, segment index, distance)."""
    tree = shapely.STRtree(segs); mid = points(L_sub.xm.values, L_sub.ym.values)
    li, gi = tree.query_nearest(mid, max_distance=max_dist, all_matches=all_matches, return_distance=False)
    if len(li) == 0: return np.array([], int), np.array([], int), np.array([])
    d = shapely.line_locate_point(segs[gi], mid[li]); a = shapely.line_interpolate_point(segs[gi], np.maximum(d - 5, 0)); b = shapely.line_interpolate_point(segs[gi], d + 5)
    sb = np.degrees(np.arctan2(shapely.get_y(b) - shapely.get_y(a), shapely.get_x(b) - shapely.get_x(a))) % 360
    lb = L_sub.bearing.values[li]; ok = np.minimum(bearing_diff(lb, sb), bearing_diff(lb, sb + 180)) <= max_bearing
    dist = shapely.distance(segs[gi], mid[li])
    li, gi, dist = li[ok], gi[ok], dist[ok]
    # keep the closest per link
    o = np.lexsort((dist, li)); li, gi, dist = li[o], gi[o], dist[o]; first = np.r_[True, li[1:] != li[:-1]]
    return li[first], gi[first], dist[first]
