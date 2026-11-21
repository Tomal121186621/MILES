# Validation

Every stage is tested on data it was neither estimated nor calibrated on. Following Roorda, Miller and Habib (2008),
**verification** compares a model with the data it was estimated on and **validation** with data used in no estimation
or calibration step. Each stage page shows the headline numbers, the main figure and every comparison in detail.

| Stage | Tested against |
|---|---|
| [Synthetic population](population.md) | ACS PUMS 2014–18, held-out PUMS test split, travel survey |
| [Land use](landuse.md) | ACS, Census estimates, JOLTS, permits, county flows; out of sample 2021–24 |
| [School location](schools.md) | Survey students, ACS enrolment |
| [Activities](activities.md) | Survey hold-out half; ATUS, ACS 2024, LODES |
| [Traffic](traffic.md) | MDOT SHA 2024 counts, TMAS continuous counts, screenlines, MDOT SHA mileage |
| [County view](county.md) | Synthetic population by county, all 24 Maryland counties |

Traffic is compared as a ratio, because the assignment carries residents only: simulated passenger-vehicle volumes are
0.81 of the 2024 counts at 2,308 mainline stations (R² 0.90 across stations).

## Strategy

Each stage is estimated on one set of data and tested on another:

| Stage | Estimated on | Tested on |
|---|---|---|
| Synthetic population | ACS PUMS 2012–16, training split | Held-out test split; ACS 2014–18, Maryland and 96 PUMAs |
| Land use | ACS PUMS movers 2014–18 and households; survey estimation half; calibrated on 2017–20 | Held-out PUMS movers; ACS and Census 2021–24 (out of sample) |
| Schools | Survey estimation half | Survey hold-out half; ACS enrolment |
| Activities | Survey estimation half (10,889 households) | Survey hold-out half (10,899 households); chain test on the synthetic population; ATUS, ACS and LODES for 2024 |
| Traffic | Nothing estimated; network from fixed rules | 2024 counts, continuous counters, screenlines, mileage |

The 2017/18 Regional Travel Survey is split at random into two halves by household, stratified by home county and
household size. The hold-out half enters no estimation or calibration step. TASHA was validated on a later survey of
the same region; no later diary exists here, so the hold-out half and the 2024 benchmarks take its place
([details](activities.md#estimation-and-validation-strategy)).

## Measures and criteria

| Stage | Measure | Criterion (source) | Runs |
|---|---|---|---|
| Population synthesis | Marginals and joint tables against the PUMS test split | SRMSE at the sampling floor (own) | 1 |
| Land use, consistency | County population; employment; vacancies; construction | Imposed; county population ±2 % (own) | 5 seeds |
| Land use, tests | Event rates; household size; car ownership; moves and mover flows; commuting | Rates ±5 %; shares ±5 pp (own) | 5 seeds |
| Location choice | Hold-out log-likelihood; trip-length distribution (KS); shares by area | KS below its 5 % critical value; mean within 5 % (FHWA, 2010) | – |
| Activities | Activities by purpose; start-time and duration profiles (KS on hourly values); trips per chain | Start times within 2 pp per hour (Roorda et al., 2008) | 10 replications |
| Assignment | AAWDT by facility and volume group; hourly counts | %RMSE by volume group (FDOT, 2008; Wegmann, 2016); GEH < 5 for > 85 % of flows (DfT) | 5 seeds |

Own: threshold chosen for this study where no published guideline exists. SRMSE: standardised root-mean-square error;
KS: Kolmogorov–Smirnov distance; pp: percentage points; GEH: Geoffrey E. Havers statistic of hourly flows. Location
choice is tested on the survey hold-out half, which involves no simulation.

The land-use results are the mean and range of five seeds. The activity model is run with ten replications on each
population; for 2024 on the land-use seed closest to the mean of the five, with a 10 % household sample, and the
assignment receives the replication closest to the mean.

What the differences mean is stated in [Known limitations](../limitations.md).
