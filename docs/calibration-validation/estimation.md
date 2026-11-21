# Estimation

## Common design

- **Sample.** All survey-based models are estimated on the estimation half of the travel survey; the land-use models
  of residential location and car ownership on ACS PUMS households.
- **Weights.** The survey is stratified by home location, which every model except residential location takes as
  given, so these models are estimated without weights. Weights are used only where the sample is selected on the
  outcome: the PUMA level of residential location (whose sample is selected on origin and destination inside the
  zone-system area) and the work tour mode choice (whose sample over-represents rail commuters; weighted exogenous
  sample maximum likelihood).
- **Location probabilities.** A survey location known by traffic zone or tract may cover several model zones; its
  probability is the sum of the probabilities of those zones, weighted by housing units, enrolment or jobs.
- **Choice sets.** School and activity-location models use the full choice set of 1,588 zones; workplace choice the
  chosen zone and 99 sampled zones; the PUMA level of residential location all 97 PUMAs, and the dwelling level 30
  sampled alternatives.
- **Specification search.** Each model is built in blocks of variables from a basic model. A block is kept when its
  likelihood-ratio test is significant at 5 %, it lowers the BIC and its signs are as expected; non-nested forms are
  compared by BIC.
- **Standard errors** are robust (sandwich).
- **Hold-out.** The hold-out half was consulted more than once in the specification search of several models, so its
  fit is not a fully independent test.
- **Software:** Python Biogeme for every model of the estimation package.

## All estimated models

The full results of every model, coefficient by coefficient, are in [Estimated models](estimates/index.md).

\(N\): observations; \(K\): parameters; LL: log-likelihood at the estimates; \(\bar\rho^2\): adjusted rho-square.
Hold-out: log-likelihood per mover (residential location), \(\rho^2\) (car ownership), log-likelihood per record
(workplace, schools, locations) or total log-likelihood (tour formation and mode) on held-out data.

| Model (alternatives) | \(N\) | \(K\) | LL | \(\bar\rho^2\) | Hold-out |
|---|---:|---:|---:|---:|---:|
| ***Land use and workplace*** | | | | | |
| Residential location: PUMA (97)<sup>1</sup> | 15,163 | 14 | −34,670.3 | 0.500 | −2.297 |
| Residential location: dwelling (30 sampled) | 15,163 | 18 | −47,478.6 | 0.079 | −3.115 |
| Car ownership (4) | 91,348 | 56 | −78,613.6 | 0.379 | 0.375 |
| Workplace (100 sampled) | 9,707 | 24 | −21,376.5 | 0.521 | −4.811<sup>2</sup> |
| ***Schools (full choice set)*** | | | | | |
| K–8 (1,144 zones) | 1,509 | 13 | −2,885.6 | 0.721 | −1.953 |
| High school (719 zones) | 668 | 6 | −1,217.0 | 0.722 | −1.810 |
| College (141 zones) | 673 | 9 | −1,810.4 | 0.454 | −2.789 |
| ***MAST: locations (1,588 zones)*** | | | | | |
| Main activity, four purposes (pooled) | 14,341 | 62 | −49,427.4 | 0.532 | −3.370 |
| Stop: shopping | 3,979 | 23 | −9,982.6 | 0.659 | −2.527 |
| Stop: recreation | 5,064 | 20 | −15,874.9 | 0.574 | −3.205 |
| Stop: accompanying | 3,515 | 22 | −12,488.1 | 0.517 | −3.396 |
| Stop: other errands | 8,055 | 20 | −24,653.3 | 0.584 | −3.028 |
| Outing from the workplace: first stop | 1,180 | 10 | −3,112.3 | 0.663 | −2.707 |
| Work business: usual-workplace workers | 1,539 | 18 | −8,432.1 | 0.310 | −5.554 |
| Work business: other persons | 1,259 | 16 | −6,819.3 | 0.292 | −5.625 |
| Work trips of home workers | 366 | 5 | −1,640.9 | 0.430 | −4.389 |
| School without record; daycare (pooled) | 846 | 9 | −3,798.5 | 0.440 | −4.396 |
| ***MAST: tour formation and mode*** | | | | | |
| Outing from the workplace (2) | 8,613 | 8 | −3,061.5 | 0.486 | −3,093.2 |
| Mode of the outing (2) | 1,177 | 7 | −360.6 | 0.549 | −299.8 |
| Return home (2) | 28,349 | 33 | −13,697.0 | 0.301 | −13,771.8 |
| Tour mode: work (6)<sup>3</sup> | 9,126 | 51 | −4,313.1 | 0.626 | −4,284.0 |
| Tour mode: school (6) | 2,651 | 34 | −972.5 | 0.651 | −1,096.5 |
| Tour mode: shopping (6) | 3,206 | 44 | −1,150.2 | 0.713 | −1,107.0 |
| Tour mode: other (6, nested) | 10,405 | 57 | −4,916.7 | 0.623 | −5,049.8 |
| Joint shopping (5) | 452 | 15 | −112.8 | 0.780 | −94.0 |
| Joint recreation and other (6) | 1,296 | 25 | −450.3 | 0.710 | −459.1 |
| Transit-tour legs (5)<sup>4</sup> | 6,773 | 35 | −3,421.5 | 0.621 | −3,291.0 |

<p class='estnote'>1. Weighted by the expected in-area share of origin and destination; inclusive value of the dwelling level with coefficient 1. 2. Full choice set of 1,587 zones with jobs. 3. Choice-based sample weights (weighted pseudo-log-likelihood). 4. Car driver available only with a household car that is free over the tour window.</p>

The synthetic population (CVAE) is not a likelihood model; its fit is reported in [validation](validation/index.md). The activity
distributions of MAST are 3,946 weighted relative frequencies of the estimation half.

## Linking logsums

Three logsums connect the models:

- **Mode-choice logsum** of a person between two zones for a purpose, from the tour mode model; it enters the stop
  models as the logsum detour.
- **Non-work accessibility** of a zone, the destination-choice logsum over all 1,588 zones for shopping, recreation,
  accompanying and other trips, weighted by trip shares (0.329, 0.279, 0.148, 0.243). It enters car ownership as the
  accessibility gained from a car.
- **Inclusive value** of the dwelling level in the PUMA level of residential location.

## Re-estimating the models yourself

Every model can be re-estimated from its data with Python Biogeme; see [the estimation package](../developers/estimation-package.md).
