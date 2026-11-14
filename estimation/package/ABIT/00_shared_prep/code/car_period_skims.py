#!/usr/bin/env python3
"""Car travel times by period for the tour mode choice.

    python3 car_period_skims.py [events.xml.gz network.xml.gz]

Periods (start of the main activity for the outbound half-tour, its end for the return half-tour):
    AM 06:00-09:00, MD 09:00-15:00, PM 15:00-19:00, NT 19:00-06:00.
One pass over the events of the resident-only MATSim assignment of the chain (synthetic residents' trips, 2023 network, Key
Bridge open, 20 iterations): per car link and period the mean realised time of the vehicles entering the link in the period (links
without an entry keep the free-flow time; transit vehicles excluded; the pending entry is dropped at 'vehicle leaves traffic'), as
pipeline/matsim_to_skim.py does for the AM peak.  Dijkstra between the zone nodes on each period's link times.

The period skim keeps the level of the base car skim (3_abit/skims/traveltime_auto, the AM-peak skim every other ABIT model
uses) and takes only the profile over the day from MATSim:
    t_p(i,j) = t_base(i,j) * clip(T_p(i,j) / T_AM(i,j), 0.5, 1.5)        both zones on the network (<= 4 km from a node)
    t_p(i,j) = t_base(i,j)                                                otherwise
so AM = base exactly.  Output: work/skims/car_time_<P>.csv.gz (FROM,TO,VALUE minutes) and work/skims/car_period_stats.json."""
# COPY of Validation_2026/3_abit/mode_choice/car_period_skims.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "00_shared_data"))          # provided inputs
RAW = _os_pkg.environ.get("ABIT_RAW", _os_pkg.path.join(SHARED, "raw"))                                                              # your downloads
REBUILT = _os_pkg.environ.get("ABIT_REBUILT", _os_pkg.path.join(SHARED, "rebuilt"))                  # outputs of this chain
MDATA = REBUILT
import gzip, json, os, re, sys
import numpy as np, pandas as pd, geopandas as gpd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

ROOT = SHARED; V = SHARED  # PATH
RUN = f"{RAW}/matsim_resident_run_2023"  # PATH: output_events.xml.gz, output_network.xml.gz of the MATSim run
EV = sys.argv[1] if len(sys.argv) > 1 else f"{RUN}/output_events.xml.gz"
NET = sys.argv[2] if len(sys.argv) > 2 else f"{RUN}/output_network.xml.gz"
OUT = f"{REBUILT}/skims/mode_choice_periods"; os.makedirs(OUT, exist_ok=True)  # PATH
BASE = f"{SHARED}/skims/abit_base_2016/traveltime_auto.csv.gz"  # PATH
PER = {"AM": [(6, 9)], "MD": [(9, 15)], "PM": [(15, 19)], "NT": [(19, 30), (0, 6)]}   # NT wraps (MATSim times run past 24 h)
PN = list(PER)


def period_of(t):
    h = t / 3600.0
    for k, (p, wins) in enumerate(PER.items()):
        for a, b in wins:
            if a <= h < b: return k
    return 3


