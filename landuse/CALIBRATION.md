# Stage 2: calibration of every SILO component against observed study-area data

Rule: each component is tuned to an observed target from the study area, on **2016–2020** only; **2021–2024** is the
out-of-sample test. Targets are by county for **every Maryland county** (user decision 2026-10-21; the six Baltimore-region counties
Anne Arundel, Baltimore City, Baltimore County, Carroll, Harford, Howard get the full per-county report) and by state for DC, DE, PA, VA, WV. Where a target does not exist in any dataset, that is written
here and the component is left as in the engine, with its effect reported. Nothing is tuned to traffic counts.

Data status: **here** = on this Mac (`inputs/pums_20xx_5yr`, LODES OD files); **public** = free download, verified
2026-10-21 (see `data_sources.md` for URLs); **request** = must be asked for.

| Engine component (class) | What is tuned | Observed target | Data | Status |
|---|---|---|---|---|
| BirthModel (+ `demographics.birth.scaler.*`, local scalers) | age-specific birth rates by marital status; per-county scaler | share of women 15–50 who gave birth in the last 12 months, by age band, marital status, county | ACS PUMS `FER` × `MAR` × `AGEP`, 2016–2024; cross-check county births from Census PEP components of change | here / public |
| DeathModel | age × sex death probabilities | deaths by age and sex by county (PEP components: county deaths per year; age-sex detail from CDC WONDER) | PEP `co-est2020/2024-alldata.csv` (deaths); CDC WONDER for age-sex shape | public |
| MarriageModel (`demographics.local.marriage.rate.adjuster`, single-person bias, interracial share) | marriage rate by age, sex; county adjuster | share married in the last 12 months by age, sex, county | ACS PUMS `MARHM`; interracial share from `RAC1P` of couples | here |
| DivorceModel | divorce rate by age, duration | share divorced in the last 12 months by age, county | ACS PUMS `MARHD` | here |
| LeaveParentHhModel | probability of leaving the parental household by age | share of 18–34 living with a parent, by age and county, and its year-to-year change | ACS PUMS `RELSHIPP` × `AGEP` | here |
| EducationModel (school exit, retirement; retirement income replacement) | school-exit hazard by age; retirement hazard by age; replacement ratio | enrollment share by age 16–29 (`SCH`); employment share by age 55–75 (`ESR`); retiree income relative to workers of same age-1 (`PINCP`, `SSP`) | ACS PUMS | here |
| DriversLicenseModel (currently off) | licence-holding by age | licensed drivers by age group and county | Maryland MVA licensed-driver tables (open data) or NHTS 2022 Maryland add-on | public / request — **decide after checking MVA**; if unavailable stays off, stated |
| EmploymentModel (take/quit job, income on hire; `real.wage.growth.rate`) | labour-force participation by age/sex; job-change rate; wage growth | employment rate by age, sex, county (`ESR`); job-to-job rate from LODES J2J; real wage growth from QCEW average weekly wage by county, deflated | PUMS here; J2J, QCEW public | here / public |
| JobMarketUpdate (`job.forecast.method = rate`, `job.growth.rate`, `employment.types`) | jobs by county, type and year | jobs by county and sector, every year 2016–2024 | LODES WAC `md_wac_S000_JT00_<year>` 2016–2023 (public, verified; 2024 not released) mapped to the four SILO job types; 2024 from QCEW county employment by sector (public, verified) | public |
| InOutMigration (per-state / county control; composition marginals) | net migration by county and year; in-migrant composition | PEP components: domestic + international net migration by county by year; in-migrant age, race, household size from PUMS `MIG` = moved from another county/state | PEP public; PUMS here | public / here |
| MovesModel (`move.or.not.*`, housing strategy, region utility) | annual move rate by household type; distance/region choice | share of households that moved in the last 12 months by tenure, size, income, age of head, county (`MV`, `MIG`); county-to-county mover flows (ACS migration flows) | PUMS here; ACS county-to-county migration flows public | here / public |
| ConstructionModel (`construct.dwelling.*`, demand/location strategy) | dwellings built per year by county and type | residential building permits by county, year, structure type (1-unit, 2–4, 5+) | Census Building Permits Survey `co<year>a.txt` (public, verified) | public |
| DemolitionModel | demolition probability by age/quality | **no county demolition series exists**; derive loss = permits − change in housing stock (PEP housing-unit estimates) per county, state the approximation | PEP housing units (public) + BPS | public, approximate |
| PricingModel (`PricingStrategyMstm`) | price response to vacancy | annual price change by county (FHFA HPI, public, verified); rents from PUMS `GRNTP`; vacancy by county from ACS (`VACS` in housing file) | public / here | |
| RenovationModel | quality transition rates | no direct data; use `YRBLT` × `VALP` relation as a weak check; otherwise engine default, stated | here, weak | |
| CarOwnership (`MaryLandUpdateCarOwnershipModel`, per region × worker class) | household vehicles by workers, size, income, county | `VEH` by `WIF`, `NP`, `HINCP`, county | PUMS here | here |
| Accessibility (`auto.accessibility.alpha/beta`) | not tuned; checked that zone accessibility ranks jobs within 45 min against LODES commute-shed | LODES OD here | here |
| Job types (`employment.types = RET,OFF,IND,OTH`) | mapping of NAICS sectors to the four types | LODES WAC sector columns (CNS01–CNS20) | public | |

