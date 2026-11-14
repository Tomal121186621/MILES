# 11_outing_generation: data preparation code

`build_estimation_tables.py` (new) writes `../data/estimation/estimation_table.parquet` and `../data/holdout/estimation_table.parquet` with a01_outing.load(half), from the files in `../data/raw` and `00_shared_data`. Run: `PYTHONDONTWRITEBYTECODE=1 python3 build_estimation_tables.py` (python3 (or the Biogeme venv: needs only numpy, pandas, pyarrow)).

Copies (paths rewritten to `00_shared_data` and `../data`, lines marked `PATH`; nothing else changed):

| File | Original location (Validation_2026/...) | Role |
|---|---|---|
| rts_common.py, survey_population.py, tasha_distributions.py, abit_metrics.py | 3_abit/ | survey files, half split, TASHA activity types and person segments, distance matrix |
| te_common.py | 3_abit/tasha_estimation/ | survey episodes of each half |
| dc_common.py | 3_abit/destination_choice/ | zones and skims |
| estimate_subtours.py | 3_abit/tasha_estimation/ | data(half): work episodes and outings -> wbs_*.parquet |
| stepwise.py, a01_outing.py | side_experiments/respec_2026-11/step_by_step/activity/ | model development and final estimate (a01_outing.load = the estimation table) |

Checked: the tables written by this folder are identical to the data frames the project scripts build (both halves).
