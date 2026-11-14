#!/usr/bin/env python3
"""Observed 2024 population as ABIT input (the design of Roorda, Miller & Habib 2008, section 5: the model is applied to the
observed population of the forecast year), built from the ACS 2024 1-year PUMS of Maryland.

    python3 -I activity/lib/reporting_2024/build_population.py [--silo oos_s1] [--frac 0.05] [--seed 2024]   -> temporal_2024/pop_acs2024/

Households   housing units of the ACS 2024 1-year file (TYPEHUGQ 1, NP > 0; group quarters are not modelled by ABIT or SILO).
             Each record is copied floor(f WGTP) times plus once more with probability f WGTP - floor(f WGTP) (f = 0.05, seed
             2024), so that the copies are a 5 % sample of the weighted households, the sample rate of the synthetic runs.
Home zone    drawn for every copy among the MSTM zones of its 2020 PUMA (zone representative point in the TIGER 2022 PUMA
             polygon), with probability proportional to the households of the zone in the SILO 2024 forecast (scenario --silo,
             microData/futureYears/dd_2024.csv: occupied dwellings).  The PUMA total is the ACS total; only the split inside the
             PUMA comes from SILO.
Persons      the household's ACS persons.  Occupation (the rule of the population synthesis, Updated VAE preprocessing.py, coded
             as ABIT reads the SILO file): age < 6 toddler (0); ESR 1, 2, 4, 5 employed (1); SCHG present student (3);
             ESR 3 unemployed (2); age 62+ and ESR 6 retiree (4); else other (2).  Driver's licence: the same rule (age 16+ and
             not walking, cycling or 'other' to work).  Income: PINCP x ADJINC, in 2016 dollars (CPI-U 2024 / 2016 = 313.689 /
             240.007), the price base of the SILO incomes; negative -> 0.  Autos: VEH capped at 3 (as the SILO files).
             Relationship (RELSHIPP): reference person and spouse married when a spouse is present, children under 18 child,
             everyone else single.
Workplace    commuters (at work, JWTRNS not 11) with a place of work in DC, DE, MD, PA, VA or WV: a zone drawn among the zones
             of their place-of-work PUMA (a county or a group of counties) with probability proportional to the LODES 2022
             jobs of the zone (bench_lodes.py).  Workers who worked at home, were not at work, or work outside the six states
             get no workplace record, so that ABIT's own fallback (its home-based work gravity) places them, as in the
             survey-population runs.
School       students (occupation 3) get a school record by the stage-2b rule (2_silo/schools/assign_students.py): schools of
             the band's type ranked by (band mismatch, car time from the home zone, -capacity, id), the first with a free seat,
             students in random order (seed 1), seats = capacity x f (rounded up); the 2024 school inventory of the SILO run.
Ids          households 800,000,001+, persons 900,000,001+ (outside the SILO id ranges, so no SILO job is attached).
Outputs      hh.csv, pp.csv, dd.csv (SILO formats), workplace_reassign.csv, zone_population_2024.csv (SILO 2024 persons per zone:
             the residents attractor of the destination choice), persons_map.csv (ACS attributes of every person), build_log.csv.
"""
import argparse, os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import t24common as C

CPI = 240.007 / 313.689           # CPI-U annual average 2016 / 2024
HH0, PP0 = 800_000_000, 900_000_000
STATES = [10, 11, 24, 42, 51, 54]
BAND_TYPE = {1: 1, 2: 2, 3: 2, 4: 3}; BANDS = {"elementary": 1, "middle": 2, "high": 3, "postsec": 4}


def silo_dir(scen): return f"{C.V}/2_silo/run/base/scenOutput/{scen}/microData/futureYears"


def read_zip(z, name, cols):
    with zipfile.ZipFile(z) as f:
        with f.open(name) as g: return pd.read_csv(g, usecols=cols, dtype={"SERIALNO": str}, low_memory=False)


