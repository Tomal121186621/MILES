#!/usr/bin/env python3
"""Build the 2024 and 2026 road networks from the audited supply network (I695_pricing/data/network_v8_supply.xml.gz).

The supply network is built from the Geofabrik OpenStreetMap extract of Maryland (replication timestamp 2026-06-11T20:21:44Z,
file inputs/osm/maryland-latest.osm.pbf), converted with pt2matsim (Updated MATSim/input/network/osm_convert_config.xml,
EPSG:26985), with freeway capacities from HCM bottleneck analysis, non-freeway classes reconciled with the MDOT SHA functional
classification and posted speeds from the OSM maxspeed tag (I695_pricing/12_corridor_fit/build_network_v8.py).  That network
describes the road system as OpenStreetMap had it in June 2026, except that the Francis Scott Key Bridge had been re-inserted
for the 2023 base year (links keybridge_eb, keybridge_wb).

The two target-year networks differ from it only by the change list below.  Each change is a set of link ids resolved here
from the network itself (by id or by a documented geometric selector); every id is checked to exist before it is applied, and
the resolved list is written to changes_2024_2026.csv (one row per change) and changes_2024_2026_links.csv (one row per link).

Outputs (this folder): network_2024.xml.gz, network_2026.xml.gz, changes_2024_2026.csv, changes_2024_2026_links.csv,
build_networks.log.
"""
import os, re, gzip, json, csv, datetime, hashlib
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = f"{ROOT}/I695_pricing/data/network_v8_supply.xml.gz"
RAW = f"{ROOT}/Validation_2026/data/raw/mdot_sha"
TODAY = datetime.date.today().isoformat()

# ------------------------------------------------------------------ read the network (streaming; the file is written back line by line)
nodes, links = {}, {}
cur = None
with gzip.open(SRC, "rt") as f:
    for line in f:
        if "<node " in line:
            m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', line); nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
        elif "<link " in line:
            m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" freespeed="([^"]+)" capacity="([^"]+)" permlanes="([^"]+)"[^>]*modes="([^"]*)"', line)
            cur = dict(id=m.group(1), f=m.group(2), t=m.group(3), length=float(m.group(4)), fs=float(m.group(5)), cap=float(m.group(6)), lanes=float(m.group(7)), modes=m.group(8), hwy="", name="")
            if "</link>" in line: links[cur["id"]] = cur; cur = None
        elif cur is not None:
            if "osm:way:highway" in line: cur["hwy"] = re.search(r">([^<]*)<", line).group(1)
            elif "osm:way:name" in line: cur["name"] = re.search(r">([^<]*)<", line).group(1)
            if "</link>" in line: links[cur["id"]] = cur; cur = None
L = pd.DataFrame.from_dict(links, orient="index")
L["x0"] = L.f.map(lambda n: nodes[n][0]); L["y0"] = L.f.map(lambda n: nodes[n][1]); L["x1"] = L.t.map(lambda n: nodes[n][0]); L["y1"] = L.t.map(lambda n: nodes[n][1])
L["xm"] = (L.x0 + L.x1) / 2; L["ym"] = (L.y0 + L.y1) / 2
print(f"source network: {len(nodes):,} nodes, {len(L):,} links")

# ------------------------------------------------------------------ MDOT interchange exits (for the geometric selectors)
EX = json.load(open(f"{RAW}/interchange_exits.geojson"))
exits = pd.DataFrame([dict(**ft["properties"], x=ft["geometry"]["coordinates"][0], y=ft["geometry"]["coordinates"][1]) for ft in EX["features"]])
def exit_xy(route, exit_no):
    r = exits[(exits.ID_PREFIX == "IS") & (exits.ID_RTE_NO == route) & (exits.EXIT_NO == f"EXIT #{exit_no}")]
    assert len(r) == 1, (route, exit_no, len(r)); return float(r.x.iloc[0]), float(r.y.iloc[0])

# ------------------------------------------------------------------ change list
# Each entry: id, description, selector (function returning link ids), action, years it applies to, source url(s), source date, status.
# 'remove' deletes the link (no vehicle can use it); nodes are kept.  'none' = checked, no change to the network in either year.
CHANGES = []

