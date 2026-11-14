# Land use

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Engine** | SILO (Simple Integrated Land Use Orchestrator), Java, with ORIOLE's estimated models |
    | **Code** | `landuse/` (inputs, engine changes, calibration, runs) |
    | **Time step** | One year, 2016 → 2024 |
    | **Agents** | Households, persons, dwellings, jobs |
    | **Sensitive to** | Car travel times and accessibility, housing prices and supply, jobs by zone, incomes, demographic rates |
    | **Produces** | Population, dwellings and jobs of every year |


The land-use stage runs on **SILO** (Simple Integrated Land Use Orchestrator), an open-source agent-based land-use
model. It advances households, persons, dwellings and jobs in **annual steps from 2016 to 2024**. ORIOLE keeps the
SILO engine and replaces its behavioural models with models estimated for this region.

## What happens in a simulated year

1. **Demography:** births, deaths, marriages, divorces, leaving the parental home, ageing.
2. **Employment and jobs:** jobs follow LODES by zone and type (QCEW for 2024); employment is aligned each year to
   the ACS rates by state, age and sex. Persons who look for a job choose among vacant jobs with the workplace model.
3. **Moving:** each household decides whether to search for a new dwelling; searching households choose a county,
   then a zone and dwelling type, then a dwelling.
4. **Construction:** new dwellings in Maryland follow the county building permits.
5. **Car ownership:** households update their cars.
6. **Control totals:** the population of every county is held to its synthetic 2016 population times its growth in
   the Census Bureau's annual county estimates.

Migration is open among 44 counties.

## Residential location

A moving household chooses with a three-level nested logit: **county → zone × dwelling type → dwelling**. The
county utility is

\[
U_r = \lambda_B\, IV^{B}_r + \lambda_A\, IV^{A}_r + \boldsymbol{\beta}_r^{\top}\mathbf{x}_r ,
\]

where \(IV^B_r\) and \(IV^A_r\) are the inclusive values of the lower levels and \(\mathbf{x}_r\) holds the car time to the
county, the previous county and its neighbours, the same state, the commute of the workers, the age of the oldest
member, school learning growth and crime.

| Level | Sample | Variables |
|---|---|---|
| County (44) | ACS PUMS movers 2014–18 | Car time beyond 20 min (weaker for higher incomes), adjacency to the previous county, previous county by age, same state, commute, school learning growth, crime for households with children |
| Zone × structure type (30 sampled) | RTS households, weighted | Size of the structure type in the zone, multimodal non-work accessibility by age and household size, commute, price level with income and household-size interactions, share of same-income households, dwellings per acre (with no-car and children interactions), retail jobs per km² |
| Dwelling (30 sampled) | ACS PUMS movers 2014–18 | Housing-cost share of income, cost, bedroom shortfall and excess, new construction, structure-type constants by children, household size and age, with income gradients |

Both inclusive-value coefficients lie in the unit interval (\(\lambda_B = 0.39\), \(\lambda_A = 0.92\)). The county level
keeps its fit on movers it was not estimated on: \(\rho^2\) 0.714 in estimation, 0.721 on held-out movers and 0.704
out of time (2019–2021).

## Moving decision

A household decides once a year whether to search:

\[
P(\text{search}) = 1 - \frac{1}{1 + a_m \exp\big[g - g_0 - 0.982\,\ln(1 + \text{years})\big]} ,
\]

with \(g\) the expected gain in utility from a search, \(g_0\) the gain in the first year of tenure and *years* the time
in the dwelling. The shift \(a_m\) is calibrated.

## Car ownership

A multinomial logit over 0, 1, 2 and 3+ cars, estimated on 91,348 Maryland PUMS households (80 % of 2014–2018). Each
alternative has its own coefficients for workers, other adults, children, the age of the oldest member and its
square, piecewise log income, dwelling type and bedrooms, dwelling density and the non-work accessibility gained
from a car (\(\rho^2\) 0.363; hold-out 0.358). County constants are calibrated.

## Workplace choice

A worker \(n\) living in zone \(h\) chooses workplace zone \(j\):

\[
V_{nj} = \mu\ln\Big(\sum_{k}e^{g_k}N_{jk}\Big) + \big(\beta_t+\boldsymbol\beta_{t}^{\top}\mathbf x_{n}\big)t_{hj}
 + \beta_{l}\ln(1+t_{hj}) + \beta_a A_j + \boldsymbol\beta_z^{\top}\mathbf z_{hj} + \boldsymbol\gamma^{\top}\mathbf s_{nj}
\]

where \(N_{jk}\) are the jobs of type \(k\) in zone \(j\), \(t_{hj}\) the AM-peak car time with slopes that vary by person
variables, \(A_j\) the non-work accessibility of the workplace zone, \(\mathbf z_{hj}\) boundary and regional terms, and \(\mathbf s_{nj}\) job-mix and wage terms interacted with
person variables. Estimated on 9,707 workers with the chosen zone and 99 sampled zones (36 parameters):

- the time slope is −0.069 per minute for the mean worker; women are 22 % more time-sensitive;
- the preference for high-wage zones rises with income, from 0.85 below \$40,000 to 3.53 at \$125,000 or more;
- hold-out log-likelihood: −4.808 per worker over all 1,587 zones with jobs.

## Other components

- **Partner matching** uses an assumed distance decay.
- **Births, marriages, divorces, leaving home** use the SILO rates, scaled by calibrated factors.
- **Deaths, incomes and job changes** follow the SILO engine and its inputs.

Full estimates of all land-use models are in the estimation package (see [Estimation package](../developers/estimation-package.md)).
