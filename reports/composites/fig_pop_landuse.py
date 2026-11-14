#!/usr/bin/env python3
"""Figures of stage 1 (population synthesis, CVAE) and stage 2 (land use, SILO).  Visual system: composite.py.

    python3 reports/composites/fig_pop_landuse.py [--silo oos_mean] [population landuse s_pop_quality s_commute]

Article
  fig_population  synthetic population against the ACS and Census by area: (a) composition, model minus ACS share of every
                  attribute category, one mark per PUMA; (b) persons in households by county / Census estimate; (c) filled
                  jobs by county / LODES 2016 (same county order as b)
  fig_landuse     land use against observed data not used in its estimation: (a) event rates by year, calibration window
                  2017-2020 and test window 2021-2024; (b) composition by county in the last test year; (c) new dwellings
                  2021-2024 by county / permits
Supplementary Material
  fig_s_pop_quality  generative quality on the held-out PUMS test split: (a) total-variation distance and SRMSE of every
                     marginal with the sampling floor; (b) the ten worst two-way tables
  fig_s_commute      commute of the synthetic workers against the RTS: (a) distance, (b) time
Data and data classes: reports/figures_validation.py (Stage1, Stage2).  The land-use test window reads
data/silo_validation_<--silo>.parquet; a rerun of this script with the five-seed out-of-sample file picks it up unchanged.
"""
import argparse, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import composite as K             # noqa: E402
import figures_validation as fv   # noqa: E402
ps = K.ps
RL = "Model ÷ observed\n(ratio)"

SHORT = {"Aged 0–17": "Age 0–17", "Aged 18–34": "Age 18–34", "Aged 35–64": "Age 35–64", "Aged 65+": "Age 65+", "Employed (16+)": "Employed 16+",
         "1-person household": "1 person", "2-person household": "2 persons", "3-person household": "3 persons", "4-person household": "4 persons",
         "5+ person household": "5+ persons", "Income under \\$25k": "Income <\\$25k", "Income \\$150k or more": "Income ≥\\$150k",
         "Living with parents (18–34)": "With parents"}


def p_comp(ax, B, tablekey, tol=5, lim=12):
    """One row per attribute category (short label), one mark per area: model minus observed share (pp); outside +-tol in the accent."""
    rows = fv.bin_rows(B, tablekey); B = B.assign(_b=B["bin"].astype(str))
    ax.axvspan(-tol, tol, color=ps.TOL_BAND, lw=0, zorder=0); ax.axvline(0, color=ps.INK2, lw=0.7, zorder=1)
    y = K.rows_axis(ax, [SHORT.get(r[2], r[2]) for r in rows]); prev = None
    for yy, (t, b, L, s, g) in zip(y, rows):
        v = np.clip(B[(B[tablekey] == t) & (B._b == b)].diff_pp.values, -lim + 0.3, lim - 0.3); ok = np.abs(v) <= tol
        ax.scatter(v[ok], np.full(ok.sum(), yy), marker="|", s=30, lw=0.8, color=K.MODEL, alpha=0.6, zorder=3)
        ax.scatter(v[~ok], np.full((~ok).sum(), yy), s=12, color=K.OUTSIDE, lw=0, zorder=4)
        if prev is not None and g != prev: ax.axhline(yy + 0.5, color=ps.AXIS, lw=0.5, zorder=1)
        prev = g
    ax.set_xlim(-lim, lim); ax.set_xticks([-10, -5, 0, 5, 10]); ax.set_xticklabels(["−10", "−5", "0", "5", "10"])
    ax.set_xlabel("Model − observed\n(percentage points)")


def p_ratio_rows(ax, names, r, band, center=1.0, err=None, xlim=None, xticks=None, label=None, show=True, log=False):
    K.ratio_band(ax, band, center)
    if log: ax.set_xscale("log")
    y = K.rows_axis(ax, names, True) if show else np.arange(len(names))[::-1]; r = np.asarray(r, float)
    K.dots(ax, r, y, ok=np.abs(r / center - 1) <= band + 1e-9, err=err)
    if xlim: ax.set_xlim(*xlim)
    if xticks is not None:
        if log: fv.plain_log(ax.xaxis, xticks)
        else: ax.set_xticks(xticks)
    if label: ax.set_xlabel(label)


