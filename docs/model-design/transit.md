# Public transit in the assignment

!!! abstract "At a glance"

    | | |
    |---|---|
    | **Timetables** | 18 GTFS feeds, one weekday (Wednesday 21 October 2026) |
    | **Transit vehicles** | on their own links, on schedule (as in the Open Berlin scenario) |
    | **Router** | SwissRailRaptor, walk access to every stop, car access to rail stations with park-and-ride |
    | **Boarding** | any vehicle that serves the traveller's alighting stop |
    | **Stuck vehicles** | kept in the simulation |
    | **Mode** | fixed by DAYMAP (Daily Activity Model for Agent Plans); MATSim chooses the access, the stops, the lines and the departure |

DAYMAP decides who travels by transit. MATSim finds each transit trip a route through the timetable and
simulates the vehicles and their passengers. This page describes the transit network, how it is simulated, and why
it is set up this way.

## 1. Network

[:material-fullscreen: Open the map full screen](../assets/maps/transit_map.html){ .md-button .md-button--primary target="_blank" }

<iframe src="../../assets/maps/transit_map.html" title="Transit network and park-and-ride lots"
        style="width:100%; height:78vh; border:1px solid var(--md-default-fg-color--lightest); border-radius:6px;"
        loading="lazy"></iframe>

<div class="tnote" markdown>
Lines drawn along the GTFS shape used by most trips of the route, between its first and last stop inside the network
area. Hover a line, station or lot for its name; the layer control (top right) switches each service type and the stops
with car access. Base map © OpenStreetMap contributors.
</div>

**Table 1.** Transit service on the modelled weekday (inside the network area).

| Service | Mode | Routes | Trips |
|---|---|---:|---:|
| MTA local bus | Bus | 66 | 6,052 |
| MTA commuter bus | Bus | 33 | 274 |
| MTA Light RailLink | Light rail | 1 | 304 |
| MTA Metro SubwayLink | Metro | 1 | 247 |
| MARC train | Commuter rail | 3 | 95 |
| Amtrak | Intercity rail | 7 | 115 |
| WMATA Metrorail (Maryland stations) | Metro | 6 | 1,509 |
| WMATA Metrobus (Maryland routes) | Bus | 78 | 8,658 |
| County and city buses<sup>a</sup> | Bus | 156 | 7,563 |
| Harbor Connector | Ferry | 3 | 282 |

<div class="tnote" markdown>
<sup>a</sup> Montgomery Ride On, Prince George's TheBus, RTA of Central Maryland, Anne Arundel, Annapolis, Harford,
Carroll, Charm City Circulator, Towson Loop. Feeds, calendars and the clip to the network area: [Transit data](../inputs-outputs/data/transit.md).
</div>

## 2. How transit is simulated

The set-up follows published MATSim practice (Table 2).

**Table 2.** Transit settings and their source.

| Element | Setting | Practice followed |
|---|---|---|
| Transit vehicles | Every route runs on its own links between consecutive stops. Link speeds are set so that no trip is late, with 30 s at every stop for boarding and alighting; stops with the same scheduled minute are spread evenly. Vehicles wait at each stop for the scheduled departure. | Open Berlin scenario: MATSim's GTFS tool with its pseudo network and its speed rule [1, 2] |
| Stuck vehicles | Kept; a vehicle blocked for 120 s is pushed on, not removed. | MATSim default, Open Berlin scenario [2] |
| Boarding | A traveller boards any vehicle that serves the stop where they plan to get off. | Recommendation of the MATSim developers for travellers stranded after a missed vehicle [3] |
| Walk access and egress | Every stop; search from 4 km, widened in 2 km steps until a stop is found. | SwissRailRaptor default |
| Car access and egress | Only for persons whose household owns a car and who hold a licence; only to rail, Metro and Light RailLink stations with park-and-ride (Section 3), and only when the trip rides rail; search up to 25 km. Car access only from home, car egress only to home. | SBB's intermodal SwissRailRaptor (person and stop filters) [4]; the park-and-ride tour rule of the eqasim Paris study [5] |
| Car access traffic | Drives to and from the station are routed and simulated on the road network like any car trip. | — |
| Scoring of travel | Every travel minute is valued alike (car, car passenger, transit door to door, drive access); money at the traveller's value of time (half the household income per working hour); car operating cost \$0.1112/km (AAA 2017); transit fares are flat per ride and so do not affect the route. | The generalised cost of the DAYMAP work tour-mode model, so that MATSim routes travellers with the trade-offs DAYMAP was estimated with |
| Transfer penalty | −0.13 utils per transfer, about 10 in-vehicle minutes | Open Berlin scenario, about 9 min [2] |
| Transfer walk | Walks between stops for a transfer up to 300 m | Open Berlin and the other VSP scenarios [2]; MATSim default 100 m |
| Walk instead of transit | Not allowed while a transit route exists. | Modes are fixed by DAYMAP |

