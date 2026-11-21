# Data preparation code

Copies of the project scripts. Only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder:

    ~/.venvs/biogeme/bin/python build_estimation_data.py

The estimation tables are already in `../data`; running it again rewrites the same files.

| File | Original location | Role |
|---|---|---|
| `build_estimation_data.py` | new | **new for this package**: writes ../data/estimation and ../data/holdout from the copies below, with the same calls (and random draws) as the original run; adds the persons-16+ dummies (p16_2, p16_3, p16_4p) and the Baltimore City column (city) of the final model |
| `mnl.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/car_ownership/mnl.py` | the original estimator (MNL, set outcome, weights, robust s.e.) |
| `s01_data.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/car_ownership/s01_data.py` | car ownership: household table hh.parquet from PUMS |
| `s04_form.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/car_ownership/s04_form.py` | car ownership: piecewise income |
| `s06_age.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/car_ownership/s06_age.py` | car ownership: age of the oldest member |
| `s07_sequence.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/car_ownership/s07_sequence.py` | car ownership: specification sequence |
| `s08_oldest_age.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/car_ownership/s08_oldest_age.py` | car ownership: final model (oldest member's age) |
