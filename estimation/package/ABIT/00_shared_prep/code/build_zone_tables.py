#!/usr/bin/env python3
"""Zone tables of the location models.

    python3 build_zone_tables.py [--jobs-from-raw]
      zones_model_attributes.csv   dc_common.zones(): ABIT zone attributes + 2016 population, jobs by type (retail / office /
                                   other), school enrolment, area dummies, retail density, land-use mix (the zone variables of
                                   every location model); reads 00_shared_data/zones (provided) or, with --jobs-from-raw, the jobs
                                   extract rebuilt from raw/synthetic_population_2016/jj_2016.csv
      jobs_2016_zone_type.parquet  (--jobs-from-raw) columns zone, type of jj_2016.csv (SILO 2016 base jobs)
    writes rebuilt/zones/
"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from pkg_paths import RAW, out
import dc_common as C      # noqa: E402

if "--jobs-from-raw" in sys.argv:
    f = out("zones/jobs_2016_zone_type.parquet")
    pd.read_csv(f"{RAW}/synthetic_population_2016/jj_2016.csv", usecols=["zone", "type"]).to_parquet(f, index=False)
    C.JOBS = f; print("wrote", f)
z = C.zones(); f = out("zones/zones_model_attributes.csv"); z.to_csv(f, index=False); print("wrote", f, z.shape)
