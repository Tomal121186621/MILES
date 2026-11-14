#!/usr/bin/env python3
"""Keep MATSim activities off car links outside the network's strongly connected component (validation study, 2026-11-02).

With the cordon gateways off (abit_to_matsim_pop.py --residents-only), activities of residents outside the study area keep their real
coordinates, and MATSim attaches each activity to the nearest car link.  For points beyond the north-east edge of network_2024 that
nearest link can be a dead-end piece of the I-95 Express Toll Lanes that no route reaches (MATSim stops: "No route found ... by mode car").
This script computes the largest strongly connected component of the car links and, for every activity whose nearest car link
is outside it (or a non-SCC link lies within 500 m of the distance to the nearest SCC link), writes link="<nearest SCC link>" on the
activity; every other activity is left to MATSim's own XY-to-link mapping.  Coordinates are unchanged.
Usage: pop_scc_links.py <network.xml.gz> <population in> <population out>"""
import sys, gzip, re, collections
import numpy as np, shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
net, pin, pout = sys.argv[1:4]
nodes, links = {}, []
for line in gzip.open(net, "rt"):
    if "<node " in line:
        m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', line); nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    elif "<link " in line:
        m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)"', line); mo = re.search(r'modes="([^"]*)"', line)
        if mo and "car" in mo.group(1).split(","): links.append((m.group(1), m.group(2), m.group(3)))
nid = {n: i for i, n in enumerate(nodes)}
f = np.array([nid[l[1]] for l in links]); t = np.array([nid[l[2]] for l in links])
G = csr_matrix((np.ones(len(links)), (f, t)), shape=(len(nodes), len(nodes)))
nc, lab = connected_components(G, directed=True, connection="strong"); big = np.bincount(lab).argmax()
in_scc = (lab[f] == big) & (lab[t] == big)
xy = np.array([nodes[l[1]] + nodes[l[2]] for l in links])
geoms = shapely.linestrings(np.stack([xy[:, :2], xy[:, 2:]], axis=1))
ids = np.array([l[0] for l in links])
tree_in = shapely.STRtree(geoms[in_scc]); tree_out = shapely.STRtree(geoms[~in_scc]); ids_in = ids[in_scc]
print(f"car links {len(links):,}; largest SCC {in_scc.sum():,}; outside {(~in_scc).sum():,}")
rx = re.compile(r'<activity [^>]*?x="([^"]+)" y="([^"]+)"')
lines = gzip.open(pin, "rt").readlines()
idx = [i for i, l in enumerate(lines) if "<activity " in l and 'link="' not in l]
P = shapely.points(np.array([[float(v) for v in rx.search(lines[i]).groups()] for i in idx]))
g_in, g_out = geoms[in_scc], geoms[~in_scc]
(_, j_in), d_in = tree_in.query_nearest(P, return_distance=True, all_matches=False)
(_, j_out), d_out = tree_out.query_nearest(P, return_distance=True, all_matches=False)
sel = d_out <= d_in + 500; fixed = collections.Counter()
for k in np.nonzero(sel)[0]:
    i = idx[k]; lid = ids_in[j_in[k]]; lines[i] = lines[i].replace("<activity ", f'<activity link="{lid}" ', 1); fixed[lid] += 1
with gzip.open(pout, "wt") as fo: fo.writelines(lines)
print(f"activities {len(idx):,}; link set (nearest SCC link) on {int(sel.sum()):,}; target links {dict(fixed.most_common(5))}")
