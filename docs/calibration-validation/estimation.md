# Estimation

## Common design

- **Sample.** All survey-based models are estimated on the estimation half of the travel survey; the land-use models
  of residential location and car ownership on ACS PUMS households.
- **Weights.** The survey is stratified by home location, which every model except residential location takes as
  given, so these models are estimated without weights. Weights are used only where the sample is selected on the
  outcome: the zone level of residential location (whose outcome is the home location) and the work tour mode choice
  (whose sample over-represents rail commuters; weighted exogenous sample maximum likelihood).
- **Location probabilities.** A survey location known by traffic zone or tract may cover several model zones; its
  probability is the sum of the probabilities of those zones, weighted by housing units, enrolment or jobs.
- **Choice sets.** School and activity-location models use the full choice set of 1,588 zones; workplace choice the
  chosen zone and 99 sampled zones; the zone and dwelling levels of residential location 30 sampled alternatives.
- **Specification search.** Each model is built in blocks of variables from a basic model. A block is kept when its
  likelihood-ratio test is significant at 5 %, it lowers the BIC and its signs are as expected; non-nested forms are
  compared by BIC.
- **Standard errors** are robust (sandwich).
- **Software:** Python Biogeme for every model of the estimation package.

## All estimated models

\(N\): observations; \(K\): parameters; LL: log-likelihood at the estimates; \(\bar\rho^2\): adjusted rho-square.
Hold-out: \(\rho^2\) (county, zone, dwelling, cars), log-likelihood per record (workplace, schools, locations) or total
log-likelihood (tour formation and mode) on held-out data.

| Model (alternatives) | \(N\) | \(K\) | LL | \(\bar\rho^2\) | Hold-out |
|---|---:|---:|---:|---:|---:|
| **Land use and workplace** | | | | | |
| Residential location: county (44) | 15,163 | 14 | −15,959.4 | 0.714 | 0.714 |
| zone × dwelling type (30 sampled, weighted) | 10,655 | 15 | −28,089.7 | 0.224 | 0.139 |
| dwelling (30 sampled) | 15,163 | 38 | −47,688.2 | 0.075 | 0.082 |
| Car ownership (4) | 91,348 | 51 | −80,664.0 | 0.363 | 0.358 |
| Workplace (100 sampled) | 9,707 | 36 | −21,334.3 | 0.522 | −4.808 |
| **Schools (full choice set)** | | | | | |
| K–8 (1,144 zones) | 1,509 | 9 | −2,941.0 | 0.717 | −1.983 |
| High school (719 zones) | 668 | 5 | −1,243.3 | 0.716 | −1.853 |
| College (141 zones) | 673 | 9 | −1,827.8 | 0.448 | −2.824 |
| **ORIOLE-Day: locations (1,588 zones)** | | | | | |
| Main activity, four purposes (pooled) | 14,341 | 71 | −49,122.5 | 0.535 | −3.352 |
| Stop: shopping | 3,979 | 23 | −9,987.8 | 0.659 | −2.527 |
| Stop: recreation | 5,064 | 22 | −15,801.1 | 0.576 | −3.195 |
| Stop: accompanying | 3,515 | 26 | −12,417.5 | 0.520 | −3.406 |
| Stop: other errands | 8,055 | 23 | −24,580.1 | 0.586 | −3.024 |
| Outing from the workplace: first stop | 1,180 | 13 | −3,089.9 | 0.665 | −2.715 |
| Work business: usual-workplace workers | 1,539 | 22 | −8,402.2 | 0.312 | −5.541 |
| Work business: other persons | 1,259 | 19 | −6,766.7 | 0.297 | −5.588 |
| Work trips of home workers | 366 | 6 | −1,634.6 | 0.431 | −4.375 |
| School without record; daycare (pooled) | 846 | 11 | −3,706.8 | 0.453 | −4.280 |
| **ORIOLE-Day: tour formation and mode** | | | | | |
| Outing from the workplace (2) | 8,613 | 8 | −3,061.5 | 0.486 | −3,093.2 |
| Mode of the outing (2) | 1,177 | 8 | −360.2 | 0.549 | −299.7 |
| Return home (2) | 28,349 | 33 | −13,697.0 | 0.301 | −13,771.8 |
| Tour mode: work (6, weighted) | 9,126 | 51 | −4,313.1 | 0.626 | −4,284.0 |
| Tour mode: school (6) | 2,651 | 34 | −972.5 | 0.651 | −1,096.5 |
| Tour mode: shopping (6) | 3,206 | 44 | −1,150.2 | 0.713 | −1,107.0 |
| Tour mode: other (6, nested) | 10,405 | 57 | −4,916.7 | 0.623 | −5,049.8 |
| Joint shopping (5) | 452 | 15 | −112.8 | 0.780 | −94.0 |
| Joint recreation and other (6) | 1,296 | 25 | −450.3 | 0.710 | −459.1 |
| Transit leg mode (5) | 6,792 | 35 | −3,501.8 | | −3,366.7 |

The synthetic population (CVAE) is not a likelihood model; its fit is reported in [validation](validation/index.md). The activity
distributions of ORIOLE-Day are 3,946 weighted relative frequencies of the estimation half.

## Linking logsums

Three logsums connect the models:

- **Mode-choice logsum** of a person between two zones for a purpose, from the tour mode model; it enters the stop
  models as the logsum detour.
- **Non-work accessibility** of a zone, the destination-choice logsum over all 1,588 zones for shopping, recreation,
  accompanying and other trips, weighted by trip shares (0.329, 0.279, 0.148, 0.243). It enters residential
  location, car ownership and workplace choice.
- **Inclusive values** of the residential location levels.

## Re-estimating the models yourself

Every model can be re-estimated from its data with Python Biogeme; see [the estimation package](../developers/estimation-package.md).
