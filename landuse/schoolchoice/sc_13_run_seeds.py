#!/usr/bin/env python3
"""Schools step on the SILO seed runs: for each seed (scenOutput/oos_s<k>) and year 2016-2024, student alignment + upper-limit
assignment (sc_10_assign.py; shadow prices warm-started from the previous year), then the validation tables (sc_11_test_assign.py,
tag _oos_s<k>).  A seed is started when its futureYears/pp_2024.csv exists and has not changed for 10 minutes (checked every 10 min).
Layout of a run: microData/pp_<Y>.csv and dd_<Y>.csv (2016-2023), futureYears/hh_<Y>.csv (all years), futureYears/{pp,dd}_2024.csv.
Outputs: schoolchoice/runs/oos_s<k>/<Y>/ (assignment, alignment, convergence, records, lambda; the full person file and the school file
only for 2024: pp_2024.csv, schools_2024.csv in SILO's futureYears/schools_2024.csv structure), tables/assignment_<Y>_oos_s<k>_*.csv.
Usage: sc_13_run_seeds.py 1 3 5
2026-11-09: SCHOOL_SPEC=respec uses the SILO runs oos_respec_s<k> and apply/school_choice_coefficients_respec.csv (outputs runs/oos_respec_s<k>)."""
import os, sys, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(HERE); RUN = f"{S}/run/base/scenOutput"
SPEC = os.environ.get("SCHOOL_SPEC", "record"); assert SPEC in ("record", "respec"), SPEC; TAG = "oos_respec_s" if SPEC == "respec" else "oos_s"
COEF = ["--coefficients", f"{HERE}/apply/school_choice_coefficients_respec.csv"] if SPEC == "respec" else []
for k in sys.argv[1:]:
    M = f"{RUN}/{TAG}{k}/microData"; F = f"{M}/futureYears"; last = None
    while True:
        p = f"{F}/pp_2024.csv"
        if os.path.exists(p):
            st = (os.path.getsize(p), os.path.getmtime(p))
            if time.time() - st[1] > 600 and (last is None or st == last): break
            last = st
        time.sleep(600)
    lam = None
    for y in range(2016, 2025):
        O = f"{HERE}/runs/{TAG}{k}/{y}"; os.makedirs(O, exist_ok=True)
        if os.path.exists(f"{O}/school_assignment_{y}.parquet") and (y < 2024 or os.path.exists(f"{O}/pp_{y}.csv")): lam = f"{O}/school_lambda_{y}.csv"; continue
        pp = f"{F}/pp_2024.csv" if y == 2024 else f"{M}/pp_{y}.csv"; dd = f"{F}/dd_2024.csv" if y == 2024 else f"{M}/dd_{y}.csv"
        cmd = [sys.executable, f"{HERE}/sc_10_assign.py", "--pp", pp, "--hh", f"{F}/hh_{y}.csv", "--dd", dd, "--schools", f"{S}/input/schools_2016.csv", "--year", str(y),
               "--out", O, "--write-pp", "1" if y == 2024 else "0"] + (["--lam-in", lam] if lam else []) + (["--schools-template", f"{F}/schools_2024.csv"] if y == 2024 else []) + COEF
        with open(f"{O}/assign.log", "w") as lg: r = subprocess.run(cmd, stdout=lg, stderr=subprocess.STDOUT)
        if r.returncode: print(f"seed {k} year {y} FAILED (see {O}/assign.log)", flush=True); break
        subprocess.run([sys.executable, f"{HERE}/sc_11_test_assign.py", "--dir", O, "--year", str(y), "--tag", f"_{TAG}{k}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        lam = f"{O}/school_lambda_{y}.csv"; print(f"seed {k} year {y} done", flush=True)
    print(f"seed {k} finished", flush=True)