# 1. Francis Scott Key Bridge, I-695 over the Patapsco River: collapsed 2024-03-26, both directions of I-695 closed at the river since.
#    Replacement: MDTA request for proposals (2024-05-31) listed project completion in fall 2028; MDTA's community update of December 2025
#    gave late 2030 as the anticipated open-to-traffic date.  Closed in 2024 and 2026.  The supply network carries two re-inserted links
#    for the 2023 base year; both are removed.  The mainline and ramp stubs between the MDTA closure points (outer loop at MD 173,
#    inner loop at MD 157) and the river stay in the network as dead ends, as on the ground.
CHANGES.append(dict(change_id="KEY_BRIDGE_CLOSED", description="Francis Scott Key Bridge (I-695 over the Patapsco River) closed in both directions since the collapse of 2024-03-26; replacement not open before late 2030",
                    action="remove", years="2024;2026", select=lambda: ["keybridge_eb", "keybridge_wb"],
                    source_url="https://mva.maryland.gov/major-traffic-alert-detours-place-following-collapse-interstate-695-bridge-over-patapsco-river; https://mdta.maryland.gov/blog-category/mdta-news-releases/mdta-invites-proposals-rebuilding-francis-scott-key-bridge; https://www.dundalkeagle.com/key_bridge/mdta-details-updates-on-key-bridge-restoration-and-timeline/article_b231d5d1-9aa6-47f7-8974-0bb9662cd944.html",
                    source_date="2024-03-26; 2024-05-31; 2025-12", status="applied"))

# 2. I-95 northbound Express Toll Lanes extension, MD 43 (exit 67) to MD 152 (exit 74): opened to traffic in December 2024 (MDTA project page).
#    Absent for the 2024 annual-average year, present in 2026.  Selector: northbound links (x increases along the link; I-95 runs
#    south-west to north-east here) of the OSM way 'Express Toll Lanes' (motorway) whose midpoint lies north-east of the MD 43 exit,
#    up to the merge taper north of MD 152.  The southbound Express Toll Lanes end at MD 43 and are untouched.
#    Ramps that lead only into the removed section (the MD 43 access ramp to the extended lanes) are removed with it; the end of the surviving
#    northbound Express Toll Lanes is reconnected to the general-purpose lanes by a 25 m merge link at the point where the lanes ended before
#    the extension (node 6855978126 to the adjacent mainline node 2088408242, 21 m apart), so that the 2024 network has the pre-extension merge.
x43, y43 = exit_xy(95, 67); x152, y152 = exit_xy(95, 74); x24, y24 = exit_xy(95, 77)
def etl_north_of_md43():
    e = L[(L.name == "Express Toll Lanes") & (L.hwy.isin(["motorway", "motorway_link"])) & (L.xm > x43) & (L.x1 > L.x0)]
    ids = set(e.index)
    while True:   # ramps whose end node loses every outgoing car link become dead ends: remove them too (they only served the removed lanes)
        out_ok = L[L.modes.str.contains("car") & ~L.index.isin(ids)].groupby("f").size()
        dead = L[(L.hwy == "motorway_link") & ~L.index.isin(ids) & ~L.t.map(out_ok).fillna(0).astype(bool)]
        if len(dead) == 0: break
        ids |= set(dead.index)
    return sorted(ids, key=lambda i: (len(i), i))
ETL_MERGE = dict(id="etl_merge_2024", f="6855978126", t="2088408242", length=25.0, freespeed=29.0576, capacity=4000.0, permlanes=2.0, modes="car", hwy="motorway", name="Express Toll Lanes (merge into general-purpose lanes, 2024)")
CHANGES.append(dict(change_id="I95_ETL_NB_MD43_MD152", description="I-95 northbound Express Toll Lanes extension from MD 43 (exit 67) to MD 152 (exit 74), opened to traffic December 2024; not in the 2024 network (lanes and their access ramp removed, pre-extension merge into the general-purpose lanes at MD 43 restored by one added link), in the 2026 network",
                    action="remove", years="2024", select=etl_north_of_md43, add=[ETL_MERGE],
                    source_url="https://mdta.maryland.gov/I95ETLNB/home.html", source_date="accessed 2026-10-21 (page states: opened to traffic in December 2024)", status="applied"))

