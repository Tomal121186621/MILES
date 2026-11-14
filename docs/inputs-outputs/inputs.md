# Data

MILES is built from public data, with two exceptions marked † (released by the agency on request). The tables list
the data by the stage that uses them; bracketed numbers refer to the sources at the end of the page. The role of a
dataset is *estimation* (a model is estimated on it), *input* (used as given), *target* (a calibrated parameter is
matched to it) or *test* (used only for validation).

Files are placed in the workspace under `data/raw/<source>/`. The instruction sheet of each model in the estimation
package lists the exact files and variables.

## Synthetic population

| Dataset | Source | Years | Role |
|---|---|---|---|
| ACS Public Use Microdata Sample, 5-year, six states | U.S. Census Bureau [1] | 2012–16 | Estimation; test (held-out split) |
| ACS Public Use Microdata Sample, 5-year | U.S. Census Bureau [1] | 2014–18 | Test |
| Redistricting files, block housing units | U.S. Census Bureau [2] | 2010, 2020 | Input: households by zone |
| LEHD Origin–Destination Employment Statistics | U.S. Census Bureau [3] | 2016 | Input: jobs by zone |
| Job Openings and Labor Turnover Survey | Bureau of Labor Statistics [4] | 2016 | Input: vacant jobs |

## Land use and workplaces

| Dataset | Source | Years | Role |
|---|---|---|---|
| ACS PUMS, households that moved | U.S. Census Bureau [1] | 2014–21 | Estimation (2014–18); test (2019–21) |
| ACS PUMS, households | U.S. Census Bureau [1] | 2014–18 | Estimation: car ownership |
| ACS PUMS, 1-year | U.S. Census Bureau [1] | 2016–24 | Target; test |
| Population estimates and components of change | U.S. Census Bureau [5] | 2010–24 | Input: county totals; test |
| LEHD Origin–Destination Employment Statistics | U.S. Census Bureau [3] | 2016–23 | Input: jobs; test: commute flows |
| Quarterly Census of Employment and Wages | Bureau of Labor Statistics [6] | 2016–24 | Input: jobs in 2024 |
| Job Openings and Labor Turnover Survey | Bureau of Labor Statistics [4] | 2016–24 | Input: vacancies; test: quits |
| Building Permits Survey | U.S. Census Bureau [7] | 2016–24 | Input: new dwellings |
| County-to-county commuting and migration flows | U.S. Census Bureau [8] | 2014–20 | Test |
| Stanford Education Data Archive, county learning growth | Stanford University [9] | 2009–18 | Estimation: residential location |
| Uniform Crime Reporting, county index offences | Maryland Statistical Analysis Center [10] | 2016 | Estimation: residential location |
| Consumer Price Index, all urban consumers | Bureau of Labor Statistics [11] | 2014–24 | Input: constant dollars |

## School location

| Dataset | Source | Years | Role |
|---|---|---|---|
| Common Core of Data and Private School Survey | National Center for Education Statistics [12] | 2023–25 | Input: schools and enrolment |
| Integrated Postsecondary Education Data System | National Center for Education Statistics [13] | 2023–24 | Input: colleges and enrolment |
| School Attendance Boundary Survey | National Center for Education Statistics [14] | 2015–16 | Input: attendance zones |

## Activities

| Dataset | Source | Years | Role |
|---|---|---|---|
| Regional Travel Survey † | Baltimore Metropolitan Council; Metropolitan Washington Council of Governments [15] | 2017/18 | Estimation (one half); test (other half) |
| Traffic analysis zones of the survey | Baltimore Metropolitan Council; MWCOG [16] | 2010 | Input: survey locations |
| American Time Use Survey | Bureau of Labor Statistics [17] | 2021–24 | Test |
| National Household Travel Survey | Federal Highway Administration [18] | 2017 | Test |
| Vehicle operating cost | AAA [19] | 2017 | Input: car cost |
| Transit fares | MTA Maryland; WMATA [20] | 2017/18 | Input: transit cost |

## Networks and traffic

| Dataset | Source | Years | Role |
|---|---|---|---|
| Maryland Statewide Transportation Model: zones and car skims † | Maryland Department of Transportation [21] | base year | Input: zones, car times |
| OpenStreetMap | OpenStreetMap contributors [22] | 2026 | Input: road network |
| Roadway functional class, lanes, speed-limit signs | MDOT State Highway Administration [23] | 2021–26 | Input: speeds; network check |
| GTFS timetables of 18 operators | MTA Maryland and regional operators [24] | 2026 | Input: transit network and skims |
| Traffic counts, average weekday traffic (3,797 stations) | MDOT State Highway Administration [23] | 2024 | Test |
| Continuous count stations, hourly volumes | Federal Highway Administration [25] | 2024 | Test |
| Vehicle-miles by county and road class | MDOT State Highway Administration [26] | 2024 | Test |
| National Transit Database, boardings by mode | Federal Transit Administration [27] | 2017/18, 2024 | Test |

† Released by the agency on request; not redistributed with MILES.

## Geography

