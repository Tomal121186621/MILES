# Input data in detail

These pages document the data that MILES reads: for each dataset a short description, the codebook of the variables
the models use, descriptive statistics computed from the files, and the processing applied in the code. Bracketed
numbers refer to the sources on the [Data](../inputs.md#sources) page.

Two datasets are released by the agencies on request and are not redistributed: the 2017/18 Regional Travel Survey and
the zones and skims of the Maryland Statewide Transportation Model. For these, the pages give aggregate statistics only
(weighted shares, means and counts); no record-level or zone-level values are shown, and cells based on fewer than 10
unweighted records are suppressed (shown as —).

Statistics are unweighted counts of records unless a table says *weighted*; weighted shares use the survey weights
named in the codebook. Percentages are rounded to one decimal and may not sum to 100.

## Overview

| Dataset | Unit of observation | Records | Variables used | Years | Coverage | Page |
|---|---|---:|---:|---|---|---|
| ACS PUMS 2012–16, 5-year | Household; person | 253,029 households; 626,201 persons | 30 | 2012–16 | Model-area PUMAs of DC, DE, MD, PA, VA, WV | [ACS Public Use Microdata Sample](acs-pums.md) |
| ACS PUMS 2014–18, 5-year | Household; person | 114,078 Maryland households (car ownership) | 13 | 2014–18 | Six states (controls); Maryland (car ownership, test) | [ACS Public Use Microdata Sample](acs-pums.md) |
| ACS PUMS mover households | Household | 18,983 (2014–18); 10,294 (2019–21) | 27 | 2014–18; 2019–21 | Six states, PUMAs touching the zone system | [ACS Public Use Microdata Sample](acs-pums.md) |
| ACS PUMS 2015–19, 5-year (interview years 2017–19) | Person (commuter) | 227,521 commuters | 8 | 2017–19 | DC, MD, VA, WV | [ACS Public Use Microdata Sample](acs-pums.md) |
| ACS PUMS 1-year | Person; household (2024) | 62,777 Maryland persons (2024) | 12 | 2016–24 | Six states (employment); Maryland (2024 benchmarks) | [ACS Public Use Microdata Sample](acs-pums.md) |
| Regional Travel Survey 2017/18 † | Household, person, trip, tour | 21,788 households; 41,914 persons; 163,290 trips; 54,149 closed tours | 84 | 2017/18 | Baltimore and Washington regions | [Regional Travel Survey 2017/18](travel-survey.md) |
| LODES workplace area characteristics | Census block × year | 32,239 Maryland blocks (2016) | w_geocode, C000, CNS01–CNS20 | 2016–2023 | Maryland; five other states 2017, 2022 | [Employment: LODES, QCEW, JOLTS](employment.md#lodes-workplace-area-characteristics) |
| LODES origin–destination flows | Home block × workplace block | 2,032,069 pairs (2016) | h_geocode, w_geocode, S000 | 2016–2023 | Maryland residents and workplaces | [Employment: LODES, QCEW, JOLTS](employment.md#lodes-origindestination-flows) |
| Quarterly Census of Employment and Wages | County × year | 594 county files | annual_avg_emplvl, avg_annual_pay | 2016–2024 | 66 counties, six states | [Employment: LODES, QCEW, JOLTS](employment.md#quarterly-census-of-employment-and-wages) |
| Job Openings and Labor Turnover Survey | State × month | 648 state-months | openings rate, quits rate | 2016–2024 | Six states | [Employment: LODES, QCEW, JOLTS](employment.md#job-openings-and-labor-turnover-survey) |
| Population estimates and components of change | County × year | 283 counties, six states | POPESTIMATE, BIRTHS, DEATHS | 2010–2025 | Six states | [Population, housing and neighbourhood controls](landuse-controls.md#population-estimates-and-components-of-change) |
| Redistricting data, housing units | Census block | 145,247 (2010); 83,827 (2020) | H1 total, occupied, vacant | 2010, 2020 | Maryland | [Population, housing and neighbourhood controls](landuse-controls.md#redistricting-data-housing-units-by-block) |
| Building Permits Survey | County × year | 216 Maryland county-years | units by structure size | 2016–2024 | Maryland | [Population, housing and neighbourhood controls](landuse-controls.md#building-permits-survey) |
| County-to-county commuting flows | County pair | 122,335 | workers | 2016–2020 | United States | [Population, housing and neighbourhood controls](landuse-controls.md#county-to-county-commuting-flows) |
| County-to-county migration flows | County pair | 282,463; 264,203 | movers | 2014–2018, 2016–2020 | United States | [Population, housing and neighbourhood controls](landuse-controls.md#county-to-county-migration-flows) |
| Stanford Education Data Archive | County × subgroup | 3,214 counties (all students) | cs_mn_grd_eb, tot_asmts | 2009–2018 pooled | United States | [Population, housing and neighbourhood controls](landuse-controls.md#stanford-education-data-archive) |
| Uniform Crime Reporting, county offences | County × year | 61 counties (2016) | violent, property offences | 2016 | Zone-system counties | [Population, housing and neighbourhood controls](landuse-controls.md#crime-by-county) |
| Consumer Price Index (CPI-U) | Year | 11 | annual average index | 2014–2024 | United States | [Population, housing and neighbourhood controls](landuse-controls.md#consumer-price-index) |
| Common Core of Data, public schools | School | 7,708 | 11 | 2024–25 | Six states | [Schools and colleges](schools.md) |
| Private School Universe Survey | School | 2,985 | 12 | 2023–24 | Six states | [Schools and colleges](schools.md) |
| IPEDS institutions and enrolment | Institution | 649 | 9 | 2023–24 | Six states | [Schools and colleges](schools.md) |
| School Attendance Boundary Survey | Attendance zone | 6,367 | 6 | 2015–16 | Six states | [Schools and colleges](schools.md) |
| School inventory (combined) | School and grade band | 6,749 | 11 | 2023–25 | Model zones | [Schools and colleges](schools.md) |
| MSTM zone system (restricted) | Zone | 1,588 | 9 | base year | MD, DC and parts of DE, PA, VA, WV | [Zones, skims and census geography](zones-geography.md) |
| Car and transit skims | Zone pair | 2,521,744 per matrix | 3 | base year; 2024 | Zone system | [Zones, skims and census geography](zones-geography.md) |
| TIGER/Line tracts, Gazetteer, tract–PUMA and PUMA crosswalks | Census tract; PUMA | 7,412 tracts | 9 | 2010 | Six states | [Zones, skims and census geography](zones-geography.md) |
| OpenStreetMap road network (MATSim network 2024) | Link | 469,434 car links | highway, maxspeed, lanes, oneway, name | 2026 extract (network of 2024) | Central Maryland and the Maryland suburbs of Washington | [Road network](road-network.md) |
| MDOT SHA functional class, lane mileage, speed-limit signs | Segment; sign | 69,501 segments; 85,104 segments; 7,080 signs | FUNCTIONAL_CLASS, MAINLINE_LANE_MILES, SpeedLimit | 2021–26 | Network bounding box | [Road network](road-network.md) |
| GTFS timetables, 18 feeds | Weekday trip | 25,003 trips | route_type, stop_times, stops, calendar | 2026 (feeds of 2022–26) | Maryland part of the network area | [Transit](transit.md) |
| National Transit Database, MTA Maryland | Mode × period | 2,231 monthly rows | mode, time_period, upt | 2017/18, 2023–24 | MTA Maryland | [Transit](transit.md) |
| MDOT SHA AADT count stations | Station | 8,189 (Maryland); 3,797 (six counties) | F_SYSTEM, AADT_2024, AAWDT_2024, directional split, vehicle classes | 2015–24 (2024 used) | Maryland; six study-area counties used | [Traffic counts](traffic-counts.md) |
| FHWA TMAS continuous counts | Station × direction × lane × day | 81,208 records | hour_00–hour_23, travel_dir, f_system | 2024 | Maryland; 24 stations in the six counties | [Traffic counts](traffic-counts.md) |
| MDOT SHA vehicle-miles of travel | County × functional class | 24 counties × 7 classes | annual VMT | 2024 | Maryland | [Traffic counts](traffic-counts.md) |
| American Time Use Survey | Person diary day | 252,808 diaries (1,510 DC, MD, VA weekday 2017–24) | 15 | 2017–19, 2021–24 | DC, Maryland, Virginia | [Validation benchmarks](benchmarks.md#american-time-use-survey) |
| National Household Travel Survey | Trip | 1,982 trips (2017, Baltimore area); 131 car-driver trips (2022) | 18 | 2017, 2022 | Baltimore metropolitan area; South Atlantic class | [Validation benchmarks](benchmarks.md#national-household-travel-survey) |
| ACS 2024 journey to work (PUMS) | Person | 62,777 (1-year); 299,422 (5-year) | 12 | 2024; 2020–24 | Maryland | [Validation benchmarks](benchmarks.md#american-community-survey-2024-journey-to-work) |
| ACS summary tables | County; census tract | 60 county and 114 tract files | 17 | 2012–16, 2020–24, 2024 | Study area (six counties) | [Validation benchmarks](benchmarks.md#american-community-survey-summary-tables) |

## Pages

- [ACS Public Use Microdata Sample](acs-pums.md)
- [Regional Travel Survey 2017/18](travel-survey.md)
- [Employment: LODES, QCEW, JOLTS](employment.md)
- [Population, housing and neighbourhood controls](landuse-controls.md)
- [Schools and colleges](schools.md)
- [Zones, skims and census geography](zones-geography.md)
- [Road network](road-network.md)
- [Transit](transit.md)
- [Traffic counts](traffic-counts.md)
- [Validation benchmarks](benchmarks.md)
