#!/usr/bin/env python3
# Copy of 2_silo/resloc/s01_geography.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Geography of the residential location estimation.

PUMS records carry the 2010 PUMA of the current residence, the migration PUMA (MIGPUMA) of the residence one year ago and the
place-of-work PUMA (POWPUMA).  These are linked to the 44 SILO regions and 1,588 zones through 2010 census tracts:
  tract -> zone      internal point of the tract in the MSTM zone polygons (3_abit/survey_pop/tract_zone.csv)
  tract -> PUMA      Census 2010 tract-to-PUMA relationship file (data/raw/resloc/2010_Census_Tract_to_2010_PUMA.txt)
  PUMA -> MIGPUMA / POWPUMA   IPUMS 2010 crosswalk puma_migpuma1_pwpuma00.xls (data/raw/resloc/)
  tract weights      2010 housing units HU10 of the Census 2010 tract gazetteer
Outputs (work/):
  geo_zone.csv          zone, region, county, state, dwellings 2016 (synthetic stock), jobs 2016, households 2016
  geo_puma_region.csv   puma7 (state*100000+puma), region, share of the PUMA's in-area HU10 in the region, coverage of the PUMA by the zone system
  geo_mig_zone.csv      mig7 (state*100000+migpuma), zone, weight (dwellings 2016 of the zone x in-area HU share); same for pow (jobs weight)
"""
import numpy as np, pandas as pd
from rc import *

z = zones()
dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["zone", "hhID"])
jj = pd.read_csv(f"{MICRO}/jj_2016.csv", usecols=["zone"])
z["dwellings"] = z.zone.map(dd.groupby("zone").size()).fillna(0)
z["households"] = z.zone.map(dd[dd.hhID > 0].groupby("zone").size()).fillna(0)
z["jobs"] = z.zone.map(jj.groupby("zone").size()).fillna(0)
z.to_csv(f"{WORK}/geo_zone.csv", index=False)

tz = pd.read_csv(TRACT_ZONE, dtype={"geoid": str})
gaz = pd.read_csv(GAZ, sep="\t", dtype={"GEOID": str}); gaz.columns = [c.strip() for c in gaz.columns]
tp = pd.read_csv(f"{RAW}/2010_Census_Tract_to_2010_PUMA.txt", dtype=str)
tp["geoid"] = tp.STATEFP + tp.COUNTYFP + tp.TRACTCE
tp = tp[tp.STATEFP.astype(int).isin(STATES.values())]
tp["puma7"] = tp.STATEFP.astype(int) * 100000 + tp.PUMA5CE.astype(int)
tp = tp.merge(gaz[["GEOID", "HU10"]], left_on="geoid", right_on="GEOID", how="left").merge(tz[["geoid", "zone"]], on="geoid", how="left")
tp["zone"] = tp.zone.fillna(-1).astype(int)
tp["region"] = tp.zone.map(z.set_index("zone").region).fillna(-1).astype(int)
tot = tp.groupby("puma7").HU10.sum()
ina = tp[tp.zone > 0].groupby(["puma7", "region"]).HU10.sum().rename("hu").reset_index()
ina["share"] = ina.hu / ina.groupby("puma7").hu.transform("sum")
ina["coverage"] = ina.puma7.map(ina.groupby("puma7").hu.sum() / tot)
ina.to_csv(f"{WORK}/geo_puma_region.csv", index=False)

# PUMA -> zone weights inside the PUMA: dwellings of the zone (the zone's tract points define membership)
tz_puma = tp[tp.zone > 0].groupby(["puma7", "zone"]).HU10.sum().rename("hu").reset_index()
tz_puma.to_csv(f"{WORK}/geo_puma_zone.csv", index=False)

x = pd.read_excel(f"{RAW}/puma_migpuma1_pwpuma00.xls", header=None, skiprows=3, dtype=str).iloc[:, :4]
x.columns = ["st", "puma", "powst", "mig"]
x = x.dropna(); x = x[x.st.str.strip().str.isdigit()]
x["puma7"] = x.st.astype(int) * 100000 + x.puma.astype(int)
x["mig7"] = x.powst.astype(int) * 100000 + x.mig.astype(int)
x = x[x.st.astype(int).isin(STATES.values())]
x[["puma7", "mig7"]].drop_duplicates().to_csv(f"{WORK}/geo_puma_mig.csv", index=False)
# MIGPUMA (= POWPUMA geography in 2010) -> zones, with zone weights by dwellings (origins) and by jobs (workplaces)
m = tz_puma.merge(x[["puma7", "mig7"]], on="puma7")
m = m.groupby(["mig7", "zone"]).hu.sum().reset_index()
m["w_dd"] = m.zone.map(z.set_index("zone").dwellings)
m["w_jobs"] = m.zone.map(z.set_index("zone").jobs)
mig_tot = tp.merge(x[["puma7", "mig7"]], on="puma7").groupby("mig7").HU10.sum()
m["coverage"] = m.mig7.map(m.groupby("mig7").hu.sum() / mig_tot)
m.to_csv(f"{WORK}/geo_mig_zone.csv", index=False)

print(f"zones {len(z)}, regions {z.region.nunique()}; dwellings 2016 {z.dwellings.sum():,.0f}, jobs {z.jobs.sum():,.0f}")
c = ina.groupby("puma7").agg(n=("region", "size"), cov=("coverage", "first"))
print(f"PUMAs touching the zone system {len(c)}; fully covered (>=0.99) {(c['cov'] >= .99).sum()}; partly {(c['cov'] < .99).sum()}; multi-region {(c.n > 1).sum()}")
print(c[c['cov'] < .99].to_string())
mc = m.groupby("mig7").coverage.first()
print(f"MIGPUMAs touching the zone system {len(mc)}; partly covered {(mc < .99).sum()}")
