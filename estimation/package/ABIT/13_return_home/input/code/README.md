# 13_return_home: data preparation code

`build_estimation_tables.py` (new) writes `../data/estimation/estimation_table.parquet` and `../data/holdout/estimation_table.parquet` with a03_return.load(half) (drops the work-work pairs), from the files in `../data/raw` and `00_shared_data`. Run: `PYTHONDONTWRITEBYTECODE=1 python3 build_estimation_tables.py` (python3 with statsmodels (a03_return.py imports it)).

Copies (paths rewritten to `00_shared_data` and `../data`, lines marked `PATH`; nothing else changed):

| File | Original location (Validation_2026/...) | Role |
|---|---|---|
| rts_common.py, survey_population.py, tasha_distributions.py, abit_metrics.py | 3_abit/ | survey files, half split, TASHA activity types and person segments, distance matrix |
| te_common.py | 3_abit/tasha_estimation/ | survey episodes of each half |
| dc_common.py | 3_abit/destination_choice/ | zones and skims |
| estimate_return_home.py | 3_abit/tasha_estimation/ | pairs(half): pairs of consecutive out-of-home episodes -> rh_pairs_wbs_*.parquet; design() |
| stepwise.py, a03_return.py | side_experiments/respec_2026-11/step_by_step/activity/ | model development and final estimate (a03_return.load = the estimation table) |

Checked: the tables written by this folder are identical to the data frames the project scripts build (both halves).
