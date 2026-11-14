# Data preparation code

Copies of the project scripts. Only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder:

    ~/.venvs/biogeme/bin/python build_estimation_data.py

The estimation tables are already in `../data`; running it again rewrites the same files.

| File | Original location | Role |
|---|---|---|
| `build_estimation_data.py` | new | **new for this package**: writes ../data/estimation and ../data/holdout from the copies below, with the same calls (and random draws) as the original run, and checks the log-likelihood at the original estimates |
| `mnl.py` | `Validation_2026/2_silo/resloc/mnl.py` | the original estimator (MNL, set outcome, weights, robust s.e.) |
| `r01_income_similarity.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r01_income_similarity.py` | zone: income similarity |
| `r02_age_hhsize.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r02_age_hhsize.py` | zone: age and household size terms |
| `r03_sequence.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r03_sequence.py` | zone: land-use terms and the specification sequence (final spec in r03_fit.csv) |
| `r08_zone_multimodal.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r08_zone_multimodal.py` | zone: car-based vs multimodal accessibility (multimodal chosen) |
| `r11_zone_landuse.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r11_zone_landuse.py` | upstream: zone land-use attributes (zone_landuse_2016.csv) |
| `r12_zone_acc_split.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/r12_zone_acc_split.py` | zone: final estimation run (pooled non-work accessibility) |
| `rc.py` | `Validation_2026/2_silo/resloc/rc.py` | paths and helpers of the residential models |
| `run_residential_chain_1110.sh` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/run_residential_chain_1110.sh` | the original run order of the residential scripts (reference only; paths not rewritten) |
| `s01_geography.py` | `Validation_2026/2_silo/resloc/s01_geography.py` | upstream: zone / PUMA / MIGPUMA geography (outputs in 00_shared_data/resloc_work; its crosswalk inputs are not copied) |
| `s05_zone.py` | `Validation_2026/2_silo/resloc/s05_zone.py` | zone level: RTS households, cells, sampling of the 30 cells (seed 1022), design |
