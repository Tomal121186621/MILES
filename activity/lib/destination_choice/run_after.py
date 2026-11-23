#!/usr/bin/env python3
"""DAYMAP runs with the estimated destination MNL (after), one at a time: waits while any other RunAbit process is active.
    python3 activity/lib/destination_choice/run_after.py   -> run_survey/svy_est_mnl_s01..10, svy_val_mnl_s01..10, run/val_mnl_s01..10
Coefficient set destination_choice/coef_mnl_run (coef_calibrated + dest_choice_mnl.csv + dest.choice.model = mnl); skims
3_abit/skims/base_transit2024 (base car time and distance, 2024 door-to-door transit: the skims of estimation)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, subprocess, sys, time
A3 = f"{WORKSPACE}/3_abit"; HERE = f"{A3}/destination_choice"   # data
sys.path.insert(0, f"{MILES_HOME}/activity/survey"); sys.path.insert(0, f"{MILES_HOME}/activity")
import survey_population as S, run_activity_model as R
COEF = f"{HERE}/coef_mnl_run"; SK = f"{A3}/skims/base_transit2024"
def wait():
    while subprocess.run(["pgrep", "-f", "RunAbit"], capture_output=True).returncode == 0: time.sleep(30)
for half in ["estimation", "validation"]:
    for s in range(1, 11): wait(); S.run(half, s, coef=COEF, tag="mnl", skims=SK)
for s in range(1, 11): wait(); R.run(f"val_mnl_s{s:02d}", COEF, seed=s, sample=0.05, threads=6, xmx="8g", skims=SK)
print("all after runs done", flush=True)
