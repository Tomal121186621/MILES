# raw/osm

**OpenStreetMap Maryland extract** (Geofabrik)

- URL: https://download.geofabrik.de/north-america/us/maryland.html (verify: the project documents the file maryland-latest.osm.pbf, replication timestamp 2026-06-11, but not the URL)
- How: Download maryland-latest.osm.pbf. Used only indirectly: it is the source of the MATSim network (4_matsim/network: pt2matsim OSM converter, build_networks.py), on which the transit schedule is mapped and the period car times are measured.
- Files: maryland-latest.osm.pbf
- Notes: Network building is the MATSim stage of the chain, outside this package.


- Files shipped: maryland-latest.osm.pbf, copied 2026-11-17 from inputs/osm (project-relative to VAE-SILO-MITO-MATSIM).
