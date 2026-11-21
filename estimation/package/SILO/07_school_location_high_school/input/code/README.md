# Data preparation code

Copies of the project scripts. Only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder:

    ~/.venvs/biogeme/bin/python school_attributes_data.py   # school attributes (optional: outputs provided in 00_shared_data/school_choice_work)
    ~/.venvs/biogeme/bin/python build_estimation_data.py

The estimation tables are already in `../data`; running them again rewrites the same files.

| File | Original location | Role |
|---|---|---|
| `build_estimation_data.py` | new | **new for this package**: writes ../data/estimation and ../data/holdout from the copies below, with the same calls as the original run, and checks the log-likelihood at the final estimates (both halves) |
| `school_final_spec.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/locations/l10_school.py` (renamed) | schools: final specification sequence (cleanups, charter-or-magnet share, quality, own-race share) and final models |
| `school_model_ext.py` | `.../step_by_step/locations/l09_school_ext.py` (renamed) | schools: engine extensions (new variables, size weights fixed at 0) and the earlier tests (separate charter and magnet shares, zone-level quality, Baltimore City high-school term, college dormitory students) |
| `school_attributes_data.py` | `.../step_by_step/locations/l09_school_data.py` (renamed) | school attributes: student race (RTS), enrolment by race (CCD 052, PSS, IPEDS EF2023A), charter (CCD 029) and magnet (CCD 129 2017-18) flags, % proficient (EDFacts), dormitory capacity (IPEDS IC2023); writes `00_shared_data/school_choice_work/school_*` (output names changed from l09_* to school_*) |
| `l07_school.py` | `.../step_by_step/locations/l07_school.py` | schools: previous specification sequence and final model (reference) |
| `sc_00_sabs.py` | `Validation_2026/2_silo/schoolchoice/sc_00_sabs.py` | upstream: attendance boundaries (SABS 2015-16; inputs not copied) |
| `sc_01_data.py` | `Validation_2026/2_silo/schoolchoice/sc_01_data.py` | upstream: students, home / school location mixtures, enrolment by zone (inputs not copied) |
| `sc_03_engine.py` | `Validation_2026/2_silo/schoolchoice/sc_03_engine.py` | schools: design (full choice set, location mixture) and estimator |
| `sc_04_stepwise.py` | `Validation_2026/2_silo/schoolchoice/sc_04_stepwise.py` | schools: term names and expected signs |
| `sc_common.py` | `Validation_2026/2_silo/schoolchoice/sc_common.py` | schools: paths, zones, skim, enrolment |
| `check_against_provided.py` | new | compares rebuilt tables with the provided ones |

`sc_03_engine.py` reads the school-tour logsums (not in the final models) from `00_shared_data/school_choice_work/logsum.npy`
(changed 2026-11-18; before: the project folder). `*_pre1118d.py`: the versions before 2026-11-18 (previous models).
