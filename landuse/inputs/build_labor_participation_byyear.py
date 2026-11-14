#!/usr/bin/env python3
"""Employment rates by single year of age and sex for every year 2016-2024 (2026-10-28, author decision), for the employment model's
yearly targets (demographics.labor.participation.file.byyear).  ACS PUMS 1-year person files of MD, DC, DE, PA, VA and WV
(data/raw/pums_<Y>_1yr/csv_p<st>.zip; 2020: the experimental 1-year file with experimental weights, Census
programs-surveys/acs/experimental/2020), persons in households (group quarters excluded: RELP 16/17 up to 2018, RELSHIPP 37/38 from
2019), employed = ESR 1, 2, 4, 5, person weights PWGTP, pooled over the PUMAs of the model area (the engine applies one schedule to all
persons; it cannot take state-specific rates): 2010 PUMAs (files 2016-2021) that contain a model zone (resloc/work/geo_puma_zone.csv);
2020 PUMAs (files 2022-2024) whose tracts lie mostly in model counties (data/raw/geo/2020_Census_Tract_to_2020_PUMA.txt; merged
zone-system counties expanded).  PUMAs partly inside the area are taken whole.  Smoothed over a 3-year age window, as
build_labor_participation.py (the engine smooths again over 5 ages).
2026-10-28 (author decision): also by state (MD, DC, DE whole states, which lie in the model area; PA, VA, WV their model-area PUMAs)
for the engine's state-specific targets (demographics.labor.participation.file.bystate).
Output: input/laborParticipationRates_byYear.csv (year, age, male, female); input/laborParticipationRates_byYearState.csv (state,
year, age, male, female); data/silo_employment_rates_byyear_summary.csv.
Usage: python3 landuse/inputs/build_labor_participation_byyear.py"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import zipfile, numpy as np, pandas as pd
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; S = f"{V}/2_silo"
ST = {"md": 24, "dc": 11, "de": 10, "pa": 42, "va": 51, "wv": 54}
MERGED = {51919: [51059, 51600, 51610], 51942: [51153, 51683, 51685], 51951: [51069, 51840]}
cty = set(); [cty.update(MERGED.get(c, [c])) for c in pd.read_csv(f"{S}/input/zoneSystem.csv").COUNTYFIPS.unique()]
p10 = set(pd.read_csv(f"{S}/resloc/work/geo_puma_zone.csv").puma7.astype(int))
tr = pd.read_csv(f"{V}/data/raw/geo/2020_Census_Tract_to_2020_PUMA.txt", dtype=str); tr["c"] = (tr.STATEFP + tr.COUNTYFP).astype(int)
tr["p"] = tr.STATEFP.astype(int) * 100000 + tr.PUMA5CE.astype(int); t = tr.groupby("p").c.apply(lambda s: s.isin(cty).mean()); p20 = set(t[t > 0.5].index)
rows, summ, srows, summ_st = [], [], [], []
for y in range(2016, 2025):
    parts = []
    for s, code in ST.items():
        zf = zipfile.ZipFile(f"{V}/data/raw/pums_{y}_1yr/csv_p{s}.zip"); n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        d = pd.read_csv(zf.open(n), usecols=lambda c: c in ("PUMA", "PUMA10", "PUMA20", "ST", "PWGTP", "AGEP", "SEX", "ESR", "RELP", "RELSHIPP"), low_memory=False)
        gq = d.RELP.isin([16, 17]) if "RELP" in d else d.RELSHIPP.isin([37, 38]); d = d[~gq]
        pu = d["PUMA"] if "PUMA" in d else (d["PUMA20"] if "PUMA20" in d else d["PUMA10"])
        key = code * 100000 + pu.astype(int); d = d[key.isin(p20 if y >= 2022 else p10).values]; parts.append(d[["PWGTP", "AGEP", "SEX", "ESR"]].assign(state=code))
    P = pd.concat(parts); P["emp"] = P.ESR.isin([1, 2, 4, 5]).astype(float)
    def sched(Pq):
        out = {"age": np.arange(100)}
        for sex, col in [(1, "male"), (2, "female")]:
            dd = Pq[Pq.SEX == sex]; w = dd.groupby("AGEP").PWGTP.sum().reindex(range(100), fill_value=0); ew = (dd.PWGTP * dd.emp).groupby(dd.AGEP).sum().reindex(range(100), fill_value=0)
            sm = pd.DataFrame({"w": w, "ew": ew}).rolling(3, center=True, min_periods=1).sum(); out[col] = (sm.ew / sm.w.replace(0, np.nan)).fillna(0).round(4).values
        return pd.DataFrame(out)
    rows.append(sched(P).assign(year=y)[["year", "age", "male", "female"]])
    for code in ST.values():
        a_ = P[(P.state == code) & (P.AGEP >= 16)]
        srows.append(sched(P[P.state == code]).assign(state=code, year=y)[["state", "year", "age", "male", "female"]])
        summ_st.append(dict(state=code, year=y, persons=int((P.state == code).sum()), employed_share_16plus=(a_.PWGTP * a_.emp).sum() / a_.PWGTP.sum()))
    a = P[P.AGEP >= 16]
    summ.append(dict(year=y, persons=len(P), employed_share_16plus=(a.PWGTP * a.emp).sum() / a.PWGTP.sum(), file="experimental 1-year" if y == 2020 else "1-year"))
R = pd.concat(rows); R.to_csv(f"{S}/input/laborParticipationRates_byYear.csv", index=False)
pd.concat(srows).to_csv(f"{S}/input/laborParticipationRates_byYearState.csv", index=False)
SS = pd.DataFrame(summ_st); SS.to_csv(f"{V}/data/silo_employment_rates_byyear_state_summary.csv", index=False)
print(SS.pivot(index="state", columns="year", values="employed_share_16plus").round(3).to_string())
M = pd.DataFrame(summ); M.to_csv(f"{V}/data/silo_employment_rates_byyear_summary.csv", index=False); print(M.round(4).to_string(index=False))
old = pd.read_csv(f"{S}/input/laborParticipationRates.csv").set_index("age"); n16 = R[R.year == 2016].set_index("age")
for lo, hi in [(16, 19), (20, 24), (25, 54), (55, 64), (65, 74), (75, 99)]:
    print(f"2016 vs current file, ages {lo}-{hi}: male {n16.loc[lo:hi].male.mean():.3f} vs {old.loc[lo:hi].male.mean():.3f}, female {n16.loc[lo:hi].female.mean():.3f} vs {old.loc[lo:hi].female.mean():.3f}")
