#!/usr/bin/env python3
"""Zone table for the rebuilt SILO: the 1,588-zone MSTM system with ONE REGION PER MARYLAND COUNTY (region id = county FIPS);
the other states keep the original MSTM region groupings (ids unchanged).  Output: Validation_2026/2_silo/input/zoneSystem.csv
plus regions.csv (region id, name, state, counties) used by every control and calibration file."""
import pandas as pd, os
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; OUT = f"{ROOT}/Validation_2026/2_silo/input"; os.makedirs(OUT, exist_ok=True)
z = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv")
z["Region_mstm"] = z.Region
z["Region"] = z.apply(lambda r: int(r.COUNTYFIPS) if r.STFIPS == 24 else int(r.Region_mstm), axis=1)
z.to_csv(f"{OUT}/zoneSystem.csv", index=False)
# region table: a county belongs to the region holding most of its zones (needed for the Census controls of the non-Maryland regions)
rows = []
for reg, g in z.groupby("Region"):
    cnt = g.groupby("COUNTYFIPS").size()
    rows.append(dict(region=reg, state=int(g.STFIPS.iloc[0]), name=g.JUR_NAME.iloc[0] if g.STFIPS.iloc[0] == 24 else f"MSTM region {reg}",
                     zones=len(g), counties=";".join(str(c) for c in cnt.index), main_counties=";".join(str(c) for c, n in cnt.items() if n == z[z.COUNTYFIPS == c].shape[0] or n >= 0.5 * z[z.COUNTYFIPS == c].shape[0])))
R = pd.DataFrame(rows); R.to_csv(f"{OUT}/regions.csv", index=False)
print(f"zones {len(z)}, regions {z.Region.nunique()} (Maryland {z[z.STFIPS == 24].Region.nunique()} counties, other states {z[z.STFIPS != 24].Region.nunique()} MSTM regions)")
print(R[R.state == 24][["region", "name", "zones"]].to_string(index=False))
