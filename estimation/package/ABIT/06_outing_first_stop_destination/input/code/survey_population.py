#!/usr/bin/env python3
"""Stage 3, Roorda-style validation: the observed survey population as DAYMAP input, and the DAYMAP runs on it.

    python3 survey_population.py build                 # both halves -> 3_abit/survey_pop/<half>/
    python3 survey_population.py run --half estimation --seeds 1-10 [--xmx 8g]

Design (Roorda, Miller & Habib 2008, section 5): the model is applied to the OBSERVED population of the survey households, so
that the comparison with the observed travel of these households measures the error of the activity model alone, free of the
error of the synthetic population.  One input population per half of the 2017/18 Regional Travel Survey (data/rts_split.csv,
seed 2026): the estimation half (verification, the households the calibration targets come from) and the validation half
(validation, households never used by the calibration).

Households (RTS_raw_flat_data.csv, one record per household)
  home zone       the MSTM zone (ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp, 1,588 zones) that contains the
                  internal point of the household's 2010 census tract (home_state_county_fips + home_tract_fips; Census 2010
                  tract gazetteer, I695_pricing/data/census/Gaz_tracts_national.txt).  The TPB / BMC TAZ codes have no
                  crosswalk to the MSTM zones in the project; the tract is the finest geography with a public reference point.
                  Households whose tract point falls outside every zone are left out (counted in the build log).
  autos           numvehicle;  income: midpoint of hh_income_detailed (unknown: the weighted median class of the half).
Persons
  travellers      every person of the file (the file holds the persons with at least one trip on the travel day): age, gender
                  (RTS 1 female / 2 male written as the SILO codes 2 / 1; -9 -> drawn 50/50), licence (license 1; -9 -> licensed when 16+), occupation as the SILO codes DAYMAP reads:
                  age < 5 -> 0 toddler, employment_status 0 -> 1 employed, student_status 1 -> 3 student, employment_status 1 ->
                  4 retiree, else 2 unemployed (rts_common.person_type).
  non-travellers  hhsize minus the travellers of the household (the survey keeps their count, not their records).  Their role
                  follows the household counts: workers = numworkers - travelling workers, students = numstudents - travelling
                  students, the rest others; their age, gender and licence are copied from a donor drawn among the travellers
                  of the same role in the same half (weight wtperfin, seed 2026); licences beyond numdrivers are removed.
  weight          wtperfin for travellers, the household weight wthhfin for the imputed members (used to weight model output).
  workplace       employed persons with a usual work location (j1_workplace_loc 1, 2 or 4) and a work tract inside the zone
                  system: the zone of the work tract (workplace.reassign.file); the rest (work at home, unknown tract, imputed
                  workers): DAYMAP's own fallback, the RTS home-based work gravity (MarylandLosDataReader.sampleWorkZone).
  school          students with a school tract inside the zone system: the school record of the person's band (elementary 5-10,
                  middle 11-13, high 14-17, postsec 18+, as SILO) nearest to the tract point (schoolId of schools_2016.csv);
                  others schoolId -2, i.e. the SILO rule: the nearest school of the band from home.
Ids: households 10,000,001+, persons 20,000,001+ (outside the SILO id ranges, so the SILO job file read for the zone job counts
never attaches a synthetic job to a survey person); the map to the survey ids is in persons_map.csv.

Run (one DAYMAP at a time, <= 8 GB heap): the properties of the synthetic-population runs (make_abit_properties.py, coefficient
set coef_calibrated copied into the run as in run_abit.py) with households / persons / dwellings replaced by the survey
files, sample.fraction = 1, workplace.reassign.file, and zone.population.file = the 2016 base population per zone, read by the
class overlay survey_overlay/ (MarylandLosDataReader with the one optional property; 3_abit/classes is unchanged): the residents
attractor of the destination choice is then the full population, as in the synthetic runs, and not the survey sample.
"""
# COPY of Validation_2026/3_abit/survey_population.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import argparse, os, re, shutil, subprocess, sys, time
import numpy as np
import pandas as pd
from rts_common import ROOT, V, RTS, load_split, person_type, band_of

