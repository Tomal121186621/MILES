# Raw downloads

Put the raw data here, one folder per source (catalog: `../../00_shared_prep/DATA_SOURCES.json`). The project's copies of the raw files are shipped in these folders (copied 2026-11-17; each folder's README.md says from where), except rts_2017_18 (read from ../rts_2017_18/raw) and matsim_resident_run_2023 (run no longer on disk); the chain (`../../00_shared_prep`) reads them and writes to `../rebuilt/`.

| Folder | Source | Status |
|---|---|---|
| `acs_pums_2015_2019_5yr/` | ACS PUMS 2015-2019 5-year person files of DC, MD, VA, WV | shipped (copy); documented (pattern) |
| `census2010/` | Census 2010 PL 94-171 Maryland (block housing units, H1) and 2020 PL of DC, VA, WV; 2010 Maryland blocks | shipped (copy); verify |
| `census2020_pl_dc_va_wv/` | Census 2010 PL 94-171 Maryland (block housing units, H1) and 2020 PL of DC, VA, WV; 2010 Maryland blocks | shipped (copy); verify |
| `census_gazetteer_2010/` | Census 2010 Gazetteer file of census tracts (internal points) | shipped (copy); verify |
| `census_tract_to_puma_2010/` | Census 2010 tract-to-PUMA relationship file | shipped (copy); documented (2_silo/data_sources.md) |
| `gtfs/` | MTA Maryland GTFS static feeds: local bus, light rail, metro, MARC, commuter bus; GTFS of the 13 regional operators (with the 5 MTA feeds the 18 feeds merged by merge_gtfs_full.py) | shipped (copy); documented (verified 2026-10-21); documented (verified 2026-10-22) |
| `lodes_wac/` | LEHD LODES 8, WAC 2017 (all jobs, C000) and block crosswalks of MD, DC, VA, WV, PA, DE | shipped (copy); documented |
| `lodes_wac_2017_extra/` | LEHD LODES 8, WAC 2017 (all jobs, C000) and block crosswalks of MD, DC, VA, WV, PA, DE | shipped (copy); documented |
| `matsim_network_2024/` | MATSim 2024 network with transit links and the regional transit schedule | shipped (copy); project product |
| `matsim_resident_run_2023/` | MATSim resident-only assignment of the chain (events and network), source of the car time profile by period | not shipped (run folder not found); project product |
| `matsim_tools/` | MATSim 2024.0 run jar of the project and compiled TransitSkim classes | shipped (copy); project product |
| `mstm_skims_2016/` | Maryland Statewide Transportation Model (MSTM) 2016 skims, 1,588 SMZ/RMZ zones | shipped (copy); verify (MDOT-provided) |
| `mstm_zone_system/` | MSTM zone system: SMZ/RMZ polygons, zone table, DAYMAP (Daily Activity Model for Agent Plans) zone attributes | shipped (copy); verify (MDOT-provided) |
| `osm/` | OpenStreetMap Maryland extract | shipped (copy); verify |
| `rts_2017_18/` | 2017/18 Regional Travel Survey (Baltimore and Washington regions), household travel survey, weekday travel day | not copied here (provided in ../rts_2017_18/raw); verify (no public URL) |
| `silo_workplace_work/` | SILO workplace-choice work files (RTS workers and the 2016 zone table of the workplace model) | shipped (copy); project product |
| `synthetic_population_2016/` | Synthetic 2016 base population of the chain (SILO input): persons, households, dwellings, jobs, schools | shipped (copy); project product |
| `taz_bmc/` | BMC TAZ2010 for the Activity Based Model (the BMC TAZ codes of the RTS) | shipped (copy); documented (downloaded 2026-10-27) |
| `taz_tpb/` | TPB/MWCOG TAZ 3722 system (the TPB TAZ codes of the RTS) | shipped (copy); documented (downloaded 2026-10-27) |
| `tiger_tracts_2010/` | TIGER/Line 2010 census tracts of DE, DC, MD, PA, VA, WV | shipped (copy); verify |

Sources without a folder (constants in the code, or derived): AAA 2017 driving cost, transit fares, CPI-U (not used by the DAYMAP likelihoods), paid-parking shares (from the survey).
