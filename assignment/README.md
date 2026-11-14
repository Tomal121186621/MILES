# Stage 4: MATSim traffic assignment
Java runner: `java/matsim-run` (de.umd.matsim.RunBaltimoreToll, MATSim 2024.0; build with `mvn package` -> baltimore-matsim-1.0.jar). `java/transit_mapping`: pt2matsim shape-guided mapping.
Order:
1. network/build_networks.py (+ recode_speed_capacity.py, match_count_stations.py, fetch_mdot.py): road networks 2024 and 2026 and count-station matching; roadpricing_HARB_2024.xml: harbor tolls
2. transit/build_transit.sh, merge_gtfs.py, make_ptmapper_config.py, clean_*.py, vehicle_types.py: transit schedule and vehicles from GTFS, mapped on the network
3. validation/run_seeds_respec.sh: MATSim 2024 seeds 1-5 (calls pipeline/run_chain.py matsim), then extract_link_hours.py writes hourly link volumes
4. validation/: count and screenline validation (validate_counts.py, screenlines.py, tmas_hourly.py, regional_validation.py, route_table.py, mode_share.py, gap_*.py, scatter_fig.py, map_study_area.py)
