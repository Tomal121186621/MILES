# Network audit: 2024 road network against MDOT SHA inventories

Audit date 2026-10-21. Network: `network_2024.xml.gz` (built by `build_networks.py` from the OpenStreetMap extract of Maryland with
replication timestamp 2026-06-11, converted with pt2matsim in EPSG:26985; freeway capacities from HCM bottleneck analysis; non-freeway
classes reconciled with the MDOT functional classification; posted speeds from the OSM `maxspeed` tag). The 2026 network differs by
the change list in `changes_2024_2026.csv` only. MDOT layers: `fetch_mdot.py`, downloaded 2026-10-21 into `data/raw/mdot_sha/`.
Study area: the six Baltimore-region counties (Anne Arundel, Baltimore, Baltimore City, Carroll, Harford, Howard).

## Size

| | nodes | links | car links | car links in the six counties | km of car links in the six counties |
|---|---|---|---|---|---|
| network_2024 | 214,599 | 473,098 | 469,434 | 263,661 | 40,148 |

Freeways and expressways (motorway, trunk) in the six counties: 7,442 links, 1,764 km; ramps: 5,049 links.

## 1 Functional class (MDOT SHA Roadway Functional Classification)

Method: the nearest MDOT centreline segment within 20 m of the link midpoint with a bearing within 30 degrees of the link. OSM classes map to
MDOT groups as motorway = 1 or 2, trunk = 2 or 3 (an OSM trunk road is an expressway or a principal arterial without full access control), primary = 3,
secondary = 4, tertiary = 5 or 6, residential/unclassified/living_street/service = 7. Ramps agree when MDOT inventories a ramp or a class 1-4 road there.

- Matched: 76.2 % of car links in the area (65.8 % of km). Unmatched links are mostly service roads,
  driveways and private roads that MDOT does not inventory, and links farther than 20 m from the inventoried centreline (dual carriageways with wide medians).
- Agreement: 83.3 % of matched links, 81.6 % of matched km. OSM lower than MDOT (e.g. OSM residential, MDOT collector): 12,781 links;
  OSM higher than MDOT: 28,049 links.
- By OSM group (non-ramp links): group 1: n=3,244, agree 94.7 %, OSM lower 0.0 %, OSM higher 34.9 %; group 2: n=3,655, agree 83.4 %, OSM lower 0.1 %, OSM higher 90.8 %; group 3: n=16,594, agree 62.7 %, OSM lower 2.2 %, OSM higher 35.1 %; group 4: n=21,132, agree 65.9 %, OSM lower 7.8 %, OSM higher 26.4 %; group 5: n=28,328, agree 56.0 %, OSM lower 14.7 %, OSM higher 43.1 %; group 7: n=125,153, agree 94.7 %, OSM lower 5.3 %, OSM higher 0.0 %.

Crosstab (links and km): `data/network_audit_class_crosstab.csv`; summary by class: `data/network_audit_class_summary.csv`; figure `fig_net_class_matrix`.

Resolution: the supply network already carries the capacity and base speed of the MDOT class wherever MDOT rates a road higher than OSM
(links were upgraded, never downgraded, in `build_network_v8.py`); the residual "OSM lower" cells are links whose MDOT match failed the 20 m / 30 degree
test in that step or whose MDOT class is 1-2 while OSM has primary/secondary (expressway sections of US 40, MD 295, MD 10 and similar, where
OSM tags the road trunk/primary). These links keep their OSM-class capacity; their count and km are stated above and in the crosstab. The
"OSM higher" cells (OSM primary, MDOT minor arterial or collector) are left as in OSM: MDOT's classification is a federal-aid category, OSM's
is a traffic-role tag, and for assignment the higher capacity is the conservative choice on a road that carries arterial traffic. Both groups
are flagged per link in `network_audit_links.parquet` (`fc_delta`) so count-station comparisons can be stratified by agreement.

## 2 Lanes (MDOT SHA Roadway Lane Mileage)

Method: mainline lane-miles divided by segment length gives the inventoried through lanes of both directions (the inventory-direction segment
carries the total; verified on I-695 where 2, 3 and 4 network lanes per direction meet 4, 6 and 8 inventoried lanes); the total is halved for
every road with two directions and kept for one-way streets. Compared with the network's `permlanes` for 19,364 non-ramp links matched within 20 m.

