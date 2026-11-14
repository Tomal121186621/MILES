# Zone system and networks

## Zones

| Item | Value |
|---|---|
| Zones | 1,588 (Maryland Statewide Transportation Model) |
| Area | Maryland, District of Columbia, parts of Virginia, Pennsylvania, Delaware and West Virginia |
| Land-use regions | 44 counties (one region per Maryland county) |
| Study area | Baltimore City and the counties of Anne Arundel, Baltimore, Carroll, Harford and Howard |
| Coordinate system | EPSG:26985 (NAD83, Maryland) |

The zone system and its polygons come from MDOT on request; they are not part of the repository.

## Skims

Land use and activities read fixed zone-to-zone skims, stored as gzipped CSV with columns `FROM,TO,VALUE`
(2,521,744 pairs each):

| Skim | File | Source |
|---|---|---|
| Car time, AM peak | `auto_peak_time.csv.gz`, `traveltime_auto.csv.gz` | MSTM base year |
| Car distance | `distance_auto.csv.gz` | MSTM |
| Transit door-to-door time | `transit_peak_time.csv.gz` | Computed on the MATSim transit schedule (SwissRailRaptor, `pipeline/transit_skim.py`) |
| Bus and rail time | `bus_tt.csv.gz`, `rail_tt00.csv.gz` | Same |

## Road network

Built by `assignment/network/build_networks.py` from OpenStreetMap (via pt2matsim) as `network_2024.xml.gz`, with the
Key Bridge closed.

- Free speed: posted speed, × 0.9 below 51 km/h; missing tags filled from MDOT SHA speed signs or the road-class median
  nearby (`recode_speed_capacity.py`, rules in `SPEED_CAPACITY.md`).
- Capacity: per lane by road class (1,500 veh/h primary, 800 secondary, 600 tertiary and residential), Highway
  Capacity Manual bottleneck capacity on motorways and trunk roads.
- Tolls: `roadpricing_HARB_2024.xml`, \$3.00 per crossing of the Fort McHenry and Baltimore Harbor tunnels.
- Count stations are matched to links by `match_count_stations.py`.

## Transit

`assignment/transit/build_transit.sh` builds the schedule from the GTFS feeds of the region's operators (MTA local
and commuter bus, Light Rail, Metro, MARC, Charm City Circulator, county services, WMATA and others):

1. merge the feeds (`merge_gtfs.py`);
2. convert them for a weekday (`Gtfs2TransitSchedule`);
3. map routes on the road network guided by the GTFS shapes (`MapWithShapes`);
4. clean routes and set vehicle types;
5. check plausibility.

Outputs: `transitSchedule_2024.xml.gz`, `transitVehicles_2024.xml.gz`, `network_2024_pt.xml.gz`.