### Moves model: county crime index of the dwelling and region utility

The Maryland housing strategy reads `input/crimeIndex.csv` (one county rate per `COUNTYFIPS` of the zone system) and
enters it as `1 − rate` in the dwelling utility (weight θ = 0–0.10 by household type, `DwellingUtilityCalcMstm`) and, area-weighted
per region, in the region utility (weight γ = 0.05–0.25 by income group, `RegionUtilityCalcMstm`); the indicator therefore has
to lie in [0, 1] with 1 = highest crime. The indicator is built by `input_build/build_crime_index.py` from observed 2016 UCR data:
index offenses (violent + property Part I offenses, arson excluded) per 100,000 residents (Census PEP 2016), divided by the
highest county rate in the zone system (Baltimore City, 6,671 per 100,000 = 1.0). Maryland's 24 jurisdictions come from the
Maryland SAC county table of the Crime in Maryland UCR; DC from FBI CIUS 2016 Table 3; Pennsylvania's 9 counties from the PSP
annual report (Table 2); Virginia's 16 jurisdictions and 2 West Virginia counties from FBI Tables 8 + 6 summed over the county
agency and its towns (Virginia State Police offenses, about 1–3 % of a county total, are not in these tables). Delaware's 3
counties take the state rate apportioned by the county-to-state ratio of the NIBRS serious-offense rate (Crime in Delaware
2012–2016), and 6 rural West Virginia counties whose reporting agencies cover less than a third of the state rate take the WV
state rate; method and source per county are in `data/crime_index_sources.csv`. The Maryland range is 0.20 (Carroll) to 1.00
(Baltimore City), median 0.33; the 1 − rate utility term is not tuned, its weights stay as in the engine.

## Procedure per component

1. Build the target table from the data above for every year 2016–2024 (script in `calibration/targets_<component>.py`,
   output `../data/silo_target_<component>.parquet`).
2. Run SILO 2016 → 2020, compare the component's simulated event rates (from the engine's event logs, `log.util.*`
   switched on) with the targets, adjust the component's parameters, repeat until each rate is within its tolerance
   (±5 % relative for rates, ±5 pp for shares) on 2016–2020.
3. Freeze. Run 2016 → 2024 with 5 seeds. Report 2021–2024 against the targets as the out-of-sample result in
   `validation/`, mean and spread per county.
4. Only then: the 2024 population goes to stage 3, and the run is extended to 2026.

## Still to decide
- Driver's licence model: on, if MVA licensed-driver counts by age and county can be obtained; otherwise off (as now).
- Geography of controls: decided 2026-10-21, county for all Maryland counties.

## Calibration as run (2016–2020, ten rounds; results in `calibration/calibration_log.csv`, values used in the last round in `data/silo_calibration_final.csv`; the next proposed values in `calibration/params.json`)

Update rule for every rate lever: θ ← θ · (observed/model)^0.8 per round, one 2016–2020 run per round. Levers and targets:

