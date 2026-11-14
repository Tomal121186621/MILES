#!/usr/bin/env python3
"""Validation figures of the TR Part A paper (Section 5 and Online Appendix), one scheme for the four stages.

    python3 reports/figures_validation.py                      # all stages
    python3 reports/figures_validation.py 2 --silo oos_mean    # stage 2 only, from data/silo_validation_oos_mean.parquet
    python3 reports/figures_validation.py 4 --matsim-runs <dir>

Every figure is drawn at its printed size (\\textwidth = 5.313 in wide, at most 0.85 \\textheight high) and included with
width=\\textwidth; paperstyle.finish() refuses to save a figure with text below 7.5 pt, overlapping text or anything beyond the
canvas.  Main figures have at most four panels (one message each); the other dimensions and the detail are appendix figures.
Labels are plain words with units; data-source names, acronyms and statistics are in the captions, not in the plots.

    stage 1  fig_v1_main  (a) persons by county  (b) composition by attribute  (c) joint structure, held-out data  (d) commute distance
             appendix     fig_v1_a levels detail, fig_v1_b composition detail, fig_v1_d held-out marginals, fig_v1_e commute
    stage 2  fig_v2_main  (a) event rates  (b) composition  (c) construction by county  (d) one-person and low-income households
             appendix     fig_v2_a events by year, fig_v2_a2 calibration rounds, fig_v2_b composition by county, fig_v2_c
                          construction map, fig_v2_d controlled totals, fig_v2_d2 attribute shares over time, fig_v2_e jobs and commute
    stage 3  TASHA form (Roorda et al., 2008; reports/tasha_stage3.py): tables tab_s3_{verification,validation,chain}.tex and
             fig_t3_{start,duration,chains,distance}_{verification,validation,chain}
             appendix     fig_v3_a tours (gate runs), fig_v3_b2 mode shares, fig_v3_c groups, fig_v3_e trip distance by purpose
    stage 4  fig_v4_inputs (network and transit inputs), appendix fig_v4_a (class matrix); fig_v4_main pending (assignment runs)
Outputs: 5_reports/figures/fig_v*.pdf/png (copied to paper/figures/), 5_reports/FIGURE_CATALOGUE.md.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, glob, json, os, re, shutil, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.colors import ListedColormap, BoundaryNorm, LogNorm
from matplotlib.ticker import FuncFormatter, FixedLocator, NullFormatter, NullLocator, MaxNLocator

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps   # noqa: E402
DATA = f"{V}/data"; OUT = f"{V}/5_reports/figures"; PAPERFIG = f"{V}/5_reports/paper/figures"; os.makedirs(OUT, exist_ok=True)
CAT_ROWS = []
DIST_LABELS = ["0-1", "1-2", "2-3", "3-5", "5-7.5", "7.5-10", "10-15", "15-20", "20-30", "30-50", "50+"]     # data keys
DIST_TICKS = [s.replace("-", "–") for s in DIST_LABELS]                                                     # printed
DIST_EDGES = [0, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 50, np.inf]
HOUR_ORDER = list(range(4, 24)) + list(range(0, 4))
HALO = [pe.withStroke(linewidth=2.4, foreground="white")]
RLAB = ps.RATIO_LABEL


# ================================================================================================ shared helpers
def record(stage, dim, fig, data, func, caption, status="ready"):
    CAT_ROWS.append(dict(stage=stage, dim=dim, fig=fig, data=data, func=func, caption=caption, status=status))


def H_(key, tol=None):
    """Legend handle by role; labels from paperstyle.LEG (identical in every figure)."""
    L = ps.LEG
    if key == "model": return Line2D([], [], color=ps.MODEL, marker="o", ms=4, lw=1.4, label=L["model"])
    if key == "observed": return Line2D([], [], color=ps.OBSERVED, marker="s", ms=3.6, lw=1.4, label=L["observed"])
    if key == "model_bar": return Patch(facecolor=ps.MODEL, label=L["model"])
    if key == "observed_bar": return Patch(facecolor=ps.OBSERVED, label=L["observed"])
    if key == "model_dot": return Line2D([], [], color=ps.MODEL, marker="o", ms=4.5, ls="", label=L["model"])
    if key == "seed": return Patch(facecolor=ps.SEED_BAND, edgecolor="none", label=L["seed"])
    if key == "seed_bar": return Line2D([], [], color=ps.MODEL, marker="|", ms=7, mew=1.0, ls="", label=L["seed"])
    if key == "tol": return Patch(facecolor=ps.TOL_BAND, edgecolor="none", label=ps.tol_label(tol))
    if key == "outside": return Line2D([], [], marker="o", ls="", mfc="white", mec=ps.MODEL, mew=1.0, ms=4.5, label=L["outside"])
    raise KeyError(key)


def fig_legend(fig, keys, tol=None, ncol=None):
    h = [H_(k, tol) for k in keys]
    fig.legend(handles=h, loc="outside upper center", ncol=ncol or len(h), frameon=False)


def save(fig, name, panels=None):
    if panels:
        for k, ax in panels.items(): ps.panel_label(ax, k)
    p = ps.finish(fig, f"{OUT}/{name}"); shutil.copy(p, f"{PAPERFIG}/{name}.pdf"); return f"5_reports/figures/{name}.pdf"


def heading(ax, txt):
    """Short plain-word heading of a small-multiple panel (8 pt, centred), next to the bold panel letter."""
    ax.set_title(txt, loc="center", fontsize=ps.FONT, fontweight="normal", color=ps.INK2)


def zonesys():
    return pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv")


def county_names():
    z = zonesys().drop_duplicates("COUNTYFIPS").set_index("COUNTYFIPS").JUR_NAME
    def short(s):
        s = re.sub(r", (MD|DC|VA|WV|DE|PA)$", "", s)
        s = s.replace("Baltimore County", "Baltimore County").replace("District of Columbia", "Washington DC").replace("Fairfax County/Fairfax City/Falls Church City", "Fairfax")
        s = s.replace("Prince William County/Manassas City/Manassas Park City", "Prince William").replace("Alexandria City", "Alexandria")
        s = s.replace(" County", "") if s != "Baltimore County" else s
        return s.replace("St. Mary's", "St Mary's")
    return z.map(short)


NAMES = county_names()


def counties():
    """County polygons of the zone system: zone shapefile dissolved by COUNTYFIPS (cached in data/zone_counties.gpkg)."""
    import geopandas as gpd
    f = f"{DATA}/zone_counties.gpkg"
    if not os.path.exists(f):
        g = gpd.read_file(f"{ABIT_HOME}/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp")[["zone_id", "geometry"]]
        z = zonesys()[["ZoneId", "COUNTYFIPS", "STFIPS"]]
        g = g.merge(z, left_on="zone_id", right_on="ZoneId"); g["geometry"] = g.geometry.buffer(0)
        c = g.dissolve(by="COUNTYFIPS", aggfunc={"STFIPS": "first"}).reset_index()
        c["geometry"] = c.geometry.simplify(150); c.to_file(f, driver="GPKG")
    c = gpd.read_file(f); c["COUNTYFIPS"] = c.COUNTYFIPS.astype(int)
    return c.set_index("COUNTYFIPS")


def md_counties():
    c = counties(); return c[c.STFIPS == 24]


def dist_pmf(x, w=None):
    b = pd.cut(pd.Series(x), DIST_EDGES, right=False, labels=DIST_LABELS)
    s = (pd.Series(1.0 if w is None else w, index=b.index)).groupby(b, observed=False).sum()
    return (s / s.sum()).reindex(DIST_LABELS).values


def dist_axis(ax, label="Distance (km)", show=True):
    ax.set_xticks(range(len(DIST_LABELS)))
    if show: ax.set_xticklabels(DIST_TICKS, rotation=45, ha="right", rotation_mode="anchor"); ax.set_xlabel(label)
    else: ax.tick_params(labelbottom=False)
    ax.set_xlim(-0.5, len(DIST_LABELS) - 0.5)


def hour_axis(ax, every=4, label="Activity start hour (h)", show=True):
    x = np.arange(24); ax.set_xticks(x[::every]); ax.set_xlim(-0.5, 23.5)
    if show: ax.set_xticklabels([f"{h}" for h in HOUR_ORDER][::every]); ax.set_xlabel(label)
    else: ax.tick_params(labelbottom=False)


def plain_log(axis, ticks):
    axis.set_major_locator(FixedLocator(ticks)); axis.set_minor_locator(NullLocator())
    axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))


def dot_chart(ax, names, r, band, center=1.0, err=None, label=RLAB, log=False, xlim=None, ticks=None, show_names=True, s=18):
    """Horizontal dot chart of ratios sorted ascending (largest at the top); open markers outside center*(1 +- band)."""
    r = np.asarray(r, float); o = np.argsort(r); r = r[o]; y = np.arange(len(r)); names = np.asarray(names)[o]
    ps.ratio_axis(ax, band=band, center=center, orient="x", label=label, log=log)
    ok = np.abs(r / center - 1) <= band + 1e-9
    if err is not None: ax.errorbar(r, y, xerr=np.asarray(err)[o], fmt="none", ecolor=ps.MODEL, elinewidth=0.7, zorder=2)
    ax.scatter(r[ok], y[ok], s=s, color=ps.MODEL, zorder=3, lw=0)
    ax.scatter(r[~ok], y[~ok], s=s, facecolor="white", edgecolor=ps.MODEL, lw=1.0, zorder=3)
    ax.set_ylim(-0.7, len(r) - 0.3); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0)
    if show_names: ax.set_yticks(y); ax.set_yticklabels(names)
    else: ax.set_yticks([])
    if xlim: ax.set_xlim(*xlim)
    if log and ticks: plain_log(ax.xaxis, ticks)
    return names


# ---- attribute bins in plain words (composition).  For two-category attributes only one category is shown (the other mirrors it).
INC = ["under \\$25k", "\\$25–50k", "\\$50–75k", "\\$75–100k", "\\$100–150k", "\\$150k or more"]
INC_SHORT = ["Under 25", "25–50", "50–75", "75–100", "100–150", "150+"]
BINS = {"age band": ("Age (years)", {"0": "0–17", "1": "18–34", "2": "35–64", "3": "65+"}, "Aged {}"),
        "sex": ("Sex", {"2": "Female"}, "{}"),
        "employed (16+)": ("Employed", {"1": "Employed (16+)"}, "{}"),
        "household size": ("Household size (persons)", {"1": "1", "2": "2", "3": "3", "4": "4", "5": "5+"}, "{}-person household"),
        "autos": ("Cars", {"0": "0", "1": "1", "2": "2", "3": "3+"}, "{} cars"),
        "cars": ("Cars", {"0": "0", "1": "1", "2": "2", "3": "3+"}, "{} cars"),
        "income class": ("Household income ($1,000)", dict(zip("012345", INC_SHORT)), "Income {}"),
        "income class (2016 $)": ("Household income ($1,000)", dict(zip("012345", INC_SHORT)), "Income {}"),
        "adults 18-34 living with parents": ("Living with parents", {"1": "With parents (18–34)"}, "Living with parents (18–34)")}


def bin_rows(B, tablekey="table"):
    """[(table, bin, long label, short label, group)] in the table order of the data, plain words."""
    rows = []
    for t in B[tablekey].unique():
        g, lab, fmt = BINS[t]; g = g.replace("$", "\\$")
        for b in dict.fromkeys(B[B[tablekey] == t]["bin"].astype(str)):
            if b in lab:
                s = lab[b]; L = fmt.format(s)
                L = {"0 cars": "No car", "1 cars": "1 car", "5+-person household": "5+ person household"}.get(L, L)
                if L.startswith("Income "): L = "Income " + dict(zip(INC_SHORT, INC))[s]
                rows.append((t, b, L, s, g))
    return rows


def strip_pp(ax, B, rowkey, tablekey="table", tol=5):
    """Composition: one row per attribute bin, one mark per area (model minus observed share, pp); tolerance band +-tol."""
    rows = bin_rows(B, tablekey); n = len(rows); B = B.assign(_b=B["bin"].astype(str))
    ax.axvspan(-tol, tol, color=ps.TOL_BAND, lw=0, zorder=0); ax.axvline(0, color=ps.INK2, lw=0.7, zorder=1)
    lim = max(10, np.ceil(B.diff_pp.abs().max() + 1))
    prev = None
    for i, (t, b, L, s, g) in enumerate(rows):
        y = n - 1 - i; v = B[(B[tablekey] == t) & (B._b == b)].diff_pp.values; ok = np.abs(v) <= tol
        ax.scatter(v[ok], np.full(ok.sum(), y), marker="|", s=28, lw=0.8, color=ps.MODEL, alpha=0.55, zorder=3)
        ax.scatter(v[~ok], np.full((~ok).sum(), y), s=16, facecolor="white", edgecolor=ps.MODEL, lw=1.0, zorder=4)
        if prev is not None and g != prev: ax.axhline(y + 0.5, color=ps.AXIS, lw=0.6, zorder=1)
        prev = g
    ax.set_yticks(range(n)); ax.set_yticklabels([r[2] for r in rows][::-1]); ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlim(-lim, lim); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0)
    ax.set_xlabel(ps.PP_LABEL)
    return rows


def heat_groups(ax, H, rows, row_labels=None, annotate=5, outline=False, fmt="{:+.0f}", top_groups=True):
    """Diverging heatmap of model minus observed (pp) on -PP_LIM..+PP_LIM; columns = attribute bins grouped by attribute
    (white separators, attribute names on top); only cells beyond +-annotate are labelled (or outlined)."""
    ax.grid(False); im = ax.imshow(np.clip(H, -ps.PP_LIM, ps.PP_LIM), cmap=ps.DIV, vmin=-ps.PP_LIM, vmax=ps.PP_LIM, aspect="auto", interpolation="nearest")
    groups = []
    for j, r in enumerate(rows):
        if groups and groups[-1][0] == r[4]: groups[-1][2] = j
        else: groups.append([r[4], j, j])
    for g, a, b in groups[1:]: ax.axvline(a - 0.5, color="white", lw=2.0)
    ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[3] for r in rows], rotation=45, ha="right", rotation_mode="anchor")
    if top_groups:
        sec = ax.secondary_xaxis("top"); multi = [(g, a, b) for g, a, b in groups if b > a]
        sec.set_xticks([(a + b) / 2 for g, a, b in multi]); sec.set_xticklabels([g.replace(" (", "\n(") for g, a, b in multi], fontsize=ps.FONT)
        sec.tick_params(length=0, pad=1); sec.spines["top"].set_visible(False)
    if row_labels is not None: ax.set_yticks(range(H.shape[0])); ax.set_yticklabels(row_labels)
    else: ax.set_yticks([])
    ax.tick_params(length=0)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            v = H[i, j]
            if np.isfinite(v) and abs(v) > annotate:
                if outline: ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=ps.INK, lw=0.8))
                else: ax.text(j, i, fmt.format(v).replace("-", "−"), ha="center", va="center", fontsize=ps.FONT, color="white" if abs(v) > 6 else ps.INK)
    return im


def pp_colorbar(fig, im, ax, orientation="vertical", label=ps.PP_LABEL, **kw):
    cb = fig.colorbar(im, ax=ax, ticks=[-10, -5, 0, 5, 10], orientation=orientation, **kw); cb.set_label(label); cb.outline.set_visible(False)
    cb.ax.tick_params(length=2)
    return cb


def ratio_heat(ax, H, row_labels, col_labels, tol, fmt="{:.2f}"):
    """Ratio heatmap in the shared RATIO classes; only cells beyond 1 +- tol are labelled."""
    ax.grid(False)
    ax.imshow(np.clip(H, 0.31, 1.69), cmap=ListedColormap(ps.RATIO_COLORS), norm=BoundaryNorm([0.3, 0.5, 0.75, 0.9, 1.1, 1.25, 1.5, 1.7], 7), aspect="auto")
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            v = H[i, j]
            if np.isfinite(v) and abs(v - 1) > tol + 1e-9:
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=ps.FONT, color=ps.INK if ps.ratio_color(v) in ("#86b6ef", "#e8e7e1", "#f0a09f") else "white")
    ax.set_yticks(range(len(row_labels))); ax.set_yticklabels(row_labels); ax.set_xticks(range(len(col_labels))); ax.set_xticklabels(col_labels)
    ax.tick_params(length=0)


def ratio_legend(fig, ncol=4, nodata=False, loc="outside lower center", title=None):
    return fig.legend(handles=ps.ratio_class_handles(nodata), loc=loc, ncol=ncol, title=title, handlelength=1.4, handleheight=1.0)


def settings_direct_labels(ax, ys, xs, labels):
    """Direct labels for the three settings, written to the right of the markers of one row."""
    for y, x, l in zip(ys, xs, labels):
        ax.text(x, y, l, va="center", ha="left", fontsize=ps.FONT, color=ps.INK2, path_effects=HALO)


# ================================================================================================ stage 1: population synthesis
class Stage1:
    def __init__(self):
        self.R = pd.read_parquet(f"{DATA}/stage1_validation.parquet")
        self.J = json.load(open(f"{VAE_HOME}/outputs/07_validation/full/results.json"))
        self.W = pd.read_csv(f"{DATA}/stage1_workplace_check.csv").rename(columns={"Unnamed: 0": "county"})
        self.C = self.commute_curves()

    # ---- data
    def persons(self):
        A = self.R[(self.R.section == "A counts") & self.R.table.str.startswith("persons")].copy(); A["county"] = A.geo.astype(int); A["name"] = A.county.map(NAMES)
        return A.sort_values("ratio")

    def households_puma(self):
        H = self.R[(self.R.section == "A counts") & self.R.table.str.startswith("households")].copy(); H["puma"] = H.geo.str.replace("PUMA ", "").astype(int)
        return H

    def comp(self):
        B = self.R[self.R.section == "B composition"].copy(); B["puma"] = B.geo.str.replace("PUMA ", "").astype(int); return B

    def commute_curves(self):
        """Commute time (5-min bins) and distance of the synthetic workers (AM-peak skims) and of the reported home-work car-driver
        trips of the 2017/18 RTS (weighted); cached in data/stage1_commute_curves.csv."""
        f = f"{DATA}/stage1_commute_curves.csv"
        if os.path.exists(f): return pd.read_csv(f, dtype={"bin": str})
        import h5py
        h = h5py.File(f"{ABIT_HOME}/input/mito_los/skims/traveltime_auto.omx", "r"); T = h["data/mat1"][:]; ids = h["lookup/destinations"][:]; idx = {int(z): i for i, z in enumerate(ids)}
        Dk = h5py.File(f"{ABIT_HOME}/input/mito_los/skims/distance_auto.omx", "r")["data/mat1"][:] / 1000.0
        jj = pd.read_parquet(f"{V}/1_vae/vae_outputs/05_workplace/jj.parquet", columns=["personId", "zone"])
        pp = pd.read_parquet(f"{V}/1_vae/output/pp.parquet", columns=["pp_id", "hh_id"]); hh = pd.read_parquet(f"{V}/1_vae/output/hh.parquet", columns=["hh_id", "zone_id"])
        w = jj.merge(pp, left_on="personId", right_on="pp_id").merge(hh, on="hh_id"); del pp, hh, jj
        w = w[w.zone_id.isin(idx) & w.zone.isin(idx)]; i, j = w.zone_id.map(idx).values, w.zone.map(idx).values
        t, km = T[i, j], Dk[i, j]; del T, Dk
        r = pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv", low_memory=False, usecols=["o_activity", "d_activity", "travel_mode", "reported_travel_time", "distance", "wttrdfin"])
        r = r[(r.travel_mode == 4) & (((r.o_activity == 1) & (r.d_activity == 2)) | ((r.o_activity == 2) & (r.d_activity == 1)))]
        rt = r[r.reported_travel_time.between(1, 180)]; rd = r[r.distance.between(0.2, 120)]
        tb = np.arange(0, 125, 5)
        def tpmf(x, wt=None):
            s = pd.Series(1.0 if wt is None else wt, index=range(len(x))).groupby((np.clip(np.asarray(x), 0, 119.99) // 5 * 5).astype(int)).sum()
            return (s / s.sum()).reindex(tb[:-1], fill_value=0).values
        rows = [dict(quantity="time", bin=str(b), model=m, observed=o) for b, m, o in zip(tb[:-1], tpmf(t), tpmf(rt.reported_travel_time.values, rt.wttrdfin.values))]
        rows += [dict(quantity="distance", bin=b, model=m, observed=o) for b, m, o in zip(DIST_LABELS, dist_pmf(km), dist_pmf(rd.distance.values * 1.609344, rd.wttrdfin.values))]
        rows += [dict(quantity="mean_min", bin="", model=float(np.mean(t)), observed=float(np.average(rt.reported_travel_time, weights=rt.wttrdfin))),
                 dict(quantity="mean_km", bin="", model=float(np.mean(km)), observed=float(np.average(rd.distance * 1.609344, weights=rd.wttrdfin)))]
        pd.DataFrame(rows).to_csv(f, index=False); return pd.read_csv(f, dtype={"bin": str})

    # ---- panels
    def p_persons(self, ax):
        A = self.persons(); dot_chart(ax, A.name.values, A.ratio.values, band=0.05, center=0.977, label="Persons in households,\nmodel ÷ observed (–)", xlim=(0.75, 1.08))
        ax.set_ylim(-0.7, len(A) + 0.9); ax.text(0.977, len(A) - 0.2, "Expected 0.977", ha="center", va="bottom", fontsize=ps.FONT, color=ps.INK2, path_effects=HALO)

    def p_comp(self, ax):
        strip_pp(ax, self.comp(), "puma")

    def p_joint(self, ax):
        J = self.J
        rows = [("Persons, single attributes", J["3_joints_pp"]["1way_mean_srmse"]), ("Persons, pairs", J["3_joints_pp"]["2way_mean_srmse"]),
                ("Persons, triples", J["3_joints_pp"]["3way_mean_srmse"]), ("Households, single attributes", J["3_joints_hh"]["1way_mean_srmse"]),
                ("Households, pairs", J["3_joints_hh"]["2way_mean_srmse"])]
        y = np.array([5.4, 4.4, 3.4, 1.0, 0.0])
        ax.barh(y, [v for _, v in rows], color=ps.MODEL, height=0.7)
        ax.set_yticks(y); ax.set_yticklabels([l for l, _ in rows]); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0)
        ax.set_xlabel("Standardised root-mean-square error\nagainst held-out households (–)"); ax.set_xlim(0, 0.25)

    def p_dist(self, ax):
        d = self.C[self.C.quantity == "distance"]; x = np.arange(len(d))
        ax.plot(x, d.observed * 100, color=ps.OBSERVED, marker="s", ms=3.4); ax.plot(x, d.model * 100, color=ps.MODEL, marker="o", ms=3.4)
        dist_axis(ax, "Commute distance (km)"); ax.set_ylabel("Share of commuters (%)"); ax.set_ylim(0, 20)

    # ---- figures
    def main(self):
        fig = ps.new_figure(5.9); gs = fig.add_gridspec(2, 1, height_ratios=[3.3, 2.0]); r1 = gs[0].subgridspec(1, 2, width_ratios=[1, 1.08]); r2 = gs[1].subgridspec(1, 2, width_ratios=[1, 1.1])
        ax = {"a": fig.add_subplot(r1[0]), "b": fig.add_subplot(r1[1]), "c": fig.add_subplot(r2[0]), "d": fig.add_subplot(r2[1])}
        self.p_persons(ax["a"]); self.p_comp(ax["b"]); self.p_joint(ax["c"]); self.p_dist(ax["d"])
        fig_legend(fig, ["model", "observed", "tol", "outside"])
        p = save(fig, "fig_v1_main", ax)
        for k, d in zip("abcd", ["stage1_validation.parquet (A counts)", "stage1_validation.parquet (B composition)", "VAE_HOME/outputs/07_validation/full/results.json",
                                  "stage1_commute_curves.csv"]):
            record(1, {"a": "a", "b": "b", "c": "b (joint)", "d": "e"}[k], f"{p} ({k})", d, f"Stage1.main ({k})", "see paper caption")
        return p

    def app_a(self):
        fig = ps.new_figure(3.9); gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.15]); a = fig.add_subplot(gs[0]); b = fig.add_subplot(gs[1])
        H = self.households_puma(); dot_chart(a, H.geo.values, H.ratio.values, band=0.05, show_names=False, s=14, label="Households, model ÷ observed (–)", xlim=(0.93, 1.07))
        a.set_ylabel("Census microdata areas (44),\nsorted by ratio")
        D = self.R[self.R.section == "D jobs"].copy(); D["name"] = D.geo.astype(int).map(NAMES)
        dot_chart(b, D.name.values, D.ratio.values, band=0.10, label="Filled jobs, model ÷ observed (–)", xlim=(0.85, 1.35))
        fig_legend(fig, ["model_dot", "tol", "outside"])
        p = save(fig, "fig_v1_a", {"a": a, "b": b})
        record(1, "a", p, "stage1_validation.parquet (A counts, D jobs)", "Stage1.app_a", "see paper caption")

    def app_b(self, height=6.4, name="fig_v1_b"):
        fig = ps.new_figure(height); gs = fig.add_gridspec(2, 2, height_ratios=[3.9, 1.5])
        a = fig.add_subplot(gs[0, :]); B = self.comp(); rows = bin_rows(B)
        hh = self.households_puma().set_index("puma").observed.sort_values(ascending=False)
        B["_b"] = B["bin"].astype(str); H = np.array([[B[(B.puma == p) & (B.table == t) & (B._b == b)].diff_pp.iloc[0] for t, b, *_ in rows] for p in hh.index])
        im = heat_groups(a, H, rows, annotate=5, outline=True); a.set_ylabel("Census microdata areas (44),\nlargest at the top")
        pp_colorbar(fig, im, a, fraction=0.04, pad=0.02, aspect=25)
        J = self.R[self.R.section == "C joint"].copy(); out = {"a": a}
        for k, (tab, rl, ylab) in enumerate([("size x autos", ["1", "2", "3", "4+"], "Household size\n(persons)"), ("income x autos", ["<25", "25–50", "50–100", "100+"], "Household income\n(\\$1,000)")]):
            ax = fig.add_subplot(gs[1, k]); d = J[J.table == tab].copy(); d[["r", "c"]] = d["bin"].str.strip("()").str.split(",", expand=True).astype(int)
            M = d.pivot(index="r", columns="c", values="diff_pp"); ax.grid(False)
            im = ax.imshow(M.values, cmap=ps.DIV, vmin=-ps.PP_LIM, vmax=ps.PP_LIM, aspect="auto")
            ax.set_yticks(range(M.shape[0])); ax.set_yticklabels(rl[:M.shape[0]]); ax.set_xticks(range(M.shape[1])); ax.set_xticklabels(["0", "1", "2", "3+"][:M.shape[1]])
            ax.set_xlabel("Cars"); ax.set_ylabel(ylab); ax.tick_params(length=0); out["bc"[k]] = ax
        p = save(fig, name, out)
        record(1, "b", p, "stage1_validation.parquet (B composition, C joint)", "Stage1.app_b", "see paper caption")

    def app_d(self):
        J = self.J; hh = J["2_marginals_hh"]; pp = J["2_marginals_pp"]; fl = J["12_identifiability_floor_hh"]
        lab = {"dwellingType": "dwelling type", "tenure": "tenure", "autos": "cars", "income_bin": "income", "age_bin": "age", "gender": "sex", "race": "race",
               "occupation": "occupation", "driversLicense": "driving licence", "relationship": "relationship", "nationality": "nationality"}
        fig = ps.new_figure(5.6); gs = fig.add_gridspec(2, 1, height_ratios=[1.35, 1]); ax = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1])
        names = [f"Households: {lab[k]}" for k in hh] + [f"Persons: {lab[k]}" for k in pp]; tv = [hh[k]["tv"] for k in hh] + [pp[k]["tv"] for k in pp]
        sr = [hh[k]["srmse"] for k in hh] + [pp[k]["srmse"] for k in pp]; y = np.arange(len(names))[::-1]; h = 0.38
        ax.barh(y + h / 2, tv, h, color=ps.MODEL, label="Total-variation distance"); ax.barh(y - h / 2, sr, h, color=ps.SEED_BAND, edgecolor=ps.MODEL, lw=0.5, label="Standardised root-mean-square error")
        ax.scatter([fl[k] for k in hh], [y[i] - h / 2 for i, k in enumerate(hh)], marker="|", s=60, lw=1.4, color=ps.OBSERVED, zorder=4, label="Sampling floor")
        ax.set_yticks(y); ax.set_yticklabels(names); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0)
        ax.set_xlabel("Distance to the held-out households (–)"); fig.legend(*ax.get_legend_handles_labels(), loc="outside upper center", ncol=3)
        W = J["3_joints_pp"]["worst_pairs"] + J["3_joints_hh"]["worst_pairs"]
        def nm(p_, i):
            p_ = p_.replace("_bin", "").replace("×", " × ").replace("dwellingType", "dwelling type").replace("autos", "cars").replace("driversLicense", "driving licence")
            return ("Households: " if i >= 5 else "Persons: ") + p_
        y2 = np.arange(len(W))[::-1]; ax2.barh(y2, [v for _, v in W], color=ps.MODEL, height=0.65)
        ax2.set_yticks(y2); ax2.set_yticklabels([nm(p_, i) for i, (p_, _) in enumerate(W)]); ax2.grid(axis="y", visible=False); ax2.tick_params(axis="y", length=0)
        ax2.set_xlabel("Standardised root-mean-square error (–)")
        p = save(fig, "fig_v1_d", {"a": ax, "b": ax2})
        record(1, "b (joint)", p, "VAE_HOME/outputs/07_validation/full/results.json", "Stage1.app_d", "see paper caption")

    def app_e(self):
        fig = ps.new_figure(2.5); gs = fig.add_gridspec(1, 3); a, b, c = [fig.add_subplot(gs[i]) for i in range(3)]
        t = self.C[self.C.quantity == "time"]; x = t.bin.astype(int).values + 2.5
        a.plot(x, t.observed * 100, color=ps.OBSERVED, marker="s", ms=2.6, lw=1.2); a.plot(x, t.model * 100, color=ps.MODEL, marker="o", ms=2.6, lw=1.2)
        a.set_xlabel("Commute time (min)"); a.set_ylabel("Share of commuters (%)"); a.set_xlim(0, 120); a.set_xticks([0, 30, 60, 90, 120]); a.set_ylim(0, 16); a.set_yticks([0, 5, 10, 15])
        xt = np.r_[0, t.bin.astype(int).values + 5]
        b.plot(xt, np.r_[0, t.observed.cumsum()] * 100, color=ps.OBSERVED, lw=1.4); b.plot(xt, np.r_[0, t.model.cumsum()] * 100, color=ps.MODEL, lw=1.4)
        b.set_xlabel("Commute time (min)"); b.set_ylabel("Cumulative share (%)"); b.set_xlim(0, 120); b.set_xticks([0, 30, 60, 90, 120]); b.set_ylim(0, 101)
        d = self.C[self.C.quantity == "distance"]; e = np.array(DIST_EDGES[:-1])          # up to 50 km; the rest is the open band 50+
        c.plot(e, np.r_[0, d.observed.cumsum().values[:-1]] * 100, color=ps.OBSERVED, lw=1.4, marker="s", ms=2.6); c.plot(e, np.r_[0, d.model.cumsum().values[:-1]] * 100, color=ps.MODEL, lw=1.4, marker="o", ms=2.6)
        c.set_xlabel("Commute distance (km)"); c.set_ylabel("Cumulative share (%)"); c.set_xlim(0, 52); c.set_xticks([0, 10, 20, 30, 40, 50]); c.set_ylim(0, 101)
        fig_legend(fig, ["model", "observed"])
        p = save(fig, "fig_v1_e", {"a": a, "b": b, "c": c})
        record(1, "e", p, "stage1_commute_curves.csv; stage1_workplace_check.csv", "Stage1.app_e", "see paper caption")

    def levels(self):
        """Article figure of the levels (no panel shared with fig_v1_b or fig_v1_d): (a) persons by county, (b) filled jobs by county,
        (c) households by PUMA, (d) commute distance.  Same data and panel functions as fig_v1_main (a, d) and fig_v1_a (a, b)."""
        fig = ps.new_figure(5.5); gs = fig.add_gridspec(2, 2, height_ratios=[3.3, 1.9], width_ratios=[1, 1.08])
        ax = {"a": fig.add_subplot(gs[0, 0]), "b": fig.add_subplot(gs[0, 1]), "c": fig.add_subplot(gs[1, 0]), "d": fig.add_subplot(gs[1, 1])}
        self.p_persons(ax["a"])
        D = self.R[self.R.section == "D jobs"].copy(); D["name"] = D.geo.astype(int).map(NAMES)
        dot_chart(ax["b"], D.name.values, D.ratio.values, band=0.10, label="Filled jobs,\nmodel ÷ observed (–)", xlim=(0.85, 1.35))
        H = self.households_puma(); dot_chart(ax["c"], H.geo.values, H.ratio.values, band=0.05, show_names=False, s=10, label="Households, model ÷ observed (–)", xlim=(0.93, 1.07))
        ax["c"].set_ylabel("Census microdata\nareas (44), sorted")
        self.p_dist(ax["d"])
        fig_legend(fig, ["model", "observed", "tol", "outside"])
        p = save(fig, "fig_v1_levels", ax)
        record(1, "a", p, "stage1_validation.parquet (A counts, D jobs); stage1_commute_curves.csv", "Stage1.levels", "see article caption")
        return p

    def run(self):
        self.main(); self.app_a(); self.app_b(); self.app_d(); self.app_e(); self.levels(); self.app_b(5.5, "fig_v1_comp")


# ================================================================================================ stage 2: land use
EVENTS = [("Births", "births per woman 15-50", "Maryland", "Births per 100\nwomen aged 15–50"), ("Marriages", "new marriages share of adults", "Maryland", "Persons marrying\nper 100 adults"),
          ("Divorces", "divorces share of married", "Maryland", "Persons divorcing per\n100 married persons"),
          ("Deaths", "deaths share of persons (engine events; observed: Maryland)", "all regions", "Deaths per\n100 persons"),
          ("Moves", "persons who moved share (persons aged 1+)", "Maryland", "Persons who moved\nper 100 persons")]


class Stage2:
    def __init__(self, scen="calib_r16", window=None):
        self.scen = scen; self.R = pd.read_parquet(f"{DATA}/silo_validation_{scen}.parquet"); self.R["tbl"] = self.R.table.str.replace(r" \[PUMS \d+\]", "", regex=True)
        self.has_sd = "seed_sd" in self.R and self.R.seed_sd.notna().any(); self.nseeds = int(self.R.n_seeds.max()) if "n_seeds" in self.R else 1
        if window: w0, w1 = map(int, window.split("-"))
        else: w0, w1 = (2021, 2024) if scen.startswith("oos") else (2017, 2020)
        w1 = min(w1, int(self.R.year.max())); self.win = list(range(w0, w1 + 1)); self.yl = w1; self.wlab = f"{w0}–{w1}"
        self.md = self.R.geo.astype(str).str.match(r"^24\d{3}$")

    def ev(self, table, geo):
        return self.R[(self.R.section == "C events") & (self.R.table == table) & (self.R.geo == geo)].sort_values("year")

    def comp(self, year):
        B = self.R[(self.R.section == "B composition") & (self.R.year == year) & self.md].copy(); B["county"] = B.geo.astype(int); B["name"] = B.county.map(NAMES); return B

    def pop(self):
        A = self.R[(self.R.section == "A totals") & self.md].copy(); A["county"] = A.geo.astype(int); A["name"] = A.county.map(NAMES); return A

    def by_size(self):
        """Maryland counties, largest population (observed, last year) first."""
        P = self.pop(); return P[P.year == self.yl].sort_values("observed", ascending=False).county.tolist()

    def constr(self):
        D = self.R[(self.R.section == "D2 construction") & self.md & self.R.year.isin(self.win)].groupby("geo")[["model", "observed"]].sum(); D.index = D.index.astype(int)
        D["ratio"] = D.model / D.observed; D["name"] = D.index.map(NAMES); return D

    def jobs(self, year):
        J = self.R[(self.R.section == "D jobs") & self.md & (self.R.year == year)].copy(); J["county"] = J.geo.astype(int); return J

    def median_share(self, tbl, b):
        yrs = sorted(self.R[self.R.section == "B composition"].year.unique())
        return pd.DataFrame([self.comp(y).query("tbl == @tbl and bin.astype('str') == @b", engine="python")[["model", "observed"]].median() * 100 for y in yrs], index=yrs)

    # ---- panels
    def p_events(self, ax):
        ps.ratio_axis(ax, band=0.05, orient="y", label="Event rate, model ÷ observed (–)"); n = len(self.win); off = (np.arange(n) - (n - 1) / 2) * 0.17
        for i, (lab, tab, geo, _) in enumerate(EVENTS):
            d = self.ev(tab, geo); d = d[d.year.isin(self.win)]; x = i + off[:len(d)]
            if self.has_sd: ax.errorbar(x, d.ratio, yerr=2 * d.seed_sd / d.observed, fmt="none", ecolor=ps.MODEL, elinewidth=0.7, zorder=3)
            ok = ((d.ratio - 1).abs() <= 0.05).values
            ax.scatter(x[ok], d.ratio[ok], s=18, color=ps.MODEL, zorder=4, lw=0); ax.scatter(x[~ok], d.ratio[~ok], s=18, facecolor="white", edgecolor=ps.MODEL, lw=1.0, zorder=4)
            m = d.model.sum() / d.observed.sum(); ax.plot([i - 0.36, i + 0.36], [m, m], color=ps.INK, lw=1.2, zorder=5)
        ax.set_xticks(range(len(EVENTS))); ax.set_xticklabels([e[0] for e in EVENTS], rotation=30, ha="right", rotation_mode="anchor")
        ax.grid(axis="x", visible=False); ax.set_xlim(-0.6, len(EVENTS) - 0.4); ax.set_ylim(0.6, 1.58); ax.set_yticks([0.6, 0.8, 1.0, 1.2, 1.4])
        ax.legend(handles=[Line2D([], [], marker="o", ls="", color=ps.MODEL, ms=4.5, label=f"Single year, {self.wlab}\n(left to right)"),
                           Line2D([], [], color=ps.INK, lw=1.2, label=f"Mean {self.wlab}")], loc="upper left", borderaxespad=0.2)

    def p_comp(self, ax):
        strip_pp(ax, self.comp(self.yl), "county", "tbl")

    def p_constr(self, ax):
        D = self.constr(); dot_chart(ax, D.name.values, D.ratio.values, band=0.10, log=True, label=f"New dwellings {self.wlab},\nmodel ÷ observed (–)",
                                     xlim=(0.012, 9), ticks=[0.03, 0.1, 0.3, 1, 3])

    def p_shares(self, ax):
        for (tbl, b, lab, ls) in [("household size", "1", "One-person households", "-"), ("income class (2016 $)", "0", "Income under \\$25,000", "--")]:
            md = self.median_share(tbl, b)
            ax.plot(md.index, md.observed, color=ps.OBSERVED, ls=ls, marker="s", ms=3.4); ax.plot(md.index, md.model, color=ps.MODEL, ls=ls, marker="o", ms=3.4)
            y0 = md.values.max() + 1.2 if ls == "-" else md.iloc[:3].values.min() - 1.0
            ax.text(md.index[0], y0, lab, ha="left", va="bottom" if ls == "-" else "top", fontsize=ps.FONT, color=ps.INK2)
        yrs = sorted(self.R[self.R.section == "B composition"].year.unique())
        ax.set_ylabel("Share of households,\ncounty median (%)"); ax.set_xlabel("Year"); ax.set_ylim(10, 36); ax.set_xticks(yrs[::2] if len(yrs) > 6 else yrs)
        ax.set_xlim(min(yrs) - 0.3, max(yrs) + 0.3)

    def main(self):
        # columns of unequal split: the two panels with 22-24 labelled rows, (b) and (c), get the larger share of the height
        fig = ps.new_figure(6.1); gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.15])
        L = gs[0].subgridspec(2, 1, height_ratios=[2.15, 3.85]); Rr = gs[1].subgridspec(2, 1, height_ratios=[3.75, 2.25])
        ax = {"a": fig.add_subplot(L[0]), "b": fig.add_subplot(Rr[0]), "c": fig.add_subplot(L[1]), "d": fig.add_subplot(Rr[1])}
        self.p_events(ax["a"]); self.p_comp(ax["b"]); self.p_constr(ax["c"]); self.p_shares(ax["d"])
        fig_legend(fig, ["model", "observed"] + (["seed"] if self.has_sd else []) + ["tol", "outside"])
        p = save(fig, "fig_v2_main", ax)
        for k, dim, d in [("a", "a", "C events"), ("b", "b", "B composition"), ("c", "c", "D2 construction"), ("d", "d", "B composition")]:
            record(2, dim, f"{p} ({k})", f"silo_validation_{self.scen}.parquet ({d})", f"Stage2.main ({k})", "see paper caption")
        return p

    def app_a(self):
        fig = ps.new_figure(4.6); gs = fig.add_gridspec(2, 3); out = {}
        for i, (lab, tab, geo, ylab) in enumerate(EVENTS):
            ax = fig.add_subplot(gs[i // 3, i % 3]); d = self.ev(tab, geo)
            if self.has_sd: ax.fill_between(d.year, (d.model - 2 * d.seed_sd) * 100, (d.model + 2 * d.seed_sd) * 100, color=ps.SEED_BAND, lw=0)
            ax.fill_between(d.year, d.observed * 95, d.observed * 105, color=ps.TOL_BAND, lw=0, zorder=0)
            ax.plot(d.year, d.observed * 100, color=ps.OBSERVED, marker="s", ms=3.2); ax.plot(d.year, d.model * 100, color=ps.MODEL, marker="o", ms=3.2)
            ax.set_xticks(d.year.values[::2] if len(d) > 5 else d.year.values); ax.set_xlim(d.year.min() - 0.3, d.year.max() + 0.3)
            ax.set_ylim(0, max(d.model.max(), d.observed.max()) * 100 * 1.35); ax.set_ylabel(ylab); ax.set_xlabel("Year"); out["abcde"[i]] = ax
        lg = fig.add_subplot(gs[1, 2]); lg.set_axis_off()
        lg.legend(handles=[H_("model"), H_("observed")] + ([H_("seed")] if self.has_sd else []) + [H_("tol", "±5 %")], loc="center")
        p = save(fig, "fig_v2_a", out)
        record(2, "a", p, f"silo_validation_{self.scen}.parquet (C events)", "Stage2.app_a", "see paper caption")
        if self.scen.startswith("oos") or not os.path.exists(f"{V}/2_silo/calibration/calibration_log.csv"): return
        fig = ps.new_figure(2.7); ax = fig.add_subplot(111); L = pd.read_csv(f"{V}/2_silo/calibration/calibration_log.csv"); L = L[L.ratio.notna()]
        NM = {"births": "Births", "marriages": "Marriages", "divorces": "Divorces", "moves": "Household moves", "construction": "New dwellings",
              "leaveParents": "Leaving the parental home", "employed": "Employed share"}
        ps.ratio_axis(ax, band=0.05, label=RLAB)
        for j, (comp, name) in enumerate(NM.items()):
            d = L[L.component == comp].sort_values("round")
            if len(d): ax.plot(d["round"], d.ratio, color=ps.CAT[j], marker="o", ms=3, lw=1.2, label=name)
        ax.set_xlabel("Calibration round (each a 2016–2020 run)"); ax.set_xticks(sorted(L["round"].unique())); ax.set_ylim(0.4, max(1.5, L.ratio.max() * 1.05))
        h, l = ax.get_legend_handles_labels(); ax.legend(h + [H_("tol", "±5 %")], l + [ps.tol_label("±5 %")], loc="center left", bbox_to_anchor=(1.01, 0.5))
        p = save(fig, "fig_v2_a2")
        record(2, "a", p, "2_silo/calibration/calibration_log.csv", "Stage2.app_a (a2)", "see paper caption")

    def app_b(self):
        fig = ps.new_figure(5.4); ax = fig.add_subplot(111); B = self.comp(self.yl); rows = bin_rows(B, "tbl"); B["_b"] = B["bin"].astype(str); order = self.by_size()
        H = np.array([[B[(B.county == c) & (B.tbl == t) & (B._b == b)].diff_pp.iloc[0] for t, b, *_ in rows] for c in order])
        im = heat_groups(ax, H, rows, row_labels=[NAMES[c] for c in order], annotate=5)
        pp_colorbar(fig, im, ax, orientation="horizontal", label=ps.PP_LABEL.replace("\n", " "), fraction=0.03, pad=0.01, aspect=50, shrink=0.6)
        p = save(fig, "fig_v2_b")
        record(2, "b", p, f"silo_validation_{self.scen}.parquet (B composition)", "Stage2.app_b", "see paper caption")

    # label centres of the construction map (km, EPSG:26918); a leader line is drawn when the label sits outside its county
    MAPLAB = {"Garrett": (138, 4381), "Allegany": (186, 4392), "Washington": (250, 4385), "Frederick": (292, 4366), "Carroll": (328, 4391),
              "Baltimore County": (352, 4417), "Harford": (385, 4372), "Cecil": (420, 4389), "Baltimore City": (402, 4351), "Howard": (327, 4347),
              "Montgomery": (305, 4333), "Anne Arundel": (357, 4317), "Prince George's": (330, 4295), "Charles": (318, 4261), "Calvert": (368, 4270),
              "St Mary's": (358, 4228), "Kent": (408, 4340), "Queen Anne's": (416, 4325), "Talbot": (399, 4290), "Caroline": (431, 4307),
              "Dorchester": (404, 4246), "Wicomico": (459, 4257), "Somerset": (429, 4210), "Worcester": (479, 4233)}

    def app_c(self):
        fig = ps.new_figure(3.75); ax = fig.add_subplot(111); g = md_counties(); D = self.constr()
        ps.choropleth(ax, g, D.ratio); ax.set_xlim(108e3, 506e3); ax.set_ylim(4188e3, 4424e3)
        rp = g.representative_point()
        for c in g.index:
            nm = NAMES[c]; r = D.ratio.get(c, np.nan)
            if not np.isfinite(r) or abs(r - 1) <= 0.10: continue          # label the counties outside the tolerance
            tx, ty = (v * 1e3 for v in self.MAPLAB[nm]); px, py = rp[c].x, rp[c].y
            if not g.loc[[c]].contains(__import__("shapely").geometry.Point(tx, ty)).iloc[0]: ax.plot([px, tx], [py, ty], color=ps.INK2, lw=0.6, zorder=5)
            ax.text(tx, ty, nm, ha="center", va="center", fontsize=ps.FONT, color=ps.INK, path_effects=HALO, zorder=6)
        ratio_legend(fig, ncol=4)
        p = save(fig, "fig_v2_c")
        record(2, "c", p, f"silo_validation_{self.scen}.parquet (D2 construction); zone_counties.gpkg", "Stage2.app_c", "see paper caption")

    def app_d(self):
        fig = ps.new_figure(4.7); gs = fig.add_gridspec(1, 2); order = self.by_size(); out = {}
        P = self.pop(); J = self.R[(self.R.section == "D jobs") & self.md].groupby(["geo", "year"])[["model", "observed"]].sum().reset_index()
        J["ratio"] = J.model / J.observed; J["county"] = J.geo.astype(int)
        for k, (D, tol, xl, fm) in enumerate([(P, 0.02, "Population, by year", "{:.3f}"), (J, 0.10, "Jobs, by year", "{:.2f}")]):
            ax = fig.add_subplot(gs[k]); M = D.pivot_table(index="county", columns="year", values="ratio").reindex(order)
            M = M[[y for y in M.columns if y == M.columns.min() or y in self.win]]          # base year and the comparison window
            ratio_heat(ax, M.values, [NAMES[c] for c in order] if k == 0 else [""] * len(order), [str(y) for y in M.columns], tol, fmt=fm)
            ax.set_xticklabels([str(y) for y in M.columns], rotation=45, ha="right", rotation_mode="anchor"); ax.set_xlabel(xl)
            if k == 1: ax.set_yticks([])
            out["ab"[k]] = ax
        ratio_legend(fig, ncol=4)
        p = save(fig, "fig_v2_d", out)
        record(2, "d", p, f"silo_validation_{self.scen}.parquet (A totals, D jobs)", "Stage2.app_d", "see paper caption")
        fig = ps.new_figure(4.0); gs = fig.add_gridspec(2, 2); out = {}
        SH = [("cars", "0", "Households with no car"), ("employed (16+)", "1", "Employed, aged 16 and over"), ("adults 18-34 living with parents", "1", "Aged 18–34, living with parents"),
              ("age band", "3", "Aged 65 and over")]
        for k, (tbl, b, lab) in enumerate(SH):
            ax = fig.add_subplot(gs[k // 2, k % 2]); md = self.median_share(tbl, b)
            ax.plot(md.index, md.observed, color=ps.OBSERVED, marker="s", ms=3.2); ax.plot(md.index, md.model, color=ps.MODEL, marker="o", ms=3.2)
            lo, hi = np.nanmin(md.values), np.nanmax(md.values); pad = max(2.0, (hi - lo) * 0.4); ax.set_ylim(max(0, lo - pad), hi + pad)
            ax.set_xticks(md.index[::2] if len(md) > 6 else md.index); heading(ax, lab); ax.set_ylabel("County median (%)")
            if k >= 2: ax.set_xlabel("Year")
            out["abcd"[k]] = ax
        fig_legend(fig, ["model", "observed"])
        p = save(fig, "fig_v2_d2", out)
        record(2, "d", p, f"silo_validation_{self.scen}.parquet (B composition)", "Stage2.app_d (d2)", "see paper caption")

    def app_e(self):
        fig = ps.new_figure(6.6); gs = fig.add_gridspec(2, 2, height_ratios=[4.3, 1.55], width_ratios=[1, 1]); order = self.by_size()
        a = fig.add_subplot(gs[0, 0]); J = self.jobs(self.yl); M = J.pivot_table(index="county", columns="bin", values="ratio").reindex(order)
        ratio_heat(a, M.values, [NAMES[c] for c in order], [{"IND": "Industry", "OFF": "Office", "OTH": "Other", "RET": "Retail"}.get(c, c) for c in M.columns], 0.10)
        a.set_xticklabels(a.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor"); a.set_xlabel(f"Jobs by type, {self.yl}")
        b = fig.add_subplot(gs[0, 1]); A = pd.read_parquet(f"{DATA}/abit_validation.parquet")
        w = A[(A.section == "work") & (A.metric == "commute_mean_km") & ~A.county.isin(["all", "other"])].copy(); w["name"] = w.county.astype(int).map(NAMES); w["ratio"] = w.model / w.observed
        dot_chart(b, w.name.values, w.ratio.values, band=0.05, err=2 * w.seed_sd.values / w.observed.values, label="Mean commute distance,\nmodel ÷ observed (–)", xlim=(0.8, 1.32))
        c = fig.add_subplot(gs[1, :]); W = A[(A.section == "work") & (A.county == "all") & A.metric.str.startswith("commute_share_")].set_index("metric")
        o, m, sd = [np.array([W.loc[f"commute_share_{b_}", col] for b_ in DIST_LABELS]) * 100 for col in ("observed", "model", "seed_sd")]; x = np.arange(len(DIST_LABELS))
        c.fill_between(x, m - 2 * sd, m + 2 * sd, color=ps.SEED_BAND, lw=0); c.plot(x, o, color=ps.OBSERVED, marker="s", ms=3.2); c.plot(x, m, color=ps.MODEL, marker="o", ms=3.2)
        dist_axis(c, "Commute distance (km)"); c.set_ylabel("Share of commutes (%)"); c.set_ylim(0, 19)
        fig.legend(handles=[H_("model"), H_("observed"), H_("seed"), H_("tol", "±5 %"), H_("outside")], loc="outside upper center", ncol=3)
        ratio_legend(fig, ncol=4)
        p = save(fig, "fig_v2_e", {"a": a, "b": b, "c": c})
        record(2, "e", p, f"silo_validation_{self.scen}.parquet (D jobs); abit_validation.parquet (work)", "Stage2.app_e", "see paper caption")

    def run(self):
        self.main(); self.app_a(); self.app_b(); self.app_c(); self.app_d(); self.app_e()


# ================================================================================================ stage 3: activity generation
TYPES = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME", "ALL"]; SUBT = ["RECREATION", "ACCOMPANY", "OTHER_OTHER"]
TLAB = {"WORK": "Work", "SCHOOL": "School", "SHOPPING": "Shopping", "OTHER": "Other", "HOME": "Return home", "ALL": "All activities",
        "RECREATION": "  Recreation", "ACCOMPANY": "  Accompanying", "OTHER_OTHER": "  Other errands"}
SETS = [("verification", "D", ps.MODEL, "Verification"), ("validation", "o", ps.MODEL, "Validation"), ("chain", "^", ps.MODEL, "Chain test")]
SET_HANDLES = [Line2D([], [], marker=m, ls="", color=c, ms=4.5, label=l) for _, m, c, l in SETS]
PURP = ["WORK", "EDUCATION", "SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
PLAB = {"WORK": "Work", "EDUCATION": "Education", "SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompanying", "OTHER": "Other", "all": "All purposes"}
MODES = ["CAR_DRIVER", "CAR_PASSENGER", "BUS", "TRAIN", "WALK", "BIKE"]; MLAB = {"CAR_DRIVER": "Car driver", "CAR_PASSENGER": "Car passenger", "BUS": "Bus", "TRAIN": "Rail", "WALK": "Walk", "BIKE": "Bicycle"}
MIN_PERSONS = 300      # tours by county: counties with >= 300 surveyed persons (validation half)
MIN_ACT = 30           # duration by start hour: curves end at the first night hour with fewer than 30 observed activities


class Stage3:
    def __init__(self):
        self.T = pd.read_csv(f"{DATA}/abit_roorda_tables.csv"); self.T = self.T[self.T.variant == "base"]
        self.E = pd.read_csv(f"{DATA}/abit_roorda_extra.csv"); self.K = pd.read_csv(f"{DATA}/abit_roorda_ks.csv"); self.C = pd.read_parquet(f"{DATA}/abit_roorda_curves.parquet")
        if "variant" in self.K: self.K = self.K[self.K.variant == "base"] if (self.K.variant == "base").any() else self.K
        self.A = pd.read_parquet(f"{DATA}/abit_validation.parquet"); self.S = pd.read_parquet(f"{DATA}/abit_validation_seeds.parquet")
        self.N = pd.read_csv(f"{DATA}/abit_roorda_duration_counts.csv")
        # 2026-10-22: the estimated destination MNL (3_abit/destination_choice) replaces the gravity form; its runs are the settings
        # <setting>_mnl of the Roorda files and data/abit_validation*_mnl.parquet.  STAGE3_MODEL=gravity draws the former model.
        mnl_sets = {"verification_mnl", "validation_mnl", "chain_mnl"}
        have = mnl_sets <= set(self.T.setting) and os.path.exists(f"{DATA}/abit_validation_mnl.parquet")
        self.model = os.environ.get("STAGE3_MODEL", "mnl" if have else "gravity")
        if self.model == "mnl":
            ren = lambda d: d[~d.setting.isin(["verification", "validation", "chain"])].assign(setting=lambda x: x.setting.str.replace("_mnl", "", regex=False))
            self.T, self.E, self.K, self.C = ren(self.T), ren(self.E), ren(self.K), ren(self.C)
            self.A = pd.read_parquet(f"{DATA}/abit_validation_mnl.parquet"); self.S = pd.read_parquet(f"{DATA}/abit_validation_seeds_mnl.parquet")
        print(f"stage 3 figures: destination choice = {self.model}")

    def sel(self, section, metric, purpose="all", segment="all", county="all"):
        A = self.A; x = A[(A.section == section) & (A.metric == metric) & (A.purpose == purpose) & (A.segment == segment) & (A.county == county)]
        return x.iloc[0] if len(x) else None

    def curve(self, setting, figure, typ):
        return self.C[(self.C.setting == setting) & (self.C.figure == figure) & (self.C.type == typ)].set_index("hour")

    def tot(self, s, c, col="total"):
        r = self.T[(self.T.setting == s) & (self.T.type == c)].iloc[0]
        if col == "total": return r.model_total / r.observed_total, 2 * r.model_total_sd / r.observed_total
        return r.model_km / r.observed_km, 2 * r.model_km_sd / r.observed_km

    def ext(self, table, metric):
        return lambda s, g: (lambda r: (r.model / r.observed, 2 * r.model_sd / r.observed))(self.E[(self.E.setting == s) & (self.E.table == table) & (self.E.group == g) & (self.E.metric == metric)].iloc[0])

    def settings_dots(self, ax, cats, labels, getter, band=0.10, label=RLAB, xlim=None, direct=True):
        """Ratio by category (rows, top to bottom) in the three settings, +-2 s.d. of the replications; settings labelled on the first row."""
        n = len(cats); pos = np.arange(n)[::-1]; off = [0.27, 0, -0.27]
        ps.ratio_axis(ax, band=band, orient="x", label=label); first = []
        for (s, mk, fc, lab), o in zip(SETS, off):
            r = [getter(s, c) for c in cats]; v = np.array([a for a, _ in r]); e = np.array([b for _, b in r]); p = pos + o
            ax.errorbar(v, p, xerr=e, fmt="none", ecolor=ps.MODEL, elinewidth=0.7, zorder=3)
            ax.scatter(v, p, marker=mk, s=18 if mk == "D" else 22, facecolor=fc, edgecolor=ps.MODEL, lw=0.9, zorder=4); first.append((p[0], v[0] + e[0]))
        ax.set_yticks(pos); ax.set_yticklabels(labels); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", length=0); ax.set_ylim(-0.6, n - 0.4)
        if xlim: ax.set_xlim(*xlim)
        if direct:
            x = max(xx for _, xx in first) + 0.012
            settings_direct_labels(ax, [y for y, _ in first], [x] * 3, [s[3] for s in SETS])

    # ---- panels
    def tl(self, purpose):
        obs = np.array([self.sel("triplength", f"share_{b}", purpose).observed for b in DIST_LABELS]) * 100
        sm = self.S[(self.S.section == "triplength") & (self.S.purpose == purpose) & (self.S.county == "all") & self.S.metric.str.startswith("share_")]
        sm = sm.pivot(index="seed", columns="metric", values="value")[[f"share_{b}" for b in DIST_LABELS]].values * 100
        return obs, sm.mean(0), sm.std(0, ddof=1)

    def p_triplength(self, ax, purpose="all", show_x=True, ylab=True, top=None):
        obs, m, sd = self.tl(purpose); x = np.arange(len(DIST_LABELS))
        ax.fill_between(x, m - 2 * sd, m + 2 * sd, color=ps.SEED_BAND, lw=0); ax.plot(x, obs, color=ps.OBSERVED, marker="s", ms=3); ax.plot(x, m, color=ps.MODEL, marker="o", ms=3)
        dist_axis(ax, "Trip distance (km)", show=show_x); ax.set_ylim(0, top or max(obs.max(), m.max()) * 1.2)
        ax.yaxis.set_major_locator(MaxNLocator(5, steps=[1, 2, 5, 10], integer=True))
        if ylab: ax.set_ylabel("Share of trips (%)")

    def county_ratio(self):
        t = self.A[(self.A.section == "tours") & (self.A.metric == "tours_per_traveller_day") & (self.A.purpose == "all") & (self.A.segment == "all") & ~self.A.county.isin(["all", "other"])]
        t = t[t.n_obs >= MIN_PERSONS]
        return t.county.astype(int).map(NAMES).values, (t.model / t.observed).values, (2 * t.seed_sd / t.observed).values

    def app_a(self):
        """Gate runs: home-based tours per traveller-day by purpose and by county (the levels by activity type are in the TASHA-form tables)."""
        fig = ps.new_figure(3.0); gs = fig.add_gridspec(1, 2)
        c = fig.add_subplot(gs[0, 0]); r = [self.sel("tours", "tours_per_traveller_day", p_) for p_ in PURP]
        dot_chart(c, [PLAB[p_] for p_ in PURP], [q.model / q.observed for q in r], band=0.10, err=[2 * q.seed_sd / q.observed for q in r],
                  label="Tours per traveller-day,\nmodel ÷ observed (–)", xlim=(0.6, 1.2))
        d = fig.add_subplot(gs[0, 1]); nm, rr, ee = self.county_ratio()
        dot_chart(d, nm, rr, band=0.10, err=ee, label="Tours per traveller-day,\nmodel ÷ observed (–)", xlim=(0.75, 1.12))
        fig.legend(handles=[H_("model_dot"), H_("seed_bar"), H_("tol", "±10 %"), H_("outside")], loc="outside upper center", ncol=4)
        p = save(fig, "fig_v3_a", {"a": c, "b": d})
        record(3, "a", p, "abit_validation.parquet (tours)", "Stage3.app_a", "see paper caption")
        record(3, "c", p + " (b)", "abit_validation.parquet (tours by county)", "Stage3.app_a (b)", "see paper caption")

    def app_b(self):
        """Gate runs: trip mode shares by purpose, model minus survey (the start-time profiles are the TASHA-form figures fig_t3_start_*)."""
        fig = ps.new_figure(2.9); ax = fig.add_subplot(111); P = PURP + ["all"]
        H = np.array([[(self.sel("modes", f"trip_share_{m}", p_).model - self.sel("modes", f"trip_share_{m}", p_).observed) * 100 for m in MODES] for p_ in P]).T
        ax.grid(False); im = ax.imshow(H, cmap=ps.DIV, vmin=-ps.PP_LIM, vmax=ps.PP_LIM, aspect="auto")
        for i in range(H.shape[0]):
            for j in range(H.shape[1]):
                if abs(H[i, j]) > 2: ax.text(j, i, f"{H[i, j]:+.1f}".replace("-", "−"), ha="center", va="center", fontsize=ps.FONT, color=ps.INK)
        ax.set_yticks(range(len(MODES))); ax.set_yticklabels([MLAB[m] for m in MODES]); ax.set_xticks(range(len(P))); ax.set_xticklabels([PLAB[p_] for p_ in P], rotation=30, ha="right", rotation_mode="anchor")
        ax.set_xlabel("Trip purpose"); ax.tick_params(length=0)
        pp_colorbar(fig, im, ax, fraction=0.04, pad=0.02, aspect=20)
        p = save(fig, "fig_v3_b2")
        record(3, "b", p, "abit_validation.parquet (modes)", "Stage3.app_b (b2)", "see paper caption")

    def app_c(self):
        fig = ps.new_figure(4.4); gs = fig.add_gridspec(2, 2, height_ratios=[4, 5]); out = {}
        AR = ["Baltimore City", "Washington DC", "inner suburbs", "outer counties"]; PT = ["worker", "student 5-17", "student 18+", "non-worker", "retiree"]
        ARL = ["Baltimore City", "Washington DC", "Inner suburbs", "Outer counties"]; PTL = ["Worker", "Student, 5–17", "Student, 18+", "Non-worker", "Retiree"]
        for k, (cats, labs, metric, xl, xlim, row) in enumerate([(AR, ARL, "activities_per_person_ALL", "Activities per person,\nmodel ÷ observed (–)", (0.8, 1.25), 0),
                                                                 (AR, ARL, "avg_km", "Mean distance,\nmodel ÷ observed (–)", (0.6, 1.25), 0),
                                                                 (PT, PTL, "activities_per_person_ALL", "Activities per person,\nmodel ÷ observed (–)", (0.8, 1.25), 1),
                                                                 (PT, PTL, "avg_km", "Mean distance,\nmodel ÷ observed (–)", (0.6, 1.25), 1)]):
            table = "area" if cats is AR else "ptype"; ax = fig.add_subplot(gs[row, k % 2])
            self.settings_dots(ax, cats, labs if k % 2 == 0 else [""] * len(cats), self.ext(table, metric), label=xl, xlim=xlim, direct=False)
            out["abcd"[k]] = ax
        fig.legend(handles=SET_HANDLES + [H_("seed_bar"), H_("tol", "±10 %")], loc="outside upper center", ncol=3)
        p = save(fig, "fig_v3_c", out)
        record(3, "c", p, "abit_roorda_extra.csv", "Stage3.app_c", "see paper caption")

    def app_e(self):
        fig = ps.new_figure(5.9); gs = fig.add_gridspec(3, 2); out = {}
        for k, p_ in enumerate(PURP):
            ax = fig.add_subplot(gs[k // 2, k % 2]); self.p_triplength(ax, p_, show_x=k >= 4, ylab=k % 2 == 0, top=30); heading(ax, PLAB[p_]); out["abcdef"[k]] = ax
        fig_legend(fig, ["model", "observed", "seed"])
        p = save(fig, "fig_v3_e", out)
        record(3, "e", p, "abit_validation*.parquet (triplength)", "Stage3.app_e", "see paper caption")

    def run(self):
        import tasha_stage3 as t3                     # TASHA-form tables and figures (Roorda et al., 2008): verification, validation, chain test
        for f in t3.run(t3.parse_variants(os.environ.get("ABIT_VARIANTS", ""))):
            kind = "a" if f.endswith(".tex") else {"start": "b", "duration": "d", "chains": "e", "distance": "e"}[f.split("fig_t3_")[1].split("_")[0]]
            record(3, kind, f, "abit_roorda_tables.csv, abit_roorda_ks.csv, abit_roorda_curves.parquet, abit_roorda_duration_counts.csv",
                   "tasha_stage3.py", "TASHA form (Roorda et al., 2008), see paper caption")
        self.app_a(); self.app_b(); self.app_c(); self.app_e()


# ================================================================================================ stage 4: assignment
# %RMSE thresholds by AADT volume group (FDOT 2008 as transcribed by Wegmann 2016): CHECK the values against Wegmann (2016) before the first use.
FDOT_GROUPS = [(0, 5000), (5000, 10000), (10000, 15000), (15000, 20000), (20000, 30000), (30000, 50000), (50000, 60000), (60000, np.inf)]
FDOT_ACCEPT = [100, 45, 35, 30, 27, 25, 20, 19]
OSM_ROWS = ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street", "service"]
# classes taken as equivalent, as in 4_matsim/network/NETWORK_AUDIT.md section 1 (trunk = 2 or 3: expressway or principal arterial)
AGREE = {("motorway", 1), ("motorway", 2), ("trunk", 2), ("trunk", 3), ("primary", 3), ("secondary", 4), ("tertiary", 5), ("tertiary", 6), ("residential", 7),
         ("unclassified", 7), ("living_street", 7), ("service", 7)}
FC_WORDS = {1: "Interstate", 2: "Other\nfreeway or\nexpressway", 3: "Principal\narterial", 4: "Minor\narterial", 5: "Major\ncollector", 6: "Minor\ncollector", 7: "Local"}


class Stage4:
    """Assignment against counts (held-out half of the stations only).  The main figure fig_v4_main is written only when the 2024
    five-seed MATSim runs and the counter, screenline and corridor files exist (formats as documented in the catalogue); no
    placeholder figure is produced.  The input checks (network and transit against the state and MTA inventories) are ready."""

    def __init__(self, runs_dir):
        self.runs = sorted(glob.glob(f"{runs_dir}/*2024*_s[1-5]")) if runs_dir and os.path.isdir(runs_dir) else []

    def run(self):
        pend = "pending: 2024 five-seed assignment"
        for k, d, cap in [("a", "MATSim link volumes; count_stations_split.csv (held_out)", "Model daily volume against AADT at the held-out stations by facility class, FDOT %RMSE band."),
                          ("b", "as (a)", "%RMSE by AADT volume group against the FDOT acceptable values; GEH at the permanent counters."),
                          ("c", "as (a); count_stations_matched.csv", "Held-out stations by model/AADT ratio class (map only if the pattern is spatial; else sorted dot chart)."),
                          ("d", "MATSim hourly link volumes; data/count_hourly_2024.csv (permanent counters, not yet obtained)", "Hourly profiles at the permanent counters (GEH < 5 share)."),
                          ("e", "data/screenlines.csv; data/npmrds_corridors.csv (NPMRDS, data request)", "Screenline totals by direction and corridor travel times against NPMRDS.")]:
            record(4, k, "fig_v4_main / fig_v4_" + k, d, f"Stage4 ({k})", cap, pend if not self.runs else "pending: counter, screenline and corridor files")
        if self.runs: print("stage 4: assignment runs found; implement fig_v4_main (four panels) once the counter, screenline and corridor files exist")

    def class_tables(self):
        ct = pd.read_csv(f"{DATA}/network_audit_class_crosstab.csv", index_col=0)
        n = ct[[c for c in ct.columns if c.startswith("links_")]]; n.columns = [int(c.split("fc")[1]) for c in n.columns]
        rows = [c for c in OSM_ROWS if c in n.index]; n = n.loc[rows]; return n, n.div(n.sum(axis=1), axis=0)

    def inputs(self):
        fig = ps.new_figure(5.9); gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.08]); out = {}
        r1 = gs[0].subgridspec(1, 2, width_ratios=[1, 1]); r2 = gs[1].subgridspec(1, 2, width_ratios=[1.2, 1])
        n, share = self.class_tables()
        a = fig.add_subplot(r1[0]); agree = np.array([sum(share.loc[r, c] for c in n.columns if (r, c) in AGREE) for r in n.index]) * 100
        y = np.arange(len(n))[::-1]; a.barh(y, agree, color=ps.MODEL, height=0.65)
        a.set_yticks(y); a.set_yticklabels([r.replace("_", " ").capitalize() for r in n.index]); a.set_xlim(0, 100); a.grid(axis="y", visible=False); a.tick_params(axis="y", length=0)
        a.set_xlabel("Links whose class agrees\nwith the state inventory (%)"); a.set_ylabel("OpenStreetMap road type"); out["a"] = a
        SP = pd.read_csv(f"{DATA}/network_audit_speed_pairs.csv").dropna(subset=["osm_posted"]); vals = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
        P = pd.crosstab(SP.osm_posted.round().astype(int), SP.mdot_sign_mph.round().astype(int)).reindex(index=vals, columns=vals).fillna(0).astype(int)
        b = fig.add_subplot(r1[1]); b.grid(False)
        im = b.imshow(np.where(P.values > 0, P.values, np.nan), cmap=ps.SEQ, norm=LogNorm(vmin=1, vmax=max(P.values.max(), 10)), origin="lower", aspect="auto")
        tk = list(range(0, len(vals), 2)); b.set_xticks(tk); b.set_xticklabels([vals[i] for i in tk]); b.set_yticks(tk); b.set_yticklabels([vals[i] for i in tk])
        b.set_xlabel("Posted speed, state sign\ninventory (mph)"); b.set_ylabel("Posted speed,\nOpenStreetMap (mph)"); b.plot([-0.5, len(vals) - 0.5], [-0.5, len(vals) - 0.5], color=ps.INK2, lw=0.7)
        cb = fig.colorbar(im, ax=b, fraction=0.05, pad=0.03); cb.set_label("Number of signs"); cb.ax.yaxis.set_major_locator(FixedLocator([1, 10, 100, 1000]))
        cb.ax.set_yticklabels(["1", "10", "100", "1,000"]); cb.ax.yaxis.set_minor_formatter(NullFormatter()); cb.outline.set_visible(False); out["b"] = b
        c = fig.add_subplot(r2[0]); bins = np.arange(-32.5, 33, 5); c.axvspan(-5, 5, color=ps.TOL_BAND, lw=0, zorder=0)
        h, _ = np.histogram(SP.osm_minus_mdot.clip(-30, 30), bins=bins); c.bar(bins[:-1] + 2.5, 100 * h / h.sum(), width=4.2, color=ps.MODEL, label="OpenStreetMap speed")
        h2, _ = np.histogram(SP.coded_minus_mdot.clip(-30, 30), bins=bins); c.step(bins[:-1] + 2.5, 100 * h2 / h2.sum(), where="mid", color=ps.OBSERVED, lw=1.3, label="Free speed in the model")
        c.set_xlabel("Difference to the posted sign (mph)"); c.set_ylabel("Share of signs (%)"); c.set_ylim(0, 135); c.set_yticks([0, 20, 40, 60, 80, 100]); c.set_xticks([-30, -15, 0, 15, 30]); c.set_xlim(-36, 36)
        c.legend(handles=[Patch(color=ps.MODEL, label="OpenStreetMap"), Line2D([], [], color=ps.OBSERVED, lw=1.3, label="Model free speed"), H_("tol", "±5 mph")],
                 loc="upper left", borderaxespad=0.2, handlelength=1.2)
        out["c"] = c
        d = fig.add_subplot(r2[1]); Hh = pd.read_csv(f"{DATA}/transit_gtfs_headways_core.csv")
        bus = sorted([(r.route.replace("CityLink ", "").title(), r.am_peak / 10.0) for r in Hh.itertuples() if r.route.startswith("CityLink")], key=lambda r: r[1])
        mt = Hh[Hh.route.str.startswith("METRO")].iloc[0]; metro = [("Morning peak", mt.am_peak / 8.0), ("Midday", mt.midday / 10.0), ("Evening", mt.evening / 11.0)]
        rows = [("Metro subway", None)] + metro + [("CityLink bus, morning peak", None)] + bus[::-1]
        y = np.arange(len(rows))[::-1]; ps.ratio_axis(d, band=0.2, orient="x", label="Headway, timetable\n÷ published (–)")
        for yy, (nm_, v) in zip(y, rows):
            if v is None: continue
            ok = abs(v - 1) <= 0.2; d.scatter([v], [yy], s=18, facecolor=ps.MODEL if ok else "white", edgecolor=ps.MODEL, lw=1.0, zorder=3)
        d.set_yticks(y); d.set_yticklabels([("" if v is None else "  ") + nm_ for nm_, v in rows]); d.grid(axis="y", visible=False); d.tick_params(axis="y", length=0)
        for t, (nm_, v) in zip(d.get_yticklabels(), rows):
            if v is None: t.set_fontweight("bold"); t.set_color(ps.INK)
        d.set_xlim(0.6, 1.7); d.set_ylim(-0.6, len(rows) - 0.4); out["d"] = d
        p = save(fig, "fig_v4_inputs", out)
        record(4, "inputs", p, "network_audit_class_crosstab.csv; network_audit_speed_pairs.csv; transit_gtfs_headways_core.csv", "Stage4.inputs", "see paper caption")
        # appendix: the full class matrix
        fig = ps.new_figure(3.6); ax = fig.add_subplot(111); ax.grid(False)
        im = ax.imshow(share.values * 100, cmap=ps.SEQ, vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(n.columns))); ax.set_xticklabels([FC_WORDS[c] for c in n.columns], rotation=0)
        ax.set_yticks(range(len(n))); ax.set_yticklabels([r.replace("_", " ").capitalize() for r in n.index]); ax.tick_params(length=0)
        ax.set_xlabel("Functional class in the state inventory"); ax.set_ylabel("OpenStreetMap road type")
        for i, r in enumerate(n.index):
            for j, c in enumerate(n.columns):
                v = share.iloc[i, j]
                if v >= 0.05: ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=ps.FONT, color="white" if v > 0.55 else ps.INK)
                if (r, c) in AGREE: ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=ps.INK, lw=1.0))
        cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02); cb.set_label("Share of the road type's links (%)"); cb.outline.set_visible(False)
        p = save(fig, "fig_v4_a")
        record(4, "inputs", p, "network_audit_class_crosstab.csv", "Stage4.inputs (a)", "see paper caption")
        return p


# ================================================================================================ catalogue
def write_catalogue(scen):
    f = f"{V}/5_reports/FIGURE_CATALOGUE.md"
    stage = {1: "1 population synthesis (CVAE)", 2: "2 land use (SILO)", 3: "3 activity generation (ABIT)", 4: "4 assignment (MATSim)"}
    L = ["# Validation figure catalogue (generated by `reports/figures_validation.py`; do not edit by hand)", "",
         "Every figure is drawn at its printed size: exactly \\textwidth (384 pt = 5.313 in, from main.log) wide and at most 0.85 \\textheight "
         "(6.61 in) high, included with `width=\\textwidth`; all text >= 8 pt (tick labels 7.5 pt, panel letters 9 pt bold). "
         "`paperstyle.finish()` refuses to save a figure with overlapping text, a label or legend over data markers or bars, text or artists "
         "beyond the canvas, or a font below 7.5 pt. "
         "Main figures have at most four panels; detail and the remaining dimensions are appendix figures. Plain-word labels with units; "
         "data-source names, acronyms and statistics are in the captions. Model blue, observed grey, seed range (±2 s.d.) light blue, "
         "tolerance band light grey; ratios model ÷ observed on a linear axis with a line at 1 (log axis where ratios span more than a factor "
         "of five); share differences in percentage points on one diverging scale (−10 to +10); ratio classes written out ('Within ±10 %'). "
         "Maps only where the spatial pattern carries information (else sorted dot charts). Files in `5_reports/figures/` (PDF + PNG), "
         "copied to `paper/figures/`. Data paths relative to `WORKSPACE/data/` unless stated.",
         f"Land-use input file of this build: `data/silo_validation_{scen}.parquet`.", "",
         "Dimensions: a levels/totals, b composition (and joint structure), c spatial, d temporal, e length/interaction.", "",
         "## Matrix (stage × dimension)", "", "| stage | a levels | b composition | c spatial | d temporal | e length |", "|---|---|---|---|---|---|"]
    C = pd.DataFrame(CAT_ROWS)
    for s in [1, 2, 3, 4]:
        cells = []
        for k in "abcde":
            d = C[(C.stage == s) & (C.dim.str.startswith(k))]; st = "ready" if len(d) and (d.status == "ready").all() else ("pending" if len(d) else "–")
            files = sorted(set(re.sub(r" \(.\)$", "", x).replace("5_reports/figures/", "").replace(".pdf", "") for x in d.fig))
            cells.append(f"{', '.join(files)} — **{st}**" if len(d) else "–")
        L.append(f"| {stage[s]} | " + " | ".join(cells) + " |")
    L += ["", "Stage 1 has no time dimension (base year); its spatial check is the county dot chart of fig_v1_main (a) and the PUMA dot "
          "chart of fig_v1_a (a) (county and PUMA maps were almost uniformly in the 'within ±10 %' class and were replaced). "
          "Stage 4 input checks (network and transit against MDOT and MTA): `fig_v4_inputs`, `fig_v4_a` — **ready**.", "",
          "## Pending", "",
          "- Land use, test window 2021–2024: the paper figures are from the calibration window (round 16, one seed), matching the text of "
          "Section 5.2. `data/silo_validation_oos_mean.parquet` (five seeds) now exists and is the default of the script when no `--silo` is "
          "given; build the paper set with `python3 reports/figures_validation.py --silo calib_r16` until the land-use text and the Fig. 7 "
          "caption are updated to 2021–2024 (the OOS build was tested: all stage-2 figures pass the checks).",
          "- Assignment (stage 4): fig_v4_main (four panels: model against AADT at the held-out stations by facility class; %RMSE by volume "
          "group; hourly profiles at the permanent counters; screenlines and corridor travel times) once the 2024 five-seed MATSim runs "
          "(`pipeline/runs/matsim/*2024*_s[1-5]`) and `data/count_hourly_2024.csv`, `data/screenlines.csv`, `data/npmrds_corridors.csv` exist. "
          "The FDOT %RMSE thresholds in `FDOT_ACCEPT` must be checked against Wegmann (2016) before first use.", "",
          "## Entries", "", "| stage | dim | figure | data | function | status | caption |", "|---|---|---|---|---|---|---|"]
    for r in CAT_ROWS: L.append(f"| {r['stage']} | {r['dim']} | `{r['fig']}` | {r['data']} | `{r['func']}` | {r['status']} | {r['caption']} |")
    open(f, "w").write("\n".join(L) + "\n"); print("catalogue:", f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("stages", nargs="*", type=int, default=[1, 2, 3, 4])
    ap.add_argument("--silo", default=None, help="scenario of data/silo_validation_<scen>.parquet (default: oos_mean if it exists, else calib_r16)")
    ap.add_argument("--silo-window", default=None, help="years of the comparison window, e.g. 2021-2024 (default from the scenario name)")
    ap.add_argument("--matsim-runs", default=f"{V}/pipeline/runs/matsim")
    a = ap.parse_args(); scen = a.silo or ("oos_mean" if os.path.exists(f"{DATA}/silo_validation_oos_mean.parquet") else "calib_r16")
    if 1 in a.stages: Stage1().run()
    if 2 in a.stages: Stage2(scen, a.silo_window).run()
    if 3 in a.stages: Stage3().run()
    if 4 in a.stages: s4 = Stage4(a.matsim_runs); s4.inputs(); s4.run()
    if set(a.stages) == {1, 2, 3, 4}: write_catalogue(scen)
    else: print("catalogue not rewritten (run all stages to regenerate it)")
