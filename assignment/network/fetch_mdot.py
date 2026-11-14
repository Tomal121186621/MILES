#!/usr/bin/env python3
"""Download the MDOT SHA roadway layers used by the network audit into Validation_2026/data/raw/mdot_sha/ (one file per layer,
GeoJSON in EPSG:26985, paged through the ArcGIS REST API; a manifest records URL, query, record count and download date).
Layers (ArcGIS organisation njFNhDsUCentVYJW = MDOT SHA open data):
  functional_class   Roadway Functional Classification, study-area extent (incl. EXIT_NUMBER / RAMP_NUMBER of ramps)
  interchange_exits  Roadway Interchange Exits (points, exit number and crossing route)
  speed_limit_signs  Roadway Sign Inventory, posted speed-limit signs (points with SpeedLimit, Route, TravelDirection)
  lane_mileage       Roadway Lane Mileage (segments with mainline / auxiliary lane-miles -> through lanes)
  projects           SHA project portal, construction and completed projects in the six study-area counties
The study-area extent is the bounding box of the six Baltimore-region counties (bmr_counties.gpkg) plus 2 km."""
import json, os, sys, time, urllib.request, urllib.parse, datetime
import geopandas as gpd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RAW = f"{ROOT}/Validation_2026/data/raw/mdot_sha"; os.makedirs(RAW, exist_ok=True)
BASE = "https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services"
cty = gpd.read_file(f"{ROOT}/Updated MATSim/data/bmr_counties.gpkg").to_crs(26985)
x0, y0, x1, y1 = cty.total_bounds; BBOX = f"{x0-2000},{y0-2000},{x1+2000},{y1+2000}"
COUNTIES_SHA = ["Anne Arundel", "Baltimore", "Baltimore City", "Carroll", "Harford", "Howard"]

LAYERS = {
    "functional_class": ("MDOT_SHA_Roadway_Functional_Classification", "1=1", True),
    "interchange_exits": ("MDOT_SHA_Roadway_Interchange_Exits", "1=1", True),
    "speed_limit_signs": ("MDOT_SHA_Roadway_Sign_Inventory_3M_Posted_Speed_Limit_Signs", "1=1", True),
    "lane_mileage": ("MDOT_SHA_Roadway_Lane_Mileage", "1=1", True),
    "projects_construction": ("MDOT_SHA_Projects_(Construction)", "1=1", False),
    "projects_completed": ("MDOT_SHA_Project_Portal_(Completed)", "1=1", False),
}

def fetch(service, where, spatial, page=2000):
    feats, offset = [], 0
    while True:
        q = {"where": where, "outFields": "*", "f": "geojson", "outSR": "26985", "resultOffset": offset, "resultRecordCount": page}
        if spatial: q.update({"geometry": BBOX, "geometryType": "esriGeometryEnvelope", "inSR": "26985", "spatialRel": "esriSpatialRelIntersects"})
        url = f"{BASE}/{urllib.parse.quote(service)}/FeatureServer/0/query?" + urllib.parse.urlencode(q)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=120) as r: d = json.load(r); break
            except Exception as e:
                if attempt == 4: raise
                time.sleep(3 * (attempt + 1))
        if "error" in d: raise RuntimeError(d["error"])
        feats += d["features"]
        if not d.get("properties", {}).get("exceededTransferLimit") and len(d["features"]) < page: break
        offset += len(d["features"])
    return feats, url.split("?")[0]

manifest = {}
for key, (service, where, spatial) in LAYERS.items():
    out = f"{RAW}/{key}.geojson"
    if os.path.exists(out) and "--force" not in sys.argv:
        print("kept", out); continue
    feats, url = fetch(service, where, spatial)
    json.dump({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:26985"}}, "features": feats}, open(out, "w"))
    manifest[key] = {"service_url": url, "where": where, "bbox_26985": BBOX if spatial else None, "features": len(feats), "downloaded": datetime.date.today().isoformat()}
    print(f"{key}: {len(feats):,} features -> {out}")
mp = f"{RAW}/manifest.json"
old = json.load(open(mp)) if os.path.exists(mp) else {}
old.update(manifest); json.dump(old, open(mp, "w"), indent=1)
print("manifest", mp)
