# 01 primary destination (pooled): data preparation code

Run with the project Python (numpy, pandas, pyarrow, torch), from this folder:

1. optional: `python3 prep_dc_taz.py` rebuilds `../data/raw/dc_{rec,cand,cfg}_<half>_taz.parquet` from the survey (00_shared_data). Checked: the rebuilt files are identical to the shipped ones (all columns, both halves). It overwrites the shipped files.
2. `python3 build_estimation_tables.py` writes `../data/{estimation,holdout}/<PURPOSE>/{records,candidates,configurations}.parquet` with `estimate_fullset_taz.load` (adds `multi`, tour with stops). Checked: identical to the original project loader's output.
3. `python3 build_biogeme_data.py` writes `biogeme_part*.parquet` and `biogeme_meta.json` (car distance and car generalised time from every home configuration to every zone).
4. optional: `python3 check_project_likelihood.py [--at full|article]` evaluates the project's own likelihood (Chunk of estimate_fullset_taz.py) at the reference estimates: -49,122.4992 on the estimation half.

My scripts (new): `build_estimation_tables.py`, `build_biogeme_data.py`, `check_project_likelihood.py`.

Copies (paths rewritten to `00_shared_data` and `../data`, lines marked `PATH`; nothing else changed):

| File | Original location (Validation_2026/...) | Role |
|---|---|---|
| prep_dc_taz.py | 3_abit/tasha_estimation/ | records from the survey traffic zones; location mixture (destination, home) |
| estimate_fullset_taz.py | 3_abit/tasha_estimation/ | `load()`, full-set chunked likelihood `Chunk` |
| estimate_dc_taz.py, dc_taz_engine.py, estimate_complexity.py, estimate_stops_seq.py | 3_abit/tasha_estimation/ | loader, mixture, `multi_flag` |
| te_common.py | 3_abit/tasha_estimation/ | survey episodes |
| dc_common.py, dc_model.py, prep_dc_data.py, estimate_dc.py | 3_abit/destination_choice/ | zones, skims, variables, chooser attributes |
| rts_common.py, survey_population.py, tasha_distributions.py, abit_metrics.py | 3_abit/ | survey files, half split, tract-to-zone |
| d_primary.py | side_experiments/respec_2026-11/step_by_step/dest_primary/ | separate purpose models; adds ln distance x male / one-person household |
| dp_pooled.py, pool_core.py | side_experiments/respec_2026-11/step_by_step/dest_pooled/ | pooled estimation (`dp_pooled.py revise`: final model) |

prep_dc_taz.py reads the TAZ crosswalks of `00_shared_data/taz_crosswalks` (BMC and TPB TAZ to model zone; 2010 tracts split by housing units and by jobs).
