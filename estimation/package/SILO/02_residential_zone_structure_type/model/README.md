# Residential location: zone x structure type

Article table: `est_zone`. Middle level of the residential location model: which zone x structure-type cell a household lives in within its county.

## Model
Multinomial logit over the observed cell and 29 cells sampled uniformly from the cells of the household's county (zones with
dwellings of that structure type). Data: RTS 2017/18 households with the age of their members, estimation half (10,655).

Script: `estimate_residential_zone_structure_type.py` (Biogeme 3.3.5). Parameters are named after the article rows; start values are the article
estimates. Robust standard errors (Biogeme default report).

Special handling:
- Sampled alternatives: the exact 30-cell sets of the original estimation (generator seed 1022, first draw), in the data; uniform sampling, no correction term.
- Weights: RTS household weight / its mean (WESML), written inside the log-likelihood so that the robust s.e. are the article's WESML sandwich; option --biogeme-weight uses Biogeme's 'weight' formula. LL values are weighted.
- Accessibility: multimodal non-work logsum of the household's segment (accessibility_2016_new_multimodal.csv).
- Households with fewer than 30 cells in their county have av = 0 for the missing alternatives.

## Run
    cd model
    ~/.venvs/biogeme/bin/python estimate_residential_zone_structure_type.py --check      # LL at the article coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_residential_zone_structure_type.py              # estimation; report, pickle/yaml and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py  # your estimates against reference_estimates.csv

`--check --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates of the original run.
Data: `../input/data/estimation` (dictionary: `data_dictionary.csv`); rebuild with `../input/code/build_estimation_data.py`.
Hold-out: `zone_holdout_fullset.parquet`: validation half, full choice set (all cells of the county), long format, unweighted. Article: LL = -49,873.8 at the estimates.


## Verification (log-likelihood)
| | Value |
|---|---|
| Article LL(beta) | -28,089.7 (weighted) |
| Biogeme LL at the article coefficients (4 decimals) | -28089.7213 |
| Biogeme LL at the full-precision estimates of the original run | -28089.7212 |
| N / K | 10655 / 15 |

Memory and time on this machine (64 GB, other jobs running): 8 s and 0.7 GB for --check; estimation about 15 s in a test run (coefficients and robust s.e. equal to the article's to 4 decimals).

`reference_estimates.csv`: parameter, article coefficient, robust s.e., p, full-precision estimate, article fit statistics.
