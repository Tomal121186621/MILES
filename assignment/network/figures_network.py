#!/usr/bin/env python3
"""Paper figure of the network step (through reports/paperstyle.py), written to WORKSPACE/4_matsim/figures/ and copied to
5_reports/paper/figures/:
  fig_net_map   study-area road network by functional class with the MDOT count stations (held-out half marked)
Drawn at its printed size (\\textwidth = 5.313 in); paperstyle.finish() refuses overlapping or cropped text and fonts below 7.5 pt.
The former fig_net_class_matrix and fig_net_speed_osm_mdot are replaced by fig_v4_inputs and fig_v4_a (reports/figures_validation.py).
Data: data/network_audit_links.parquet, data/count_stations_split.csv, data/count_stations_matched.csv, MATSIM_HOME/data/bmr_counties.gpkg."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, shutil
import numpy as np, pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from netio import ROOT, DATA, study_area
sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps

FIG = f"{WORKSPACE}/4_matsim/figures"; os.makedirs(FIG, exist_ok=True)
PAPERFIG = f"{WORKSPACE}/5_reports/paper/figures"
A = pd.read_parquet(f"{DATA}/network_audit_links.parquet")
counties, area = study_area()

GROUP = {"motorway": "Freeway", "trunk": "Freeway", "motorway_link": "Ramp", "trunk_link": "Ramp", "primary": "Principal arterial", "secondary": "Minor arterial", "tertiary": "Collector"}
COL = {"Freeway": ps.CAT[0], "Ramp": ps.CAT[0], "Principal arterial": ps.CAT[1], "Minor arterial": ps.CAT[3], "Collector": ps.MUTED}
LW = {"Freeway": 1.3, "Ramp": 0.5, "Principal arterial": 0.75, "Minor arterial": 0.55, "Collector": 0.35}
HALO = [pe.withStroke(linewidth=2.6, foreground="white")]

fig, ax = ps.figure(6.2)
ax.set_aspect("equal"); ax.set_axis_off(); ax.grid(False)
counties.boundary.plot(ax=ax, color=ps.AXIS, linewidth=0.6, zorder=1)
for grp in ["Collector", "Minor arterial", "Principal arterial", "Ramp", "Freeway"]:
    d = A[A.hwy.map(GROUP) == grp]
    segs = np.stack([np.stack([d.x0.values, d.y0.values], 1), np.stack([d.x1.values, d.y1.values], 1)], 1) / 1000
    ax.add_collection(LineCollection(segs, colors=COL[grp], linewidths=LW[grp], zorder=2 if grp != "Freeway" else 3, alpha=0.9 if grp != "Collector" else 0.6))
S = pd.read_csv(f"{DATA}/count_stations_split.csv"); M = pd.read_csv(f"{DATA}/count_stations_matched.csv")
S = S.merge(M[["LOCATION_ID", "x", "y"]], on="LOCATION_ID")
cc = S[S.split == "calibration_check"]; ho = S[S.split == "held_out"]
ax.scatter(cc.x / 1000, cc.y / 1000, s=3.0, facecolor=ps.OBSERVED, edgecolor="none", zorder=4)
ax.scatter(ho.x / 1000, ho.y / 1000, s=6.0, facecolor="none", edgecolor=ps.CAT[7], linewidths=0.55, zorder=5)
ax.annotate("Key Bridge\n(closed)", xy=(437.9, 170.2), xytext=(447, 158), fontsize=ps.FONT, color=ps.INK, ha="left", zorder=7, path_effects=HALO,
            arrowprops=dict(arrowstyle="-", color=ps.INK2, lw=0.7))
# county labels in open parts of each county (km, EPSG:26985)
LABELS = {"Carroll": (390, 210), "Baltimore County": (452, 214), "Harford": (476, 222), "Howard": (398, 172), "Anne Arundel": (452, 140)}
for nm, (lx, ly) in LABELS.items():
    ax.text(lx, ly, nm, fontsize=ps.FONT, color=ps.INK, ha="center", va="center", zorder=8, path_effects=HALO)
ax.annotate("Baltimore City", xy=(431, 188), xytext=(412, 199), fontsize=ps.FONT, color=ps.INK, ha="center", va="center", zorder=8, path_effects=HALO,
            arrowprops=dict(arrowstyle="-", color=ps.INK2, lw=0.7, shrinkA=2, shrinkB=0))
# scale bar (10 km) and north arrow, lower right
sx, sy = 462, 124
ax.plot([sx, sx + 10], [sy, sy], color=ps.INK, lw=1.8, solid_capstyle="butt", zorder=8)
ax.text(sx + 5, sy + 1.4, "10 km", fontsize=ps.FONT, color=ps.INK, ha="center", va="bottom", zorder=8, path_effects=HALO)
ax.annotate("", xy=(sx + 5, sy + 15), xytext=(sx + 5, sy + 7), arrowprops=dict(arrowstyle="-|>", color=ps.INK, lw=1.0, mutation_scale=10), zorder=8)
ax.text(sx + 5, sy + 15.8, "N", fontsize=ps.FONT, color=ps.INK, ha="center", va="bottom", zorder=8, path_effects=HALO)
handles = [Line2D([0], [0], color=COL[g], lw=max(LW[g] * 2, 1.0), label=g) for g in ["Freeway", "Principal arterial", "Minor arterial", "Collector"]]
handles += [Line2D([0], [0], marker="o", ls="", ms=3, mfc=ps.OBSERVED, mec="none", label=f"Count station used for\nnetwork checks ({len(cc):,})"),
            Line2D([0], [0], marker="o", ls="", ms=4.5, mfc="none", mec=ps.CAT[7], mew=0.8, label=f"Count station held out\nfor validation ({len(ho):,})")]
ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 0.0), handlelength=1.8, labelspacing=0.6)
x0, y0, x1, y1 = counties.total_bounds / 1000; ax.set_xlim(x0 - 2, x1 + 2); ax.set_ylim(y0 - 2, y1 + 2)
p = ps.finish(fig, f"{FIG}/fig_net_map")
shutil.copy(p, f"{PAPERFIG}/fig_net_map.pdf")
print("figure written to", FIG, "and copied to", PAPERFIG)