Mode choice stays off: a transit trip of DAYMAP remains a transit trip. Each iteration, 15 % of agents reroute
(which may change the stops, the lines and the access mode) and 10 % shift departure times; plans are no longer changed
after iteration 90.

## 3. Park-and-ride stops

A stop gets car access when it is served by MARC, Amtrak, Metro SubwayLink, Metrorail or Light RailLink and a
park-and-ride lot lies within 400 m. Car access is limited to rail as in DAYMAP, whose train alternative has drive access
and whose bus alternative has walk access only; a route that drives to a station and then rides only buses is routed again
without the car. The lots are those tagged `park_ride` in OpenStreetMap
(273 lots in Maryland and the District of Columbia). Stations whose operator lot is not tagged in OpenStreetMap were
added from the operator and station descriptions (23 stops, among them Baltimore Penn Station, Perryville, Glen Burnie,
Ferndale, Linthicum, Falls Road, Timonium and North Bethesda).

**Table 3.** Stops with car access.

| Service | Stops<sup>a</sup> | Stations or stop locations |
|---|---:|---:|
| MARC | 61 | 32 |
| Amtrak | 11 | 11 |
| Light RailLink | 38 | 19 |
| Metro SubwayLink | 13 | 7 |
| Metrorail | 27 | 24 |
| **Total** | **150** | **93** |

<div class="tnote" markdown>
<sup>a</sup> One stop per platform or direction, as in the timetables.
</div>

## 4. Why this set-up

When buses and trains are mapped onto the road network and stuck vehicles are removed, a vehicle delayed or removed in
traffic strands its passengers and everyone waiting for it further down the route, and travellers who miss a planned
transfer may wait for good. Running every transit vehicle on its own links and on schedule, keeping stuck vehicles
and letting travellers board any vehicle that serves their alighting stop avoids these losses, as in the Open Berlin
scenario. The transfer penalty and the transfer walk follow published MATSim scenarios; neither is fitted to ridership or
counts.

## Sources

1. Ziemke, D., Kaddoura, I., Nagel, K. (2019). The MATSim Open Berlin Scenario. *Procedia Computer Science* 151, 870–877.
   [Working paper](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2019/19-01/ZiemkeEtAl2019OpenBerlinScenarioVSPWP.pdf)
2. MATSim Open Berlin scenario, configuration and build ([matsim-berlin](https://github.com/matsim-vsp/matsim-berlin));
   MATSim `CreateTransitScheduleFromGtfs` and `AdjustSameDepartureTimes` ([matsim-libs](https://github.com/matsim-org/matsim-libs)).
3. MATSim developers, "Agents which are using PT get stuck and abort"
   ([matsim-code-examples issue 119](https://github.com/matsim-org/matsim-code-examples/issues/119)).
4. Swiss Federal Railways, MATSim extensions: intermodal access and egress of the SwissRailRaptor
   ([matsim-sbb-extensions](https://github.com/SchweizerischeBundesbahnen/matsim-sbb-extensions)).
5. Yin et al. (2022). Evaluation of low traffic neighborhoods: the Paris case study. MATSim User Meeting 2022
   ([slides](https://matsim.org/conferences/mum2022/presentations/Yin_EtAl_MUM_2022_Presentation.pdf)).
