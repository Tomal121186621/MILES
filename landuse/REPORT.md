# Stage 2 — land-use model: calibration and validation report

## 00 Final run (2026-10-29): five seeds 2016–2024, calibration window 2017–20, out of sample 2021–24

Setup: as in 00a below, plus Maryland construction placed by each year's observed county building permits (Census BPS 2016–2024,
`input/construction_county_permits.csv`, property `construct.dwelling.region.permits.file`; engine 3066ca9). Per county and year the
model builds the permitted units: 2–4 units → MF234, 5+ → MF5plus, 1-unit split into SFD/SFA/MH by the engine's demand. The demand
scaler (`construct.dwelling.demand.scaler`) now acts only on the regions outside Maryland and is no longer calibrated. Levers of round 51
(`calibration/params_calib_r51.json`, = `params.json`; check run r50 and damped round r51 in `CALIBRATION.md`). Tables:
`data/silo_final_tables.csv`, `data/silo_validation_oos_mean.parquet`; unplaced in-migrants by target region and year from the engine
log: `data/silo_final_unplaced_inmigrants.csv` (`validation/unplaced_inmigrants.py`). Figure `5_reports/figures/fig_landuse.pdf`
redrawn (calibration window = round 51). Previous run kept as `*_pass7`.

**Imposed (consistency checks, not tests):** county population, employment level, vacancy share of jobs, Maryland construction (permits).

**Year convention:** the step starting in year Y targets PEP for Y+1, so pp_Y is the population of July Y+1 and is scored as year Y+1; pp_2023 = pp_2024 (the end-year file repeats the last state) is the 2024 population.

| quantity (Maryland) | model 2017–20 | observed 2017–20 | model 2021–24 | observed 2021–24 | kind |
|---|---|---|---|---|---|
| population / PEP | 0.9994 | 1 | 0.997 | 1 | imposed |
| counties within ±2 % (of 24) | 24.0 | 24 | 23.1 (2024: 22.4) | 24 | imposed |
| employed share 16+ | 64.9 % | 65.3 % | 63.3 % | 65.2 % | imposed |
| vacant share of jobs (year end) | 4.2 % | 4.6 % | 4.5 % | 6.4 % | imposed |
| new dwellings / permits | 1.000 | 1 | 1.000 | 1 | imposed |
| job-to-job changes / employed | 24.2 % | 25.2 % (JOLTS quits) | 23.9 % | 25.2 % | test |
| mean car time to work, min | 30.2 | 32.7 (ACS, all modes) | 30.4 | 31.2 | test |
| work in Maryland | 82.7 % | 82.7 % | 82.2 % | 84.1 % | test |
| same county (of in-state workplaces) | 61.9 % | ACS 65.9 % with WFH, 62.2 % without | 61.6 % | same | test |
| persons who moved | 12.2 % | 12.4 % | 12.5 % | 10.9 % | test |
| mover flows, correlation with ACS 2016–20 | 0.972 | 1 | 0.962 | 1 | test |
| movers staying in their region | 70.0 % | 68.9 % | 66.1 % | 68.9 % | test |
| births per woman 15–50 | 0.0508 | 0.0510 | 0.0493 | 0.0482 | test |
| deaths per person | 0.0079 | 0.0081 | 0.0080 | 0.0091 | test |
| marriages per adult | 0.0170 | 0.0169 | 0.0157 | 0.0166 | test |
| divorces per married | 0.0156 | 0.0154 | 0.0156 | 0.0147 | test |
| households 1 / 2 / 3 / 4 / 5+ persons | 24.2 / 30.7 / 18.5 / 15.3 / 11.3 % | 27.6 / 32.5 / 16.4 / 13.5 / 10.1 % | 25.9 / 30.2 / 18.2 / 15.0 / 10.6 % | 28.6 / 32.1 / 16.0 / 13.3 / 10.1 % | test |
| households with 0 / 1 / 2 / 3+ cars | 8.4 / 31.7 / 37.3 / 22.7 % | 8.7 / 32.4 / 36.5 / 22.4 % | 8.4 / 32.8 / 35.8 / 23.1 % | 8.7 / 33.5 / 35.8 / 22.1 % | test |
| dwelling vacancy (all dwellings) | 2.9 % | — | 3.1 % | — | test (no observed series) |
| unplaced in-migrant households / year | 2,683 | — | 23,291 | — | diagnostic |

Unplaced in-migrant households by year (seed mean, engine log, 2016–2023 simulation years), Maryland target counties / other regions:
108 / 1,179; 144 / 885; 205 / 1,717; 118 / 6,377; 195 / 13,292; 413 / 19,048; 1,462 / 23,952; 3,407 / 31,396. With permits imposed the
Maryland part is small; the growing total is in the regions outside Maryland (VA/PA/DE/WV regions, construction by the demand scaler).
Maryland counties short in 2024 (population / PEP): Carroll 0.944 and Prince George's 0.975, both at 0 % model vacancy although built =
permits (1.000); Queen Anne's, Cecil, Wicomico now 1.000 (previous run: 0.962–0.996). County-to-county commuting (seed 1, 2018) vs ACS
2016–20: correlation of counts 0.995, 52 % of the 148 pairs ≥ 1,000 within ±20 % (`data/silo_final_commute_flows.csv`).

