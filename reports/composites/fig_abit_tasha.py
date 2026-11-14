#!/usr/bin/env python3
"""ABIT validation figures in the set of Roorda, Miller & Habib (2008), "Validation of TASHA", TR-A 42:360-375, Figs. 2-8,
for the behavioural model of record (ten replications) in the three settings.  Visual system: composite.py.

    python3 reports/composites/fig_abit_tasha.py [validation verification chain]

Figures (one per setting s = validation | verification | chain):
  fig_abit_start_<s>     weekday activity start time distribution (Roorda Figs. 2, 6), six types
  fig_abit_duration_<s>  weekday activity duration distribution: mean duration by start hour (Figs. 3, 7), six types
  fig_abit_chains_<s>    distribution of the number of trips per home-based chain (Fig. 4)
  fig_abit_distance_<s>  average distance to activities by start hour, zone-skim distance on both sides (Figs. 5, 8), six types
Observed: weighted survey (dark-grey steps or line); model: mean (blue) and 90 % band (mean +- 1.645 s.d.) of the ten replications.
Each panel carries Roorda's Kolmogorov-Smirnov statistic on the hourly values (D, P).
Data: data/abit_roorda_curves.parquet, data/abit_roorda_ks.csv (activity/validation/validate_survey.py) and data/abit_tasha_curves.parquet
(abit_tasha_data.py: replication spread of the durations, distance by type).
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import composite as K                                            # noqa: E402
from matplotlib.ticker import MaxNLocator                        # noqa: E402
ps = K.ps
_legend = K.legend
K.legend = lambda fig, handles, ncol=None, **kw: _legend(fig, handles, ncol=ncol or (2 if len(handles) > 2 else None), **kw)   # 2026-10-29: two columns, the one-row legend overflowed the canvas
HOURS = list(range(4, 24)) + list(range(0, 4))
TYPES = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME", "ALL"]
TNAME = {"WORK": "Work", "SCHOOL": "School", "SHOPPING": "Shopping", "OTHER": "Other", "HOME": "Return home", "ALL": "All activities"}
SUF = os.environ.get("ABIT_SUFFIX", "_behav")     # setting suffix of the model runs, e.g. ABIT_SUFFIX=_respec for the re-specified models
SETTING = {"validation": f"validation{SUF}", "verification": f"verification{SUF}", "chain": f"chain{SUF}"}
C = pd.read_parquet(f"{K.V}/data/abit_roorda_curves.parquet")
KS = pd.read_csv(f"{K.V}/data/abit_roorda_ks.csv")
T = pd.read_parquet(f"{K.V}/data/abit_tasha_curves.parquet")
MIN_DRAW = 30                     # observed activities per hour from which a value is drawn as a full point (the KS threshold)
MIN_SHOW = 10                     # ... and from which it is drawn at all (10-29: open marker)
LEG = [K.h_obs("Observed (survey)"), __import__("matplotlib.lines").lines.Line2D([], [], ls="none", marker="o", ms=3.2, mfc="white", mec=K.OBSERVED, label="Observed, 10–29 activities in the hour (open)"), K.h_model("Model, mean of 10 replications"), K.h_band("Model, 90 % band")]


def ptxt(p):
    return "P < 0.001" if p < 0.001 else f"P = {p:.3f}"


def ks_box(fig, ax, D, P, series, x_halfwidth=0.5):
    """Roorda's KS statistic in the panel, in the upper corner that needs the lower y limit; the y limit is raised until the text
    clears every series (list of (x, y) arrays: observed, model, upper band) under it."""
    txt = f"D = {D:.3f}\n{ptxt(P)}"
    best = None
    for side in ("right", "left"):
        t = ax.text(0.98 if side == "right" else 0.02, 0.97, txt, transform=ax.transAxes, ha=side, va="top", fontsize=ps.FONT, color=ps.INK)
        fig.canvas.draw(); bb = t.get_window_extent(fig.canvas.get_renderer()).transformed(ax.transData.inverted())
        bba = t.get_window_extent(fig.canvas.get_renderer()).transformed(ax.transAxes.inverted())
        lo, hi = bb.x0 - x_halfwidth, bb.x1 + x_halfwidth
        ymax = max([np.nanmax(np.where((x >= lo) & (x <= hi), y, np.nan)) if ((x >= lo) & (x <= hi) & np.isfinite(y)).any() else 0 for x, y in series])
        need = ymax / max(bba.y0 - 0.04, 0.2)
        t.remove()
        if best is None or need < best[1]: best = (side, need)
    side, need = best
    if ax.get_ylim()[1] < need: ax.set_ylim(0, need)
    nice(ax)
    return ax.text(0.98 if side == "right" else 0.02, 0.97, txt, transform=ax.transAxes, ha=side, va="top", fontsize=ps.FONT, color=ps.INK)


def nice(ax, n=4):
    """Round the upper y limit up to a tick of a 1-2-2.5-5 locator."""
    loc = MaxNLocator(n, steps=[1, 2, 5, 10]); top = ax.get_ylim()[1]
    tk = loc.tick_values(0, top); ax.set_ylim(0, tk[-1] if tk[-1] >= top else tk[-1] + (tk[1] - tk[0])); ax.yaxis.set_major_locator(loc)


def hour_axis(ax, show):
    ax.set_xticks(np.arange(0, 24, 4)); ax.set_xlim(-0.5, 23.5); ax.grid(axis="x", visible=False)
    if show: ax.set_xticklabels([str(h) for h in HOURS[::4]]); ax.set_xlabel("Activity start time (h)")
    else: ax.tick_params(labelbottom=False)


def ks(s, fig, ty):
    r = KS[(KS.setting == s) & (KS.figure == fig) & (KS.type == ty)].iloc[0]; return r.D_hourly, r.P_hourly


def six_panels(height=4.3):
    fig = K.new(height); axes = K.grid(fig, 2, 3, sharex=True); return fig, axes


# ------------------------------------------------------------------------------------------------ figures
def fig_start(st):
    s = SETTING[st]; fig, axes = six_panels(); x = np.arange(24); out = {}
    for i, (ax, ty) in enumerate(zip(axes, TYPES)):
        d = C[(C.setting == s) & (C.figure == "start_time") & (C.type == ty)].set_index("hour").reindex(HOURS)
        o, m, sd = d.observed.values, d.model.values, d.model_sd.values
        K.obs_steps(ax, o); K.model_line(ax, x, m, sd=sd)
        ax.set_ylim(0, max(np.nanmax(o), np.nanmax(m + K.Z90 * sd)) * 1.08); nice(ax)
        hour_axis(ax, i >= 3)
        if i % 3 == 0: ax.set_ylabel("Share of activities (%)")
        K.title(ax, K.LETTERS[i], TNAME[ty])
        D, P = ks(s, "start_time", ty); ks_box(fig, ax, D, P, [(x, o), (x, m + K.Z90 * sd)])
        out[ty] = (D, P)
    K.legend(fig, LEG)
    print(f"start {st}:", {k: (round(a, 3), round(b, 3)) for k, (a, b) in out.items()})
    return K.save(fig, f"fig_abit_start_{st}")


def curve_panels(st, figname, ylab, stem):
    s = SETTING[st]; fig, axes = six_panels(); x = np.arange(24); out = {}
    for i, (ax, ty) in enumerate(zip(axes, TYPES)):
        d = T[(T.setting == s) & (T.figure == figname) & (T.type == ty)].set_index("hour").reindex(HOURS)
        # drawn: observed at hours with >= MIN_DRAW observed activities; model over the span of the drawn observed hours (the KS
        # statistic is the stored one, on all hours with both values)
        shown = (d.observed_all.notna() & (d.n_obs >= MIN_SHOW)).values
        lo = hi = int(np.argmax(d.n_obs.values))                         # contiguous block around the busiest hour, one-hour gaps allowed
        while lo > 0 and (shown[lo - 1] or (lo > 1 and shown[lo - 2])): lo -= 1
        while hi < 23 and (shown[hi + 1] or (hi < 22 and shown[hi + 2])): hi += 1
        span = (np.arange(24) >= lo) & (np.arange(24) <= hi); shown = shown & span
        o = np.where(shown, d.observed_all, np.nan); thin = shown & (d.n_obs < MIN_DRAW).values; m = np.where(span & d.model.notna(), d.model, np.nan)
        sd = np.where(np.isfinite(m), d.model_sd.fillna(0), np.nan); both = shown & d.model.notna()
        ax.plot(x, o, color=K.OBSERVED, lw=K.LW_OBS, zorder=3); K.model_line(ax, x, m, sd=sd)
        ax.plot(x[thin], o[thin], "o", ms=3.2, mfc="white", mec=K.OBSERVED, mew=0.8, zorder=5)
        ax.set_ylim(0, np.nanmax(np.r_[o, m + K.Z90 * sd]) * 1.08); nice(ax)
        hour_axis(ax, i >= 3)
        if i % 3 == 0: ax.set_ylabel(ylab)
        K.title(ax, K.LETTERS[i], TNAME[ty])
        D, P = d.D_hourly.iloc[0], d.P_hourly.iloc[0]; ks_box(fig, ax, D, P, [(x, o), (x, m + K.Z90 * sd)])
        out[ty] = (round(D, 3), round(P, 3), int(both.sum()))
    K.legend(fig, LEG, ncol=2)
    print(f"{figname} {st}:", out)
    return K.save(fig, f"{stem}_{st}")


def fig_duration(st):
    return curve_panels(st, "duration", "Mean duration (min)", "fig_abit_duration")


def fig_distance(st):
    return curve_panels(st, "distance", "Mean distance (km)", "fig_abit_distance")


def fig_chains(st):
    s = SETTING[st]; fig = K.new(2.2); ax = K.grid(fig, 1, 1)[0]
    d = C[(C.setting == s) & (C.figure == "chains") & (C.type == "ALL")].set_index("hour").reindex(range(1, 9)); x = np.arange(8)
    o, m, sd = d.observed.values, d.model.values, d.model_sd.values
    # discrete counts: paired bars (observed, model) with the model's 90 % band as an error bar
    w = 0.38
    ax.bar(x - w / 2, o, w, color=K.OBSERVED)
    ax.bar(x + w / 2, m, w, color=K.MODEL)
    ax.errorbar(x + w / 2, m, yerr=K.Z90 * sd, fmt="none", ecolor="#0b0b0b", elinewidth=0.6, capsize=1.5)
    K.cat_axis(ax, [str(i) for i in range(1, 8)] + ["8+"]); ax.set_xlabel("Number of trips per home-based chain"); ax.set_ylabel("Share of chains (%)")
    ax.set_ylim(0, max(np.nanmax(o), np.nanmax(m + K.Z90 * sd)) * 1.08); nice(ax, 5)
    D, P = ks(s, "chains", "ALL"); ks_box(fig, ax, D, P, [(x, o), (x, m + K.Z90 * sd)])
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    K.legend(fig, [Patch(color=K.OBSERVED, label="Observed (survey)"), Patch(color=K.MODEL, label="Model, mean of 10 replications"),
                   Line2D([], [], color="#0b0b0b", lw=0.6, label="Model, 90 % band")])
    print(f"chains {st}: D = {D:.3f}, P = {P:.3f}; obs {np.round(o, 1)}; model {np.round(m, 1)}")
    return K.save(fig, f"fig_abit_chains_{st}")


if __name__ == "__main__":
    for st in sys.argv[1:] or ["validation", "verification", "chain"]:
        for f in (fig_start, fig_duration, fig_chains, fig_distance): print(f(st))