# 3. I-95 northbound Express Toll Lanes, MD 152 to north of MD 24: under construction, expected to open by the end of 2027 (same page).
#    Check: no 'Express Toll Lanes' link starts north-east of the MD 24 exit in the June 2026 extract.
def etl_north_of_md152():
    return list(L[(L.name == "Express Toll Lanes") & (L.x0 > x24)].index)
CHANGES.append(dict(change_id="I95_ETL_NB_MD152_MD24", description="I-95 northbound Express Toll Lanes, MD 152 to north of MD 24: under construction, opening expected by end of 2027; verified absent from both networks",
                    action="none", years="", select=etl_north_of_md152, source_url="https://mdta.maryland.gov/I95ETLNB/home.html", source_date="accessed 2026-10-21", status="checked, no change"))

# 4. I-695 part-time shoulder use, I-70 to MD 43 (MDOT SHA contract BA0065172): first section (I-70 to I-83) expected to open in 2027,
#    I-83 to MD 43 in 2028.  No shoulder lanes in either year.
CHANGES.append(dict(change_id="I695_PTSU_I70_MD43", description="I-695 part-time shoulder use between I-70 and MD 43 (MDOT SHA BA0065172): not open in 2024 or 2026 (first section expected 2027, second 2028); no change",
                    action="none", years="", select=lambda: [], source_url="https://foxbaltimore.com/spotlight-on-maryland/maryland-is-betting-184-million-on-i-695-drivers-have-questions; https://www.roads.maryland.gov/ohd2/BA0065172_Concrete%20General_TP.pdf",
                    source_date="2026-08-25", status="checked, no change"))

# 5. I-695 ramps to the I-95 northbound Express Toll Lanes (MDTA): construction anticipated to begin in 2027.  No change.
CHANGES.append(dict(change_id="I695_RAMPS_I95_ETL", description="New ramps from I-695 to the I-95 northbound Express Toll Lanes at the I-95/I-695 interchange (MDTA): construction to begin 2027; no change",
                    action="none", years="", select=lambda: [], source_url="https://mdta.maryland.gov/sites/default/files/Files/I95ETLNB/KH3046_695%20Ramp_rd09_proof_ada.pdf", source_date="Spring 2026", status="checked, no change"))

# 6. MDOT SHA project portal (layers 'Projects (Construction)' and 'Project Portal (Completed)', downloaded by fetch_mdot.py): every entry in
#    the six study-area counties whose work type mentions interchange, widening, lanes, closure, realignment or shoulder was read.  None adds
#    or removes a link between 2024 and 2026: the I-695 median-shoulder conversion (Stevenson Rd to Joppa Rd) is the peak-period shoulder of
#    item 4; the MD 122 ramp closures at I-695 (2024-09, 2025-08) were weekend closures; the MD 175 / MD 295 interchange reconstruction keeps
#    the existing ramps open and completes in fall 2027; the remaining entries are turn lanes, resurfacing and repairs.
CHANGES.append(dict(change_id="SHA_PROJECT_PORTAL_REVIEW", description="MDOT SHA project portal, six study-area counties: 53 completed and 9 active capacity-related entries reviewed; none changes a link between 2024 and 2026 (temporary closures, turn lanes, repairs; MD 175/MD 295 interchange completes fall 2027)",
                    action="none", years="", select=lambda: [], source_url="https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/MDOT_SHA_Project_Portal_(Completed)/FeatureServer/0; https://www.roads.maryland.gov/mdotsha/pages/pressreleasedetails.aspx?newsId=4801&PageId=818; https://www.roads.maryland.gov/mdotsha/pages/pressreleasedetails.aspx?newsId=5418&PageId=818; https://www.roads.maryland.gov/mdotsha/pages/pressreleasedetails.aspx?newsId=5596&PageId=818",
                    source_date=f"layers downloaded {TODAY}; releases 2023-09-27, 2025-08-04, 2026-04-06", status="checked, no change"))