A3 = f"{SHARED}/rts_2017_18"; OUTD = f"{A3}/survey_pop"; RUNROOT = f"{A3}/run_survey"  # PATH
ZONES_SHP = f"{ROOT}/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918.shp"
GAZ = f"{ROOT}/I695_pricing/data/census/Gaz_tracts_national.txt"
SCHOOLS = f"{SHARED}/zones/schools_2016.csv"  # PATH          # read only
MICRO = f"{V}/2_silo/input/microData"                     # read only
HH0, PP0 = 10_000_000, 20_000_000
INC_MID = {1: 10000, 2: 20000, 3: 30000, 4: 42500, 5: 62500, 6: 87500, 7: 125000, 8: 200000}
OVERLAY = f"{A3}/survey_overlay/classes"


# ------------------------------------------------------------------------------------------------ geography
def tract_zone():
    """GEOID (11 digits, str) -> MSTM zone of the tract's internal point; plus the point (x, y, EPSG:26918)."""
    f = f"{OUTD}/tract_zone.csv"
    if os.path.exists(f): return pd.read_csv(f, dtype={"geoid": str})
    import geopandas as gpd
    g = pd.read_csv(GAZ, sep="\t", dtype={"GEOID": str}); g.columns = [c.strip() for c in g.columns]
    g = g[g.GEOID.str[:2].isin(["10", "11", "24", "42", "51", "54"])]
    pts = gpd.GeoDataFrame(g[["GEOID"]], geometry=gpd.points_from_xy(g.INTPTLONG.astype(float), g.INTPTLAT.astype(float)), crs="EPSG:4326").to_crs("EPSG:26918")
    z = gpd.read_file(ZONES_SHP)[["id", "geometry"]]
    j = gpd.sjoin(pts, z, how="left", predicate="within").drop_duplicates("GEOID")
    out = pd.DataFrame({"geoid": j.GEOID.values, "zone": j["id"].fillna(-1).astype(int).values, "x": j.geometry.x.values, "y": j.geometry.y.values})
    os.makedirs(OUTD, exist_ok=True); out.to_csv(f, index=False); return out


def geoid(county, tract):
    c = pd.to_numeric(county, errors="coerce"); t = pd.to_numeric(tract, errors="coerce")
    ok = (c > 0) & (t >= 0) & (t < 999999)
    return pd.Series(np.where(ok, c.fillna(0).astype(int).map("{:05d}".format) + t.fillna(0).astype(int).map("{:06d}".format), ""), index=county.index)


def zone_population():
    """Persons of the 2016 base population per zone (residents attractor of the destination choice)."""
    f = f"{OUTD}/zone_population_2016.csv"
    if os.path.exists(f): return f
    pp = pd.read_csv(f"{MICRO}/pp_2016.csv", usecols=["hhID"]); dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["hhID", "zone"])
    n = pp.groupby("hhID").size(); dd = dd[dd.hhID > 0].drop_duplicates("hhID"); dd["persons"] = dd.hhID.map(n).fillna(0)
    dd.groupby("zone").persons.sum().astype(int).reset_index().to_csv(f, index=False); return f