## 00a Previous final run (2026-10-29, superseded): r49 levers, construction by fixed 2016–19 county shares (outputs `*_pass7`): five seeds 2016–2024, calibration window 2017–20, out of sample 2021–24

Setup: base_v4 (consistent 2016 base, workplaces from the RTS workplace model), workplace choice rts3 with the ACS-anchored DC term
(engine 33b955a), job input from QCEW county growth × state JOLTS openings rates, yearly ACS employment rates by home state with the
end-of-year alignment (6fd0117, aade705), job-to-job changes at the JOLTS quits rate, local marriage market, SILO's original couple
rule with a vacant-dwelling fallback, population controls on the 2010–2020 intercensal + vintage-2025 series; levers of calibration
round 49 (`calibration/params_calib_r49.json`; `CALIBRATION.md`). Tables: `data/silo_final_tables.csv` (seed mean, 90 % band = mean
± 1.645 s.d., by year), `data/silo_final_tables_seeds.csv`, `data/silo_validation_oos_mean.parquet`; script
`validation/final_tables.py`. Article figure `5_reports/figures/fig_landuse.pdf` redrawn (calibration window = round 49).

**Imposed by construction (consistency checks, not tests):** county population (regional control), employment level (alignment
to the yearly ACS rates by state), vacancy share of jobs (QCEW × JOLTS job input).

| quantity (Maryland) | model 2017–20 | observed 2017–20 | model 2021–24 | observed 2021–24 | kind |
|---|---|---|---|---|---|
| population / PEP | 0.9995 | 1 | 0.996 | 1 | imposed |
| counties within ±2 % (of 24) | 24.0 | 24 | 22.1 (2024: 20.4) | 24 | imposed |
| employed share 16+ | 64.9 % | 65.3 % | 63.3 % | 65.2 % | imposed (1-year ACS by state; ACS 5-year shown) |
| vacant share of jobs (year end) | 4.2 % | 4.6 % | 4.6 % | 6.4 % | imposed |
| job-to-job changes / employed | 24.2 % | 25.2 % (JOLTS quits) | 23.9 % | 25.2 % | test |
| mean car time to work, min | 30.2 | 32.7 (ACS, all modes) | 30.4 | 31.2 | test |
| work in Maryland | 82.7 % | 82.7 % | 82.3 % | 84.1 % | test |
| same county (of in-state workplaces) | 61.9 % | ACS 65.9 % with WFH, 62.2 % without | 61.6 % | same | test |
| persons who moved | 12.2 % | 12.4 % | 12.2 % | 10.9 % | test |
| mover flows, correlation with ACS 2016–20 | 0.973 | 1 | 0.960 | 1 | test |
| movers staying in their region | 70.1 % | 68.9 % | 66.2 % | 68.9 % | test |
| births per woman 15–50 | 0.0507 | 0.0510 | 0.0494 | 0.0482 | test |
| deaths per person | 0.0079 | 0.0081 | 0.0080 | 0.0091 | test |
| marriages per adult | 0.0172 | 0.0169 | 0.0158 | 0.0166 | test |
| divorces per married | 0.0158 | 0.0154 | 0.0156 | 0.0147 | test |
| new dwellings / permits | 1.003 | 1 | 1.018 | 1 | test |
| households 1 / 2 / 3 / 4 / 5+ persons | 24.2 / 30.8 / 18.5 / 15.3 / 11.3 % | 27.6 / 32.5 / 16.4 / 13.5 / 10.1 % | 25.9 / 30.2 / 18.2 / 15.1 / 10.6 % | 28.6 / 32.1 / 16.0 / 13.3 / 10.1 % | test |
| households with 0 / 1 / 2 / 3+ cars | 8.4 / 31.6 / 37.3 / 22.7 % | 8.7 / 32.4 / 36.5 / 22.4 % | 8.4 / 32.8 / 35.8 / 23.1 % | 8.7 / 33.5 / 35.8 / 22.1 % | test |
| dwelling vacancy (all dwellings) | 2.8 % | — | 3.3 % | — | test (no observed series) |
| unplaced in-migrant households / year | 2,505 | — | 23,412 | — | diagnostic |

By year, unplaced in-migrant households: 1,401 / 1,092 / 1,815 / 5,709 / 13,474 / 18,512 / 25,765 / 35,896 (2017–2024): in the
test years the housing stock binds in the growing counties (construction follows permits), and counties within ±2 % fall to 20.4
by 2024. The employed share of 2021–22 follows the 2020 ACS 1-year (experimental) rates. Tenure is not in the SILO microdata and is
not reported.

---

## Earlier report (before 2026-10-29)

## 0 Current state (2026-10-27): workplace choice, job-to-job change, couples' households; calibration round 41

