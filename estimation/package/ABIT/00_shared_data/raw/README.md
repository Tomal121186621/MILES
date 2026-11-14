# Raw downloads

Put the raw data here, one folder per source (catalog: `../../00_shared_prep/DATA_SOURCES.json`). Nothing is shipped in these folders; the chain (`../../00_shared_prep`) reads them and writes to `../rebuilt/`.

| Folder | Source | Status |
|---|---|---|
| `acs_pums_2015_2019_5yr/` | ACS PUMS 2015-2019 5-year person files of DC, MD, VA, WV | documented (pattern) |
| `census2010/` | Census 2010 PL 94-171 Maryland (block housing units, H1) and 2020 PL of DC, VA, WV; 2010 Maryland blocks | verify |
| `census2020_pl_dc_va_wv/` | Census 2010 PL 94-171 Maryland (block housing units, H1) and 2020 PL of DC, VA, WV; 2010 Maryland blocks | verify |
| `census_gazetteer_2010/` | Census 2010 Gazetteer file of census tracts (internal points) | verify |
| `census_tract_to_puma_2010/` | Census 2010 tract-to-PUMA relationship file | documented (2_silo/data_sources.md) |
| `gtfs/` | MTA Maryland GTFS static feeds: local bus, light rail, metro, MARC, commuter bus; GTFS of the 13 regional operators (with the 5 MTA feeds the 18 feeds merged by merge_gtfs_full.py) | documented (verified 2026-10-21); documented (verified 2026-10-22) |
| `lodes_wac/` | LEHD LODES 8, WAC 2017 (all jobs, C000) and block crosswalks of MD, DC, VA, WV, PA, DE | documented |
| `lodes_wac_2017_extra/` | LEHD LODES 8, WAC 2017 (all jobs, C000) and block crosswalks of MD, DC, VA, WV, PA, DE | documented |
| `matsim_network_2024/` | MATSim 2024 network with transit links and the regional transit schedule | project product |
| `matsim_resident_run_2023/` | MATSim resident-only assignment of the chain (events and network), source of the car time profile by period | project product |
| `matsim_tools/` | MATSim 2024.0 run jar of the project and compiled TransitSkim classes | project product |
| `mstm_skims_2016/` | Maryland Statewide Transportation Model (MSTM) 2016 skims, 1,588 SMZ/RMZ zones | verify (MDOT-provided) |
| `mstm_zone_system/` | MSTM zone system: SMZ/RMZ polygons, zone table, ABIT zone attributes | verify (MDOT-provided) |
| `osm/` | OpenStreetMap Maryland extract | verify |
| `rts_2017_18/` | 2017/18 Regional Travel Survey (Baltimore and Washington regions), household travel survey, weekday travel day | verify (no public URL) |
| `silo_workplace_work/` | SILO workplace-choice work files (RTS workers and the 2016 zone table of the workplace model) | project product |
| `synthetic_population_2016/` | Synthetic 2016 base population of the chain (SILO input): persons, households, dwellings, jobs, schools | project product |
| `taz_bmc/` | BMC TAZ2010 for the Activity Based Model (the BMC TAZ codes of the RTS) | documented (downloaded 2026-10-27) |
| `taz_tpb/` | TPB/MWCOG TAZ 3722 system (the TPB TAZ codes of the RTS) | documented (downloaded 2026-10-27) |
| `tiger_tracts_2010/` | TIGER/Line 2010 census tracts of DE, DC, MD, PA, VA, WV | verify |

Sources without a folder (constants in the code, or derived): AAA 2017 driving cost, transit fares, CPI-U (not used by the ABIT likelihoods), paid-parking shares (from the survey).
