# 20_transit_leg_mode: data preparation code

`build_estimation_tables.py` (new) writes `../data/estimation/estimation_table.parquet` and `../data/holdout/estimation_table.parquet` with estimate_transit_legs.features(legs(half)) and the free-car rule of `free_car.py` (car driver only when a household car is free over the tour window), legs whose chosen mode is available, from the files in `../data/raw` and `00_shared_data`. Run: `PYTHONDONTWRITEBYTECODE=1 python3 build_estimation_tables.py` (python3 (or the Biogeme venv)).

Copies (paths rewritten to `00_shared_data` and `../data`, lines marked `PATH`; nothing else changed):

| File | Original location (Validation_2026/...) | Role |
|---|---|---|
| rts_common.py, survey_population.py, tasha_distributions.py, abit_metrics.py | 3_abit/ | survey files, half split, TASHA activity types and person segments, distance matrix |
| te_common.py | 3_abit/tasha_estimation/ | survey episodes of each half |
| dc_common.py | 3_abit/destination_choice/ | zones and skims |
| mc_common.py, prep_tours.py | 3_abit/mode_choice/ | period skims, fares, tours (tours_<half>.parquet) |
| estimate_transit_legs.py | 3_abit/tasha_estimation/ | legs(half), features(), the search and final estimate |
| free_car.py | new | free-car rule of the car-driver availability (as in the leg-mode draw of DAYMAP, the Daily Activity Model for Agent Plans) |

Checked: the tables written by this folder give the reference LL of both halves (estimation N 6,773, hold-out N 6,417).
