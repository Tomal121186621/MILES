#!/usr/bin/env python3
"""Validation of the land-use model (stage 2, SILO) against the American Community Survey and other observed data.

    python3 build_silo.py [--seeds oos_respec_s1 ... oos_respec_s5] [--mean oos_respec_mean] [--calib calib_respecF_r4] [--test-window 2021-2024] [--out PDF] [--work DIR]

Each scenario name is the suffix of data/silo_validation_<name>.parquet (written by 2_silo/validation).
--seeds    the seed scenarios (one run each), --mean the mean over the seeds with their standard deviation (out of sample),
--calib    the calibration-window scenario (one run).  Every number in the text is computed from these files.
Defaults: the final runs of the re-specified model.  The earlier runs stay reachable, e.g. --seeds oos_s1 ... oos_s5 --mean oos_mean --calib calib_r51.
--seed-choice  table of the rule that picked the run passed to the activity model (one row per seed, column ssq_rel_dev).
--acs-commute  ACS 2024 one-year commute extraction shared with the activity-model validation (travel time, work in Maryland).
"""
import argparse, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("--seeds", nargs="+", default=[f"oos_respec_s{i}" for i in range(1, 6)])
ap.add_argument("--mean", default="oos_respec_mean")
ap.add_argument("--calib", default="calib_respecF_r4")
ap.add_argument("--test-window", default="2021-2024")
ap.add_argument("--seed-choice", default=f"{V}/side_experiments/respec_2026-11/engine_check/tables/p01_seed_choice.csv")
ap.add_argument("--acs-commute", default=f"{V}/3_abit/temporal_2024/data")
ap.add_argument("--out", default=f"{HERE}/silo_validation.pdf")
ap.add_argument("--work", default=f"{HERE}/work/silo")
a = ap.parse_args()
WORK = os.path.abspath(a.work); FIG = f"{WORK}/fig"; os.makedirs(FIG, exist_ok=True)
fv = patch_fig_dirs(FIG)
import paperstyle as ps
import composite as K
import fig_pop_landuse as PL
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.colors import ListedColormap, BoundaryNorm

C = fv.Stage2(a.calib); T = fv.Stage2(a.mean, a.test_window)
SEEDS = [fv.Stage2(s, a.test_window) for s in a.seeds]
NS = len(SEEDS); NAMES = fv.NAMES
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}; nw = WORDS.get(NS, str(NS))
cw, tw = C.wlab, T.wlab
cyrs, tyrs = C.win, T.win
ev_all = T.R[T.R.section == "C events"]
EVT = ev_all[["table", "geo"]].drop_duplicates().values.tolist()
DEATHS = "deaths share of persons (engine events; observed: Maryland)"
EVLAB = {"births per woman 15-50": "Births per woman aged 15–50", "persons leaving Maryland (deaths, out-migration, moves to other states)": "Persons leaving Maryland",
         "new marriages share of adults": "New marriages, share of adults", "divorces share of married": "Divorces, share of married persons",
         "job starts share of non-employed adults": "Job starts, share of non-employed adults", "job quits share of employed": "Job quits, share of employed persons",
         "persons who moved share (persons aged 1+)": "Persons who moved, share of persons aged 1+",
         "households moved share (households present both years; diagnostic)": "Households that moved, share of households",
         DEATHS: "Deaths, share of persons"}


def ratio_window(S, tab, geo, yrs):
    d = S.ev(tab, geo); d = d[d.year.isin(yrs)]
    return d.model.sum() / d.observed.sum() if len(d) and d.observed.sum() else np.nan


def comp_cells(S, yrs):
    B = S.R[(S.R.section == "B composition") & S.md & S.R.year.isin(yrs)].copy(); B["bin"] = B["bin"].astype(str); return B


def bin_stats(S, yrs):
    B = comp_cells(S, yrs); rows = {}
    for (t, b), g in B.groupby(["tbl", "bin"]):
        rows[(t, b)] = dict(bias=g.diff_pp.mean(), mad=g.diff_pp.abs().mean(), within=(g.diff_pp.abs() <= 5).mean(), worst=g.diff_pp.abs().max())
    return pd.DataFrame(rows).T


bc, bt = bin_stats(C, cyrs), bin_stats(T, tyrs)
bs = [bin_stats(S, S.win) for S in SEEDS]
brows = fv.bin_rows(comp_cells(T, tyrs), "tbl")
doc = Doc("Validation of the land-use model", "Stage 2 of the Baltimore chain: SILO", WORK)

# ------------------------------------------------------------------ PUMS vintages by model year
B_all = T.R[(T.R.section == "B composition")]
VINT = B_all.assign(v=B_all.table.str.extract(r"\[PUMS (\d+)\]")[0].astype(float)).groupby("year").v.first().dropna().astype(int)
def vlab(v): return f"{v - 4}–{str(v)[2:]}"
nfile_t = VINT[VINT.index.isin(tyrs)].nunique(); nfile_c = VINT[VINT.index.isin(cyrs)].nunique()
flat_years = [y for y in tyrs if VINT.get(y) == VINT.max()]
SC = pd.read_csv(a.seed_choice) if os.path.exists(a.seed_choice) else None
chosen_seed = int(SC.loc[SC.ssq_rel_dev.idxmin(), "seed"]) if SC is not None else None

