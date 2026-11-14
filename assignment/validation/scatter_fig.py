#!/usr/bin/env python3
"""Standard count scatter of the MATSim stage: modelled against counted daily volume at every mainline count station, (a) all
vehicles, (b) passenger vehicles, coloured by facility group; equality line, least-squares line through the origin (slope),
coefficient of determination R^2 (squared Pearson correlation), %RMSE and number of stations in each panel.
Reads the station table of validate_counts.py (model = mean of the seeds).  Nothing is fitted to the counts.
Usage: python3 scatter_fig.py [data_dir] [out_without_ext]   (defaults: data/, 5_reports/article/figures/fig_net_scatter)"""
import os, sys, numpy as np, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); V = os.path.dirname(os.path.dirname(H))
sys.path.insert(0, f"{V}/5_reports"); import paperstyle as ps   # noqa: E402
from matplotlib.lines import Line2D                              # noqa: E402
DATA = sys.argv[1] if len(sys.argv) > 1 else f"{H}/data"
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{V}/5_reports/article/figures/fig_net_scatter"
GROUPS = [("freeway", "Interstate, freeway, expressway", ps.CAT[0]), ("arterial", "Principal and minor arterial", ps.CAT[1]),
          ("collector", "Collector and local", ps.CAT[2])]


def stats(c, m):
    slope = (c * m).sum() / (c * c).sum(); r2 = np.corrcoef(c, m)[0, 1] ** 2
    prmse = 100 * np.sqrt(np.mean((m - c) ** 2)) / c.mean(); return slope, r2, prmse


def main():
    S = pd.read_csv(f"{DATA}/stations_model_vs_count.csv", low_memory=False); S = S[S["use"] == "mainline"]
    fig, axs = ps.figure(3.0, ncols=2); rows = []
    for ax, (mc, cc, lab) in zip(axs, [("model_all_mean", "count_all", "All vehicles"), ("model_car_mean", "count_pass", "Passenger vehicles")]):
        d = S[[mc, cc, "fac"]].dropna(); c, m = d[cc].values / 1e3, d[mc].values / 1e3
        hi = np.ceil(max(c.max(), m.max()) * 1.05 / 25) * 25
        for key, gl, col in GROUPS:
            k = d.fac.eq(key).values; ax.scatter(c[k], m[k], s=4, color=col, lw=0, alpha=0.75, zorder=2)
        slope, r2, prmse = stats(c, m)
        ax.plot([0, hi], [0, hi], color=ps.INK2, lw=0.8, zorder=3); ax.plot([0, hi], [0, slope * hi], color=ps.INK2, lw=0.8, ls="--", zorder=3)
        ax.set_xlim(0, hi); ax.set_ylim(0, hi); ax.set_aspect("equal")
        ax.set_xlabel("Counted (thousand vehicles per weekday)"); ax.set_ylabel("Modelled (thousand vehicles per weekday)")
        ax.text(0.04, 0.96, f"{lab}\nn = {len(d):,}\nslope = {slope:.2f}\n$R^2$ = {r2:.2f}\n%RMSE = {prmse:.1f}", transform=ax.transAxes,
                va="top", ha="left", fontsize=ps.TICK, color=ps.INK)
        rows.append(dict(panel=lab, n=len(d), slope=slope, r2=r2, prmse=prmse))
        for key, gl, col in GROUPS:
            k = d.fac.eq(key).values; s_, r_, p_ = stats(c[k], m[k]); rows.append(dict(panel=f"{lab}: {gl}", n=int(k.sum()), slope=s_, r2=r_, prmse=p_))
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=col, ms=3, label=gl) for _, gl, col in GROUPS]
               + [Line2D([], [], color=ps.INK2, lw=0.8, label="Modelled = counted"), Line2D([], [], color=ps.INK2, lw=0.8, ls="--", label="Least-squares line through the origin")],
               loc="outside lower center", ncol=3, fontsize=ps.TICK)
    ps.finish(fig, OUT, panel_labels="ab")
    R = pd.DataFrame(rows); R.to_csv(f"{DATA}/scatter_stats.csv", index=False, float_format="%.4f"); print(R.to_string())


if __name__ == "__main__":
    main()