- Equal lanes: 71.0 %; network fewer: 5.6 %; network more: 23.4 %; km-weighted mean difference (network minus MDOT) +0.05 lanes.
- By class: motorway: equal 53.8 %, fewer 13.9 %, more 32.3 % (n=1,124); trunk: equal 66.6 %, fewer 8.0 %, more 25.4 % (n=2,600); primary: equal 64.7 %, fewer 3.3 %, more 32.0 % (n=6,671); secondary: equal 78.1 %, fewer 4.5 %, more 17.4 % (n=7,586); tertiary: equal 85.6 %, fewer 8.3 %, more 6.0 % (n=829); residential: equal 79.6 %, fewer 18.6 %, more 1.8 % (n=392); unclassified: equal 93.2 %, fewer 5.6 %, more 1.2 % (n=162).

Table: `data/network_audit_lanes.csv`. The freeway lane counts were set from MDOT lane counts at the HCM capacity step (I-695) and from the
OSM `lanes` tag elsewhere; differences on arterials are dominated by turn lanes at intersections (MDOT counts through lanes only) and by
OSM ways tagged with the two-way total on one-way pairs. Resolution: lanes are left as coded; capacity on arterials is governed by the per-lane
value of the class (section 4), and the lane difference is reported per link (`lane_delta`) for the count comparison.

## 3 Posted speeds (OSM maxspeed vs MDOT SHA posted-speed-limit signs)

Method: each of the 3,424 MDOT sign records in the area is attached to the nearest car link within 30 m whose direction agrees with the sign's
travel direction; 3,005 signs attach. The sign's limit is compared with the OSM `maxspeed` tag of the link's way (available for 68.8 % of
attached signs) and with the coded free speed.

- OSM tag equals the MDOT sign: 84.3 %; within 5 mph: 91.4 %; mean difference (OSM minus MDOT) +0.2 mph (p10 +0, p90 +0).
- Coded free speed minus MDOT sign: mean +3.2 mph (p10 -5, p90 +10). On non-freeway classes the coded speed is
  below the posted limit by construction (class base speed scaled by posted / class median, so that signal delay and stops are carried by the link speed).
- OSM `maxspeed` coverage in the area: motorway 97.3 %; trunk 87.7 %; primary 83.4 %; secondary 68.0 %; tertiary 49.1 %; residential 27.0 %.
- By class: motorway: n=202, equal 86.5 %, within 5 mph 90.6 %; trunk: n=465, equal 84.9 %, within 5 mph 91.5 %; primary: n=906, equal 82.5 %, within 5 mph 91.4 %; secondary: n=1117, equal 85.5 %, within 5 mph 91.8 %; tertiary: n=184, equal 86.9 %, within 5 mph 92.9 %; residential: n=71, equal 41.7 %, within 5 mph 75.0 %.

Tables: `data/network_audit_speeds.csv`, `data/network_audit_speed_pairs.csv`, coverage `data/network_audit_speed_coverage.csv`; figure `fig_net_speed_osm_mdot`.
Resolution: the signs cover state routes only (MDOT SHA inventory) and give the limit at the sign, which changes between signs; a difference of
5 mph within a tagged way is the resolution of the comparison. Links where the OSM tag and the sign differ by more than 5 mph are listed in the
pairs table with the sign's route and milepost; they are not corrected here because the sign inventory has no segment extent and a one-sided change would
mix two sources on one road. The NPMRDS free-flow and congested speed check is open (section 7).

## 4 Capacity per lane by class

| class | links | km | lanes (median) | capacity per lane p10 | median | p90 | reference |
|---|---|---|---|---|---|---|---|
| motorway | 3,560 | 1,073 | 3 | 2,000 | 2,000 | 2,043 | 2,000-2,400 (HCM 2016 basic freeway segments, pc/h/ln at free-flow 55-75 mph) |
| motorway_link | 2,871 | 610 | 1 | 1,158 | 2,100 | 2,100 | 1,800-2,200 (HCM ramp roadways) |
| trunk | 3,882 | 690 | 2 | 1,500 | 1,500 | 1,500 | 1,800-2,200 (multilane highways) |
| trunk_link | 566 | 60 | 2 | 118 | 1,070 | 2,000 | 1,500-2,000 |
| primary | 17,133 | 1,809 | 2 | 900 | 900 | 900 | 800-1,200 veh/h/ln (signalised arterial: 1,900 saturation x 0.45-0.60 green) |
| primary_link | 852 | 74 | 1 | 900 | 900 | 900 | 800-1,200 |
| secondary | 22,723 | 3,182 | 1 | 1,000 | 1,000 | 1,000 | 700-1,000 |
| secondary_link | 525 | 32 | 1 | 1,000 | 1,000 | 1,000 | 700-1,000 |
| tertiary | 32,696 | 5,844 | 1 | 600 | 600 | 1,000 | 500-800 |
| tertiary_link | 235 | 13 | 1 | 600 | 600 | 600 | 500-800 |
| residential | 168,023 | 24,622 | 1 | 600 | 600 | 600 | 300-600 |
| unclassified | 10,566 | 2,132 | 1 | 600 | 600 | 600 | 300-600 |
| living_street | 27 | 2 | 1 | 300 | 300 | 300 | 200-400 |
| other | 2 | 4 | 2 | 2,000 | 2,000 | 2,000 |  |