# ------------------------------------------------------------------ data and targets
nco = T.R[T.R.section == "A totals"].geo[T.md].nunique()
ncell_c, ncell_t = len(comp_cells(C, cyrs)), len(comp_cells(T, tyrs))
nclass = comp_cells(T, tyrs).groupby(["tbl", "bin"]).ngroups
doc.section("Data and targets")
doc.para(f"The land-use model starts from the synthetic population of 2016 and simulates demographic events, household moves, construction, "
         f"employment and school enrolment year by year. The comparison covers Maryland and its {nco} counties and county equivalents. "
         f"The model is calibrated on the years {cw}. The years {tw} are not used in calibration and are tested out of sample. "
         f"This window was inspected during model development, but no parameter was estimated or calibrated on it. "
         f"The out-of-sample result is the mean of {nw} runs that differ only in the random seed; the calibration window is one run.")
doc.para(f"Targets. Household size, cars, age, sex, employment, household income and young adults living with their parents: "
         f"American Community Survey (ACS) PUMS, five-year files, shares by county. Model year $Y$ is compared with the five-year file centred on $Y$, "
         f"which ends in $Y+2$: model year {cyrs[0]} with the {vlab(VINT[cyrs[0]])} file, model year {tyrs[0]} with the {vlab(VINT[tyrs[0]])} file. "
         f"The latest file is {vlab(VINT.max())}, so model years {flat_years[0]} to {flat_years[-1]} are all compared with it and the observed series is flat over these years. "
         f"The five-year files also overlap the calibration years: the {vlab(VINT[tyrs[0]])} file contains {cyrs[-2]} and {cyrs[-1]}. "
         f"The out-of-sample test therefore rests on {nfile_t} distinct observed files and is not fully independent of the calibration data.")
doc.para("Event rates: births and deaths from the Census population estimates; marriages, divorces and moves from the ACS PUMS files as above. "
         "Jobs by county: LODES workplace counts. Commuting: ACS 2024 one-year PUMS, workers who travelled to work, all modes, and LODES 2023. "
         "Mover flows between regions: ACS county-to-county flows 2016 to 2020.")
doc.para("Tolerances. Event rates within 5\\% of the observed rate. Shares within 5 percentage points (pp) of the observed share, for every class. Jobs within 10\\%. "
         "Two quantities are controls and not tests. County population is held to the Census growth of each county: migration is scaled so that the county total "
         "follows the growth of the Census estimate. New dwellings equal the building permits of the county and year. Both are shown as input checks.")
doc.para("Spread across runs. Tables give the standard deviation (s.d.) of the runs; figures shade plus and minus two standard deviations.")
if chosen_seed is not None:
    doc.para(f"Run passed on. The activity model reads the 2024 population of run {chosen_seed}. This run is closest to the mean of the {nw} runs in 2024: "
             f"it has the smallest sum of squared relative deviations from the mean over the county populations, the Maryland households, employed persons, "
             f"students by school type and the mean commute time.")

# ------------------------------------------------------------------ headline table
def comp_summary(S, yrs):
    B = comp_cells(S, yrs); return (B.diff_pp.abs() <= 5).mean(), B.diff_pp.abs().mean(), B.diff_pp.abs().max()


def pop_ratio(S):
    A = S.pop(); return A[A.year == S.yl]


def jobs_ratio(S):
    J = S.jobs(S.yl); return J.model.sum() / J.observed.sum()


def jobs_ratio_window(S):
    J = S.R[(S.R.section == "D jobs") & S.md & S.R.year.isin(S.win)]; return J.model.sum() / J.observed.sum()


def constr_ratio(S):
    D = S.constr(); return D.model.sum() / D.observed.sum()


def seed_metrics(S):
    yrs = S.win; m = {}
    m["cells"], m["mad"], m["worst"] = comp_summary(S, yrs)
    P = pop_ratio(S); m["pop_within"] = ((P.ratio - 1).abs() <= 0.02).mean(); m["pop_max"] = (P.ratio - 1).abs().max()
    m["constr"] = constr_ratio(S); m["jobs"] = jobs_ratio(S)
    for lab, (tab, geo) in {"births": ("births per woman 15-50", "Maryland"), "deaths": (DEATHS, "all regions"), "marriages": ("new marriages share of adults", "Maryland"),
                            "divorces": ("divorces share of married", "Maryland"), "moves": ("persons who moved share (persons aged 1+)", "Maryland")}.items():
        m[lab] = ratio_window(S, tab, geo, yrs)
    cb = comp_cells(S, yrs); k = cb[(cb.tbl == "cars") & (cb.bin == "0")]; m["nocar"] = k.diff_pp.mean()
    k = cb[(cb.tbl == "household size") & (cb.bin == "1")]; m["onep"] = k.diff_pp.mean()
    return m


