#!/usr/bin/env python3
"""Structural vacancy by SILO region (2026-11-17): the vacancy rate of each region in the 2016 base stock (microData_v8 dd_2016,
dwelling vacant = hhID <= 0), all dwelling types together (within a region the base rates differ little by type).
Output input/structural_vacancy_2016.csv (region, rate, dwellings, vacant), read by the engine through structural.vacancy.file."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, pandas as pd
S = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
z = pd.read_csv(f"{S}/input/zoneSystem.csv").set_index("ZoneId")
d = pd.read_csv(f"{S}/run/base/microData_v8/dd_2016.csv", usecols=["zone", "hhID"])
d["region"] = d.zone.map(z.Region); d["vac"] = d.hhID <= 0
t = d.groupby("region").agg(dwellings=("vac", "size"), vacant=("vac", "sum")).reset_index()
t["rate"] = (t.vacant / t.dwellings).round(5)
t[["region", "rate", "dwellings", "vacant"]].to_csv(f"{S}/input/structural_vacancy_2016.csv", index=False)
print(t.describe().loc[["min", "50%", "max"], "rate"].to_dict(), len(t), "regions")
