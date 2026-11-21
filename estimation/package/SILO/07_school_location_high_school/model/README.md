# School location: high school

Article table: `est_school` (high school panel). School zone of high school students given the home zone.

## Model
Multinomial logit over all 719 zones with high school enrolment; RTS 2017/18 students with a school record, estimation half (668).
Terms: size term (public enrolment outside the attendance boundary = reference, in-boundary public; private enrolment with log weight fixed at 0, i.e. weight 1), car time, other county x public share, charter-or-magnet share, own-race share of the zone's enrolment.

Script: `estimate_school_location_high_school.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
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
  Without it the hold-out log-likelihood is -1,227.63 (with it -1,207.53).
- Charter-or-magnet share: charter flag CCD 2024-25 directory, magnet flag CCD 2017-18 school characteristics.
- The data are stored in long format (students, alternatives, candidates); the script makes the wide table itself.
- Memory: the estimation compiles the analytical Hessian of the whole expression (JAX). Options that change only how derivatives are computed, not the model (not tested here): in ../output/biogeme.toml set analytical_hessian_mode = "chunked" (with a smaller hessian_memory_fraction), or calculating_second_derivatives = "finite_differences". Run the school models alone, with the Java jobs stopped.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_school_location_high_school.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_school_location_high_school.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `*_holdout_*.parquet`: validation half (667 students), same tables. Article: hold-out LL = -1,207.5 (-1.810 per student).

## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -1,217.0 |
| Original estimator, final model | -1216.9605 |
| Biogeme LL at the article coefficients (4 decimals) | -1216.9605 |
| Biogeme LL at the full-precision estimates of the original run | -1216.9605 |
| N / K | 668 / 6 |
| LL(0), rho2, AIC, BIC | -4,394.0, 0.723, 2,445.9, 2,472.9 |

Memory and time on this machine (48 GB): 191 s and 6.6 GB for --check. Estimation not run here (expect hours and more memory than the check).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics; rows without
a parameter are terms not in the model or fixed at 0.

## Specification search
Blocks were added on the estimation half when their likelihood-ratio test was significant at 5 %, they lowered the BIC and their
sign was as expected. The hold-out half was also used during the specification search, so its fit is not an independent test.
Logs: `../input/data/raw/l10_school_hs.log` (final sequence) and `l09_school_hs.log` (earlier tests).

| K | LL | BIC | Hold-out LL |
|---|---|---|---|
| 6 | -1,217.0 | 2,472.9 | -1,207.5 |

Private log weight fixed at 0 (p = 0.37). Added: charter-or-magnet share, own-race share.

Tested and not kept:
- Quality of the public part and share without a score: with the private log weight fixed at 0, K 7, LL -1,231.1, LR p = 0.056;
  with it free, K 8, LL -1,224.4, quality 0.203 (t 3.2), BIC 2,500.8, 0.4 above the model without quality (2,500.4).
- Separate charter and magnet shares: BIC 2,505.4 against 2,500.2 for one share.
- A quality form at the zone level (with City in-boundary enrolment counted as ordinary public enrolment) lowered the BIC
  from 2,500.2 to 2,498.5; both K-12 models use the public-part form, which does not pass here.
- Baltimore City (about 22 City students in the estimation half): in-boundary log weight x City home -1.23 (t -0.9, LR p = 0.25);
  City in-boundary enrolment counted as ordinary public enrolment: LL -1,243.4 against -1,243.6, BIC change 0.4. Neither is kept.
