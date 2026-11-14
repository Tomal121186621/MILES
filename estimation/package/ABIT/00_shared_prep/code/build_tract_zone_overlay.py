#!/usr/bin/env python3
"""Tract-to-zone measurement weights of the location models (prep_dc_data.overlay, unchanged): 2010 census tracts of DE, DC,
MD, PA, VA, WV intersected with the 1,588 MSTM zones; b = overlap area / zone area, overlaps below 1 % of the tract dropped.

    python3 build_tract_zone_overlay.py     (needs geopandas)  reads raw/tiger_tracts_2010/tl_2010_<st>_tract10/*.shp,
                                            raw/mstm_zone_system/SMZ_RMZ_02152011inMSTM_EPSG26918.shp
                                            writes rebuilt/zones/tract_zone_overlay.parquet
"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_dc_data as PD   # noqa: E402
o = PD.overlay(); print(o.shape)
