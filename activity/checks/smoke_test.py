#!/usr/bin/env python3
"""Smoke run of the re-specified DAYMAP models (coefficient set activity/parameters, formerly 3_abit/coef_respec, 2026-11-09) on the fin24 inputs: SILO 2024
population of seed 5 (persons and schools after the schools step), skims base_transit2024, base-year attendance (no telework
input), DAYMAP seed 1, 1 % household sample.  Reference: the model of record (the fin24 snapshot final_2024/frozen: coef_tasha and
its classes) on the same 1 % sample and seed, and the fin24 runs (10 %, seeds 1-10, data/run_totals.csv, tables/fin24_tables.md).

    python3 activity/checks/smoke_test.py run       -> run_respec_smoke/smk_{tasha,respec}_s01 (legs/activities parquet, mc_tours.csv kept)
    python3 activity/checks/smoke_test.py compare   -> run_respec_smoke/smoke_compare.csv (+ printed table)
Measures as report_2024.py (temporal_2024/t24common.acts_from_legs, 5_reports/measures.measure): Maryland residents 5+ trips per
person and trip mode shares (Table F6 form), Baltimore CBSA residents 5+ activities per person and mean zone-skim distance by type
(Table F5 form); RTS 2017/18 from temporal_2024/data (obs.pkl, rts_persons / rts_acts)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re, shutil, subprocess, sys, time, pickle
import numpy as np, pandas as pd

V = WORKSPACE; A3 = f"{V}/3_abit"; HERE = f"{A3}/final_2024"   # data (runs, frozen snapshot)
sys.path.insert(0, f"{MILES_HOME}/activity/lib")
import replications as F   # noqa: E402  (inputs, reduce)
RUN = f"{HERE}/run_respec_smoke"; SAMPLE = "0.01"; SEED = 1
SETS = {"tasha": (f"{HERE}/frozen/coef", f"{HERE}/frozen/classes", f"{HERE}/frozen/abit_classpath.txt"),
        "respec": (f"{MILES_HOME}/activity/parameters", f"{A3}/classes", f"{MILES_HOME}/activity/abit_classpath.txt")}


def run(tag):
    coef, classes, cpf = SETS[tag]; name = f"smk_{tag}_s{SEED:02d}"; d = f"{RUN}/{name}"
    if os.path.exists(f"{d}/output/legs_full.parquet"): print(f"{name}: done, skipped"); return
    os.makedirs(d, exist_ok=True); rc = f"{d}/coef"; shutil.rmtree(rc, ignore_errors=True); shutil.copytree(coef, rc)
    env = dict(os.environ) | {"ABIT_RUN_ROOT": RUN, "ABIT_COEF_DIR": rc, "SILO_SCEN_DIR": F.SCEN_DIR}
    r = subprocess.run([sys.executable, f"{MILES_HOME}/activity/write_properties.py", name, f"oos_s{F.SILO_SEED}", "2024", SAMPLE, F.SK], capture_output=True, text=True, env=env)
    if r.returncode: raise SystemExit(f"write_properties failed: {r.stdout}{r.stderr}")
    props = f"{RUN}/{name}.properties"; t = open(props).read()
    for k, v in {"persons.file": f"{F.SCH}/pp_2024.csv", "schools.file": f"{F.SCH}/schools_2024.csv", "number.of.threads": F.THREADS, "modechoice.dir": rc}.items():
        t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
    open(props, "w").write(t + "\n# smoke_test.py: persons and schools after the schools step, base-year attendance\n")
    java = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"
    cp = f"{classes}:{os.path.expandvars(open(cpf).read().strip())}"; t0 = time.time()
    with open(f"{d}/abit.log", "w") as lg:
        lg.write(f"# {name}: SILO oos_s{F.SILO_SEED} 2024, ABIT seed {SEED}, sample {SAMPLE}, coef {coef}, classes {classes}, {time.ctime()}\n"); lg.flush()
        code = subprocess.run([java, f"-Xmx{F.XMX}", f"-Dabit.seed={SEED}", f"-Djava.library.path={F.LIB}", "-cp", cp, "abm.RunAbitMarylandLos", props],
                              stdout=lg, stderr=subprocess.STDOUT, cwd=d).returncode
    ok = code == 0 and os.path.exists(f"{d}/output/legs_{name}.csv")
    print(f"{name}: rc {code}, {time.time() - t0:.0f} s, {'ok' if ok else 'FAILED'}", flush=True)
    if not ok: raise SystemExit(f"ABIT {name} failed; see {d}/abit.log")
    mc = f"{d}/output/mc_tours.csv"; keep = mc + ".keep"
    if os.path.exists(mc): os.rename(mc, keep)
    F.reduce(d, name)
    if os.path.exists(keep): os.rename(keep, mc)


# ------------------------------------------------------------------------------------------------ comparison
def compare():
    sys.path.insert(0, f"{MILES_HOME}/activity/validation"); import report_2024 as R
    C = R.C; obs = pickle.load(open(f"{R.T24}/data/measures/obs.pkl", "rb")); rts = obs["rts"][0]; kN = "Baltimore CBSA|5+"
    rk = pd.read_parquet(f"{R.T24}/data/rts_persons.parquet"); ra = pd.read_parquet(f"{R.T24}/data/rts_acts.parquet")
    rp = rk[(rk.age >= 5) & (rk.county // 1000 == 24)]; w = dict(zip(rp.person_id, rp.w)); rs = ra[ra.pid.isin(rp.person_id)].assign(w=lambda x: x.pid.map(w))
    rmode = rs.groupby("mode").w.sum() / rs.w.sum(); rtrips = rs.w.sum() / rp.w.sum()
    pp = pd.read_csv(f"{F.SCH}/pp_2024.csv", usecols=["id", "hhid", "age", "occupation"], engine="pyarrow")
    cols = {}
    tags = [t for t in ["tasha", "respec0", "respec1", "respec2", "respec3", "respec4", "respec5", "respec6", "respec7", "respec"] if os.path.exists(f"{RUN}/smk_{t}_s{SEED:02d}/output/legs_full.parquet")]
    for tag in tags:
        name = f"smk_{tag}_s{SEED:02d}"; o = f"{RUN}/{name}/output"
        l = pd.read_parquet(f"{o}/legs_full.parquet", columns=["person_id", "previous_purpose", "start_time_min", "start_zone", "next_purpose", "end_time", "end_zone", "mode", "time_min", "distance_m"])
        for c in R.NUM + ["person_id"]: l[c] = pd.to_numeric(l[c])
        per = pd.read_parquet(f"{o}/persons.parquet"); q = pp[pp.id.isin(per.person_id)]
        hz = per.dropna(subset=["home_zone"]).groupby("household_id").home_zone.first()
        P = pd.DataFrame({"pid": q.id.values, "w": 1.0, "age": q.age.values, "occ": q.occupation.values})
        P["county"] = q.hhid.map(hz).map(C.zone_county()).fillna(-1).astype(int).values
        A = C.acts_from_legs(l); pa = P.set_index("pid")
        md5 = A[A.pid.map(pa.age).ge(5) & (A.pid.map(pa.county) // 1000 == 24)]; n5 = int(((P.age >= 5) & (P.county // 1000 == 24)).sum())
        mm = R.measure(P, A, with_flows=False)
        c = {"persons (Maryland 5+)": n5, "trips per person (Maryland 5+)": len(md5) / n5, "person-km per person (Maryland 5+)": md5.km.sum() / n5}
        for m_, s in md5["mode"].map(C.MODEL_MODE).value_counts(normalize=True).items(): c[f"trip mode share: {m_} (%)"] = 100 * s
        for t in C.TYPES + ["ALL"]:
            c[f"{C.TLAB[t]}: activities per person (CBSA 5+)"] = mm_val(mm, kN, "acts_per_person", t)
            c[f"{C.TLAB[t]}: mean distance km (CBSA 5+)"] = mm_val(mm, kN, "mean_km", t)
        mt = f"{o}/mc_tours.csv"
        if os.path.exists(mt):
            tt = pd.read_csv(mt, usecols=["segment", "alt", "realloc", "joint"]); c["tours"] = len(tt)
            for s, g in tt.groupby("segment"):
                c[f"tour mode share {s}: car driver (%)"] = 100 * (g.alt == "CD").mean(); c[f"tour mode share {s}: car passenger (%)"] = 100 * (g.alt == "CP").mean()
        ms = pd.read_csv(f"{o}/mc_summary.csv").set_index("measure").value
        c["car-driver tours"] = ms["car_driver_tours_before_allocation"]
        nb = ms.get("car_driver_tours_reallocated", ms.get("car_driver_tours_beyond_car_count_not_reallocated"))
        c["car-driver tours overlapping beyond the household's cars"] = nb; c["  same, % of car-driver tours"] = 100 * nb / ms["car_driver_tours_before_allocation"]
        c["households with such an overlap"] = ms["households_with_a_car_conflict"]
        c["  reallocated to another mode (1 = yes)"] = 1.0 if "car_driver_tours_reallocated" in ms else 0.0
        if "tasha_conflict_sets" in ms:
            c["TASHA: car-driver units (joint group = 1)"] = ms["tasha_car_driver_units"]; c["TASHA: conflict sets"] = ms["tasha_conflict_sets"]
            c["TASHA: units in conflict sets"] = ms["tasha_units_in_conflict_sets"]; c["TASHA: sets solved greedily"] = ms["tasha_conflict_sets_greedy"]
            c["TASHA: units reassigned"] = ms["tasha_units_reassigned"]; c["TASHA: units reassigned, % of car-driver units"] = 100 * ms["tasha_units_reassigned"] / ms["tasha_car_driver_units"]
            for a in ["CP", "WK", "BK", "BUS", "TRAIN"]: c[f"TASHA: reassigned to {a} (% of reassigned)"] = 100 * ms[f"tasha_reassigned_to_{a}"] / max(1, ms["tasha_units_reassigned"])
            c["TASHA: households with overlap beyond the cars after allocation"] = ms["tasha_households_overlap_beyond_cars_after"]
            c["car-driver tours overlapping beyond the household's cars"] = ms["tasha_households_overlap_beyond_cars_after"]; c["  same, % of car-driver tours"] = 0.0
        cols[tag] = c
    tot = pd.read_csv(f"{HERE}/data/run_totals.csv"); f10 = tot[tot.form == "fin24"]
    ref = {"trips per person (Maryland 5+)": (f10.trips_md5 / f10.persons_md5).mean(), "person-km per person (Maryland 5+)": (f10.km_md5 / f10.persons_md5).mean()}
    for c in [x for x in tot.columns if x.startswith("mode_")]: ref[f"trip mode share: {c[5:]} (%)"] = 100 * f10[c].mean()
    rtsc = {"trips per person (Maryland 5+)": rtrips}
    for m_, s in rmode.items(): rtsc[f"trip mode share: {m_} (%)"] = 100 * s
    for t in C.TYPES + ["ALL"]:
        rtsc[f"{C.TLAB[t]}: activities per person (CBSA 5+)"] = R.ov(rts, kN, "acts_per_person", t); rtsc[f"{C.TLAB[t]}: mean distance km (CBSA 5+)"] = R.ov(rts, kN, "mean_km", t)
    lab = {"tasha": "coef_tasha 1 %", "respec0": "coef_respec, short/joint 0 + old reallocation 1 %", "respec1": "coef_respec, short/joint applied, no allocation 1 %",
           "respec2": "coef_respec, no short (plain availability in estimation), TASHA allocation 1 %",
           "respec3": "coef_respec, no short (overlap-count availability in estimation), TASHA allocation 1 %",
           "respec4": "coef_respec, no short (simultaneous-use availability in estimation), TASHA allocation on leg windows 1 %",
           "respec5": "coef_respec, as respec4 + joint tours: own choices, one car unit per joint group 1 %",
           "respec6": "coef_respec, + discretionary frequencies by licence, one household driver per joint group 1 %",
           "respec7": "coef_respec, + frequencies by licence, joint-tour representative, conditional joint start 1 %",
           "respec": "coef_respec, + group-level joint mode model, joint frequency and members by work / school that day 1 %"}
    df = pd.DataFrame({**{lab[t]: pd.Series(cols[t]) for t in tags}, "coef_tasha fin24 10 % (10 seeds)": pd.Series(ref),
                       "RTS 2017/18": pd.Series(rtsc)})
    df["respec - tasha"] = df[lab["respec"]] - df["coef_tasha 1 %"]
    df.to_csv(f"{RUN}/smoke_compare.csv"); pd.set_option("display.width", 220); print(df.round(3).to_string())


def mm_val(mm, key, metric, t):
    """value of a measure.measure() result (the structure report_2024.sv reads from one replication)"""
    import report_2024 as R
    return R.ov(mm[0], key, metric, t)


if __name__ == "__main__":
    if sys.argv[1] == "run":
        for tag in (sys.argv[2:] or list(SETS)): run(tag)
    else: compare()