# ================================================================================================ article
def population(S):
    fig = K.new(4.2); gs = fig.add_gridspec(1, 3)
    a = fig.add_subplot(gs[0]); b = fig.add_subplot(gs[1]); c = fig.add_subplot(gs[2], sharey=b)
    p_comp(a, S.comp(), "table")
    P = S.persons().sort_values("ratio", ascending=False)
    J = S.R[S.R.section == "D jobs"].copy(); J["county"] = J.geo.astype(int); J = J.set_index("county").reindex(P.county)
    p_ratio_rows(b, P.name.values, P.ratio.values, band=0.05, center=0.977, xlim=(0.74, 1.09), xticks=[0.8, 0.9, 1.0], label=RL)
    p_ratio_rows(c, P.name.values, J.ratio.values, band=0.10, xlim=(0.85, 1.36), xticks=[0.9, 1.0, 1.1, 1.2, 1.3], label=RL, show=False)
    c.tick_params(labelleft=False, axis="y", length=0); c.grid(axis="y", visible=False)
    K.title(a, "a", "Composition"); K.title(b, "b", "Persons"); K.title(c, "c", "Jobs")
    K.legend(fig, [K.h_model_dot("Model, one area"), K.h_out(), K.h_tol()])
    return K.save(fig, "fig_population")


def p_events(ax, C, T):
    """Rows: events; upper sub-row the calibration window 2017-2020 (one seed, diamonds), lower sub-row the test window
    (mean of the seeds with the 90 % band across seeds, mean +- 1.645 s.d., circles); one mark per year, window mean as a black bar."""
    K.ratio_band(ax, 0.05); names = [e[0] for e in fv.EVENTS]; y = K.rows_axis(ax, names)
    for yy, (lab, tab, geo, _) in zip(y, fv.EVENTS):
        for S, off, mk in [(C, 0.2, "D"), (T, -0.2, "o")]:
            d = S.ev(tab, geo); d = d[d.year.isin(S.win)]; n = len(d); yj = np.full(n, yy + off)
            ok = ((d.ratio - 1).abs() <= 0.05).values; v = d.ratio.values
            if S.has_sd: ax.errorbar(v, yj, xerr=1.645 * d.seed_sd.values / d.observed.values, fmt="none", ecolor=K.MODEL, elinewidth=0.7, zorder=3)
            col = K.LIGHT_MODEL if mk == "D" else K.MODEL
            ax.scatter(v[ok], yj[ok], s=12, marker=mk, color=col, edgecolor=K.MODEL if mk == "D" else "none", lw=0.4, zorder=4)
            ax.scatter(v[~ok], yj[~ok], s=12, marker=mk, color=K.OUTSIDE, lw=0, zorder=5)
            m = d.model.sum() / d.observed.sum(); ax.plot([m, m], [yy + off - 0.17, yy + off + 0.17], color=ps.INK, lw=1.3, zorder=6)
    for k in range(1, len(names)): ax.axhline(k - 0.5, color=ps.AXIS, lw=0.5, zorder=1)
    ax.set_xlim(0.78, 1.22); ax.set_xticks([0.8, 0.9, 1.0, 1.1, 1.2]); ax.set_xlabel(RL)


def landuse(scen):
    C = fv.Stage2("calib_r51"); T = fv.Stage2(scen, "2021-2024")   # calibration window: round 51 (2026-10-29, construction by yearly county permits), the levers of the final seeds
    fig = K.new(4.2); gs = fig.add_gridspec(1, 3)
    a, b, c = (fig.add_subplot(gs[i]) for i in range(3))
    p_events(a, C, T)
    p_comp(b, T.comp(T.yl), "tbl")
    D = T.constr().sort_values("ratio", ascending=False)
    p_ratio_rows(c, D.name.values, D.ratio.values, band=0.10, log=True, xlim=(0.3, 5), xticks=[0.5, 1, 2, 4], label=RL)
    K.title(a, "a", "Event rates"); K.title(b, "b", "Composition"); K.title(c, "c", "Dwellings")
    K.legend(fig, [K.Line2D([], [], marker="D", ms=K.MS - 0.6, ls="", color=K.LIGHT_MODEL, mec=K.MODEL, mew=0.4, label="Model, 2017–2020, one year"),
                   K.h_model_dot(f"Model, {T.win[0]}–{T.win[-1]}, one year or county"), K.h_err("Model, 90 % band of seeds"),
                   K.Line2D([], [], color=ps.INK, marker="|", ms=8, mew=1.3, ls="", label="Window mean"), K.h_out(), K.h_tol()], ncol=3)
    return K.save(fig, "fig_landuse")


# ================================================================================================ supplementary
LAB = {"dwellingType": "Dwelling type", "tenure": "Tenure", "autos": "Cars", "income_bin": "Income", "age_bin": "Age", "gender": "Sex", "race": "Race",
       "occupation": "Occupation", "driversLicense": "Driving licence", "relationship": "Relationship", "nationality": "Nationality"}


