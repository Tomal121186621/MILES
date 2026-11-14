# Free speed and capacity of the surface streets, network 2024 (2026-11-02)

Script: `recode_speed_capacity.py` (run with `python3 recode_speed_capacity.py network_2024_pre_speed.xml.gz network_2024.xml.gz ../transit/network_2024_pt_pre_speed.xml.gz ../transit/network_2024_pt.xml.gz`).
Per-link table: `link_speed_capacity_2024.csv.gz` (posted speed, its source, old and new free speed and capacity). Summary: `speed_capacity_summary_2024.csv`.

No traffic count and no model/count ratio was used to set any value below.

## Why

Before this step, each surface class kept the flat base speed of the earlier network, scaled by posted / class-median posted speed
(`I695_pricing/12_corridor_fit/build_network_v8.py`). The level therefore differed by class. Median coded free speed / posted speed:
primary 1.14, secondary 1.17, tertiary 1.00, residential 0.80. Per-lane capacity was 900 on primary and 1,000 on secondary roads,
600 on tertiary and residential roads. None of these class levels had a documented source.

## Scope

Car links of OSM class primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, unclassified, residential and living_street:
452,045 links. The following are **not** changed:
- motorway, trunk and their ramps (HCM bottleneck capacities, `fix_ramps.py` / `hcm_bottlenecks.py`);
- the I-95 Express Toll Lanes merge link and the Key Bridge closure;
- transit-only links, the topology, the link ids and the tolls (`roadpricing_HARB_2024.xml`).

Lanes are as coded.

## Rules

1. **Posted speed.** The first available of:
   - a. the OSM `maxspeed` tag of the link's way (Geofabrik Maryland extract, 2026-06-11; `I695_pricing/data/network_v8/osm_way_tags.csv`);
   - b. the MDOT SHA posted-speed-limit signs attached to links of the same way. This uses the median sign value; the signs come from the sign inventory, as attached in `data/network_audit_links.parquet` (`NETWORK_AUDIT.md` section 3);
   - c. the median of a/b over links with the same road name and class in the same 5 km cell;
   - d. the median of a/b over links of the same class in the same 5 km cell, if that cell has at least 5 such links. This is a local proxy for area type;
   - e. the median of a/b over the class in the whole network.

   No observed speeds exist locally: the NPMRDS request is open (`data_sources.md`), and no INRIX or HERE data is available.
2. **Free speed** = posted speed × urban factor. The factor is 0.9 below 51 km/h (posted 25 and 30 mph) and 1.0 otherwise.
   - Source: the MATSim OSM network reader, matsim-libs `contrib/osm` 2025.0, `org.matsim.contrib.osm.networkReader.LinkProperties.calculateSpeedIfSpeedTag`. It was read from the local jar `~/.m2/repository/org/matsim/contrib/osm/2025.0-PR3643`.
   - The same rule applies to every class in scope.
3. **Capacity** = capacity per lane × max(lanes, 1). The per-lane values come from the same MATSim reader (`LinkProperties.create*`):

   | class | veh/h per lane |
   |---|---|
   | primary, primary_link | 1,500 |
   | secondary, secondary_link | 800 |
   | tertiary, tertiary_link, unclassified, residential | 600 |
   | living_street | 300 |

   The class used is the MDOT-reconciled class of the supply network (`I695_pricing/data/network_v8/link_changes.csv`, column `profile`). That class is the OSM class, or the MDOT SHA functional class where MDOT rates the road higher.

## Files

| file | content |
|---|---|
| `network_2024.xml.gz` | recoded network |
| `network_2024_pre_speed.xml.gz` | the network before this step |
| `../transit/network_2024_pt.xml.gz` | the recoded MATSim run network. The same 452,045 links are rewritten; ids, transit links and modes are unchanged |
| `../transit/network_2024_pt_pre_speed.xml.gz` | the run network before this step |
| `pipeline/runs/matsim_pop/2024/population_2024_scc.xml.gz` | rebuilt with `pop_scc_links.py`. It is identical to the earlier file (`*_pre_speed`) because the topology did not change |

`network_2026.xml.gz` and `network_2026_pt.xml.gz` are not recoded yet.

## Before and after, by OSM class (whole network, medians)

| class | links | posted mph | free speed km/h, before → after | capacity veh/h, before → after |
|---|---|---|---|---|
| primary | 28,863 | 35 | 64.4 → 56.3 | 1,800 → 3,000 |
| secondary | 36,932 | 35 | 56.3 → 56.3 | 1,000 → 800 |
| tertiary | 58,334 | 30 | 48.3 → 43.5 | 600 → 600 |
| unclassified | 14,775 | 25 | 40.0 → 36.2 | 600 → 600 |
| residential | 310,083 | 25 | 32.0 → 36.2 | 600 → 600 |
| *_link (primary, secondary, tertiary) | 3,027 | 25 | 40–47 → 36.2 | as the class |

Links changed: 447,067 of the 452,045 links in scope (98.9 %), which is 95.2 % of all car links.

Sources of the posted speed:
- d (same class, 5 km cell): 54 %
- a (OSM tag): 27 %
- e (class, whole network): 13 %
- c (same road, 5 km cell): 5 %
- b (MDOT sign): 0.7 %

## Test: one seed, 2024, 10 % sample, 100 iterations (`pipeline/runs/matsim/2024_s1`)

The test is compared with the same seed on the earlier network (`2024_s1_abitfix`).

Model/count ratio, all vehicles:

| facility class | before | after |
|---|---|---|
| principal arterial | 0.87 | 0.89 |
| minor arterial | 0.75 | 0.64 |
| major collector | 0.58 | 0.54 |
| minor collector / local | 0.61 | 0.56 |
| all classes | 0.733 | 0.734 |

%RMSE for all classes went from 68.9 to 64.8.

The collector gradient by the earlier free-speed band did not flatten. At major collectors, the ratio from the ≤25 mph band to the >46 mph band was 0.47 → 0.96 before and 0.44 → 0.83 after. The gap is therefore not caused by the speed or capacity coding.
