#!/usr/bin/env python3
"""County shares of construction by dwelling type (Baltimore 2026, construct.dwelling.region.shares.file): share of each Maryland
county in the housing units permitted in Maryland 2016-2019 (Census Building Permits Survey, data/silo_target_permits_by_county_year.csv;
the calendar years simulated in the 2016-2020 calibration window), by structure type: 1-unit permits for SFD, SFA and MH, 2-4 units for
MF234, 5+ units for MF5plus. The engine's vacancy response sets the Maryland total by type; the shares split it. The out-of-sample
years 2021-2024 keep these 2016-2019 shares. Output: 2_silo/input/construction_county_shares.csv (type, region, share)."""
import pandas as pd
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"
P = pd.read_csv(f"{V}/data/silo_target_permits_by_county_year.csv"); P = P[P.year.between(2016, 2019)].groupby("county")[["units_1", "units_2_4", "units_5plus"]].sum()
rows = []
for t, c in [("SFD", "units_1"), ("SFA", "units_1"), ("MH", "units_1"), ("MF234", "units_2_4"), ("MF5plus", "units_5plus")]:
    s = P[c] / P[c].sum()
    rows += [dict(type=t, region=int(r), share=round(float(v), 6)) for r, v in s.items()]
pd.DataFrame(rows).to_csv(f"{V}/2_silo/input/construction_county_shares.csv", index=False)
print(P.assign(total=P.sum(1)).assign(share=lambda d: (d.total / d.total.sum()).round(4)).to_string())