Engine `baltimore-2026` up to 4e82166: estimated workplace-choice model over all vacancies of the year (`jobchoice/ESTIMATION_REPORT.md`,
article table `5_reports/article/sections/est/est_jobchoice.tex`); households being formed search from their origin (the region-weight
cache keyed by the id −1 shared by all of them is fixed); every new couple forms its own household and chooses its dwelling with both
partners' commutes; commute-driven job-to-job change, yearly search probability 0.5·exp(0.02·(t − 38)), t = car time to the current job,
up to 5 offers each compared with the current job. γ = 0.02/min was set so that the 2016–2020 commute holds at its base level (not
estimated); the base 0.5 gives 24.6 % job-to-job changes a year in 2017–2019 against 25.2 % in the JOLTS quits rate for Maryland, an
upper bound because quits include exits from employment. Diagnosis of the commute drift: `jobchoice/DIAGNOSIS.md`. Calibration: rounds
36–41 in `CALIBRATION.md`; round 41 accepted (`calibration/params.json`). Five seeds 2016–2024 (`data/silo_validation_oos_s<k>.parquet`,
`oos_mean`); before = round-34 run (`*_pass4`), tables `data/silo_oos_before_after.csv` (`compare_passes.py _pass4`), headline numbers
`data/silo_headline_2024.csv` (`validation/headline_2024.py`). Figures redrawn 2026-10-27: `5_reports/figures/fig_landuse.pdf` (article),
`5_reports/figures/fig_v2_*.pdf`, `2_silo/figures/fig_s2_*.pdf`.

#### Maryland 2024, mean of five seeds [90 % band across seeds = mean ± 1.645 s.d.] (before: round-34 run)
| quantity | model | before | observed | criterion |
|---|---|---|---|---|
| population (24 counties) | 5,889,000 [5,879,000–5,898,000], 0.972 | 0.991 | 6,056,000 (PEP) | counties ±2 %: 12/24 (before 21), ±5 %: 19/24 (23) — **fail** |
| households | 2,354,000 [2,350,000–2,357,000], 0.996 | 0.975 | 2,363,000 (ACS 2020–24) | pass |
| new dwellings 2021–2024 | 90,200 [89,100–91,300], 1.159 | 1.212 | 77,791 (permits) | counties ±25 %: 12/24 (before 14) — fail |
| employed share of persons 16+ | 62.8 % [62.7–62.9] | 63.8 % | 65.2 % (ACS) | −2.4 pp |
| working in Maryland | 90.3 % [90.3–90.4] | 69.4 % | 84.1 % (ACS) | +6 pp, overshoots |
| mean car time to work | 26.1 min [26.0–26.2] | 46.9 | base 2016: 31.4; ACS all modes 31.2 | below base, overshoots |
| home-county share of MD workplaces | 69.9 % [69.8–70.0] | 54.2 % | 65.9 % (ACS 2016–20 commuting flows) | +4 pp |
| persons who moved (aged 1+) | 11.2 % [11.1–11.3] | 11.7 % | 10.8 % (ACS) | +0.4 pp |

Calibration window (round 41, 2017–2020, one seed): births 1.011, deaths 0.962 (unchanged), marriages 0.995, divorces 1.008,
construction 1.000 with all counties within ±25 %, moves 0.968, leaving home 0.976; employment men 20–24 1.051, women 20–24 1.061,
men 25–34 1.020 (accepted residuals).

Findings:
- The commute no longer drifts outward; it now overshoots inward in the test years: the job-to-job change (one search in four a year)
  keeps moving workers to nearer vacancies, and the vacancy pool grows from 1 % to 4.7 % of jobs in 2021–2024, so the mean car time
  falls from 31.4 (2016) to 26.1 min and 90 % of Maryland residents work in Maryland (ACS 84 %). γ was set on 2016–2020 only.
- Home-county share: the right benchmark is the ACS (65.9 % for 2016–2020, worker-reported usual workplace, the table the base
  assignment was fitted to); the model's 2016 base equals it. LODES (46.5–48 %) counts jobs, not workers, and places the jobs of
  multi-establishment employers and some public employers by imputation or administrative address, which spreads home–work pairs
  across counties; LODES remains the benchmark for jobs by workplace and the in-Maryland share is checked against both. The
  workplace-choice model was estimated on LODES flows, so its county-crossing term (−0.28) is probably too weak against the ACS.
- Population: counties fall short of the PEP path (Prince George's 0.927, Cecil 0.931, Wicomico 0.935, Carroll 0.937, Caroline
  0.938; 12 counties outside ±2 %). Every couple now needs a vacant dwelling; couples that find none leave the model area (851 in
  2016, 4,500–10,700 a year afterwards, seed 1), and households grow faster than in the round-34 run (0.996 vs 0.975 of the ACS).
- Residuals as before: births 6–9 % high and deaths 3–18 % low in the test years (static tables); marriages 10–13 % low in 2021–2024;
  young employment high (men and women 20–24: 79–80 % vs 70 %), older employment low.
