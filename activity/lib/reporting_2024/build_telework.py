#!/usr/bin/env python3
"""Year-specific work-at-home input of the attendance step (the variant 'with 2024 telework input').

    python3 -I activity/lib/reporting_2024/build_telework.py   -> temporal_2024/telework/wfh_attendance_2024.csv, wfh_attendance_2017_19.csv, telework_input.csv

The frozen model reads one table (ABIT/input/maryland/wfh_attendance_fips.csv: countyfips, p = usual work-at-home share of
workers, ACS PUMS 2019-2023) and keeps a worker at home on a work day with probability min(0.6, 1.6274 p) (the day factor
estimated on the base survey, unchanged).  The variant replaces p by the observed share of the year being simulated, like the
population: workers at work in the reference week (ESR 1, 4; age 16+) whose means of transportation is 'worked from home'
(JWTRNS 11), person weights PWGTP.
  2024     ACS 2024 1-year person files of DC, DE, MD, PA, VA, WV (2020 PUMAs)
  2017-19  the 2017, 2018 and 2019 interview years of the ACS 2015-2019 5-year files (2010 PUMAs)
By home county: the share over the PUMAs that overlap the county (2024: PUMS 2024 geography lookup; 2017-19: Census 2010
tract-to-PUMA file); a county whose PUMA set holds fewer than 100 worker records takes the state share.  Same 61 counties as
the frozen table.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import t24common as C

OD = f"{C.T24}/telework"; os.makedirs(OD, exist_ok=True)
FROZEN = f"{C.ROOT}/ABIT/input/maryland/wfh_attendance_fips.csv"
ST = {11: "dc", 10: "de", 24: "md", 42: "pa", 51: "va", 54: "wv"}
COLS = ["SERIALNO", "PUMA", "PWGTP", "AGEP", "ESR", "JWTRNS", "RELSHIPP"]


def persons(v, st):
    if v == "2024": f = f"{C.PUMS1}/csv_p{ST[st]}.zip"; yrs = None
    else: f = f"{C.RAW}/pums_2019_5yr_de/csv_pde.zip" if st == 10 else f"{C.PUMS5_2019}/csv_p{ST[st]}.zip"; yrs = [2017, 2018, 2019]
    p = C.read_pums_persons(f, COLS, yrs); p = p[p.ESR.isin([1, 4]) & (p.AGEP >= 16) & p.JWTRNS.notna()]
    return p.assign(wfh=(p.JWTRNS == 11).astype(float))


def county_pumas(v):
    if v == "2024":
        g = C.geo_lookup(); return g.groupby("county").apply(lambda d: set(zip(d.state, d.puma)), include_groups=False)
    r = pd.read_csv(f"{C.RAW}/resloc/2010_Census_Tract_to_2010_PUMA.txt", dtype=str)
    r["county"] = (r.STATEFP + r.COUNTYFP).astype(int); r["st"] = r.STATEFP.astype(int); r["pu"] = r.PUMA5CE.astype(int)
    return r.groupby("county").apply(lambda d: set(zip(d.st, d.pu)), include_groups=False)


def table(v):
    fr = pd.read_csv(FROZEN); P = {st: persons(v, st) for st in ST}; cp = county_pumas(v); rows = []
    for c in fr.countyfips:
        st = c // 1000; p = P[st]; keys = {pu for s, pu in cp.get(c, set()) if s == st}
        q = p[p.PUMA.isin(keys)]
        if len(q) >= 100: share, n, lvl = float(np.average(q.wfh, weights=q.PWGTP)), len(q), "county (PUMA set)"
        else: share, n, lvl = float(np.average(p.wfh, weights=p.PWGTP)), len(p), "state"
        rows.append(dict(countyfips=c, p=round(share, 4), n_records=n, level=lvl))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = []
    for v, fn in [("2024", "wfh_attendance_2024.csv"), ("2017_19", "wfh_attendance_2017_19.csv")]:
        t = table(v); t[["countyfips", "p"]].to_csv(f"{OD}/{fn}", index=False); out.append(t.assign(vintage=v))
    fr = pd.read_csv(FROZEN).rename(columns={"p": "p_frozen_2019_23"})
    T = pd.concat(out).pivot_table(index="countyfips", columns="vintage", values="p").reset_index().merge(fr, on="countyfips")
    T.to_csv(f"{OD}/telework_input.csv", index=False); print(T.to_string())
