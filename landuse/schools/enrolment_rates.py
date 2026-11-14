#!/usr/bin/env python3 -I
"""ACS enrolment rates for the student alignment of the schools step (assign_schools.py --align), 2016-2024.
ACS PUMS 1-year person files (data/raw/pums_<Y>_1yr/csv_p<st>.zip; 2020: the experimental 1-year file with experimental weights, as
build_labor_participation_byyear.py), persons in households (group quarters excluded, as the employment rates: RELP 16/17 up to 2018,
RELSHIPP 37/38 from 2019), PUMAs of the model area (2010 PUMAs of resloc/work/geo_puma_zone.csv to 2021; 2020 PUMAs with most tracts in
model counties from 2022), weights PWGTP.
Enrolled = SCH 2 or 3 (public or private school, past 3 months) and SCHG >= 2 (kindergarten or above; nursery excluded: SILO students
start at kindergarten).  Worker = ESR 1, 2, 4, 5.
Cells: sex x age; ages 5-17 single years ('rate' = enrolled / persons); ages 18+: 18, 19, 20, 21, 22, 23, 24, 25-29, 30-34, 35-44, 45-54,
55-64, 65+ ('rate' = enrolled NON-workers / persons, the rate the alignment uses for adults; 'rate_all' = all enrolled / persons).
By state (MD, DC, VA, DE, PA, WV); a cell with fewer than 30 sample persons takes the rate of all states pooled (flag pooled = 1).
Output apply/school_enrolment_rates.csv.   Usage: python3 -I landuse/schools/enrolment_rates.py"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import zipfile, numpy as np, pandas as pd
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; AP = f"{S}/schoolchoice/apply"
ST = {"md": 24, "dc": 11, "de": 10, "pa": 42, "va": 51, "wv": 54}
MERGED = {51919: [51059, 51600, 51610], 51942: [51153, 51683, 51685], 51951: [51069, 51840]}
cty = set(); [cty.update(MERGED.get(c, [c])) for c in pd.read_csv(f"{S}/input/zoneSystem.csv").COUNTYFIPS.unique()]
p10 = set(pd.read_csv(f"{S}/resloc/work/geo_puma_zone.csv").puma7.astype(int))
tr = pd.read_csv(f"{V}/data/raw/geo/2020_Census_Tract_to_2020_PUMA.txt", dtype=str); tr["c"] = (tr.STATEFP + tr.COUNTYFP).astype(int)
tr["p"] = tr.STATEFP.astype(int) * 100000 + tr.PUMA5CE.astype(int); t = tr.groupby("p").c.apply(lambda s: s.isin(cty).mean()); p20 = set(t[t > 0.5].index)
EDGES = [18, 19, 20, 21, 22, 23, 24, 25, 30, 35, 45, 55, 65, 200]
def cell(age): return np.where(age < 18, age.astype(str), pd.cut(age, EDGES, right=False, labels=["18", "19", "20", "21", "22", "23", "24", "25-29", "30-34", "35-44", "45-54", "55-64", "65+"]).astype(str))
rows = []
for y in range(2016, 2025):
    parts = []
    for s, code in ST.items():
        zf = zipfile.ZipFile(f"{V}/data/raw/pums_{y}_1yr/csv_p{s}.zip"); n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        d = pd.read_csv(zf.open(n), usecols=lambda c: c in ("PUMA", "PUMA10", "PUMA20", "PWGTP", "AGEP", "SEX", "ESR", "SCH", "SCHG", "RELP", "RELSHIPP"), low_memory=False)
        gq = d.RELP.isin([16, 17]) if "RELP" in d else d.RELSHIPP.isin([37, 38]); d = d[~gq & (d.AGEP >= 5)]
        pu = d["PUMA20"] if y >= 2022 and "PUMA20" in d else d["PUMA10"] if "PUMA10" in d else d["PUMA"]
        d = d[(code * 100000 + pu.astype(int)).isin(p20 if y >= 2022 else p10).values]; parts.append(d.assign(state=code))
    P = pd.concat(parts); P["enr"] = (P.SCH.isin([2, 3]) & (pd.to_numeric(P.SCHG, errors="coerce") >= 2)).astype(float)
    P["wrk"] = P.ESR.isin([1, 2, 4, 5]).astype(float); P["cell"] = cell(P.AGEP.values)
    P["we"] = P.PWGTP * P.enr; P["wen"] = P.PWGTP * P.enr * (1 - P.wrk)
    allc = P.groupby(["SEX", "cell"]).agg(w=("PWGTP", "sum"), we=("we", "sum"), wen=("wen", "sum"))
    for (code, sex, c), g in P.groupby(["state", "SEX", "cell"]):
        a = allc.loc[(sex, c)]; pooled = len(g) < 30; src = a if pooled else g[["PWGTP", "we", "wen"]].sum().rename({"PWGTP": "w"})
        adult = not c.isdigit() or int(c) >= 18
        rows.append(dict(year=y, state=code, sex=sex, cell=c, sample=len(g), pooled=int(pooled), rate_all=src.we / src.w, rate=(src.wen if adult else src.we) / src.w,
                         adult=int(adult), weights="experimental 1-year" if y == 2020 else "1-year"))
    print(y, "done", flush=True)
R = pd.DataFrame(rows); R.to_csv(f"{AP}/school_enrolment_rates.csv", index=False)
print(R[(R.year == 2016) & (R.state == 24)].round(3).to_string(index=False))