- New hires and couples (`jobchoice/DIAGNOSIS.md` section 6): entrants still take the vacancies left after job changers (2019 smoke
  test: 54.6 min vs 25.8 for unchanged workers); a worker who keeps the job in a couple's new household goes from 26 to 58 min on
  average because partners are matched without geography; the job-to-job change shortens these commutes in later years.

---

## Previous run (2026-10-26, round 34)

Status 2026-10-26: engine of the stage-2 completion (`CALIBRATION.md`, commits up to 4d854e6), calibration stopped at round 34
(19 of 22 levers within ±2 %), five-seed out-of-sample test 2016–2024 with the values used in round 34. Data files are the source of
every number: `data/silo_calibration_final.csv` (round 34; round 20 kept as `data/silo_calibration_final_r20.csv`),
`calibration/calibration_log.csv`, `data/silo_validation_calib_r34.parquet` (calibration window), `data/silo_validation_oos_s<k>.parquet`
and `data/silo_validation_oos_mean.parquet` (out-of-sample, seed mean and seed s.d.). "Before" below is the previous five-seed test
(2026-10-23 report, archived at the end of this file; `data/silo_validation_oos_*_pass3.parquet`); before/after tables
`data/silo_oos_before_after.csv` (`validation/compare_passes.py _pass3`). Figures: `figures/fig_s2_*.pdf` (`figures_stage2.py oos_mean`)
and `5_reports/figures/fig_v2_*.pdf` (`5_reports/figures_validation.py 2 --silo oos_mean`), all redrawn 2026-10-26.

### 1 Design
- Engine: open-source SILO (Maryland use case) with the extensions listed in `CALIBRATION.md`; 44 regions (24 Maryland counties + 20);
  population control by region; job control by zone and type; market vacancies only; estimated residential location model.
- Calibration window 2016–2020, one seed, damped ratio updates with secant steps for moves, construction and leaving home
  (`calibration/calibrate.py`); test window 2021–2024, five seeds, nothing re-tuned. Targets: `VALIDATION.md`; data: `data_sources.md`.
- Moves are validated person-based: Maryland residents aged 1+ whose dwelling changed or who came from outside the model area, against
  ACS persons aged 1+ with `MIG ≠ 1`.

### 2 Calibration result (round 34, 2017–2020 means)
| component | model / observed |
|---|---|
| births per woman 15–50 | 0.998 |
| marriages per adult | 1.001 |
| divorces per married | 0.995 |
| persons who moved per year (aged 1+) | 0.985 |
| new dwellings vs permitted units (Maryland) | 1.001 |
| adults 18–34 not living with parents | 0.988 |
| employed share by age band × sex, 16 cells | 13 within ±2 %; outside: men 20–24 1.045, women 16–19 0.913, women 20–24 1.054 |
| car ownership, county cells within ±5 pp | 100 % |
| county population 2020 within ±2 % / ±5 % | 23 / 24 counties, 24 / 24 |
| composition cells (county × bin) within ±5 pp, 2020 | 95.5 % |
| construction by county 2017–2020 within ±25 % | 24 / 24 |

The three employment cells outside ±2 % are reported as residuals (decision 2026-10-26, `CALIBRATION.md`).

### 3 Out-of-sample 2016–2024 (seed means of five seeds)

##### Maryland totals, 2024
| quantity | model | observed | ratio |
|---|---|---|---|
| population (24 counties) | 6,000,000 | 6,056,000 (PEP growth path) | 0.991 |
| households | 2,305,000 (seeds 2,299,000–2,311,000) | 2,363,000 (ACS 2020–24, 5-year) | 0.975 |

The 2016 base has 2,179,000 households; the ACS 5-year count is a 2020–2024 average.

##### County population (24 Maryland counties), within ±2 % / ±5 % of the PEP growth path

| year | before ±2 % | before ±5 % | after ±2 % | after ±5 % | after: counties outside ±2 % (ratio) |
|---|---|---|---|---|---|
| 2021 | 20/24 | 23/24 | 23/24 | 24/24 | Calvert (0.977) |
| 2022 | 19/24 | 23/24 | 23/24 | 24/24 | Calvert (0.962) |
| 2023 | 18/24 | 22/24 | 23/24 | 24/24 | Calvert (0.952) |
| 2024 | 18/24 | 22/24 | 21/24 | 23/24 | Calvert (0.948), Prince George's (0.972), Baltimore County (0.975) |

Seed s.d. of the 2024 county populations: Calvert 460 persons, Prince George's 15,700, Baltimore County 8,900.

##### Composition, Maryland county × bin cells within ±5 pp of the ACS

| attribute | 2021 before | 2021 after | 2024 before | 2024 after |
|---|---|---|---|---|
| age band | 94% | 100% | 90% | 99% |
| sex | 100% | 100% | 100% | 100% |
| employed (16+) | 67% | 75% | 79% | 67% |
| household size | 79% | 92% | 77% | 88% |
| cars | 100% | 100% | 99% | 98% |
| income class (2016 $) | 94% | 97% | 85% | 89% |
| adults 18-34 living with parents | 71% | 71% | 62% | 54% |