| Dataset | Source | Years | Role |
|---|---|---|---|
| TIGER/Line census tracts and blocks | U.S. Census Bureau [28] | 2010 | Input: tract–zone matching |
| Gazetteer, tract internal points | U.S. Census Bureau [29] | 2010 | Input: tract distances |
| Tract-to-PUMA relationship file | U.S. Census Bureau [30] | 2010 | Input: crosswalk |
| PUMA, migration PUMA and place-of-work PUMA crosswalk | IPUMS USA [31] | 2010 | Input: crosswalk |

## Sources

1. U.S. Census Bureau. *American Community Survey Public Use Microdata Sample.* <https://www2.census.gov/programs-surveys/acs/data/pums/>
2. U.S. Census Bureau. *Decennial Census Redistricting Data (PL 94-171).* <https://www2.census.gov/census_2010/01-Redistricting_File--PL_94-171/>; <https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/>
3. U.S. Census Bureau. *LEHD Origin–Destination Employment Statistics (LODES 8).* <https://lehd.ces.census.gov/data/lodes/LODES8/>
4. Bureau of Labor Statistics. *Job Openings and Labor Turnover Survey.* <https://www.bls.gov/jlt/>
5. U.S. Census Bureau. *County Population Totals and Components of Change.* <https://www2.census.gov/programs-surveys/popest/datasets/>
6. Bureau of Labor Statistics. *Quarterly Census of Employment and Wages.* <https://www.bls.gov/cew/>
7. U.S. Census Bureau. *Building Permits Survey, county data.* <https://www2.census.gov/econ/bps/County/>
8. U.S. Census Bureau. *County-to-County Commuting and Migration Flows.* <https://www.census.gov/topics/population/migration/guidance/county-to-county-migration-flows.html>
9. Reardon, S.F., et al. *Stanford Education Data Archive.* <https://edopportunity.org/get-the-data/>
10. Maryland Statistical Analysis Center. *Violent Crime and Property Crime by County.* <https://opendata.maryland.gov/>
11. Bureau of Labor Statistics. *Consumer Price Index for All Urban Consumers, series CUUR0000SA0.* <https://data.bls.gov/timeseries/CUUR0000SA0>
12. National Center for Education Statistics. *Common Core of Data; Private School Universe Survey.* <https://nces.ed.gov/ccd/>; <https://nces.ed.gov/surveys/pss/>
13. National Center for Education Statistics. *Integrated Postsecondary Education Data System.* <https://nces.ed.gov/ipeds/>
14. National Center for Education Statistics. *School Attendance Boundary Survey 2015–16.* <https://nces.ed.gov/programs/edge/SABS>
15. Baltimore Metropolitan Council; Metropolitan Washington Council of Governments. *2017/2018 Regional Travel Survey.* <https://www.baltometro.org/>; <https://www.mwcog.org/>
16. Baltimore Metropolitan Council GIS; MWCOG Regional Transportation Data Clearinghouse. *Traffic analysis zones.* <https://gis.baltometro.org/>; <https://rtdc-mwcog.opendata.arcgis.com/>
17. Bureau of Labor Statistics. *American Time Use Survey.* <https://www.bls.gov/tus/>
18. Federal Highway Administration. *2017 National Household Travel Survey.* <https://nhts.ornl.gov/>
19. AAA. *Your Driving Costs, 2017 edition.* <https://newsroom.aaa.com/auto/your-driving-costs/>
20. Maryland Transit Administration; Washington Metropolitan Area Transit Authority. *Fares.* <https://www.mta.maryland.gov/>; <https://www.wmata.com/>
21. Maryland Department of Transportation. *Maryland Statewide Transportation Model.* <https://www.roads.maryland.gov/>
22. OpenStreetMap contributors. *Maryland extract, via Geofabrik.* <https://download.geofabrik.de/north-america/us/maryland.html>
23. MDOT State Highway Administration. *Open data (functional classification, lane mileage, signs, traffic volumes).* <https://data.imap.maryland.gov/>
24. Maryland Transit Administration and regional operators. *GTFS feeds*, also mirrored by the Mobility Database. <https://www.mta.maryland.gov/developer-resources>; <https://mobilitydatabase.org/>
25. Federal Highway Administration. *Travel Monitoring Analysis System, 2024.* <https://www.fhwa.dot.gov/policyinformation/tables/tmasdata/2024/>
26. MDOT State Highway Administration. *2024 Mileage Reports.* <https://www.roads.maryland.gov/OPPEN/2024_Mileage_Reports.pdf>
27. Federal Transit Administration. *National Transit Database.* <https://www.transit.dot.gov/ntd/ntd-data>
28. U.S. Census Bureau. *TIGER/Line Shapefiles, 2010.* <https://www2.census.gov/geo/tiger/TIGER2010/>
29. U.S. Census Bureau. *Gazetteer Files.* <https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html>
30. U.S. Census Bureau. *2010 Census Tract to 2010 PUMA Relationship File.* <https://www2.census.gov/geo/docs/maps-data/data/rel/2010_Census_Tract_to_2010_PUMA.txt>
31. IPUMS USA. *PUMA, MIGPUMA and POWPUMA crosswalk.* <https://usa.ipums.org/usa/resources/volii/puma_migpuma1_pwpuma00.xls>
