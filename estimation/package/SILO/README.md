# SILO models: manual estimation package (Biogeme)

Each estimated SILO-side model of the Baltimore chain, as published in the article (the specification the engine runs use),
with its exact estimation data, a Biogeme script and the article estimates for comparison. The Route B revisions of
13 November 2026 are not in this package (they are in `../CLAUDE_TABLES/SILO/route_B_2026-11-13`). The residential location
models (01, 02) are the two-level model of the estimation document; the SILO code for it is not written yet, so the engine
runs still use the former model. The workplace model (05) is the simplified 25-parameter model of the estimation document
(the former 35-parameter scripts and data are in `05_workplace_choice/_former_35_parameter_model/`).

| Folder | Model | Table | N | Alternatives |
|---|---|---|---|---|
| `01_residential_puma` | Residential location: PUMA (upper level) | est_resloc_puma | 15,163 | 97 PUMAs (all available) |
| `02_residential_dwelling` | Residential location: dwelling within the PUMA (lower level) | est_resloc_dwelling | 15,163 | 30 sampled dwellings |
| `04_car_ownership` | Car ownership | est_cars | 91,348 | 4 |
| `05_workplace_choice` | Workplace (simplified, 25 parameters) | est_workplace | 9,707 | 100 sampled zones |
| `06_school_location_K8` | School location, K-8 | est_school | 1,509 | 1,144 zones (all) |
| `07_school_location_high_school` | School location, high school | est_school | 668 | 719 zones (all) |
| `08_school_location_college` | School location, college | est_school | 673 | 141 zones (all) |

The residential location model has two levels (PUMA, then dwelling within the PUMA), estimated on ACS PUMS 2014-2018 movers
only. It replaces the former three-level model (county, zone x structure type, dwelling), whose folders
`01_residential_county`, `02_residential_zone_structure_type` and `03_residential_dwelling` are kept unchanged in
`_superseded_1117/` (their relative paths to `00_shared_data` need one more `../` there). There is no folder 03; the other
folders keep their numbers. The PUMA level uses a crosswalk in which every zone has a PUMA (zones without a 2010 tract
internal point by their centroid) and a market size M = dwelling stock x fixed PUMA turnover rate; density x household type and income and a core-city share
correct the city-vs-suburb bias; see
`01_residential_puma/model/README.md`.

No other SILO model is estimated (the overview table of the estimation document lists these seven).

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
package build scripts, except the PUMA build (01), which needs geopandas: `/opt/homebrew/anaconda3/bin/python3`.
New environment: `python3 -m venv ~/.venvs/biogeme && ~/.venvs/biogeme/bin/pip install biogeme==3.3.5 pyarrow`.

## Run order
02 dwelling before 01 PUMA: the PUMA model uses the dwelling inclusive value (a data column; the provided data hold that of
the reference dwelling model). 04 to 08 are independent. In each folder:

    cd model
    ~/.venvs/biogeme/bin/python estimate_<name>.py --check   # LL at the reference coefficients, writes nothing (01, 02: also --evaluate, --evaluate --holdout)
    ~/.venvs/biogeme/bin/python estimate_<name>.py           # estimation, results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py

## Verification: Biogeme log-likelihood at the article coefficients

| Model | Article LL(beta) | Biogeme, article coefficients (4 decimals) | Biogeme, full-precision estimates |
|---|---|---|---|
| PUMA (weighted) | -32,616.7 | -32,616.6903 | -32,616.6898 |
| Dwelling within the PUMA | -47,478.6 | -47,478.5882 | -47,478.5882 |
| Car ownership | -78,613.6 | -78,613.6202 | -78,613.6191 |
| Workplace | -21,375.7 | -21,375.7428 | -21,375.7397 |
| School K-8 | -2,885.6 | -2,885.6038 | -2,885.6038 |
| School high school | -1,217.0 | -1,216.9605 | -1,216.9605 |
| School college | -1,810.4 | -1,810.3506 | -1,810.3506 |

Hold-out sample, Biogeme at the full-precision estimates: PUMA -8,236.7000, dwelling -11,900.3181 (equal to the original run).
The hold-out half of the residential models had been used before in model development, so its log-likelihood is not a fully
independent test. Test estimations of models 01, 02 and 04 gave the reference coefficients and robust s.e. to 4 decimals; 05 gives the reference LL
and robust s.e. to 4 decimals and coefficients within 0.002 (Biogeme converges slightly further; see its README).
For the weighted model (01) the weight is written inside the log-likelihood so that the robust s.e. are the article's WESML
sandwich; Biogeme's own 'weight' formula (option `--biogeme-weight`) gives the same estimates but other robust s.e.

## Memory and time
Models 01 to 05: under 4 minutes and 5 GB each (01: estimation 26 s, 4.5 GB; its data build 2.5 min, 4 GB). The school models use the full choice set with a location mixture (exact, with
`WeightedLogSumExp`): the LL check takes 9 s (college), 3 min / 6.6 GB (high school) and 35 min / 15.5 GB (K-8). A test estimation of the
previous college model was stopped after 31 min at 8.4 GB (compilation of the analytical Hessian). Estimating the high-school and K-8 models
will need much more time and memory; with the Java runs using most of the memory it is probably not feasible on this machine.
See the school READMEs for derivative settings that may reduce memory.

Update 2026-11-18: school models 06-08 are the final models with the own-race share, the charter-or-magnet share (K-12) and test-score quality (K-8); the K-8 value at the article coefficients is the Biogeme value at 4 decimals, equal to the full-precision value to 4 decimals.