Table: `data/network_audit_capacity.csv`. Freeway and ramp capacities on I-695 are HCM bottleneck values (merge, diverge, weave and lane-drop
segments), the remaining freeways carry 2,000 veh/h/lane; arterials carry one value per class from the converter, scaled by the MDOT class where
a link was upgraded. The arterial values sit at the top of or above the signalised reference range; they are stated here and tested by the count
comparison at arterial stations (stage 4 report), not changed before that test.

## 5 Connectivity

- Largest strongly connected component: 99.999 % of car links in the whole network (99.997 % of km); in the six counties 99.997 % of links
  (7 links outside it).
- Dead-end links (no outgoing car link at the end node): 0 in the whole network, 0 in the six counties, of which 0 on
  motorway/trunk/primary/secondary links (`data/network_audit_dead_ends_major.csv`).
  Two-way streets end in a node that still has the return link, so cul-de-sacs are not dead ends; at the closed Key Bridge the I-695 mainline is cut at the
  exit 44 and exit 1 junction nodes, whose ramps carry the traffic back.
- Source-only links (no incoming car link at the start node): 3 in the six counties.

Table: `data/network_audit_connectivity.csv`. Agents can only be routed inside the strongly connected component; the count-station matching
step verifies that every matched link is inside it.

## 6 I-695 interchanges by exit number

Method: OSM `motorway_junction` nodes within 40 m of an I-695 mainline link give the exit numbers (`data/osm_motorway_junctions.csv`; the letter
suffixes A/B/C of split exits are grouped under the exit number); for each exit, motorway_link links within 500 m are classified as off-ramps
(leaving a Beltway node) or on-ramps (joining one). MDOT: SHA interchange-exit points (exits 4-32, the SHA-maintained section) and the SHA ramp
inventory of route RP 695 (all exits, including the MDTA-maintained section, exits 1-3 and 33-44; I-695 has no exit 37).

- Exits with junction nodes in OSM: 43 (1-44); with both on- and off-ramps in the network: 43.
- Exits in the MDOT inventories without an OSM junction node: none.
- Exits without ramps in one direction: none.

