# Estimation package

The estimation package lets anyone re-estimate every model of TERP with **Python Biogeme** and check the result
against the published estimates. It lives in `estimation/package/`; the specification search behind each model is in `estimation/development/`.

## Layout

```text
estimation/package/
├── RUN_ORDER.pdf                 which folder to run, in which order
├── SILO/                         land-use, workplace and school models (8)
│   ├── 00_shared_data/           (not in the repository) census microdata, survey, zones, skims
│   ├── 01_residential_county/
│   │   ├── INSTRUCTIONS.pdf      from data download to output, step by step
│   │   ├── 01_residential_county_estimation.ipynb
│   │   ├── input/code/           data preparation scripts
│   │   ├── input/data/raw/       source extracts
│   │   ├── input/data/estimation/  the estimation table and its data dictionary
│   │   ├── input/data/holdout/   hold-out sample
│   │   ├── model/                Biogeme script, published estimates
│   │   └── output/               your results
│   └── ...
├── ABIT/                         TERP-Day: distributions and 20 models
│   ├── 00_tasha_distributions/   activity distributions (not a Biogeme model)
│   ├── 01_primary_destination_pooled/
│   └── ...
└── tools/                        notebook and instruction builders
```

## The models

| Folder | Model |
|---|---|
| SILO/01 | Residential location: county |
| SILO/02 | Residential location: zone × structure type |
| SILO/03 | Residential location: dwelling |
| SILO/04 | Car ownership |
| SILO/05 | Workplace choice |
| SILO/06–08 | School location: K–8, high school, college |
| ABIT/00 | Activity distributions (frequency, start, duration, joint) |
| ABIT/01 | Main destination, four purposes pooled |
| ABIT/02–05 | Stops: shopping, recreation, accompanying, other errands |
| ABIT/06 | Outing from the workplace: first stop |
| ABIT/07–08 | Work business: usual-workplace workers; other persons |
| ABIT/09 | Work trips of home workers |
| ABIT/10 | School without record and daycare, pooled |
| ABIT/11–13 | Outing generation, outing mode, return home |
| ABIT/14–19 | Tour mode: work, school, shopping, other, joint shopping, joint other |
| ABIT/20 | Transit leg mode |

## The notebooks

Every model folder has a notebook, `<folder>_estimation.ipynb`, that runs from the raw data to the estimates:

1. Raw data and where to download it
2. Data preparation steps
3. The estimation table and its data dictionary
4. Descriptive statistics and choice shares
5. Correlation heatmaps and variance inflation factors of the variables in the utilities
6. The model specification (the folder's Biogeme script, unchanged)
7. Log-likelihood at the published coefficients
8. Biogeme estimation
9. Estimates in the published format, fit, comparison with the published values, correlation of the estimates
10. Hold-out log-likelihood

Open a notebook in VS Code, select the kernel *Python (biogeme)* and run all cells. Switches at the top choose what is
recomputed; the largest models (schools, stops, the location models) default to reading saved results, because
their estimation needs more memory than a laptop has.

## From the command line

```bash
cd estimation/package/SILO
./run_model.sh 04_car_ownership     # check, estimate, compare; log in 04_car_ownership/output/run_log.txt
./run_all.sh                        # all SILO models in order
```

## Data

The repository holds the scripts, notebooks and published estimates of every model, but not the estimation tables:
they are built from the census microdata and the travel survey by each folder's `input/code` scripts. Each folder's
`INSTRUCTIONS.pdf` lists the downloads, from raw data to estimates.

## How estimates reach the engines

| Estimation output | Engine file |
|---|---|
| Residential location, car ownership, workplace, schools | `landuse/engine_inputs/`, `landuse/schools/parameters/` (via `landuse/coefficients/write_residential_location.py`–`e04`) |
| Tour mode choice | `activity/parameters/tour_mode_choice.csv` |
| Destinations and stops | `activity/parameters/dest_choice_mnl.csv` |
| Return home, outings | `activity/parameters/tasha/tasha_return_home.csv`, `tasha_subtour.csv` |
| Activity distributions | `activity/parameters/tasha/tasha_frequency.csv`, `tasha_start.csv`, `tasha_duration.csv` |

`activity/build_parameters.py` writes the activity files and `TERM_MAP.csv`, which maps all 699 estimated terms to
their engine file and variable.
