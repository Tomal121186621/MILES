# School location: college

Article table: `est_school (column college)`. Zone of the college or university of students given the home zone.

## Model
Multinomial logit over all 141 zones with college enrolment; RTS 2017/18 students with a school record, estimation half (673).

Script: `estimate_school_location_college.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
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
    ~/.venvs/biogeme/bin/python estimate_school_location_college.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_school_location_college.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `*_holdout_*.parquet`: validation half (686 students). Article: validation LL = -1,937.0.


## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -1,827.8 |
| Biogeme LL at the article coefficients (4 decimals) | -1827.7888 |
| Biogeme LL at the full-precision estimates of the original run | -1827.7886 |
| N / K | 673 / 9 |

Memory and time on this machine (64 GB, other jobs running): 20 s and 1.05 GB for --check; estimation a test run was stopped after 31 min at 8.4 GB (compilation of the analytical Hessian) without finishing.

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.
