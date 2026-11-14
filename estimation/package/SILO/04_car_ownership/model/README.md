# Car ownership

Article table: `est_cars`. Number of cars (0, 1, 2, 3+) of a household.

## Model
Multinomial logit, 4 alternatives, 0 cars = reference; every variable has its own coefficient for 1, 2 and 3+ cars.
Data: ACS PUMS 2014-2018 Maryland households, estimation sample 80 % (91,348). Unweighted.

Script: `estimate_car_ownership.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates. Robust standard errors (Biogeme default report).

Special handling:
- Age = age of the oldest member (as the engine computes it), (age - 45)/10 and its square.
- ln income x ln density uses the density centred at the estimation-sample mean 5.485957407613654 (already in the column).

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_car_ownership.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_car_ownership.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `car_ownership_holdout.csv`: hold-out 20 % (22,730 households). Article: hold-out LL -20,219.2 (s08_fit.csv).


## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -80,664.0 |
| Biogeme LL at the article coefficients (4 decimals) | -80664.0051 |
| Biogeme LL at the full-precision estimates of the original run | -80664.0043 |
| N / K | 91348 / 51 |

Memory and time on this machine (64 GB, other jobs running): 4 s and 0.8 GB for --check; estimation a few seconds in a test run (coefficients and robust s.e. equal to the article's to 4 decimals).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.