# ------------------------------------------------------------------ resolve, check, write the change list
rows, link_rows = [], []
removed = {"2024": set(), "2026": set()}; added = {"2024": [], "2026": []}
for c in CHANGES:
    ids = c["select"]()
    missing = [i for i in ids if i not in links]
    if missing: raise SystemExit(f"{c['change_id']}: {len(missing)} link ids not in the network: {missing[:10]}")
    if c["action"] == "none" and ids: raise SystemExit(f"{c['change_id']}: expected no links, found {len(ids)}")
    for a in c.get("add", []):
        if a["id"] in links: raise SystemExit(f"{c['change_id']}: added link id {a['id']} already exists")
        if a["f"] not in nodes or a["t"] not in nodes: raise SystemExit(f"{c['change_id']}: added link {a['id']} refers to a missing node")
    km = L.loc[ids, "length"].sum() / 1000 if ids else 0.0
    yrs = [s for s in c["years"].split(";") if s]
    for y in yrs: removed[y].update(ids); added[y] += c.get("add", [])
    rows.append(dict(change_id=c["change_id"], description=c["description"], action=c["action"] + (" + add" if c.get("add") else ""), applies_to_year=c["years"].replace(";", " and ") or "none",
                     n_links=len(ids), length_km=round(km, 2), link_ids=";".join(ids), links_added=";".join(a["id"] for a in c.get("add", [])), source_url=c["source_url"], source_date=c["source_date"], status=c["status"]))
    for i in ids: link_rows.append(dict(change_id=c["change_id"], link=i, action="remove", highway=links[i]["hwy"], name=links[i]["name"], length_m=round(links[i]["length"], 1), lanes=links[i]["lanes"], capacity=links[i]["cap"], applies_to_year=c["years"].replace(";", " and ")))
    for a in c.get("add", []): link_rows.append(dict(change_id=c["change_id"], link=a["id"], action="add", highway=a["hwy"], name=a["name"], length_m=a["length"], lanes=a["permlanes"], capacity=a["capacity"], applies_to_year=c["years"].replace(";", " and ")))
    print(f"{c['change_id']}: {c['action']} {len(ids)} links, {km:.2f} km, add {len(c.get('add', []))}, years {c['years'] or '-'}")
pd.DataFrame(rows).to_csv(f"{HERE}/changes_2024_2026.csv", index=False)
pd.DataFrame(link_rows).to_csv(f"{HERE}/changes_2024_2026_links.csv", index=False)

# ------------------------------------------------------------------ write the two networks
def write(year, drop, add):
    out = f"{HERE}/network_{year}.xml.gz"; n = 0; skipping = False; h = hashlib.sha256()
    with gzip.open(SRC, "rt") as fi, gzip.open(out, "wt") as fo:
        for line in fi:
            if "<link " in line:
                lid = re.search(r'<link id="([^"]+)"', line).group(1)
                if lid in drop:
                    n += 1
                    if "</link>" not in line: skipping = True
                    continue
            if skipping:
                if "</link>" in line: skipping = False
                continue
            if "</links>" in line:
                for a in add:
                    line = (f'\t\t<link id="{a["id"]}" from="{a["f"]}" to="{a["t"]}" length="{a["length"]:.1f}" freespeed="{a["freespeed"]:.4f}" capacity="{a["capacity"]:.1f}" permlanes="{a["permlanes"]:.1f}" oneway="1" modes="{a["modes"]}">\n'
                            f'\t\t\t<attributes>\n\t\t\t\t<attribute name="osm:way:highway" class="java.lang.String">{a["hwy"]}</attribute>\n\t\t\t\t<attribute name="osm:way:name" class="java.lang.String">{a["name"]}</attribute>\n\t\t\t</attributes>\n\t\t</link>\n') + line
            if "<network" in line and "name=" not in line: line = line.replace("<network", f'<network name="Baltimore region {year}, built {TODAY} from network_v8_supply"', 1)
            fo.write(line); h.update(line.encode())
    h = h.hexdigest()[:16]
    print(f"network_{year}: removed {n} links, added {len(add)} -> {out} (sha256 of content {h})"); return n, h

log = []
for y in ["2024", "2026"]:
    n, h = write(y, removed[y], added[y]); log.append(dict(year=y, links=len(L) - n + len(added[y]), nodes=len(nodes), removed=n, added=len(added[y]), sha256_16=h))
with open(f"{HERE}/build_networks.log", "w") as f:
    f.write(f"built {TODAY} from {SRC}\nsource: {len(nodes):,} nodes, {len(L):,} links\n")
    for r in log: f.write(f"network_{r['year']}: {r['nodes']:,} nodes, {r['links']:,} links, {r['removed']} removed, {r['added']} added, sha256[:16] of the uncompressed file {r['sha256_16']}\n")
print(open(f"{HERE}/build_networks.log").read())
