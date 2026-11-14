# Input data

ORIOLE uses public data, with two exceptions: the Regional Travel Survey and the MSTM zone system and skims, which
are obtained by request from their agencies.

## Data by stage

Input: used as given. Target: a parameter is adjusted to match it. Test: not used to estimate or calibrate the
component tested.

| Dataset (size) | Source, years | Used for |
|---|---|---|
| **1. Synthetic population** | | |
| ACS PUMS 5-year file (253,029 households) | Census 2012–16 | Training of the synthesiser; held-out test |
| Census block counts of housing units | Census 2010, 2020 | Input: placing households in zones |
| **2. Land use and workplaces** | | |
| ACS PUMS, households that moved (29,277) | Census 2014–21 | Estimation of residential location (2014–18); test (2019–21) |
| ACS PUMS, households (114,078) | Census 2014–18 | Estimation of car ownership |
| ACS PUMS 1-year files | Census 2016–24 | Calibration targets; tests |
| Population estimates | Census 2010–24 | Input: county totals; test of births, deaths |
| LODES jobs and commute flows | Census 2016–23 | Input: jobs by zone; test of commute flows |
| QCEW jobs by county | BLS 2016–24 | Input: jobs in 2024 |
| JOLTS job openings and quits | BLS 2016–24 | Input: vacancies; test of quits |
| Building permits | Census 2016–24 | Input: new dwellings |
| ACS county-to-county flows | Census 2014–20 | Test of commute and mover flows |
| **3. Schools** | | |
| CCD and PSS school directories (4,260 schools) | NCES 2023–25 | Input: schools and enrolment |
| IPEDS colleges (192) | NCES 2023–24 | Input: colleges and enrolment |
| School attendance boundaries | NCES 2015–16 | Input: attendance zones |
| **4. Activities and travel** | | |
| Regional Travel Survey (10,889 / 10,899 households) | MWCOG, BMC 2017–18 | Estimation (one half); test (other half) |
| ATUS time-use diaries (279) | BLS 2021–24 | Test of activities and start times |
| NHTS travel diaries | FHWA 2017 | Test of activities and trip lengths |
| **5. Networks and traffic** | | |
| MSTM car skims (1,588 zones) | MDOT, base year | Input: car times |
| OpenStreetMap road network | OSM 2026 | Input: roads, lanes, posted speeds |
| GTFS transit timetables | 18 operators, 2026 | Input: transit network and skims |
| Traffic counts (3,797 stations; 3,437 matched to links, 2,308 on the mainline) | MDOT SHA 2024 | Test of daily volumes |
| TMAS hourly counts (21 stations) | FHWA 2024 | Test of hourly volumes |

## The travel survey and its two halves

The 2017/18 Regional Travel Survey of the Baltimore and Washington regions is a one-day household travel diary of
21,788 households and 163,290 trips, sampled by home location. Its households are split at random, stratified by
home county and household size:

- the **estimation half** (10,889 households) estimates every survey-based model and every activity distribution;
- the **hold-out half** (10,899 households) enters no estimation or calibration step and is used for validation.

## Matching survey locations to zones

Survey locations are recorded by traffic zone or census tract, which can cover several model zones. They are matched
to model zones through census blocks; in estimation, the probability of a survey location is the sum of the
probabilities of its model zones, weighted by housing units (homes), school enrolment (schools) or jobs (other
locations).

## Where to get each source

The download page, files, years and variables of every source are listed, model by model, in the instruction sheet
of each folder of the estimation package (see [Estimation package](../developers/estimation-package.md)).
