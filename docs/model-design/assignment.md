# Traffic assignment (MATSim)

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Engine** | MATSim 2024.0, queue simulation, SwissRailRaptor transit router |
    | **Code** | `assignment/` |
    | **Road network** | OpenStreetMap via pt2matsim; 214,716 nodes, 474,037 links |
    | **Transit** | 18 GTFS feeds, one weekday, mapped with pt2matsim |
    | **Demand** | MAST weekday plans, 10 % sample, modes fixed |
    | **Choices** | Route, departure time |
    | **Runs** | 100 iterations; three independent chains, seeds 1–3 |

Each iteration, every agent executes one plan in a queue simulation; the plan is scored, and a share of agents
changes its route or departure time. After 100 iterations the link volumes are read for validation.

## 1. Demand

**Table 1.** Demand passed to MATSim (2024, 10 % sample).

| Item | Value |
|---|---|
| Persons | 262,842 |
| — residents working in the study area | 209,401 |
| — residents working outside | 25,290 |
| — in-commuters | 28,151 |
| Legs | 1,032,562 |
| Modes | car, ride, transit, walk, bike (fixed) |
| Not modelled | trucks, commercial vehicles, visitors, through traffic |

**Table 2.** Activity locations.

| Activity | Location | Activities |
|---|---|---:|
| Home | OSM residential building in the home zone<sup>a</sup> | all |
| Other, inside the study area | OSM point of interest of the matching category in the chosen zone<sup>b</sup> | 590,509 |
| Outside the study area | Coordinate from MAST | 82,891 |

<div class="tnote" markdown>

<sup>a</sup> One building per household; a residential street point where the zone has no building.

<sup>b</sup> Drawn at random. Categories: work → work; school, escort → education; shopping → shopping; recreation → recreation; other → other. Fallback: other, then any POI of the zone.

</div>

MATSim attaches each activity to its nearest car link. The 1,036 activities (0.08 %) nearest to one of seven
unreachable dead-end links are attached to the nearest connected link (`pipeline/snap_to_network.py`).

## 2. Road network

### 2.1 Conversion

Source: Geofabrik OpenStreetMap extract of Maryland (2026-06-11), clipped to the network area and converted with
pt2matsim 24.4 to EPSG:26985.

```bash
curl -O https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf
java -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.CreateDefaultOsmConfig osm_convert_config.xml
java -Xmx8g -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.Osm2MultimodalNetwork osm_convert_config.xml
```

**Table 3.** Converter settings (`osm_convert_config.xml`).

| Parameter | Value |
|---|---|
| `outputCoordinateSystem` | EPSG:26985 |
| `keepPaths` | false |
| `maxLinkLength` | 500 m |
| `keepTagsAsAttributes` | true |
| `keepWaysWithPublicTransit` | true |
| `parseTurnRestrictions` | false |
| `scaleMaxSpeed` | false |
| `routableSubnetwork` | car; car + bus |

**Table 4.** Converter defaults for untagged ways.

| OSM class | Free speed (km/h) | Capacity (veh/h/lane) | Lanes | One-way |
|---|---:|---:|---:|:---:|
| motorway | 120 | 2,000 | 2 | yes |
| motorway_link | 80 | 1,500 | 1 | yes |
| trunk | 80 | 2,000 | 2 | no |
| trunk_link | 50 | 1,500 | 1 | no |
| primary | 80 | 1,500 | 1 | no |
| primary_link | 60 | 1,500 | 1 | no |
| secondary (_link) | 30 | 1,000 | 1 | no |
| tertiary (_link) | 25 | 600 | 1 | no |

Tagged values take precedence; most motorways carry a 65 mph tag (105 km/h). Capacities are replaced by Tables 5 and 6.

### 2.2 Cleaning

**Table 5.** Corrections to the converted network.

| Step | Rule | Source |
|---|---|---|
| Road class | Upgraded to the MDOT class where MDOT rates a road higher<sup>a</sup> | MDOT SHA functional classification |
| Ramp lanes | MDOT value where higher (18 ramps) | MDOT SHA count inventory |
| I-695 capacity | 2,197 veh/h/lane, basic; 2,043 at merges, diverges, lane drops; HCM formula at weaves<sup>b</sup> | HCM |
| Other motorways | 2,000 veh/h/lane | converter |
| Trunk roads | 1,500 veh/h/lane | network audit |
| Ramp capacity | 1,800–2,200 veh/h/lane by free speed<sup>c</sup> | HCM |
| Exit storage | + 300 m of storage on the first exit-ramp link | HCM, ch. 38 |
| Transit-only links | 754 removed before transit mapping | `clean_network.py` |
| Key Bridge | removed (closed March 2024) | MDTA |
| I-95 ETL extension | removed (opened December 2024; 2026 network only) | MDTA |

