# Residential location: PUMA of moving households

Table `est_resloc_puma`. Upper level of the two-level residential location model: which PUMA a moving household chooses.
The lower level is the dwelling within the PUMA (`../../02_residential_dwelling`); it enters through its inclusive value.

## Model
Multinomial logit over the PUMAs of the zone-system area (no sampling). Data: ACS PUMS movers 2014-2018, estimation sample.
The PUMS records the destination PUMA exactly and the origin only as a migration PUMA (MIGPUMA), a group of whole PUMAs
(Maryland has 16, 8 of them a single PUMA); the origin terms are expectations over the PUMAs of that area.

    U_p = IV_p + b1 ln M_p + b2 d2_p + b3 d3_p + b4 same_p + b5 adjacent_p + b6 same_state_p + b7 commute_p
          + b8 crime_p x children + b9 lnddens_p + b10 own_race_p
          + b11 lnddens_p x single + b12 lnddens_p x young + b13 lnddens_p x ln income + b14 core_p

- IV_p: inclusive value of the dwelling level, ln of the mean of exp(V_d) over 200 dwellings drawn from the PUMA's market
  (fixed seed), V_d from the dwelling-level estimates. Coefficient held at 1 (in the specification search the free estimate, 1.43,
  was above the nested-logit bound), so the two levels are one logit over all dwellings of the area.
- ln M_p, a separate term: M_p = r_p x dwellings of the PUMA (occupied and vacant), with the fixed turnover rate r_p = weighted PUMS
  dwellings (WGTP) whose household moved in within 12 months x the PUMA's share of housing units in the zone system / the PUMA's
  2016 dwellings. In estimation M_p is the PUMS movers' dwellings x coverage; in the simulation it changes only with construction
  and demolition. `../input/data/estimation/market.csv` gives M_p, r_p and the 2016 dwellings.
- d2, d3: AM-peak car time t from the previous home to the PUMA (origin migration area and PUMA zones weighted by 2016
  dwellings; a zone split between PUMAs by its housing units), times (1 - same): per minute between 20 and 60 min, and above 60 min; no slope below 20 min.
- same: share of the dwellings of the previous migration area in the PUMA's zones (1 when the migration area is one PUMA;
  the same in the simulation, from the migration area of the current home). adjacent: share in PUMAs bordering the PUMA, times (1 - same). same_state: the
  PUMA is in the state lived in a year earlier.
- commute: sum over the household's workers of ln(1 + T), T the time (min) from the PUMA to the jobs of the worker's
  place-of-work PUMA (jobs-weighted): car time, transit door-to-door time (at most 180 min) for households without a car.
- crime x children: county crime index (index offences per 100,000 relative to Baltimore City), dwelling-weighted over the
  PUMA's zones, for households with a member under 18.
- lnddens: dwelling-weighted mean of the zones' ln(dwellings per acre).
- lnddens x single (household of one person), x young (oldest member under 35), x ln income (ln(max(income, 5000) / 50000),
  2016 $): the density effect for these households. The main density coefficient applies to the reference household
  ($50k, two or more persons, oldest member 35 or older).
- core: core-city share of the PUMA, the share of its dwellings (same zone weights as the other attributes) in DC or Baltimore
  City. Added, with the three density interactions, because the model without them under-predicted moves into DC and
  Baltimore City and over-predicted the suburbs on the estimation half. Tested and not kept: transit accessibility of the PUMA
  (negative sign, VIF near 10), multifamily share, car time to the nearest downtown, density x children and x 65+ (higher
  BIC). Fairfax (VA) remains over-predicted by about 2 percentage points.
- own_race: share of the PUMA's 2016 households whose householder race category (white, Black, Hispanic, other: the
  categories of the synthetic population) equals that of the mover's householder. In the simulation it is recomputed every year from the current
  households.
- Weight: dest_cov x orig_cov (expected in-area share of destination and origin) divided by its mean, written inside the
  log-likelihood (w ln P): the robust s.e. are the WESML sandwich of the original estimator. `--biogeme-weight` uses Biogeme's
  `weight` formula instead (same estimates, other robust s.e.).

Race is included by the author's decision. The own-race term measures a composition effect: households move more often to
PUMAs where their own group lives; preference, discrimination, steering and history cannot be separated with these data. No
other model of the chain uses race.

Geography: zones are linked to PUMAs and migration PUMAs by the 2010 tracts whose internal points they contain; the 252 zones
that contain none belong to the PUMA and migration PUMA of their centroid (`00_shared_data/resloc_work/geo_*_zone_all.csv`,
built by `../input/code/crosswalk.py`; weight: the zone's 2016 dwellings, jobs for workplaces). Zones whose crosswalk housing
units are all 0 get weight 0. All 97 PUMAs are available to every record and no mover is dropped (N = 15,163; hold-out 3,820).

## Run
Run `02_residential_dwelling` first only if you want the inclusive values of your own dwelling estimates (rebuild with
`DWELLING_ESTIMATES=...`, see `../input/code/README.md`); the shipped data hold those of the reference dwelling model.

    cd model
    ~/.venvs/biogeme/bin/python estimate_residential_puma.py --evaluate             # LL at the reference coefficients, writes nothing
    ~/.venvs/biogeme/bin/python estimate_residential_puma.py --evaluate --holdout   # same, hold-out sample
    ~/.venvs/biogeme/bin/python estimate_residential_puma.py                        # estimation; report and <name>_estimates.csv in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py

`--evaluate --start start_values_full_precision.csv` evaluates the LL at the full-precision estimates (`--check` is the same
as `--evaluate`). Data: `../input/data/estimation/puma_estimation.parquet` (index of the PUMAs `puma_index.csv`, dictionary
`data_dictionary.csv`); hold-out `../input/data/holdout/puma_holdout.parquet` (weight 1: the hold-out LL is unweighted).

## Verification (log-likelihood)
| | Estimation sample (weighted) | Hold-out sample (unweighted) |
|---|---|---|
| Original run | -34,670.3212 | -8,773.1592 |
| Biogeme at the reference coefficients (4 decimals) | -34,670.3308 | -8,773.1653 |
| Biogeme at the full-precision estimates | -34,670.3212 | -8,773.1592 |
| N / K | 15,163 / 14 | 3,820 |

LL(0) = -69,366.3 (equal shares of the 97 PUMAs). A Biogeme estimation (42 s) gives LL -34,670.32 and the reference
coefficients within 0.0001 and robust s.e. within 0.00005. The hold-out sample was also used in the specification search, so its log-likelihood is not a fully independent test.

## Robustness: the same model without the own-race share
`../input/data/raw/original_estimates_without_race.csv`, `original_fit_without_race.csv` (dwelling level unchanged).

| | With own-race share | Without |
|---|---|---|
| LL (estimation, weighted) | -34,670.3 | -35,439.4 |
| Hold-out LL | -8,773.2 | -8,968.6 |
| Crime index x children | -1.1607 (0.1142) | -0.7974 (0.1092) |
| ln dwelling density | -0.5466 (0.0196) | -0.6176 (0.0193) |
| ln dwelling density x ln income | -0.1153 (0.0105) | -0.1403 (0.0101) |
| ln dwelling density x single | 0.1698 (0.0229) | 0.1482 (0.0224) |
| Car time 20-60 min | -0.0339 | -0.0360 |
| Other terms | | within 3 % |

Omitting the own-race share biases the crime and density terms: crime x children falls by a third and the density terms move by
10-22 %, because they correlate with the racial composition of the PUMAs. The other terms change by at most 6 % (car time
20-60 min).
