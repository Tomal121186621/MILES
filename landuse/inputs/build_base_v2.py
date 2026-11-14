#!/usr/bin/env python3
"""Consistent 2016 base (base_v2, 2026-10-28), built from base_rtswp (pp/jj_2016_rtswp.csv, hh/dd_2016.csv), data only:
a) Employment by age x sex: the employed persons (with a job) of every single year of age x sex, over all regions, are brought up to
   the ACS employment rates the engine's participation targets start from (input/laborParticipationRates.csv, ACS PUMS, with the
   engine's in-place 5-age smoothing for ages 18-97; computed as EmploymentModelImpl does).  The engine's calibrated multipliers
   (labor_participation_adjusters.csv) are applied only with --with-adjusters (see below).  Non-employed persons of the
   cell living in MD, DC or VA zones are promoted at random; occupation 1 (employed); income = max(current income, a draw from the
   base-year incomes of employed persons of the same sex and age +-2 years), the engine's wage-at-hire rule (drawBaseYearEarnings,
   2016 so no wage growth); household income = sum of the members.  They get NO workplace (workplace -1): the workplaces of all
   MD/DC/VA base workers are reassigned afterwards.  Cells above the target are brought down the same way (2026-10-28): employed
   persons of the cell in MD, DC or VA homes are demoted at random by the engine's job-loss rule without the benefit (occupation 2,
   unemployed; income = the non-wage income of a base-year non-employed person of the same sex and age +-2, the engine's rule after
   the benefit year); their jobs become vacant.
b) Jobs: total jobs T = workers / (1 - 0.0401) (JOLTS 2016 openings rate); the T - J0 jobs added (not covered by LODES:
   self-employed and others) are spread over zone x type in proportion to the existing base jobs (LODES in Maryland, the MSTM
   inventory elsewhere), largest remainders, all vacant.
Outputs: input/microData/{pp,hh,jj}_2016_v2.csv; run/base_v2/ (input, skims links; microData links to the v2 files and dd_2016.csv);
tables: WORKSPACE/2_silo/input_build/base_v2_employment.csv, base_v2_jobs_added.csv.   Usage: python3 landuse/inputs/build_base_v2.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, numpy as np, pandas as pd
S = f"{WORKSPACE}/2_silo"; MD = f"{S}/input/microData"; OUT = f"{S}/input_build"
RATE = 0.0401; rng = np.random.default_rng(20161028)
pp = pd.read_csv(f"{MD}/pp_2016_rtswp.csv"); hh = pd.read_csv(f"{MD}/hh_2016.csv"); dd = pd.read_csv(f"{MD}/dd_2016.csv", usecols=["id", "zone"])
jj = pd.read_csv(f"{MD}/jj_2016_rtswp.csv")
Z = pd.read_csv(f"{S}/input/zoneSystem.csv").set_index("ZoneId")
# ---- engine target shares
lp = pd.read_csv(f"{S}/input/laborParticipationRates.csv").set_index("age")
share = np.zeros((2, 100)); 
for a in range(100):
    if a in lp.index: share[0, a], share[1, a] = lp.at[a, "male"], lp.at[a, "female"]
# 2026-10-28: the calibrated multipliers of input/labor_participation_adjusters.csv (0.94-2.14) are NOT applied by default: with them
# the 2016 target is 71.9 % of persons 16+ (Maryland residents 76.9 % after promotion, ACS 65.4 %); they compensated for hires blocked
# by empty vacancy pools in the calibration runs.  --with-adjusters applies them.
import sys
adj = pd.read_csv(f"{S}/input/labor_participation_adjusters.csv") if "--with-adjusters" in sys.argv else pd.DataFrame(columns=["sex", "age_from", "age_to", "adjuster"]); cell = np.ones((2, 100))
for r in adj.itertuples():
    g = 0 if r.sex.strip().lower() == "male" else 1
    for a in range(int(r.age_from), min(99, int(r.age_to)) + 1): cell[g, a] = r.adjuster
share = np.minimum(1.0, share * 1.0 * cell).astype(np.float32)
for g in range(2):
    for a in range(18, 98):   # in place, as the engine (already smoothed ages a-2, a-1 enter)
        share[g, a] = np.float32((share[g, a - 2] / 4 + share[g, a - 1] / 2 + share[g, a] + share[g, a + 1] / 2 + share[g, a + 2] / 4) / 2.5)
# ---- persons
pp["g"] = (pp.gender == 2).astype(int); pp["emp"] = pp.workplace > 0
hz = pp.hhID.map(hh.set_index("id").dwelling).map(dd.set_index("id").zone); pp["st"] = hz.map(Z.STFIPS)
_m = pp[(pp.age >= 16) & (pp.st == 24)]; md_before = _m.emp.mean()
before = pp[pp.age <= 99].groupby(["g", "age"]).agg(n=("id", "size"), emp=("emp", "sum"))
earn = {(g, a): pp[(pp.g == g) & pp.emp & pp.age.between(a - 2, a + 2)].income.values for g in range(2) for a in range(100)}
nonwage = {(g, a): pp[(pp.g == g) & ~pp.emp & pp.age.between(a - 2, a + 2)].income.values for g in range(2) for a in range(100)}
promoted = []; demoted = []; rows = []
for (g, a), r in before.iterrows():
    target = int(round(share[g, a] * r.n)); need = target - int(r.emp)
    cand = pp.index[(pp.g == g) & (pp.age == a) & ~pp.emp & (pp.occupation != 1) & pp.st.isin([24, 11, 51])]
    k = max(0, min(need, len(cand)))
    if k > 0: promoted += list(rng.choice(cand, k, replace=False))
    kd = 0
    if need < 0:
        cd = pp.index[(pp.g == g) & (pp.age == a) & pp.emp & pp.st.isin([24, 11, 51])]; kd = min(-need, len(cd))
        if kd > 0: demoted += list(rng.choice(cd, kd, replace=False))
    rows.append(dict(sex="male" if g == 0 else "female", age=a, persons=int(r.n), employed_before=int(r.emp), target=target, promoted=k, demoted=kd,
                     shortfall=max(0, need - k), excess_left=max(0, -need - kd)))
E = pd.DataFrame(rows); promoted = np.array(promoted, dtype=int)
ix = promoted
draw = np.array([rng.choice(earn[(pp.g[i], pp.age[i])]) if len(earn[(pp.g[i], pp.age[i])]) else 0 for i in ix])
pp.loc[ix, "income"] = np.maximum(pp.loc[ix, "income"].values, draw).astype(int)
pp.loc[ix, "occupation"] = 1   # employed; workplace stays -1 until the reassignment
dm = np.array(demoted, dtype=int)
freed = pp.loc[dm, "workplace"].values
nw = np.array([rng.choice(nonwage[(pp.g[i], pp.age[i])]) if len(nonwage[(pp.g[i], pp.age[i])]) else 0 for i in dm])
pp.loc[dm, "income"] = nw.astype(int); pp.loc[dm, "occupation"] = 2; pp.loc[dm, "workplace"] = -1
jj.loc[jj.id.isin(freed), "personId"] = -1
hh["income"] = hh.id.map(pp.groupby("hhID").income.sum()).fillna(0).astype(int)
# ---- jobs
workers = int((pp.workplace > 0).sum()) + len(ix)          # employed with a job (after demotion) + promoted (job to be assigned)
J0 = len(jj); T = max(J0, int(round(workers / (1 - RATE)))); add = T - J0   # original jobs are never removed
cnt = jj.groupby(["zone", "type"]).size(); q = cnt / cnt.sum() * add; base_ = np.floor(q).astype(int); rem = add - base_.sum()
base_[q.sub(base_).sort_values(ascending=False).index[:rem]] += 1
newj = base_.repeat(base_.values).reset_index()[["zone", "type"]] if add > 0 else pd.DataFrame(columns=["zone", "type"])
newj = newj.assign(id=np.arange(jj.id.max() + 1, jj.id.max() + 1 + len(newj)), personId=-1)[["id", "zone", "personId", "type"]]
jj2 = pd.concat([jj, newj], ignore_index=True)
# ---- write
pp.drop(columns=["g", "emp", "st"]).to_csv(f"{MD}/pp_2016_v2.csv", index=False); hh.to_csv(f"{MD}/hh_2016_v2.csv", index=False); jj2.to_csv(f"{MD}/jj_2016_v2.csv", index=False)
B = f"{S}/run/base_v2"; os.makedirs(f"{B}/microData", exist_ok=True); os.makedirs(f"{B}/scenOutput", exist_ok=True)
for l, t in [("input", f"{S}/input"), ("skims", f"{S}/input/skims")]:
    if not os.path.lexists(f"{B}/{l}"): os.symlink(t, f"{B}/{l}")
for k, f in [("pp", "pp_2016_v2.csv"), ("hh", "hh_2016_v2.csv"), ("jj", "jj_2016_v2.csv"), ("dd", "dd_2016.csv")]:
    p = f"{B}/microData/{k}_2016.csv"
    if os.path.lexists(p): os.remove(p)
    os.symlink(f"{MD}/{f}", p)
E.to_csv(f"{OUT}/base_v2_employment.csv", index=False)
JA = newj.assign(county=newj.zone.map(Z.COUNTYFIPS)).groupby("county").size().rename("jobs_added").reset_index(); JA.to_csv(f"{OUT}/base_v2_jobs_added.csv", index=False)
a16 = E[E.age >= 16]; md = pp[(pp.age >= 16) & (pp.st == 24)]
E.loc[:, "employed_after"] = E.employed_before + E.promoted - E.demoted
print(f"persons 16-99: employed share {a16.employed_before.sum() / a16.persons.sum():.4f} -> {(a16.employed_before.sum() + a16.promoted.sum() - a16.demoted.sum()) / a16.persons.sum():.4f}; target {a16.target.sum() / a16.persons.sum():.4f}")
print(f"promoted {len(ix):,}, demoted {len(dm):,} (shortfall {E.shortfall.sum():,}, excess left {E.excess_left.sum():,}); MD residents 16+ employed share before {md_before:.4f}, after {(md.occupation == 1).mean():.4f} (ACS 0.654)")
print(f"jobs {J0:,} -> {T:,} (+{add:,}); workers {workers:,}; vacant {T - workers:,} = {(T - workers) / T:.4f}")
print(JA.sort_values("jobs_added", ascending=False).head(10).to_string(index=False))