##### Events, Maryland, model (before → after) and observed

| event | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| births per woman 15-50 | 0.0515 → 0.0512 (0.0492) | 0.0515 → 0.0509 (0.0475) | 0.0517 → 0.0508 (0.0486) | 0.0520 → 0.0506 (0.0476) |
| deaths per person | 0.0078 → 0.0078 (0.0092) | 0.0079 → 0.0079 (0.0096) | 0.0081 → 0.0082 (0.0093) | 0.0083 → 0.0084 (0.0087) |
| marriages per adult | 0.0157 → 0.0152 (0.0164) | 0.0154 → 0.0148 (0.0166) | 0.0153 → 0.0146 (0.0166) | 0.0153 → 0.0144 (0.0166) |
| divorces per married | 0.0148 → 0.0149 (0.0151) | 0.0149 → 0.0153 (0.0146) | 0.0149 → 0.0156 (0.0146) | 0.0150 → 0.0156 (0.0146) |
| persons who moved, aged 1+ | 0.1126 → 0.1167 (0.1117) | 0.1133 → 0.1197 (0.1082) | 0.1144 → 0.1191 (0.1082) | 0.1144 → 0.1175 (0.1082) |

New dwellings 2021–2024 vs units permitted: before 87,962 / 77,791 = 1.131 (5/24 counties within ±25 %); after 94,268 / 77,791 =
1.212 (14/24 counties within ±25 %).

##### Statewide income class (2016 $), Maryland households (model before / after / ACS)

| bin | 2016 | 2020 | 2024 |
|---|---|---|---|
| <25k | 12.7% / 12.7% / 14.5% | 13.6% / 14.2% / 14.2% | 14.4% / 16.2% / 14.8% |
| 25-50k | 18.4% / 18.4% / 17.5% | 15.1% / 15.9% / 16.5% | 14.1% / 15.3% / 16.6% |
| 50-75k | 18.0% / 18.0% / 16.3% | 15.0% / 15.4% / 15.9% | 13.8% / 14.6% / 16.0% |
| 75-100k | 12.8% / 12.8% / 13.3% | 12.9% / 13.0% / 13.5% | 12.2% / 12.4% / 13.3% |
| 100-150k | 19.1% / 19.1% / 18.2% | 19.4% / 19.0% / 18.3% | 18.9% / 18.1% / 17.9% |
| ≥150k | 19.0% / 19.0% / 20.2% | 23.9% / 22.6% / 21.6% | 26.7% / 23.4% / 21.4% |

##### Household size and workers per household, Maryland households (model before / after / ACS)

| bin | 2020 | 2024 |
|---|---|---|
| size 1 | 25.5% / 24.2% / 27.8% | 27.2% / 25.5% / 28.7% |
| size 2 | 29.1% / 30.3% / 32.4% | 28.1% / 29.8% / 32.0% |
| size 3 | 18.3% / 18.8% / 16.2% | 18.0% / 18.4% / 16.0% |
| size 4 | 15.6% / 15.7% / 13.4% | 15.5% / 15.5% / 13.3% |
| size 5+ | 11.4% / 11.0% / 10.2% | 11.2% / 10.7% / 10.0% |
| 0 workers | 19.5% / 21.9% / 21.8% | 20.1% / 23.7% / 22.1% |
| 1 worker | 34.2% / 33.7% / 37.3% | 33.7% / 34.1% / 37.2% |
| 2 workers | 34.8% / 32.2% / 31.9% | 33.0% / 29.8% / 31.6% |
| 3+ workers | 11.4% / 12.2% / 9.0% | 13.1% / 12.4% / 9.2% |

##### Employment, Maryland (model before / after / ACS; all 16 cells in `data/silo_oos_before_after.csv`)

| cell | 2020 | 2024 |
|---|---|---|
| employed share of persons 16+ | 66.5% / 65.1% / 65.0% | 67.7% / 63.8% / 65.2% |
| men 16–19 | 13.2% / 30.1% / 29.2% | 18.8% / 37.1% / 30.1% |
| men 20–24 | 56.1% / 77.2% / 69.8% | 66.1% / 81.3% / 69.6% |
| women 16–19 | 14.6% / 30.9% / 33.2% | 20.7% / 38.1% / 35.0% |
| women 20–24 | 58.5% / 77.1% / 69.3% | 68.2% / 80.7% / 69.9% |
| men 25–34 | 89.5% / 89.2% / 85.9% | 94.2% / 91.3% / 86.6% |
| women 55–64 | 70.4% / 64.2% / 64.8% | 69.7% / 61.6% / 66.0% |
| women 65–74 | 29.9% / 25.2% / 26.9% | 28.6% / 23.3% / 28.2% |

##### Jobs, commutes and mover flows (model before → after; observed)

