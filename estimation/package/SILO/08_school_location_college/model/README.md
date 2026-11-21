# School location: college

Article table: `est_school` (college panel). School zone of college students given the home zone.

## Model
Multinomial logit over all 141 zones with college enrolment; RTS 2017/18 students with a school record, estimation half (673).
Terms: size term (public 4-year = reference, private 4-year, 2-year), car time, ln(1+t), time x income $125k+, other county, other state, own-race share of the zone's enrolment.

Script: `estimate_school_location_college.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates (4 decimals); `start_values_full_precision.csv` holds the full-precision estimates. Robust standard errors (Biogeme default report).

Special handling:
- Full choice set (no sampling): all zones with enrolment of the segment; an alternative is available when it has enrolment of the student's own band.
- Location mixture: the survey home and school locations can each spread over several model zones (weights w_h, w_c). L_n = sum_h sum_c w_h w_c exp(V_hc) / sum_j av_hj exp(V_hj), written with Biogeme's WeightedLogSumExp (exact).
- Size term mu ln(sum_k exp(g_k) N_k + 1e-12) with the first enrolment component as reference (weight 1), as in the original estimator.
- Variables in single precision, as the original estimator computes them (t, ln(1+t), shares).
- Own-race share: share of the zone's enrolment of the student's band that is of the student's race (white non-Hispanic, Black non-Hispanic,
  Hispanic, other; student race from the RTS person file, which mixes two race codings by region: handled by home county; unknown race: 0).
  Enrolment by race: CCD 2024-25 membership (public), PSS 2023-24 (private), IPEDS EF2023A (college). In SILO the share is recomputed every
  simulated year from the assigned students. It is a composition effect: preference, information, transport and history are not separable.
  Without it the hold-out log-likelihood is -1,938.87 (with it -1,913.52).
- The data are stored in long format (students, alternatives, candidates); the script makes the wide table itself.
- Memory: the estimation compiles the analytical Hessian of the whole expression (JAX). Options that change only how derivatives are computed, not the model (not tested here): in ../output/biogeme.toml set analytical_hessian_mode = "chunked" (with a smaller hessian_memory_fraction), or calculating_second_derivatives = "finite_differences". Run the school models alone, with the Java jobs stopped.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_school_location_college.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_school_location_college.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `*_holdout_*.parquet`: validation half (686 students), same tables. Article: hold-out LL = -1,913.5 (-2.789 per student).

## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -1,810.4 |
| Original estimator, final model | -1810.3506 |
| Biogeme LL at the article coefficients (4 decimals) | -1810.3506 |
| Biogeme LL at the full-precision estimates of the original run | -1810.3506 |
| N / K | 673 / 9 |
| LL(0), rho2, AIC, BIC | -3,330.5, 0.456, 3,638.7, 3,679.3 |

Memory and time on this machine (48 GB): 9 s and 1.4 GB for --check. Estimation not run here (a test estimation of the previous college model was stopped after 31 min at 8.4 GB).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics; rows without
a parameter are terms not in the model or fixed at 0.

## Specification search
Blocks were added on the estimation half when their likelihood-ratio test was significant at 5 %, they lowered the BIC and their
sign was as expected. The hold-out half was also used during the specification search, so its fit is not an independent test.
Logs: `../input/data/raw/l10_school_college.log` (final sequence) and `l09_school_college.log` (earlier tests).

| K | LL | BIC | Hold-out LL |
|---|---|---|---|
| 9 | -1,810.4 | 3,679.3 | -1,913.5 |

Removed in the search: time x income < $40k (BIC). Added: own-race share.

Dormitory students (tested, not kept). 16% of the Maryland college enrolment lives in dormitories (IPEDS IC2023 dormitory capacity;
23% public 4-year, 21% private 4-year, 0.6% 2-year; `00_shared_data/school_choice_work/school_dorm_share_md.csv`).
- Size from commuting enrolment (enrolment - dormitory capacity): LL -1,859.1 against -1,831.0, hold-out -1,965.8 against -1,938.9.
- Separate size component for the dormitory part: log weight -0.18 (t -0.4); with the own-race share -0.44 (t -0.9), not significant.
The size term is total enrolment. The survey samples households, so dormitory residents are not in the data; SILO has no group quarters.