<div class="tnote" markdown>

<sup>a</sup> Nearest MDOT segment within 20 m and 30°; links are never downgraded.

<sup>b</sup> 2,350 pc/h/lane × heavy-vehicle factor 0.935; 0.93 queue-discharge factor at bottlenecks; all 604 mainline links.

<sup>c</sup> 2,200 (> 50 mph), 2,100 (40–50), 2,000 (30–40), 1,900 (20–30), 1,800 (< 20 mph).

</div>

### 2.3 Surface streets

**Table 6.** Free speed and capacity of primary and lower roads.

| Item | Rule |
|---|---|
| Posted speed | OSM `maxspeed`, else MDOT sign, else local median<sup>a</sup> |
| Free speed | posted × 0.9 below 51 km/h; posted otherwise |
| Capacity (veh/h/lane) | primary 1,500; secondary 800; tertiary, residential 600; living street 300 |
| Link capacity | per-lane capacity × max(lanes, 1) |

<div class="tnote" markdown>

<sup>a</sup> Median of the same road name and class in the same 5 km cell, then of the class in the cell, then of the class. Free speed and capacity rules follow the MATSim OSM reader.

</div>

No traffic count was used to set any speed, capacity or lane value.

### 2.4 Tolls

Baltimore Harbor and Fort McHenry tunnels: \$3.00 per passage, both directions, six links
(`roadpricing_HARB_2024.xml`).

## 3. Transit network

### 3.1 Feeds

**Table 7.** GTFS feeds.

| Operator group | Feeds |
|---|---|
| MTA | local bus, Light RailLink, Metro SubwayLink, MARC, commuter bus |
| Baltimore region | Charm City Circulator, Harbor Connector, Towson Loop, RTA, Anne Arundel County Transit, Annapolis Transit, Harford Transit LINK, Carroll Transit |
| Washington region | WMATA Metrorail, WMATA Metrobus, Ride On, TheBus |
| Intercity | Amtrak |

Service day: Wednesday 21 October 2026 (last published Wednesday for expired feeds). Stops more than 250 m from the
network are dropped.

### 3.2 Mapping

```bash
python3 assignment/transit/merge_gtfs.py <raw GTFS folder> network_2024.xml.gz gtfs_merged/
java -Xmx8g -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.Gtfs2TransitSchedule \
     gtfs_merged/ 20261021 EPSG:26985 schedule_unmapped.xml.gz transitVehicles_gtfs.xml.gz
java -Xmx9g -cp classes:pt2matsim-24.4-shaded.jar de.umd.transit.MapWithShapes \
     ptmapper_config_2024.xml gtfs_merged/shapes.txt EPSG:26985 300 100
java -Xmx8g -cp pt2matsim-24.4-shaded.jar org.matsim.pt2matsim.run.CheckMappedSchedulePlausibility \
     transitSchedule_2024.xml.gz network_2024_pt.xml.gz EPSG:26985 plausibility_2024/
```

**Table 8.** PTMapper settings (`ptmapper_config_2024.xml`).

| Parameter | Value |
|---|---|
| `travelCostType` | travelTime |
| `maxLinkCandidateDistance` | 90 m |
| `nLinkThreshold` | 6 |
| `candidateDistanceMultiplier` | 1.2 |
| `routingWithCandidateDistance` | true |
| `maxTravelCostFactor` | 5.0 |
| `scheduleFreespeedModes` | artificial, rail, subway |
| Shape corridor / weight distance<sup>a</sup> | 300 m / 100 m |

<div class="tnote" markdown>

<sup>a</sup> Routes with a GTFS shape use only links within 300 m of it; link cost rises with distance from the shape.

</div>

Buses run on the car network, light rail and Baltimore Metro on their own links, MARC and Amtrak on rail links;
Metrorail and ferries on artificial links.

**Table 9.** Mapped schedule.

| Item | Value |
|---|---:|
| Lines | 354 |
| Routes | 4,319 |
| Departures | 25,099 |
| Stop facilities | 16,687 |
| Stops within 25 m of their link | 91.7 % |
| Stops within 50 m of their link | 96.2 % |
| Route length on artificial links | 4.6 % |
| Car links opened to buses | 38,040 |

### 3.3 Vehicles

**Table 10.** Transit vehicle types.

| Type | Operators | Seats | Standing | Length (m) | PCE |
|---|---|---:|---:|---:|---:|
| Local bus | MTA, WMATA, county services | 38 | 32 | 12.2 | 2.0 |
| Commuter coach | MTA | 57 | 0 | 13.7 | 2.5 |
| Light rail, 2 cars | MTA | 170 | 200 | 58 | 5.2 |
| Metro, 4 cars | MTA | 304 | 360 | 92 | 4.4 |
| Metrorail, 8 cars | WMATA | 512 | 880 | 183 | 4.4 |
| Commuter rail | MARC | 780 | 0 | 180 | 27.1 |
| Intercity rail | Amtrak | 550 | 0 | 200 | 27.1 |
| Ferry | Harbor Connector | 50 | 0 | 15 | 1.0 |

