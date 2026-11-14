# Workplace choice

Article table: `est_jobchoice`. Zone of the usual workplace of a worker, given the home zone.

## Model
Multinomial logit over the chosen zone and 99 zones sampled uniformly from the other zones with jobs, with a size term
mu ln(RET + exp(g_OFF) OFF + exp(g_IND) IND + exp(g_OTH) OTH) (same nonlinear form as the original estimator). Data: RTS 2017/18
workers with a usual workplace outside the home, estimation half (9,707). Unweighted.

Script: `estimate_workplace_choice.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates. Robust standard errors (Biogeme default report).

Special handling:
- Sampled alternatives: the exact 100-zone sets of the original estimation (seed 20261106), in the data; no correction term.
- Person variables of the car-time interactions are centred at their estimation-half means (columns *_c; constants in centring_constants.csv).
- Bounds as in the original estimator: 0.01 <= mu <= 3, |g| <= 10 (not active).

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_workplace_choice.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_workplace_choice.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `workplace_holdout_workers.csv` (9,749 validation workers) and `zones_with_jobs.csv`: their choice set is all 1,587 zones with jobs (car times from 00_shared_data/skims). Article: validation LL = -46,873.4 (wdc.Model.holdout_ll in input/code).


## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -21,334.3 |
| Biogeme LL at the article coefficients (4 decimals) | -21334.2842 |
| Biogeme LL at the full-precision estimates of the original run | -21334.2822 |
| N / K | 9707 / 36 |

Memory and time on this machine (64 GB, other jobs running): 15 s and 1.7 GB for --check; estimation about 3.5 min in a test run (coefficients and robust s.e. equal to the article's to 4 decimals).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.
