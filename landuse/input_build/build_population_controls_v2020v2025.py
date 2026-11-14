#!/usr/bin/env python3
"""Population control totals by region and year for SILO (population.control.total = region).
Observed: Census Population Estimates, county totals (vintage 2020 for 2016-2019, vintage 2025 for 2020-2025); 2026 = 2025 x the
2024->2025 growth ratio of the county (stated extrapolation, replaced when the vintage-2026 estimates are published).
Scaling: the synthetic population of 2016 differs slightly from the Census count; the target of region r in year Y is
   SILO_persons_2016(r) x PEP(r, Y) / PEP(r, 2016)
so the control imposes the OBSERVED growth path, not a jump at the base year.  Regions of other states: sum of their counties
(a county split across regions is counted in the region that holds most of its zones).
Outputs: Validation_2026/2_silo/input/assumptions/populationControlTotalByRegion.csv (Year,Region,Population) and
         Validation_2026/data/silo_target_population_by_region.csv (observed PEP by region and year, for validation)."""
import pandas as pd, numpy as np, os
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; V = f"{ROOT}/Validation_2026"; RAW = f"{V}/data/raw/pep"
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
P = pd.concat([pep("co-est2020-alldata.csv", range(2016, 2020)), pep("co-est2025-alldata.csv", range(2020, 2026))], axis=1)
P[2026] = (P[2025] * (P[2025] / P[2024])).round()
P = P[P.index.isin(set(CW.county))]
M = CW.merge(P, left_on="county", right_index=True)
for y in range(2016, 2027): M[y] = M[y] * M.w
obs = M.groupby("region")[list(range(2016, 2027))].sum().round().astype(int)     # observed persons by region and year
# synthetic 2016 persons by region
dd = pd.read_csv(f"{V}/2_silo/input/microData/dd_2016.csv", usecols=["id", "zone", "hhID"]); hh = pd.read_csv(f"{V}/2_silo/input/microData/hh_2016.csv", usecols=["id", "dwelling", "hhSize"])
hh["zone"] = hh.dwelling.map(dd.set_index("id").zone); hh["region"] = hh.zone.map(z.set_index("ZoneId").Region)
base = hh.groupby("region").hhSize.sum()
rows = []
for r in obs.index:
    if r not in base.index: continue
    for y in range(2016, 2027):
        rows.append(dict(Year=y, Region=int(r), Population=int(round(base[r] * obs.at[r, y] / obs.at[r, 2016]))))
T = pd.DataFrame(rows); T.to_csv(f"{OUT}/populationControlTotalByRegion.csv", index=False)
obs.reset_index().melt(id_vars="region", var_name="year", value_name="persons_pep").to_csv(f"{V}/data/silo_target_population_by_region.csv", index=False)
cmp = pd.DataFrame({"synthetic_2016": base, "pep_2016": obs[2016], "pep_2024": obs[2024], "pep_2026_extrap": obs[2026]}).dropna()
cmp["synthetic/pep 2016"] = (cmp.synthetic_2016 / cmp.pep_2016).round(3); cmp["growth 2016-2024"] = (cmp.pep_2024 / cmp.pep_2016 - 1).round(3)
md = cmp[cmp.index > 24000]; md = md[md.index < 25000]
print(md.to_string()); print(f"\nall regions: synthetic 2016 {cmp.synthetic_2016.sum():,.0f} vs PEP {cmp.pep_2016.sum():,.0f} ({cmp.synthetic_2016.sum() / cmp.pep_2016.sum():.3f}); rows written {len(T)}")
