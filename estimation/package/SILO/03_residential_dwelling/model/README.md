# Residential location: dwelling

Article table: `est_dwelling`. Lower level of the residential location model: which dwelling a moving household chooses within its destination PUMA.

## Model
Multinomial logit over the mover's own dwelling and 29 dwellings sampled uniformly from the dwellings of the same PUMA
occupied by households that moved in within 12 months. Data: ACS PUMS movers 2014-2018, estimation sample (15,163). Unweighted.

Script: `estimate_residential_dwelling.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates. Robust standard errors (Biogeme default report).

Special handling:
- Sampled alternatives: the exact 30-dwelling sets of the original estimation (generator seed 20261022, first draw), in the data; uniform sampling, no correction term.
- Structure type SFD is the reference; age band 35-49 of the oldest member is the reference of the age interactions.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_residential_dwelling.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_residential_dwelling.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `dwelling_holdout.parquet`: validation movers (3,820) with their 30-dwelling sets (second draw of the same generator). Article: validation LL = -11,923.5.


## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -47,688.2 |
| Biogeme LL at the article coefficients (4 decimals) | -47688.1973 |
| Biogeme LL at the full-precision estimates of the original run | -47688.1973 |
| N / K | 15163 / 38 |

Memory and time on this machine (64 GB, other jobs running): 6 s and 1.4 GB for --check; estimation about 50 s in a test run (coefficients and robust s.e. equal to the article's to 4 decimals).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.
