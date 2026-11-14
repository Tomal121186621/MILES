# 15_tour_mode_school: data preparation code

Run from this folder with the Biogeme venv (numpy, pandas, pyarrow; no torch needed):

    PYTHONDONTWRITEBYTECODE=1 ~/.venvs/biogeme/bin/python build_estimation_tables.py

It writes `../data/estimation/tours.parquet` and `../data/holdout/tours.parquet`: the numeric DataFrame the estimation passed to
`biogeme.database.Database` (`m07_children.data(half, "school")`, one row per tour),
plus the label column `choice`. Checked 2026-11-13: identical to the project code's output for both halves.

My script (new): `build_estimation_tables.py`. Copies (paths rewritten to `00_shared_data` and `../data`, lines marked `PATH`):

| File | Original location (Validation_2026/...) | Role |
|---|---|---|
| m08_sequence.py | side_experiments/respec_2026-11/step_by_step/mode_choice/ | model development of work, shopping, other (final model = these articles' tables) |
| m09_school.py | same | school model development (final model of model 15) |
| m11_joint_group.py | same | joint household groups and their model (models 18, 19) |
| m07_children.py, m06_literature.py, m03_time_cost.py | same | data(): tour variables, time and cost, parking, members under 18 |
| m10_car_availability.py | same | car-driver availability under the household car allocation |
| t_mc_tables.py | same | writes the article tables |
| mc_common.py, prep_tours.py, estimate_gc.py, estimate_hh.py, estimate_wesml.py, mc_apply.py, wesml_targets.py | 3_abit/mode_choice/ | tours, level of service, fares, availability, WESML weights |
| dc_common.py | 3_abit/destination_choice/ | zones and skims |
| te_common.py | 3_abit/tasha_estimation/ | survey episodes (joint travel groups) |
| rts_common.py, survey_population.py, tasha_distributions.py, abit_metrics.py | 3_abit/ | survey files and TASHA definitions |

Notes
- `prep_tours.py` builds `raw/tours_<half>.parquet` from the survey and the period skims (`00_shared_data/skims/mode_choice_periods`); the shipped files are the ones the estimation read.
- `wesml_targets.py` needs the ACS PUMS 2015-19 person files and the 2010 tract-to-PUMA file, which are not shipped; its outputs are in `00_shared_data/mode_choice_inputs/wesml` and `raw/wesml_<half>.parquet` (model 14).
- The project estimated with `m08_sequence.py` / `m09_school.py` / `m11_joint_group.py` (Biogeme); `../../model` has a standalone script of the final model.
