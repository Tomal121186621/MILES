# Traffic assignment (MATSim)

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Engine** | MATSim 2024.0 (Java 21), queue simulation (QSim) with the SwissRailRaptor transit router |
    | **Code** | `assignment/` (network and transit builders, runner, validation) |
    | **Road network** | OpenStreetMap, Geofabrik Maryland extract, converted with pt2matsim; 214,716 nodes, 474,037 links |
    | **Transit** | GTFS of 18 feeds (MTA, WMATA, county services, Amtrak), one weekday, mapped with pt2matsim |
    | **Demand** | Weekday plans of MILES-Day, 10 % sample, modes fixed |
    | **Choices in MATSim** | Route and departure time |
    | **Runs** | 100 iterations, five seeds |

The weekday plans of MILES-Day are executed on the 2024 road and transit networks. In each iteration every agent
executes one plan in a queue simulation, the plan is scored, and a share of agents changes a route or a departure
time. After 100 iterations the network loads have settled and the link volumes are read for validation.

The sections below follow the order of the build: [demand](#1-demand), [road network](#2-road-network),
[transit network](#3-transit-network), [simulation set-up](#4-simulation-set-up) and [outputs](#5-outputs).

## 1. Demand

| Item | Setting |
|---|---|
| Source | Weekday plans of MILES-Day, 2024 |
| Persons | Residents of the six counties and workers commuting into them: 209,401 resident and 28,151 in-commuting persons, plus 25,290 residents working outside, in the 10 % sample |
| Sample | 10 % of households |
| Modes | Car, car passenger (ride), transit, walk, bike, fixed by MILES-Day; MATSim does not change them |
| Activity locations | Point locations from OpenStreetMap, inside the zone chosen by MILES-Day (see below) |
| Not modelled | Trucks, commercial vehicles, visitors and through traffic |

**Placing activities.** MILES-Day chooses zones; the bridge to MATSim (`pipeline/activities_to_matsim.py`) gives each
activity a point:

| Activity | Point | 2024 run |
|---|---|---|
| Home | An OpenStreetMap residential building of the home zone, the same one for all members of a household (a residential street point where the zone has no building) | all homes |
| Work, school, shopping, recreation, escort, other | An OpenStreetMap point of interest of the matching category inside the chosen zone, drawn at random among the zone's points of that category. Categories: work → work; school → education, else other; escort → education, else other; shopping → shopping; recreation → recreation, else other; other → other. Any POI of the zone if none of the category exists | 590,509 activities, all those inside the study area |
| Outside the six counties | The coordinate written by MILES-Day | 82,891 activities |

MATSim then attaches each activity to its nearest car link. Seven short dead-end links (pieces of the I-95 Express Toll
Lanes at the network edge) cannot be reached by any route; the 1,036 activities (0.08 %) whose nearest link was one of
them are attached to the nearest connected link instead (`pipeline/snap_to_network.py`). Coordinates are not changed.

## 2. Road network

### 2.1 Conversion from OpenStreetMap

The road network is built from the Geofabrik OpenStreetMap extract of Maryland (`maryland-latest.osm.pbf`,
replication timestamp 2026-06-11), clipped to the network area (`bmr.osm.gz`) and converted with **pt2matsim 24.4**
(`Osm2MultimodalNetwork`) into EPSG:26985 (Maryland State Plane, metres).

```bash
# 1. download the Maryland extract
curl -O https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf

# 2. clip the extract to the network area (file bmr.osm.gz, the osmFile of the converter configuration)
#    and write a default converter configuration, then edit it (values below)
java -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.CreateDefaultOsmConfig osm_convert_config.xml

# 3. convert OpenStreetMap to a MATSim network
java -Xmx8g -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.Osm2MultimodalNetwork osm_convert_config.xml
```

Converter settings (`osm_convert_config.xml`):

| Parameter | Value | Meaning |
|---|---|---|
| `outputCoordinateSystem` | EPSG:26985 | Maryland State Plane, metres |
| `keepPaths` | false | Only intersections and branch points become nodes |
| `maxLinkLength` | 500 m | Longer ways are split |
| `keepTagsAsAttributes` | true | OSM tags (highway, lanes, maxspeed, name) are kept on each link |
| `keepWaysWithPublicTransit` | true | Ways used by transit routes are kept |
| `parseTurnRestrictions` | false | Turn restrictions are not modelled |
| `scaleMaxSpeed` | false | Posted speeds are not scaled at conversion |
| `routableSubnetwork` | car; bus + car | Links outside the strongly connected network of these modes are removed |

Default values per OSM class, used where a way has no tag of its own:

| OSM class | Free speed (km/h) | Capacity per lane (veh/h) | Lanes | One-way |
|---|---:|---:|---:|---|
| motorway | 120 | 2,000 | 2 | yes |
| motorway_link | 80 | 1,500 | 1 | yes |
| trunk | 80 | 2,000 | 2 | no |
| trunk_link | 50 | 1,500 | 1 | no |
| primary | 80 | 1,500 | 1 | no |
| primary_link | 60 | 1,500 | 1 | no |
| secondary, secondary_link | 30 | 1,000 | 1 | no |
| tertiary, tertiary_link | 25 | 600 | 1 | no |
| rail / light rail / tram | 160 / 80 / 40 | — | 1 | — |

For roads, these defaults are replaced by the rules of 2.2 and 2.3.

### 2.2 Cleaning and reconciliation with MDOT

| Step | Rule | Source |
|---|---|---|
| Road class | Each non-freeway link is matched to the MDOT SHA functional classification (nearest segment within 20 m, direction within 30°). Where MDOT rates the road higher than OSM, the link takes the class of MDOT; links are never downgraded | MDOT SHA Roadway Functional Classification |
| Lanes | Ramps where the MDOT count inventory records more lanes than OSM take the MDOT value (18 ramps) | MDOT SHA AADT station inventory |
| Freeway capacity | HCM 7th edition: basic segment 2,350 pc/h/lane × heavy-vehicle factor 0.935 = 2,197 veh/h/lane; merge, diverge and lane-drop sections 2,043 veh/h/lane (queue-discharge factor 0.93); weaving sections by the HCM weaving formula | Highway Capacity Manual |
| Ramp capacity | HCM ramp-roadway capacity by free speed: 2,200 (> 50 mph), 2,100 (40–50), 2,000 (30–40), 1,900 (20–30), 1,800 pc/h/lane (< 20 mph) | Highway Capacity Manual |
| Exit storage | The first link of each exit ramp gets the storage of a 300 m deceleration lane, so a queue on the ramp does not block the freeway at once | HCM, off-ramp spillback |
| Isolated links | Links outside the strongly connected car network are removed; 754 transit-only links left from an earlier mapping are dropped before transit mapping | pt2matsim, `clean_network.py` |
| 2024 changes | Francis Scott Key Bridge closed (March 2024); I-95 northbound Express Toll Lanes extension MD 43 – MD 152 open (December 2024) | MDTA, MDOT SHA project portal |

### 2.3 Free speed and capacity of surface streets

| Item | Rule |
|---|---|
| Posted speed | First available of: OSM `maxspeed` of the way; MDOT SHA posted-speed signs on the same way; median of the same road name and class in the same 5 km cell; median of the class in the cell (at least 5 links); median of the class |
| Free speed | Posted speed × 0.9 below 51 km/h (25 and 30 mph), × 1.0 otherwise (rule of the MATSim OSM reader) |
| Capacity per lane | primary 1,500; secondary 800; tertiary, unclassified, residential 600; living street 300 veh/h (MATSim OSM reader) |
| Capacity | Capacity per lane × max(lanes, 1) |

No traffic count was used to set any speed, capacity or lane value. The network was audited link by link against
the MDOT inventories; the audit and the speed recoding are documented in `assignment/network/NETWORK_AUDIT.md` and
`SPEED_CAPACITY.md`.

### 2.4 Tolls

The 2024 tolls of the Baltimore Harbor and Fort McHenry tunnels are applied with the MATSim road-pricing module
(`roadpricing_HARB_2024.xml`, enforcement 100 %).

## 3. Transit network

### 3.1 Feeds and representative day

Eighteen GTFS feeds are merged: MTA local bus, Light RailLink, Metro SubwayLink, MARC, commuter bus; Charm City
Circulator, Harbor Connector, Towson Loop, RTA of Central Maryland, Anne Arundel County Transit, Annapolis Transit,
Harford Transit LINK, Carroll Transit; WMATA Metrorail and Metrobus; Montgomery County Ride On; Prince George's
County TheBus; Amtrak.

- **Day:** Wednesday 21 October 2026. A service runs on that day when `calendar.txt` lists it with the Wednesday flag
  or `calendar_dates.txt` adds it, and no exception removes it. Feeds whose calendar had ended use their last
  published Wednesday.
- **Area:** stops more than 250 m from any node of the network are dropped (DC and Virginia ends of routes);
  consecutive kept stops across a gap stay connected by the scheduled times.

### 3.2 Conversion and mapping

```bash
# 1. merge the feeds for the representative day
python3 assignment/transit/merge_gtfs.py <raw GTFS folder> network_2024.xml.gz gtfs_merged/

# 2. GTFS -> unmapped MATSim schedule and vehicles
java -Xmx8g -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.Gtfs2TransitSchedule \
     gtfs_merged/ 20261021 EPSG:26985 schedule_unmapped.xml.gz transitVehicles_gtfs.xml.gz

# 3. map the schedule onto the road and rail network (PTMapper guided by the GTFS shapes)
java -Xmx9g -cp classes:pt2matsim-24.4-shaded.jar de.umd.transit.MapWithShapes \
     ptmapper_config_2024.xml gtfs_merged/shapes.txt EPSG:26985 300 100

# 4. check the mapped schedule
java -Xmx8g -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.CheckMappedSchedulePlausibility \
     transitSchedule_2024.xml.gz network_2024_pt.xml.gz EPSG:26985 plausibility_2024/
```

All steps run with `miles assignment transit`.

PTMapper settings (`ptmapper_config_2024.xml`):

| Parameter | Value | Meaning |
|---|---|---|
| `travelCostType` | travelTime | Routes between stops minimise travel time |
| `maxLinkCandidateDistance` | 90 m | Links farther than this from a stop are not candidates |
| `nLinkThreshold` | 6 | Number of candidate links per stop |
| `candidateDistanceMultiplier` | 1.2 | Candidates up to 1.2 × the distance of the nearest link |
| `routingWithCandidateDistance` | true | The stop-to-link distance enters the routing cost |
| `maxTravelCostFactor` | 5.0 | Paths longer than 5 × the schedule time become artificial links |
| `scheduleFreespeedModes` | artificial, rail, subway | Free speed of these links set from the schedule |
| Shapes | GTFS shapes, 300 m and 100 m corridors | Candidate links restricted to the shape of the route |

Mode rules: buses run on the car network (`car,bus`); light rail on `light_rail,tram` links; Baltimore Metro on
`subway` links; MARC and Amtrak on `rail` links; ferries and lines without a matching network (Metrorail) on artificial
links that follow the scheduled times. After mapping, loops and U-turns are removed (`clean_routes.py`).

| Result | Value |
|---|---:|
| Lines / routes | 354 / 4,319 |
| Departures on the day | 25,099 |
| Stop facilities | 16,687 |
| Stops within 25 m / 50 m of their link | 91.7 % / 96.2 % |
| Route length on artificial links | 4.6 % |
| Car links opened to buses | 38,040 |

### 3.3 Transit vehicles

One vehicle per departure, typed by agency and mode. Capacity and passenger-car equivalents are multiplied by the
sample rate (0.1) in each run.

| Type | Operators | Seats + standing | Length | PCE |
|---|---|---:|---:|---:|
| Local bus | MTA, WMATA, Ride On, TheBus, RTA, county services | 38 + 32 | 12.2 m | 2.0 |
| Commuter coach | MTA commuter bus | 57 | 13.7 m | 2.5 |
| Light rail, 2 cars | MTA Light RailLink | 170 + 200 | 58 m | — |
| Metro, 4 cars | MTA Metro SubwayLink | 304 + 360 | 92 m | — |
| Metrorail, 8 cars | WMATA | 512 + 880 | 183 m | — |
| Commuter rail | MARC | 780 | 180 m | — |
| Intercity rail | Amtrak | 550 | 200 m | — |
| Ferry | Harbor Connector | 50 | 15 m | — |

## 4. Simulation set-up

The values below are those of the 2024 validation runs (MATSim output configuration).

### 4.1 Controller and simulation

| Module · parameter | Value | Meaning |
|---|---|---|
| `controller.lastIteration` | 100 | Iterations per run |
| `global.randomSeed` | 1–5 | One run per seed |
| `global.coordinateSystem` | EPSG:26985 | Maryland State Plane |
| `qsim.flowCapacityFactor` | 0.1 | Link flow capacity scaled to the 10 % sample |
| `qsim.storageCapacityFactor` | 0.1778 | 0.1^0.75: storage scaled less than flow, so short links do not jam at low sample rates |
| `qsim.trafficDynamics` / `linkDynamics` | queue / FIFO | Standard queue model |
| `qsim.mainMode` | car | Cars are simulated as vehicles; buses run in the same simulation |
| `qsim.stuckTime` | 120 s | Vehicles blocked longer are moved to the next link |
| `qsim.endTime` | 36:00 | Late tours can finish |
| `linkStats.averageLinkStatsOverIterations` | 5 | Link volumes averaged over the last five iterations |

### 4.2 Routing

| Module · parameter | Value | Meaning |
|---|---|---|
| `routing.networkModes` | car, ride | Car and car passenger routed on the road network with congested times; only cars occupy road space |
| walk | 1.23 m/s, beeline × 1.3 | Teleported |
| bike | 3.1 m/s, beeline × 1.3 | Teleported |
| `routing.routingRandomness` | 3.0 | Spread of toll sensitivity in route search |
| Transit router | SwissRailRaptor | Schedule-based routing on the mapped timetable |
| `transitRouter.searchRadius` | 4,000 m | Radius in which stops are searched around an origin or destination |
| `transitRouter.extensionRadius` | 2,000 m | Extra radius beyond the nearest stop |
| `transitRouter.maxBeelineWalkConnectionDistance` | 100 m | Longest walk between stops at a transfer |
| `swissRailRaptor.transferPenaltyBaseCost` | 0 | Cost per transfer added by the router |
| `swissRailRaptor.useCapacityConstraints` | false | Vehicle capacity not used in routing |

### 4.3 Replanning strategies

| Strategy | Weight | What it does |
|---|---:|---|
| `ReRoute` | 0.15 | A new route on the travel times of the last iteration (car and ride on the road network, transit on the timetable) |
| `TimeAllocationMutator` | 0.10 | Shifts activity end times by up to ± 30 minutes (`mutationRange` 1,800 s) around the planned times; durations are not changed |
| `ChangeExpBeta` | 0.75 | Chooses among the agent's stored plans with a logit on their scores (`brainExpBeta` 1.0) |

| Parameter | Value | Meaning |
|---|---|---|
| `maxAgentPlanMemorySize` | 5 | Plans kept per agent |
| `fractionOfIterationsToDisableInnovation` | 0.9 | From iteration 90 on, agents only choose among stored plans |
| Mode choice | off | Modes are fixed by MILES-Day |

### 4.4 Scoring

| Parameter | Value | Meaning |
|---|---|---|
| `performing` | 0.78 utils/h | Marginal utility of time at an activity; also the time cost of car travel |
| `lateArrival` | −1.872 utils/h | Late arrival at work = −2.4 × performing (Small, 1982) |
| `waitingPt` | −1.02 utils/h | Waiting at a stop |
| car: travel / distance | 0 utils/h / −$0.075 per km | Car time costs the performing rate only; operating cost per km |
| ride: travel / distance | 0 utils/h / −$0.075 per km | Passenger time valued as car time |
| transit: travel / distance | −1.02 utils/h / −$0.50 per km | In-vehicle time; fare proxy |
| walk: travel | −4.4 utils/h | |
| bike: travel | −2.345 utils/h | |
| Activity types | home 12 h, work 8 h, education 6 h, shopping 2 h, other 2 h, escort 15 min, eat 45 min, errand 30 min, social and recreation 1.5 h | Typical durations; home, work, shopping and other are split into duration classes of 10 minutes |

Mode constants are present in the scoring but have no effect, because MATSim does not choose modes.

**Value of time.** Each person's marginal utility of money is 0.78 / VOT, with VOT = 0.5 × max(annual household
income, \$5,000) / 2,080 h, the USDOT rule for local personal travel and the rule of the MILES-Day tour mode choice.
Route search uses the value at the median household income: \$23.91 per hour.

## 5. Outputs

| Output | Use |
|---|---|
| Link volumes by hour and over the day (cars, buses) | Comparison with counts, screenlines and continuous counters |
| Executed trips and legs, with routes | Vehicle-miles, trip lengths, travel times |
| Transit boardings by line | Comparison with National Transit Database boardings |
| Congested travel times by period | Skims for the next land-use and activity cycle |

The comparison with counts, screenlines and continuous counters is in
[Traffic validation](../calibration-validation/validation/traffic.md) and
[Interstates by station](../calibration-validation/validation/interstates.md).

## Running

```bash
miles assignment network      # build the 2024 and 2026 road networks
miles assignment transit      # merge GTFS, convert and map the schedules
miles assignment plans        # MILES-Day plans -> MATSim population, snapped to the network
miles assignment run          # one MATSim run (seed 1)
miles assignment seeds        # five seeds
miles assignment validate     # counts, screenlines, continuous counters
```
