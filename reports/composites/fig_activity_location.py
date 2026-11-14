#!/usr/bin/env python3
"""Figures of activity generation and scheduling (ABIT) and of destination/location choice.  Visual system: composite.py.

NOTE (2026-10-26): fig_activity, fig_s_duration and fig_s_chains are superseded in the article by the TASHA-form set of
fig_abit_tasha.py (start, duration, chains, distance; validation in the article, verification and chain test in the
Supplementary Material); fig_location is now a Supplementary figure (label fig:s_location).

    python3 reports/composites/fig_activity_location.py [activity location s_duration s_chains s_stops]

Article
  fig_activity  start-time distribution by activity type (work, school, shopping, other, return home, all), behavioural
                model on the observed households of the held-out half, mean and 90 % band of ten replications, against the
                weighted survey (form of Roorda et al. 2008, Fig. 6)
  fig_location  trip-length distribution of the primary destinations of the four discretionary purposes on the held-out
                half: estimated multinomial logit (full choice set) and former model against the survey
Supplementary Material
  fig_s_duration  mean duration by start hour, four activity types, with the hours of 90 % of the observed starts
  fig_s_chains    (a) trips per home-based chain, (b) mean trip distance by start hour
  fig_s_stops     trip-length distribution of the stops of the four discretionary purposes
Data: data/abit_roorda_{curves,ks}.* (activity/validation/validate_survey.py, read with tasha_stage3.Data);
3_abit/destination_choice/results/heldout_tld.csv.
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import composite as K                                            # noqa: E402
ps = K.ps
sys.path.insert(0, f"{K.MILES_HOME}/reports"); import tasha_stage3 as t3  # noqa: E402
from matplotlib.ticker import MaxNLocator, MultipleLocator       # noqa: E402
import matplotlib.transforms as mtrans                           # noqa: E402

SET = "validation_behav"                     # behavioural model, observed households of the held-out half
HOURS = t3.HOUR_ORDER                        # 4, 5, ..., 23, 0, ..., 3
TNAME = {"WORK": "Work", "SCHOOL": "School", "SHOPPING": "Shopping", "OTHER": "Other", "HOME": "Return home", "ALL": "All activities"}
DC = f"{K.V}/3_abit/destination_choice/results"
DIST = ["0-1", "1-2", "2-3", "3-5", "5-7.5", "7.5-10", "10-15", "15-20", "20-30", "30-50", "50+"]
DTICK = [s.replace("-", "–") for s in DIST]
PURP = [("SHOPPING", "Shopping"), ("RECREATION", "Recreation"), ("ACCOMPANY", "Accompanying"), ("OTHER", "Other errands")]


def curves():
    C = pd.read_parquet(f"{K.V}/data/abit_roorda_curves.parquet"); return C[C.setting == SET]


def curve(C, fig, ty):
    return C[(C.figure == fig) & (C.type == ty)].set_index("hour").reindex(HOURS)


def hour_axis(ax, show):
    ax.set_xticks(np.arange(0, 24, 4)); ax.set_xlim(-0.5, 23.5); ax.grid(axis="x", visible=False)
    if show: ax.set_xticklabels([str(h) for h in HOURS[::4]]); ax.set_xlabel("Start hour (h)")
    else: ax.tick_params(labelbottom=False)


def ks_line(ty, fig="start_time"):
    K_ = pd.read_csv(f"{K.V}/data/abit_roorda_ks.csv"); r = K_[(K_.setting == SET) & (K_.figure == fig) & (K_.type == ty)].iloc[0]
    return f"{TNAME[ty]} D = {r.D_hourly:.2f}, P = {r.P_hourly:.2f}"


# ================================================================================================ article
def fig_activity():
    C = curves(); fig = K.new(4.0); axes = K.grid(fig, 2, 3, sharex=True)
    types = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME", "ALL"]
    for i, (ax, ty) in enumerate(zip(axes, types)):
        d = curve(C, "start_time", ty); x = np.arange(24)
        K.obs_steps(ax, d.observed.values); K.model_line(ax, x, d.model.values, sd=d.model_sd.values)
        top = max(d.observed.max(), d.model.max()) * 1.12
        ax.set_ylim(0, top); ax.yaxis.set_major_locator(MaxNLocator(4, steps=[1, 2, 5, 10], integer=True))
        hour_axis(ax, i >= 3)
        if i % 3 == 0: ax.set_ylabel("Share of activities (%)")
        K.title(ax, K.LETTERS[i], TNAME[ty])
    K.legend(fig, [K.h_obs(), K.h_model(), K.h_band("Model, 90 % band of 10 replications")])
    print("KS (caption):", "; ".join(ks_line(t) for t in types))
    return K.save(fig, "fig_activity")


def tld_panels(kind, name):
    T = pd.read_csv(f"{K.V}/3_abit/tasha_estimation/results/heldout_tld_taz.csv"); T = T[(T.half == "validation") & (T.bin != "mean_km")]   # 2026-10-29: models of record, TAZ records
    fig = K.new(4.0); axes = K.grid(fig, 2, 2, sharex=True, sharey=True); x = np.arange(len(DIST))
    for i, (ax, (pur, nm)) in enumerate(zip(axes, PURP)):
        g = T[T.segment == f"{pur}_{kind}"]; get = lambda m: 100 * g[g.model == m].set_index("bin").share.reindex(DIST).values
        has_former = (g.model == "gravity").any()
        K.obs_steps(ax, get("observed"))
        if has_former: K.model_line(ax, x, get("gravity"), color=K.LIGHT_MODEL, ls=(0, (4, 2)), zorder=3)
        K.model_line(ax, x, get("mnl"))
        assert np.nanmax(np.r_[get("observed"), get("mnl")] if not has_former else np.r_[get("observed"), get("mnl"), get("gravity")]) < 24.5
        ax.set_ylim(0, 25); ax.set_yticks([0, 5, 10, 15, 20, 25])
        K.cat_axis(ax, DTICK, rotate=True, show=i >= 2)
        if i >= 2: ax.set_xlabel("Trip distance (km)")
        if i % 2 == 0: ax.set_ylabel("Share of trips (%)")
        K.title(ax, K.LETTERS[i], nm)
    hs = [K.h_obs(), K.h_model("Model, estimated destination choice")] + ([K.h_variant("Former model (gravity)")] if kind == "primary" else [])
    K.legend(fig, hs)
    return K.save(fig, name)


def fig_location():
    return tld_panels("primary", "fig_location")


# ================================================================================================ supplementary
def s_duration():
    C = curves(); D = t3.Data([("_behav", "behavioural")]); fig = K.new(3.6); axes = K.grid(fig, 2, 2, sharex=True)
    for i, (ax, ty) in enumerate(zip(axes, ["WORK", "SCHOOL", "SHOPPING", "OTHER"])):
        d = curve(C, "duration", ty); th = D.thin("validation", ty); x = np.arange(24)
        o = np.where(th, np.nan, d.observed.values); m = np.where(th, np.nan, d.model.values)
        lo, hi = d.band_lo.iloc[0] / 60 - 0.5, d.band_hi.iloc[0] / 60 - 0.5        # hours of 90 % of the observed starts, x of HOURS
        tr = mtrans.blended_transform_factory(ax.transData, ax.transAxes)
        ax.plot([lo, hi], [0.95, 0.95], color=ps.INK2, lw=0.9, transform=tr, solid_capstyle="butt")
        for v in (lo, hi): ax.plot([v, v], [0.91, 0.99], color=ps.INK2, lw=0.9, transform=tr)
        ax.plot(x, o, color=K.OBSERVED, lw=K.LW_OBS, zorder=3); ax.plot(x, m, color=K.MODEL, lw=K.LW_MODEL, zorder=4)
        top = np.nanmax(np.r_[o, m]); step = 120 if top > 200 else (30 if top < 100 else 60)
        ax.set_ylim(0, np.ceil(top * 1.3 / step) * step); ax.yaxis.set_major_locator(MultipleLocator(step * (2 if top / step > 4 else 1)))
        hour_axis(ax, i >= 2)
        if i % 2 == 0: ax.set_ylabel("Mean duration (min)")
        K.title(ax, K.LETTERS[i], TNAME[ty])
    K.legend(fig, [K.h_obs(), K.h_model(), K.Line2D([], [], color=ps.INK2, lw=0.9, marker="|", ms=6, label="Hours of 90 % of observed starts")])
    print("KS duration (caption):", "; ".join(ks_line(t, "duration") for t in ["WORK", "SCHOOL", "SHOPPING", "OTHER"]))
    return K.save(fig, "fig_s_duration")


def s_chains():
    C = curves(); fig = K.new(2.5); a, b = K.grid(fig, 1, 2)
    d = C[(C.figure == "chains") & (C.type == "ALL")].set_index("hour").reindex(range(1, 9)); x = np.arange(8)
    a.errorbar(x + 0.12, d.model.values, yerr=K.Z90 * d.model_sd.values, fmt="o", ms=K.MS, color=K.MODEL, elinewidth=0.8, capsize=0, zorder=4)
    a.plot(x - 0.12, d.observed.values, "s", ms=K.MS - 0.4, color=K.OBSERVED, zorder=4)
    K.cat_axis(a, [str(i) for i in range(1, 8)] + ["8+"]); a.set_xlabel("Trips per home-based chain"); a.set_ylabel("Share of chains (%)")
    a.set_ylim(0, 70); a.yaxis.set_major_locator(MultipleLocator(10))
    d = curve(C, "distance_by_hour", "ALL"); x = np.arange(24)
    b.plot(x, d.observed.values, color=K.OBSERVED, lw=K.LW_OBS, zorder=3); b.plot(x, d.model.values, color=K.MODEL, lw=K.LW_MODEL, zorder=4)
    hour_axis(b, True); b.set_ylabel("Mean trip distance (km)"); b.set_ylim(0, 30); b.yaxis.set_major_locator(MultipleLocator(10))
    K.title(a, "a", "Trips per chain"); K.title(b, "b", "Distance by start hour")
    K.legend(fig, [K.Line2D([], [], color=K.OBSERVED, lw=K.LW_OBS, marker="s", ms=K.MS - 0.4, label="Observed"),
                   K.Line2D([], [], color=K.MODEL, lw=K.LW_MODEL, marker="o", ms=K.MS, label="Model"),
                   K.Line2D([], [], color=K.MODEL, marker="|", ms=7, mew=0.8, ls="", label="Model, 90 % band of 10 replications")])
    print("KS (caption):", ks_line("ALL", "chains"), ks_line("ALL", "distance_by_hour"))
    return K.save(fig, "fig_s_chains")


def s_stops():
    return tld_panels("stop", "fig_s_stops")


if __name__ == "__main__":
    w = sys.argv[1:] or ["activity", "location", "s_duration", "s_chains", "s_stops"]
    for k, f in [("activity", fig_activity), ("location", fig_location), ("s_duration", s_duration), ("s_chains", s_chains), ("s_stops", s_stops)]:
        if k in w: print(f())
