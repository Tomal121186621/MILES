#!/usr/bin/env python3
"""SILO base-year microdata for the rebuild: the corrected synthetic population (1_vae/vae_outputs/06_silo_input) plus the
vacant-job buffer SILO's labour market needs (every synthetic job is filled, 1:1 with workers; without vacancies no one can
take a job). The buffer is the observed BLS JOLTS job-openings rate (1_vae/vacancy_rate.json), not the 27 % of the old MSTM file.  Vacant jobs (personId = -1) are added per
zone and job type in proportion to the filled jobs there, so that vacancies = VACANCY_SHARE of all jobs; filled-job ids are
unchanged so pp.workplace links survive.  Output: 2_silo/input/microData/{hh,pp,dd,jj}_2016.csv"""
import pandas as pd, numpy as np, os, shutil
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; V = f"{ROOT}/Validation_2026"
SRC = f"{V}/1_vae/vae_outputs/06_silo_input"; OUT = f"{V}/2_silo/input/microData"; os.makedirs(OUT, exist_ok=True)
import json; VACANCY_SHARE = json.load(open(f"{V}/1_vae/vacancy_rate.json"))["job_openings_rate_2016"]; rng = np.random.default_rng(16)   # BLS JOLTS job-openings rate, not the inherited 27 %
# ---- vacant dwellings (stage-1 data item): the synthetic stock holds occupied dwellings only; SILO's moves, construction and pricing
# models need the vacant stock. Vacant units per zone from the 2010/2020 Census block counts interpolated to 2016
# (1_vae/zone_vacancy_2016.py; Maryland 214,743 units, 8.7 %); attributes (type, bedrooms, quality, cost, year built) drawn from the
# zone's occupied dwellings; hhID = -1. Other states: the Maryland vacancy rate of the zone's dwelling type (no block data here).
dd = pd.read_csv(f"{SRC}/dd_2016.csv"); vz = pd.read_csv(f"{V}/1_vae/output/zone_vacancy_2016.csv").set_index("zone_id")
# only market vacancies (for rent / for sale / rented or sold, not yet occupied) are available to movers: ACS PUMS 2013-17 VACS by
# 2010 PUMA (1_vae/market_vacancy_2016.py); seasonal, migrant-worker and other vacant units are withheld from the stock
MK = pd.read_csv(f"{V}/1_vae/output/market_vacancy_by_puma_2016.csv"); mkt = dict(zip(MK.PUMA.astype(int), MK.market_share)); mkt_md = MK.market_w.sum() / MK.vacant_w.sum()
zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").set_index("ZoneId")
occ = dd.groupby("zone").size(); md_rate = mkt_md * vz.loc[vz.STFIPS == 24, "vacant_2016"].sum() / (vz.loc[vz.STFIPS == 24, ["vacant_2016", "occupied_units_2016"]].sum().sum())
n_vac = {}
for zone, n in occ.items():
    if zone in vz.index and vz.at[zone, "STFIPS"] == 24: n_vac[zone] = int(round(vz.at[zone, "vacant_2016"] * n / max(vz.at[zone, "occupied_units_2016"], 1) * mkt.get(int(zs.at[zone, "PUMA_10"]) % 100000, mkt_md)))   # scaled to the synthetic occupied count; market vacancies only
    else: n_vac[zone] = int(round(n * md_rate / (1 - md_rate)))
next_id = dd.id.max() + 1; parts = []
for zone, k in n_vac.items():
    if k <= 0: continue
    src = dd[dd.zone == zone]; s = src.sample(n=k, replace=True, random_state=int(zone)).copy(); s["id"] = np.arange(next_id, next_id + k); s["hhID"] = -1; next_id += k; parts.append(s)
