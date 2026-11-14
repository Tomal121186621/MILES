# Stage 3: ABIT activity-based model
Java: `java/README.md`. Coefficients of the final models: `coef_respec/` (built by build_coef_respec.py).
Order:
1. build_coef_respec.py: build `coef_respec/` from the estimation results (coef_tools.py helper)
2. final_2024/runs_respec24.py snapshot | run --jobs 2 | persons | choose: freeze coefficients and classes, run 10 replications (ABIT seeds 1-10, 10 % households) on the SILO seed 1 population after the schools step, collect the persons table, choose the replication for MATSim (pick_seed.py rule; replication 8)
   - runs_fin24.py: run helper used by runs_respec24.py; make_abit_properties.py: writes the ABIT properties file; run_abit.py: single run
3. roorda_validation.py (with tasha_distributions.py, tasha_runs.py, rts_common.py, survey_population.py, respec_survey_runs.py): TASHA-style validation against the 2017/18 survey
- respec_*.py: checks of the re-specified models (decomposition, joint tours, unit check, person frequencies, survey mode shares)
- final_2024/respec_smoke.py, respec24_mode_shares.py, fin24_report.py: smoke test, mode shares and report of the 2024 runs
- abit_metrics.py, build_targets.py, education_*.py: targets and metrics used by the validation
- abit_day.py: representative-day picker imported by pipeline/abit_to_matsim_pop.py (originally ABIT/validation/)
