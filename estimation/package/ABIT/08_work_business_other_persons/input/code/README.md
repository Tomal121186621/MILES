# 08 work business of other persons (from home): data preparation code

Run with the project Python (numpy, pandas, pyarrow, torch), from this folder:

1. `python3 build_estimation_tables.py` reads `../data/raw/loc_records_<half>.parquet` and `loc_cand_<half>.parquet` with `estimate_locations.load(half, "WORK_wbhome", "primary")` and writes the estimation tables (`../data/estimation/`, `../data/holdout/`: records, candidates, configurations).
2. `python3 build_biogeme_data.py` adds the zone variables (car distance from home) and writes `biogeme_part*.parquet` for Biogeme.

My scripts (new): `build_estimation_tables.py`, `build_biogeme_data.py`.

Copies (paths rewritten to `00_shared_data` and `../data`, lines marked `PATH`; nothing else changed):

| File | Original location (Validation_2026/...) | Role |
|---|---|---|
| estimate_locations.py | 3_abit/tasha_estimation/ | `records(half)` builds `loc_records/loc_cand`; `load()` selects the segment |
| te_common.py | 3_abit/tasha_estimation/ | survey episodes of each half |
| tasha_distributions.py, abit_metrics.py | 3_abit/ | TASHA activity types and person segments |
| rts_common.py, survey_population.py | 3_abit/ | survey files, half split, tract-to-zone |
| prep_dc_data.py | 3_abit/destination_choice/ | chooser attributes, tract-to-zone overlay |
| dc_common.py, dc_model.py | 3_abit/destination_choice/ | zones, skims, utility variables |
| estimate_dc.py | 3_abit/destination_choice/ | imported by estimate_locations.py |
| l_locations.py, l_locations_newls.py | side_experiments/respec_2026-11/step_by_step/locations/ | model development and final estimation (model `l04_wbhome`) |
| estimate_fullset_loc.py, estimate_fullset_taz.py, dc_taz_engine.py, estimate_dc_taz.py, estimate_subtour_dest.py, estimate_complexity.py, estimate_stops_seq.py | 3_abit/tasha_estimation/ | full-choice-set likelihood used by l_locations.py (imports) |
| mode_logsum_new.py | side_experiments/respec_2026-11/step_by_step/accessibility_new/ | mode-choice logsum (not in this model) |
| mc_common.py, prep_tours.py | 3_abit/mode_choice/ | imported by l_locations_newls.py |

Notes
- The raw record files are the files the estimation read (built 2026-10-23). Rebuilding them from `00_shared_data` gives the same rows except `male`, coded the other way round in the shipped files (survey population rebuilt with the corrected gender coding on 2026-10-27). `male` and the mode-choice logsum are not in this model.
- The estimation ran with `l_locations_newls.py revise l04_wbhome` (PyTorch, L-BFGS-B, robust sandwich covariance). The Biogeme script in `../../model` writes the same likelihood.
