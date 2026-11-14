#!/usr/bin/env python3
"""Feedback bridge of the integrated loop: AM-peak congested zone-to-zone car travel times from a MATSim run.
  1. car network -> nodes and directed car links (length, free speed)
  2. output events -> per-link mean realised travel time of vehicles ENTERING the link between PEAK_FROM and PEAK_TO (default
     07:00-09:00); links not used in that window keep their free-flow time
  3. zone centroids (zone shapefile, 1,588 MSTM zones) -> nearest network node
  4. Dijkstra on the congested graph between all centroid nodes
  5. output: <out_prefix>.csv.gz (FROM,TO,VALUE minutes; what SILO reads) and <out_prefix>.omx (matrix mat1, lookup
     origins/destinations; what the activity model reads). Intra-zonal time = half the time to the nearest other centroid, floor 1 min.
Usage: python pipeline/skims_from_matsim.py <network.xml.gz> <output_events.xml.gz> <out_prefix> [peak_from_h peak_to_h [prior.csv.gz]]
  prior (FROM,TO,VALUE, e.g. the 2016 base skim): zone pairs with an endpoint more than 4 km from the network (the MSTM zone system
  extends beyond the modelled network) or without a path keep the prior value; without a prior they are set to 999 min.
Checks printed: share of links with observations, mean free-flow vs congested time of the skim, number of off-network zones, pairs from the prior."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys, gzip, re, os, numpy as np, pandas as pd, geopandas as gpd
from scipy.sparse import csr_matrix; from scipy.sparse.csgraph import dijkstra; from scipy.spatial import cKDTree
ROOT = f"{PROJECT_ROOT}"
net_path, ev_path, out = sys.argv[1], sys.argv[2], sys.argv[3]; PEAK_FROM = float(sys.argv[4]) * 3600 if len(sys.argv) > 4 else 7 * 3600; PEAK_TO = float(sys.argv[5]) * 3600 if len(sys.argv) > 5 else 9 * 3600
PRIOR = sys.argv[6] if len(sys.argv) > 6 else None
# ---- network
nodes = {}; L = []
with gzip.open(net_path, "rt") as f:
    for line in f:
        if "<node " in line:
            m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', line); nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
        elif "<link " in line and 'modes="' in line and "car" in line.split('modes="')[1].split('"')[0]:
            m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)" length="([^"]+)" freespeed="([^"]+)"', line); L.append((m.group(1), m.group(2), m.group(3), float(m.group(4)), float(m.group(5))))
links = pd.DataFrame(L, columns=["id", "f", "t", "length", "fs"]); links["tt_ff"] = links.length / links.fs; lid = {l: i for i, l in enumerate(links.id)}
print(f"network: {len(nodes):,} nodes, {len(links):,} car links")
# ---- realised link times in the peak window
enter = {}; ssum = np.zeros(len(links)); scnt = np.zeros(len(links)); rx = re.compile(r'time="([^"]+)"[^>]*type="(entered link|left link)"[^>]*link="([^"]+)"[^>]*vehicle="([^"]+)"')
transit_veh = set()   # transit vehicles (TransitDriverStarts) are excluded: their stop dwell times are not car travel times (found 2026-10-22, chain test)
with gzip.open(ev_path, "rt") as f:
    for line in f:
        if "TransitDriverStarts" in line: transit_veh.add(re.search(r'vehicleId="([^"]+)"', line).group(1)); continue
        if "vehicle leaves traffic" in line:   # trip end: the pending 'entered link' must not be closed by the next trip's 'left link' hours later (found 2026-10-22)
            m = re.search(r'link="([^"]+)"[^>]*vehicle="([^"]+)"', line); enter.pop((m.group(2), m.group(1)), None); continue
        if "entered link" not in line and "left link" not in line: continue
        m = rx.search(line)
        if not m: continue
        t, typ, link, veh = float(m.group(1)), m.group(2), m.group(3), m.group(4)
        if veh in transit_veh: continue
        if typ == "entered link":
            if PEAK_FROM <= t < PEAK_TO: enter[(veh, link)] = t
        else:
            t0 = enter.pop((veh, link), None)
            if t0 is not None and link in lid: i = lid[link]; ssum[i] += t - t0; scnt[i] += 1
tt = np.where(scnt > 0, ssum / np.maximum(scnt, 1), links.tt_ff.values); tt = np.maximum(tt, links.tt_ff.values)
print(f"links observed in {PEAK_FROM / 3600:.0f}-{PEAK_TO / 3600:.0f} h: {(scnt > 0).mean():.1%}; mean realised/free-flow on observed links {np.mean((tt / links.tt_ff.values)[scnt > 0]):.2f}")
# ---- zones -> nodes
Z = gpd.read_file(f"{ABIT_HOME}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp").to_crs(26985); Z["zone"] = Z.SMZRMZ.astype(int); c = Z.geometry.representative_point()
nid = list(nodes.keys()); xy = np.array([nodes[n] for n in nid]); tree = cKDTree(xy); d, j = tree.query(np.c_[c.x.values, c.y.values]); off = d > 4000
print(f"zones {len(Z)}, off-network (> 4 km from a node) {off.sum()}")
# ---- Dijkstra
nidx = {n: i for i, n in enumerate(nid)}; G = csr_matrix((tt, (links.f.map(nidx).values, links.t.map(nidx).values)), shape=(len(nid), len(nid)))
src = np.unique(j); D = dijkstra(G, directed=True, indices=src); Dmap = {s: k for k, s in enumerate(src)}
zones = Z.zone.values; M = np.array([[D[Dmap[j[a]], j[b]] for b in range(len(zones))] for a in range(len(zones))]) / 60.0
bad = ~np.isfinite(M) | off[:, None] | off[None, :]   # no path, or an endpoint beyond the network
for a in range(len(zones)):
    if off[a]: continue
    row = np.where(bad[a], np.inf, M[a]); row[a] = np.inf; M[a, a] = max(1.0, 0.5 * row.min()) if np.isfinite(row.min()) else 1.0; bad[a, a] = False
if PRIOR:
    pr = pd.read_csv(PRIOR); pidx = {z: i for i, z in enumerate(zones)}; Pm = np.full(M.shape, 999.0)
    sel = pr.FROM.isin(pidx) & pr.TO.isin(pidx); Pm[pr.FROM[sel].map(pidx).values, pr.TO[sel].map(pidx).values] = pr.VALUE[sel].values
    M[bad] = Pm[bad]; print(f"pairs taken from the prior {os.path.basename(PRIOR)}: {bad.mean():.1%} ({(~np.isfinite(M) | bad).sum() - bad.sum()} without prior value)")
else: M[bad] = 999.0
M[~np.isfinite(M)] = 999.0
order = np.argsort(zones); zones_s, Ms = zones[order], M[np.ix_(order, order)]
good = ~bad[np.ix_(order, order)]
print(f"skim: MATSim pairs {good.mean():.1%}, their mean {Ms[good].mean():.1f} min (max {Ms[good].max():.0f}); all pairs mean {Ms[Ms < 999].mean():.1f} min, unreachable {(Ms >= 999).mean():.3%}")
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
F, T = np.meshgrid(zones_s, zones_s, indexing="ij")
with gzip.open(out + ".csv.gz", "wt") as fo:
    fo.write("FROM,TO,VALUE\n"); np.savetxt(fo, np.c_[F.ravel(), T.ravel(), Ms.ravel()], fmt="%d,%d,%.3f")
import openmatrix as omx
with omx.open_file(out + ".omx", "w") as fo:
    fo["mat1"] = Ms.astype(np.float32); fo.create_mapping("origins", zones_s.astype(np.int32)); fo.create_mapping("destinations", zones_s.astype(np.int32))
print("written", out + ".csv.gz", out + ".omx")