# ------------------------------------------------------------------------------------------------ population
def build(half, seed=2026):
    rng = np.random.default_rng(seed + (0 if half == "estimation" else 1))
    tz = tract_zone().set_index("geoid"); split = load_split()
    cols = ["household_id", "person_id", "home_state_county_fips", "home_tract_fips", "hhsize", "numworkers", "numstudents", "numdrivers", "numvehicle",
            "hh_income_detailed", "wthhfin", "age", "gender", "license", "employment_status", "student_status", "school_type", "j1_workplace_loc",
            "work_state_county_fips", "work_tract_fips", "school_state_county_fips", "school_tract_fips", "wtperfin"]
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv.gz", usecols=cols, low_memory=False)
    r = r[r.household_id.map(split).eq(half)]
    h = r.drop_duplicates("household_id").set_index("household_id")
    p = r.drop_duplicates("person_id").set_index("person_id").copy()
    log = {"half": half, "households_survey": len(h), "travellers_survey": len(p), "hhsize_sum": int(h.hhsize.sum())}
    # home zone
    h["geoid"] = geoid(h.home_state_county_fips, h.home_tract_fips)
    h["zone"] = h.geoid.map(tz.zone).fillna(-1).astype(int)
    log["households_tract_known"] = int((h.geoid != "").sum()); log["households_zone"] = int((h.zone > 0).sum())
    log["households_zone_weighted_share"] = float(h.wthhfin[h.zone > 0].sum() / h.wthhfin.sum())
    h = h[h.zone > 0]; p = p[p.household_id.isin(h.index)]
    # income: midpoint of the detailed class; unknown -> weighted median class of the half
    cls = h.hh_income_detailed.where(h.hh_income_detailed > 0)
    k = cls.dropna(); o = np.argsort(k.values); cw = np.cumsum(h.wthhfin[k.index].values[o]); med = int(k.values[o][np.searchsorted(cw, cw[-1] / 2)])
    h["income"] = cls.fillna(med).astype(int).map(INC_MID)
    # travellers
    p["occ"] = 2
    p.loc[p.employment_status.eq(1), "occ"] = 4
    p.loc[p.student_status.eq(1), "occ"] = 3
    p.loc[p.employment_status.eq(0), "occ"] = 1
    p.loc[p.age < 5, "occ"] = 0
    p["role"] = np.select([p.occ.eq(1), p.occ.eq(3)], ["worker", "student"], "other")
    # RTS GENDER 1 female, 2 male -> SILO gender 1 male, 2 female (Gender.valueOf); -9 drawn 1/2 50/50 in the RTS coding, then mapped
    p["gender_m"] = 3 - np.where(p.gender.isin([1, 2]), p.gender, rng.integers(1, 3, len(p)))
    p["lic"] = np.where(p.license.eq(1), True, np.where(p.license.eq(2), False, p.age >= 16)) & (p.age >= 15)
    p["w"] = p.wtperfin; p["imputed"] = False
    # non-travelling members (donor imputation within the half)
    trav = p.groupby("household_id").agg(nt=("age", "size"), nw=("role", lambda s: (s == "worker").sum()), ns=("role", lambda s: (s == "student").sum()), nl=("lic", "sum"))
    h = h.join(trav); miss = (h.hhsize - h.nt).clip(lower=0)
    donors = {ro: p[p.role == ro] for ro in ["worker", "student", "other"]}
    rows = []
    for hid, m in miss[miss > 0].items():
        hr = h.loc[hid]; mw = int(max(0, hr.numworkers - hr.nw)); ms = int(max(0, hr.numstudents - hr.ns))
        roles = (["worker"] * mw + ["student"] * ms)[:int(m)]; roles += ["other"] * (int(m) - len(roles))
        lic_left = int(max(0, hr.numdrivers - hr.nl)) if hr.numdrivers >= 0 else 99
        for ro in roles:
            d = donors[ro]; j = rng.choice(len(d), p=(d.w / d.w.sum()).values); dr = d.iloc[j]
            lic = bool(dr.lic) and lic_left > 0; lic_left -= int(lic)
            rows.append(dict(household_id=hid, age=dr.age, gender_m=dr.gender_m, lic=lic, occ=dr.occ, role=ro, w=hr.wthhfin, imputed=True,
                             employment_status=dr.employment_status, student_status=dr.student_status, j1_workplace_loc=-9, work_state_county_fips=-9,
                             work_tract_fips=-9, school_state_county_fips=-9, school_tract_fips=-9))
    imp = pd.DataFrame(rows); imp.index = pd.Index([-(i + 1) for i in range(len(imp))], name="person_id")
    log["persons_imputed"] = len(imp)
    pa = pd.concat([p.reset_index(), imp.reset_index()], ignore_index=True)
    pa = pa.sort_values(["household_id", "imputed", "age"], ascending=[True, True, False], kind="stable").reset_index(drop=True)
    # ids
    hid_new = pd.Series(np.arange(1, len(h) + 1) + HH0, index=h.index)
    pa["id"] = np.arange(1, len(pa) + 1) + PP0; pa["hhID"] = pa.household_id.map(hid_new)
    # income per person: household income split over workers (else adults 18+)
    nw = pa.groupby("household_id").occ.apply(lambda s: (s == 1).sum()); na = pa.groupby("household_id").age.apply(lambda s: (s >= 18).sum()).clip(lower=1)
    hw = pa.household_id.map(nw); inc = pa.household_id.map(h.income)
    pa["income"] = np.where(hw > 0, np.where(pa.occ == 1, inc / hw.clip(lower=1), 0), np.where(pa.age >= 18, inc / pa.household_id.map(na), 0)).round().astype(int)
    # relationship: the two oldest adults of a household with 2+ adults married, other adults single, under 18 child
    pa["adult_rank"] = pa[pa.age >= 18].groupby("household_id").age.rank(method="first", ascending=False)
    nad = pa.household_id.map(pa[pa.age >= 18].groupby("household_id").size()).fillna(0)
    pa["rel"] = np.where(pa.age < 18, "CHILD", np.where((nad >= 2) & (pa.adult_rank <= 2), "MARRIED", "SINGLE"))
    # workplace zone
    pa["work_geoid"] = geoid(pa.work_state_county_fips, pa.work_tract_fips)
    pa["work_zone"] = pa.work_geoid.map(tz.zone).fillna(-1).astype(int)
    usual = pa.j1_workplace_loc.isin([1, 2, 4]) & (pa.occ == 1)
    pa.loc[~usual, "work_zone"] = -1
    wk = pa.occ == 1
    log["workers"] = int(wk.sum()); log["workers_imputed"] = int((wk & pa.imputed).sum())
    log["workers_home_based_job"] = int((wk & pa.j1_workplace_loc.eq(3)).sum())
    log["workers_work_zone"] = int((wk & (pa.work_zone > 0)).sum())
    # school record nearest to the school tract point, same band
    sc = pd.read_csv(SCHOOLS, usecols=["id", "zone", "band", "coordX", "coordY"])
    pa["band"] = band_of(pa.age.clip(lower=5)).values
    pa["school_geoid"] = geoid(pa.school_state_county_fips, pa.school_tract_fips)
    st = (pa.occ == 3) & pa.school_geoid.ne("") & pa.school_geoid.isin(tz.index)
    st &= pa.school_geoid.map(tz.zone).fillna(-1).gt(0)
    pa["schoolId"] = np.where(pa.occ == 3, -2, -1)
    for b, g in pa[st].groupby("band"):
        s = sc[sc.band == b]
        if len(s) == 0: continue
        xy = tz.loc[g.school_geoid, ["x", "y"]].values
        d2 = (xy[:, None, 0] - s.coordX.values[None, :]) ** 2 + (xy[:, None, 1] - s.coordY.values[None, :]) ** 2
        pa.loc[g.index, "schoolId"] = s.id.values[d2.argmin(axis=1)]
    log["students"] = int((pa.occ == 3).sum()); log["students_school_record"] = int((pa.schoolId > 0).sum())
    log["persons_total"] = len(pa); log["households_total"] = len(h)
    # files in the SILO formats DAYMAP reads
    od = f"{OUTD}/{half}"; os.makedirs(od, exist_ok=True)
    hh = pd.DataFrame({"id": hid_new.values, "dwelling": hid_new.values, "hhSize": pa.groupby("hhID").size().reindex(hid_new.values).values,
                       "autos": h.numvehicle.clip(lower=0).astype(int).values, "income": h.income.values, "race": "other"})
    hh.to_csv(f"{od}/hh.csv", index=False)
    pd.DataFrame({"id": hid_new.values, "zone": h.zone.values, "type": "SFD", "hhID": hid_new.values, "bedrooms": 3, "quality": 3, "monthlyCost": 1000,
                  "restriction": 0, "yearBuilt": 2000}).to_csv(f"{od}/dd.csv", index=False)
    pd.DataFrame({"id": pa.id, "hhID": pa.hhID, "age": pa.age.astype(int), "gender": pa.gender_m.astype(int), "race": "other", "occupation": pa.occ.astype(int),
                  "driversLicense": np.where(pa.lic, "True", "False"), "workplace": np.where(pa.occ == 1, 0, -1), "income": pa.income, "nationality": 1,
                  "relationShip": pa.rel, "schoolId": pa.schoolId.astype(int)}).to_csv(f"{od}/pp.csv", index=False)
    wz = pa[pa.work_zone > 0]
    pd.DataFrame({"person_id": wz.id, "home_zone": wz.hhID.map(pd.Series(h.zone.values, index=hid_new.values)), "work_zone": wz.work_zone}).to_csv(f"{od}/workplace_reassign.csv", index=False)
    pm = pa[["id", "hhID", "household_id", "person_id", "age", "occ", "role", "imputed", "w", "work_zone", "schoolId"]].copy()
    pm["home_zone"] = pm.hhID.map(pd.Series(h.zone.values, index=hid_new.values)); pm["county"] = pm.household_id.map(h.home_state_county_fips)
    pm["wthhfin"] = pm.household_id.map(h.wthhfin)
    pm.to_csv(f"{od}/persons_map.csv", index=False)
    pd.Series(log).to_csv(f"{od}/build_log.csv", header=["value"]); print(pd.Series(log).to_string())
    return log


