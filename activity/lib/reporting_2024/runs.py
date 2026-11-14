#!/usr/bin/env python3
"""ABIT runs of the 2024 temporal validation, one ABIT at a time (waits while any other RunAbit process is active; 8 GB heap).

    python3 activity/lib/reporting_2024/runs.py snapshot                      # freeze the coefficient set and the compiled model (once, before the first run)
    python3 activity/lib/reporting_2024/runs.py acs2024  --seeds 1-10         # observed 2024 population (pop_acs2024, build_population.py)
    python3 activity/lib/reporting_2024/runs.py silo2024 --seeds 1-10         # SILO 2024 forecast population, 5 % household sample
    python3 activity/lib/reporting_2024/runs.py base     --seeds 1-10         # observed 2017/18 population: the RTS survey households (both halves)

Model: the coefficient set 3_abit/coef_calibrated and the classes 3_abit/classes (+ the survey overlay reader, which only adds
the optional zone.population.file property) as they stood at the snapshot (temporal_2024/frozen/, hashes in
frozen/MANIFEST.csv); no parameter is changed between the base year and 2024.
Inputs by setting
  base      2016 base inputs of the chain (jobs, schools, zone population of 2016), base skims (3_abit/skims), the survey
            households of 3_abit/survey_pop/<half>/ (survey_population.py), as the Roorda-style verification runs.
  acs2024   SILO 2024 forecast jobs, schools and persons per zone (scenario oos_s1), skims: base car time and distance with the
            2024 door-to-door transit skims (3_abit/skims/base_transit2024); households/persons/dwellings of pop_acs2024,
            workplace.reassign.file, zone.population.file = SILO 2024 persons per zone, sample.fraction 1.
  silo2024  the SILO 2024 microdata of oos_s1 (households, persons, dwellings, jobs, schools), sample.fraction 0.05, same skims.
After a run the two CSV outputs are reduced to output/legs.parquet and output/persons.parquet (person, household, home zone)
and the CSVs are deleted (2 GB per run).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, csv, hashlib, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import t24common as C

FROZEN = {"final": f"{C.T24}/frozen_final", "mc": f"{C.T24}/frozen_mc"}.get(C.MODEL, f"{C.T24}/frozen"); SRC_COEF = f"{C.A3}/coef_tasha" if C.MODEL in ("final", "mc") else f"{C.A3}/coef_calibrated"; RUNROOT = f"{C.T24}/run"; SILO_SCEN = os.environ.get("T24_SILO", "oos_s1_pass3")
SCEN_DIR = f"{C.V}/2_silo/run/base/scenOutput/{SILO_SCEN}"
SK24 = f"{C.A3}/skims/base_transit2024"; SKB = f"{C.A3}/skims"
LIB = f"{C.ROOT}/ABIT/src/main/resources/lib/macosx64"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def snapshot():
    if os.path.exists(f"{FROZEN}/MANIFEST.csv"): print("snapshot exists:", FROZEN); return
    os.makedirs(FROZEN, exist_ok=True)
    shutil.copytree(SRC_COEF, f"{FROZEN}/coef"); shutil.copytree(f"{C.A3}/classes", f"{FROZEN}/classes")
    shutil.copytree(f"{C.A3}/survey_overlay/classes", f"{FROZEN}/overlay_classes"); shutil.copy(f"{TERP_HOME}/activity/abit_classpath.txt", f"{FROZEN}/abit_classpath.txt")
    rp = f"{FROZEN}/coef/run_params.csv"   # the tour mode choice reads its coefficient file from the frozen copy
    if os.path.exists(rp):
        txt = open(rp).read(); open(rp, "w").write(txt.replace(f"{SRC_COEF}/tour_mode_choice.csv", f"{FROZEN}/coef/tour_mode_choice.csv"))
    rows = []
    for d in ["coef", "classes", "overlay_classes"]:
        for r, _, fs in os.walk(f"{FROZEN}/{d}"):
            for f in sorted(fs): p = f"{r}/{f}"; rows.append(dict(file=os.path.relpath(p, FROZEN), bytes=os.path.getsize(p), sha256=sha(p)))
    rows.sort(key=lambda x: x["file"])
    tot = hashlib.sha256("".join(r["sha256"] for r in rows if r["file"].startswith("coef/")).encode()).hexdigest()
    clt = hashlib.sha256("".join(r["sha256"] for r in rows if not r["file"].startswith("coef/")).encode()).hexdigest()
    with open(f"{FROZEN}/MANIFEST.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "bytes", "sha256"]); w.writeheader(); w.writerows(rows)
    open(f"{FROZEN}/HASH.txt", "w").write(f"snapshot {time.ctime()}\ncoefficient set ({os.path.relpath(SRC_COEF, C.A3)}): {tot}\nclasses + overlay: {clt}\n")
    print(open(f"{FROZEN}/HASH.txt").read())


RES = {"proc": None}


def _others():
    """RunAbit processes other than this script's own reservation."""
    out = subprocess.run(["pgrep", "-f", "RunAbit"], capture_output=True, text=True).stdout.split()
    mine = str(RES["proc"].pid) if RES["proc"] else None
    return [p for p in out if p != mine]