vac_dd = pd.concat(parts); dd_out = pd.concat([dd, vac_dd], ignore_index=True); dd_out.to_csv(f"{OUT}/dd_2016.csv", index=False)
print(f"dwellings: occupied {len(dd):,} + vacant {len(vac_dd):,} = {len(dd_out):,} (vacancy {len(vac_dd) / len(dd_out):.3f}; Maryland zones from Census blocks, other states at the Maryland rate)")
# ---- household role consistency (stage-1 data item): the land-use model pairs spouses by gender, so married pairs must be opposite-sex.
# The synthesizer draws gender and role independently: 10.5 % of married pairs are same-gender against 0.97 % in the ACS (married-couple
# households, PUMS 2014-2018 Maryland). Same-gender pairs beyond the ACS share get one partner's gender swapped, alternating which gender
# is swapped so that sex totals stay balanced; married persons under 18 and the surplus person of odd-count households become SINGLE.
pp = pd.read_csv(f"{SRC}/pp_2016.csv"); ACS_SAME_SEX = 0.0097
minors = (pp.relationShip == "MARRIED") & (pp.age < 18); pp.loc[minors, "relationShip"] = "SINGLE"
m = pp[pp.relationShip == "MARRIED"]; cnt = m.groupby("hhID").size(); odd = cnt[cnt % 2 == 1].index
surplus = m[m.hhID.isin(odd)].sort_values(["hhID", "age"]).groupby("hhID").head(1).index; pp.loc[surplus, "relationShip"] = "SINGLE"
m = pp[pp.relationShip == "MARRIED"]; pairs = m.groupby("hhID").agg(n=("gender", "size"), g=("gender", "nunique")); same = pairs[(pairs.n == 2) & (pairs.g == 1)]
keep = set(same.sample(n=int(round(ACS_SAME_SEX * len(pairs))), random_state=7).index); fix = same.index[~same.index.isin(keep)].to_numpy().copy(); rng.shuffle(fix)
first = m[m.hhID.isin(fix)].sort_values(["hhID", "id"]).groupby("hhID").nth(0).set_index("hhID"); second = m[m.hhID.isin(fix)].sort_values(["hhID", "id"]).groupby("hhID").nth(1).set_index("hhID")
pick = pd.Series(np.where(np.arange(len(fix)) % 2 == 0, first.loc[fix, "id"].values, second.loc[fix, "id"].values))   # alternate partner -> balanced sex totals
sw = pp.id.isin(pick); pp.loc[sw, "gender"] = np.where(pp.loc[sw, "gender"] == 1, 2, 1)
# keep the student-school assignment (schoolId, 2_silo/schools/assign_students.py) if the current file already carries it
if os.path.exists(f"{OUT}/pp_2016.csv") and "schoolId" in open(f"{OUT}/pp_2016.csv").readline():
    sch = pd.read_csv(f"{OUT}/pp_2016.csv", usecols=["id", "schoolId"]); pp = pp.merge(sch, on="id", how="left"); pp["schoolId"] = pp.schoolId.fillna(-1).astype(int)
pp.to_csv(f"{OUT}/pp_2016.csv", index=False)
m2 = pp[pp.relationShip == "MARRIED"]; p2 = m2.groupby("hhID").agg(n=("gender", "size"), g=("gender", "nunique"))
print(f"roles: married minors -> single {int(minors.sum()):,}; odd-count surplus -> single {len(surplus)}; same-gender married pairs {len(same):,} of {len(pairs):,} ({len(same) / len(pairs):.3%}) -> {int(((p2.n == 2) & (p2.g == 1)).sum()):,} kept ({ACS_SAME_SEX:.2%} ACS); gender swapped for {int(sw.sum()):,} persons; sex share male {(pp.gender == 1).mean():.4f}")
hh = pd.read_csv(f"{SRC}/hh_2016.csv"); n4 = int((hh.autos > 3).sum()); hh["autos"] = hh.autos.clip(upper=3)   # SILO convention: 0, 1, 2, 3+ cars
hh.to_csv(f"{OUT}/hh_2016.csv", index=False); print(f"households {len(hh):,}; cars clipped to 3+ for {n4:,} households")
jj = pd.read_csv(f"{SRC}/jj_2016.csv"); n_vac = int(round(len(jj) * VACANCY_SHARE / (1 - VACANCY_SHARE)))
cell = jj.groupby(["zone", "type"]).size(); p = cell / cell.sum()
draw = rng.choice(len(cell), size=n_vac, p=p.values); counts = pd.Series(draw).value_counts().sort_index()
rows = []; next_id = jj.id.max() + 1
for i, n in counts.items():
    z, t = cell.index[i]; rows.append(pd.DataFrame({"id": np.arange(next_id, next_id + n), "zone": z, "personId": -1, "type": t})); next_id += n
vac = pd.concat(rows); out = pd.concat([jj, vac], ignore_index=True); out.to_csv(f"{OUT}/jj_2016.csv", index=False)
print(f"jobs: filled {len(jj):,} + vacant {len(vac):,} = {len(out):,} (vacancy share {len(vac) / len(out):.3f}); by type: {out.type.value_counts().to_dict()}")
