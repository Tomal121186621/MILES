#!/usr/bin/env python3
"""Survey-population runs (seeds 1-10, both halves) of the TAZ sets and, as a control, of the current model-of-record sets
(coef_tasha / coef_tasha_cal as of 2026-10-27, after the tour-mode changes; the svy_*_behav / _cal runs of record are of 2026-10-26).
Tags: behavtaz (coef_tasha_taz), caltaz (coef_tasha_cal_taz), behavnow (coef_tasha), calnow (coef_tasha_cal).  2026-10-28."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
A3 = f"{WORKSPACE}/3_abit"   # coefficient sets (data)
sys.path.insert(0, f"{TERP_HOME}/activity/survey")
import survey_population as S, survey_runs as TR
SETS = {"behavtaz": "coef_tasha_taz", "caltaz": "coef_tasha_cal_taz", "behavnow": "coef_tasha", "calnow": "coef_tasha_cal"}
for tag, c in SETS.items():
    for hf in ["estimation", "validation"]:
        for s in range(1, 11): TR.wait(); S.run(hf, s, coef=f"{A3}/{c}", tag=tag, skims=TR.SK, threads=4)
print("done", flush=True)
