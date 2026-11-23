#!/usr/bin/env python3
"""Figures of the tour mode choice and of the network and transit inputs.  Visual system: composite.py.

    python3 reports/composites/fig_mode_network.py [mode s_mode_purpose s_mode_cars s_net_maps s_net_checks]

Article
  fig_mode          tour mode share by one-way tour distance, six modes, observed tours of the held-out half (mode choice
                    alone): model mean and 5th-95th percentile of 10 replications against the survey
Supplementary Material
  fig_s_mode_purpose  model minus observed tour mode share by purpose (pp) in three settings: mode choice alone, tours DAYMAP
                      generates for the observed held-out population, chain test (synthetic population)
  fig_s_mode_cars     car-driver and car-passenger share by car sufficiency: mode choice alone and chain test
  fig_s_net_maps      mapped transit routes, network area and Baltimore
  fig_s_net_checks    (a) OSM road type agreeing with the MDOT SHA functional class, (b) speed tag and model free speed
                      against the posted-speed sign, (c) scheduled / published headway
Data: 3_abit/mode_choice/results/obs_validation.csv, abit_mode_validation.csv (validate_mode_choice.py); data/network_audit_*.csv,
data/transit_gtfs_headways_core.csv; assignment/transit/figures_transit.py (map segments).
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import composite as K                                   # noqa: E402
ps = K.ps; V = K.V
sys.path.insert(0, f"{K.MILES_HOME}/assignment/transit")
import figures_transit as TR                            # noqa: E402
from matplotlib.lines import Line2D                     # noqa: E402
from matplotlib.patches import Patch                    # noqa: E402
from matplotlib.colors import LogNorm                   # noqa: E402
from matplotlib.ticker import FixedLocator, NullFormatter   # noqa: E402

RES = f"{V}/3_abit/mode_choice/results"; DATA = f"{V}/data"
MODES = ["CAR_DRIVER", "CAR_PASSENGER", "BUS", "TRAIN", "WALK", "BIKE"]
MLAB = {"CAR_DRIVER": "Car driver", "CAR_PASSENGER": "Car passenger", "BUS": "Bus", "TRAIN": "Train", "WALK": "Walk", "BIKE": "Bicycle"}
MSHORT = {"CAR_DRIVER": "Car\ndriver", "CAR_PASSENGER": "Car\npassenger", "BUS": "Bus", "TRAIN": "Train", "WALK": "Walk", "BIKE": "Bicycle"}
PURP = ["WORK", "EDUCATION", "SHOPPING", "RECREATION", "ACCOMPANY", "OTHER", "all"]
PLAB = {"WORK": "Work", "EDUCATION": "School", "SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompanying", "OTHER": "Other", "all": "All tours"}
DLAB = ["0-2", "2-5", "5-10", "10-20", "20-40", "40-80", "80+"]
CARS = ["0 cars", "cars < drivers", "cars >= drivers"]; CARLAB = ["No car", "Cars < drivers", "Cars ≥ drivers"]
MABBR = {"CAR_DRIVER": "CD", "CAR_PASSENGER": "CP", "BUS": "Bus", "TRAIN": "Tr", "WALK": "Wk", "BIKE": "Bk"}


# ================================================================================================ mode choice
def mode_data():
    o = pd.read_csv(f"{RES}/obs_validation.csv"); a = pd.read_csv(f"{RES}/abit_mode_validation.csv")
    return {"obs": o[(o.setting == "validation") & (o.variant == "behavioural")],
            "abit": a[(a.setting == "validation") & (a.variant == "behav")],
            "chain": a[(a.setting == "chain") & (a.variant == "behav")]}


def fig_mode():
    D = mode_data()["obs"]; fig = K.new(3.9); axes = K.grid(fig, 2, 3, sharex=True); x = np.arange(len(DLAB))
    for i, (ax, m) in enumerate(zip(axes, MODES)):
        r = D[(D.dim == "distance") & (D["mode"] == m)].set_index("group").reindex(DLAB)
        ax.plot(x, 100 * r.observed, color=K.OBSERVED, lw=K.LW_OBS, marker="s", ms=K.MS - 0.6, zorder=3)
        K.model_line(ax, x, 100 * r.model, lo=100 * r.p05, hi=100 * r.p95); ax.plot(x, 100 * r.model, "o", color=K.MODEL, ms=K.MS - 0.4, zorder=5)
        top = 100 * max(np.nanmax(r.observed), np.nanmax(r.p95)); step = 20 if top > 50 else (10 if top > 20 else (5 if top > 6 else 1))
        ax.set_ylim(0, min(100, np.ceil(top * 1.15 / step) * step)); ax.yaxis.set_major_locator(FixedLocator(np.arange(0, 101, step)))
        K.cat_axis(ax, [s.replace("-", "–") for s in DLAB], rotate=True, show=i >= 3)
        if i >= 3: ax.set_xlabel("One-way tour distance (km)")
        if i % 3 == 0: ax.set_ylabel("Share of tours (%)")
        K.title(ax, K.LETTERS[i], MLAB[m])
    K.legend(fig, [K.Line2D([], [], color=K.OBSERVED, lw=K.LW_OBS, marker="s", ms=K.MS - 0.6, label="Observed"),
                   K.Line2D([], [], color=K.MODEL, lw=K.LW_MODEL, marker="o", ms=K.MS - 0.4, label="Model"), K.h_band("Model, 90 % band of 10 replications")])
    return K.save(fig, "fig_mode")


def diff_matrix(d):
    d = d[d.dim.isin(["purpose", "all"])]
    return np.array([[100 * (r.model - r.observed) for r in [d[(d.group == p) & (d["mode"] == m)].iloc[0] for m in MODES]] for p in PURP])


def s_mode_purpose():
    D = mode_data(); fig = K.new(2.9); gs = fig.add_gridspec(1, 4, width_ratios=[1, 1, 1, 0.06])
    axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    for i, (ax, key, t) in enumerate(zip(axes, ["obs", "abit", "chain"], ["Choice alone", "Generated", "Chain test"])):
        H = diff_matrix(D[key]); ax.grid(False)
        im = ax.imshow(np.clip(H, -ps.PP_LIM, ps.PP_LIM), cmap=ps.DIV, vmin=-ps.PP_LIM, vmax=ps.PP_LIM, aspect="auto", interpolation="nearest")
        ax.axhline(len(PURP) - 1.5, color="white", lw=2.0)
        for a_ in range(H.shape[0]):
            for b_ in range(H.shape[1]):
                v = H[a_, b_]
                if abs(v) >= 2: ax.text(b_, a_, f"{v:+.0f}".replace("-", "−"), ha="center", va="center", fontsize=ps.TICK, color="white" if abs(v) > 6 else ps.INK)
        ax.set_xticks(range(len(MODES))); ax.set_xticklabels([MABBR[m] for m in MODES])
        ax.set_yticks(range(len(PURP))); ax.set_yticklabels([PLAB[p] for p in PURP] if i == 0 else [""] * len(PURP)); ax.tick_params(length=0)
        for sp in ax.spines.values(): sp.set_visible(False)
        K.title(ax, K.LETTERS[i], t)
    cax = fig.add_subplot(gs[0, 3]); cb = fig.colorbar(im, cax=cax, ticks=[-10, -5, 0, 5, 10]); cb.outline.set_visible(False)
    cb.ax.set_yticklabels(["−10", "−5", "0", "5", "10"]); cb.set_label("Model − observed (percentage points)"); cb.ax.tick_params(length=2)
    return K.save(fig, "fig_s_mode_purpose")


def s_mode_cars():
    D = mode_data(); fig = K.new(2.5); axes = K.grid(fig, 1, 2, sharey=True)
    for i, (ax, m) in enumerate(zip(axes, ["CAR_DRIVER", "CAR_PASSENGER"])):
        y = K.rows_axis(ax, CARLAB) if i == 0 else np.arange(len(CARLAB))[::-1]
        for d, col, off, mk in [(D["obs"], "observed", 0.22, "s"), (D["obs"], "model", 0.0, "o"), (D["chain"], "model", -0.22, "D")]:
            r = d[(d.dim == "cars") & (d["mode"] == m)].set_index("group").reindex(CARS)
            if col == "observed": ax.plot(100 * r.observed, y + off, "s", ms=K.MS - 0.4, color=K.OBSERVED, ls="", zorder=4); continue
            c = K.MODEL if mk == "o" else K.LIGHT_MODEL
            ax.errorbar(100 * r.model, y + off, xerr=[100 * (r.model - r.p05).clip(lower=0), 100 * (r.p95 - r.model).clip(lower=0)], fmt=mk, ms=K.MS - (0 if mk == "o" else 0.6),
                        color=c, mec=K.MODEL, mew=0.5, ecolor=K.MODEL, elinewidth=0.8, capsize=0, zorder=5)
        ax.set_xlim(-3, 80); ax.set_xticks([0, 20, 40, 60, 80]); ax.set_xlabel("Share of tours (%)")
        if i: ax.tick_params(labelleft=False)
        K.title(ax, K.LETTERS[i], MLAB[m])
    K.legend(fig, [K.h_obs_dot(), K.h_model_dot("Model, mode choice alone"), K.Line2D([], [], color=K.LIGHT_MODEL, mec=K.MODEL, mew=0.5, marker="D", ms=K.MS - 0.6, ls="", label="Model, chain test"),
                   K.Line2D([], [], color=K.MODEL, marker="|", ms=7, mew=0.8, ls="", label="90 % band of 10 replications")], ncol=2)
    return K.save(fig, "fig_s_mode_cars")


# ================================================================================================ network and transit
OSM_ROWS = ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street", "service"]
AGREE = {("motorway", 1), ("motorway", 2), ("trunk", 2), ("trunk", 3), ("primary", 3), ("secondary", 4), ("tertiary", 5), ("tertiary", 6), ("residential", 7),
         ("unclassified", 7), ("living_street", 7), ("service", 7)}


def p_class(ax):
    ct = pd.read_csv(f"{DATA}/network_audit_class_crosstab.csv", index_col=0)
    n = ct[[c for c in ct.columns if c.startswith("links_")]]; n.columns = [int(c.split("fc")[1]) for c in n.columns]
    n = n.loc[[r for r in OSM_ROWS if r in n.index]]; share = n.div(n.sum(axis=1), axis=0)
    agree = np.array([sum(share.loc[r, c] for c in n.columns if (r, c) in AGREE) for r in n.index]) * 100
    y = K.rows_axis(ax, [r.replace("_", " ").capitalize() for r in n.index]); K.dots(ax, agree, y)
    ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xlabel("Links agreeing with\nthe inventory (%)")


def speed_pairs():
    return pd.read_csv(f"{DATA}/network_audit_speed_pairs.csv").dropna(subset=["osm_posted"])


def p_speed_diff(ax, SP):
    bins = np.arange(-32.5, 33, 5); ax.axvspan(-5, 5, color=ps.TOL_BAND, lw=0, zorder=0); ax.axvline(0, color=ps.INK2, lw=0.7, zorder=1)
    h, _ = np.histogram(SP.osm_minus_mdot.clip(-30, 30), bins=bins); ax.stairs(100 * h / h.sum(), bins, color=K.MODEL, lw=K.LW_MODEL, zorder=4, baseline=None)
    h2, _ = np.histogram(SP.coded_minus_mdot.clip(-30, 30), bins=bins); ax.stairs(100 * h2 / h2.sum(), bins, color=K.LIGHT_MODEL, lw=K.LW_MODEL, ls=(0, (4, 2)), zorder=3, baseline=None)
    ax.set_xlabel("Difference to the\nposted sign (mph)"); ax.set_ylabel("Share of signs (%)"); ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticks([-30, -15, 0, 15, 30]); ax.set_xlim(-36, 36)


def p_headway(ax):
    Hh = pd.read_csv(f"{DATA}/transit_gtfs_headways_core.csv")
    bus = sorted([(r.route.replace("CityLink ", "").title(), r.am_peak / 10.0) for r in Hh.itertuples() if r.route.startswith("CityLink")], key=lambda r: r[1])
    mt = Hh[Hh.route.str.startswith("METRO")].iloc[0]; metro = [("Morning peak", mt.am_peak / 8.0), ("Midday", mt.midday / 10.0), ("Evening", mt.evening / 11.0)]
    rows = [("Metro subway", None)] + metro + [("CityLink bus, peak", None)] + bus[::-1]
    K.ratio_band(ax, 0.2); y = K.rows_axis(ax, [nm_ for nm_, v in rows])
    vv = np.array([np.nan if v is None else v for _, v in rows]); m = np.isfinite(vv)
    K.dots(ax, vv[m], y[m], ok=np.abs(vv[m] - 1) <= 0.2); ax.set_xlabel("Model ÷ published\n(ratio)")
    for t, (nm_, v) in zip(ax.get_yticklabels(), rows[::-1]):
        if v is None: t.set_fontweight("bold"); t.set_color(ps.INK)
    ax.set_xlim(0.7, 1.6); ax.set_xticks([0.8, 1.0, 1.2, 1.4])


def s_net_maps():
    S = TR.load_segments(); fig = K.new(2.9); a, b = K.grid(fig, 1, 2)
    TR.draw_map(a, S, zoom=False); TR.draw_map(b, S, zoom=True)
    K.title(a, "a", "Network area"); K.title(b, "b", "Baltimore")
    K.legend(fig, TR.handles(), ncol=4)
    return K.save(fig, "fig_s_net_maps")


def s_net_checks():
    SP = speed_pairs(); fig = K.new(3.4); a, b, c = K.grid(fig, 1, 3)
    p_class(a); p_speed_diff(b, SP); p_headway(c)
    K.title(a, "a", "Road class"); K.title(b, "b", "Speed"); K.title(c, "c", "Headway")
    K.legend(fig, [K.h_model_dot("Network or timetable"), K.h_model("Speed tag"), K.h_variant("Model free speed"), K.h_out(), K.h_tol()], ncol=3)
    return K.save(fig, "fig_s_net_checks")


if __name__ == "__main__":
    w = sys.argv[1:] or ["mode", "s_mode_purpose", "s_mode_cars", "s_net_maps", "s_net_checks"]
    for k, f in [("mode", fig_mode), ("s_mode_purpose", s_mode_purpose), ("s_mode_cars", s_mode_cars), ("s_net_maps", s_net_maps), ("s_net_checks", s_net_checks)]:
        if k in w: print(f())