| quantity | 2020 | 2024 |
|---|---|---|
| Maryland-resident jobs in Maryland located in the home county (LODES) | 51.4% → 59.0% (47.0%) | 42.8% → 54.2% (46.5%) |
| Maryland-resident workers employed in Maryland (ACS) | 69.7% → 74.7% (83.3%) | 61.7% → 69.4% (84.1%) |
| travel time to work, mean, min (model: car peak skim; ACS: all modes) | 45.4 → 41.8 (31.9) | 53.1 → 46.9 (31.2) |
| travel time to work, median, min | 34.6 → 29.2 (30.0) | 42.3 → 32.7 (25.0) |
| vacant share of jobs (JOLTS openings rate) | 3.5% → 1.0% (5.0%) | 5.1% → 3.2% (5.1%) |
| moving households staying in their region (ACS flows 2016–20) | 17.8% → 62.0% (68.9%) | 17.4% → 57.0% (68.9%) |
| Maryland movers moving to another state | 33.1% → 12.0% (7.5%) | 31.0% → 13.3% (7.5%) |
| correlation of region-to-region mover flows with the ACS (all pairs) | 0.621 → 0.957 | 0.625 → 0.956 |

Summary:
- Totals: Maryland population 0.991 of the PEP path in 2024; 21/24 counties within ±2 % and 23/24 within ±5 % (before 18 and 22);
  Calvert 0.948, Prince George's 0.972, Baltimore County 0.975. Households 0.975 of the ACS 2020–24 count.
- Income: households at or above $150k 23.4 % in 2024 against 21.4 % (before 26.7 %); below $25k 16.2 % against 14.8 % (before
  14.4 %); income cells within ±5 pp 89 % (before 85 %).
- Composition: age 99 % of cells within ±5 pp (before 90 %), household size 88 % (77 %); employed 67 % (79 %) and adults with parents
  54 % (62 %) are lower than before.
- Employment: 63.8 % of persons 16+ against 65.2 % in 2024 (before 67.7 %); persons 16–24 are employed 3–12 pp above the ACS, persons
  55+ 1–5 pp below it.
- Moves 11.7–12.0 % in 2021–2024 against 10.8–11.2 % (before 11.3–11.4 %); births 5.06–5.12 vs 4.75–4.92 per 100 women; deaths
  0.78–0.84 % vs 0.87–0.96 %; marriages 7–13 % low; divorces 7 % high.
- Commutes: home-county work share 54 % against 47 % (before 43 % and falling); car peak skim time mean 46.9 / median 32.7 min against
  the all-mode ACS time 31.2 / 25.0 min; 69 % of Maryland-resident workers work in Maryland against 84 %.

### 4 Residuals (stated, not tuned away)
1. Young employment (calibration residual): men 20–24, women 16–19 and women 20–24 end calibration outside ±2 % (1.045, 0.913,
   1.054), and the 16–24 cells drift upward in the test years (2024: 37–38 % vs 30–35 % at 16–19, 81 % vs 70 % at 20–24) while
   persons 55+ fall below the ACS; the statewide share ends 1.4 pp low.
2. Moves: the rate meets the 2017–2020 level but does not follow the decline of the ACS rate after 2020 (2024: 11.7 % vs 10.8 %);
   movers leave Maryland more often (13 % vs 7.5 %) and stay in their region less often (57 % vs 69 %) than in the ACS flows.
3. Households: 2.5 % fewer than the ACS 5-year count, too few one- and two-person households (25.5 % and 29.8 % vs 28.7 % and
   32.0 %) and too many with three or more workers (12.4 % vs 9.2 %); households at or above $150k +2.0 pp.
4. Construction: 1.21 × the permitted units in 2021–2024, 14/24 counties within ±25 %; Calvert, Prince George's and Baltimore County
   fall 2.5–5 % short of the PEP path by 2024.
5. Commutes: too many out-of-state workplaces and longer car skim times than the reported all-mode times.
6. The static fertility, mortality and marriage tables miss the 2020–2024 trends.

---

### Archive: report of 2026-10-23 (engine of 2026-10-22, round-20 values; the "before" columns above)

(File names in this archive refer to that run: its out-of-sample tables are now `data/silo_validation_oos_*_pass3.parquet`, its round-20 calibration values `data/silo_calibration_final_r20.csv`.)

Status 2026-10-23: engine with the move and income fixes of 2026-10-22 (commits a09dde0–f099285 and the job-search commits, see
`CALIBRATION.md`), check rounds 17–20 on 2016–2020, five-seed out-of-sample test 2016–2024 complete. Data files are the source of every
number: `data/silo_calibration_final.csv` (round 20), `calibration/calibration_log.csv`, `data/silo_validation_calib_r20.parquet`
(calibration window), `data/silo_validation_oos_s<k>.parquet` and `data/silo_validation_oos_mean.parquet` (out-of-sample, seed mean and
seed s.d.); the run before the fixes is kept as `*_pass2` (`data/silo_validation_oos_*_pass2.parquet`, person-based moves of those runs in
`data/silo_moves_person_pass2.csv`); before/after tables `data/silo_oos_before_after.csv` (`validation/compare_passes.py`); microdata
diagnostics `validation/diagnostics/`. Figures `figures/fig_s2_*.pdf` are from the earlier run: `figures_stage2.py` now stops at the
font-size check of `5_reports/paperstyle.py` (county labels 6 pt) and has to be adjusted before they are redrawn.

