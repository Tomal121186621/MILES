# Stage 4: MATSim traffic assignment

The code is here; networks, transit files, run outputs and validation data stay in the workspace (`WORKSPACE/4_matsim/network`,
`WORKSPACE/4_matsim/transit`, `WORKSPACE/4_matsim/validation`, `WORKSPACE/pipeline/runs*`, `WORKSPACE/data`).

Java: `engine/matsim-run` (de.umd.matsim.RunBaltimoreToll, MATSim 2024.0; build with `mvn package` -> baltimore-matsim-1.0.jar,
used from the configured MATSim folder); `engine/transit-mapping/MapWithShapes.java`: pt2matsim shape-guided mapping.

Order:
1. `network/build_networks.py` (with `recode_speed_capacity.py`, `audit_network.py`, `match_count_stations.py`, `fetch_mdot.py`,
   `fetch_gtfs.sh`, `check_transit.py`, `figures_network.py`): road networks 2024 and 2026, network audit and count-station
   matching; the harbor tolls are `WORKSPACE/4_matsim/network/roadpricing_HARB_2024.xml`.
2. `transit/build_transit.sh` (runs `merge_gtfs.py`, `clean_network.py`, `make_ptmapper_config.py`, `clean_routes.py`,
   `vehicle_types.py`, `validate_mapping.py`; feeds from `transit/fetch_gtfs_regional.sh`): transit schedule and vehicles from
   GTFS, mapped on the networks.
3. `run_seeds.sh [first_seed] [last_seed]`: MATSim 2024 seeds (calls `pipeline/run_chain.py matsim`), then
   `validation/extract_link_hours.py` writes the hourly link volumes.
4. `validation/`: count and screenline validation (`validate_counts.py`, `screenlines.py`, `tmas_hourly.py`,
   `regional_validation.py`, `route_table.py`, `mode_share.py`, `coverage_estimate.py`, `gap_*.py`, `scatter_fig.py`,
   `map_study_area.py`, `validation_map.py`, `validation_diagnostics.py`).

Run every script from the repository root, e.g. `bash assignment/run_seeds.sh 1 5`.
