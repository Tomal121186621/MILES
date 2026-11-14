#!/usr/bin/env python3
"""Fixed zone attributes of the land-use terms of the re-specified zone part (2026-11-10), new file only:
  2_silo/input/resloc_zone_attributes_respec.csv   zone,acres,park  (acres of zoneSystem.csv; paid-parking share of r11_zone_landuse.py)
The engine recomputes dwelling density, job density, retail density and mix every year from its dwellings and jobs.
    python3 e05_zone_attributes.py"""
import os
import pandas as pd
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; OUT = f"{V}/2_silo/input/resloc_zone_attributes_respec.csv"
L = pd.read_csv(f"{V}/side_experiments/respec_2026-11/step_by_step/residential/zone_landuse_2016.csv")
zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv")[["ZoneId", "ACRES"]].rename(columns={"ZoneId": "zone", "ACRES": "acres"})
out = zs.merge(L[["zone", "park"]], on="zone"); assert len(out) == len(zs) == 1588 and out.notna().all().all()
assert not os.path.exists(OUT); out.to_csv(OUT, index=False); print(out.describe().T)
