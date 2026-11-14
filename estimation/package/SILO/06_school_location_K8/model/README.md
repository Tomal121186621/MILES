# School location: K-8

Article table: `est_school (column K-8)`. School zone of K-8 students given the home zone.

## Model
Multinomial logit over all 1,144 zones with K-8 enrolment; RTS 2017/18 students with a school record, estimation half (1,509).

Script: `estimate_school_location_K8.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates. Robust standard errors (Biogeme default report).

Special handling:
- Full choice set (no sampling): all zones with enrolment of the segment; an alternative is available when it has enrolment of the student's own band.
- Location mixture: the survey home and school locations can each spread over several model zones (weights w_h, w_c). L_n = sum_h sum_c w_h w_c exp(V_hc) / sum_j av_hj exp(V_hj), written with Biogeme's WeightedLogSumExp (exact).
- Size term mu ln(sum_k exp(g_k) N_k + 1e-12) with the first enrolment component as reference (weight 1), as in the original estimator.
- Variables in single precision, as the original estimator computes them (t, ln(1+t), shares).
- The data are stored in long format (students, alternatives, candidates); the script makes the wide table itself.
- Memory: the estimation compiles the analytical Hessian of the whole expression (JAX). Options that change only how derivatives are computed, not the model (not tested here): in ../output/biogeme.toml set analytical_hessian_mode = "chunked" (with a smaller hessian_memory_fraction), or calculating_second_derivatives = "finite_differences". Run the school models alone, with the Java jobs stopped.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_school_location_K8.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_school_location_K8.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `*_holdout_*.parquet`: validation half (1,534 students), same tables. Article: validation LL = -3,041.5.


## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -2,941.0 |
| Biogeme LL at the article coefficients (4 decimals) | -2941.0295 |
| Biogeme LL at the full-precision estimates of the original run | not run (33 min per evaluation); the exported tables reproduce the original estimator to 1e-4 |
| N / K | 1509 / 9 |

Memory and time on this machine (64 GB, other jobs running): 1985 s and 4.2 GB for --check; estimation NOT run: the smallest school model (college) already needed more than 8.4 GB and 31 min without finishing; the K-8 expression is 32 times larger (4 x 1,144 utilities). Expect several hours and tens of GB; probably not feasible on this machine while the Java jobs run.

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.
