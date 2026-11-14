#!/usr/bin/env python3
"""Paper figure of the transit build (reports/paperstyle.py): fig_net_transit = the mapped transit routes by mode over the 2024 road
network, (a) the network area, (b) Baltimore.  Links used by a route are drawn once per mode (rail over bus); artificial links
(no network link: rail without OSM track, ferry, a route between candidate links without a road path) dashed.
Usage: python assignment/transit/figures_transit.py <schedule.xml.gz> <network_pt.xml.gz> <out without extension>
Panel functions (used by reports/composites/fig_mode_network.py): load_segments() parses the two files once and caches the line
segments in data/transit_map_segments_<stem>.pkl; draw_map(ax, S, zoom) draws one map; handles() gives the legend entries."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys, gzip, re, os, collections, pickle, numpy as np
sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
HERE = f"{WORKSPACE}/4_matsim/transit"; DATA = f"{WORKSPACE}/data"   # transit build files and cached segments (workspace)
CLS = [("bus_local", "Bus (local)", ps.CAT[0], 0.35), ("bus_coach", "Commuter bus", ps.CAT[6], 0.5), ("ferry", "Ferry", ps.CAT[4], 0.9),
       ("light_rail", "Light rail", ps.CAT[2], 1.1), ("metro", "Metro (MTA, WMATA)", ps.CAT[7], 1.1), ("rail", "MARC, Amtrak", ps.CAT[1], 1.1)]
BALTIMORE = ((418000, 446000), (168000, 196000))     # EPSG:26985


def cls(feed, mode):
    if mode == "bus": return "bus_coach" if feed == "cb" else "bus_local"
    return {"tram": "light_rail", "subway": "metro", "rail": "rail", "ferry": "ferry"}[mode]


def load_segments(sched=f"{HERE}/transitSchedule_2024.xml.gz", net=f"{HERE}/network_2024_pt.xml.gz", cache=True):
    """{'bg': segments of the major road network, cls: (real segments, artificial segments), 'extent': ((x0,x1),(y0,y1))}."""
    f = f"{DATA}/transit_map_segments_{os.path.basename(sched).split('.')[0]}.pkl"
    if cache and os.path.exists(f) and os.path.getmtime(f) > max(os.path.getmtime(sched), os.path.getmtime(net)): return pickle.load(open(f, "rb"))
    nodes, links = {}, {}
    with gzip.open(net, "rt") as fh:
        for l in fh:
            if "<node " in l: m = re.search(r'id="([^"]+)" x="([^"]+)" y="([^"]+)"', l); nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
            elif "<link " in l:
                m = re.search(r'id="([^"]+)" from="([^"]+)" to="([^"]+)".*?freespeed="([^"]+)" capacity="([^"]+)"', l); links[m.group(1)] = (m.group(2), m.group(3), float(m.group(4)), float(m.group(5)), re.search(r'modes="([^"]*)"', l).group(1))
    used = collections.defaultdict(set); feed = mode = None
    with gzip.open(sched, "rt") as fh:
        for l in fh:
            if "<transitLine " in l: feed = re.search(r'id="([^:"]+)', l).group(1)
            elif "<transportMode>" in l: mode = re.search(r">([^<]+)", l).group(1)
            elif "<link refId=" in l: used[cls(feed, mode)].add(re.search(r'refId="([^"]+)"', l).group(1))
    seg = lambda ids: np.array([(nodes[links[i][0]], nodes[links[i][1]]) for i in ids if links[i][0] != links[i][1]]).reshape(-1, 2, 2)
    S = {"bg": seg([i for i, v in links.items() if "car" in v[4] and v[2] >= 17 and v[3] >= 1500])}
    for c, *_ in CLS:
        ids = used[c]; S[c] = (seg([i for i in ids if "artificial" not in links[i][4]]), seg([i for i in ids if "artificial" in links[i][4]]))
    xy = np.array([nodes[links[i][0]] for c in used for i in used[c]])
    S["extent"] = ((np.percentile(xy[:, 0], 0.5) - 3000, np.percentile(xy[:, 0], 99.5) + 3000), (np.percentile(xy[:, 1], 0.5) - 3000, np.percentile(xy[:, 1], 99.5) + 3000))
    if cache: pickle.dump(S, open(f, "wb"))
    return S


def draw_map(ax, S, zoom=False, rasterized=True, scalebar=True):
    ax.add_collection(LineCollection(S["bg"], colors=ps.GRID, linewidths=0.3, zorder=1, rasterized=rasterized))
    for k, (c, lab, col, lw) in enumerate(CLS):
        real, art = S[c]
        ax.add_collection(LineCollection(real, colors=col, linewidths=lw * (1.4 if zoom else 1), zorder=3 + k, rasterized=rasterized))
        ax.add_collection(LineCollection(art, colors=col, linewidths=lw * 0.8, linestyles=(0, (2, 1.5)), zorder=2, rasterized=rasterized))
    ax.set_aspect("equal"); ax.grid(False); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    (x0, x1), (y0, y1) = BALTIMORE if zoom else S["extent"]; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    if scalebar:
        x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
        ax.plot([x0 + 0.05 * (x1 - x0), x0 + 0.05 * (x1 - x0) + 10000], [y0 + 0.04 * (y1 - y0)] * 2, color=ps.INK2, lw=1.2, zorder=20)
        ax.text(x0 + 0.05 * (x1 - x0) + 5000, y0 + 0.06 * (y1 - y0), "10 km", ha="center", fontsize=ps.TICK, color=ps.INK2, zorder=20, bbox=dict(facecolor="white", edgecolor="none", pad=1))


def handles():
    return [Line2D([], [], color=col, lw=max(lw, 0.8) * 1.5, label=lab) for c, lab, col, lw in CLS] + \
           [Line2D([], [], color=ps.MUTED, lw=0.9, ls=(0, (2, 1.5)), label="Artificial link"), Line2D([], [], color=ps.GRID, lw=1.5, label="Major road")]


if __name__ == "__main__":
    sched, net, out = sys.argv[1:4]
    S = load_segments(sched, net)
    fig, axs = ps.figure(ps.DOUBLE, 4.3, ncols=2)
    for k, ax in enumerate(axs): draw_map(ax, S, zoom=bool(k), rasterized=False)
    fig.legend(handles=handles(), loc="outside lower center", ncols=4)
    print(ps.finish(fig, out, ["a", "b"]))