# ------------------------------------------------------------------------------------------------ DAYMAP run
def run(half, seed, xmx="8g", threads=6, coef=f"{A3}/coef_calibrated", force=False, tag="", skims=f"{A3}/skims"):
    """tag: run-name infix (svy_<half>_<tag>_s<seed>), e.g. 'mnl' for the runs with the estimated destination MNL (2026-10-22);
    the coefficient set decides the model (dest.choice.model in <coef>/run_params.csv)."""
    name = f"svy_{half[:3]}_{tag + '_' if tag else ''}s{seed:02d}"; d = f"{RUNROOT}/{name}"; outs = [f"{d}/output/activities_{name}.csv", f"{d}/output/legs_{name}.csv"]
    if all(os.path.exists(o) for o in outs) and not force: print(f"{name}: output exists, skipped"); return d
    os.makedirs(d, exist_ok=True); rc = f"{d}/coef"; shutil.rmtree(rc, ignore_errors=True); shutil.copytree(coef, rc)
    env = dict(os.environ) | {"ABIT_RUN_ROOT": RUNROOT, "ABIT_COEF_DIR": rc}
    r = subprocess.run([sys.executable, f"{A3}/make_abit_properties.py", name, "base", "2016", "1.0", skims], capture_output=True, text=True, env=env)
    if r.returncode != 0: raise SystemExit(f"make_abit_properties failed: {r.stdout}{r.stderr}")
    props = f"{RUNROOT}/{name}.properties"; t = open(props).read(); od = f"{OUTD}/{half}"
    for k, v in [("households.file", f"{od}/hh.csv"), ("persons.file", f"{od}/pp.csv"), ("dwellings.file", f"{od}/dd.csv"), ("number.of.threads", str(threads))]:
        t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
    t += f"\n# survey population (survey_population.py)\nworkplace.reassign.file = {od}/workplace_reassign.csv\nzone.population.file = {zone_population()}\n"
    open(props, "w").write(t)
    java = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"
    cp = f"{OVERLAY}:{A3}/classes:{open(f'{A3}/abit_classpath.txt').read().strip()}"
    cmd = [java, f"-Xmx{xmx}", f"-Dabit.seed={seed}", f"-Djava.library.path={ROOT}/ABIT/src/main/resources/lib/macosx64", "-cp", cp, "abm.RunAbitMarylandLos", props]
    t0 = time.time()
    with open(f"{d}/abit.log", "w") as log:
        log.write(f"# {name}: survey population {half}, seed {seed}, coef {coef}, started {time.ctime()}\n"); log.flush()
        code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=d).returncode
    ok = code == 0 and all(os.path.exists(o) for o in outs)
    print(f"{name}: rc {code}, {time.time() - t0:.0f} s, outputs {'ok' if ok else 'MISSING'}", flush=True)
    if not ok: raise SystemExit(f"ABIT {name} failed; see {d}/abit.log")
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "run"]); ap.add_argument("--half", default="both"); ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--xmx", default="8g"); ap.add_argument("--threads", type=int, default=6); ap.add_argument("--force", action="store_true")
    ap.add_argument("--tag", default=""); ap.add_argument("--coef", default=f"{A3}/coef_calibrated"); ap.add_argument("--skims", default=f"{A3}/skims")
    a = ap.parse_args(); halves = ["estimation", "validation"] if a.half == "both" else [a.half]
    if a.cmd == "build":
        zone_population()
        for hf in halves: build(hf)
    else:
        lo, hi = (int(x) for x in a.seeds.split("-"))
        for hf in halves:
            for s in range(lo, hi + 1): run(hf, s, a.xmx, a.threads, coef=a.coef, force=a.force, tag=a.tag, skims=a.skims)
