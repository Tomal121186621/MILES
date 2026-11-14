#!/usr/bin/env python3
"""Deliverable tables of the final five-seed run (2026-10-29; base_v4, rts3_dcacs, QCEW jobs, state employment rates, end-of-year
alignment, local marriage market, intercensal population series; levers of calibration round 49): seed mean and 90 % band
(mean +- 1.645 s.d.) by year 2017-2024, split into the calibration window (2017-2020) and out of sample (2021-2024).
Imposed by construction (consistency checks, not tests): county population (regional control), employment level (alignment to the
yearly ACS rates), vacancy share of jobs (QCEW x JOLTS job input).  Everything else is a test.
Reads data/silo_validation_oos_s<k>.parquet, run/logs/oos_s<k>.log and the seeds' microdata (dwelling vacancy).
Writes data/silo_final_tables.csv and prints Markdown.   Usage: python3 landuse/validation/final_tables.py [n_seeds=5]
Environment: SILO_SEEDS = seed-run prefix (default oos_s; e.g. oos_respec_s), SILO_OUT_SUFFIX = suffix of the output files (default none)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re, sys, numpy as np, pandas as pd
PFX = os.environ.get("SILO_SEEDS", "oos_s"); SUF = os.environ.get("SILO_OUT_SUFFIX", "")
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
Z = pd.read_csv(f"{S}/input/zoneSystem.csv").set_index("ZoneId")
ACS_HOMECTY = {"with WFH": 0.659, "without WFH": 0.622}   # ACS 2016-20 county-to-county commuting flows, Maryland residents (in-state workplaces)
rows = []
def add(k, q, y, m, o=np.nan, kind="test"): rows.append(dict(seed=k, quantity=q, year=y, model=m, observed=o, kind=kind))
for k in range(1, n + 1):
    R = pd.read_parquet(f"{V}/data/silo_validation_{PFX}{k}.parquet"); R["geo"] = R.geo.astype(str); md = R.geo.str.match(r"^24\d{3}$")
    for y, a in R[(R.section == "A totals") & md].groupby("year"):
        add(k, "MD population / PEP", y, a.model.sum() / a.observed.sum(), 1.0, "imposed")
        add(k, "MD counties within +-2 % of PEP", y, (a.ratio.sub(1).abs() <= .02).sum(), 24, "imposed")
    g = lambda sec, key: R[(R.section == sec) & R.table.str.contains(key, regex=False)]
    for y, d in g("B composition", "employed (16+)").query("geo == '24'").groupby("year"):
        d = d[d["bin"].astype(str) == "1"]; add(k, "MD employed share 16+", y, d.model.mean(), d.observed.mean(), "imposed")
    for y, d in g("D jobs", "vacant share of jobs").groupby("year"): add(k, "vacant share of jobs (year end)", y, d.model.mean(), d.observed.mean(), "imposed")
    for tbl, lab in [("household size", "household size"), ("cars", "cars")]:
        for (y, b), d in g("B composition", tbl).query("geo == '24'").groupby(["year", "bin"]): add(k, f"MD households, {lab} {b}", y, d.model.mean(), d.observed.mean())
    for y, d in g("E commute", "home county").query("geo == '24'").groupby("year"):
        add(k, "same county (MD workplaces), vs LODES", y, d.model.mean(), d.observed.mean())
        for w, o in ACS_HOMECTY.items(): add(k, f"same county vs ACS 2016-20 {w}", y, d.model.mean(), o)
    for y, d in g("E commute", "employed in Maryland").groupby("year"): add(k, "MD residents working in MD", y, d.model.mean(), d.observed.mean())
    for y, d in g("E commute", "travel time to work, mean").groupby("year"): add(k, "mean car time to work (ACS: all modes)", y, d.model.mean(), d.observed.mean())
    for y, d in g("F flows", "correlation of region-to-region mover flows with the ACS flows 2016-20 (all pairs)").groupby("year"): add(k, "mover flows correlation vs ACS (all pairs)", y, d.model.mean(), 1.0)
    for y, d in g("F flows", "staying in their region").groupby("year"): add(k, "moving households staying in region", y, d.model.mean(), d.observed.mean())
    for t_, lab in [("births per woman", "births per woman 15-50"), ("new marriages", "marriages per adult"), ("divorces share", "divorces per married"), ("persons who moved", "persons who moved"), ("deaths share", "deaths per person")]:
        for y, d in g("C events", t_).groupby("year"): add(k, lab, y, d.model.mean(), d.observed.mean())
    D2 = R[(R.section == "D2 construction") & md]
    for y, d in D2.groupby("year"): add(k, "new dwellings / permits (MD)", y, d.model.sum() / d.observed.sum(), 1.0, "imposed")   # 2026-10-29: county permits imposed each year
    log = open(f"{S}/run/logs/{PFX}{k}.log").read()
    jj = re.findall(r"Job-to-job: (\d+) searches, (\d+) changes", log); un = re.findall(r"Encountered (\d+) cases where household wanted to inmigrate", log)
    cons = re.findall(r"Job consistency (\d{4}): (\d+) employed", log)
    for i, (s_, c_) in enumerate(jj):
        y = 2016 + i; emp = float(cons[i][1]) if i < len(cons) else np.nan; add(k, "job-to-job changes / employed (JOLTS quits 25.2 %)", y + 1, int(c_) / emp, 0.252)
    for i, u in enumerate(un): add(k, "unplaced in-migrant households", 2016 + i + 1, int(u))
    O = f"{S}/run/base/scenOutput/{PFX}{k}/microData"
    for y in range(2016, 2024):
        fdd = f"{O}/dd_{y}.csv" if os.path.exists(f"{O}/dd_{y}.csv") else f"{O}/futureYears/dd_{y}.csv"
        d = pd.read_csv(fdd, usecols=["zone", "hhID"]); d = d[d.zone.map(Z.STFIPS) == 24]; add(k, "MD dwelling vacancy (all dwellings)", y + 1, (d.hhID <= 0).mean())
T = pd.DataFrame(rows); T.to_csv(f"{V}/data/silo_final_tables_seeds{SUF}.csv", index=False)
G = T.groupby(["kind", "quantity", "year"]).agg(mean=("model", "mean"), sd=("model", "std"), observed=("observed", "first")).reset_index()
G["lo"] = G["mean"] - 1.645 * G.sd.fillna(0); G["hi"] = G["mean"] + 1.645 * G.sd.fillna(0); G.to_csv(f"{V}/data/silo_final_tables{SUF}.csv", index=False)
W = G[G.year.between(2017, 2024)].assign(window=lambda x: np.where(x.year <= 2020, "2017-20 calibration", "2021-24 out of sample"))
S_ = W.groupby(["kind", "quantity", "window"]).agg(model=("mean", "mean"), observed=("observed", "mean")).unstack("window").round(4)
print(S_.to_string())