MC = seed_metrics(C); MT = seed_metrics(T); MS = [seed_metrics(S) for S in SEEDS]
SD = {k: np.std([m[k] for m in MS], ddof=1) if NS > 1 else np.nan for k in MT}
MM = {k: np.mean([m[k] for m in MS]) for k in MT}
doc.section("Summary of the fit")
rows = []
TESTS = [("Class shares within 5 pp, share of cells", "cells", dict(d=1, pct=True)), ("Class shares, mean absolute gap (pp)", "mad", dict(d=2)), ("Class shares, largest gap (pp)", "worst", dict(d=1)),
         ("Births, model / observed", "births", dict(d=3)), ("Deaths, model / observed", "deaths", dict(d=3)), ("Marriages, model / observed", "marriages", dict(d=3)),
         ("Divorces, model / observed", "divorces", dict(d=3)), ("Persons who moved, model / observed", "moves", dict(d=3)), ("Filled jobs, last year of the window, model / LODES", "jobs", dict(d=3)),
         ("No-car households, gap (pp)", "nocar", dict(d=2, sign=True)), ("One-person households, gap (pp)", "onep", dict(d=2, sign=True))]
CTRL = [("County population within 2\\%, share of counties", "pop_within", dict(d=0, pct=True)), ("County population, largest deviation", "pop_max", dict(d=1, pct=True)),
        ("New dwellings, model / permits", "constr", dict(d=3))]
def srow(lab, k, kw):
    sd = num(SD[k], d=kw.get("d", 2) + (0 if kw.get("pct") else 1), pct=kw.get("pct", False)) if NS > 1 else "--"
    return [lab, num(MC[k], **kw), num(MM[k], **kw), sd] + [num(m[k], **kw) for m in MS]
rows = [srow(*s) for s in TESTS]
ncol = 4 + NS
rows.append([f"\\multicolumn{{{ncol}}}{{l}}{{\\emph{{Controls (input checks, not tests)}}}}"] )
rows += [srow(*s) for s in CTRL]
doc.table(["Measure", cw, tw, hd("S.d. of", "runs")] + [f"Run {i + 1}" for i in range(NS)], rows, "L{0.36\\textwidth}rrr" + "r" * NS,
          f"Fit of the land-use model, calibration window ({cw}) and out of sample ({tw}).",
          note=f"Calibration window: one run. Out of sample: mean of {NS} runs (columns Run 1 to Run {NS} give each run). "
               f"Class shares: every county, year and class of the window ({nco} counties, {len(tyrs)} years, {nclass} classes, {ncell_t} cells per run); both classes of the binary attributes "
               f"(sex, employed, living with parents) are counted, and the share of cells within 5 pp is the mean over the runs. "
               "Gaps are model minus observed. Window ratios are the sum over the years of the model divided by the sum of the observed. "
               "Deaths: model rate of all regions against the Maryland rate. Controls: county population is held to the Census growth and new dwellings to the permits.",
          midrules=(len(TESTS),))

# ------------------------------------------------------------------ against the tolerances
doc.sub("Results against the tolerances")
ev_ok = lambda r: abs(r - 1) <= 0.05
cls = {(t, b): L for t, b, L, s, g in brows}
def bstat(t, b, k): return bt.loc[(t, b), k]
miss_cls = [(cls[k], bt.loc[k, "within"]) for k in bt.index if k in cls and bt.loc[k, "within"] < 0.95]
miss_cls.sort(key=lambda x: x[1])
rows = []
for lab, k, tol in [("Births", "births", "5\\%"), ("Deaths", "deaths", "5\\%"), ("Marriages", "marriages", "5\\%"), ("Divorces", "divorces", "5\\%"), ("Persons who moved", "moves", "5\\%"), ("Filled jobs, last year", "jobs", "10\\%")]:
    t_ = 0.10 if k == "jobs" else 0.05
    rows.append([lab, tol, num(MC[k], 3), "yes" if abs(MC[k] - 1) <= t_ else "no", num(MM[k], 3), "yes" if abs(MM[k] - 1) <= t_ else "no"])
rows.append(["Class shares, all cells", "5 pp", num(MC["cells"], 1, pct=True), "no" if MC["cells"] < 1 else "yes", num(MM["cells"], 1, pct=True), "no" if MM["cells"] < 1 else "yes"])
for L, w in miss_cls:
    k = next(k for k in cls if cls[k] == L)
    rows.append([L, "5 pp", num(bc.loc[k, "within"], 0, pct=True), "no" if bc.loc[k, "within"] < 1 else "yes", num(w, 0, pct=True), "no"])
doc.table(["Measure", "Tolerance", cw, "Met", tw, "Met"], rows, "lrrlrl", "Tested measures against their tolerances.",
          note="Event and job rows: ratio of model to observed over the window. Class-share rows: share of county-year cells within 5 pp; only classes with fewer than 95\\% of the cells within 5 pp out of sample are listed. "
               "The controls of Table 1 are not counted.", midrules=(6,))
d_y = T.ev(DEATHS, "all regions"); d_y = d_y[d_y.year.isin(tyrs)]
mv = T.ev("persons who moved share (persons aged 1+)", "Maryland"); mvc = mv[mv.year.isin(cyrs)]; mvt = mv[mv.year.isin(tyrs)]
mr = T.ev("new marriages share of adults", "Maryland"); mrc = mr[mr.year.isin(cyrs)]; mrt = mr[mr.year.isin(tyrs)]
doc.para(f"Deaths. The model has {100 * (1 - MM['deaths']):.0f}\\% fewer deaths than observed out of sample (yearly ratios "
         + ", ".join(f"{r:.2f}" for r in d_y.ratio) + f" for {tyrs[0]}--{tyrs[-1]}). The model applies the death rates of the base period and has no excess mortality of 2020 to 2022. "
         "The shortfall is largest in 2022 and shrinks by 2024.")
