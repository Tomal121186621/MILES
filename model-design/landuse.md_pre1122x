# Land use

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Engine** | SILO (Simple Integrated Land Use Orchestrator), Java, with MILES's estimated models |
    | **Code** | `landuse/` (inputs, engine changes, calibration, runs) |
    | **Time step** | One year, 2016 → 2024 |
    | **Agents** | Households, persons, dwellings, jobs |
    | **Sensitive to** | Car travel times and accessibility, housing costs and supply, vacancies, jobs by zone, incomes, demographic rates |
    | **Produces** | Population, dwellings and jobs of every year |


The land-use stage runs on **SILO** (Simple Integrated Land Use Orchestrator), an open-source agent-based land-use
model. It advances households, persons, dwellings and jobs in **annual steps from 2016 to 2024**. MILES keeps the
SILO engine and replaces its behavioural models with models estimated for this region.

## What happens in a simulated year

1. **Demography:** births, deaths, marriages, divorces, leaving the parental home, ageing.
2. **Employment and jobs:** jobs follow LODES by zone and type (QCEW for 2024); employment is aligned each year to
   the ACS rates by state, age and sex. Persons who look for a job choose among vacant jobs with the workplace model.
3. **Moving:** each household decides whether to search for a new dwelling; searching households choose a PUMA,
   then a dwelling in it.
4. **Construction:** new dwellings in Maryland follow the county building permits.
5. **Car ownership:** households update their cars.
6. **Control totals:** the population of every county is held to its synthetic 2016 population times its growth in
   the Census Bureau's annual county estimates.

Migration is open among 44 counties.

## Residential location

A moving household chooses a **PUMA**, then a **dwelling** within it. Both levels are estimated on ACS PUMS movers of
2014–2018 (15,163 in estimation, 3,820 held out). The utility of PUMA \(p\) is

\[
U_p = IV_p + \beta_M \ln M_p + \boldsymbol{\beta}^{\top}\mathbf{x}_p, \qquad
IV_p = \ln \frac{1}{200}\sum_{d \in S_p} \exp V_d ,
\]

where \(V_d\) is the utility of dwelling \(d\) and \(S_p\) holds 200 dwellings drawn at random from the PUMA; the
inclusive-value coefficient is held at 1. The market size \(M_p\) is the PUMA's dwelling stock times a fixed turnover
rate, so it changes only with construction and demolition.

| Level | Alternatives | Variables |
|---|---|---|
| PUMA (14 parameters) | The 97 PUMAs of the zone-system area | Market size; car time from the previous home (no effect below 20 min); inside and bordering the previous migration area; same state; commute of the workers; crime × children; ln dwelling density, also × single-person household, × oldest member under 35 and × ln income; share of dwellings in DC or Baltimore City; own-race share |
| Dwelling (18 parameters) | Chosen dwelling and 29 drawn from the PUMA | Cost above 30 % of income; ln monthly cost; bedroom shortfall and excess (need = household size, at most 5); built in the last five years; structure type; each also × ln income |

The own-race share is the share of the PUMA's households whose householder is of the race category of the mover's
householder (white, Black, Hispanic, other). It is recomputed every simulated year. It describes where households of
each group move; preference, discrimination, steering and history cannot be separated with these data. Of the other
models, only school location uses race.

Hold-out log-likelihood per mover: −2.297 (PUMA) and −3.115 (dwelling).

**In the simulation.** The vacant dwellings of every PUMA are counted exactly. A PUMA is available while it has a
vacant dwelling, and its weight is multiplied by \(\min(1, v_p / v_p^{2016})\), its vacancy rate relative to 2016. The
household draws a PUMA, chooses among 30 of its vacant dwellings, and moves only if that dwelling beats its current
one.

## Moving decision

A household decides once a year whether to search:

\[
P(\text{search}) = 1 - \frac{1}{1 + a_m \exp\big[g - g_0 - 0.982\,\ln(1 + \text{years})\big]} ,
\]

with \(g\) the expected gain in utility from a search (the PUMA log-sum minus the utility of the current dwelling),
\(g_0\) the gain in the first year of tenure and *years* the time in the dwelling. The shift \(a_m\) is calibrated.

## Car ownership

A multinomial logit over 0, 1, 2 and 3+ cars, estimated on 91,348 Maryland PUMS households (80 % of 2014–2018; 56
parameters). Each alternative has its own coefficients for workers, persons aged 16+ (2, 3, 4 or more), children,
the age of the oldest member and its square, piecewise log income, dwelling type and bedrooms, dwelling density, the
non-work accessibility gained from a car and a Baltimore City term (\(\rho^2\) 0.379; hold-out 0.375). The Baltimore
City term is estimated with the other coefficients; no constant is calibrated.

## Workplace choice

A worker \(n\) living in zone \(h\) chooses workplace zone \(j\):

\[
V_{nj} = \mu\ln N_{j} + \big(\beta_t+\boldsymbol\beta_{t}^{\top}\mathbf x_{n}\big)t_{hj}
 + \beta_{l}\ln(1+t_{hj}) + \boldsymbol\beta_z^{\top}\mathbf z_{hj} + \boldsymbol\gamma^{\top}\mathbf s_{nj}
\]

where \(N_{j}\) are the jobs of zone \(j\) (retail, office, industrial and other, equal weights), \(t_{hj}\) the AM-peak
car time with slopes that vary by person variables (sex, age, income group, licence, household size, rural home, no
car in the household), \(\mathbf z_{hj}\) boundary terms (same zone, other county, other state) and a District of
Columbia workplace term for homes outside the District, and \(\mathbf s_{nj}\) job-mix and high-wage shares interacted
with person variables. Estimated on 9,707 workers with the chosen zone and 99 sampled zones (24 parameters):

- the time slope is −0.070 per minute for the mean worker; women are 23 % more time-sensitive;
- the preference for high-wage zones rises with income, from 0.64 below \$40,000 to 3.29 at \$125,000 or more;
- the District term (0.83) is used as estimated, without a shift;
- hold-out log-likelihood: −4.811 per worker over all 1,587 zones with jobs.

From 2017 on, every job search uses this model among the vacant jobs.

## Other components

- **Partner matching** uses an assumed distance decay.
- **Births, marriages, divorces, leaving home** use the SILO rates, scaled by calibrated factors.
- **Deaths, incomes and job changes** follow the SILO engine and its inputs.

Full estimates of all land-use models are in [Estimated models](../calibration-validation/estimates/landuse.md); the
estimation code is in the [estimation package](../developers/estimation-package.md).
