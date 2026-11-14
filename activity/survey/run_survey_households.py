#!/usr/bin/env python3
"""Survey-population and chain-test runs of the re-specified ABIT (coefficient set activity/parameters, all its switches; 2026-11-10) for the
verification / validation / chain test of the validation report (validate_survey.py settings verification_respec, validation_respec,
chain_respec): ten replications (seeds 1-10) on the households of the estimation half and of the held-out half (run_survey/
svy_est_respec_sNN, svy_val_respec_sNN; skims base_transit2024), and ten on a 5 % sample of the synthetic 2016 population
(run/val_respec_sNN), as the record settings.
    python3 activity/survey/run_survey_households.py [survey|chain|all]"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
A3 = f"{WORKSPACE}/3_abit"   # data (skims, runs)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f"{ORIOLE_HOME}/activity")
import survey_population as S, run_activity_model as R
COEF = f"{ORIOLE_HOME}/activity/parameters"; SK = f"{A3}/skims/base_transit2024"
what = sys.argv[1] if len(sys.argv) > 1 else "all"
if what in ("survey", "all"):
    for half in ("estimation", "validation"):
        for s in range(1, 11): S.run(half, s, threads=4, coef=COEF, tag="respec", skims=SK)
if what in ("chain", "all"):
    for s in range(1, 11): R.run(f"val_respec_s{s:02d}", COEF, seed=s, sample=0.05, threads=4, xmx="8g", skims=SK)
print("done", flush=True)