### 1 Design
- Engine: open-source SILO (Maryland use case) with the extensions listed in `CALIBRATION.md`; 44 regions (24 Maryland counties + 20);
  population control by region (first pass at the start of the year aiming at the next year's target, second pass at the end of the
  year closing the remaining gap); job control by zone and type; market vacancies only.
- Calibration window 2016–2020, one seed, damped ratio updates (`calibrate.py`; round 20 started at a secant value for the move lever);
  test window 2021–2024, five seeds, nothing re-tuned. Targets and benchmarks: `VALIDATION.md`; observed data: `data_sources.md`.
- Moves are validated person-based: Maryland residents aged 1+ whose dwelling changed or who came from outside the model area, against
  ACS persons aged 1+ with `MIG ≠ 1` (previously households whose dwelling changed, against all persons incl. infants).

### 2 Calibration result (round 20, 2017–2020 means)
| component | model / observed |
|---|---|
| births per woman 15–50 | 1.005 |
| marriages per adult | 1.000 |
| divorces per married | 0.997 |
| persons who moved per year (aged 1+) | 0.962 (by year 11.8, 12.0, 11.7, 12.1 % vs 13.1, 12.5, 12.2, 11.7 %) |
| new dwellings vs permitted units (Maryland) | 0.971 |
| adults 18–34 not living with parents | 0.980 |
| employed share of persons 16+ (county mean) | 0.983 |
| car ownership, county cells within ±5 pp | 100 % |
| county population 2020 within ±2 % / ±5 % | 19 / 24 counties, 23 / 24 |
| composition cells (county × bin) within ±5 pp, 2020 | 91.0 % |
| construction by county 2017–2020 within ±25 % / ±50 % | 8 / 24, 11 / 24 (bounded by the development-capacity input) |

### 3 Out-of-sample 2016–2024: before and after the fixes (seed means; seed s.d. of the county ratios ≤ 0.0054)

##### County population (24 Maryland counties), share within ±2 % / ±5 % of PEP growth

| year | before ±2 % | before ±5 % | after ±2 % | after ±5 % | after worst county (ratio) |
|---|---|---|---|---|---|
| 2021 | 20/24 | 23/24 | 20/24 | 23/24 | 24017 (0.943) |
| 2022 | 21/24 | 23/24 | 19/24 | 23/24 | 24017 (0.944) |
| 2023 | 22/24 | 22/24 | 18/24 | 22/24 | 24017 (0.942) |
| 2024 | 21/24 | 22/24 | 18/24 | 22/24 | 24017 (0.940) |

##### Composition, Maryland county × bin cells within ±5 pp of the ACS

| attribute | 2021 before | 2021 after | 2024 before | 2024 after |
|---|---|---|---|---|
| age band | 99% | 94% | 94% | 90% |
| sex | 100% | 100% | 100% | 100% |
| employed (16+) | 71% | 67% | 71% | 79% |
| household size | 78% | 79% | 70% | 77% |
| cars | 100% | 100% | 100% | 99% |
| income class (2016 $) | 79% | 94% | 73% | 85% |
| adults 18-34 living with parents | 62% | 71% | 54% | 62% |

##### Events, Maryland, model (before → after) vs observed

| event | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| births per woman 15-50 | 0.0512 → 0.0515 (0.0492) | 0.0512 → 0.0515 (0.0475) | 0.0512 → 0.0517 (0.0486) | 0.0515 → 0.0520 (0.0476) |
| deaths per person | 0.0079 → 0.0078 (0.0092) | 0.0081 → 0.0079 (0.0096) | 0.0083 → 0.0081 (0.0093) | 0.0085 → 0.0083 (0.0087) |
| marriages per adult | 0.0157 → 0.0157 (0.0164) | 0.0154 → 0.0154 (0.0166) | 0.0154 → 0.0153 (0.0166) | 0.0154 → 0.0153 (0.0166) |
| divorces per married | 0.0152 → 0.0148 (0.0151) | 0.0154 → 0.0149 (0.0146) | 0.0154 → 0.0149 (0.0146) | 0.0156 → 0.0150 (0.0146) |
| persons who moved, aged 1+ | 0.1992 → 0.1126 (0.1117) | 0.2036 → 0.1133 (0.1082) | 0.2084 → 0.1144 (0.1082) | 0.2112 → 0.1144 (0.1082) |

new dwellings vs permits 2021-24 (before): 94345 / 76632 = 1.231

new dwellings vs permits 2021-24 (after): 87962 / 76632 = 1.148

##### Statewide income class (2016 $), Maryland households (model before / after / ACS)

