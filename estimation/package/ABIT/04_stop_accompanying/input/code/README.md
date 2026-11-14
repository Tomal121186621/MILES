# 04_stop_accompanying: data preparation code

Run with the project Python (numpy, pandas, pyarrow, torch), from this folder:

1. `python3 build_estimation_tables.py` reads `../data/raw/dc_{rec,cand,cfg}_<half>_taz.parquet` and writes the estimation tables of the accompany stops (`../data/estimation/`, `../data/holdout/`: records, candidates, configurations).
2. `python3 build_biogeme_data.py` computes, for every anchor configuration and every zone, the detour (`imp`), and the mode-choice logsum of the detour (`ls`), and writes `biogeme_part*.parquet` for Biogeme (about 1-3 minutes per half; the logsum is the slow part).

My scripts (new): `build_estimation_tables.py`, `build_biogeme_data.py`.

Copies (paths rewritten to `00_shared_data` and `../data`, lines marked `PATH`; nothing else changed):

| File | Original location (Validation_2026/...) | Role |
|---|---|---|
| prep_dc_taz.py | 3_abit/tasha_estimation/ | builds `dc_rec/dc_cand/dc_cfg_<half>_taz.parquet` from the survey (traffic-zone locations, anchor configurations) |
| estimate_fullset_taz.py | 3_abit/tasha_estimation/ | `load()` of the records; `Chunk.ll`, the full-set mixture likelihood the estimation used |
| dc_taz_engine.py, estimate_dc_taz.py, estimate_complexity.py, estimate_stops_seq.py | 3_abit/tasha_estimation/ | location mixture, record loader, imports |
| te_common.py | 3_abit/tasha_estimation/ | survey episodes |
| rts_common.py, survey_population.py, tasha_distributions.py, abit_metrics.py | 3_abit/ | survey files, half split, tract-to-zone |
| dc_common.py, dc_model.py, prep_dc_data.py, estimate_dc.py | 3_abit/destination_choice/ | zones, skims, utility variables, chooser attributes |
| s_stops.py | side_experiments/respec_2026-11/step_by_step/dest_stop/ | model development (blocks, decision rule, final stage); adds male / household size to the chooser flags |
| s_stops_newls.py | same | the logsum variable `ls` of the re-estimated tour mode models (used by build_biogeme_data.py) |
| s_stops_refit.py | same | final refit with the current logsum: produced the published estimates (`s_acc_coef.csv` rows "final") |
| mode_logsum_new.py | side_experiments/respec_2026-11/step_by_step/accessibility_new/ | mode-choice logsum; reads `00_shared_data/mode_choice_logsums/m08_coef.csv` (and `m09_coef.csv`) |
| mc_common.py | 3_abit/mode_choice/ | tour level of service: period skims (`00_shared_data/skims/mode_choice_periods`), fares, parking share (`00_shared_data/mode_choice_inputs`) |

Notes
- The `dc_*_taz.parquet` files in `../data/raw` are the files the estimation read (built 2026-11-04). They hold all four purposes; `build_estimation_tables.py` selects the accompany stops.
- The logsum values written by the copies were checked against the original project modules on 25 records per purpose (largest difference 0).
- The estimation itself ran with `s_stops_newls.py` / `s_stops_refit.py` (PyTorch, L-BFGS-B, robust sandwich covariance). The Biogeme script in `../../model` writes the same likelihood.