def wait():
    """Block while another RunAbit runs (checked twice, 5 s apart); then hold a reservation process named 'RunAbitReservation
    temporal_2024' (the convention of tasha_runs.py) while this script runs; the reservation is dropped while waiting, so that
    two waiting scripts never hold each other up."""
    release()
    while True:
        if not _others():
            time.sleep(5)
            if not _others(): break
        time.sleep(10)
    if RES["proc"] is None or RES["proc"].poll() is not None:
        RES["proc"] = subprocess.Popen(["bash", "-c", 'exec -a "RunAbitReservation temporal_2024" sleep 86400'])


def release():
    if RES["proc"] is not None and RES["proc"].poll() is None: RES["proc"].terminate()


def reduce(d, name):
    o = f"{d}/output"; lf, af = f"{o}/legs_{name}.csv", f"{o}/activities_{name}.csv"
    l = pd.read_csv(lf, usecols=["person_id", "previous_purpose", "start_time_min", "start_zone", "next_purpose", "end_time", "end_zone", "mode", "time_min", "distance_m"], engine="pyarrow")
    l.to_parquet(f"{o}/legs.parquet", index=False)
    a = pd.read_csv(af, usecols=["person_id", "household_id", "purpose", "zone"], engine="pyarrow")
    ph = a[a.purpose == "HOME"].drop_duplicates("person_id")[["person_id", "household_id", "zone"]].rename(columns={"zone": "home_zone"})
    allp = a.drop_duplicates("person_id")[["person_id", "household_id"]]
    allp.merge(ph[["person_id", "home_zone"]], on="person_id", how="left").to_parquet(f"{o}/persons.parquet", index=False)
    os.remove(lf); os.remove(af)


TW = {"base_tw": f"{C.T24}/telework/wfh_attendance_2017_19.csv", "acs2024_tw": f"{C.T24}/telework/wfh_attendance_2024.csv",
      "silo2024_tw": f"{C.T24}/telework/wfh_attendance_2024.csv"}


