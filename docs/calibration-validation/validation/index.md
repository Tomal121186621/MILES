# Validation

Every stage is tested on data it was neither estimated nor calibrated on. **Verification** compares a model with its
estimation data; **validation** with data used in no estimation or calibration step. Each stage page shows the same
things: headline numbers, the main figure, every comparison in detail, and a scorecard.

| Stage | Tested against | Comparisons | Result |
|---|---|---:|---|
| [Synthetic population](population.md) | ACS PUMS 2014–18, held-out PUMS test split, LODES, travel survey | 31 | <span class="vb ok">25 within</span> <span class="vb close">3 close</span> <span class="vb out">3 outside</span> |
| [Land use](landuse.md) | ACS, Census estimates, JOLTS, permits, county flows; out of sample 2021–24 | 36 | <span class="vb ok">22 within</span> <span class="vb close">8 close</span> <span class="vb out">6 outside</span> |
| [School location](schools.md) | Survey students, ACS enrolment | 8 | <span class="vb ok">1 within</span> <span class="vb close">5 close</span> <span class="vb out">2 outside</span> |
| [Activities](activities.md) | Survey hold-out half; ATUS, ACS 2024, LODES | 43 | <span class="vb ok">21 within</span> <span class="vb close">12 close</span> <span class="vb out">10 outside</span> |
| [Traffic](traffic.md) | 2,308 count stations, 21 continuous counters, 7 screenlines, mileage | — | model ÷ count 0.81 (passenger vehicles), R² 0.90 |

**Within:** a distribution within 5 percentage points (total variation distance) or a rate within 5 % (mean absolute
percentage error) of the observed value, the acceptance limits of the land-use and activity tests. **Close:** within twice
that. **Outside:** beyond. Traffic is compared as a ratio, because the model carries residents only.

## Strategy

Each stage is estimated on one set of data and tested on another:

| Stage | Estimated on | Tested on |
|---|---|---|
| Synthetic population | ACS PUMS 2012–16, 80 % training split by PUMA | 10 % held-out test split; ACS 2014–18 by PUMA |
| Land use | ACS PUMS movers 2014–18; survey estimation half; calibrated on 2017–20 | Movers 2019–21 (out of time); ACS and Census 2021–24 (out of sample) |
| Schools | Survey estimation half | Survey hold-out half; ACS enrolment |
| Activities | Survey estimation half (10,889 households) | Survey hold-out half (10,899 households); chain test on the synthetic population; ATUS, ACS and LODES for 2024 |
| Traffic | Nothing estimated; network from fixed rules | 2024 counts, continuous counters, screenlines, mileage |

The 2017/18 Regional Travel Survey is split at random into two halves by household, stratified by home county and
household size. The hold-out half enters no estimation or calibration step. TASHA was validated on a later survey of
the same region; no later diary exists here, so the hold-out half and the 2024 benchmarks take its place
([details](activities.md#estimation-and-validation-strategy)).

## Design

| Stage | Test | Measure and criterion | Runs |
|---|---|---|---|
| Population | Held-out PUMS test split; ACS by PUMA | SRMSE at the sampling floor | 1 |
| Land use | Calibrated 2017–20, tested 2021–24 | Rates ±5 %; shares ±5 pp | 5 seeds |
| Activities | Survey hold-out half; 2024 benchmarks | Start times within 2 pp per hour | 10 replications |
| Traffic | 2024 counts and continuous counters | %RMSE by volume group (FDOT); GEH < 5 for > 85 % of hourly flows | 5 seeds |

What the misses mean is stated in [Known limitations](../limitations.md).
