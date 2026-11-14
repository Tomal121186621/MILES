#!/usr/bin/env python3
"""Figures of the destination-choice estimation and validation (paperstyle, strict checks: reports/paperstyle.finish).

    python3 validate_dc.py figures

  fig_dc_decay        impedance utility against distance (primary destinations) and detour (stops), by purpose: the
                      piecewise-linear term plus beta_cgt x the mean car generalized time of the zone pairs in each 1 km band
                      (median-income household; primary destinations only, the stop panel shows the detour term), relative to the
                      value at 1 km
  fig_dc_tld_primary  held-out half: observed and predicted trip-length distributions of primary destinations by purpose
                      (estimated MNL and the former gravity form; full-choice-set expectations)
  fig_dc_tld_stop     the same for stops (former rule: the corridor rule)
  fig_dc_sim_tld      ABIT runs on the survey population of the validation half (10 seeds): discretionary trip lengths by
                      purpose, before (gravity) and after (estimated MNL), against the survey
Output: 3_abit/figures/fig_dc_*.pdf/png.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_common as C
sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps   # noqa: E402
import matplotlib.pyplot as plt   # noqa: E402

FIG = f"{C.A3}/figures"; RES = f"{C.DCD}/results"
DIST_LABELS = ["0-1", "1-2", "2-3", "3-5", "5-7.5", "7.5-10", "10-15", "15-20", "20-30", "30-50", "50+"]
TICKS = [s.replace("-", "–") for s in DIST_LABELS]
PNAME = {"SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompany", "OTHER": "Other errands"}


def decay():
    from validate_dc import final_model
    sk = C.skims(); d = sk["d"].astype(float); t = sk["t"].astype(float); dr = sk["draw"].astype(float)
    vf = np.clip((7018.0 / C.VOT_REF) ** C.VOT_ELAST, C.VOT_MIN, C.VOT_MAX); gt = t + dr * 0.12 * 60 / (30 * vf)
    xs = np.arange(0.5, 60.5, 1.0)
    band = np.clip(np.floor(d).astype(int), 0, 300); mean_gt = (np.bincount(band.ravel(), weights=gt.ravel(), minlength=301) / np.maximum(np.bincount(band.ravel(), minlength=301), 1))[:60]
    ps.use(); fig, axes = plt.subplots(1, 2, figsize=(ps.WIDTH, 2.9), sharey=True)
    for ax, kind in zip(axes, ["primary", "stop"]):
        for k, pur in enumerate(C.DISC):
            spec, x, _ = final_model(f"{pur}_{kind}"); b = dict(zip(spec.params(), x)); knots = C.DKNOTS if kind == "stop" else C.KNOTS
            names = C.pw_names("dt" if kind == "stop" else "d", knots)
            u = sum(b.get(n, 0.0) * p for n, p in zip(names, C.pw(xs, knots)))
            if kind == "primary": u = u + b.get("cgt", 0.0) * mean_gt[:len(xs)] + b.get("ctime", 0.0) * 0
            u = u - np.interp(1.0, xs, u)
            ax.plot(xs, u, color=ps.CAT[k], label=PNAME[pur])
        ax.set_xlabel("Distance from home (km)" if kind == "primary" else "Detour of the stop (km)"); ax.set_xlim(0, 60)
    axes[0].set_ylabel("Impedance utility relative to 1 km (–)")
    h, l = axes[0].get_legend_handles_labels(); fig.legend(h, l, loc="outside lower center", ncol=4)
    return ps.finish(fig, f"{FIG}/fig_dc_decay", ["a", "b"])


def tld_heldout(kind):
    T = pd.read_csv(f"{RES}/heldout_tld.csv"); T = T[(T.half == "validation") & (T.bin != "mean_km")]
    ps.use(); fig, axes = plt.subplots(2, 2, figsize=(ps.WIDTH, 4.8), sharex=True)
    x = np.arange(len(DIST_LABELS)); w = 0.27
    old = "Former gravity form" if kind == "primary" else "Former corridor rule"
    for ax, pur in zip(axes.flat, C.DISC):
        g = T[T.segment == f"{pur}_{kind}"]
        get = lambda m: 100 * g[g.model == m].set_index("bin").share.reindex(DIST_LABELS).values
        ax.bar(x - w, get("observed"), w, color=ps.OBSERVED, label="Observed")
        ax.bar(x, get("mnl"), w, color=ps.MODEL, label="Estimated model")
        ax.bar(x + w, get("gravity"), w, color=ps.VARIANT, label=old)
        top = max(get("observed").max(), get("mnl").max(), get("gravity").max()); ax.set_ylim(0, top * 1.12)
        ax.set_ylabel("Share of trips (%)"); ax.set_xticks(x); ax.set_xticklabels(TICKS, rotation=45, ha="right")
        ax.set_title(PNAME[pur], loc="right", fontsize=8, fontweight="normal", color=ps.INK2)
    for ax in axes[-1]: ax.set_xlabel("Trip distance (km)")
    h, l = axes[0, 0].get_legend_handles_labels(); fig.legend(h, l, loc="outside lower center", ncol=3)
    return ps.finish(fig, f"{FIG}/fig_dc_tld_{kind}", list("abcd"))


def tld_sim(setting="validation"):
    f = f"{RES}/sim_tld.csv"
    if not os.path.exists(f): return None
    T = pd.read_csv(f); T = T[T.setting == setting]
    if T.variant.nunique() < 2: return None
    ps.use(); fig, axes = plt.subplots(2, 2, figsize=(ps.WIDTH, 4.8), sharex=True)
    x = np.arange(len(DIST_LABELS)); w = 0.27
    for ax, pur in zip(axes.flat, C.DISC):
        g = T[T.purpose == pur]
        ob = 100 * g[g.variant == "after"].set_index("bin").observed.reindex(DIST_LABELS).values
        af = 100 * g[g.variant == "after"].set_index("bin").model.reindex(DIST_LABELS).values
        be = 100 * g[g.variant == "before"].set_index("bin").model.reindex(DIST_LABELS).values
        ax.bar(x - w, ob, w, color=ps.OBSERVED, label="Observed"); ax.bar(x, af, w, color=ps.MODEL, label="Model, estimated destination choice")
        ax.bar(x + w, be, w, color=ps.VARIANT, label="Model, former destination choice")
        ax.set_ylim(0, max(ob.max(), af.max(), be.max()) * 1.12); ax.set_ylabel("Share of trips (%)")
        ax.set_xticks(x); ax.set_xticklabels(TICKS, rotation=45, ha="right")
        ax.set_title(PNAME[pur], loc="right", fontsize=8, fontweight="normal", color=ps.INK2)
    for ax in axes[-1]: ax.set_xlabel("Trip distance (km)")
    h, l = axes[0, 0].get_legend_handles_labels(); fig.legend(h, l, loc="outside lower center", ncol=2)
    return ps.finish(fig, f"{FIG}/fig_dc_sim_tld_{setting}", list("abcd"))


def main():
    out = [decay(), tld_heldout("primary"), tld_heldout("stop")]
    for s in ["validation", "chain"]: out.append(tld_sim(s))
    for f in out:
        if f: print("figure", f)


if __name__ == "__main__":
    main()