def run(setting, seed, half=None, force=False):
    """setting <x>_tw: the variant 'with telework input' -- the same frozen model and inputs as <x>, with the attendance step's
    county work-at-home table replaced by the observed table of the simulated year (build_telework.py)."""
    tw = TW.get(setting); setting0 = setting; setting = setting.replace("_tw", "")
    name = f"{C.PFX}{setting0}{'_' + half[:3] if half else ''}_s{seed:02d}"; d = f"{RUNROOT}/{name}"
    if os.path.exists(f"{d}/output/legs.parquet") and not force: print(f"{name}: done, skipped"); return d
    if not os.path.exists(f"{FROZEN}/MANIFEST.csv"): raise SystemExit("run 'runs.py snapshot' first")
    os.makedirs(d, exist_ok=True); rc = f"{d}/coef"; shutil.rmtree(rc, ignore_errors=True); shutil.copytree(f"{FROZEN}/coef", rc)
    env = dict(os.environ) | {"ABIT_RUN_ROOT": RUNROOT, "ABIT_COEF_DIR": rc}
    if setting == "base":
        args = [name, "base", "2016", "1.0", SK24 if C.MODEL in ("final", "mc") else SKB]   # the final model was estimated and verified with base_transit2024
    else:
        env["SILO_SCEN_DIR"] = SCEN_DIR; args = [name, SILO_SCEN, "2024", "1.0" if setting == "acs2024" else "0.05", SK24]
    r = subprocess.run([sys.executable, f"{TERP_HOME}/activity/write_properties.py"] + args, capture_output=True, text=True, env=env)
    if r.returncode != 0: raise SystemExit(f"write_properties failed: {r.stdout}{r.stderr}")
    props = f"{RUNROOT}/{name}.properties"; t = open(props).read()
    rep = {"number.of.threads": "6"}; extra = ""
    if tw and C.MODEL not in ("final", "mc"): rep["wfh.attendance.file"] = tw
    if setting == "base":
        od = f"{C.A3}/survey_pop/{half}"
        rep |= {"households.file": f"{od}/hh.csv", "persons.file": f"{od}/pp.csv", "dwellings.file": f"{od}/dd.csv"}
        extra = f"workplace.reassign.file = {od}/workplace_reassign.csv\nzone.population.file = {C.A3}/survey_pop/zone_population_2016.csv\n"
    elif setting == "acs2024":
        od = f"{C.T24}/pop_acs2024"
        rep |= {"households.file": f"{od}/hh.csv", "persons.file": f"{od}/pp.csv", "dwellings.file": f"{od}/dd.csv"}
        extra = f"workplace.reassign.file = {od}/workplace_reassign.csv\nzone.population.file = {od}/zone_population_2024.csv\n"
    for k, v in rep.items(): t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
    if tw and C.MODEL in ("final", "mc"): extra += f"tasha.attendance.file = {tw}\n"   # the TASHA path's attendance step (MarylandTashaGenerator)
    open(props, "w").write(t + (f"\n# temporal validation 2024 (runs.py)\n{extra}" if extra else ""))
    java = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"
    cp = f"{FROZEN}/overlay_classes:{FROZEN}/classes:{os.path.expandvars(open(f'{FROZEN}/abit_classpath.txt').read().strip())}"
    cmd = [java, "-Xmx8g", f"-Dabit.seed={seed}", f"-Djava.library.path={LIB}", "-cp", cp, "abm.RunAbitMarylandLos", props]
    wait(); t0 = time.time()
    with open(f"{d}/abit.log", "w") as lg:
        lg.write(f"# {name}: setting {setting}, seed {seed}, frozen model {FROZEN}, started {time.ctime()}\n"); lg.flush()
        code = subprocess.run(cmd, stdout=lg, stderr=subprocess.STDOUT, cwd=d).returncode
    ok = code == 0 and os.path.exists(f"{d}/output/legs_{name}.csv")
    msg = f"{name}: rc {code}, {time.time() - t0:.0f} s, {'ok' if ok else 'FAILED'}"; print(msg, flush=True)
    open(f"{RUNROOT}/runs.log", "a").write(f"{time.ctime()}  {msg}\n")
    if not ok: raise SystemExit(f"ABIT {name} failed; see {d}/abit.log")
    reduce(d, name); return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["snapshot", "acs2024", "silo2024", "base", "acs2024_tw", "silo2024_tw", "base_tw"]); ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--force", action="store_true"); a = ap.parse_args(); os.makedirs(RUNROOT, exist_ok=True)
    if a.cmd == "snapshot": snapshot(); sys.exit()
    lo, hi = (int(x) for x in a.seeds.split("-"))
    try:
        for s in range(lo, hi + 1):
            if a.cmd.startswith("base"):
                for hf in ["estimation", "validation"]: run(a.cmd, s, hf, a.force)
            else: run(a.cmd, s, force=a.force)
    finally:
        release()
    print("done", flush=True)
