#!/usr/bin/env python3
"""Stage 3 (activity generation) tables and figures in the form of Roorda, Miller & Habib (2008), "Validation of TASHA",
Transportation Research Part A 42, 360-375: Table 1/2 (activity frequency comparison) and Figs. 2-8 (start time, duration,
trips per chain, distance by start time), for the verification (estimation half of the 2017/18 RTS, survey population as
input), the validation (held-out half) and the chain test (synthetic population).

    python3 reports/tasha_stage3.py                                   # current data, one MAST variant
    python3 reports/tasha_stage3.py --variants "_behav=MAST, behavioural (no calibration);=MAST, calibrated"

Also run by `python3 reports/figures_validation.py 3` (stage 3) and by the full build.

Input (written by activity/validation/validate_survey.py): data/abit_roorda_tables.csv (variant 'base' = exclusion rule persons 5+,
internal trips), abit_roorda_ks.csv (Roorda's KS on the hourly values: D_hourly, P_hourly), abit_roorda_curves.parquet,
abit_roorda_duration_counts.csv, abit_roorda_extra.csv (trips per chain).

MAST variants: each variant is a suffix of the setting names in the data files ('' -> verification, validation, chain;
'_behav' -> verification_behav, ...) and a label.  The first variant is the primary one (TASHA design: no calibration);
a second variant is added as a second row block in the tables and as a second (light-blue) bar or line series in the figures.
Variants whose settings are missing from the data are skipped with a message.

Outputs: 5_reports/figures/fig_t3_{start,duration,chains,distance}_{verification,validation,chain}.pdf/png (copied to
paper/figures/) and paper/sections/s3_tables/tab_s3_{verification,validation,chain}.tex (\\input by 05_results.tex).
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, os, shutil, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, MaxNLocator

V = f"{WORKSPACE}"
sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps   # noqa: E402
DATA = f"{V}/data"; OUT = f"{V}/5_reports/figures"; PAPERFIG = f"{V}/5_reports/paper/figures"
TABDIR = f"{V}/5_reports/paper/sections/s3_tables"
HOUR_ORDER = list(range(4, 24)) + list(range(0, 4))
TYPES = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME"]
TROW = {"WORK": "Work", "SCHOOL": "School", "SHOPPING": "Shopping", "OTHER": "Other", "HOME": "Home", "ALL": "Total"}
TTITLE = {"WORK": "Work activities", "SCHOOL": "School activities", "SHOPPING": "Shopping activities", "OTHER": "Other activities",
          "HOME": "Return home activities"}
SETTINGS = ["verification", "validation", "chain"]
SWORD = {"verification": "Verification", "validation": "Validation", "chain": "Chain test"}
SHALF = {"verification": "verification (estimation half)", "validation": "validation (held-out half)",
         "chain": "chain test (synthetic population, held-out half)"}
LABEL = {"verification": "tab:s3_ver", "validation": "tab:s3_val", "chain": "tab:s3_chain"}
MIN_ACT = 30                       # duration curves end at the first night hour with fewer than 30 observed activities
BAR = [ps.MODEL, "#86b6ef"]        # MAST variant 1 (primary), variant 2
LINE = [dict(color=ps.MODEL, ls="-"), dict(color="#86b6ef", ls="-")]
OBS_BAR = ps.OBSERVED; OBS_LINE = dict(color=ps.OBSERVED, ls=(0, (5, 2.5)))
Y_START = "Share of daily activities (%)"; X_START = "Activity start time (hour)"


# ------------------------------------------------------------------------------------------------ data
class Data:
    def __init__(self, variants):
        T = pd.read_csv(f"{DATA}/abit_roorda_tables.csv"); self.T = T[T.variant == "base"]
        self.K = pd.read_csv(f"{DATA}/abit_roorda_ks.csv"); self.C = pd.read_parquet(f"{DATA}/abit_roorda_curves.parquet")
        self.N = pd.read_csv(f"{DATA}/abit_roorda_duration_counts.csv"); self.E = pd.read_csv(f"{DATA}/abit_roorda_extra.csv")
        have = set(self.T.setting)
        self.variants = []
        for suf, lab in variants:
            miss = [s + suf for s in SETTINGS if s + suf not in have]
            if miss: print(f"tasha_stage3: variant '{lab}' skipped, settings missing in the data: {', '.join(miss)}"); continue
            self.variants.append((suf, lab))
        if not self.variants: raise SystemExit("tasha_stage3: no ABIT variant with data")

    def curve(self, setting, fig, typ):
        return self.C[(self.C.setting == setting) & (self.C.figure == fig) & (self.C.type == typ)].set_index("hour")

    def ks(self, setting, fig, typ):
        r = self.K[(self.K.setting == setting) & (self.K.figure == fig) & (self.K.type == typ)]
        return r.iloc[0] if len(r) else None

    def row(self, setting, typ):
        return self.T[(self.T.setting == setting) & (self.T.type == typ)].iloc[0]

    def thin(self, setting, typ):
        """Start hours (in HOUR_ORDER) dropped from the duration curves: from the first hour after 20:00 with < MIN_ACT observed."""
        base = setting.split("_")[0]
        n = self.N[(self.N.setting == base) & (self.N.type == typ)].set_index("hour").n_obs_dur.reindex(HOUR_ORDER).fillna(0).values
        thin = n < MIN_ACT; late = np.arange(24) >= 16
        if (thin & late).any(): thin[np.argmax(thin & late):] = True
        return thin


# ------------------------------------------------------------------------------------------------ figure helpers
def save(fig, name):
    p = ps.finish(fig, f"{OUT}/{name}"); shutil.copy(p, f"{PAPERFIG}/{name}.pdf"); return f"5_reports/figures/{name}.pdf"


def ptxt(p):
    return "P < 0.001" if p < 0.001 else f"P = {p:.3f}"


def ks_lines(D, rows, labels):
    if len(rows) == 1:
        r = rows[0]; return f"Kolmogorov–Smirnov test\nD = {r.D_hourly:.3f},  {ptxt(r.P_hourly)}"
    return "Kolmogorov–Smirnov test\n" + "\n".join(f"{l}: D = {r.D_hourly:.3f}, {ptxt(r.P_hourly)}" for l, r in zip(labels, rows))


def _line_points(ax):
    """Display coordinates of the drawn data lines, densified (lines carry no markers, so check() does not see them)."""
    P = []
    for ln in ax.lines:
        if not ln.get_visible() or ln.get_gid() == "guide": continue
        xy = ln.get_xydata(); xy = xy[np.isfinite(xy).all(1)]
        if len(xy) < 2: continue
        t = np.linspace(0, 1, 30)[:, None]
        seg = np.vstack([a + t * (b - a) for a, b in zip(xy[:-1], xy[1:])])
        P.append(ax.transData.transform(seg))
    return np.vstack(P) if P else np.zeros((0, 2))


def clear_space(fig, ax, artists, grow=1.12, tries=14):
    """Raise the upper y limit until no artist (text, legend) touches a bar or a data line."""
    for _ in range(tries):
        fig.canvas.draw(); r = fig.canvas.get_renderer()
        bars = [b.get_window_extent(r) for c in ax.containers for b in getattr(c, "patches", []) if b.get_height() > 0]
        P = _line_points(ax); hit = False
        for a in artists:
            bb = a.get_window_extent(r).expanded(1.04, 1.10)
            if any(bb.x0 < q.x1 and q.x0 < bb.x1 and bb.y0 < q.y1 and q.y0 < bb.y1 for q in bars): hit = True
            if len(P) and ((P[:, 0] > bb.x0) & (P[:, 0] < bb.x1) & (P[:, 1] > bb.y0) & (P[:, 1] < bb.y1)).any(): hit = True
        if not hit: return
        lo, hi = ax.get_ylim(); ax.set_ylim(lo, hi * grow)
    raise RuntimeError(f"no free space for {[getattr(a, 'get_text', lambda: 'legend')() for a in artists]}")


def nice_top(v, steps=(5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)):
    return next((s for s in steps if s >= v), v)


def legend_handles(D, kind):
    if kind == "bar":
        return [Patch(facecolor=BAR[i], label=l) for i, (_, l) in enumerate(D.variants)] + [Patch(facecolor=OBS_BAR, label="RTS")]
    return [Line2D([], [], lw=1.4, label=l, **LINE[i]) for i, (_, l) in enumerate(D.variants)] + [Line2D([], [], lw=1.4, label="RTS", **OBS_LINE)]


def paired_bars(ax, x, series, width=0.8):
    """series: [(values, colour)] drawn side by side at every x."""
    k = len(series); w = width / k
    for i, (v, c) in enumerate(series):
        ax.bar(x + (i - (k - 1) / 2) * w, v, w, color=c, edgecolor=c, lw=0)


# ------------------------------------------------------------------------------------------------ figures
def fig_start(D, s):
    """Roorda Fig. 2/6: % of 24-h frequency by start hour (4..3), five activity types, KS D and P in each panel."""
    fig = ps.new_figure(6.4); gs = fig.add_gridspec(3, 2); x = np.arange(24)
    pos = {"WORK": gs[0, 0], "SHOPPING": gs[1, 0], "OTHER": gs[2, 0], "SCHOOL": gs[0:2, 1], "HOME": gs[2, 1]}
    for ty in TYPES:
        ax = fig.add_subplot(pos[ty]); ser = []; rows = []
        for i, (suf, _) in enumerate(D.variants):
            d = D.curve(s + suf, "start_time", ty).loc[HOUR_ORDER]; ser.append((d.model.values, BAR[i])); rows.append(D.ks(s + suf, "start_time", ty))
        obs = D.curve(s + D.variants[0][0], "start_time", ty).loc[HOUR_ORDER].observed.values
        paired_bars(ax, x, ser + [(obs, OBS_BAR)])
        top = max(max(v.max() for v, _ in ser), obs.max())
        ax.set_ylim(0, nice_top(top * 1.25)); ax.yaxis.set_major_locator(MultipleLocator(10 if ax.get_ylim()[1] > 40 else 5))
        ax.set_xticks(x[::2]); ax.set_xticklabels([str(h) for h in HOUR_ORDER[::2]]); ax.set_xlim(-0.6, 23.6)
        ax.grid(axis="x", visible=False); ax.set_title(TTITLE[ty], loc="center", fontsize=ps.FONT, fontweight="bold", color=ps.INK)
        ax.set_xlabel(X_START); ax.set_ylabel(Y_START)
        left = obs[:12].sum() < obs[12:].sum()          # text over the emptier half of the day
        t = ax.text(0.03 if left else 0.97, 0.96, ks_lines(D, rows, [l for _, l in D.variants]), transform=ax.transAxes,
                    ha="left" if left else "right", va="top", fontsize=ps.FONT, color=ps.INK)
        clear_space(fig, ax, [t])
        ax.set_ylim(0, nice_top(ax.get_ylim()[1])); ax.yaxis.set_major_locator(MultipleLocator(10 if ax.get_ylim()[1] > 40 else 5))
    fig.legend(handles=legend_handles(D, "bar"), loc="outside upper center", ncol=len(D.variants) + 1)
    return save(fig, f"fig_t3_start_{s}")


def _band_arrow(ax, lo, hi, curves, ymax, fmax=0.93):
    """Roorda's double arrow over the band of the 90 % of starts (vertical lines at its ends), at the lowest free height."""
    xs = np.linspace(lo, hi, 60); vals = [np.interp(xs, cx, cy, left=np.nan, right=np.nan) for cx, cy in curves]
    for f in np.arange(0.10, fmax, 0.02):
        y = f * ymax; ok = all(np.nanmin(np.abs(v - y)) > 0.10 * ymax for v in vals if np.isfinite(v).any())
        if ok: break
    else:
        return None
    for xv in (lo, hi): ax.plot([xv, xv], [0, y + 0.06 * ymax], color=ps.INK2, lw=0.8, gid="guide")
    ax.annotate("", xy=(lo, y), xytext=(hi, y), arrowprops=dict(arrowstyle="<|-|>", color=ps.INK2, lw=0.9, shrinkA=0, shrinkB=0, mutation_scale=7))
    return ax.text((lo + hi) / 2, y, "90%", ha="center", va="center", fontsize=ps.FONT, color=ps.INK,
                   bbox=dict(facecolor="white", edgecolor=ps.INK2, lw=0.6, pad=1.2))


