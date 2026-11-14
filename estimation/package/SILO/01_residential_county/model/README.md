# Residential location: county of moving households (44 counties)

Article table: `est_region`. Upper level of the residential location model: which county (SILO region) a moving household chooses.

## Model
Multinomial logit over all 44 counties (SILO regions: Maryland counties and county groups of the neighbouring states), upper
level of a sequentially estimated nested logit. Data: ACS PUMS movers 2014-2018, estimation sample (15,163).

Script: `estimate_residential_county.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates. Robust standard errors (Biogeme default report).

Special handling:
- Observed outcome = destination PUMA, which can span several counties. The likelihood is that of the set: log P = log sum_j chosen_set_j exp(V_j) - log sum_j av_j exp(V_j), written with Biogeme's WeightedLogSumExp (exact, not approximated).
- Inclusive values IV_B (zone x structure type) and IV_A (dwelling) enter as data columns, exactly as estimated (computed by r07_county_iv.py with the final zone and dwelling models). Their coefficients are lambda_B and lambda_A.
- Car time under 20 min: coefficient fixed at 0 (Beta status 1); car time applies to counties other than the previous county.
- Weights: expected in-area share of destination and origin, divided by its mean. The weight is written inside the log-likelihood (w ln P) so that the robust s.e. are the WESML sandwich of the article; option --biogeme-weight uses Biogeme's 'weight' formula (same estimates, different robust s.e.).
- Unavailable counties (av = 0) have their variables set to 0 in the data; they never enter the likelihood.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_residential_county.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_residential_county.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `county_holdout.parquet`: validation movers (3,820), same columns. Article: validation LL = -4,027.49 at the estimates.
Dependencies: 03_residential_dwelling (the inclusive value IV_A of the dwelling model is a data column); 02_residential_zone_structure_type (the inclusive value IV_B of the zone x structure-type model is a data column). The data already contain the inclusive values of the published lower-level models.

## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -15,959.4 (weighted) |
| Biogeme LL at the article coefficients (4 decimals) | -15959.4401 |
| Biogeme LL at the full-precision estimates of the original run | -15959.4331 |
| N / K | 15163 / 14 |

Memory and time on this machine (64 GB, other jobs running): 8 s and 1.0 GB for --check; estimation about 45 s in a test run (coefficients and robust s.e. equal to the article's to 4 decimals).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.