| component | lever (run property) | target (observed) | final value | model / observed, round 10 |
|---|---|---|---|---|
| births | `demographics.local.birth.rate.adjuster` | births per woman 15–50, Census components of change | 2.02 | 0.998 |
| marriages | `demographics.local.marriage.rate.adjuster` | married in the last 12 months, ACS PUMS | 1.64 | 1.000 |
| divorces | `demographics.local.divorce.rate.adjuster` | divorced in the last 12 months, ACS PUMS | 0.88 | 1.002 |
| residential moves | `move.or.not.binomial.log.shift.parameter` (binomial-logit shift, slope 10) | persons who moved in the last 12 months, ACS PUMS | 0.058 | 1.010 |
| construction | `construct.dwelling.demand.scaler` | housing units permitted, Building Permits Survey | 0.18 | 1.003 |
| leaving the parental home | `demographics.local.leave.parents.adjuster` | adults 18–34 not living with a parent, ACS PUMS | 1.25 | 0.959 |
| employment | `demographics.labor.participation.adjuster` on the observed employment rates by age and sex (`input/laborParticipationRates.csv`, ACS PUMS 2013–17) | employed share of persons 16+, ACS PUMS | 1.08 | 1.000 |
| car ownership | county constants `input/car_ownership_region_constants.csv` (alternatives 1, 2, 3+ against 0 cars), additive log-ratio update | vehicles per household by county, ACS PUMS | — | 100 % of county cells within 5 pp |