def main(scen, frac, seed):
    rng = np.random.default_rng(seed); od = f"{C.T24}/pop_acs2024"; os.makedirs(od, exist_ok=True); log = {"silo_scenario": scen, "fraction": frac}
    h = read_zip(f"{C.PUMS1}/csv_hmd.zip", "psam_h24.csv", ["SERIALNO", "PUMA", "WGTP", "NP", "VEH", "TYPEHUGQ"])
    h = h[(h.TYPEHUGQ == 1) & (h.NP > 0)].copy(); log["acs_households"] = len(h); log["acs_households_weighted"] = int(h.WGTP.sum())
    pc = ["SERIALNO", "SPORDER", "AGEP", "SEX", "ESR", "SCHG", "JWTRNS", "JWDP", "JWMNP", "JWRIP", "POWSP", "POWPUMA", "PINCP", "ADJINC", "RELSHIPP", "PWGTP", "WKHP"]
    p = read_zip(f"{C.PUMS1}/csv_pmd.zip", "psam_p24.csv", pc); p = p[p.SERIALNO.isin(h.SERIALNO)].copy()
    # ---- copies of the households
    x = frac * h.WGTP.values; k = np.floor(x).astype(int) + (rng.random(len(h)) < x - np.floor(x))
    hc = h.loc[h.index.repeat(k)].reset_index(drop=True); hc["hid"] = np.arange(1, len(hc) + 1) + HH0
    log["households"] = len(hc)
    # ---- home zone inside the PUMA, by the SILO 2024 households per zone
    dd = pd.read_csv(f"{silo_dir(scen)}/dd_2024.csv", usecols=["id", "zone", "hhID"]); occ_dd = dd[dd.hhID > 0]
    zhh = occ_dd.zone.value_counts(); zp = C.zone_puma20()
    zz = pd.DataFrame({"zone": zp.index, "puma": zp.values}); zz["w"] = zz.zone.map(zhh).fillna(0)
    hc["zone"] = 0
    for pu, g in hc.groupby("PUMA"):
        c = zz[zz.puma == pu]; w = c.w.values if c.w.sum() > 0 else np.ones(len(c))
        hc.loc[g.index, "zone"] = rng.choice(c.zone.values, size=len(g), p=w / w.sum())
    # ---- persons
    pp = hc[["SERIALNO", "hid", "zone"]].merge(p, on="SERIALNO").sort_values(["hid", "SPORDER"]).reset_index(drop=True)
    pp["id"] = np.arange(1, len(pp) + 1) + PP0; a = pp.AGEP.values; esr = pp.ESR.fillna(6).values; schg = pp.SCHG.fillna(0).values
    pp["occ"] = np.where(a < 6, 0, np.where(np.isin(esr, [1, 2, 4, 5]), 1, np.where(schg > 0, 3, np.where(esr == 3, 2, np.where((a >= 62) & (esr == 6), 4, 2)))))
    jw = pp.JWTRNS.fillna(0).values
    pp["lic"] = (a >= 16) & ~np.isin(jw, [9, 10, 12])
    pp["income"] = np.maximum(0, pp.PINCP.fillna(0) * pp.ADJINC / 1e6 * CPI).round().astype(int)
    rel = pp.RELSHIPP.fillna(36).values
    has_sp = pp.hid.map(pp.assign(sp=np.isin(rel, [21, 23])).groupby("hid").sp.any())
    pp["rel"] = np.where(np.isin(rel, [21, 23]) | ((rel == 20) & has_sp), "married", np.where(a < 18, "child", "single"))
    # ---- workplace: zone within the place-of-work PUMA by LODES 2022 jobs
    cg = C.county_group(); zj = pd.read_csv(f"{C.OUT}/lodes2022_zone_jobs.csv"); zj["unit"] = zj.county.map(cg.unit)
    com = (pp.occ == 1) & pp.ESR.isin([1, 4]) & pp.JWTRNS.notna() & (pp.JWTRNS != 11) & pp.POWSP.isin(STATES) & pp.POWPUMA.notna()
    pp["work_unit"] = np.where(com, pp.POWSP.fillna(0).astype(int) * 100000 + pp.POWPUMA.fillna(0).astype(int), -1)
    pp["work_zone"] = -1
    for u, g in pp[com].groupby("work_unit"):
        c = zj[zj.unit == u].groupby("zone").jobs.sum()
        if len(c) == 0: continue
        pp.loc[g.index, "work_zone"] = rng.choice(c.index.values, size=len(g), p=(c / c.sum()).values)
    wk = pp.occ == 1
    log["persons"] = len(pp); log["workers"] = int(wk.sum()); log["workers_commuting_with_zone"] = int((pp.work_zone > 0).sum())
    log["workers_worked_at_home"] = int((wk & (pp.JWTRNS == 11)).sum()); log["workers_not_at_work"] = int((wk & pp.ESR.isin([2, 5])).sum())
    log["workers_outside_six_states_or_unplaced"] = int((wk & (pp.work_zone <= 0) & ~(pp.JWTRNS == 11) & ~pp.ESR.isin([2, 5])).sum())
    # ---- school: stage-2b rule on the SILO 2024 inventory
    sch = pd.read_csv(f"{silo_dir(scen)}/schools_2024.csv") if os.path.exists(f"{silo_dir(scen)}/schools_2024.csv") else pd.read_csv(f"{C.V}/2_silo/input/schools_2016.csv")
    full = pd.read_csv(f"{C.V}/2_silo/input/schools.csv", usecols=["id", "band"]).set_index("id").band
    sch["band_code"] = sch.id.map(full).map(BANDS).fillna(0).astype(int); sch["seats"] = np.ceil(sch.capacity * frac).astype(int)
    sk = pd.read_csv(f"{C.V}/2_silo/input/skims/auto_peak_time.csv.gz"); NZ = int(max(sk.FROM.max(), sk.TO.max(), sch.zone.max())) + 1
    T = np.full((NZ, NZ), np.nan); T[sk.FROM.values, sk.TO.values] = sk.VALUE.values; del sk
    import geopandas as gpd
    zg = gpd.read_file(C.ZONES_SHP); cen = zg.geometry.centroid; cx = pd.Series(cen.x.values, index=zg["id"].astype(int)); cy = pd.Series(cen.y.values, index=zg["id"].astype(int))
    st = pp[pp.occ == 3].copy(); st["band"] = np.select([st.AGEP < 11, st.AGEP < 14, st.AGEP < 18], [1, 2, 3], default=4)
    typ = sch.type.values; sb = sch.band_code.values; sz = sch.zone.values.astype(int); cap = sch.capacity.values; sid = sch.id.values
    occs = np.zeros(len(sch), int); seats = sch.seats.values; rank = {}; ptr = {}
    def ranking(z, b):
        if (z, b) in rank: return rank[(z, b)]
        cand = np.where(typ == BAND_TYPE[b])[0]; m = T[z, sz[cand]]; ok = np.isfinite(m) & (m > 0)
        if not ok.all(): m = np.where(ok, m, np.hypot(sch.coordX.values[cand] - cx.get(z, np.nan), sch.coordY.values[cand] - cy.get(z, np.nan)) / 500.0)
        mis = (sb[cand] != 0) & (sb[cand] != b); r = cand[np.lexsort((sid[cand], -cap[cand], m, mis))]; rank[(z, b)] = r; return r
    order = np.random.default_rng(1).permutation(len(st)); out = np.full(len(st), -2); zs = st.zone.values; bs = st.band.values
    for i in order:
        r = ranking(zs[i], bs[i]); q = ptr.get((zs[i], bs[i]), 0)
        while q < len(r) and occs[r[q]] >= seats[r[q]]: q += 1
        ptr[(zs[i], bs[i])] = q; s = r[q] if q < len(r) else r[0]; occs[s] += 1; out[i] = sid[s]
    pp["schoolId"] = -1; pp.loc[st.index, "schoolId"] = out
    log["students"] = len(st); log["students_with_school"] = int((out > 0).sum())
    # ---- files
    hc["hhSize"] = hc.hid.map(pp.groupby("hid").size()).astype(int); hc["autos"] = hc.VEH.fillna(0).clip(0, 3).astype(int)
    hc["income"] = hc.hid.map(pp.groupby("hid").income.sum()).fillna(0).astype(int)
    pd.DataFrame({"id": hc.hid, "dwelling": hc.hid, "hhSize": hc.hhSize, "autos": hc.autos, "income": hc.income, "race": "other"}).to_csv(f"{od}/hh.csv", index=False)
    pd.DataFrame({"id": hc.hid, "zone": hc.zone, "type": "SFD", "hhID": hc.hid, "bedrooms": 3, "quality": 3, "monthlyCost": 1000, "restriction": 0,
                  "yearBuilt": 2000}).to_csv(f"{od}/dd.csv", index=False)
    pd.DataFrame({"id": pp.id, "hhID": pp.hid, "age": pp.AGEP.astype(int), "gender": pp.SEX.astype(int), "race": "other", "occupation": pp.occ.astype(int),
                  "driversLicense": np.where(pp.lic, "True", "False"), "workplace": np.where(pp.occ == 1, 0, -1), "income": pp.income, "nationality": 1,
                  "relationShip": pp.rel, "schoolId": pp.schoolId.astype(int)}).to_csv(f"{od}/pp.csv", index=False)
    w = pp[pp.work_zone > 0]
    pd.DataFrame({"person_id": w.id, "home_zone": w.zone, "work_zone": w.work_zone}).to_csv(f"{od}/workplace_reassign.csv", index=False)
    pm = pp[["id", "hid", "SERIALNO", "SPORDER", "zone", "AGEP", "SEX", "occ", "ESR", "SCHG", "JWTRNS", "JWDP", "JWMNP", "JWRIP", "POWSP", "POWPUMA", "work_unit", "work_zone", "schoolId", "PWGTP"]].copy()
    pm["county"] = pm.zone.map(C.zone_county()); pm.to_csv(f"{od}/persons_map.csv", index=False)
    # residents attractor: SILO 2024 persons per zone
    hh = pd.read_csv(f"{silo_dir(scen)}/hh_2024.csv", usecols=["id", "dwelling", "hhSize"]); hz = hh.dwelling.map(dd.set_index("id").zone)
    zpop = hh.hhSize.groupby(hz).sum().astype(int).rename("persons"); zpop.index.name = "zone"; zpop.reset_index().to_csv(f"{od}/zone_population_2024.csv", index=False)
    log["silo_2024_persons"] = int(zpop.sum())
    pd.Series(log).to_csv(f"{od}/build_log.csv", header=["value"]); print(pd.Series(log).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--silo", default="oos_s1_pass3"); ap.add_argument("--frac", type=float, default=0.05); ap.add_argument("--seed", type=int, default=2024)
    a = ap.parse_args(); main(a.silo, a.frac, a.seed)
