#!/usr/bin/env python3
"""Job control totals consistent with the number of employed residents (Baltimore 2026, consistency of occupation and workplace).

The model area is closed for commuting: every employed person holds one job of the area. The LODES growth path of the job
control (build_job_controls.py) grows the jobs of the area by 2.4 % 2016-2024 while its persons 16+ grow by 5.0 % (PEP) at an
ACS employed share of 65 % (LODES counts UI-covered primary jobs by workplace; the ACS counts employed residents incl.
self-employed), and the SILO base has 62.9 % of Maryland residents 16+ employed against 65.5 % in the ACS 2014-18. Before the
consistency check this gap was hidden by persons who shared another person's job id (in-migrant copies). The employment model applies the
Maryland employment rates by age and sex to the whole area, so the control total of year Y is set to
    jobs(Y) = N16(2016) x Pop(Y) / Pop(2016) x s(Y) / (1 - v(Y))
with N16(2016) the persons 16+ of the SILO base population (all regions), Pop(Y) the population control total of the area
(input/assumptions/populationControlTotalByRegion.csv, Census PEP), s(Y) the ACS employed share of Maryland residents 16+ in
households (ESR 1, 2, 4, 5; PUMS 5-year file centred on Y, as in validate_landuse.py: vintage min(Y + 2, 2024)) and v(Y) the
Maryland JOLTS job-openings rate (annual mean of the monthly rates,
openings / (employment + openings), BLS series JTS000000240000000JOR, data/raw/jolts/). LODES (and QCEW for 2024-2026) keep
the distribution by zone and job type: every zone and type of year Y is multiplied by jobs(Y) / LODES-based total(Y). Years
after 2024 keep the 2024 share and rate with the population target of the year. The Maryland share is applied to the
non-Maryland zones too (no ACS of those states here; the employment model uses the Maryland rates there as well).
Input:  2_silo/input/assumptions/jobControlTotals_lodes.csv (copy of the LODES-based file, made on the first run)
Output: 2_silo/input/assumptions/jobControlTotals.csv; data/silo_target_job_totals.csv (year, s, v, persons 16+, jobs, factor)"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, os, shutil, zipfile
import numpy as np, pandas as pd

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; S = f"{V}/2_silo"
A = f"{S}/input/assumptions"
if not os.path.exists(f"{A}/jobControlTotals_lodes.csv"): shutil.copy(f"{A}/jobControlTotals.csv", f"{A}/jobControlTotals_lodes.csv")
J = pd.read_csv(f"{A}/jobControlTotals_lodes.csv")
d = json.load(open(f"{V}/data/raw/jolts/jolts_openings_rate_md_us_2016_2024.json"))
md = [s for s in d["Results"]["series"] if s["seriesID"] == "JTS000000240000000JOR"][0]["data"]
v = pd.DataFrame([(int(x["year"]), float(x["value"])) for x in md if x["period"] != "M13"], columns=["year", "rate"]).groupby("year").rate.mean() / 100
W = {}
for vint in sorted({min(y + 2, 2024) for y in range(2016, 2025)}):
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_{vint}_5yr/csv_pmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        P = pd.read_csv(zf.open(n), usecols=lambda c: c in ["PWGTP", "AGEP", "ESR", "RELP", "RELSHIPP"], low_memory=False)
    P = P[~(P.RELP.isin([16, 17]) if "RELP" in P else P.RELSHIPP.isin([37, 38]))]
    q = P[P.AGEP >= 16]; W[vint] = float((q.PWGTP * q.ESR.isin([1, 2, 4, 5])).sum() / q.PWGTP.sum())
pp = pd.read_csv(f"{S}/input/microData/pp_2016.csv", usecols=["age"]); N16 = int((pp.age >= 16).sum())
pop = pd.read_csv(f"{A}/populationControlTotalByRegion.csv").groupby("Year").Population.sum()
rows = []
for y in range(2016, 2027):
    yy = min(y, 2024); s = W[min(yy + 2, 2024)]; jobs = N16 * pop[y] / pop[2016] * s / (1 - v[yy])
    cols = [c for c in J.columns if c != "SMZ" and c.endswith(f"{y % 100:02d}")]
    tot = J[cols].values.sum(); f = jobs / tot; J[cols] = (J[cols] * f).round(1)
    rows.append(dict(year=y, acs_employed_share_md=s, jolts_openings_rate_md=v[yy], persons16_area=N16 * pop[y] / pop[2016], jobs_target=jobs, lodes_total=tot, factor=f))
J.to_csv(f"{A}/jobControlTotals.csv", index=False)
T = pd.DataFrame(rows); T.to_csv(f"{V}/data/silo_target_job_totals.csv", index=False); print(T.round(4).to_string(index=False))
