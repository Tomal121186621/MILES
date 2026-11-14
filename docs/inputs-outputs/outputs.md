# Outputs

## Synthetic population

SILO-format CSV files of the 2016 base:

| File | Columns |
|---|---|
| `hh_2016.csv` | `id, dwelling, hhSize, autos, income, race` |
| `pp_2016.csv` | `id, hhID, age, gender, race, occupation, driversLicense, workplace, income, nationality, relationShip` |
| `dd_2016.csv` | `id, zone, type, hhID, bedrooms, quality, monthlyCost, restriction, yearBuilt` |
| `jj_2016.csv` | `id, zone, personId, type` |

## Land use

`scenOutput/<scenario>/`:

| File or folder | Content |
|---|---|
| `microData/futureYears/hh_<Y>.csv` | households of every year: `id, dwelling, hhSize, autos` |
| `microData/futureYears/pp_2024.csv` | persons: `id, hhid, age, gender, relationShip, occupation, driversLicense, workplace, income, race, schoolId` |
| `microData/futureYears/dd_2024.csv` | dwellings with coordinates |
| `microData/futureYears/jj_2024.csv` | jobs with coordinates |
| `microData/futureYears/schools_2024.csv` | schools: capacity, occupancy |
| `resultFile.csv`, `resultFileSpatial.csv` | yearly totals, by zone |
| `siloResults/moveDiagnostics.csv` | moves by year and group |
| `siloResults/relocation/relocation<Y>.csv.gz` | every move |
| `timeTracker.csv` | run time of each model by year |
| `fullProperties.properties` | the resolved properties |

## Activities

`<run>/output/`:

| File | Columns |
|---|---|
| `activities_<run>.csv` | `person_id, household_id, day, start_time_min, end_time_min, purpose, zone_id, x, y, zone, activity_type` |
| `legs_<run>.csv` | `person_id, previous_purpose, start_time_min, start_x, start_y, start_zone, next_purpose, end_time, end_x, end_y, end_zone, mode, time_min, distance_m` |
| `mc_tours.csv`, `mc_summary.csv` | tours with their modes; tours, joint groups and car reallocations |
| `tasha_summary.csv` | which distribution cell (or fallback) each draw used |

## MATSim plans

`pipeline/abit_to_matsim_pop.py` writes `population.xml.gz`: one weekday per person, homes on residential buildings,
other activities on points of interest of the matching type, and the person attributes `age, gender, occupation,
driversLicense, hhSize, autos, hhIncome, personIncome, race, homeZone, homeCounty, workZone`. Race is carried for reporting; no choice model uses it.

| Activity-model mode | MATSim mode |
|---|---|
| Car driver | `car` |
| Car passenger | `ride` |
| Bus, train | `pt` |
| Walk, bicycle | `walk`, `bike` |

## Assignment

`<run>/`:

| File | Content |
|---|---|
| `output_plans.xml.gz` | executed plans with routes and scores |
| `output_trips.csv.gz`, `output_legs.csv.gz` | every trip and leg |
| `output_events.xml.gz` | event stream (large; extract and delete) |
| `output_links.csv.gz` | link volumes |
| `modestats`, `scorestats`, `traveldistancestats` | statistics by iteration |
| `ITERS/it.100/linkstats.txt.gz` | link statistics of the last iteration |
| `link_hours_s<N>.csv.gz` | hourly volumes by link and vehicle class (`assignment/validation/extract_link_hours.py`) |
