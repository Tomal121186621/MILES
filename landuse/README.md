# Stage 2: SILO land use (calibration, 5 seeds, schools)
Engine: Java, see `java/README.md`. Run order:
1. input_build/*.py: build SILO inputs (zones, controls, microdata, development, permits, ...)
2. engine_check/e01-e05_*.py: write the engine input files of the re-specified models (`input/*respec*.csv`); c01-c05: unit checks; w01_base_respec.py: re-assign base 2016 workplaces
3. run/make_properties.py: write a properties file (examples: run/oos_respec_s1..5.properties, run/calib_respecF_r1..4.properties)
4. run/run_silo.sh: run the engine on a properties file (classpath.txt, log4j2_quiet.xml)
5. calibration/calibrate.py 4 1 (env CALIB_SPEC=respec CALIB_TAG=F): calibrate 2016-2020, final parameters params_respec.json (= params_respecF.json), log calibration_log_respec.csv
6. run/run_oos.py 5 2 (env OOS_SPEC=respec): five out-of-sample seeds 2016-2024 with the calibrated parameters
7. schoolchoice/sc_13_run_seeds.py 1 2 3 4 5 (env SCHOOL_SPEC=respec): school assignment per seed (sc_10_assign.py, coefficients in schoolchoice/apply)
8. validation/validate_silo.py <scenario> 2016 2024: validation tables (called by run_oos.py); aggregate_seeds.py, final_tables.py, headline_2024.py: seed means and tables
- schools/: build the school inventory and assign students (earlier step used by the base year)
- engine_check/p01_respec_seeds.py: seed comparison and choice of the seed
- calibration/targets_construction.py, fetch_data.py: calibration targets
- input/: small SILO input tables (respec coefficient files and configuration)
- REPORT.md, CALIBRATION.md: stage reports
