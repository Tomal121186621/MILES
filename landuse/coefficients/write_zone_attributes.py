#!/usr/bin/env python3
"""Fixed zone attributes of the land-use terms of the re-specified zone part (2026-11-10), new file only:
  2_silo/input/residential_zone_attributes.csv   zone,acres,park  (acres of zoneSystem.csv; paid-parking share of r11_zone_landuse.py)
The engine recomputes dwelling density, job density, retail density and mix every year from its dwellings and jobs.
    python3 landuse/coefficients/write_zone_attributes.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import pandas as pd
V = f"{WORKSPACE}"; OUT = f"{V}/2_silo/input/residential_zone_attributes.csv"
L = pd.read_csv(f"{ESTIMATION_RESULTS}/residential/zone_landuse_2016.csv")
zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv")[["ZoneId", "ACRES"]].rename(columns={"ZoneId": "zone", "ACRES": "acres"})
out = zs.merge(L[["zone", "park"]], on="zone"); assert len(out) == len(zs) == 1588 and out.notna().all().all()
assert not os.path.exists(OUT); out.to_csv(OUT, index=False); print(out.describe().T)
