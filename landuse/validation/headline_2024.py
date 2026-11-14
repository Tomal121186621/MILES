#!/usr/bin/env python3
"""Headline out-of-sample numbers, Maryland 2024 (dwellings: 2021-2024 sums), per seed and as mean with the 90 % band across seeds
(mean +- 1.645 s.d.). Households from the seed microdata (occupied dwellings in Maryland zones) against ACS PUMS 2020-24 5-year.
Output data/silo_headline_2024.csv.  Usage: python3 landuse/validation/headline_2024.py [n_seeds=5] [suffix='']"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, sys, zipfile
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; S = f"{V}/2_silo"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 5; sfx = sys.argv[2] if len(sys.argv) > 2 else ""
Z = pd.read_csv(f"{S}/input/zoneSystem.csv", usecols=["ZoneId", "STFIPS"]).set_index("ZoneId").STFIPS
with zipfile.ZipFile(f"{ROOT}/inputs/pums_2024_5yr/csv_hmd.zip") as zf:
    H = pd.read_csv(zf.open([x for x in zf.namelist() if x.endswith(".csv")][0]), usecols=lambda c: c in ["WGTP", "NP", "TYPE", "TYPEHUGQ"])
hh_obs = H[(H[("TYPE" if "TYPE" in H else "TYPEHUGQ")] == 1) & (H.NP > 0)].WGTP.sum()
rows = []
for k in range(1, n + 1):
    R = pd.read_parquet(f"{V}/data/silo_validation_oos_s{k}{sfx}.parquet"); R["geo"] = R.geo.astype(str); md = R.geo.str.match(r"^24\d{3}$"); y = R[R.year == 2024]
    A = y[(y.section == "A totals") & md]; d = pd.read_csv(f"{S}/run/base/scenOutput/oos_s{k}{sfx}/microData/futureYears/dd_2024.csv", usecols=["zone", "hhID"])
    D2 = R[(R.section == "D2 construction") & R.year.between(2021, 2024) & md]; Dc = D2.groupby("geo")[["model", "observed"]].sum()
    g = lambda sec, key, geo="24": y[(y.section == sec) & y.table.str.contains(key, regex=False) & (y.geo.isin([geo, "all regions", "24", "Maryland"]))]
    emp = y[(y.section == "B composition") & (y.geo == "24") & y.table.str.startswith("employed") & (y["bin"].astype(str) == "1")]
    rows.append(dict(seed=k, population=A.model.sum(), population_obs=A.observed.sum(), counties_2pct=int((A.ratio.sub(1).abs() <= .02).sum()), counties_5pct=int((A.ratio.sub(1).abs() <= .05).sum()),
                     households=((d.hhID > 0) & (d.zone.map(Z) == 24)).sum(), households_obs=hh_obs,
                     dwellings_2021_24=D2.model.sum(), permits_2021_24=D2.observed.sum(), dwelling_counties_25pct=int(((Dc.model / Dc.observed).sub(1).abs() <= .25).sum()),
                     employed_16plus=emp.model.mean(), employed_16plus_obs=emp.observed.mean(),
                     work_in_md=g("E commute", "employed in Maryland").model.mean(), work_in_md_obs=g("E commute", "employed in Maryland").observed.mean(),
                     commute_mean=g("E commute", "travel time to work, mean").model.mean(), commute_mean_obs=g("E commute", "travel time to work, mean").observed.mean(),
                     home_county=g("E commute", "home county").model.mean(), home_county_lodes=g("E commute", "home county").observed.mean(),
                     moves=g("C events", "persons who moved").model.mean(), moves_obs=g("C events", "persons who moved").observed.mean()))
T = pd.DataFrame(rows); T.to_csv(f"{V}/data/silo_headline_2024{sfx}.csv", index=False)
m, s = T.mean(numeric_only=True), T.std(numeric_only=True)
for c in [c for c in T.columns if c != "seed" and not c.endswith("_obs") and c not in ("permits_2021_24", "home_county_lodes")]:
    print(f"{c:24s} {m[c]:14.4f}  90% [{m[c] - 1.645 * s[c]:.4f}, {m[c] + 1.645 * s[c]:.4f}]")
print({c: round(m[c], 4) for c in T.columns if c.endswith("_obs") or c in ("permits_2021_24", "home_county_lodes")})
