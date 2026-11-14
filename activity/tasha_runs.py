#!/usr/bin/env python3
"""ABIT runs with the TASHA-style generator (MarylandTashaGenerator, 2026-10-22), one ABIT at a time (waits while any other
RunAbit process is active; <= 8 GB heap).

    python3 tasha_runs.py survey --set tasha|tcal|behav|cal [--half both] [--seeds 1-10]   -> run_survey/svy_<est|val>_<set>_s<seed>
    python3 tasha_runs.py chain  --set tasha|tcal|behav|cal [--seeds 1-10]                 -> run/val_<set>_s<seed> (5 % household sample)
(tasha / tcal: the runs of 2026-10-22/23 before the finalisation; behav / cal: the model of record, same directories after
coef_tools.finalize_tasha and the re-calibration)
Coefficient sets: tasha = coef_tasha (behavioural: distributions of the estimation half, estimated destination MNL, no
calibration), tcal = coef_tasha_cal (the same, calibrated on the estimation half by calibrate_abit.py --tasha).  Skims: base car
time and distance with the 2024 door-to-door transit skims (3_abit/skims/base_transit2024), the skims the destination MNL was
estimated with."""
import argparse, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import survey_population as S, run_abit as R

SETS = {"tasha": f"{HERE}/coef_tasha", "tcal": f"{HERE}/coef_tasha_cal",
        # model of record (2026-10-23, ROORDA_VALIDATION.md section 10): the same two sets after the finalisation (estimated
        # anchored locations, estimated return-home logit, conditional regeneration, joint relocation); runs *_behav_*, *_cal_*
        "behav": f"{HERE}/coef_tasha", "cal": f"{HERE}/coef_tasha_cal",
        # 2026-11-02: coef_tasha after the re-estimation (frequency by mandatory band, tour mode choice with household-structure
        # terms) and the application fixes (joint stops, joint-tour mode); runs *_reest_*
        "reest": f"{HERE}/coef_tasha",
        # 2026-11-03: coef_tasha after the WESML re-estimation of the work tour mode choice (mode_choice/estimate_wesml.py); runs *_rail_*
        "rail": f"{HERE}/coef_tasha",
        # 2026-11-03: work-based subtour model, return-home logit re-estimated without the outings, accompany frequency by licence
        # (tasha_estimation/estimate_subtours.py, tasha_distributions.py); runs *_sched_*
        "sched": f"{HERE}/coef_tasha"}
SK = f"{HERE}/skims/base_transit2024"


_RES = None


def reserve():
    """Hold the ABIT slot for this batch: a sleeping process named RunAbitReservation, which the waiting loops of the other run
    drivers (pgrep -f RunAbit) see as an active run, so they pause after their current run; ours waits only for java runs."""
    global _RES
    if _RES is None:
        _RES = subprocess.Popen(["perl", "-e", "$0 = 'RunAbitReservation tasha_runs'; sleep 14400"])
        import atexit; atexit.register(release)


def release():
    global _RES
    if _RES is not None: _RES.terminate(); _RES = None


def wait():
    """Block while an ABIT java run is active (one ABIT at a time), then hold the slot."""
    reserve()
    while subprocess.run(["pgrep", "-f", "bin/java.*RunAbit"], capture_output=True).returncode == 0: time.sleep(5)


def seeds(s):
    lo, hi = (int(x) for x in s.split("-")); return range(lo, hi + 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["survey", "chain"]); ap.add_argument("--set", default="tasha", choices=list(SETS))
    ap.add_argument("--half", default="both"); ap.add_argument("--seeds", default="1-10"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); coef = SETS[a.set]
    if a.cmd == "survey":
        for hf in (["estimation", "validation"] if a.half == "both" else [a.half]):
            for s in seeds(a.seeds): wait(); S.run(hf, s, coef=coef, tag=a.set, skims=SK, force=a.force)
    else:
        for s in seeds(a.seeds): wait(); R.run(f"val_{a.set}_s{s:02d}", coef, seed=s, sample=0.05, threads=6, xmx="8g", skims=SK, force=a.force)
    print("done", flush=True)