doc.para(f"Moves. The observed share of persons who moved falls from {100 * mvc.observed.mean():.1f}\\% in {cw} to {100 * mvt.observed.mean():.1f}\\% in {tw}, "
         f"while the model rate does not fall ({100 * mvc.model.mean():.1f}\\% and {100 * mvt.model.mean():.1f}\\%). The model therefore has {100 * (MM['moves'] - 1):.0f}\\% too many movers out of sample. "
         "Too many moves relocate more households than observed, so the residential locations passed to the activity model change faster than in reality.")
doc.para(f"Marriages. The observed marriage rate is about {100 * mrt.observed.mean():.2f}\\% of adults out of sample, the same as at the end of the calibration window, "
         f"while the model rate keeps falling with the ageing of the population ({100 * mrc.model.iloc[-1]:.2f}\\% in {cyrs[-1]}, {100 * mrt.model.iloc[-1]:.2f}\\% in {tyrs[-1]}).")
J = T.R[(T.R.section == "D jobs") & T.md].groupby("year")[["model", "observed"]].sum()
J16 = T.R[(T.R.section == "D jobs") & T.md & (T.R.year == 2016)]; J16r = (J16.model / J16.observed); n110 = int((J16r >= 1.10).sum())
doc.para(f"Jobs. Filled jobs exceed LODES by {100 * (MC['jobs'] - 1):.1f}\\% in {cyrs[-1]} and by {100 * (MM['jobs'] - 1):.1f}\\% in {tyrs[-1]}. "
         f"The excess is already in the 2016 base ({n110} counties at 1.10 or more). LODES counts jobs covered by unemployment insurance and federal civilian jobs; "
         "it leaves out the self-employed and uniformed military, which matters most in counties with military bases (St Mary's, Harford, Anne Arundel). "
         f"LODES also records the employment loss of 2020 ({num(100 * (J.observed.get(2020, np.nan) / J.observed.get(2019, np.nan) - 1), 1, sign=True)}\\% against 2019), which the model jobs do not follow until {cyrs[-1] + 1}; this raises the ratio of {cyrs[-1]}.")
e1 = T.median_share("employed (16+)", "1")
doc.para(f"Employment. The employed share is {abs(bstat('employed (16+)', '1', 'bias')):.1f} pp too low out of sample, and only {100 * bstat('employed (16+)', '1', 'within'):.0f}\\% of the cells are within 5 pp. "
         f"The county median of the model falls from {e1.model.get(tyrs[0] - 1, np.nan):.1f}\\% in {tyrs[0] - 1} to {e1.model.get(tyrs[0], np.nan):.1f}\\% in {tyrs[0]} (Fig. 3b). "
         f"The number of jobs, an input of the model, falls by {100 * (1 - J.model.get(tyrs[0]) / J.model.get(tyrs[0] - 1)):.0f}\\% from {tyrs[0] - 1} to {tyrs[0]}, and the employed share follows it. "
         "The synthetic base population also has too few employed persons (2.5 pp in Maryland), and this carries into every year.")
B24 = comp_cells(T, [T.yl])
def top(tbl, b, n=2, sign=None):
    d = B24[(B24.tbl == tbl) & (B24.bin == b)].copy(); d = d.reindex(d.diff_pp.abs().sort_values(ascending=False).index).head(n)
    return ", ".join(f"{NAMES[int(g)]} {num(v, 0, sign=True)} pp" for g, v in zip(d.geo, d.diff_pp))
doc.para(f"Household structure and income. Out of sample the model has too few two-person households ({num(bstat('household size', '2', 'bias'), 1, sign=True)} pp) and too many young adults living with their parents "
         f"({num(bstat('adults 18-34 living with parents', '1', 'bias'), 1, sign=True)} pp; largest gaps {top('adults 18-34 living with parents', '1')} in {T.yl}). "
         f"The model and the observed series move apart after {cyrs[-1]} for young adults with their parents and for persons aged 65 and over (Fig. 3c, d); part of this is the flat observed series of {flat_years[0]}--{flat_years[-1]}. "
         f"The income tails are wrong in some counties: households under \\$25k {top('income class (2016 $)', '0')}, and \\$150k or more {top('income class (2016 $)', '5')} in {T.yl}. "
         "Model incomes grow with real wages only, so counties whose income distribution changed faster than the regional trend drift from the ACS.")

# ------------------------------------------------------------------ events
doc.section("Events")
rows = []
for tab, geo in EVT:
    cr = ratio_window(C, tab, geo, cyrs); tr = ratio_window(T, tab, geo, tyrs); sr = [ratio_window(S, tab, geo, S.win) for S in SEEDS]
    d = T.ev(tab, geo); d = d[d.year.isin(tyrs)]; obs_rate = d.observed.mean()
    if not np.isfinite(tr): continue
    area = "Maryland" if tab == DEATHS or geo == "Maryland" else tx(geo)
    rows.append([EVLAB.get(tab, tx(tab)), area, num(obs_rate * 100, 2), num(cr, 3), num(tr, 3), num(np.std(sr, ddof=1), 4) if NS > 1 else "--"])
