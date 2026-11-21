# School location: K-8

Article table: `est_school` (K-8 panel). School zone of K-8 students given the home zone.

## Model
Multinomial logit over all 1,144 zones with K-8 enrolment; RTS 2017/18 students with a school record, estimation half (1,509).
Terms: size term (public enrolment outside the attendance boundary = reference, in-boundary public, private), car time, ln(1+t), time x no car, same zone, other county x public share, charter-or-magnet share, quality of the public part (per 10 points of % proficient, centred), quality x income < $40k, share of public enrolment without a score, own-race share of the zone's enrolment.

Script: `estimate_school_location_K8.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
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
  Without it the hold-out log-likelihood is -3,016.01 (with it -2,995.83).
- Charter-or-magnet share: charter flag CCD 2024-25 directory, magnet flag CCD 2017-18 school characteristics.
- Quality: school PARCC 2016-17 % proficient (mean of ELA and math; 2018-19 for 13 schools without 2016-17), Maryland public schools only,
  from the EDFacts files of the Urban Institute Education Data Portal; enters as (share of the zone's band enrolment in scored public
  schools) x (enrolment-weighted mean - 38.3) / 10, plus the share of public enrolment without a score. A fixed input in SILO.
- The data are stored in long format (students, alternatives, candidates); the script makes the wide table itself.
- Memory: the estimation compiles the analytical Hessian of the whole expression (JAX). Options that change only how derivatives are computed, not the model (not tested here): in ../output/biogeme.toml set analytical_hessian_mode = "chunked" (with a smaller hessian_memory_fraction), or calculating_second_derivatives = "finite_differences". Run the school models alone, with the Java jobs stopped.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_school_location_K8.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_school_location_K8.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `*_holdout_*.parquet`: validation half (1,534 students), same tables. Article: hold-out LL = -2,995.8 (-1.953 per student).

## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -2,885.6 |
| Original estimator, final model | -2885.6038 |
| Biogeme LL at the article coefficients (4 decimals) | -2885.6038 |
| Biogeme LL at the full-precision estimates of the original run | -2885.6038 |
| N / K | 1509 / 13 |
| LL(0), rho2, AIC, BIC | -10,407.1, 0.723, 5,797.2, 5,866.4 |

Memory and time on this machine (48 GB): 2,088 s (35 min) and 15.5 GB for --check. Estimation not run here (the expression is 4 x 1,144 utilities; expect many hours and well above the 15.5 GB of the check).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics; rows without
a parameter are terms not in the model or fixed at 0.

## Specification search
Blocks were added on the estimation half when their likelihood-ratio test was significant at 5 %, they lowered the BIC and their
sign was as expected. The hold-out half was also used during the specification search, so its fit is not an independent test.
Logs: `../input/data/raw/l10_school_k8.log` (final sequence) and `l09_school_k8.log` (earlier tests).

| K | LL | BIC | Hold-out LL |
|---|---|---|---|
| 13 | -2,885.6 | 5,866.4 | -2,995.8 |

Removed in the search: time x fewer cars than drivers (BIC). Added: charter-or-magnet share, quality of the public part with the
share without a score, quality x income < $40k, own-race share.

Tested and not kept: separate charter and magnet shares (K 10, BIC 5,936.5 against 5,932.3 for one share); a quality form at the zone level
(mean score of the zone's scored schools and a no-score indicator, BIC 5,893.7 against 5,894.6 for the public-part form, which is
used because it gives the private part of the zone no score); quality x income $125k+ (LR p = 0.15).