nodes = {}; L = []
with gzip.open(NET, "rt") as f:
    for line in f:
        if "<node " in line:
            m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', line); nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
        elif "<link " in line and 'modes="' in line and "car" in line.split('modes="')[1].split('"')[0]:
            m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" freespeed="([^"]+)"', line)
            L.append((m.group(1), m.group(2), m.group(3), float(m.group(4)), float(m.group(5))))
links = pd.DataFrame(L, columns=["id", "f", "t", "length", "fs"]); links["tt_ff"] = links.length / links.fs; lid = {l: i for i, l in enumerate(links.id)}
print(f"network: {len(nodes):,} nodes, {len(links):,} car links", flush=True)
S = np.zeros((4, len(links))); C = np.zeros((4, len(links))); enter = {}; transit = set()
rx = re.compile(r'time="([^"]+)"[^>]*type="(entered link|left link)"[^>]*link="([^"]+)"[^>]*vehicle="([^"]+)"')
n = 0
with gzip.open(EV, "rt") as f:
    for line in f:
        if "TransitDriverStarts" in line: transit.add(re.search(r'vehicleId="([^"]+)"', line).group(1)); continue
        if "vehicle leaves traffic" in line:
            m = re.search(r'link="([^"]+)"[^>]*vehicle="([^"]+)"', line); enter.pop((m.group(2), m.group(1)), None); continue
        if "entered link" not in line and "left link" not in line: continue
        m = rx.search(line)
        if not m: continue
        t, typ, link, veh = float(m.group(1)), m.group(2), m.group(3), m.group(4)
        if veh in transit: continue
        if typ == "entered link": enter[(veh, link)] = t
        else:
            t0 = enter.pop((veh, link), None)
            if t0 is not None and link in lid: i = lid[link]; k = period_of(t0); S[k, i] += t - t0; C[k, i] += 1
        n += 1
        if n % 20_000_000 == 0: print(f"  {n:,} link events", flush=True)
Z = gpd.read_file(f"{ROOT}/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(26985); Z["zone"] = Z.SMZRMZ.astype(int)
Z = Z.sort_values("zone").reset_index(drop=True); c = Z.geometry.representative_point(); zones = Z.zone.values
nid = list(nodes); xy = np.array([nodes[k] for k in nid]); d, j = cKDTree(xy).query(np.c_[c.x.values, c.y.values]); off = d > 4000
nidx = {k: i for i, k in enumerate(nid)}; fi = links.f.map(nidx).values; ti = links.t.map(nidx).values; src = np.unique(j)
pr = pd.read_csv(BASE); zi = {z: i for i, z in enumerate(zones)}; B = np.full((len(zones), len(zones)), np.nan)
B[pr.FROM.map(zi).values, pr.TO.map(zi).values] = pr.VALUE.values
Ms = []; stats = {"events": EV, "network": NET, "off_network_zones": int(off.sum()), "periods": {}}
for k, p in enumerate(PN):
    tt = np.maximum(np.where(C[k] > 0, S[k] / np.maximum(C[k], 1), links.tt_ff.values), links.tt_ff.values)
    G = csr_matrix((tt, (fi, ti)), shape=(len(nid), len(nid))); D = dijkstra(G, directed=True, indices=src); Dm = {s: q for q, s in enumerate(src)}
    M = D[[Dm[x] for x in j]][:, j] / 60.0; Ms.append(M)
    stats["periods"][p] = {"links_observed": float((C[k] > 0).mean()), "mean_realised_over_ff_observed": float(np.mean((tt / links.tt_ff.values)[C[k] > 0]))}
    print(f"{p}: links observed {(C[k] > 0).mean():.1%}", flush=True)
ok = ~(off[:, None] | off[None, :]) & np.isfinite(Ms[0]) & (Ms[0] > 0); np.fill_diagonal(ok, False)
F, T = np.meshgrid(zones, zones, indexing="ij")
for k, p in enumerate(PN):
    r = np.where(ok & np.isfinite(Ms[k]), Ms[k] / np.where(ok, Ms[0], 1.0), 1.0); r = np.clip(r, 0.5, 1.5)
    X = B * r; X[np.isnan(X)] = 999.0
    stats["periods"][p].update({"ratio_to_AM_mean": float(r[ok].mean()), "ratio_to_AM_p10": float(np.percentile(r[ok], 10)), "ratio_to_AM_p90": float(np.percentile(r[ok], 90)),
                                "pairs_with_matsim_profile": float(ok.mean())})
    with gzip.open(f"{OUT}/car_time_{p}.csv.gz", "wt") as fo:
        fo.write("FROM,TO,VALUE\n"); np.savetxt(fo, np.c_[F.ravel(), T.ravel(), X.ravel()], fmt="%d,%d,%.3f")
    print(f"{p}: ratio to AM mean {r[ok].mean():.3f} (p10 {np.percentile(r[ok], 10):.3f}, p90 {np.percentile(r[ok], 90):.3f})", flush=True)
json.dump(stats, open(f"{OUT}/car_period_stats.json", "w"), indent=1)
print("written", OUT)
