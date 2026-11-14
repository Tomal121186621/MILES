# Data catalogue

Every dataset TERP uses, with its provider, the years used, what it is used for and where to get it.
**Use**: *estimation* (a model is estimated on it), *input* (used as given), *target* (a calibrated parameter is
matched to it) or *test* (used only to validate). **Access**: <span class="vb ok">public</span> free download;
<span class="vb close">request</span> released by the agency on request; <span class="vb out">project</span> produced
by an earlier stage of TERP.

The files go into the workspace (`paths.workspace` in `terp.toml`) under `data/raw/<source>/`; the instruction sheet
of each model folder of the estimation package lists the exact files and variables.

## Census microdata and population

| Dataset | Provider | Years | Use | Access | Link |
|---|---|---|---|---|---|
| ACS Public Use Microdata Sample, 5-year (household and person files of DC, DE, MD, PA, VA, WV) | U.S. Census Bureau | 2012–16, 2014–18, 2015–19 | Estimation of the synthetic population, residential location and car ownership; tests | <span class="vb ok">public</span> | [census.gov PUMS](https://www2.census.gov/programs-surveys/acs/data/pums/) |
| ACS PUMS, 1-year files | U.S. Census Bureau | 2016–24 | Calibration targets; out-of-sample tests | <span class="vb ok">public</span> | [census.gov PUMS](https://www2.census.gov/programs-surveys/acs/data/pums/) |
| Population estimates, county totals and components of change | U.S. Census Bureau | 2010–24 | Input: county control totals; test of births and deaths | <span class="vb ok">public</span> | [popest datasets](https://www2.census.gov/programs-surveys/popest/datasets/) |
| Census 2010 and 2020 redistricting files (PL 94-171): block housing units | U.S. Census Bureau | 2010, 2020 | Input: placing households in zones | <span class="vb ok">public</span> | [2010](https://www2.census.gov/census_2010/01-Redistricting_File--PL_94-171/) · [2020](https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/) |
| TIGER/Line census tracts and blocks | U.S. Census Bureau | 2010 | Matching survey locations to zones | <span class="vb ok">public</span> | [TIGER 2010 tracts](https://www2.census.gov/geo/tiger/TIGER2010/TRACT/2010/) |
| Census Gazetteer, tract internal points | U.S. Census Bureau | 2010 | Tract-to-zone matching, trip lengths | <span class="vb ok">public</span> | [Gazetteer files](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html) |
| Tract-to-PUMA relationship file | U.S. Census Bureau | 2010 | Geography crosswalk | <span class="vb ok">public</span> | [relationship file](https://www2.census.gov/geo/docs/maps-data/data/rel/2010_Census_Tract_to_2010_PUMA.txt) |
| PUMA to migration and place-of-work PUMA crosswalk | IPUMS USA | 2010 geography | Residential location: previous home of movers | <span class="vb ok">public</span> | [IPUMS crosswalk](https://usa.ipums.org/usa/resources/volii/puma_migpuma1_pwpuma00.xls) |
| ACS county-to-county commuting and migration flows | U.S. Census Bureau | 2014–20 | Test of commute and mover flows; external workplaces | <span class="vb ok">public</span> | [census.gov flows](https://www.census.gov/topics/population/migration/guidance/county-to-county-migration-flows.html) |

## Jobs, housing and the economy

| Dataset | Provider | Years | Use | Access | Link |
|---|---|---|---|---|---|
| LEHD LODES 8: workplace area characteristics, origin–destination flows, crosswalks | U.S. Census Bureau, LEHD | 2016–23 | Input: jobs by zone and type; test of commute flows | <span class="vb ok">public</span> | [LODES 8](https://lehd.ces.census.gov/data/lodes/LODES8/) |
| Quarterly Census of Employment and Wages, county jobs | Bureau of Labor Statistics | 2016–24 | Input: jobs in 2024 | <span class="vb ok">public</span> | [QCEW](https://www.bls.gov/cew/) |
| JOLTS job openings and quits, Maryland | Bureau of Labor Statistics | 2016–24 | Input: vacant jobs; test of job changes | <span class="vb ok">public</span> | [JOLTS series](https://api.bls.gov/publicAPI/v1/timeseries/data/JTS000000240000000JOR) |
| Building Permits Survey, county | U.S. Census Bureau | 2016–24 | Input: new dwellings | <span class="vb ok">public</span> | [BPS county files](https://www2.census.gov/econ/bps/County/) |
| Consumer price index, CPI-U | Bureau of Labor Statistics | 2014–24 | Incomes in 2016 dollars | <span class="vb ok">public</span> | [CUUR0000SA0](https://data.bls.gov/timeseries/CUUR0000SA0) |
| Stanford Education Data Archive 4.1, county learning growth | SEDA, Stanford | 2009–18 | Residential location: school quality | <span class="vb ok">public</span> | [SEDA](https://edopportunity.org/get-the-data/) |
| Uniform Crime Reporting, index offences by county | Maryland Statistical Analysis Center | 2016 | Residential location: crime | <span class="vb ok">public</span> | [Maryland open data](https://opendata.maryland.gov/api/views/jwfa-fdxs/rows.csv?accessType=DOWNLOAD) |

## Schools

| Dataset | Provider | Years | Use | Access | Link |
|---|---|---|---|---|---|
| Common Core of Data and Private School Survey directories, with geocodes | NCES | 2023–25 | Input: schools and enrolment | <span class="vb ok">public</span> | [CCD](https://nces.ed.gov/ccd/files.asp) · [PSS](https://nces.ed.gov/surveys/pss/) |
| IPEDS institutional characteristics and enrolment | NCES | 2023–24 | Input: colleges and enrolment | <span class="vb ok">public</span> | [IPEDS data center](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx) |
| School Attendance Boundary Survey | NCES EDGE | 2015–16 | Input: attendance zones | <span class="vb ok">public</span> | [SABS](https://nces.ed.gov/programs/edge/data/SABS_1516_SchoolLevels.zip) |

## Travel behaviour

| Dataset | Provider | Years | Use | Access | Link |
|---|---|---|---|---|---|
| Regional Travel Survey: households, persons, trips | Baltimore Metropolitan Council and Metropolitan Washington Council of Governments | 2017/18 | Estimation of the travel models (estimation half); validation (hold-out half) | <span class="vb close">request</span> | [BMC](https://www.baltometro.org/) · [MWCOG](https://www.mwcog.org/) |
| BMC and TPB traffic analysis zones (zone codes of the survey) | BMC GIS; MWCOG Regional Transportation Data Clearinghouse | 2010 | Survey locations to model zones | <span class="vb ok">public</span> | [BMC TAZ](https://gis.baltometro.org/arcgis/rest/services/Regional_Boundaries/MapServer/14) · [TPB TAZ](https://gis.mwcog.org/wa/rest/services/RTDC/TAZ/MapServer) |
| American Time Use Survey | Bureau of Labor Statistics | 2021–24 | Test of 2024 activities and start times | <span class="vb ok">public</span> | [ATUS data files](https://www.bls.gov/tus/datafiles.htm) |
| National Household Travel Survey | FHWA | 2017 | Test of activities and trip lengths | <span class="vb ok">public</span> | [NHTS](https://nhts.ornl.gov/) |
| Vehicle operating cost | AAA, *Your Driving Costs* | 2017 | Car cost per mile in mode choice | <span class="vb ok">public</span> | [AAA](https://newsroom.aaa.com/auto/your-driving-costs/) |
| Transit fares | MTA Maryland, WMATA | 2017/18 | Transit cost in mode choice | <span class="vb ok">public</span> | [MTA](https://www.mta.maryland.gov/) · [WMATA](https://www.wmata.com/) |

## Zones, networks and transit

| Dataset | Provider | Years | Use | Access | Link |
|---|---|---|---|---|---|
| Maryland Statewide Transportation Model: 1,588-zone system, zone polygons, AM-peak car skims | MDOT | base year | Input: zones and car times | <span class="vb close">request</span> | [MDOT SHA](https://roads.maryland.gov/) |
| OpenStreetMap, Maryland extract | OpenStreetMap contributors, via Geofabrik | 2026 | Input: road network | <span class="vb ok">public</span> | [Geofabrik Maryland](https://download.geofabrik.de/north-america/us/maryland.html) |
| MDOT SHA functional classification, lane mileage, interchange exits, speed-limit signs | MDOT SHA | 2021–26 | Network audit, posted speeds | <span class="vb ok">public</span> | [MDOT SHA open data](https://data.imap.maryland.gov/) |
| MTA Maryland GTFS: local bus, light rail, Metro, MARC, commuter bus | Maryland Transit Administration | 2026 | Input: transit schedule and skims | <span class="vb ok">public</span> | [MTA developer resources](https://www.mta.maryland.gov/developer-resources) |
| GTFS of the other operators of the network area (Charm City Circulator, RTA, Annapolis, Anne Arundel, Harford, Carroll, WMATA, Ride On, TheBus, Amtrak and others) | Each operator; Mobility Database mirror | 2026 | Input: transit schedule | <span class="vb ok">public</span> | [Mobility Database](https://mobilitydatabase.org/) |

## Traffic counts and mileage (validation only)

| Dataset | Provider | Years | Use | Access | Link |
|---|---|---|---|---|---|
| Annual average daily and weekday traffic, statewide count stations | MDOT SHA | 2024 | Test of daily volumes | <span class="vb ok">public</span> | [Maryland iMAP open data](https://data.imap.maryland.gov/) |
| Travel Monitoring Analysis System, continuous count stations | FHWA | 2024 | Test of hourly volumes | <span class="vb ok">public</span> | [TMAS data](https://www.fhwa.dot.gov/policyinformation/tables/tmasdata/2024/) |
| Mileage reports, vehicle-miles by county and road class | MDOT SHA | 2024 | Test of regional traffic | <span class="vb ok">public</span> | [2024 mileage report](https://www.roads.maryland.gov/OPPEN/2024_Mileage_Reports.pdf) |
| National Transit Database, unlinked trips by mode | Federal Transit Administration | 2017/18, 2024 | Test of transit boardings | <span class="vb ok">public</span> | [NTD data](https://www.transit.dot.gov/ntd/ntd-data) |

## Produced by TERP

| Dataset | Produced by | Used by |
|---|---|---|
| Synthetic population of 2016 (households, persons, dwellings, jobs) | Synthetic population | Land use |
| Population, dwellings and jobs of every year to 2024 | Land use | Schools, activities |
| Zone accessibility by year | Pipeline (`accessibility.py`) | Residential location, car ownership, workplace choice |
| Door-to-door transit skims | Pipeline (`transit_skim.py`) on the MATSim transit schedule | Land use, activities |
| Weekday plans | Activities | Traffic assignment |
| 2024 road and transit networks | `assignment/network`, `assignment/transit` | Traffic assignment |
