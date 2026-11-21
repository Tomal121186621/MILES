# Car ownership

Article table: `est_cars`. Number of cars (0, 1, 2, 3+) of a household.

## Model
Multinomial logit, 4 alternatives, 0 cars = reference; every variable has its own coefficient for 1, 2 and 3+ cars,
except four fixed at 0 (p > 0.3 when estimated): single person for 2 and 3+ cars, ln density for 1 car, age for 3+ cars.
56 parameters. Data: ACS PUMS 2014-2018 Maryland households, estimation sample 80 % (91,348). Unweighted.

Script: `estimate_car_ownership.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates. Robust standard errors (Biogeme default report).

Special handling:
- Age = age of the oldest member (as the engine computes it), (age - 45)/10 and its square.
- ln income x ln density uses the density centred at the estimation-sample mean 5.485957407613654 (already in the column).
- Persons aged 16+ (workers + nonworking_adults) enter as dummies p16_2, p16_3, p16_4p (reference 0-1); nonworking_adults
  itself is not in the model.
- Baltimore City (city = 1 for PUMA 2400801-2400805) has its own term for 1, 2, 3+ cars, estimated with the others. It
  captures whatever makes the City different (transit, parking, history), not a behavioural effect. SILO reads it from
  the region-constants file as region 24510 (all other regions 0): 2_silo/input/car_ownership_coefficients_respec9.csv and
  car_ownership_region_constants_respec9est.csv.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_car_ownership.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_car_ownership.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `car_ownership_holdout.csv`: hold-out 20 % (22,730 households). Article: hold-out LL -19,704.5 (rho2 0.375 against
equal shares). The hold-out sample was also used in the specification search.


## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -78,613.6 |
| Biogeme LL at the article coefficients (4 decimals) | -78613.6202 |
| Biogeme LL at the full-precision estimates of the original run | -78613.6191 |
| Biogeme estimation (start = article values) | -78613.6191; coefficients and robust s.e. within 0.00005 of the article |
| N / K | 91348 / 56 |

Memory and time on this machine (64 GB, other jobs running): 4 s and 0.8 GB for --check; estimation a few seconds.
If output/ holds a `__car_ownership.iter` file from an earlier specification, Biogeme starts from it; remove or rename it first.

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.

## Fit of the model
| K | LL | BIC | Hold-out LL |
|---|---|---|---|
| 56 (4 terms with p > 0.3 fixed at 0) | -78,613.6 | 157,866.9 | -19,704.5 |

Removing income x density lowers the LL by 40 and the hold-out LL by 21; the term is kept.
