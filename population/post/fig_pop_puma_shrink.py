#!/usr/bin/env python3
"""Synthetic share against ACS share by PUMA (96 PUMAs, six states) for six attribute classes, with the equality line and the
least-squares slope of synthetic on ACS (slope below 1: PUMAs drawn toward the mean of all PUMAs).  Reads
data/stage1_composition_puma96.csv (validate_stage1_puma96.py).  Output: 5_reports/article/figures/fig_val_pop_puma.{pdf,png}."""
import sys, numpy as np, pandas as pd
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; sys.path.insert(0, f"{V}/5_reports")
import paperstyle as ps
from matplotlib.lines import Line2D
R = pd.read_csv(f"{V}/data/stage1_composition_puma96.csv"); R["bin"] = R["bin"].astype(str)
ST = {24: "Maryland", 11: "District of Columbia", 10: "Delaware", 42: "Pennsylvania", 51: "Virginia", 54: "West Virginia"}
COL = dict(zip(ST, ps.CAT))
PAN = [("household size", "1", "One person"), ("household size", "5", "5+ persons"), ("autos", "0", "No car"),
       ("income class", "0", "Income < \\$25k"), ("income class", "5", "Income \\$150k+"), ("employed (16+)", "1", "Employed (16+)")]
fig, axs = ps.figure(height=5.2, nrows=2, ncols=3); rows = []
for ax, (t, b, lab) in zip(axs.flat, PAN):
    d = R[(R.table == t) & (R.bin == b)]; x, y = 100 * d.observed.values, 100 * d.model.values
    s, c = np.polyfit(x, y, 1); hi = float(np.ceil(max(x.max(), y.max()) / 10) * 10)
    ax.plot([0, hi], [0, hi], color=ps.INK2, lw=0.8, zorder=1)
    ax.plot([0, hi], [c, c + s * hi], color=ps.INK2, lw=0.8, ls="--", zorder=1)
    for st in ST:
        k = d.state.values == st
        ax.scatter(x[k], y[k], s=12, color=COL[st], lw=0.4, edgecolor="white", zorder=3 if st == 24 else 2)
    lo = float(np.floor(min(x.min(), y.min()) / 10) * 10) if min(x.min(), y.min()) > 30 else 0.0   # employment: start near the data
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    ax.set_title(lab, loc="right", fontsize=ps.TICK, fontweight="normal", color=ps.INK2)
    ax.set_xlabel(f"ACS (%)\nslope {s:.2f}"); ax.set_ylabel("Synthetic (%)")
    rows.append(dict(cls=lab.replace("\\", ""), slope=s, intercept=c, mean_diff_pp=float((y - x).mean()), corr=float(np.corrcoef(x, y)[0, 1])))
print(pd.DataFrame(rows).round(3).to_string(index=False))
h = [Line2D([], [], ls="", marker="o", color=COL[s], markersize=5, label=f"{n} ({int((R[R.table == 'sex'].drop_duplicates(['state', 'puma']).state == s).sum())})") for s, n in ST.items()]
h += [Line2D([], [], color=ps.INK2, lw=0.8, label="Equality"), Line2D([], [], color=ps.INK2, lw=0.8, ls="--", label="Fitted line")]
fig.legend(handles=h, loc="outside lower center", ncol=4)
ps.finish(fig, f"{V}/5_reports/article/figures/fig_val_pop_puma", panel_labels="abcdef")
