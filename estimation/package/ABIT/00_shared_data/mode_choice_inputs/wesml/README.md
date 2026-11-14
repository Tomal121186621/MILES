# WESML targets of the work tour mode choice

`wesml_targets.csv` (stratum x mode: ACS share, survey shares and weights of both halves) and `wesml_strata.csv` (county -> stratum), copied from `3_abit/mode_choice/results/` (written by `3_abit/mode_choice/wesml_targets.py`).
Population shares: ACS 2015-19 5-year PUMS person files of DC, MD, VA, WV (interview years 2017-2019; not shipped: `inputs/pums_2019_5yr/csv_p<st>.zip` of the project) and the Census 2010 tract-to-PUMA file (`Validation_2026/data/raw/resloc/2010_Census_Tract_to_2010_PUMA.txt`, not shipped).
The tour weights used by model 14 are in `14_tour_mode_work/input/data/raw/wesml_<half>.parquet` and in column `wesml` of its estimation table.
