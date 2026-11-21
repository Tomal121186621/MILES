# base_v8 (2026-11-16b): copy of base_v7/b07_population_controls_v7.py with v7 -> v8 (hhfix population 1_vae/output_v8); nothing else changed
#!/usr/bin/env python3
# base_v8 (2026-11-15d) copy of input_build/build_population_controls.py (the current series): 2016 persons of run/base_v8 -> input/assumptions/populationControlTotalByRegion_v8.csv (observed PEP table written as data/silo_target_population_by_region_v8check.csv, must equal the record one)
"""Population control totals by region and year for SILO (population.control.total = region).
Observed (2026-10-28): Census county population estimates on one consistent series anchored to the 2020 Census:
  2016-2019 the 2010-2020 intercensal estimates (released 2024; data/raw/pep/intercensal_2010_2020/cc-est2020int-agesex-<st>.csv,
            POPESTIMATE of July 1, YEAR code = year - 2008), 2020-2025 vintage 2025 (co-est2025-alldata.csv);
  2026 = 2025 x the 2024->2025 growth ratio of the county (stated extrapolation).
Before 2026-10-28 the series was vintage 2020 for 2016-2019 and vintage 2025 from 2020, two series with different bases; the
2019->2020 step carried the Census-2020 correction in one year (Prince George's +5.9 %, Frederick +4.7 %, Baltimore County +3.0 %,
area +1.2 % against about +0.45 % a year), which made the population control propose 216,000 in-migrants in 2019.  The earlier
outputs are kept as *_v2020v2025.csv (and this builder as build_population_controls_v2020v2025.py).
Scaling: the synthetic population of 2016 differs slightly from the Census count; the target of region r in year Y is
   SILO_persons_2016(r) x PEP(r, Y) / PEP(r, 2016)
so the control imposes the OBSERVED growth path, not a jump at the base year.  Regions of other states: sum of their counties
(a county split across regions is counted in the region that holds most of its zones).
Outputs: WORKSPACE/2_silo/input/assumptions/populationControlTotalByRegion.csv (Year,Region,Population) and
         WORKSPACE/data/silo_target_population_by_region.csv (observed PEP by region and year, for validation)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, os
ROOT = PROJECT_ROOT; V = f"{WORKSPACE}"; RAW = f"{V}/data/raw/pep"
OUT = f"{V}/2_silo/input/assumptions"; os.makedirs(OUT, exist_ok=True)
z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv")
# county -> region weights: a county split across regions is shared in proportion to its zones (MSTM composite codes for
# Virginia independent cities are expanded to their Census counties: 51919 = Fairfax County + Fairfax City + Falls Church,
# 51942 = Prince William + Manassas + Manassas Park, 51951 = Frederick County + Winchester)
COMPOSITE = {51919: [51059, 51600, 51610], 51942: [51153, 51683, 51685], 51951: [51069, 51840]}
zc = z.groupby(["COUNTYFIPS", "Region"]).size().rename("n").reset_index(); zc["w"] = zc.n / zc.groupby("COUNTYFIPS").n.transform("sum")
rows_w = []
for r in zc.itertuples():
    for c in COMPOSITE.get(int(r.COUNTYFIPS), [int(r.COUNTYFIPS)]): rows_w.append(dict(county=c, region=int(r.Region), w=r.w))
CW = pd.DataFrame(rows_w)
def pep(file, years):
    p = pd.read_csv(f"{RAW}/{file}", encoding="latin-1", dtype={"STATE": str, "COUNTY": str}); p = p[p.SUMLEV == 50]
    p["fips"] = (p.STATE.str.zfill(2) + p.COUNTY.str.zfill(3)).astype(int)
    return p.set_index("fips")[[f"POPESTIMATE{y}" for y in years]].rename(columns=lambda c: int(c.replace("POPESTIMATE", "")))
def intercensal(years):
    parts = []
    for s in (10, 11, 24, 42, 51, 54):
        d = pd.read_csv(f"{RAW}/intercensal_2010_2020/cc-est2020int-agesex-{s}.csv", encoding="latin-1", dtype={"STATE": str, "COUNTY": str})
        d["fips"] = (d.STATE.str.zfill(2) + d.COUNTY.str.zfill(3)).astype(int); parts.append(d[d.YEAR.isin([y - 2008 for y in years])])
    d = pd.concat(parts); d["year"] = d.YEAR + 2008
    return d.pivot_table(index="fips", columns="year", values="POPESTIMATE", aggfunc="sum")
P = pd.concat([intercensal(range(2016, 2020)), pep("co-est2025-alldata.csv", range(2020, 2026))], axis=1)
P[2026] = (P[2025] * (P[2025] / P[2024])).round()
P = P[P.index.isin(set(CW.county))]
M = CW.merge(P, left_on="county", right_index=True)
for y in range(2016, 2027): M[y] = M[y] * M.w
obs = M.groupby("region")[list(range(2016, 2027))].sum().round().astype(int)     # observed persons by region and year
# synthetic 2016 persons by region
dd = pd.read_csv(f"{V}/2_silo/run/base_v8/microData/dd_2016.csv", usecols=["id", "zone", "hhID"]); hh = pd.read_csv(f"{V}/2_silo/run/base_v8/microData/hh_2016.csv", usecols=["id", "dwelling", "hhSize"])
hh["zone"] = hh.dwelling.map(dd.set_index("id").zone); hh["region"] = hh.zone.map(z.set_index("ZoneId").Region)
base = hh.groupby("region").hhSize.sum()
rows = []
for r in obs.index:
    if r not in base.index: continue
    for y in range(2016, 2027):
        rows.append(dict(Year=y, Region=int(r), Population=int(round(base[r] * obs.at[r, y] / obs.at[r, 2016]))))
T = pd.DataFrame(rows); T.to_csv(f"{OUT}/populationControlTotalByRegion_v8.csv", index=False)
obs.reset_index().melt(id_vars="region", var_name="year", value_name="persons_pep").to_csv(f"{V}/data/silo_target_population_by_region_v8check.csv", index=False)
cmp = pd.DataFrame({"synthetic_2016": base, "pep_2016": obs[2016], "pep_2024": obs[2024], "pep_2026_extrap": obs[2026]}).dropna()
cmp["synthetic/pep 2016"] = (cmp.synthetic_2016 / cmp.pep_2016).round(3); cmp["growth 2016-2024"] = (cmp.pep_2024 / cmp.pep_2016 - 1).round(3)
md = cmp[cmp.index > 24000]; md = md[md.index < 25000]
G = (obs.pct_change(axis=1) * 100); gmd = G.loc[[r for r in G.index if 24000 < r < 25000]]
print("growth % by year, Maryland counties:"); print(gmd[[2017, 2018, 2019, 2020, 2021]].round(2).to_string())
st_ = (gmd[2020] - gmd[[2018, 2019, 2021]].mean(axis=1)).abs(); print(f"largest 2019->2020 step against the neighbouring years: county {st_.idxmax()}, {gmd.loc[st_.idxmax(), 2020]:.2f} % vs {gmd.loc[st_.idxmax(), [2018, 2019, 2021]].round(2).tolist()}")
print(f"area growth % by year: {(obs.sum().pct_change() * 100).round(2).to_dict()}")
print(md.to_string()); print(f"\nall regions: synthetic 2016 {cmp.synthetic_2016.sum():,.0f} vs PEP {cmp.pep_2016.sum():,.0f} ({cmp.synthetic_2016.sum() / cmp.pep_2016.sum():.3f}); rows written {len(T)}")
