# Data preparation code: dwelling level

Copies of the project scripts; only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder:

    ~/.venvs/biogeme/bin/python build_estimation_data.py

The estimation tables are already in `../data`; running it again rewrites the same files (a few seconds).

| File | Origin | Role |
|---|---|---|
| `build_estimation_data.py` | new for this package | writes ../data/estimation and ../data/holdout with the same random draws as the original run; asserts the log-likelihood of the original run (estimation and hold-out) |
| `final_spec.py` | project script of the final model (functions only) | final design of the dwelling level (18 columns), the seed |
| `two_level.py` | project script of the two-level model | sampling of the 30-dwelling sets (`sample`) and base design (`dw_X`) |
| `mnl.py` | `2_silo/resloc/mnl.py` | the original estimator |
| `rc.py` | `2_silo/resloc/rc.py` | paths and helpers of the residential models |
| `s06_region.py`, `s04_dwelling.py` | `2_silo/resloc/` | imported by `two_level.py` (not used by the dwelling level) |
| `s03_pums.py` | `2_silo/resloc/s03_pums.py` | upstream: ACS PUMS movers and dwelling market (outputs in 00_shared_data/resloc_work) |
| `s01_geography.py` | `2_silo/resloc/s01_geography.py` | upstream: zone / PUMA / migration-PUMA geography |
| `check_against_provided.py` | new for this package | compares rebuilt tables with the provided ones |
