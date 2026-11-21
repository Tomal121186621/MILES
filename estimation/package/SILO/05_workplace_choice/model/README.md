# Workplace choice

Table `est_workplace`. Zone of the usual workplace of a worker, given the home zone.

## Model
Multinomial logit over the chosen zone and 99 zones sampled uniformly from the other zones with jobs. Data: RTS 2017/18
workers with a usual workplace outside the home, estimation half (9,707). Unweighted. 24 estimated parameters.

    V_j = (b_t + sum_k c_k (x_k - mean x_k)) t_j + b_l ln(1 + t_j) + b_s same_zone_j + b_c other_county_j + b_o other_state_j
          + b_dc DC_j x (home outside DC) + o1 office_share_j x inc<40k + r retail_share_j x age<30
          + i industrial_share_j x woman + high_wage_share_j (h + h1 inc<40k + h3 inc75-125k + h4 inc125k+)
          + mu ln(jobs_j)

- t: AM-peak car time (min) from the home zone; x_k: woman, age < 30, age 55+, income < 40k, 75-125k, 125k+, driving licence,
  household size, rural home zone, household without a car, each centred at its estimation-half mean (columns `*_c`,
  constants in `centring_constants.csv`).
- Size term: mu ln(total jobs). The script keeps the general form mu ln(RET + exp(g_OFF) OFF + exp(g_IND) IND + exp(g_OTH) OTH)
  with the three job-type log weights fixed at 0 (Beta status 1), so the four job types have equal weights. Bound 0.01 <= mu <= 3
  (not active).

Specification search (same workers, choice sets and hold-out): the size term has equal job-type weights; workplace-area dummies,
the non-work accessibility of the workplace (wrong sign) and time interactions with children and with two or more workers are
not in the model; time x household without a car is. Tested and not kept: transit time for workers without a car (much worse
fit), paid-parking share x car (BIC worse), own-race share of the workplace zone's workers (no effect), time x fewer cars than
workers (not significant), office share x income 125k+ (not significant: -0.14, p = 0.18; LR 1.6, BIC 7.6 lower without it).
Dropping the job-type share x person terms would cost 108 log-likelihood points; they are kept. Step results:
`../input/data/raw/specification_steps_*.csv`.

| K | LL (estimation) | BIC | Hold-out LL (all 1,587 zones) |
|---|---|---|---|
| 24 | -21,376.54 | 42,973.4 | -46,905.49 |

Special handling:
- Sampled alternatives: the exact 100-zone sets of the original estimation (seed 20261106), in the data; no correction term.
- Robust standard errors: the sandwich over the 24 estimated parameters (Biogeme default report). The original estimator also
  counted the three fixed job-type weights in its sandwich, which gave larger s.e. for the terms correlated with them (DC
  workplace, the job-mix and high-wage terms; e.g. retail share x age < 30: 0.2363 instead of 0.1977). `reference_estimates.csv`
  and the estimates table give the corrected s.e. (`../input/data/raw/final_model_estimates.csv`: both).

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_workplace_choice.py --check      # LL at the reference coefficients, writes nothing (--evaluate is the same)
    ~/.venvs/biogeme/bin/python estimate_workplace_choice.py              # estimation; report and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py                 # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `workplace_holdout_workers.csv` (9,749 validation workers) and `zones_with_jobs.csv`: their choice set is all 1,587 zones
with jobs (car times from 00_shared_data/skims); `wdc.Model.holdout_ll` in input/code gives -46,905.49 at the reference
estimates. The hold-out half was also used in the specification search, so its log-likelihood is not a fully independent test.

## Verification (log-likelihood)
| | Value |
|---|---|
| Original run LL(beta) | -21,376.5437 |
| Biogeme LL at the reference coefficients (4 decimals) | -21,376.5448 |
| Biogeme LL at the full-precision estimates of the original run | -21,376.5437 |
| Biogeme estimation, final LL | -21,376.5436 |
| N / K | 9,707 / 24 |

The Biogeme estimation converges a little further than the original optimiser: LL 0.0001 higher, coefficients equal to the
reference within 0.0001 except the job-mix and high-wage share terms (within 0.0006); robust s.e. equal to the reference within
0.0001. Memory and time on this machine: about 15 s for --check; estimation about 45-75 s, 7.6 GB.

If an earlier run left `../output/__workplace_choice.iter`, Biogeme starts from the values saved there; delete it before estimating
a changed specification.

`reference_estimates.csv`: parameter, coefficient, robust s.e., p, full-precision estimate, fit statistics.