doc.table(["Event", "Area", hd("Observed rate", f"{tw} (\\%)"), hd("Ratio", cw), hd("Ratio", tw), hd("S.d. of", "runs")], rows, "L{0.36\\textwidth}lrrrr",
          "Event rates against observed rates, model divided by observed.",
          note="Ratio: sum over the years of the window of the model rate divided by the sum of the observed rate. S.d. of runs: standard deviation of the ratio across the runs. "
               "Deaths: the model rate is that of all regions of the model, the observed rate that of Maryland.")
T.app_a(); doc.figure(f"{FIG}/fig_v2_a.pdf", f"Event rates by year, model and observed. Shaded blue: plus and minus two standard deviations of the runs. Grey: tolerance of 5\\% around the observed rate.")

# ------------------------------------------------------------------ per bin
doc.section("Composition by class")
rows = []
prev = None
for (t, b, L, s, g) in brows:
    k = (t, b); sd = np.std([x.loc[k, "bias"] for x in bs], ddof=1) if NS > 1 else np.nan
    rows.append([g if g != prev else "", L, num(bc.loc[k, "bias"], 2, sign=True), num(bc.loc[k, "within"], 0, pct=True), num(bt.loc[k, "bias"], 2, sign=True), num(bt.loc[k, "mad"], 2),
                 num(bt.loc[k, "within"], 0, pct=True), num(bt.loc[k, "worst"], 1), num(sd, 2)]); prev = g
doc.longtable(["Attribute", "Class", hd("Mean gap", cw), hd("Within", "5 pp"), hd("Mean gap", tw), hd("Mean", "abs. gap"), hd("Within", "5 pp"), hd("Largest", "gap"), hd("S.d. of", "runs")], rows, "L{0.15\\textwidth}L{0.2\\textwidth}rrrrrrr",
              f"Shares of each class against the ACS in Maryland counties: calibration window and out of sample, in percentage points.", small="\\scriptsize")
doc.para(f"Gap: model minus ACS share, in percentage points, averaged over the counties and years of the window. Within 5 pp: share of county-year cells with a gap of at most 5 points. "
         f"Largest gap: largest absolute gap of any cell. S.d. of runs: standard deviation across the {NS} runs of the mean gap in the out-of-sample window. "
         f"Cells: {ncell_c} in the calibration window, {ncell_t} out of sample ({nclass} classes; the second class of sex, employment and living with parents is not listed, "
         f"its gap is the negative of the class shown). Out of sample, model years {flat_years[0]}--{flat_years[-1]} share one observed file, so the cells of these years are not independent.")
T.app_b(); doc.figure(f"{FIG}/fig_v2_b.pdf", f"Model minus ACS share for every class and county in {T.yl}, in percentage points. Counties are sorted by population. Numbers are shown for gaps beyond 5 points.")
T.app_d(); doc.figure(f"{FIG}/fig_v2_d2.pdf", f"County median share by year, model and observed: households without a car, employed persons, young adults living with their parents and persons aged 65 and over. "
                      f"The model values of every year are the mean of the {nw} runs. The observed values of {flat_years[0]}--{flat_years[-1]} come from one five-year file.")