Capacity and PCE are multiplied by the sample rate (0.1) in each run.

## 4. Simulation set-up

Values of the final 2024 runs.

**Table 11.** Simulation.

| Parameter | Value |
|---|---|
| Iterations | 100 |
| Random seeds | 1–3 (one run per land-use seed) |
| Flow capacity factor | 0.1 |
| Storage capacity factor | 0.1778 (= 0.1<sup>0.75</sup>) |
| Traffic dynamics | queue, FIFO |
| Simulated mode | car (transit vehicles also simulated) |
| Stuck time | 120 s |
| End time | 36:00 |
| Link volumes | mean of the last 5 iterations |

**Table 12.** Routing.

| Parameter | Value |
|---|---|
| Network modes | car, ride<sup>a</sup> |
| Walk speed | 1.23 m/s (beeline × 1.3) |
| Bike speed | 3.1 m/s (beeline × 1.3) |
| Routing randomness | 3.0 |
| Transit router | SwissRailRaptor |
| Stop search radius | 4,000 m |
| Extension radius | 2,000 m |
| Transfer walk, max. | 300 m |
| Transfer penalty | −0.13 utils (about 10 in-vehicle minutes) |
| Capacity constraints | off |

<div class="tnote" markdown>

<sup>a</sup> Ride is routed on congested car times but does not occupy road space.

</div>

**Table 13.** Replanning.

| Strategy | Weight | Effect |
|---|---:|---|
| ReRoute | 0.15 | new route on last-iteration times |
| TimeAllocationMutator | 0.10 | end times shifted ± 30 min |
| ChangeExpBeta | 0.75 | logit choice among stored plans |

Plans kept per agent: 5. Innovation off after iteration 90. No mode choice.

**Table 14.** Scoring parameters.

| Parameter | Value | Unit |
|---|---:|---|
| Performing | 0.78 | utils/h |
| Late arrival | −1.872 | utils/h |
| Waiting for transit | 0 | utils/h |
| Transfer (line switch) | −0.13 | utils |
| Marginal utility of money | 0.78 / VOT<sup>a</sup> | utils/$ |

<div class="tnote" markdown>

<sup>a</sup> VOT = 0.5 × max(household income, \$5,000) / 2,080 h, per person (USDOT rule); \$23.91/h at the median income, used in route search.

</div>

**Table 15.** Mode parameters.

| Mode | Travel time (utils/h) | Distance cost ($/km) |
|---|---:|---:|
| Car | 0 | 0.1112 |
| Ride | 0 | 0 |
| Transit | 0 | 0 |
| Walk | 0 | — |
| Bike | 0 | — |

Every travel minute loses only the performing rate (0.78 utils/h), so all minutes are valued alike, as in the
generalised cost of the MAST work tour-mode model. Car operating cost: AAA 2017; the car passenger does not pay;
transit fares are flat per ride and do not affect the route. Mode constants are 0 (no mode choice).

**Table 16.** Activity types.

| Activity | Typical duration |
|---|---:|
| Home | 12 h |
| Work<sup>a</sup> | 8 h |
| Education | 6 h |
| Shopping<sup>b</sup> | 2 h |
| Other | 2 h |
| Social and recreation | 1.5 h |
| Eat | 45 min |
| Errand | 30 min |
| Escort | 15 min |

Home, work, shopping and other are split into 162 duration classes of 10 min.
<div class="tnote" markdown>

<sup>a</sup> Open 06:00–21:00; 5,184 types with a planned arrival time, used by the late-arrival penalty.

<sup>b</sup> Open 08:00–20:00.

</div>

## 5. Outputs

**Table 17.** Outputs.

| Output | Use |
|---|---|
| Link volumes, hourly and daily | counts, screenlines, continuous counters |
| Trips and legs with routes | vehicle-miles, trip lengths, travel times |
| Transit boardings by line | National Transit Database |
| Congested travel times | analysis; not fed back (skims are fixed) |

Validation: [Traffic](../calibration-validation/validation/traffic.md),
[Interstates by station](../calibration-validation/validation/interstates.md).

## Running

```bash
miles assignment network      # road networks 2024 and 2026
miles assignment transit      # GTFS merge, conversion, mapping
miles assignment plans        # MAST plans -> MATSim population
miles assignment run          # one run
miles assignment seeds        # several seeds
miles assignment validate     # counts, screenlines, counters
```
