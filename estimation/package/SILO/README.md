# SILO models: manual estimation package (Biogeme)

Each estimated SILO-side model of the Baltimore chain, as published in the article (the specification the engine runs use),
with its exact estimation data, a Biogeme script and the article estimates for comparison. The Route B revisions of
13 November 2026 are not in this package (they are in `../CLAUDE_TABLES/SILO/route_B_2026-11-13`).

| Folder | Model | Article table | N | Alternatives |
|---|---|---|---|---|
| `01_residential_county` | Residential location: county | est_region | 15,163 | 44 counties (all) |
| `02_residential_zone_structure_type` | Residential location: zone x structure type | est_zone | 10,655 | 30 sampled cells |
| `03_residential_dwelling` | Residential location: dwelling | est_dwelling | 15,163 | 30 sampled dwellings |
| `04_car_ownership` | Car ownership | est_cars | 91,348 | 4 |
| `05_workplace_choice` | Workplace | est_jobchoice | 9,707 | 100 sampled zones |
| `06_school_location_K8` | School location, K-8 | est_school | 1,509 | 1,144 zones (all) |
| `07_school_location_high_school` | School location, high school | est_school | 668 | 719 zones (all) |
| `08_school_location_college` | School location, college | est_school | 673 | 141 zones (all) |

No other SILO model is estimated (the article's overview table lists these eight).

## Layout of a model folder
- `input/code/` copies of the project scripts that build the data (paths changed only), `build_estimation_data.py` (writes the tables),
  `check_against_provided.py` (compares a rebuild with the provided tables); `README.md` lists the original location of each file.
- `input/data/raw/` small source extracts and a README for the large ones; `estimation/` the estimation table(s) and `data_dictionary.csv`;
  `holdout/` the hold-out sample.
- `model/estimate_<name>.py` (Biogeme), `reference_estimates.csv` (article values and the full-precision estimates of the original run),
  `start_values_full_precision.csv`, `compare_with_reference.py`, `README.md`.
- `output/` your runs (Biogeme writes there).
- `RUN.json` data sources, every step from raw data to the comparison, check values and notes. `RUN_ORDER.json`: order of the folders.

`00_shared_data/` holds the large sources once (PUMS, RTS, skims, synthetic population, accessibility, ...); see its README.

## Setup
Biogeme 3.3.5 in `~/.venvs/biogeme` (`~/.venvs/biogeme/bin/pip show biogeme`). It has numpy, pandas, pyarrow and scipy, so it also runs the
package build scripts, except the county build, which needs geopandas: `/opt/homebrew/anaconda3/bin/python3`.
New environment: `python3 -m venv ~/.venvs/biogeme && ~/.venvs/biogeme/bin/pip install biogeme==3.3.5 pyarrow`.

## Run order
03 dwelling and 02 zone before 01 county: the county model uses their inclusive values (as data columns; the provided data hold
those of the published models). 04 to 08 are independent. In each folder:

    cd model
    ~/.venvs/biogeme/bin/python estimate_<name>.py --check   # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_<name>.py           # estimation, results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py

## Verification: Biogeme log-likelihood at the article coefficients

| Model | Article LL(beta) | Biogeme, article coefficients (4 decimals) | Biogeme, full-precision estimates |
|---|---|---|---|
| County (weighted) | -15,959.4 | -15,959.4401 | -15,959.4331 |
| Zone x structure type (weighted) | -28,089.7 | -28,089.7213 | -28,089.7212 |
| Dwelling | -47,688.2 | -47,688.1973 | -47,688.1973 |
| Car ownership | -80,664.0 | -80,664.0051 | -80,664.0043 |
| Workplace | -21,334.3 | -21,334.2842 | -21,334.2822 |
| School K-8 | -2,941.0 | -2,941.0295 | not run (33 min per evaluation) |
| School high school | -1,243.3 | -1,243.2733 | -1,243.2733 |
| School college | -1,827.8 | -1,827.7888 | -1,827.7886 |

Test estimations (in a scratch folder) of models 01 to 05 gave the article coefficients and robust s.e. to 4 decimals.
For the weighted models (01, 02) the weight is written inside the log-likelihood so that the robust s.e. are the article's WESML
sandwich; Biogeme's own 'weight' formula (option `--biogeme-weight`) gives the same estimates but other robust s.e.

## Memory and time
Models 01 to 05: under 4 minutes and 3 GB each. The school models use the full choice set with a location mixture (exact, with
`WeightedLogSumExp`): the LL check takes 20 s (college), 3 min (high school) and 33 min / 4.2 GB (K-8). A test estimation of the
college model was stopped after 31 min at 8.4 GB (compilation of the analytical Hessian). Estimating the high-school and K-8 models
will need much more time and memory; with the Java runs using most of the 64 GB it is probably not feasible on this machine.
See the school READMEs for derivative settings that may reduce memory.
