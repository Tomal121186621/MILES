#!/usr/bin/env python3
"""Coefficient and attribute files read by the engine (resloc.model = mnl; ReslocModel.java):
  input/resloc_dwelling_mnl.csv      level (dwelling | zone), parameter, estimate, robust_se    (s04 D4, s05 Z7)
  input/resloc_region_mnl.csv        parameter, estimate, robust_se                              (s06b R8c; fixed values s.e. 0)
  input/resloc_region_attributes.csv region, state, school (SEDA 4.1), crime (crimeIndex.csv), dwelling-weighted per region
Usage: python3 landuse/lib/residential/s08_export.py [tag=prov] [region model=R8c]"""
import sys
import numpy as np, pandas as pd
from rc import *
import s06_region as RG

TAG = sys.argv[1] if len(sys.argv) > 1 else "prov"
REG = sys.argv[2] if len(sys.argv) > 2 else "R8c"
d = pd.read_csv(f"{TAB}/dwelling_final_numpy.csv")[["parameter", "estimate", "robust_se"]].assign(level="dwelling")
z = pd.read_csv(f"{TAB}/zone_final_{TAG}.csv")[["parameter", "estimate", "robust_se"]].assign(level="zone")
# 2026-10-27: a pooled slope (suffix _TOP = $75-125k and $125k+) is written under both groups' names, which the engine reads
_top = d[d.parameter.str.endswith("_TOP")]
d = pd.concat([d[~d.parameter.str.endswith("_TOP")]] + [_top.assign(parameter=_top.parameter.str.replace("_TOP", g)) for g in ("_HIGH", "_VERY_HIGH")])
pd.concat([d, z])[["level", "parameter", "estimate", "robust_se"]].to_csv(f"{INP}/resloc_dwelling_mnl.csv", index=False, float_format="%.6g")
r = pd.read_csv(f"{TAB}/region_{REG}_{TAG}.csv")[["parameter", "estimate", "robust_se"]]
r["robust_se"] = r.robust_se.fillna(0)
r.to_csv(f"{INP}/resloc_region_mnl.csv", index=False, float_format="%.6g")
_, R = RG.region_frame()
R.index.name = "region"
R[["state", "school", "crime"]].reset_index().to_csv(f"{INP}/resloc_region_attributes.csv", index=False, float_format="%.6g")
print(len(d), len(z), len(r), len(R))
