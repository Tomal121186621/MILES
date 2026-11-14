#!/usr/bin/env python3
"""MSTM 2016 skims (OMX, matrix mat1, lookup origins/destinations; MDOT-provided, as in ABIT/input/mito_los/skims) -> the csv.gz
files the models read (FROM, TO, VALUE; one row per zone pair, zones in the order of the OMX lookup).  The provided files in
00_shared_data/skims/abit_base_2016 are exactly these dumps (distance rounded to 4 decimals, metres).

    ~/.venvs/biogeme/bin/python convert_mstm_skims.py      reads raw/mstm_skims_2016/{traveltime_auto,distance_auto,bus_tt,rail_tt00}.omx
                                                         writes rebuilt/skims/abit_base_2016/<name>.csv.gz
"""
import os, sys
import numpy as np, pandas as pd, h5py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pkg_paths import RAW, out

for name in ["traveltime_auto", "distance_auto", "bus_tt", "rail_tt00"]:
    with h5py.File(f"{RAW}/mstm_skims_2016/{name}.omx", "r") as f:
        m = f["data/mat1"][:].astype(np.float64); o = f["lookup/origins"][:]; d = f["lookup/destinations"][:]
    n = len(o)
    df = pd.DataFrame({"FROM": np.repeat(o, n).astype(int), "TO": np.tile(d, n).astype(int), "VALUE": np.round(m.ravel(), 4)})
    df.to_csv(out(f"skims/abit_base_2016/{name}.csv.gz"), index=False)
    print(name, df.shape)