def fig_duration(D, s):
    """Roorda Fig. 3/7: average duration (min) by activity start time, MAST solid, RTS dashed, 90 % band, KS D and P."""
    fig = ps.new_figure(4.6); gs = fig.add_gridspec(2, 2); xh = np.arange(24) + 4 + 0.5
    for k, ty in enumerate(["WORK", "SCHOOL", "SHOPPING", "OTHER"]):
        ax = fig.add_subplot(gs[k // 2, k % 2]); th = D.thin(s, ty); curves = []; rows = []
        for i, (suf, _) in enumerate(D.variants):
            d = D.curve(s + suf, "duration", ty).loc[HOUR_ORDER]; m = np.where(th, np.nan, d.model.values)
            ax.plot(xh, m, lw=1.4, **LINE[i]); curves.append((xh, m)); rows.append(D.ks(s + suf, "duration", ty))
        d0 = D.curve(s + D.variants[0][0], "duration", ty).loc[HOUR_ORDER]; o = np.where(th, np.nan, d0.observed.values)
        ax.plot(xh, o, lw=1.4, **OBS_LINE); curves.append((xh, o))
        lo, hi = 4 + d0.band_lo.iloc[0] / 60, 4 + d0.band_hi.iloc[0] / 60
        top = np.nanmax(np.r_[[c[1] for c in curves]].ravel()); step = 120 if top > 200 else (30 if top < 100 else 60)
        ymax = np.ceil(top * 1.3 / step) * step; ax.set_ylim(0, ymax); ax.yaxis.set_major_locator(MultipleLocator(step))
        ax.set_xlim(4, 25); ax.set_xticks(range(4, 25, 2))
        ax.grid(axis="x", visible=False); ax.set_title(TTITLE[ty], loc="center", fontsize=ps.FONT, fontweight="bold", color=ps.INK)
        ax.set_xlabel(X_START); ax.set_ylabel("Duration (minutes)")
        t = ax.text(0.97, 0.97, ks_lines(D, rows, [l for _, l in D.variants]), transform=ax.transAxes, ha="right", va="top", fontsize=ps.FONT, color=ps.INK)
        for _ in range(8):
            fig.canvas.draw(); bb = t.get_window_extent(fig.canvas.get_renderer()).transformed(ax.transAxes.inverted())
            lab = _band_arrow(ax, lo, hi, curves, ax.get_ylim()[1], fmax=bb.y0 - 0.07)
            if lab is not None: break
            ax.set_ylim(0, ax.get_ylim()[1] + step)
        clear_space(fig, ax, [t] + ([lab] if lab is not None else []))
    fig.legend(handles=legend_handles(D, "line"), loc="outside upper center", ncol=len(D.variants) + 1, handlelength=2.6)
    return save(fig, f"fig_t3_duration_{s}")


def fig_chains(D, s):
    """Roorda Fig. 4: % of total number of chains by number of trips per chain (complete home-based chains)."""
    fig, ax = ps.figure(2.3); x = np.arange(1, 9); ser = []
    for i, (suf, _) in enumerate(D.variants): ser.append((D.curve(s + suf, "chains", "ALL").loc[range(1, 9)].model.values, BAR[i]))
    obs = D.curve(s + D.variants[0][0], "chains", "ALL").loc[range(1, 9)].observed.values
    paired_bars(ax, x, ser + [(obs, OBS_BAR)], width=0.7)
    ax.set_xticks(x); ax.set_xticklabels([str(i) for i in range(1, 8)] + ["8+"]); ax.set_xlim(0.4, 8.6); ax.grid(axis="x", visible=False)
    ax.set_xlabel("Trips per home-based chain"); ax.set_ylabel("Share of chains (%)"); ax.set_ylim(0, 70); ax.yaxis.set_major_locator(MultipleLocator(10))
    lg = ax.legend(handles=legend_handles(D, "bar"), loc="upper right"); clear_space(fig, ax, [lg])
    return save(fig, f"fig_t3_chains_{s}")


def fig_distance(D, s):
    """Roorda Fig. 5/8: average distance (km) to activities of all types by activity start time."""
    fig, ax = ps.figure(2.4); x = np.arange(24); ser = []
    for i, (suf, _) in enumerate(D.variants): ser.append((D.curve(s + suf, "distance_by_hour", "ALL").loc[HOUR_ORDER].model.values, BAR[i]))
    obs = D.curve(s + D.variants[0][0], "distance_by_hour", "ALL").loc[HOUR_ORDER].observed.values
    paired_bars(ax, x, ser + [(obs, OBS_BAR)])
    ax.set_xticks(x); ax.set_xticklabels([str(h) for h in HOUR_ORDER]); ax.set_xlim(-0.6, 23.6); ax.grid(axis="x", visible=False)
    ax.set_xlabel(X_START); ax.set_ylabel("Average distance (km)")
    top = np.nanmax(np.r_[obs, np.concatenate([v for v, _ in ser])]); ax.set_ylim(0, np.ceil(top * 1.1 / 10) * 10)
    ax.yaxis.set_major_locator(MaxNLocator(6, steps=[1, 2, 4, 5, 10], integer=True))
    lg = ax.legend(handles=legend_handles(D, "bar"), loc="upper center", ncol=len(D.variants) + 1); clear_space(fig, ax, [lg])
    return save(fig, f"fig_t3_distance_{s}")


# ------------------------------------------------------------------------------------------------ tables (LaTeX)
def _n(v, d=0, sign=False):
    s = f"{v:+,.{d}f}" if sign else f"{v:,.{d}f}"
    return s.replace("-", "$-$").replace("+", "+" if sign else "")


def _h(*lines):
    return "\\begin{tabular}[b]{@{}l@{}}" + "\\\\".join(lines) + "\\end{tabular}"


def table_tex(D, s):
    r0 = D.row(s + D.variants[0][0], "ALL"); n = int(r0.persons)
    head = " & ".join([_h("Activity", "type"), _h("Model", "average", "total", "activities", "(ABIT) [b]"),
                       _h("Model", "std. dev.", "total", "activities", "(ABIT) [b]"), _h("Observed", "total", "activities", "(RTS)"),
                       _h("Model", "$\\pm$", "activities", "(\\#)"), _h("Model", "$\\pm$", "activities", "(\\%)"),
                       _h("Model", "average", "distance", "(km) [b]"), _h("Model", "std. dev.", "distance", "(km) [b]"),
                       _h("Observed", "average", "distance", "(km)"), _h("Model", "$\\pm$", "distance", "(km)"), _h("Model", "$\\pm$", "distance", "(\\%)"),
                       _h("Observed", "reported", "distance", "(km) [c]"), _h("Model", "$\\pm$", "reported", "(\\%) [c]")]) + " \\\\"
    body = []
    for suf, lab in D.variants:
        if len(D.variants) > 1: body.append(f"\\multicolumn{{13}}{{@{{}}l}}{{\\emph{{{lab}}}}} \\\\")
        for ty in TYPES + ["ALL"]:
            r = D.row(s + suf, ty)
            if ty == "ALL": body.append("\\addlinespace")
            body.append(" & ".join([TROW[ty], _n(r.model_total), _n(r.model_total_sd), _n(r.observed_total), _n(r["diff"], 0, True), _n(r.diff_pct, 1, True),
                                    _n(r.model_km, 2), _n(r.model_km_sd, 2), _n(r.observed_km, 2), _n(r.diff_km, 2, True), _n(r.diff_km_pct, 1, True),
                                    _n(r.observed_km_reported, 2), _n(r.diff_km_pct_reported, 1, True)]) + " \\\\")
    if s == "chain":
        fa = (f"ABIT runs on the synthetic 2016 population of the platform (5\\% sample; {n:,} persons aged 5 and over living in the counties of the "
              "survey households). The comparison excludes persons younger than 5 years and survey trips with an end outside the model zone "
              "system; observed totals are the weighted activities of the held-out half of the RTS scaled to the simulated persons.")
    else:
        half = "estimation" if s == "verification" else "held-out (validation)"
        fa = (f"ABIT runs on the observed households and persons of the {half} half of the RTS. The comparison excludes persons younger than "
              "5 years (ABIT generates no activities for them) and survey trips with an end outside the model zone system; facilitate-passenger "
              f"(accompanying) activities are kept in other. Observed totals are the weighted survey activities scaled to the {n:,} persons "
              "aged 5 and over simulated.")
    fa += (" Distance: the car-distance skim between the zones of the trip's origin and destination on both sides (survey: the zones that "
           "contain the internal points of the reported origin and destination tracts; intrazonal: half the square root of the zone area).")
    fb = "Model results are the average (standard deviation) of 10 replications of the Monte Carlo simulation."
    fc = ("The survey's reported address-to-address driving distance, a different measure from the model's zone-to-zone skim "
          "distance; shown for reference.")
    cap = f"Activity frequency comparison, ABIT vs RTS, {SHALF[s]}\\ [a]"
    return "\n".join([
        "% generated by reports/tasha_stage3.py from data/abit_roorda_tables.csv (variant base); do not edit by hand",
        "\\begin{sidewaystable}[!tbp]", "  \\centering", f"  \\caption{{{cap}}}", f"  \\label{{{LABEL[s]}}}",
        "  \\footnotesize\\setlength{\\tabcolsep}{3pt}",
        "  \\begin{tabular}{@{}l*{12}{r}@{}}", "    \\toprule", "    " + head, "    \\midrule"] + ["    " + b for b in body] + [
        "    \\bottomrule", "  \\end{tabular}", "",
        "  \\parbox{\\linewidth}{\\footnotesize\\vspace{3pt}" + f"[a]\\,{fa}\\\\[1pt][b]\\,{fb}\\\\[1pt][c]\\,{fc}" + "}",
        "\\end{sidewaystable}", ""])


def run(variants):
    D = Data(variants); os.makedirs(TABDIR, exist_ok=True); out = []
    for s in SETTINGS:
        open(f"{TABDIR}/tab_s3_{s}.tex", "w").write(table_tex(D, s)); out.append(f"5_reports/paper/sections/s3_tables/tab_s3_{s}.tex")
        out += [fig_start(D, s), fig_duration(D, s), fig_chains(D, s), fig_distance(D, s)]
    return out


def parse_variants(txt):
    if not txt: return [("", "ABIT")]
    return [tuple(p.split("=", 1)) for p in txt.split(";")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--variants", default=os.environ.get("ABIT_VARIANTS", ""),
                                                    help="'suffix=label;suffix=label', primary first (default: '=ABIT')")
    for f in run(parse_variants(ap.parse_args().variants)): print(f)
