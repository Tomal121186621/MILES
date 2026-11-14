#!/usr/bin/env python3
"""Job control totals from QCEW growth and state JOLTS openings rates (2026-10-28, author decision; replaces for the runs the rule of
scale_job_controls.py, whose growth came from the area population x the Maryland employed share x 1 / (1 - the Maryland openings rate)).

  jobs(county c, Y) = J_c(2016) x Q_c(Y) / Q_c(2016) x (1 - v_s(2016)) / (1 - v_s(Y))
J_c(2016): all jobs (filled + vacant) of the county in the 2016 base (input/microData/jj_2016_v3.csv, base_v3);
Q_c(Y): QCEW annual-average employment, all industries, all ownerships (own_code 0, industry 10) of the county
(data/raw/qcew/qcew_<Y>_<fips>.csv, BLS QCEW open data; the merged zone-system counties are summed: 51919 = 51059 + 51600 + 51610,
51942 = 51153 + 51683 + 51685, 51951 = 51069 + 51840); v_s(Y): JOLTS job-openings rate of the county's own state, annual mean of the
monthly rates (data/raw/jolts/jolts_openings_rate_states_2016_2024.json, series JTS000000<ss>0000000JOR).  The vacancy share of the
jobs therefore follows the state's JOLTS rate and the filled jobs follow QCEW; self-employment is assumed to grow like QCEW jobs.
2025-2026 keep the 2024 index and rate.  Within a county, zone x type: the base share of 2016 times the LODES-based change of the
zone x type (input/assumptions/jobControlTotals_lodes.csv, Y over 2016), renormalised to the county total; a zone x type without
LODES jobs in 2016 keeps its base share.  The 2016 column equals the base jobs exactly.
Output: input/assumptions/jobControlTotals_qcew.csv (the old jobControlTotals.csv is kept); data/silo_job_controls_qcew_check.csv.
Usage: python3 landuse/inputs/build_job_controls_qcew.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, numpy as np, pandas as pd
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; S = f"{V}/2_silo"; A = f"{S}/input/assumptions"
TYPES = ["RET", "OFF", "IND", "OTH"]; YRS = list(range(2016, 2027)); QY = list(range(2016, 2025))
MERGED = {51919: [51059, 51600, 51610], 51942: [51153, 51683, 51685], 51951: [51069, 51840]}
Z = pd.read_csv(f"{S}/input/zoneSystem.csv").set_index("ZoneId"); cty = Z.COUNTYFIPS; st = Z.STFIPS
def qcew(c, y):
    d = pd.read_csv(f"{V}/data/raw/qcew/qcew_{y}_{c}.csv", dtype={"area_fips": str}); r = d[(d.own_code == 0) & (d.industry_code.astype(str) == "10")]
    return float(r.annual_avg_emplvl.iloc[0])
counties = sorted(cty.unique()); Q = pd.DataFrame({y: {c: sum(qcew(k, y) for k in MERGED.get(c, [c])) for c in counties} for y in QY})
for y in (2025, 2026): Q[y] = Q[2024]
js = json.load(open(f"{V}/data/raw/jolts/jolts_openings_rate_states_2016_2024.json")); vr = {}
for s in js["Results"]["series"]:
    stt = int(s["seriesID"][9:11]); vals = pd.DataFrame([(int(x["year"]), float(x["value"])) for x in s["data"] if x["period"] != "M13"], columns=["y", "v"]).groupby("y").v.mean() / 100
    vr[stt] = {y: vals.get(min(y, 2024)) for y in YRS}
jj = pd.read_csv(f"{S}/input/microData/jj_2016_v3.csv", usecols=["zone", "type"]); jj["type"] = jj.type.astype(str).str.strip('"')
B = jj.groupby(["zone", "type"]).size().unstack(fill_value=0).reindex(columns=TYPES, fill_value=0)
L = pd.read_csv(f"{A}/jobControlTotals_lodes.csv").set_index("SMZ")
zones = sorted(set(B.index) | set(L.index)); B = B.reindex(zones, fill_value=0)
out = pd.DataFrame(index=zones); out.index.name = "SMZ"; chk = []
for y in YRS:
    yy = f"{y % 100:02d}"; Jc = B.sum(axis=1).groupby(cty.reindex(zones).values).sum()
    tgt = {c: Jc.get(c, 0) * Q.at[c, y] / Q.at[c, 2016] * (1 - vr[int(str(c)[:2])][2016]) / (1 - vr[int(str(c)[:2])][y]) for c in Jc.index}
    W = B.astype(float).copy()
    if y > 2016:
        for t in TYPES:
            l16 = L[f"{t}16"].reindex(zones).fillna(0); ly = L[f"{t}{yy}"].reindex(zones).fillna(0)
            W[t] = W[t] * np.where(l16 > 0, ly / l16.replace(0, np.nan), 1.0)
    W = W.fillna(0); ws = W.sum(axis=1).groupby(cty.reindex(zones).values).transform("sum") if False else None
    tot_c = W.sum(axis=1).groupby(cty.reindex(zones).values).sum()
    for t in TYPES:
        f = cty.reindex(zones).map(lambda c: tgt.get(c, 0) / tot_c.get(c, 1) if tot_c.get(c, 0) > 0 else 0).values
        out[f"{t}{yy}"] = (W[t].values * f).round(1)
    for c in Jc.index: chk.append(dict(year=y, county=c, state=int(str(c)[:2]), base_jobs_2016=Jc[c], qcew=Q.at[c, y], v=vr[int(str(c)[:2])][y], jobs=tgt[c]))
out = out[[f"{t}{y % 100:02d}" for t in TYPES for y in YRS]].reset_index(); out.to_csv(f"{A}/jobControlTotals_qcew.csv", index=False)
C = pd.DataFrame(chk); C.to_csv(f"{V}/data/silo_job_controls_qcew_check.csv", index=False)
G = C.groupby(["state", "year"])[["jobs", "qcew"]].sum().unstack("year")
print("growth % a year by state, control (jobs) and QCEW:")
print(((G["jobs"].pct_change(axis=1)) * 100).round(2).iloc[:, 1:9].to_string()); print(((G["qcew"].pct_change(axis=1)) * 100).round(2).iloc[:, 1:9].to_string())
print("2016 control vs base:", round(out[[f"{t}16" for t in TYPES]].sum().sum()), int(B.values.sum()))
