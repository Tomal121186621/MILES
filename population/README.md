# Stage 1: synthetic population (CVAE)

The generator code is in `cvae/`; its data (ACS PUMS inputs, trained models, step outputs) stay in the folder
configured as `vae_home` (`VAE_HOME/inputs`, `VAE_HOME/outputs`). The base-year scripts read and write the workspace
(`WORKSPACE/1_vae/...`, `WORKSPACE/data/...`).

Order: `python population/cvae/run_all.py` (runs `cvae/steps` 00 to 07), then the scripts in `base_year/`, then those in `validation/`.

- `cvae/steps/00_analyze_raw_acs.py` ... `02_build_targets.py`: raw ACS PUMS analysis, preprocessing, targets
- `cvae/steps/03_train.py`: train the conditional VAE
- `cvae/steps/04_generate.py`: generate the population
- `cvae/steps/05_workplace.py`: workplace assignment
- `cvae/steps/06_silo_export.py`: export for the land-use model
- `cvae/steps/07_validate.py` ... `09_study_areas.py`: held-out validation, figures, study areas
- `cvae/vaelib`: shared library
- `base_year/fit_controls.py`: fit the generated population to the 2016 controls
- `base_year/jobs_2016.py`, `market_vacancy_2016.py`, `zone_vacancy_2016.py`, `zone_weights_2016.py`, `zone_weights_2020.py`: job, vacancy and zone inputs
- `base_year/external_workplaces.py`: workplaces, including jobs outside the study area
- `base_year/export_base_year.py`: 2016 base-year microdata (households, persons, dwellings, jobs) for the land-use model
  (runs `cvae/steps/05_workplace.py` and `06_silo_export.py` on the fitted population)
- `base_year/*.json`: BLS JOLTS and vacancy rate inputs
- `validation/validate_population.py`, `validate_by_puma.py`, `figures.py`, `figure_puma_shares.py`: validation tables and figures