# ------------------------------------------------------------------ cars over time
fig = ps.new_figure(3.9); gs = fig.add_gridspec(2, 2); out = {}
SH = [("cars", "0", "No car"), ("cars", "1", "One car"), ("cars", "2", "Two cars"), ("cars", "3", "Three or more cars")]
for k, (tbl, b, lab) in enumerate(SH):
    ax = fig.add_subplot(gs[k // 2, k % 2]); md = T.median_share(tbl, b)
    ax.plot(md.index, md.observed, color=ps.OBSERVED, marker="s", ms=3.2); ax.plot(md.index, md.model, color=ps.MODEL, marker="o", ms=3.2)
    ax.axvline(min(tyrs) - 0.5, color=ps.AXIS, lw=0.8, ls="--")
    lo, hi = np.nanmin(md.values), np.nanmax(md.values); pad = max(2.0, (hi - lo) * 0.4); ax.set_ylim(max(0, lo - pad), hi + pad)
    ax.set_xticks(md.index[::2]); fv.heading(ax, lab); ax.set_ylabel("County median share (%)")
    if k >= 2: ax.set_xlabel("Year")
    out["abcd"[k]] = ax
fv.fig_legend(fig, ["model", "observed"])
for k, ax in out.items(): ps.panel_label(ax, k)
p = ps.finish(fig, f"{FIG}/fig_cars")
doc.figure(p, f"Share of households by number of cars, county median by year, model and ACS. The dashed line separates the calibration window from the years tested out of sample; "
              f"the model values of every year are the mean of the {nw} runs.")

# ------------------------------------------------------------------ seeds
doc.section(f"Spread across the {nw} runs")
ev_keys = ["births", "deaths", "marriages", "divorces", "moves", "jobs"]
mx_sd = max(SD[k] for k in ev_keys if np.isfinite(SD[k])) if NS > 1 else np.nan
doc.para(f"The {NS} runs share the population, the parameters and the inputs. They differ in the random seed. "
         + (f"The standard deviation across runs of the event and job ratios is at most {mx_sd:.4f}. The share of class cells within 5 pp has a standard deviation of {100 * SD['cells']:.1f} points, "
            f"and the largest single gap one of {SD['worst']:.2f} points. The mean absolute gap of the class shares ranges from "
            f"{min(m['mad'] for m in MS):.2f} to {max(m['mad'] for m in MS):.2f} percentage points across the runs." if NS > 1 else ""))
fig, axs = ps.figure(4.8, ncols=2)
labs = [("births", "Births"), ("deaths", "Deaths"), ("marriages", "Marriages"), ("divorces", "Divorces"), ("moves", "Moves"), ("jobs", "Jobs")]
ax = axs[0]; K.ratio_band(ax, 0.05)
y = K.rows_axis(ax, [l for _, l in labs])
for yy, (k, l) in zip(y, labs):
    v = np.array([m[k] for m in MS]); ax.scatter(v, np.full(len(v), yy), s=12, color=ps.SEED_BAND, edgecolor=ps.MODEL, lw=0.6, zorder=3); ax.scatter([v.mean()], [yy], s=22, marker="|", color=ps.INK, lw=1.5, zorder=4)
ax.set_xlabel("Model ÷ observed\n(ratio)"); K.title(ax, "a", "Ratios")
ax = axs[1]
y = K.rows_axis(ax, [r[2] for r in brows]); ax.axvspan(-5, 5, color=ps.TOL_BAND, lw=0, zorder=0); ax.axvline(0, color=ps.INK2, lw=0.7)
for yy, (t, b, L, s, g) in zip(y, brows):
    v = np.array([x.loc[(t, b), "bias"] for x in bs]); ax.scatter(v, np.full(len(v), yy), s=8, color=ps.SEED_BAND, edgecolor=ps.MODEL, lw=0.5, zorder=3)
ax.set_xlabel("Mean gap, model − observed\n(percentage points)"); K.title(ax, "b", "Class shares")
fig.legend(handles=[Line2D([], [], marker="o", ls="", mfc=ps.SEED_BAND, mec=ps.MODEL, ms=4, label="One run"), Line2D([], [], color=ps.INK, marker="|", ls="", ms=7, mew=1.5, label="Mean of the runs"), K.h_tol()],
           loc="outside upper center", ncol=3)
doc.figure(ps.finish(fig, f"{FIG}/fig_seeds"), f"Each run separately, out of sample ({tw}). Left: ratio of the model to the observed value. Right: mean gap of each class share, in percentage points.")

# ------------------------------------------------------------------ county totals
doc.section("Totals by county")
P = T.pop(); Pl = P[P.year == T.yl].set_index("county")
J = T.R[(T.R.section == "D jobs") & T.md & (T.R.year == T.yl)].groupby("geo")[["model", "observed"]].sum(); J.index = J.index.astype(int)
Dc = T.constr(); Cc = C.constr()
Pc = C.pop(); Pcl = Pc[Pc.year == C.yl].set_index("county")
pep = pd.read_csv(f"{V}/data/raw/pep/co-est2025-alldata.csv", encoding="latin-1", dtype={"STATE": str, "COUNTY": str}); pep = pep[(pep.SUMLEV == 50) & (pep.STATE == "24")]
pep = pep.set_index((pep.STATE + pep.COUNTY).astype(int))[f"POPESTIMATE{T.yl}"]
rows = []
order = Pl.sort_values("observed", ascending=False).index
for c in order:
    rows.append([tx(NAMES[c]), thousands(pep.get(c, np.nan)), thousands(Pl.observed[c]), num(J.model[c] / J.observed[c], 3) if c in J.index else "--",
                 num(Pcl.ratio.get(c, np.nan), 3), num(Pl.ratio[c], 3), num(Cc.ratio.get(c, np.nan), 2), num(Dc.ratio.get(c, np.nan), 2)])
doc.table(["County", hd("Census", f"estimate {T.yl}"), hd("Census growth", "on the synthetic", "2016 population"), hd("Jobs", f"ratio {T.yl}"),
           hd("Population", f"ratio {C.yl}", "(control)"), hd("Population", f"ratio {T.yl}", "(control)"), hd("New dwellings", cw, "(control)"), hd("New dwellings", tw, "(control)")], rows, "lrrrrrrr",
          "Jobs, population and new dwellings by county, model divided by observed.",
          note=f"Census estimate: county population of July {T.yl}, all persons. Census growth on the synthetic 2016 population: the synthetic household population of 2016 grown with the Census growth "
               f"of the county from 2016 to {T.yl}; the population ratio divides the model by this value. Population and new dwellings are controls: the model holds county population to the Census growth "
               "and builds the permitted dwellings, so ratios near one are expected. Jobs: filled jobs against LODES. The population of the calibration window is one run, out of sample the mean of the runs.",
          small="\\scriptsize")
# figure: population (2 % classes) and jobs (10 % classes) by county and year
PB = [0, 0.94, 0.96, 0.98, 1.02, 1.04, 1.06, np.inf]; PLAB = ["< 0.94", "0.94–0.96", "0.96–0.98", "Within ±2 %", "1.02–1.04", "1.04–1.06", "> 1.06"]
JB = [0, 0.5, 0.75, 0.9, 1.1, 1.25, 1.5, np.inf]; JLAB = ps.RATIO_LABELS
fig = ps.new_figure(5.2); gs = fig.add_gridspec(1, 2); ordc = T.by_size()
Jall = T.R[(T.R.section == "D jobs") & T.md].groupby(["geo", "year"])[["model", "observed"]].sum().reset_index(); Jall["ratio"] = Jall.model / Jall.observed; Jall["county"] = Jall.geo.astype(int)
for k, (D_, bins_, labs_, tol, fm, ttl) in enumerate([(P, PB, PLAB, 0.02, "{:.3f}", "Population (control), by year"), (Jall, JB, JLAB, 0.10, "{:.2f}", "Jobs, by year")]):
    ax = fig.add_subplot(gs[k]); M = D_.pivot_table(index="county", columns="year", values="ratio").reindex(ordc)
    M = M[[y_ for y_ in M.columns if y_ == M.columns.min() or y_ in T.win]]; H = M.values
    ax.grid(False); ax.imshow(H, cmap=ListedColormap(ps.RATIO_COLORS), norm=BoundaryNorm([0.0001] + bins_[1:-1] + [100], 7), aspect="auto")
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            v = H[i, j]
            if np.isfinite(v) and abs(v - 1) > tol + 1e-9:
                ci = int(np.digitize(v, bins_[1:-1])); ax.text(j, i, fm.format(v), ha="center", va="center", fontsize=ps.FONT, color=ps.INK if ci in (2, 3, 4) else "white")
    ax.axvline(0.5, color="white", lw=3)
    ax.set_yticks(range(len(ordc))); ax.set_yticklabels([NAMES[c] for c in ordc] if k == 0 else [""] * len(ordc)); ax.set_xticks(range(H.shape[1]))
    ax.set_xticklabels([str(y_) for y_ in M.columns], rotation=45, ha="right", rotation_mode="anchor"); ax.tick_params(length=0)
    ax.set_xlabel(f"{ttl}\n(2016, then {T.win[0]}–{T.win[-1]})")
    if k == 1: ax.set_yticks([])
    ax.legend(handles=[Patch(facecolor=c_, edgecolor=ps.AXIS, lw=0.3, label=l_) for c_, l_ in zip(ps.RATIO_COLORS, labs_)], loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=ps.TICK,
              handlelength=1.2, handleheight=0.9, frameon=False)
p = ps.finish(fig, f"{FIG}/fig_county_years", panel_labels="ab")
doc.figure(p, f"Population and jobs by county and year, model divided by observed. Columns: the base year 2016 and the out-of-sample years; the calibration years are not shown. "
              f"Population (a, a control) is classed on a 2\\% scale and jobs (b) on a 10\\% scale; numbers are shown outside the tolerance.")

# ------------------------------------------------------------------ moves and flows
doc.section("Moves and mover flows")
mv = T.ev("persons who moved share (persons aged 1+)", "Maryland"); mv = mv[mv.year.isin(tyrs)]
rows = [[str(int(r.year)), vlab(int(VINT.get(int(r.year)))), num(r.observed * 100, 2), num(r.model * 100, 2), num(r.ratio, 3), num(r.seed_sd / r.observed, 3) if "seed_sd" in mv else "--"] for r in mv.itertuples()]
doc.table(["Model year", "ACS file", "Observed (\\%)", "Model (\\%)", "Ratio", hd("S.d. of runs", "(ratio)")], rows, "llrrrr", "Share of persons who moved during the year, Maryland.",
          note="Observed: ACS five-year file centred on the model year, persons aged 1 and over who lived at another address one year earlier. S.d. of runs: standard deviation of the model rate across the runs divided by the observed rate.")
F = T.R[(T.R.section == "F flows") & (T.R.year == T.yl)]
FL = {"moving households staying in their region [ACS flows 2016-20]": "Moving households that stay in their region", "correlation of region-to-region mover flows with the ACS flows 2016-20 (all pairs)": "Correlation with ACS flows, all region pairs",
      "correlation of region-to-region mover flows with the ACS flows 2016-20 (between regions)": "Correlation with ACS flows, between regions", "Maryland movers moving to another state [ACS flows 2016-20]": "Maryland movers who move to another state"}
GEO = {"24": "Maryland", "all regions": "All regions"}
rows = []
for r in F.itertuples():
    corr = r.table.startswith("correlation")
    rows.append([tx(FL.get(r.table, r.table)), GEO.get(r.geo, tx(r.geo)), "--" if corr else num(r.observed, 3), num(r.model, 3), "--" if corr else num(r.ratio, 3)])
doc.table(["Measure", "Area", "ACS", "Model", "Ratio"], rows, "llrrr", f"Mover flows between regions, model year {T.yl}, against the ACS flows 2016 to 2020.",
          note=f"The ACS flows are the latest county-to-county flows (2016--2020); the model year is {T.yl}. Correlation: Pearson correlation of the model flows between regions with the ACS flows (a single value).")

# ------------------------------------------------------------------ work
doc.section("Work and commuting")
E = T.R[(T.R.section == "E commute") & (T.R.year == T.yl) & (T.R.geo == "24")]
acs = pd.read_csv(f"{a.acs_commute}/acs_commute.csv"); acsF = pd.read_csv(f"{a.acs_commute}/acs_flows.csv")
A1 = lambda m: float(acs[(acs.vintage == "acs2024") & (acs.area == "Maryland") & (acs.metric == m)].value.iloc[0])
f24 = acsF[acsF.vintage == "acs2024"]; h24 = f24[f24.home_unit.astype(str).str[:2] == "24"]; in_md = h24[h24.work_unit.astype(str).str[:2] == "24"].workers.sum() / h24.workers.sum()
def erow(key):
    r = E[E.table.str.contains(key, regex=False)]; return r.iloc[0] if len(r) else None
own = erow("located in the home county"); ttm = erow("travel time to work, mean"); ttd = erow("travel time to work, median"); wmd = erow("employed in Maryland")
lod_y = own.table.split("[")[-1].rstrip("]") if own is not None else "LODES"
rows = [[f"Jobs in the home county, share of Maryland-resident jobs in Maryland ({lod_y})", num(own.observed, 2), num(own.model, 2), num(own.model / own.observed, 3)],
        ["Workers employed in Maryland, share of Maryland-resident workers (ACS 2024)", num(in_md, 2), num(wmd.model, 2), num(wmd.model / in_md, 3)],
        ["Travel time to work, mean (min; ACS 2024)", num(A1("mean travel time to work"), 1), num(ttm.model, 1), num(ttm.model / A1("mean travel time to work"), 3)],
        ["Travel time to work, median (min; ACS 2024)", num(A1("median travel time to work"), 1), num(ttd.model, 1), num(ttd.model / A1("median travel time to work"), 3)]]
doc.table(["Measure, Maryland residents", "Observed", "Model", "Ratio"], rows, "L{0.55\\textwidth}rrr", f"Commuting of Maryland residents, model year {T.yl}.",
          note="ACS 2024: one-year PUMS, workers aged 16 and over who travelled to work in the reference week (not working at home), all modes, the extraction used in the activity-model validation. "
               f"{lod_y}: jobs by home and work county. Model: every worker with a job; travel time from the AM-peak car skim of the zone pair. Shares as fractions.")
doc.para(f"The share of jobs in the home county is {own.model:.2f} in the model against {own.observed:.2f} in LODES. LODES counts jobs, not workers, and places them at the address that the employer "
         "reports, which for employers with several sites is often the head office; a worker with two jobs counts twice. The ACS place-of-work answer of the workers gives about 54\\% working in the home "
         "area for Maryland in 2024, and the same workplaces agree with it in the activity-model validation (54.4\\% against 54.0\\%). The LODES share is therefore a lower bound and the gap here is mostly "
         "a difference of definition.")
doc.para(f"The car skim used for the model travel time is the fixed AM-peak skim of the upstream stages. In the traffic assignment the congested car times are 18--31\\% shorter than this skim, "
         f"so the agreement of the mean ({ttm.model:.1f} against {A1('mean travel time to work'):.1f} min) depends on the skim. The ACS answers bunch at round values (30 min), which raises the observed median.")
J2 = T.R[(T.R.section == "B2 statewide") & (T.R.year == T.yl)]
em = J2[J2.table == "employed share by age and sex"]
rows = [["Employed share, 16 age and sex classes", "mean absolute gap", "--", "--", num(em.diff_pp.abs().mean(), 1)]]
for r in J2[J2.table == "workers per household"].itertuples():
    rows.append(["Households by number of workers" if r.bin == "0" else "", f"{r.bin} worker" + ("s" if r.bin != "1" else ""), num(r.observed * 100, 1), num(r.model * 100, 1), num(r.diff_pp, 1, sign=True)])
for r in J2[J2.table.str.startswith("persons 18-34")].itertuples():
    rows.append(["Persons aged 18--34 in non-family households", "living with others", num(r.observed * 100, 1), num(r.model * 100, 1), num(r.diff_pp, 1, sign=True)])
nf = J2[J2.table.str.startswith("persons 18-34")].iloc[0]
NF = T.R[(T.R.section == "B2 statewide") & T.R.table.str.startswith("persons 18-34") & T.R.year.isin(tyrs)]; nfy = int((NF.diff_pp.abs() > 5).sum())
doc.table(["Measure", "Class", "Observed (\\%)", "Model (\\%)", "Gap (pp)"], rows, "L{0.32\\textwidth}lrrr", f"Employment and household structure, Maryland, model year {T.yl}.",
          note="Observed: ACS five-year PUMS file as in the composition tables. Gap: model minus observed.", midrules=(1, len(rows) - 1))
doc.para(f"Among persons aged 18 to 34 in non-family households, {100 * nf.model:.0f}\\% live with others (roommates) in the model against {100 * nf.observed:.0f}\\% observed, "
         f"a gap of {num(nf.diff_pp, 1, sign=True)} pp. The gap is outside the tolerance in {nfy} of the {len(tyrs)} out-of-sample years.")
pages, errs, over = doc.build(a.out)
