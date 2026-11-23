#!/usr/bin/env python3
"""DAYMAP 2024 replications with the re-specified models (coefficient set activity/parameters, all switches of the set: TASHA car
allocation, joint-tour representative with the group-level mode model, joint frequency / members / start by work or school that
day, licence-split discretionary frequencies, allocation-consistent availability in estimation), on the re-estimated SILO
population of the chosen seed (oos_respec_s1, persons and schools after the schools step).  Same set-up as the record runs
(replications.py): ten replications (DAYMAP seeds 1-10), 10 % household sample, skims base_transit2024, base-year attendance (no
telework input), frozen snapshot of coefficients and classes, outputs reduced to parquet.
    python3 activity/run_replications.py snapshot
    python3 activity/run_replications.py run --jobs 2    -> <workspace>/3_abit/final_2024/run_respec/fin24_s01 ... s10
    python3 activity/run_replications.py persons          -> work directory persons table for build_abit.py (this population)
    python3 activity/run_replications.py choose           -> run_respec/matsim_input_choice.csv (activity/choose_replication.py rule)"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, csv, hashlib, os, shutil, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
sys.path.insert(0, f"{MILES_HOME}/activity/lib")
import replications as F
HERE = f"{WORKSPACE}/3_abit/final_2024"   # runs and frozen snapshot (data)
V = F.V; A3 = F.A3
F.RUN = RUN = f"{HERE}/run_respec"; F.FROZEN = FROZEN = f"{HERE}/frozen_respec"
F.SCEN_DIR = f"{V}/2_silo/run/base/scenOutput/oos_respec_s1"; F.SCH = SCH = f"{V}/2_silo/schoolchoice/runs/oos_respec_s1/2024"
F.SILO_SEED = "respec_s1"   # label in write_properties / the run log (the paths come from SCEN_DIR and SCH)
WORK = f"{V}/5_reports/validation_pdfs/work/abit_respec"


def snapshot():
    if os.path.exists(f"{FROZEN}/MANIFEST.csv"): print("snapshot exists"); return
    os.makedirs(FROZEN, exist_ok=True); src = f"{MILES_HOME}/activity/parameters"
    shutil.copytree(src, f"{FROZEN}/coef"); shutil.copytree(f"{A3}/classes", f"{FROZEN}/classes"); shutil.copy(f"{MILES_HOME}/activity/abit_classpath.txt", FROZEN)
    rp = f"{FROZEN}/coef/run_params.csv"; txt = open(rp).read(); open(rp, "w").write(txt.replace(f"{src}/", f"{FROZEN}/coef/"))
    rows = []
    for d in ["coef", "classes"]:
        for r, _, fs in os.walk(f"{FROZEN}/{d}"):
            for f in sorted(fs): p = f"{r}/{f}"; rows.append(dict(file=os.path.relpath(p, FROZEN), bytes=os.path.getsize(p), sha256=F.sha(p)))
    rows.sort(key=lambda x: x["file"])
    with open(f"{FROZEN}/MANIFEST.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "bytes", "sha256"]); w.writeheader(); w.writerows(rows)
    print(f"snapshot of {src} and the classes: {len(rows)} files")


def persons():
    """the persons table build_abit.py / report_2024.measure use (person, weight 1, age, occupation, home county) for THIS population"""
    os.makedirs(f"{WORK}/measures", exist_ok=True); sys.path.insert(0, f"{MILES_HOME}/activity/lib/reporting_2024"); import t24common as C
    r = pd.read_parquet(f"{RUN}/fin24_s01/output/persons.parquet")
    pp = pd.read_csv(f"{SCH}/pp_2024.csv", usecols=["id", "hhid", "age", "occupation"], engine="pyarrow"); pp = pp[pp.id.isin(r.person_id)]
    hz = r.dropna(subset=["home_zone"]).groupby("household_id").home_zone.first()
    P = pd.DataFrame({"pid": pp.id.values, "w": 1.0, "age": pp.age.values, "occ": pp.occupation.values})
    P["county"] = pp.hhid.map(hz).map(C.zone_county()).fillna(-1).astype(int).values; P.to_parquet(f"{WORK}/measures/persons.parquet", index=False)
    print(f"persons: {len(P):,}")


def choose():
    """choose_replication.py's rule on the replications: the smallest sum of squared relative deviations from the ten-replication mean of the
    key outputs (Maryland 5+ trips and person-km per person, trip mode shares)"""
    t = pd.read_csv(f"{WORK}/data/run_totals.csv"); t = t[t.form == "fin24"].copy()
    t["trips per person"] = t.trips_md5 / t.persons_md5; t["person-km per person"] = t.km_md5 / t.persons_md5
    cols = ["trips per person", "person-km per person"] + [c for c in t.columns if c.startswith("mode_")]
    d = t.set_index("run")[cols]; rel = d / d.mean() - 1
    out = pd.DataFrame({"ssq_rel_dev": (rel ** 2).sum(axis=1), "max_abs_rel_dev_pct": rel.abs().max(axis=1) * 100}).join(d)
    out.to_csv(f"{RUN}/matsim_input_choice.csv"); print(out.round(4).to_string()); print("chosen replication:", out.ssq_rel_dev.idxmin())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["snapshot", "run", "persons", "choose"]); ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--seeds", default="1-10"); a = ap.parse_args(); os.makedirs(RUN, exist_ok=True)
    if a.cmd == "snapshot": snapshot()
    elif a.cmd == "persons": persons()
    elif a.cmd == "choose": choose()
    else:
        lo, hi = (int(x) for x in a.seeds.split("-"))
        with ThreadPoolExecutor(a.jobs) as ex:
            for fut in [ex.submit(F.run, "fin24", s) for s in range(lo, hi + 1)]: fut.result()
        print("all runs done", flush=True)
