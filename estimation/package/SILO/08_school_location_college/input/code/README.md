# Data preparation code

Copies of the project scripts. Only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder:

    ~/.venvs/biogeme/bin/python build_estimation_data.py

The estimation tables are already in `../data`; running it again rewrites the same files.

| File | Original location | Role |
|---|---|---|
| `build_estimation_data.py` | new | **new for this package**: writes ../data/estimation and ../data/holdout from the copies below, with the same calls (and random draws) as the original run, and checks the log-likelihood at the original estimates |
| `l07_school.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/locations/l07_school.py` | schools: specification sequence and final model |
| `sc_00_sabs.py` | `Validation_2026/2_silo/schoolchoice/sc_00_sabs.py` | upstream: attendance boundaries (SABS 2015-16; inputs not copied) |
| `sc_01_data.py` | `Validation_2026/2_silo/schoolchoice/sc_01_data.py` | upstream: students, home / school location mixtures, enrolment by zone (inputs not copied) |
| `sc_03_engine.py` | `Validation_2026/2_silo/schoolchoice/sc_03_engine.py` | schools: design (full choice set, location mixture) and estimator |
| `sc_04_stepwise.py` | `Validation_2026/2_silo/schoolchoice/sc_04_stepwise.py` | schools: term names and expected signs |
| `sc_common.py` | `Validation_2026/2_silo/schoolchoice/sc_common.py` | schools: paths, zones, skim, enrolment |