def s_pop_quality(S):
    J = S.J; hh = J["2_marginals_hh"]; pp = J["2_marginals_pp"]; fl = J["12_identifiability_floor_hh"]
    fig = K.new(3.3); gs = fig.add_gridspec(1, 2); a, b = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    names = [f"HH {LAB[k].lower()}" for k in hh] + [f"P {LAB[k].lower()}" for k in pp]
    tv = [hh[k]["tv"] for k in hh] + [pp[k]["tv"] for k in pp]; sr = [hh[k]["srmse"] for k in hh] + [pp[k]["srmse"] for k in pp]
    y = K.rows_axis(a, names); a.grid(axis="x", visible=True)
    a.scatter(tv, y + 0.17, s=14, color=K.MODEL, lw=0, zorder=4); a.scatter(sr, y - 0.17, s=14, marker="D", facecolor="white", edgecolor=K.MODEL, lw=0.9, zorder=4)
    a.scatter([fl[k] for k in hh], y[:len(hh)] - 0.17, marker="|", s=60, lw=1.4, color=K.OBSERVED, zorder=3)
    a.set_xlim(0, 0.105); a.set_xticks([0, 0.025, 0.05, 0.075, 0.1]); a.set_xticklabels(["0", "0.025", "0.05", "0.075", "0.1"]); a.set_xlabel("Error against held-out households (–)")
    W = J["3_joints_pp"]["worst_pairs"] + J["3_joints_hh"]["worst_pairs"]; npp = len(J["3_joints_pp"]["worst_pairs"])
    def nm(p_, i):
        for x_, z in [("_bin", ""), ("dwellingType", "dwelling"), ("autos", "cars"), ("driversLicense", "licence"), ("gender", "sex"), ("relationship", "relation"), ("occupation", "occup.")]: p_ = p_.replace(x_, z)
        return ("HH " if i >= npp else "P ") + p_.replace("×", " × ")
    W = sorted([(nm(p_, i), v) for i, (p_, v) in enumerate(W)], key=lambda t: -t[1])
    y2 = K.rows_axis(b, [n for n, _ in W]); b.grid(axis="x", visible=True)
    b.scatter([v for _, v in W], y2, s=14, marker="D", facecolor="white", edgecolor=K.MODEL, lw=0.9, zorder=4)
    b.set_xlim(0, 0.25); b.set_xticks([0, 0.05, 0.1, 0.15, 0.2, 0.25]); b.set_xlabel("Error against held-out households (–)")
    K.title(a, "a", "Marginals"); K.title(b, "b", "Worst two-way tables")
    K.legend(fig, [K.Line2D([], [], color=K.MODEL, marker="o", ms=K.MS, ls="", label="Total-variation distance"),
                   K.Line2D([], [], marker="D", ms=K.MS - 0.5, ls="", mfc="white", mec=K.MODEL, mew=0.9, label="Standardised root-mean-square error"),
                   K.Line2D([], [], marker="|", ms=8, mew=1.4, ls="", color=K.OBSERVED, label="Sampling floor")])
    return K.save(fig, "fig_s_pop_quality")


def s_commute(S):
    fig = K.new(2.5); a, b = K.grid(fig, 1, 2)
    d = S.C[S.C.quantity == "distance"]; x = np.arange(len(d))
    K.obs_steps(a, d.observed * 100); K.model_line(a, x, d.model * 100)
    K.cat_axis(a, fv.DIST_TICKS, rotate=True); a.set_xlabel("Commute distance (km)"); a.set_ylabel("Share of commuters (%)"); a.set_ylim(0, 20)
    t = S.C[S.C.quantity == "time"]; x = np.arange(len(t))
    K.obs_steps(b, t.observed * 100); K.model_line(b, x, t.model * 100)
    b.set_xticks(np.arange(0, 25, 6) - 0.5); b.set_xticklabels(["0", "30", "60", "90", "120"]); b.set_xlim(-0.5, len(t) - 0.5); b.grid(axis="x", visible=False)
    b.set_xlabel("Commute time (min)"); b.set_ylabel("Share of commuters (%)"); b.set_ylim(0, 20)
    K.title(a, "a", "Distance"); K.title(b, "b", "Time")
    K.legend(fig, [K.h_model(), K.h_obs()])
    return K.save(fig, "fig_s_commute")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--silo", default="oos_mean")
    ap.add_argument("which", nargs="*", default=["population", "landuse", "s_pop_quality", "s_commute"])
    a = ap.parse_args()
    S = fv.Stage1() if {"population", "s_pop_quality", "s_commute"} & set(a.which) else None
    if "population" in a.which: print(population(S))
    if "landuse" in a.which: print(landuse(a.silo))
    if "s_pop_quality" in a.which: print(s_pop_quality(S))
    if "s_commute" in a.which: print(s_commute(S))
