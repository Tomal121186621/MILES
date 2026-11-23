# Stage 2: land use (SILO): inputs, coefficients, calibration, seed runs, schools

The code is here; inputs, runs and outputs stay in the workspace (`WORKSPACE/2_silo/input`, `WORKSPACE/2_silo/run`,
`WORKSPACE/data`, ...). The engine is Java, see `engine/README.md`; it is built in `WORKSPACE/2_silo/engine`.

## Adopted setup (final runs)
`run/adopted_settings.sh` defines the setup of all final SILO runs. Copy the files of `engine_inputs/` to `WORKSPACE/2_silo/input`,
source the script, then run the out-of-sample seeds:

    source landuse/run/adopted_settings.sh
    OOS_SPEC=respec OOS_SET="$ADOPTED_SET" python landuse/run/run_seeds.py 5 2

- Residential location: two levels, PUMA then dwelling (`residential_puma_coefficients.csv`, `residential_dwelling_coefficients.csv`,
  `residential_zone_core_city.csv`; geography `residential_puma_zones.csv`, `residential_migration_puma_zones.csv`,
  `residential_twolevel_zone_attributes.csv`, `residential_puma_adjacency.csv`, `residential_puma_turnover.csv`); market size =
  dwelling stock x fixed turnover rate; PUMA weight scaled by min(1, vacancy rate / 2016 rate); own-race share of the PUMA recomputed
  every year; exact vacancy counts; population control until no vacancy is left. Estimated with ACS PUMS only
  (`estimation/development/residential_location/r14`-`r22`).
- Moving decision: shift recalibrated to the ACS 2017-2020 share of persons who moved (`calibration/calibrate_moveshift.py`, log
  `calibration/calibration_log_moveshift.csv`); the other levers keep their values; final parameters
  `calibration/calibrated_parameters.json`.
- Workplace choice: `workplace_choice_coefficients.csv` (24 terms, size term on total jobs, `job.choice.size = jobs`); the District of
  Columbia term is the estimate, without a calibration shift (`estimation/development/workplace_choice/w13_export_silo.py`).
- School location inside SILO (`school_location_coefficients_{k8,hs,college}.csv`, data files written by
  `estimation/development/other_locations/l11_export_silo.py`), seats released when a student leaves school or the population.
  The seats of band changers and school leavers are freed at the start of the year (`school.seat.release.yearstart`),
  working students keep their seat (`education.working.students`), and the exit table is extended to age 63, with forced exit after
  64 (`education_transitions.csv`, an assumption).
- Car ownership: `car_ownership_estimated_coefficients.csv` (persons-16+ dummies), Baltimore City term estimated
  (`car_ownership_county_constants.csv`); estimation in `estimation/package/SILO/04_car_ownership`, engine files by
  `coefficients/export_car_ownership.py`.
- Driver's licences: Maryland targets by age and area (`drivers_license_targets_md.csv`). New licences in each area and age cell go to
  employed persons first (`drivers.license.allocation = employed_first`, rule-based).
- Other settings: structural vacancy 2016
  (`inputs/build_structural_vacancy.py`), population control at the end of the year, pricing after the control, gross in-migration
  rates 2014-18 (`inmigration_rate_2014_18.csv`), population and job controls and base-year microdata built by
  `inputs/base_year/build_base_year.sh`. The final runs start from the 2016 base population rebuilt against ACS 2014-18 cars by
  workers: household cars are re-assigned to the ACS 2014-18 joint distribution of cars, workers and persons 16+, keeping each
  county's car distribution, and 16-17-year-olds are enrolled at the ACS 2014-18 shares by state and employment, with schools
  assigned by the base-year rule.
- The engine switches `resloc.race.share.fixed2016` (robustness check, own-race share held at 2016) and `resloc.county.vacancy.factor`
  (tested, not adopted) are `false`.

## Earlier runs
Run order:
1. `inputs/build_*.py`: build the engine inputs (zones, controls, microdata, development, permits, ...) in `WORKSPACE/2_silo/input`.
2. `coefficients/write_*.py`: write the engine input files of the estimated models (residential location, car ownership,
   workplace choice, school location, zone attributes) from the estimation results; `inputs/assign_base_workplaces.py`:
   re-assign the 2016 base workplaces with the estimated workplace model.
3. `checks/check_*.py`: unit checks of the engine utilities against the estimation code; `checks/smoke_summary.py`: summary of a
   short run.
4. `run/write_properties.py <scenario> <start_year> <end_year> [skim_years] [seed] [record|respec]`: write a properties file
   in `WORKSPACE/2_silo/run`.
5. `run/run_silo.sh <properties> [heap]`: run the engine (Maven classpath in `run/classpath.txt`, with `$HOME` expanded;
   logging configuration `run/log4j2_quiet.xml`).
6. `calibration/calibrate.py <rounds> [start_round]` (environment `CALIB_SPEC=respec` for the estimated models): calibrate on
   2016-2020; final parameters in `calibration/calibrated_parameters.json`, log in `calibration/calibration_log.csv`.
7. `run/run_seeds.py <n_seeds> [parallel] [end_year]` (environment `OOS_SPEC=respec`): out-of-sample seed runs 2016-2024 with
   the calibrated parameters, each validated by `validation/validate_landuse.py`.
8. `run/choose_seed.py`: seed mean and choice of the representative seed.
9. `schools/assign_all_seeds.py <seeds...>` (environment `SCHOOL_SPEC=respec`): school assignment per seed and year
   (`schools/assign_schools.py`; application files in `WORKSPACE/2_silo/schoolchoice/apply`), summary by
   `schools/summarize_seeds.py`.
10. `validation/validate_landuse.py <scenario> 2016 2024`: validation tables; `aggregate_seeds.py`, `final_tables.py`,
    `headline_2024.py`: seed means and tables.

Other folders:
- `schools/`: school inventory (`build_inventory.py`), base-year students (`assign_base_students.py`), school location choice
  estimation (`school_data.py`, `school_logsums.py`, `school_likelihood.py`, `school_stepwise.py`, `school_final_model.py`,
  `school_diagnostics.py`, `school_biogeme_check.py`), application inputs (`write_inputs.py`, `enrolment_rates.py`) and tests
  (`test_assignment.py`); `schools/parameters/` holds a copy of the estimated school coefficients.
- `lib/residential/`, `lib/jobchoice/`: shared code of the residential location and workplace choice models.
- `calibration/targets_construction.py`, `fetch_data.py`: calibration targets.
- `engine_inputs/`: copy of the small engine input tables (coefficient files and configuration). The input files of the earlier
  three-level residential model (`residential_county_*`, `residential_zone_attributes.csv`, `residential_zone_dwelling_coefficients.csv`,
  `resloc_*`) were removed; they remain in the git history and are not read when `resloc.twolevel = true`.
- `engine/`: engine source changes (`src/`, `silo_changes.patch`).

Run every script from the repository root, e.g. `python landuse/run/run_seeds.py 5 2`.
