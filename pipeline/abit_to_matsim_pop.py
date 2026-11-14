#!/usr/bin/env python3
"""ABIT weekly plans -> MATSim population of the Baltimore study area (stage 3 -> stage 4 bridge of the integrated loop).

Port of ABIT/validation/build_studyarea.py (the converter of the earlier chain) with the paths as arguments, so that it runs on any
chain year.  The method: (1) one representative weekday per person (abit_day.single_day_legs: MONDAY for every person since the
second pass of stage 3, 2026-10-22, abit_day.REP_DAY; a person without legs on Monday gets a home-only plan; the first pass took
the first complete Mon-Fri home-to-home chain); (2) MITO-style subarea cut: tours are intra / inflow / outflow / external-external by the BMR zone list, persons
with only external-external tours are dropped; (3) activities outside the BMR are anchored at a cordon gateway (count station on
the cordon, chosen along the person's path, capped at the crossing's resident-share budget); (4) homes are placed on OSM residential
buildings, other activities on OSM points of interest of the matching category inside their zone; (5) person attributes from the
SILO household and person files of the same year.

Differences to the earlier script, stated: SILO column names of the rebuilt chain (hhID); EDUCATION activities keep their own
type (the MATSim runner scores "education"; the old script folded it into "other" because its runner did not); the 18 % work-from-home
lever is OFF by default (ABIT now samples daily work attendance in the model, wfh.attendance.file) and the gateway budget is
scaled by --expansion (1/sample) instead of a fixed 10.

Usage: abit_to_matsim_pop.py --activities A.csv --legs L.csv --pp pp_Y.csv --hh hh_Y.csv --out population.xml.gz
                             [--expansion 10] [--wfh-pct 0] [--seed 20260707] [--residents-only]
--activities / --legs may also be the parquet files of the final ABIT runs (activities_full.parquet / legs_full.parquet, all columns
as text, same column names as the CSV).  hhIncome: the SILO household file has no income column in the rebuilt chain, so the household
income is the sum over ALL members of the household in the person file, as ABIT computes it (12 x sum of int(annual)/12, integer
arithmetic of MarylandDataReaderManager + MarylandTourNestedModeChoice).
--residents-only (2026-11-02, validation study): only persons whose home zone is in the BMR are kept (inflow persons = non-residents are
dropped, as are external-external persons); the cordon gateways are switched off (no snapping to count stations, no count-derived
budgets): activities of residents outside the BMR keep their ABIT coordinates.
--no-gateways (2026-11-02, the definition used for the validation runs): "residents only" means no synthetic or fitted traffic (no cordon
gateways, external-external fills or copied background), not fewer chain persons: every SILO/ABIT person with a tour touching the BMR is
kept (intra, inflow, outflow; external-external persons dropped as before), the gateways and the count-derived inflow cap are off, and
activities outside the BMR keep their ABIT coordinates (MATSim attaches them to the nearest network link, i.e. at the network edge).
Prints the cut statistics (tours by flow, persons kept, legs, attribute coverage, POI placement levels)."""
import argparse, csv, gzip, math, collections, sys, os, pickle, random
import numpy as np
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"
ABIT = f"{ROOT}/ABIT"; MAT = f"{ROOT}/Updated MATSim"
sys.path.insert(0, f"{ABIT}/validation"); from abit_day import single_day_legs, hhmmss   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--activities", required=True); ap.add_argument("--legs", required=True)
ap.add_argument("--pp", required=True); ap.add_argument("--hh", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--expansion", type=float, default=10.0, help="1/sample fraction of the ABIT run (gateway budgets are in persons)")
ap.add_argument("--wfh-pct", type=int, default=0, help="share of employed persons whose work chains are removed (0 = attendance handled by ABIT)")
ap.add_argument("--seed", type=int, default=20260707)
ap.add_argument("--residents-only", action="store_true", help="BMR residents only; no cordon gateways, no inflow persons (validation study 2026-11-02; superseded by --no-gateways)")
ap.add_argument("--no-gateways", action="store_true", help="all chain persons touching the BMR (intra, inflow, outflow); cordon gateways and the count-derived inflow cap off (validation study 2026-11-02)")
ap.add_argument("--poi-decay", action="store_true", help="discretionary activities (shopping, recreation, accompany, other) placed on a POI of their zone with the "
                "estimated piecewise distance utility of ABIT's destination model from the previous placed activity, instead of uniformly (2026-11-04)")
ap.add_argument("--zone-attributes", default=f"{ABIT}/input/maryland/zone_attributes.csv")
ap.add_argument("--zone-system", default=f"{ABIT}/input/mito_los/Zonal/zoneSystem.csv")
ap.add_argument("--bmr", default=f"{ABIT}/input/maryland/BMR.txt")
ap.add_argument("--gateways", default=f"{MAT}/network_validation_2023/calibration/cordon_stations_expanded_anchored.csv")
ap.add_argument("--poi", default=f"{ABIT}/input/maryland/poi_index_26985.pkl")
ap.add_argument("--home-buildings", default=f"{ABIT}/input/maryland/home_osm_buildings_26985.pkl")
ap.add_argument("--home-streets", default=f"{ABIT}/input/maryland/home_resid_index_26985.pkl")
ap.add_argument("--zone-shp", default=f"{ABIT}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp")
a = ap.parse_args()
NOGW = a.residents_only or a.no_gateways   # gateways and the inflow cap off
for f in [a.activities, a.legs, a.pp, a.hh, a.zone_attributes, a.zone_system, a.bmr, a.gateways, a.poi, a.home_buildings, a.home_streets, a.zone_shp]:
    if not os.path.exists(f): raise SystemExit(f"missing input: {f}")

BMR = set(int(z) for z in open(a.bmr) if z.strip().isdigit())
zcent = {int(r["id"]): (float(r["x"]), float(r["y"])) for r in csv.DictReader(open(a.zone_attributes))}
zcounty = {int(r["Zone"]): r["COUNTYFIPS"] for r in csv.DictReader(open(a.zone_system))}
def rows(path):
    """dict rows of a CSV or of a parquet file (the final ABIT runs keep legs/activities as parquet with text columns)."""
    if str(path).endswith(".parquet"):
        import pyarrow.parquet as pq
        for b in pq.ParquetFile(path).iter_batches(batch_size=200000):
            yield from b.to_pylist()
    else: yield from csv.DictReader(open(path))
def zin(z):
    try: return int(z) in BMR
    except (TypeError, ValueError): return False

# ---- pass 1: tour flows per person from the activities (file grouped by person) ----
def person_blocks(path):
    cur = None; buf = []
    for r in rows(path):
        if r["person_id"] != cur:
            if buf: yield cur, buf
            cur = r["person_id"]; buf = []
        buf.append(r)
    if buf: yield cur, buf
person_flow = {}; person_home = {}; tour_flows = collections.Counter(); kept = set(); workzone = {}; n_nonres = 0
for pid, acts in person_blocks(a.activities):
    home = next((x["zone"] for x in acts if x["purpose"] == "HOME"), acts[0]["zone"]); hin = zin(home); flows = []
    for x in acts:
        if x["activity_type"] in ("MANDATORY", "PRIMARY") and x["purpose"] not in ("HOME", "SUBTOUR"):
            din = zin(x["zone"]); flows.append("intra" if hin and din else "outflow" if hin else "inflow" if din else "ee")
        if x["purpose"] == "WORK" and x["activity_type"] == "MANDATORY" and pid not in workzone: workzone[pid] = x["zone"]   # not a WORK stop (second pass, 2026-10-22)
    keep = [f for f in flows if f != "ee"]
    if not keep: continue
    if a.residents_only and not hin: n_nonres += 1; continue   # residents only: home outside the BMR = not a resident
    kept.add(pid); person_home[pid] = home
    for f in keep: tour_flows[f] += 1
    person_flow[pid] = "inflow" if not hin else "intra" if all(f == "intra" for f in keep) else "outflow"
tot = sum(tour_flows.values()) or 1
print("=== BMR subarea cut (tour level) ===")
for f in ["intra", "inflow", "outflow"]: print(f"  {f:8} {tour_flows[f]:>9,}  {100 * tour_flows[f] / tot:5.1f}%")
print(f"  persons touching the BMR: {len(kept):,} (external-external persons dropped)")
if a.no_gateways and not a.residents_only: print("  no gateways: all chain persons touching the BMR kept (inflow included); cordon gateways and inflow cap off")
if a.residents_only: print(f"  residents only: {n_nonres:,} non-resident persons (home outside the BMR, travelling into it) dropped; cordon gateways off")

# ---- SILO attributes of the kept persons ----
pp = {}; hhinc_m = collections.Counter()   # household monthly income = sum over all members of int(annual)/12 (ABIT)
for r in csv.DictReader(open(a.pp)):
    if r["id"] in kept: pp[r["id"]] = r
    try: hhinc_m[r.get("hhID", r.get("hhid"))] += int(float(r["income"])) // 12
    except (KeyError, TypeError, ValueError): pass
hhkey = "hhID" if pp and "hhID" in next(iter(pp.values())) else "hhid"
hhids = set(v[hhkey] for v in pp.values()); hh = {}
for r in csv.DictReader(open(a.hh)):
    if r["id"] in hhids: hh[r["id"]] = r

# ---- legs of the kept persons ----
MODEMAP = {"CAR_DRIVER": "car", "CAR_PASSENGER": "ride", "BUS": "pt", "TRAIN": "pt", "TRAM_METRO": "pt", "WALK": "walk", "BIKE": "bike"}
ACTMAP = {"HOME": "home", "WORK": "work", "EDUCATION": "education", "SHOPPING": "shopping", "OTHER": "other", "RECREATION": "other", "ACCOMPANY": "other", "SUBTOUR": "other"}
legs_by = collections.defaultdict(list)
for r in rows(a.legs):
    if r["person_id"] in kept:
        try: int(r["start_time_min"])
        except ValueError: continue
        legs_by[r["person_id"]].append(r)
for pid in legs_by: legs_by[pid].sort(key=lambda r: int(r["start_time_min"]))

# ---- cordon gateways (count stations on the BMR cordon): capacity weight and resident-share budget in persons ----
FACMULT = {"Interstate/Freeway": 1.0, "Principal Arterial": 0.35, "Minor Arterial": 0.20, "Collector/Local": 0.10}
RESSHARE = {"Interstate/Freeway": 0.55, "Principal Arterial": 0.75, "Minor Arterial": 0.85, "Collector/Local": 0.90}
gwx, gwy, gwcap, gwbud, gwid = [], [], [], [], []
for r in csv.DictReader(open(a.gateways)):
    try:
        fac = r.get("facility", ""); gwx.append(float(r["x"])); gwy.append(float(r["y"])); gwcap.append(float(r["obs_AADT"]) * FACMULT.get(fac, 0.20))
        gwbud.append(RESSHARE.get(fac, 0.85) * float(r["obs_AADT"]) / 2.0 / a.expansion); gwid.append(r.get("LOCATION_ID", ""))
    except (KeyError, ValueError): pass
gwx, gwy, gwcap, gwbud = map(np.array, (gwx, gwy, gwcap, gwbud)); gw_used = np.zeros(len(gwx)); gw_assign = {}
D0, DPATH = 15000.0, 8000.0
p_anchor = {}
for pid in kept:
    if person_flow.get(pid) == "intra": continue
    wz = workzone.get(pid); anc = zcent.get(int(wz)) if wz and str(wz).lstrip("-").isdigit() and zin(int(wz)) else None
    if anc is None:
        for lg in legs_by.get(pid, []):
            ez = lg.get("end_zone")
            if ez and str(ez).lstrip("-").isdigit() and zin(int(ez)): anc = zcent.get(int(ez)); break
    if anc: p_anchor[pid] = anc
def snap_gw(x, y, pid):
    """One gateway per person, chosen on the path external origin -> gateway -> internal anchor, weighted by the crossing's
    external-entry capacity, hard-capped at its resident-share budget; inflow persons with no open crossing are dropped."""
    if pid in gw_assign:
        i = gw_assign[pid]
        return None if i is None else (float(gwx[i]), float(gwy[i]))
    ax, ay = p_anchor.get(pid, (None, None)); d = np.hypot(gwx - x, gwy - y)
    if ax is not None: path = d + np.hypot(gwx - ax, gwy - ay); w = gwcap * np.exp(-(path - path.min()) / DPATH)
    else: w = gwcap * np.exp(-d / D0)
    wh = np.where(gw_used < gwbud, w, 0.0)
    if wh.sum() > 0:
        ps = int(pid) if str(pid).isdigit() else sum(ord(c) for c in str(pid))
        rng = np.random.default_rng((ps * 2654435761 + int(abs(x)) * 100003 + int(abs(y))) % (2 ** 32)); i = int(rng.choice(len(wh), p=wh / wh.sum()))
    elif person_flow.get(pid) == "inflow": gw_assign[pid] = None; return None
    else: i = int(np.argmin(gw_used / np.maximum(gwbud, 1)))
    gw_assign[pid] = i; gw_used[i] += 1; return float(gwx[i]), float(gwy[i])
def coord(x, y, zone, pid):
    z = int(zone) if str(zone).lstrip("-").isdigit() else -1
    if z != -1 and not zin(z) and not NOGW:
        cx, cy = zcent.get(z, (None, None))
        if cx is None:
            try: cx, cy = float(x), float(y)
            except (TypeError, ValueError): cx, cy = 0.0, 0.0
        g = snap_gw(cx, cy, pid); return g if g is not None else (cx, cy)
    try:
        fx, fy = float(x), float(y)
        if math.isnan(fx) or math.isnan(fy): raise ValueError
        return fx, fy
    except (TypeError, ValueError): return zcent.get(z, (0.0, 0.0))
def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")

# ---- microlocations: POIs for non-home activities, OSM residential buildings for homes ----
from shapely.geometry import Point; from shapely.prepared import prep; import geopandas as gpd; from pyproj import Transformer
zg = gpd.read_file(a.zone_shp); ZPOLY, ZPREP, ZBB = {}, {}, {}
for _, row in zg.iterrows():
    g = row.geometry
    if g is None or g.is_empty: continue
    zid = int(row["Zone"]); ZPOLY[zid] = g; ZPREP[zid] = prep(g); ZBB[zid] = g.bounds
T = Transformer.from_crs(26918, 26985, always_xy=True); random.seed(a.seed)
POI = pickle.load(open(a.poi, "rb")); POI_ANY = {z: np.vstack([x for x in d.values() if len(x)]) for z, d in POI.items() if any(len(x) for x in d.values())}
PURP_CATS = {"WORK": ["work"], "SHOPPING": ["shopping"], "OTHER": ["other"], "RECREATION": ["recreation", "other"], "ACCOMPANY": ["education", "other"], "SUBTOUR": ["other"], "EDUCATION": ["education", "other"], "HOME": []}
poi_level = collections.Counter(); n_decay = collections.Counter()
def rand_in_zone(zone):
    g = ZPOLY.get(zone)
    if g is None: return None
    pg = ZPREP[zone]; x0, y0, x1, y1 = ZBB[zone]
    for _ in range(80):
        px, py = random.uniform(x0, x1), random.uniform(y0, y1)
        if pg.contains(Point(px, py)): return T.transform(px, py)
    return None
# Distance slopes (per km, knots 1, 2, 5, 10, 20, 50 km) of ABIT's primary-destination models (Tables est_dc_*); network km = 1.3 x straight line.
# Conditional on the zone ABIT chose, a POI k is drawn with probability proportional to exp(f(1.3 d_k)), d_k its distance from the previous
# placed activity: the destination model's own distance utility applied to the POIs (equal size each) inside the chosen zone.  Nothing fitted.
DC_SLOPES = {"OTHER": [-2.0675, -1.0635, -0.3325, -0.1866, -0.0987, -0.0519, 0.0058], "SHOPPING": [-5.0864, -0.7955, -0.5628, -0.1962, -0.1546, -0.0619, 0.0147],
             "RECREATION": [-3.2715, -0.907, -0.4408, -0.1761, -0.1215, -0.0777, 0.0015], "ACCOMPANY": [-0.0462, -0.49, -0.2724, -0.1543, -0.0609, -0.0382, 0.0319]}
DC_KNOTS = np.array([0, 1, 2, 5, 10, 20, 50, 1e9]); NET_FACTOR = 1.3
def dist_utility(km, slopes):
    km = np.asarray(km, float); u = np.zeros_like(km)
    for k, b in enumerate(slopes): u += b * np.clip(km - DC_KNOTS[k], 0, DC_KNOTS[k + 1] - DC_KNOTS[k])
    return u
def poi_coord(x, y, zone, purpose, anchor=None, prev=None):
    pu = (purpose or "").upper()
    if pu == "HOME": return x, y
    try: zid = int(zone)
    except (TypeError, ValueError): poi_level[(pu, "bad_zone")] += 1; return x, y
    if not zin(zid): poi_level[(pu, "gateway")] += 1; return x, y
    zd = POI.get(zid, {})
    for cat in PURP_CATS.get(pu, ["other"]):
        arr = zd.get(cat)
        if arr is not None and len(arr):
            if pu == "SUBTOUR" and anchor is not None:
                d = (arr[:, 0] - anchor[0]) ** 2 + (arr[:, 1] - anchor[1]) ** 2; k = min(8, len(arr)); j = int(np.argpartition(d, k - 1)[:k][random.randrange(k)])
            elif a.poi_decay and prev is not None and pu in DC_SLOPES and len(arr) > 1:
                km = NET_FACTOR * np.hypot(arr[:, 0] - prev[0], arr[:, 1] - prev[1]) / 1e3
                u = dist_utility(km, DC_SLOPES[pu]); w = np.exp(u - u.max()); j = int(np.searchsorted(np.cumsum(w), random.random() * w.sum()))
                j = min(j, len(arr) - 1); n_decay[pu] += 1
            else: j = random.randrange(len(arr))
            poi_level[(pu, cat)] += 1; return float(arr[j, 0]), float(arr[j, 1])
    anyp = POI_ANY.get(zid)
    if anyp is not None and len(anyp): j = random.randrange(len(anyp)); poi_level[(pu, "any_poi")] += 1; return float(anyp[j, 0]), float(anyp[j, 1])
    rp = rand_in_zone(zid)
    if rp is not None: poi_level[(pu, "random_in_zone")] += 1; return rp
    poi_level[(pu, "centroid")] += 1; return x, y
HB = pickle.load(open(a.home_buildings, "rb")); HS = pickle.load(open(a.home_streets, "rb"))
def home_xy(hz, hhid):
    try: z = int(hz)
    except (TypeError, ValueError): return None
    if not zin(z): return None
    arr = HB.get(z)
    if arr is None or len(arr) == 0: arr = HS.get(z)
    if arr is None or len(arr) == 0: return None
    try: seed = int(hhid) & 0x7fffffff
    except (TypeError, ValueError): seed = z
    j = int(np.random.default_rng((seed * 2654435761) % (2 ** 32)).integers(len(arr))); return float(arr[j][0]), float(arr[j][1])

# ---- inflow persons whose every reachable crossing is at its budget are dropped (resident-only scope of the cordon counts) ----
dropped_inflow = set()
for pid in sorted(kept, key=lambda x: int(x)):
    if person_flow.get(pid) == "inflow" and not NOGW:
        hz = person_home.get(pid, ""); z = int(hz) if str(hz).lstrip("-").isdigit() else -1; cx, cy = zcent.get(z, (0.0, 0.0))
        if snap_gw(cx, cy, pid) is None: dropped_inflow.add(pid)
print(f"[inflow cap] {len(dropped_inflow):,} inflow persons dropped (their boundary sector is over its cordon budget)")

GENDER = {"1": "MALE", "2": "FEMALE"}; OCC = {"0": "TODDLER", "1": "EMPLOYED", "2": "UNEMPLOYED", "3": "STUDENT", "4": "RETIREE"}
FIELDS = ["age", "gender", "occupation", "driversLicense", "hhSize", "autos", "hhIncome", "personIncome", "race", "homeZone", "homeCounty", "workZone", "flow"]
cov = collections.Counter(); ntot = 0; cross = 0; nlegs = 0; wfh_persons = 0; legs_by_mode = collections.Counter()
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
out = gzip.open(a.out, "wt", encoding="utf-8")
out.write('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd">\n<population>\n')
for pid in sorted(kept, key=lambda x: int(x)):
    if pid in dropped_inflow: continue
    p = pp.get(pid)
    if p is None: continue
    h = hh.get(p[hhkey], {}); hz = person_home.get(pid, ""); hxy = home_xy(hz, p.get(hhkey, ""))
    attrs = {"age": p.get("age"), "gender": GENDER.get(p.get("gender"), ""), "occupation": OCC.get(p.get("occupation"), ""), "driversLicense": p.get("driversLicense"),
             "hhSize": h.get("hhSize"), "autos": h.get("autos"), "hhIncome": h.get("income") or 12 * hhinc_m.get(p[hhkey], 0), "personIncome": p.get("income"), "race": (p.get("race") or "").strip('"'),
             "homeZone": hz, "homeCounty": zcounty.get(int(hz)) if str(hz).isdigit() else "", "workZone": workzone.get(pid, ""), "flow": person_flow.get(pid, "")}
    ntot += 1
    for f in FIELDS:
        if attrs.get(f) not in (None, "", "None"): cov[f] += 1
    out.write(f'  <person id="{esc(pid)}">\n    <attributes>\n')
    for f in FIELDS:
        v = attrs.get(f)
        if v in (None, "", "None"): continue
        cls = "java.lang.Integer" if f in ("age", "hhSize", "autos", "hhIncome", "personIncome", "homeZone", "workZone") and str(v).lstrip("-").isdigit() else "java.lang.String"
        out.write(f'      <attribute name="{f}" class="{cls}">{esc(v)}</attribute>\n')
    out.write('    </attributes>\n    <plan selected="yes">\n')
    best, ls = single_day_legs(legs_by.get(pid, []))
    if ls and a.wfh_pct > 0 and p.get("occupation") == "1" and (int(pid) * 2654435761) % 100 < a.wfh_pct:
        chains, cur = [], []
        for lg in ls:
            cur.append(lg)
            if str(lg["next_purpose"]).upper() == "HOME": chains.append(cur); cur = []
        if cur: chains.append(cur)
        nls = [l for c in chains if not any(str(l["next_purpose"]).upper() == "WORK" or str(l["previous_purpose"]).upper() == "WORK" for l in c) for l in c]
        if len(nls) < len(ls): wfh_persons += 1; ls = nls
    if not ls:
        x, y = hxy if hxy else coord(0, 0, hz, pid); out.write(f'      <activity type="home" x="{x:.2f}" y="{y:.2f}"/>\n')
    else:
        f0 = ls[0]; x, y = coord(f0["start_x"], f0["start_y"], f0["start_zone"], pid); clock = max(0, f0["_tod_start"]); rp0 = f0["previous_purpose"]; at0 = ACTMAP.get(rp0, "other")
        if str(rp0).upper() == "HOME" and hxy: x, y = hxy
        else: x, y = poi_coord(x, y, f0["start_zone"], rp0, anchor=(x, y))
        out.write(f'      <activity type="{at0}" x="{x:.2f}" y="{y:.2f}" end_time="{hhmmss(clock)}"/>\n')
        for i, leg in enumerate(ls):
            mode = MODEMAP.get(leg["mode"], "walk"); legs_by_mode[mode] += 1; nlegs += 1
            out.write(f'      <leg mode="{mode}"/>\n')
            nx, ny = coord(leg["end_x"], leg["end_y"], leg["end_zone"], pid); rp = leg["next_purpose"]; at = ACTMAP.get(rp, "other")
            if str(rp).upper() == "HOME" and hxy: nx, ny = hxy
            else: nx, ny = poi_coord(nx, ny, leg["end_zone"], rp, anchor=(nx, ny), prev=(x, y))
            if i < len(ls) - 1:
                dep = ls[i + 1]["_tod_start"]
                if dep <= clock: cross += 1
                dep = max(dep, clock + 1); clock = dep
                out.write(f'      <activity type="{at}" x="{nx:.2f}" y="{ny:.2f}" end_time="{hhmmss(dep)}"/>\n'); x, y = nx, ny
            else: out.write(f'      <activity type="{at}" x="{nx:.2f}" y="{ny:.2f}"/>\n')
    out.write('    </plan>\n  </person>\n')
out.write('</population>\n'); out.close()
print(f"\nMATSim population: {ntot:,} persons, {nlegs:,} legs (one weekday each) -> {a.out}")
print(f"legs by mode: {dict(sorted(legs_by_mode.items()))}; same-minute departures made monotonic: {cross}; WFH chains removed: {wfh_persons:,}")
print("person flow:", dict(collections.Counter(person_flow[p] for p in kept if p not in dropped_inflow and p in pp)))
over = [(gwid[i], gw_used[i], gwbud[i]) for i in range(len(gwid)) if gw_used[i] > gwbud[i] * 1.05]
print(f"[gateway] persons assigned {int(gw_used.sum()):,}; budget {int(gwbud.sum()):,}; over-budget crossings {len(over)}")
print("attribute coverage: " + ", ".join(f"{f} {100 * cov[f] / max(1, ntot):.0f}%" for f in FIELDS))
onpoi = sum(v for k, v in poi_level.items() if k[1] in ("work", "shopping", "other", "recreation", "education", "any_poi")); nonhome = sum(poi_level.values())
print(f"POI placement: {onpoi:,} of {nonhome:,} non-home activities on a real POI ({100 * onpoi / max(1, nonhome):.1f}%); levels: {dict(sorted(poi_level.items()))}")
print("distance-aware POI placement (--poi-decay):", dict(n_decay))
