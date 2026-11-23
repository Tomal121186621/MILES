# raw/mstm_zone_system

**MSTM zone system: SMZ/RMZ polygons, zone table, DAYMAP (Daily Activity Model for Agent Plans) zone attributes** (MDOT (MSTM), via ABIT/input/mito_los/Zonal and 2_silo/input/zoneSystem.csv; ABIT/input/maryland/zone_attributes.csv (DAYMAP Maryland set-up))

- URL: https://www.roads.maryland.gov/ (verify: provided with the MSTM)
- How: Zone polygons SMZ_RMZ_02152011inMSTM_EPSG26918.shp (+ .dbf .shx .prj; field id / SMZRMZ, 1,588 zones), zoneSystem.csv (ZoneId, COUNTYFIPS, ...), zone_attributes.csv (id, centroid x/y EPSG:26985, countyfips, region types, bbsr, area_km2; built for DAYMAP from mstm_26985.shp and zoneSystem.csv, see 3_abit/coef_respec/PROVENANCE.md, script not in the project).
- Files: SMZ_RMZ_02152011inMSTM_EPSG26918.shp/.dbf/.shx/.prj, zoneSystem.csv, zone_attributes.csv
- Notes: zone_attributes.csv is provided in 00_shared_data/zones; the shapefile is needed only to rebuild tract_zone.csv, the tract-to-zone overlay, the TAZ crosswalks and the transit skims.


- Files shipped: SMZ_RMZ_02152011inMSTM_EPSG26918.cpg, SMZ_RMZ_02152011inMSTM_EPSG26918.dbf, SMZ_RMZ_02152011inMSTM_EPSG26918.prj, SMZ_RMZ_02152011inMSTM_EPSG26918.qpj, SMZ_RMZ_02152011inMSTM_EPSG26918.sbn, SMZ_RMZ_02152011inMSTM_EPSG26918.sbx, SMZ_RMZ_02152011inMSTM_EPSG26918.shp, SMZ_RMZ_02152011inMSTM_EPSG26918.shp.xml, SMZ_RMZ_02152011inMSTM_EPSG26918.shx, zoneSystem.csv, zone_attributes.csv, copied 2026-11-17 from ABIT/input/mito_los/Zonal (shapefile), Validation_2026/2_silo/input/zoneSystem.csv, ABIT/input/maryland/zone_attributes.csv (project-relative to VAE-SILO-MITO-MATSIM).
