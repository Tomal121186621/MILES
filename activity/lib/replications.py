#!/usr/bin/env python3
"""MAST 2024 on the final land-use population (fin24): the model of record (behavioural set 3_abit/coef_tasha, TASHA-type
generation, destination models on traffic zones, tour mode choice with the corrected gender coding, USDOT value of time), no
code or coefficient change.  One SILO population: seed 5 (choose_replication.py, closest to the five-seed mean), 2024 state after the
schools step.  Ten replications (MAST seeds 1-10) in two forms:
    fin24     work attendance from the set's base-year table (frozen form)
    fin24_tw  attendance with the ACS 2024 work-at-home share by county (temporal_2024/telework/wfh_attendance_2024.csv)
Skims 3_abit/skims/base_transit2024 (the chain's 'base' MAST skims), sample 10 % (the chain's production sample).
    python3 activity/lib/replications.py snapshot
    python3 activity/lib/replications.py run --jobs 2
After a run, legs and activities are kept as parquet (all columns as text: legs_full / activities_full, rewritable to the MAST CSV)
plus persons.parquet; the CSVs and mc_tours.csv are deleted (13 GB free disk: one run at a time)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, csv, hashlib, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import pyarrow.csv as pc, pyarrow.parquet as pq, pyarrow as pa
import pandas as pd

V = f"{WORKSPACE}"; ROOT = PROJECT_ROOT
A3 = f"{V}/3_abit"; HERE = f"{A3}/final_2024"; FROZEN = f"{HERE}/frozen"; RUN = f"{HERE}/run"
SILO_SEED = 5; SCEN_DIR = f"{V}/2_silo/run/base/scenOutput/oos_s{SILO_SEED}"; SCH = f"{V}/2_silo/schoolchoice/runs/oos_s{SILO_SEED}/2024"
SK = f"{A3}/skims/base_transit2024"; SAMPLE = "0.10"; TW = f"{A3}/temporal_2024/telework/wfh_attendance_2024.csv"
LIB = f"{ABIT_HOME}/src/main/resources/lib/macosx64"; XMX = "13g"; THREADS = "6"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def snapshot():
    if os.path.exists(f"{FROZEN}/MANIFEST.csv"): print("snapshot exists"); return
    os.makedirs(FROZEN, exist_ok=True); src = f"{A3}/coef_tasha"
    shutil.copytree(src, f"{FROZEN}/coef"); shutil.copytree(f"{A3}/classes", f"{FROZEN}/classes"); shutil.copy(f"{MILES_HOME}/activity/abit_classpath.txt", FROZEN)
    rp = f"{FROZEN}/coef/run_params.csv"; t = open(rp).read(); open(rp, "w").write(t.replace(f"{src}/tour_mode_choice.csv", f"{FROZEN}/coef/tour_mode_choice.csv"))
    rows = []
    for d in ["coef", "classes"]:
        for r, _, fs in os.walk(f"{FROZEN}/{d}"):
            for f in sorted(fs): p = f"{r}/{f}"; rows.append(dict(file=os.path.relpath(p, FROZEN), bytes=os.path.getsize(p), sha256=sha(p)))
    rows.sort(key=lambda x: x["file"])
    with open(f"{FROZEN}/MANIFEST.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "bytes", "sha256"]); w.writeheader(); w.writerows(rows)
    chk = {"dest_choice_mnl == coef_tasha_taz2": sha(f"{src}/dest_choice_mnl.csv") == sha(f"{A3}/coef_tasha_taz2/dest_choice_mnl.csv"),
           "tour_mode_choice != genderbug": sha(f"{src}/tour_mode_choice.csv") != sha(f"{src}/tour_mode_choice_genderbug.csv")}
    tot = hashlib.sha256("".join(r["sha256"] for r in rows if r["file"].startswith("coef/")).encode()).hexdigest()
    clt = hashlib.sha256("".join(r["sha256"] for r in rows if r["file"].startswith("classes/")).encode()).hexdigest()
    open(f"{FROZEN}/HASH.txt", "w").write(f"snapshot {time.ctime()}\ncoef_tasha: {tot}\nclasses: {clt}\nchecks: {chk}\n"); print(open(f"{FROZEN}/HASH.txt").read())


def to_parquet(csvf, out, strings=True):
    if strings:
        hdr = open(csvf).readline().strip().split(",")
        t = pc.read_csv(csvf, convert_options=pc.ConvertOptions(column_types={c.strip('"'): pa.string() for c in hdr}))
    else: t = pc.read_csv(csvf)
    pq.write_table(t, out, compression="zstd")


def reduce(d, name):
    """legs and activities -> parquet (all columns as text, rewritable to the MAST CSV), persons.parquet (person, household, home zone);
    the CSVs and mc_tours.csv are deleted (disk; mc_summary.csv is kept)."""
    o = f"{d}/output"; lf, af = f"{o}/legs_{name}.csv", f"{o}/activities_{name}.csv"
    a = pd.read_csv(af, usecols=["person_id", "household_id", "purpose", "zone"], engine="pyarrow")
    ph = a[a.purpose == "HOME"].drop_duplicates("person_id")[["person_id", "household_id", "zone"]].rename(columns={"zone": "home_zone"})
    a.drop_duplicates("person_id")[["person_id", "household_id"]].merge(ph[["person_id", "home_zone"]], on="person_id", how="left").to_parquet(f"{o}/persons.parquet", index=False)
    to_parquet(lf, f"{o}/legs_full.parquet"); to_parquet(af, f"{o}/activities_full.parquet")
    for f in [lf, af, f"{o}/mc_tours.csv"]:
        if os.path.exists(f): os.remove(f)


def run(form, seed):
    name = f"{form}_s{seed:02d}"; d = f"{RUN}/{name}"
    if os.path.exists(f"{d}/output/legs_full.parquet"): print(f"{name}: done, skipped", flush=True); return
    os.makedirs(d, exist_ok=True); rc = f"{d}/coef"; shutil.rmtree(rc, ignore_errors=True); shutil.copytree(f"{FROZEN}/coef", rc)
    env = dict(os.environ) | {"ABIT_RUN_ROOT": RUN, "ABIT_COEF_DIR": rc, "SILO_SCEN_DIR": SCEN_DIR}
    r = subprocess.run([sys.executable, f"{MILES_HOME}/activity/write_properties.py", name, f"oos_s{SILO_SEED}", "2024", SAMPLE, SK], capture_output=True, text=True, env=env)
    if r.returncode: raise SystemExit(f"write_properties failed: {r.stdout}{r.stderr}")
    props = f"{RUN}/{name}.properties"; t = open(props).read()
    for k, v in {"persons.file": f"{SCH}/pp_2024.csv", "schools.file": f"{SCH}/schools_2024.csv", "number.of.threads": THREADS, "modechoice.dir": rc}.items():
        t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
    t += "\n# fin24 (replications.py): persons and schools after the schools step\n" + (f"tasha.attendance.file = {TW}\n" if form == "fin24_tw" else "")
    open(props, "w").write(t)
    java = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"
    cp = f"{FROZEN}/classes:{os.path.expandvars(open(f'{FROZEN}/abit_classpath.txt').read().strip())}"
    t0 = time.time()
    with open(f"{d}/abit.log", "w") as lg:
        lg.write(f"# {name}: SILO oos_s{SILO_SEED} 2024 (schools step), ABIT seed {seed}, started {time.ctime()}\n"); lg.flush()
        code = subprocess.run([java, f"-Xmx{XMX}", f"-Dabit.seed={seed}", f"-Djava.library.path={LIB}", "-cp", cp, "abm.RunAbitMarylandLos", props], stdout=lg, stderr=subprocess.STDOUT, cwd=d).returncode
    ok = code == 0 and os.path.exists(f"{d}/output/legs_{name}.csv")
    msg = f"{name}: rc {code}, {time.time() - t0:.0f} s, {'ok' if ok else 'FAILED'}"; print(msg, flush=True); open(f"{RUN}/runs.log", "a").write(f"{time.ctime()}  {msg}\n")
    if not ok: raise SystemExit(f"ABIT {name} failed; see {d}/abit.log")
    reduce(d, name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["snapshot", "run"]); ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--forms", default="fin24_tw,fin24"); ap.add_argument("--seeds", default="1-10"); a = ap.parse_args(); os.makedirs(RUN, exist_ok=True)
    if a.cmd == "snapshot": snapshot(); sys.exit()
    lo, hi = (int(x) for x in a.seeds.split("-")); jobs = [(f, s) for f in a.forms.split(",") for s in range(lo, hi + 1)]
    with ThreadPoolExecutor(a.jobs) as ex:
        for fut in [ex.submit(run, f, s) for f, s in jobs]: fut.result()
    print("all runs done", flush=True)