| bin | 2016 | 2020 | 2024 |
|---|---|---|---|
| <25k | 12.7% / 12.7% / 14.5% | 15.9% / 13.6% / 14.2% | 19.5% / 14.4% / 14.8% |
| 25-50k | 18.4% / 18.4% / 17.5% | 17.6% / 15.1% / 16.5% | 18.4% / 14.1% / 16.6% |
| 50-75k | 18.0% / 18.0% / 16.3% | 16.4% / 15.0% / 15.9% | 15.9% / 13.8% / 16.0% |
| 75-100k | 12.8% / 12.8% / 13.3% | 13.3% / 12.9% / 13.5% | 12.8% / 12.2% / 13.3% |
| 100-150k | 19.1% / 19.1% / 18.2% | 18.4% / 19.4% / 18.3% | 16.9% / 18.9% / 17.9% |
| ≥150k | 19.0% / 19.0% / 20.2% | 18.4% / 23.9% / 21.6% | 16.5% / 26.7% / 21.4% |

##### Statewide household size, Maryland households (model before / after / ACS)

| bin | 2016 | 2020 | 2024 |
|---|---|---|---|
| 1 | 23.1% / 23.1% / 27.0% | 25.0% / 25.5% / 27.8% | 27.0% / 27.2% / 28.7% |
| 2 | 31.6% / 31.6% / 32.7% | 29.4% / 29.1% / 32.4% | 28.3% / 28.1% / 32.0% |
| 3 | 18.3% / 18.3% / 16.7% | 18.3% / 18.3% / 16.2% | 17.9% / 18.0% / 16.0% |
| 4 | 15.1% / 15.1% / 13.6% | 15.8% / 15.6% / 13.4% | 15.5% / 15.5% / 13.3% |
| 5+ | 11.8% / 11.8% / 10.0% | 11.5% / 11.4% / 10.2% | 11.2% / 11.2% / 10.0% |

Summary:
- Moves: the modelled rate no longer rises. Persons who moved 11.3–11.4 % in 2021–2024 against 10.8–11.2 % observed (1.01–1.06; before
  19.9–21.1 %, rising every year). The household-based share is flat at 8.2–8.5 %.
- Income: households below $25k 14.4 % in 2024 against 14.8 % (before 19.5 %, rising 0.8 pp a year). Households at or above $150k now
  rise too fast: 26.7 % in 2024 against 21.4 % (before 16.5 %, falling); the $25–75k classes are 2–3 pp low (see 4.2).
- Composition: income cells within ±5 pp 85 % (before 73 %), household size 77 % (70 %), employed 79 % (71 %), adults with parents 62 %
  (54 %); age 90 % (94 %).
- County totals: 18/24 counties within ±2 % in 2024 (before 21/24), 22/24 within ±5 %; six counties fall short of their target
  (Charles 0.940, Frederick 0.946, St. Mary's 0.951, Somerset 0.959, Calvert 0.972, Wicomico 0.978): fewer moves release fewer
  dwellings and construction is lower (new dwellings 1.15 × permits 2021–2024, before 1.23 ×), so in-migrants find no vacancy there.
- Events: births 5.15–5.20 % vs 4.75–4.92 %, deaths 0.78–0.83 % vs 0.87–0.96 % (static tables, no 2020–2022 mortality shock);
  marriages −6 to −8 %, divorces within 3 %.

### 4 Residuals and their mechanisms (stated, not tuned away)
1. Moves: the move-or-not shift lever rose from 0.058 to 0.40 because a household now moves only to a better dwelling; the rate
   matches the observed level and no longer drifts, but does not follow the 2017–2024 decline of the ACS rate (13.1 → 10.8 %). The
   region choice of a moving household ignores its current location (before the fixes 35 % of Maryland movers left the state, ACS
   2016–20: 21 % of movers came from another state).
2. Households ≥ $150k (seed 1, 2024): with the income rules fixed, person incomes by age agree with the ACS (employed medians within 10 % for
   ages 21–65; mapping every person's income to the ACS distribution of their age band lowers the model's share ≥ $150k only from 26.7
   % to 25.0 %). The remaining excess is household composition: employed share of persons 16+ 67.7 % vs 65.2 % in 2024 (the
   calibration target is the county mean, which the lever meets at 0.98), and households with three or more workers 13.1 % vs 9.2 %
   (≥ $150k within each workers class agrees: 0 workers 5.8 vs 5.7 %, 1: 14.3 vs 11.4 %, 2: 37.8 vs 36.3 %). Not-employed persons
   aged 26–65 still have higher incomes than in the ACS (medians $3,000–22,000 vs $0–10,000).
3. Young adults leaving home always form a one-person household (no joining of existing households); 74 % of these households had less
   than $25k before the fixes, against 13.5 % of ACS householders aged 25–29.
4. Construction by county follows the engine's vacancy response and the development-capacity file; the county scalers raise the
   total to the permitted level but the allocation remains within a factor of two for half the counties.
5. The job market (check round 19): hires still have longer car commutes than base-year workers (median 48 vs 26 min) because the vacant jobs are where
   the job control places them; the share of Maryland workers employed in their home county falls from 55 % to 39 % by 2020 (LODES:
   49 % → 47 %).
6. The static fertility and mortality tables miss the 2020–2024 shocks and trends; both are reported as validation findings.
