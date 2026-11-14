#!/usr/bin/env python3
"""Observed targets for the stage-2 validation rows on mover flows, workplaces and commute times (validate_landuse.py sections E, F):
  data/silo_target_region_flows_acs.csv   ACS county-to-county migration flows 2014-18 and 2016-20 (data/raw/resloc/CtyxCty_US_*.txt)
                                          aggregated to the 44 SILO regions (landuse/lib/residential/s07_region_validation.py: county_region, acs_flows)
  data/silo_target_lodes_own_county.csv   LODES 8 OD main files (home and work in Maryland, all jobs JT00) 2016-2023: share of
                                          Maryland-resident jobs located in the home county, by home county and statewide
  data/silo_target_commute_acs.csv        ACS PUMS 5-year files 2018-2024: mean and median one-way travel time to work (JWMNP, min) of
                                          Maryland workers in households who commute (JWMNP > 0), and the share of those who work in
                                          Maryland, by vintage"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys, zipfile, numpy as np, pandas as pd
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
sys.path.insert(0, f"{MILES_HOME}/landuse/lib/residential"); import s07_region_validation as RV
c2r = RV.county_region(); out = []
for nm in ["2014_2018", "2016_2020"]:
    f = RV.acs_flows(f"{V}/data/raw/resloc/CtyxCty_US_{nm}.txt", c2r).rename("flow").reset_index(); f.columns = ["orig", "dest", "flow"]; f["period"] = nm; out.append(f)
pd.concat(out).to_csv(f"{V}/data/silo_target_region_flows_acs.csv", index=False)
rows = []
for y in range(2016, 2024):
    d = pd.read_csv(f"{V}/data/raw/lodes_od/md_od_main_JT00_{y}.csv.gz", usecols=["w_geocode", "h_geocode", "S000"], dtype={"w_geocode": str, "h_geocode": str})
    d["hc"] = d.h_geocode.str[:5].astype(int); d["same"] = d.h_geocode.str[:5] == d.w_geocode.str[:5]
    g = d.groupby("hc").apply(lambda x: (x.S000 * x.same).sum() / x.S000.sum())
    rows += [dict(year=y, county=c, own_county_share=v) for c, v in g.items()]
    rows.append(dict(year=y, county=24, own_county_share=(d.S000 * d.same).sum() / d.S000.sum()))
pd.DataFrame(rows).to_csv(f"{V}/data/silo_target_lodes_own_county.csv", index=False)
rows = []
for v in range(2018, 2025):
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_{v}_5yr/csv_pmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        P = pd.read_csv(zf.open(n), usecols=lambda c: c in ["PWGTP", "JWMNP", "POWSP", "RELP", "RELSHIPP"], low_memory=False)
    P = P[~(P.RELP.isin([16, 17]) if "RELP" in P else P.RELSHIPP.isin([37, 38]))]; c = P[P.JWMNP.fillna(0) > 0]
    o = np.argsort(c.JWMNP.values); cw = np.cumsum(c.PWGTP.values[o]); med = c.JWMNP.values[o][np.searchsorted(cw, cw[-1] / 2)]
    rows.append(dict(vintage=v, mean_min=(c.JWMNP * c.PWGTP).sum() / c.PWGTP.sum(), median_min=med, work_in_md=(c.PWGTP * (c.POWSP == 24)).sum() / c.PWGTP.sum()))
pd.DataFrame(rows).to_csv(f"{V}/data/silo_target_commute_acs.csv", index=False)
print(pd.DataFrame(rows).round(3).to_string()); L = pd.read_csv(f"{V}/data/silo_target_lodes_own_county.csv"); print(L[L.county == 24].round(4).to_string())
