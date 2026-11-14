# Stage 1: synthetic population (CVAE)
Source repo of the generator: `VAE-SILO-MITO-MATSIM/Updated VAE` (data and trained models not copied).
Order: `cvae/run_all.py` runs `cvae/steps` in sequence, then `post/`.
- cvae/steps/00_analyze_raw_acs.py ... 02_build_targets.py: raw ACS PUMS analysis, preprocessing, targets
- cvae/steps/03_train.py: train the conditional VAE
- cvae/steps/04_generate.py: generate the population
- cvae/steps/05_workplace.py: workplace assignment
- cvae/steps/06_silo_export.py: export for SILO
- cvae/steps/07_validate.py ... 09_study_areas.py: held-out validation, figures, study areas
- cvae/vaelib: shared library
- post/export_silo_base.py: 2016 base microdata for SILO
- post/rebalance_population.py, workplace_balanced.py: balance population and workplaces
- post/employment_2016_lodes.py, market_vacancy_2016.py, zone_vacancy_2016.py, zone_weights_20*.py: job, vacancy and zone inputs
- post/validate_stage1.py, validate_stage1_puma96.py, figures_stage1.py, fig_pop_puma_shrink.py: stage 1 validation tables and figures
- post/*.json: BLS JOLTS and vacancy rate inputs
