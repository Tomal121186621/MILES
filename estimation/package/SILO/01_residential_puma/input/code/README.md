# Data preparation code: PUMA level

Copies of the project scripts; only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder (geopandas is needed for the bordering PUMAs):

    /opt/homebrew/anaconda3/bin/python3 build_estimation_data.py

The estimation tables are already in `../data`; running it again rewrites the same files (about 2.5 min, 4 GB).
With `DWELLING_ESTIMATES=../../../02_residential_dwelling/output/residential_dwelling_estimates.csv` the inclusive values are
computed with your dwelling-level estimates instead of the original ones (the check against the original fit is then skipped).

| File | Origin | Role |
|---|---|---|
| `build_estimation_data.py` | new for this package | writes ../data/estimation (with `market.csv`: market size M_p, turnover r_p; the added PUMA terms density x single, x young, x ln income and the core-city share) and ../data/holdout with the same calls and random draws as the original run; asserts the log-likelihood of the original run (estimation and hold-out) |
| `crosswalk.py` | project script | adds the 252 zones without a 2010 tract internal point to the zone -> PUMA / migration-PUMA crosswalk by their centroid (`00_shared_data/resloc_work/geo_*_zone_all.csv`; needs the project's TIGER tracts and tract-to-PUMA file) |
| `final_spec.py` | project script of the final model (functions only) | final design of the dwelling level, the term lists, the seed |
| `two_level.py` | project script of the two-level model | sampling of the dwelling sets, PUMA geography (crosswalks `geo_*_zone_all.csv`), PUMA-level design (inclusive value, market size, origin terms, commute, own-race share); asserts that no mover is dropped |
| `mnl.py` | `2_silo/resloc/mnl.py` | the original estimator (MNL, weights, fixed offset, robust s.e.) |
| `rc.py` | `2_silo/resloc/rc.py` | paths and helpers of the residential models |
| `s06_region.py`, `s04_dwelling.py` | `2_silo/resloc/` | helpers imported by `two_level.py` (transit skim path) |
| `s03_pums.py` | `2_silo/resloc/s03_pums.py` | upstream: ACS PUMS movers and dwelling market (outputs `pums_movers_est` / `pums_pool_est` in 00_shared_data/resloc_work) |
| `s01_geography.py` | `2_silo/resloc/s01_geography.py` | upstream: zone / PUMA / migration-PUMA geography (outputs `geo_*.csv` in 00_shared_data/resloc_work) |
| `check_against_provided.py` | new for this package | compares rebuilt tables with the provided ones |
