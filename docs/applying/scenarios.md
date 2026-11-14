# Scenarios

## 1. Pick the stage

Short-run responses (route and departure time) need only the assignment. Responses in destination and mode need
ORIOLE-Day with new skims; long-run responses in where people live and work need the land-use model too.

| Response | Stages to rerun |
|---|---|
| Route, departure time | MATSim |
| Destination, mode, trip making | ORIOLE-Day → MATSim |
| Residential and workplace location, car ownership | SILO → schools → ORIOLE-Day → MATSim |

## 2. A pricing scenario in MATSim

1. Write a road-pricing file (MATSim `roadpricing` format): the links, the time windows and the amount. The base file
   `assignment/network/roadpricing_HARB_2024.xml` is an example.
2. Run the base and the scenario with the same plans and seeds:

    ```bash
    python pipeline/run_chain.py --sample 0.1 --iterations 100 matsim 2024 2024 1 \
           --plans population_2024_scc.xml.gz --toll my_scheme.xml
    ```

3. Compare executed trips (`output_trips.csv.gz`), link volumes (`link_hours_s<N>.csv.gz`) and scores
   (`output_plans.xml.gz`) between base and scenario, seed by seed.

!!! tip "Seeds"
    Run at least five seeds for base and scenario. Differences smaller than the spread across seeds are noise.

## 3. Reading results by person

Every MATSim agent carries its household income, cars, home zone and county, so changes in travel time, toll paid and
utility can be summarised by income decile or by area.

## 4. Land-use scenarios

Edit the land-use inputs (`development_*.csv` for building capacity, job control totals for employment), write a
properties file with `landuse/run/make_properties.py`, and run SILO from 2016; then rerun schools, ORIOLE-Day and
MATSim on the scenario's 2024 population.
