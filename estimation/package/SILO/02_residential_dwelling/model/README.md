# Residential location: dwelling within the PUMA

Table `est_resloc_dwelling`. Lower level of the two-level residential location model: which dwelling a moving household
chooses within its destination PUMA. The upper level (`../../01_residential_puma`) reads its inclusive value.

## Model
Multinomial logit over the mover's own dwelling (alternative 0) and 29 dwellings drawn uniformly, without replacement, from the
dwellings of the same PUMA occupied by households that moved in within 12 months (ACS PUMS 2014-2018; the mover's own record
excluded). Data: ACS PUMS movers 2014-2018, estimation sample (15,163). Unweighted. No location term: within a PUMA the choice
depends on the dwelling and its price.

    V_d = (b1 + b2 lninc) over30_d + (b3 + b4 lninc) ln(cost_d) + (b5 + b6 lninc) short_d + (b7 + b8 lninc) excess_d
          + (b9 + b10 lninc) new5_d + sum_t (a_t + c_t lninc) type_{t,d}

- lninc = ln(max(income, 5000) / 50000), income in 2016 $.
- Affordability, over30 = max(0, 12 x cost / income - 0.30), with the share 12 x cost / income capped at 3: the housing cost
  burden above the 30 % threshold. The 30 % line is the standard housing-cost-burden threshold (HUD, Census Bureau), fixed,
  not estimated.
- Quality, ln cost = ln(max(monthly cost, 100)): the price signal of dwelling quality; it stands for dwelling characteristics
  reflected in price but not observed in the data (no direct quality measure).
- Monthly cost = gross rent (GRNTP) for renters, selected monthly owner costs (SMOCP) for owners, x ADJHSG, in 2016 $ (the
  definition of monthlyCost of the synthetic dwellings); income = household income in 2016 $, at least 5,000.
- short / excess = bedrooms below / above the need, min(household size, 5). The rule is an assumption chosen by fit (table below).
- new5 = built in the last 5 years (year built against the survey year).
- type_t: single-family attached, multi-family 2-4, multi-family 5+, mobile home (reference single-family detached).

## The two cost terms
- Without the quality term the model chooses dwellings that are too cheap: predicted mean cost of the chosen dwelling $1,539
  against $1,645 observed ($1,643 with the term); the LL falls by 398 (hold-out by 150).
- Correlation: within-choice-set correlation of the two terms +0.51; VIF ln cost 2.1, cost above 30 % 6.6 (mostly from its own
  income interaction, r = -0.87 by construction). The terms are identified because 57 % of the compared dwellings are below
  30 % of income (affordability term 0) and the share above 30 % differs by income: 87 % of the compared dwellings for incomes
  under $40k, 51 % for $40-75k, 19 % for $75-125k, 3 % for $125k+.
- Limitation: tenure is not modelled (SILO's population has no tenure); owners and renters share one market. An information
  test with owner-specific cost terms (the four cost terms x owner) raises the LL by 124 (hold-out by 52); owners accept higher
  cost shares (slope above 30 %: -2.49 against -5.14 for renters, at $50k).

## Bedroom need: rule chosen by fit
| Rule | LL (estimation) | Hold-out LL |
|---|---|---|
| 1 for one person, else household size - 1, at most 4 | -47,946.2 | -11,990.1 |
| two persons per bedroom | -48,306.5 | -12,075.9 |
| one bedroom per person, at most 5 (used) | -47,478.6 | -11,900.3 |
| no rule: bedrooms, x size, squared, x ln income | -47,529.3 | -11,928.2 (VIF 11.7) |

The hold-out sample was also used to choose the rule.

Script: `estimate_residential_dwelling.py` (Biogeme 3.3.5); start values are the reference estimates (4 decimals). Robust
standard errors (Biogeme default report).

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_residential_dwelling.py --evaluate             # LL at the reference coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_residential_dwelling.py --evaluate --holdout   # same, hold-out sample
    ~/.venvs/biogeme/bin/python estimate_residential_dwelling.py                        # estimation; report and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py                               # your estimates against reference_estimates.csv

`--evaluate --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run
(`--check` is the same as `--evaluate`). Data: `../input/data/estimation` (dictionary `data_dictionary.csv`); rebuild with
`../input/code/build_estimation_data.py`. Hold-out: `../input/data/holdout/dwelling_holdout.parquet`, the validation movers
(3,820) with their 30-dwelling sets (drawn after those of the estimation sample, same generator).

## Verification (log-likelihood)
| | Estimation sample | Hold-out sample |
|---|---|---|
| Original run | -47,478.5882 | -11,900.3181 |
| Biogeme at the reference coefficients (4 decimals) | -47,478.5882 | -11,900.3088 |
| Biogeme at the full-precision estimates | -47,478.5882 | -11,900.3181 |
| N / K | 15,163 / 18 | 3,820 |

LL(0) = -51,572.4 (equal shares of the 30 alternatives). A Biogeme estimation (15 s, 3.3 GB) gives the reference coefficients
and robust s.e. to 4 decimals. The hold-out sample was also used in the specification search, so its log-likelihood is
not a fully independent test.

`reference_estimates.csv`: parameter, section and label of the estimates table, coefficient, robust s.e., p (two-sided,
normal), full-precision estimate, fit statistics.

## Choice set and sample-size sensitivity
Choice set: the mover's dwelling plus 29 dwellings drawn uniformly at random from the PUMA's market of movers' dwellings (30
alternatives). A uniform draw gives consistent MNL estimates and costs only precision (McFadden 1978). In SILO the household sees
30 vacant dwellings drawn at random in the chosen PUMA (all if fewer). The inclusive value of the PUMA level is the ln of the mean of
exp(V) of this level over 200 dwellings drawn at random from the PUMA's market (the ln market size enters the PUMA level as its own term).

Sensitivity (estimation half, both levels re-estimated): a second random draw of 30, 60 and 100 alternatives; each draw also redraws
the 200 dwellings of the inclusive value. Largest change of a coefficient against the estimate with 30 alternatives, in its robust s.e.:

| Level (parameters) | 30, second draw | 60 | 100 |
|---|---|---|---|
| Dwelling (18) | 0.67 (built in the last 5 years) | 0.50 | 0.56 |
| PUMA (14) | 0.28 | 0.34 | 0.28 |

30 alternatives are enough. The dwelling-level LL values differ between the cases because the choice sets differ in size; they are
not a comparison of fit. Full table (all 32 terms): `../output/sample_size_sensitivity_table.csv`; outputs of the run:
`../output/sample_size_coef.csv` (level, param, coef, robust_se, case, diff_in_se) and `sample_size_fit.csv`. Script:
`sample_size_check.py`, a copy of the project script (`side_experiments/respec_2026-11/step_by_step/residential/`); it imports the
project's estimator and runs in that folder, not in this package. Its reference run (30 alternatives) re-estimates the PUMA level
with its own draw of the 200 inclusive-value dwellings, so its PUMA coefficients differ slightly from the article (e.g. ln market
size 0.846 against 0.840).
