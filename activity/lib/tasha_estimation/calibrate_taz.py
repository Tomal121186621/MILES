#!/usr/bin/env python3
"""Calibration of the TAZ coefficient set coef_tasha_cal_taz with the existing loop (calibrate_abit.main_tasha, unchanged), 2026-10-28.

    python3 activity/lib/tasha_estimation/calibrate_taz.py [--start 0] [--max-iter 10] [--threads 4]

Only the paths are redirected: behavioural set coef_tasha_taz, calibrated set coef_tasha_cal_taz (a copy of coef_tasha_cal with
the TAZ destination rows, export_dc_taz.py; the calibration starts from the levers of the model of record, not from --init).
Tag tfcaltaz: runs 3_abit/run/tfcaltaz_it<K>, log 3_abit/calibration_log_tfcaltaz.csv, history coef_history/tfcaltaz_it<K>.
Same criteria, levers, sample (5 %), seed (1) and skims (base_transit2024) as the model of record (tag tfcal)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, os, sys
A3 = f"{WORKSPACE}/3_abit"; HERE = f"{A3}/tasha_estimation"   # data; the calibration loop runs in 3_abit
sys.path.insert(0, f"{TERP_HOME}/activity/lib"); os.chdir(A3)
# calibrate_abit (the calibration loop of the old working tree) is not part of the repository
if os.path.exists(f"{A3}/calibrate_abit.py"): sys.path.append(A3)
import coef_tools as ct          # noqa: E402
import calibrate_abit as CA      # noqa: E402
ct.TASHA = f"{A3}/coef_tasha_taz"; ct.TASHA_CAL = f"{A3}/coef_tasha_cal_taz"
ap = argparse.ArgumentParser(); ap.add_argument("--start", type=int, default=0); ap.add_argument("--max-iter", type=int, default=10)
ap.add_argument("--threads", type=int, default=4); ap.add_argument("--sample", type=float, default=0.05)
a = ap.parse_args(); a.init = False; a.tag = "tfcaltaz"
CA.main_tasha(a)