| exit | OSM refs | crossing road (MDOT) | off-ramps | on-ramps | MDOT ramps inventoried |
|---|---|---|---|---|---|
| 1 | 1 | MD 695 EB; MD 695 WB; QUARANTINE RD; QUARANTINE RD NB; QUARANTINE RD SB; RAMP 4 | 1 | 1 | 6 |
| 2 | 2 | MD 10 SB; MD 695 EB; MD 695 WB | 4 | 2 | 4 |
| 3 | 3;3A;3B | MD 2 NB; MD 695 EB; MD 695 WB; MD 711; MD 711 NB; RAMP 1 (TO MD 695) | 6 | 6 | 6 |
| 4 | 4 | IS 97   NO NAME (SB/L) | 5 | 5 | 0 |
| 5 | 5 | MD 648E  BALTO ANNAPOLIS BLVD (SB/L) | 5 | 5 | 8 |
| 6 | 6A;6B | MD 170   CAMP MEADE RD (SB/L) | 2 | 2 | 4 |
| 7 | 7A;7B | MD 295   BALTIMORE WASHINGTON PKWY (SB/L) | 5 | 6 | 8 |
| 8 | 8;8A;8B | MD 168   NURSERY RD; RP 695   RAMP 5 FR IS 695 SB TO IS 895 EB | 6 | 6 | 7 |
| 9 | 9 | CO 3239   HOLLINS FERRY RD | 3 | 3 | 6 |
| 10 | 10 | US 1AL WASHINGTON BLVD (SB/L) | 1 | 3 | 5 |
| 11 | 11A;11A;11B;11B | IS 95   NO NAME | 4 | 3 | 0 |
| 12 | 12A;12B-C;12B;C;12C-B | MD 372   WILKENS AVE (WB/L); US 1   SOUTHWESTERN BLVD (SB/L) | 3 | 3 | 15 |
| 13 | 13 | MD 144   FREDERICK RD | 4 | 4 | 5 |
| 14 | 14 | CO 2600   EDMONDSON AVE | 4 | 4 | 5 |
| 15 | 15A;15B | US 40   BALTO NATIONAL PIKE | 5 | 3 | 9 |
| 16 | 16A-B;16A;16B | RP 70   RAMP 7 FR RAMP 2 TO RAMP 6 (TO IS695 SB) | 4 | 4 | 0 |
| 17 | 17 | MD 122   SECURITY BLVD (WB/L) | 3 | 3 | 8 |
| 18 | 18;18A;18A-B;18B | MD 26   LIBERTY RD | 2 | 4 | 9 |
| 19 | 19 | RP 695   RAMP 1 FR IS 695 NB TO IS 795 WB | 2 | 2 | 4 |
| 20 | 20 | MD 140   REISTERSTOWN RD (SB/L) | 3 | 4 | 8 |
| 21 | 21 | MD 129   PARK HEIGHTS AVE | 3 | 3 | 7 |
| 22 | 22 | CO 722   GREENSPRING AVE | 2 | 2 | 7 |
| 23 | 23A;23A-B;23B | MD 25A  JONES FALLS EXPWY (SB/L) | 3 | 4 | 0 |
| 24 | 24 | RP 83   RAMP 3 FR IS 83/IS 695 EB TO IS 83 NB | 3 | 4 | 0 |
| 25 | 25 | MD 139   CHARLES ST (SB/L) | 4 | 5 | 8 |
| 26 | 26;26A;26B | MD 45   YORK RD | 4 | 4 | 8 |
| 27 | 27A;27B | MD 146   DULANEY VALLEY RD | 5 | 3 | 9 |
| 28 | 28 | CO 3334   PROVIDENCE RD | 2 | 2 | 8 |
| 29 | 29A;29B;29B-A | CO 3353   CROMWELL BRIDGE RD; MD 542   LOCH RAVEN BLVD (SB/L) | 3 | 4 | 6 |
| 30 | 30A;30B | MD 41   PERRING PKWY (SB/L) | 4 | 4 | 8 |
| 31 | 31A;31A-B;31B;31C | MD 147   HARFORD RD; MD 43   WHITE MARSH BLVD | 3 | 4 | 8 |
| 32 | 32A;32B | US 1   BELAIR RD (SB/L) | 4 | 4 | 8 |
| 33 | 33 |  | 2 | 3 | 0 |
| 34 | 34 | MD 695 NB; MD 695 SB; MD 7 EB; MD 7 WB; RAMP 6 (TO MD 695) | 4 | 3 | 7 |
| 35 | 35A;35B | GOLDEN RING RD; MD 695 NB; MD 695 SB; RAMP 7; US 40 EB; US 40 WB | 6 | 6 | 9 |
| 36 | 36 | MD 695 SB; MD 702 EB | 2 | 2 | 2 |
| 38 | 38;38A;38B | MD 150 EB; MD 150 WB; MD 695 SB; RAMP 1 (TO MD695) | 5 | 3 | 6 |
| 39 | 39 | MD 157 SB; MD 695 WB; RAMP 4 (TO MD 150) | 3 | 1 | 3 |
| 40 | 40 | MD 151 EB; MD 151 WB; MD 695 NB; MD 695 SB | 4 | 2 | 4 |
| 41 | 41 | COVE RD; COVE RD EB; COVE RD WB; MD 695 NB; MD 695 SB; RAMP 6 (TO MD 695); RAMP  | 2 | 2 | 8 |
| 42 | 42 | MD 151 EB; MD 151 WB; MD 695 NB | 1 | 1 | 4 |
| 43 | 43 | MD 157 NB; MD 157 SB; MD 158 EB; MD 158 WB; MD 695 NB; MD 695 WB; RAMP 9 (TO MD6 | 2 | 1 | 8 |
| 44 | 44 | MD 695 SB; MD 695 Y; MD 695A WB; RP 6 (TO MD 695 SB) | 1 | 1 | 5 |

Table: `data/network_audit_i695_interchanges.csv`. Between exit 44 (MD 695A, Hawkins Point) and exit 1 (MD 173, Quarantine Road) the mainline
is cut at the closed Key Bridge in both loops; the ramps of these two exits are the ends of the Beltway in the 2024 and 2026 networks. Ramp capacities and gore geometry on I-695 were set from HCM and MDOT lane
counts in the supply network (`I695_pricing/12_corridor_fit/fix_ramps.py`); this audit checks presence, not capacity.

## 7 Open items

- NPMRDS travel times (free-flow and congested speeds by segment, 2024) are not available: the RITIS portal requires an account and a data
  request (`Updated MATSim/data/npmrds_2023/README_ACCESS.md`). The free-flow and congested speed check stays open until the extract is obtained.
- MDOT posted speeds exist only as a sign inventory on state routes; county and city roads are checked against the OSM tag alone.
- The 2026 network has no observed counterpart yet; its only difference from 2024 is the change list.
