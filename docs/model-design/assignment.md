# Traffic assignment

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Engine** | MATSim 2024 with a custom runner, Java |
    | **Code** | `assignment/` (network and transit builders, runner, validation) |
    | **Network** | OpenStreetMap roads, 2024; GTFS transit mapped with pt2matsim |
    | **Sensitive to** | Road capacity, speeds, tolls, transit timetables, value of time by income |
    | **Produces** | Routes, departure times, link volumes by hour, travel times, transit boardings |


The weekday plans of TERP-Day are assigned to the 2024 road and transit networks with **MATSim** (Multi-Agent
Transport Simulation). Each agent executes its plan, and over the iterations agents re-route and shift departure
times until the network loads settle.

## Scope

The assignment carries the **residents' own trips**: every car with a tour touching the six counties, and transit
riders. Trucks, commercial vehicles, visitors and through traffic are not modelled, so modelled volumes are expected
to fall below traffic counts, most of all off-peak and on roads with much freight.

## Set-up

| Item | Setting |
|---|---|
| Sample | 10 % of households |
| Iterations | 100 |
| Replanning | Re-routing; departure-time mutation (shifts of up to 30 minutes) |
| Modes | Fixed from TERP-Day |
| Runs | 5 seeds |
| Value of time | Half the hourly household income (the larger of household income and \$5,000 a year, over 2,080 hours), per person |
| Tolls | Harbour tunnel tolls of 2024 |
| Network year | 2024, Key Bridge closed |

## Road network

The network is built from **OpenStreetMap**: links, lanes, road classes and posted speeds.

- **Free speed:** the posted speed, times 0.9 below 51 km/h. Where OpenStreetMap has no speed tag (73 % of the
  links), the posted speed is the MDOT SHA speed sign or the median of the same road class nearby.
- **Capacity:** a value per lane by road class times the number of lanes — 1,500 veh/h for primary, 800 for
  secondary and 600 for tertiary and residential roads — and the bottleneck capacity of the Highway Capacity Manual
  on motorways and trunk roads.

No count was used to set any speed or capacity.

## Transit

The transit schedule is built from the GTFS timetables of the region's operators with **pt2matsim**, mapped on the
road network; buses run on the road network.

## Outputs

- Link volumes by hour and over the day, for comparison with counts.
- Executed car trips and their routes, for vehicle-miles and trip lengths.
- Transit boardings by line and mode.
- Congested travel times by period.

The comparison with counts, screenlines and continuous counters is in [validation](../calibration-validation/validation/index.md).
