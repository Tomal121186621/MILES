# Stage 2: land use (SILO): inputs, coefficients, calibration, seed runs, schools

The code is here; inputs, runs and outputs stay in the workspace (`WORKSPACE/2_silo/input`, `WORKSPACE/2_silo/run`,
`WORKSPACE/data`, ...). The engine is Java, see `engine/README.md`; it is built in `WORKSPACE/2_silo/engine`.

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
8. `run/choose_seed.py`: seed mean, scorecard and choice of the representative seed.
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
- `engine_inputs/`: copy of the small engine input tables (coefficient files and configuration).
- `engine/`: engine source changes (`src/`, `silo_changes.patch`).

Run every script from the repository root, e.g. `python landuse/run/run_seeds.py 5 2`.
