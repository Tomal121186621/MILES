# raw/taz_bmc

**BMC TAZ2010 for the Activity Based Model (the BMC TAZ codes of the RTS)** (Baltimore Metropolitan Council GIS)

- URL: https://gis.baltometro.org/arcgis/rest/services/Regional_Boundaries/MapServer/14 (and /15 for the vintage check)
- How: ArcGIS REST query: where=1=1, outFields=*, outSR=26918, f=geojson -> layer14.geojson (and layer15.geojson). Documented in Validation_2026/data/raw/taz_bmc/SOURCES.txt and 2_silo/jobchoice/TAZ_CROSSWALK.md.
- Files: layer14.geojson, layer15.geojson
- Notes: Layer note: do not distribute to third parties without asking the BMC Modelling Group. Used for the TAZ crosswalk of the TAZ-located records (models 01-05).

