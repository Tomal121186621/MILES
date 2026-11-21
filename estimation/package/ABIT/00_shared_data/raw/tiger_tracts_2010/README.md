# raw/tiger_tracts_2010

**TIGER/Line 2010 census tracts of DE, DC, MD, PA, VA, WV** (U.S. Census Bureau)

- URL: https://www2.census.gov/geo/tiger/TIGER2010/TRACT/2010/ (verify: files tl_2010_<state FIPS>_tract10.zip; no download log in the project)
- How: Download tl_2010_10_tract10.zip, tl_2010_11_tract10.zip, tl_2010_24_tract10.zip, tl_2010_42_tract10.zip, tl_2010_51_tract10.zip, tl_2010_54_tract10.zip and unzip each into a folder of the same name. Used by the tract-to-zone overlay (prep_dc_data.overlay) and the TAZ / tract splits (taz_crosswalk.py, rts_11_data_v2.py).
- Files: tl_2010_<st>_tract10/tl_2010_<st>_tract10.shp (st = 10, 11, 24, 42, 51, 54)
- Notes: tract_zone_overlay.parquet is provided (00_shared_data/zones).


- Files shipped: tl_2010_10_tract10.zip, tl_2010_10_tract10/, tl_2010_11_tract10.zip, tl_2010_11_tract10/, tl_2010_24_tract10.zip, tl_2010_24_tract10/, tl_2010_42_tract10.zip, tl_2010_42_tract10/, tl_2010_51_tract10.zip, tl_2010_51_tract10/, tl_2010_54_tract10.zip, tl_2010_54_tract10/, copied 2026-11-17 from Validation_2026/data/raw/tiger_tracts_2010 (project-relative to VAE-SILO-MITO-MATSIM).