Fixed by data, not calibrated: real wage growth 0.5 % per year (QCEW Maryland average annual pay, CPI-deflated, 2016–2024); unemployment benefit at job loss (half of earnings, at most $22,360 a year, then flat in real terms); retirement income replacement 0.8 with a $15,000 floor; vacant dwelling stock = market vacancies only (for rent, for sale, rented or sold not occupied: ACS PUMS vacancy status by PUMA, 36 % of Maryland's vacant units); job control = base-year jobs by zone and type scaled by the LODES growth path (QCEW for 2024–2026), the engine adding or removing jobs by zone to meet it (vacant jobs first); county crime index from 2016 UCR rates; school inventory and student assignment (`schools/`).

## Engine fixes for the move-rate and income drifts (2026-10-22) and the check rounds 17–20

The five-seed test before these fixes (archived as `run/base/scenOutput/oos_s<k>_pass2`, `data/silo_validation_oos_*_pass2.parquet`)
had two drifts that the 2016–2020 calibration (mean only) did not show. Mechanisms were traced in the microdata
(`validation/diagnostics/`, seed 1) and in the engine's move diagnostics (`siloResults/moveDiagnostics.csv`, new); each fix is
one commit on branch `baltimore-2026` with a "Baltimore 2026" comment at the change.

| commit | component | mechanism found | change |
|---|---|---|---|
| a09dde0 | MovesModelImpl | (diagnostics only) | yearly utility mean/s.d. and move probability by household type, mean utility components, current vs chosen dwelling of movers |
| d621dc1 | MovesModelImpl | 68 % (2016) – 52 % (2018) of movers moved into a dwelling of lower utility than the one they left (dwelling choice ≈ uniform over 20 sampled vacancies, never compared with the current dwelling); utility s.d. within each type 0.16 → 0.20, mean move probability 12.8 % → 15.7 %; households that had moved the year before moved again at 40 % (never-moved households: 9.9 % → 4.7 %) | a household that searches moves only if the found dwelling has a higher utility than its current one (ineligible households still move) |
| cfe8c9d, 3ae2d16, bec23f2 | JobDataManagerImpl | job region chosen by the shortest travel time to the region × vacancies, job inside the region at random: hires had a median car commute of 51 min vs 26 min of base-year workers; Maryland workers employed in their home county 55 % (2016) → 37 % (2020) → 21 % (2024), LODES 49 % → 47 %; commute utility 0.615 → 0.546 | vacant job drawn from 500 sampled vacancies of all regions with weight f(t) = observed base-year commute share at t / share of all home–job pairs at t (`input/job_search_impedance.csv`, `input_build/build_job_search_impedance.py`, property `job.search.impedance.file`) |
| 7f5bba2 | IncomeAdjustment | freeze-and-grow kept a worker at the wage of the year of hire: employed 25–30 median $34,000 (2016) → $20,000 (2024), 30–35 $43,800 → $29,100, employed median $43,600 → $34,800 | employed income × base-year ratio of mean earnings at the new to the previous age, by sex (0.90–1.25), plus real wage growth |
| f23afcf | EmploymentModelImpl | hires without a wage in the run kept their non-wage income as wage (unemployed hired: median $4,800–5,250 before, $22,000–24,000 after only because of the last-wage rule; base-year non-employed had none) or got the 2016 cell mean ± $5,000 | wage drawn from the base-year incomes of employed persons of the same sex and age (±2 y), grown by real wage growth; re-hires keep the last wage; in-migrant copies keep the original's last wage |
| f099285 | JobDataManagerImpl / IncomeAdjustment | the unemployment benefit (½ wage ≤ $22,360) was kept for life: non-employed 26–55 median $5,000–15,000 vs $0–2,100 in the ACS | benefit until the end of the year after the job loss, then the non-wage income of a base-year non-employed person of the same sex and age (never above the benefit) |

Validation definition (validate_silo.py): the move rate is now person-based like the ACS: Maryland residents aged 1+ whose dwelling
differs from the previous year's or who were not in the model area a year before, against ACS persons aged 1+ with `MIG ≠ 1`
(the ACS asks `MIG` only from age 1; the earlier observed value counted infants as movers). The household-based share is kept as a
diagnostic. Before the fixes the person-based modelled rate was 14.8 % (2017) → 21.1 % (2024), seed mean, against 13.1 % → 11.8 %.

Contributions to the 2016 → 2024 change of the Maryland household-income shares before the fixes (seed 1; households of 2024 by
origin, weight × (share − 2016 share), `validation/diagnostics/income_stock_decomposition.py`):

| source | < $25k (+6.8 pp) | ≥ $150k (−2.6 pp) |
|---|---|---|
| households formed by leaving the parental home (9.0 % of 2024 households, 74 % below $25k) | +5.5 | −1.7 |
| households formed by divorce / marriage | +0.5 / +0.3 | −0.3 / −0.4 |
| in-migrant copies | +0.2 | −0.2 |
| original households: income change of the survivors (job loss, retirement, members leaving; no age progression) | +4.2 | +2.8 |
| original households: selection of the survivors | −3.9 | −2.7 |

Year-to-year, the person transitions that moved households into or out of < $25k were (2017–2024 sums, pp of households): member
left +5.5, job loss +2.5, re-hire −2.3, member joined −2.4, school leaver hired −1.0; the ACS (2020–24) shows 13.5 % below $25k for
householders aged 25–29 against 74 % for the model's leaving-home households. In-migrant copies are not dominated by low-income
households (8–19 % below $25k, 18–27 % above $150k, against 13–15 % and 19 % for all households). Household income is the sum of person incomes, which like `HINCP` (the sum of
the members' `PINCP`) includes non-wage income; at the 2020 check (round 20) the share above $150k matches the ACS within each
number-of-workers class (0: 5.4 % vs 5.7 %, 1: 13.0 vs 12.0, 2: 34.9 vs 36.1, 3+: 54.4 vs 48.3) but the model has more households
with two or more workers (46.2 % vs 41.0 %), which raises the statewide share above $150k.

Check rounds (2016–2020, one seed; `calibration/calibration_log.csv`): the round-17 run had the move and income fixes, round 18 the
job-choice fix, round 19 the impedance file (2000 sampled jobs), round 20 the final engine (500 sampled jobs). With the
better-dwelling rule the move shift lever had to rise from 0.058 to about 0.4; the damped ratio rule moved it by too little per round
(model rate ∝ shift^0.28), so round 20 was started at the secant value 0.39 from rounds 18–19.

| component (model / observed, 2017–2020) | r16 (old engine) | r17 | r18 | r19 | r20 |
|---|---|---|---|---|---|
| births | 1.000 | 1.001 | 0.999 | 0.999 | 1.005 |
| marriages | 0.999 | 1.011 | 1.004 | 1.002 | 1.000 |
| divorces | 1.002 | 1.021 | 1.009 | 0.996 | 0.997 |
| moves (r16: households; r17–20: persons 1+) | 0.988 | 0.592 | 0.661 | 0.724 | 0.962 |
| construction | 1.018 | 1.123 | 1.041 | 1.004 | 0.971 |
| adults 18–34 not with parents | 0.981 | 0.991 | 0.989 | 0.986 | 0.980 |
| employed 16+ | 0.997 | 0.978 | 0.979 | 0.981 | 0.983 |
| move shift lever | 0.058 | 0.058 | 0.089 | 0.124 | 0.390 |

Round 20 by year: persons moved 11.8, 12.0, 11.7, 12.1 % (2017–2020; observed 13.1, 12.5, 12.2, 11.7 %), no longer rising.
The out-of-sample runs use the values proposed after round 20 (`calibration/params.json`).

Out-of-sample result with the fixed engine (five seeds, `REPORT.md` section 3, `data/silo_oos_before_after.csv`): persons who moved
11.3–11.4 % in 2021–2024 vs 10.8–11.2 % observed (before 19.9–21.1 %, rising); households below $25k 14.4 % in 2024 vs 14.8 %
(before 19.5 %); households at or above $150k 26.7 % vs 21.4 % (before 16.5 %): the person incomes by age now agree with the ACS and
the remaining excess comes from the employed share (67.7 % vs 65.2 %, the employment lever is calibrated on the county mean) and from
too many households with three or more workers (13.1 % vs 9.2 %). The values of the table "Calibration as run" above are those of
round 10; the values used now are in `data/silo_calibration_final.csv` (round 20) and `calibration/params.json`.

## Stage-2 completion (2026-10-23 to 2026-10-25): estimated residential location, job consistency, check rounds 21-31

Engine commits on `baltimore-2026` (after bec23f2), each with a "Baltimore 2026" comment at the change:

| commit | component | mechanism found | change |
|---|---|---|---|
| 92b19d9 | merge of `resloc` | | estimated 3-level nested logit (region, zone × type, dwelling) and logsum accessibility; worktree removed |
| 40d1e92 | InOutMigrationImpl, JobDataManagerImpl, EmploymentModelImpl, JobConsistency | in 2024 11.4 % of the EMPLOYED pointed to another person's job, 1.1 % to a removed job: in-migrant copies were registered only after their job search (lookForJob finds the person by id and needs the home zone), so they never searched and kept the original's job id; a later quitJob of either released the other's job | copies registered and placed first, then search their own job (unemployed with the benefit rule if none); quitJob never releases another person's job; a person who finds no job is not EMPLOYED; year-end check `siloResults/jobConsistency.csv` |
| db8448f, cd55462 | JobDataManagerImpl | hires into jobs removed after the vacancy lists were built (≈ 50,000 a year); jobs added by the job-market update entered the lists only a year later (4.4 million exhausted searches in round 29, young age groups 3–8 % below the ACS employment rate) | removed or filled candidates get no weight; new vacant jobs enter the lists at once |
| c353a21 | EmploymentModelImpl | single adjuster on the county mean left the statewide employed share 2.5 pp high | multipliers by age band × sex (`input/labor_participation_adjusters.csv`) on the statewide ACS employed share by age and sex |
| 09ef066 | LeaveParentHhModelImpl | every leaver formed a one-person household | a leaver 18–34 joins a roommate household with probability 0.386 (ACS PUMS 2014–18: roomers, housemates, other non-relatives among non-family persons 18–34, cohabiting couples excluded; 54.8 % of them live with others) |
| bca70a0 | AccessibilityLogsumMd | | car availability against drivers (persons 16+), as in the destination-choice logsum file |
| 69c3c7e, 68a424b, db533de | ReslocModel, HousingStrategyMstm, MovesModelImpl | move-or-not used the inherited satisfaction utility (contains race); with the absolute gap the population sorted and the search probability fell 11.6 → 7.0 % in four years; the region-scale comparison counted the moving costs twice (86 % of movers stayed in their region vs 69 % ACS) | P = 1 − 1/(1 + shift·exp(gap − gap₀ − 0.982·ln(1+years))), gap = expected maximum utility of the search set (region drawn with P_r, best of 20 dwellings) − utility of the current dwelling (region terms + λ_B(V_B − ln D) + λ_A V_A), gap₀ = gap in the first year of the tenure; tenure from the ACS MV distribution by age (`input/tenure_by_age.csv`, slope −0.982 from the MV distribution, `input_build/build_tenure.py`); better-dwelling rule on V_A + V_B − ln D |
| cf3a875, a0ccc56, 956bf12 | ConstructionModelMstm | the Maryland construction class called the demand strategy without the region: the county scalers of rounds 1–24 never applied; demand a county could not build was built anywhere weighted by land (rural counties) | county demand split by the 2016–2019 permit shares by structure type (`input/construction_county_shares.csv`); unbuildable demand stays unbuilt; Baltimore City infill capacity 1.5 × the land its 2016–2026 permits need (`input/development_2026.csv`, `input_build/build_development_capacity.py`) |

Inputs: final logsum accessibility `data/accessibility_2016.csv`; resloc zone and region levels re-estimated with it (`resloc/ESTIMATION_REPORT.md` 4.6); car ownership with the logsum gain (`input/car_ownership_coefficients_logsum.csv`), county constants recalibrated from zero; job control total = persons 16+ of the area (PEP path) × ACS employed share ÷ (1 − Maryland JOLTS openings rate), LODES distribution by zone and type (`input_build/scale_job_controls.py`, `data/silo_target_job_totals.csv`). Validation (`validate_silo.py`): new rows B2 (employed by age × sex, workers per household, roommates), D (vacant share vs JOLTS), E (own-county work share vs LODES OD, travel time vs ACS JWMNP), F (stay share and flow correlation vs ACS county flows); construction now compares dwellings built in year Y with units permitted in Y (before: Y + 1).

### Check rounds 21–34 and the stopping decision (2026-10-26)

Each round is one 2016–2020 run, seed 1; model / observed, means 2017–2020 (`calibration/calibration_log.csv`). Rounds 21–29 ran the
engine of 2026-10-23; rounds 30–34 add cd55462 and 4d854e6 (vacant jobs added during the year enter the vacancy lists at once,
synchronized append); from round 32 the employment multiplier of a band is first limited to 1 / (highest employment rate of the band),
since above it the rate is capped at 1 and the multiplier no longer acts (the teenage multipliers had run up to 4.3–5.5 while hires
were blocked). 22 levers: six rate levers and 16 employment cells (age band × sex).

| round | births | marriages | divorces | moves | construction | leaving home | employment cells within ±2 % (worst cell) | levers within ±2 % | move shift |
|---|---|---|---|---|---|---|---|---|---|
| 21 | 0.978 | 0.908 | 0.975 | 0.709 | 0.873 | 0.952 | 4/16 (female 16-19 0.428) | 4/22 | 0.402 |
| 22 | 1.003 | 0.975 | 0.981 | 0.684 | 0.908 | 0.958 | 9/16 (female 16-19 0.665) | 11/22 | 0.750 |
| 23 | 1.009 | 0.995 | 0.986 | 0.813 | 0.958 | 0.963 | 13/16 (female 16-19 0.789) | 16/22 | 1.017 |
| 24 | 1.007 | 0.999 | 0.996 | 0.977 | 1.007 | 0.967 | 12/16 (female 16-19 0.871) | 16/22 | 1.460 |
| 25 | 1.000 | 1.000 | 0.990 | 1.009 | 1.046 | 0.970 | 12/16 (female 16-19 0.878) | 16/22 | 1.528 |
| 26 | 0.999 | 1.001 | 0.997 | 1.000 | 1.047 | 0.974 | 12/16 (female 16-19 0.888) | 16/22 | 1.509 |
| 27 | 1.007 | 0.998 | 0.998 | 1.008 | 1.029 | 0.977 | 12/16 (female 16-19 0.903) | 16/22 | 1.508 |
| 28 | 1.000 | 1.002 | 0.994 | 1.001 | 1.012 | 0.978 | 12/16 (female 16-19 0.910) | 17/22 | 1.499 |
| 29 | 0.998 | 1.002 | 0.999 | 1.004 | 0.993 | 0.983 | 12/16 (female 16-19 0.924) | 18/22 | 1.497 |
| 30 | 0.999 | 0.997 | 0.996 | 1.004 | 0.997 | 0.977 | 12/16 (male 16-19 1.113) | 17/22 | 1.492 |
| 31 | 1.000 | 1.001 | 0.996 | 1.010 | 1.009 | 0.981 | 12/16 (male 16-19 1.120) | 18/22 | 1.488 |
| 32 | 1.001 | 1.000 | 0.999 | 1.004 | 1.020 | 0.985 | 6/16 (female 16-19 0.692) | 12/22 | 1.476 |
| 33 | 1.000 | 0.997 | 0.998 | 1.000 | 1.014 | 0.982 | 11/16 (female 16-19 0.917) | 17/22 | 1.466 |
| 34 | 0.998 | 1.001 | 0.995 | 0.985 | 1.001 | 0.988 | 13/16 (female 16-19 0.913) | 19/22 | 1.467 |

Decision (2026-10-26): calibration stops at round 34, 19 of 22 levers within ±2 %. The out-of-sample runs use the values **used in
round 34** (not the values proposed after it): rate levers in `calibration/params.json` (births 2.0216, marriages 1.7993, divorces
0.9281, move shift 1.4671, construction 0.3639, leaving home 2.0354, single employment adjuster 1.0), employment multipliers in
`input/labor_participation_adjusters.csv` (the round-34 `value` column of the log), car-ownership county constants in
`input/car_ownership_region_constants.csv` (the round-34 update reversed from `data/silo_validation_calib_r34.parquet`, exact to the
fourth decimal), county construction scalers unchanged (counties follow the permit shares). The values proposed after round 34 are
kept in `calibration/after_r34_proposed/`.

Residuals at round 34, reported, not tuned further: employed share of men 20–24 1.045, women 16–19 0.913 and women 20–24 1.054 of the
ACS (2017–2020 means). The young cells did not settle in rounds 30–34 (women 16–19: 1.096, 1.102, 0.692, 0.917, 0.913; men 20–24:
1.052, 1.060, 0.941, 1.035, 1.045).

Out-of-sample test with the round-34 values (five seeds, 2016–2024, `REPORT.md` sections 3–4): Maryland population 0.991 of the PEP
path in 2024, 21/24 counties within ±2 % (outside: Calvert 0.948, Prince George's 0.972, Baltimore County 0.975); households 0.975 of
the ACS 2020–24 count; households at or above $150k 23.4 % vs 21.4 %; employed share 16+ 63.8 % vs 65.2 %, with the young-employment
residual growing in the test years (20–24: 81 % vs 70 %). Note: from this run on, `calibration/params.json` holds the values used in
round 34, not the next proposed ones; SILO runs filter the per-person "No jobs remaining" warnings (`run/log4j2_quiet.xml`, logging
only), which cut the logs about ninefold.

### Rounds 36–40 (2026-10-26): new marriage rule and job-to-job change; marriage, divorce and construction levers only
Engine 4e82166 (couples always form a new household; commute-driven job change base 0.5, γ = 0.02/min, t_ref 38 min, 5 offers;
γ set so that the 2016–2020 commute holds at its base level, not estimated; base calibrated to the JOLTS Maryland quits rate
2017–19, 25.2 % a year, series JTS000000240000000QUR, an upper bound because quits include exits from employment). All other
levers frozen at round 34 (`calibration/params.json`, input files unchanged); values in `calibration/params_recal.json`, script
`calibration/recalibrate_subset.py`, acceptance check `calibration/go_check.py`.

| round | marriage adj. | divorce adj. | construction scaler | marriages | divorces | construction | births | moves | levers ±2 % |
|---|---|---|---|---|---|---|---|---|---|
| 36 (smoke_jc4) | 1.7993 | 0.9281 | 0.3639 | 1.038 | 1.134 | 1.394 | 1.024 | 0.997 | 14/22 |
| 37 | 1.7338 | 0.8183 | 0.1484 | 0.952 | 1.032 | 0.663 | 1.010 | 0.892 | 9/22 |
| 38 | 1.8205 | 0.7932 | 0.4511 | 1.056 | 1.060 | 1.564 | 1.028 | 1.007 | 14/22 |
| 39 (log-linear fit of 36–38) | 1.775 | 0.760 | 0.248 | 1.005 | 1.022 | 1.019 | 1.021 | 0.945 | — |
| 40 (damped ratio^−0.5; construction interpolated in the 37/39 bracket) | 1.7706 | 0.7518 | 0.2427 | 1.004 | 1.015 | 0.997 | 1.022 | 0.960 | — |

Round 40: the three recalibrated levers meet the acceptance criteria (marriages, divorces ±2 %, construction ±5 %, all counties
within ±25 %), but frozen levers moved: births 1.022 (round 34: 0.998), moves 0.960 (0.985), employed men 20–24 1.052 (1.045),
women 20–24 1.060 (1.054), men 25–34 1.020 (1.015). Not accepted; the five-seed run was not started (decision pending).

Round 41 (author decision: one round that also moves the move-shift lever ×1/0.960 and the birth adjuster ×1.022^−0.5, marriage,
divorce and construction at their round-40 values): birth adjuster 1.9997, move shift 1.5282, marriage 1.7706, divorce 0.7518,
construction 0.2427. Result 2017–2020: births 1.011, deaths 0.962 (round 34: 0.962), marriages 0.995, divorces 1.008, construction
1.000 (all counties within ±25 %), moves 0.968, leaving home 0.976. **Accepted** (`calibration/params.json` = round-41 values; round
34 kept in `params_r34.json`). Stated residuals: moves 0.968 (within ±5 %, accepted by rule), leaving home 0.976 (round 34: 0.988),
employment cells men 20–24 1.051, women 20–24 1.061, men 25–34 1.020 (0.001–0.007 beyond their round-34 values).

Out-of-sample test with the round-41 values (five seeds, 2016–2024; `REPORT.md` section 0, `data/silo_headline_2024.csv`): Maryland 2024
population 0.972 of the PEP path (12/24 counties within ±2 %), households 0.996 of the ACS 2020–24 count, new dwellings 2021–2024
1.16 × permits, employed share 16+ 62.8 % vs 65.2 %, working in Maryland 90.3 % vs 84.1 %, mean car time 26.1 min (2016 base 31.4),
home-county share 69.9 % vs 65.9 % (ACS commuting flows, the benchmark for this quantity), persons who moved 11.2 % vs 10.8 %.
Calibration ends at round 41.

### Rounds 42–43 (2026-10-27): couples without a dwelling stay; job-change search scaled by vacancies (engine 662135a)
- Marriage: a couple that finds no vacant dwelling moves into one partner's dwelling by SILO's original rule instead of leaving the
  area (1,600–12,200 couples a year in 2016–2019, logged each year).
- Job change: search probability × min(1, v_ref / v_t), v_t = vacant share of all jobs when the year's events are drawn; γ and base
  unchanged. v_ref = 0.0403, the mean of that engine measure in 2016–2019 (round 42 first used 0.0143, the year-end share of the
  validation tables, which is a different measure; the factor was then 0.24–0.47 in every calibration year and halved the
  JOLTS-calibrated change rate).

| round | values | births | deaths | marriages | divorces | moves | construction | leaving home |
|---|---|---|---|---|---|---|---|---|
| 42 (check, round-41 values, v_ref 0.0143) | — | 1.014 | 0.958 | 1.041 | 1.003 | 0.984 | 0.976 | 0.984 |
| 43 (marriage 1.7706 → 1.7354 = ×1.041^−0.5; v_ref 0.0403) | `params.json` (round 41: `params_r41.json`) | 1.010 | 0.961 | 1.028 | 1.009 | 0.980 | 0.982 | 0.980 |

Round 43 is the last round (one damped round allowed): marriages 1.028 stay outside ±2 % and are a stated residual; moves and leaving
home at 0.980; employment cells as in round 41. Calibration ends at round 43.

### Rounds 45–49 and the final run (2026-10-28/29)
Base base_v2/v3/v4 (consistent 2016 employment and jobs, workplaces from the RTS workplace model), no participation multipliers
(employment is aligned at year end to the yearly ACS rates by home state, not calibrated), QCEW × JOLTS job input, intercensal
population series. Six levers, damped (`calibration/calibrate_v3.py`; births 0.8, marriages and divorces 0.5, moves 1.0, leaving
home 0.8, construction 1.3).

| round | change | births | marriages | divorces | moves | construction | leaving home |
|---|---|---|---|---|---|---|---|
| 45 | base_v3, rts2, pooled rates | 0.990 | 1.209 | 1.046 | 1.018 | 0.820 | 0.985 |
| 46 | | 0.981 | 1.114 | 1.034 | 0.997 | 0.979 | 0.980 |
| 47 | state employment rates | 0.986 | 1.062 | 1.026 | 1.002 | 0.996 | 0.983 |
| 48 | intercensal population series | 0.989 | 1.030 | 1.028 | 0.995 | 1.099 | 0.980 |
| 49 | base_v4, rts3 | 0.996 | 1.020 | 1.017 | 0.984 | 0.998 | 0.984 |

Final run with the values round 49 used (`calibration/params_calib_r49.json`: births 2.0877, marriages 1.4296, divorces 0.7036, move
shift 1.5087, construction 0.2871, leaving home 2.1564). Results: `REPORT.md` section 00.

### Rounds 50–51: construction by yearly county permits (2026-10-29)

Maryland construction now places each year's observed county permits (Census BPS, engine 3066ca9); the construction lever left the
calibration (the demand scaler 0.2871 acts only outside Maryland). r50 (seed 1, 2016–20, r49 levers): births 0.997, marriages 1.022,
divorces 1.020, moves 0.996, leaveParents 0.979; built/permits 1.000 every year; all 24 counties within ±2 %. One damped round r51
(`params_calib_r51.json`): births 0.995, marriages 1.007, divorces 1.014, moves 0.987, leaveParents 0.977 (left as is: the one damped
round asked for). Unplaced in-migrants r51 2016–19: 1,296 / 961 / 2,636 / 6,699, mostly in regions outside Maryland. Final seeds run
with the r51 levers (`params.json`; r49 kept as `params_r49_pass7.json`; previous seeds `*_pass7`). REPORT.md section 00.
