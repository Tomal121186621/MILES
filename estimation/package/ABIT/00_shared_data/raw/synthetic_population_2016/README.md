# raw/synthetic_population_2016

**Synthetic 2016 base population of the chain (SILO input): persons, households, dwellings, jobs, schools** (this project: VAE synthetic population (1_vae/export_silo_base.py -> 1_vae/vae_outputs/06_silo_input) + 2_silo/input_build/build_microdata.py (vacant jobs and dwellings) + 2_silo/schools/assign_students.py (school records, schools_2016.csv))

- URL: not downloadable: produced by the VAE and SILO input stages of the project; the SILO manual-estimation package ships hh_2016.csv and dd_2016.csv (manual_estimation/SILO/00_shared_data/synthetic_population_2016); pp_2016.csv and jj_2016.csv are in Validation_2026/2_silo/input/microData
- How: Copy pp_2016.csv, dd_2016.csv, hh_2016.csv, jj_2016.csv (2_silo/input/microData, versions of 2026-10-22) and schools_2016.csv (2_silo/input) of the project. Used for: zone population (persons per zone, survey_population.zone_population), jobs by zone and type (RET / OFF / other; build_zone_tables.py --jobs-from-raw), school enrolment by zone (occupancy of schools_2016.csv).
- Files: pp_2016.csv, dd_2016.csv, hh_2016.csv, jj_2016.csv, schools_2016.csv
- Notes: Status: the derived tables are provided (00_shared_data/zones: zone_population_2016.csv, jobs_2016_zone_type.parquet, schools_2016.csv). Rebuilding the population itself is the VAE stage (Updated VAE pipeline; inputs ACS PUMS 2012-2016 5-year, LODES 2016, JOLTS), outside this package.

