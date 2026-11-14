# Data preparation code

Copies of the project scripts. Only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder:

    /opt/homebrew/anaconda3/bin/python3 build_estimation_data.py   # needs geopandas (not in the Biogeme venv)

The estimation tables are already in `../data`; running it again rewrites the same files.

| File | Original location | Role |
|---|---|---|
| `build_estimation_data.py` | new | **new for this package**: writes ../data/estimation and ../data/holdout from the copies below, with the same calls (and random draws) as the original run, and checks the log-likelihood at the original estimates |
| `mnl.py` | `Validation_2026/2_silo/resloc/mnl.py` | the original estimator (MNL, set outcome, weights, robust s.e.) |
| `r01_income_similarity.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r01_income_similarity.py` | zone: income similarity |
| `r04_dwelling_age.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r04_dwelling_age.py` | dwelling: age bands |
| `r05_region_sequence.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r05_region_sequence.py` | county: added variables (add_growth) and the specification sequence; final = step Ja |
| `r06_dwelling_income.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r06_dwelling_income.py` | dwelling: final specification (terms x ln income, dropped terms) |
| `r07_county_iv.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r07_county_iv.py` | county: inclusive values of the final zone and dwelling models (county_data_*.pkl) |
| `rc.py` | `Validation_2026/2_silo/resloc/rc.py` | paths and helpers of the residential models |
| `run_residential_chain_1110.sh` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/run_residential_chain_1110.sh` | the original run order of the residential scripts (reference only; paths not rewritten) |
| `s01_geography.py` | `Validation_2026/2_silo/resloc/s01_geography.py` | upstream: zone / PUMA / MIGPUMA geography (outputs in 00_shared_data/resloc_work; its crosswalk inputs are not copied) |
| `s03_pums.py` | `Validation_2026/2_silo/resloc/s03_pums.py` | upstream: ACS PUMS movers and dwelling market (outputs pums_movers_est / pums_pool_est in 00_shared_data/resloc_work) |
| `s04_dwelling.py` | `Validation_2026/2_silo/resloc/s04_dwelling.py` | dwelling level: sampling of the 30 alternatives (seed 20261022) and base design |
| `s05_zone.py` | `Validation_2026/2_silo/resloc/s05_zone.py` | zone level: RTS households, cells, sampling of the 30 cells (seed 1022), design |
| `s06_region.py` | `Validation_2026/2_silo/resloc/s06_region.py` | county level: region attributes, inclusive values, assembly of the county data |
| `s07_region_validation.py` | `Validation_2026/2_silo/resloc/s07_region_validation.py` | county: validation helpers (X_of) |
