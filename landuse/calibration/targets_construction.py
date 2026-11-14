#!/usr/bin/env python3
"""Observed construction target for SILO's construction model: housing units permitted by county and year (Census Building Permits
Survey, county annual files co<year>a.txt; two header rows; units by structure size 1, 2, 3-4, 5+), mapped to SILO dwelling types
(SFD/SFA = 1-unit, MF234 = 2 to 4 units, MF5plus = 5+ units; MH not permitted through BPS). Maryland, 2016-2024.
Output: data/silo_target_permits_by_county_year.csv (county, year, units_1, units_2_4, units_5plus, units_total)."""
import pandas as pd, numpy as np
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; rows = []
for y in range(2016, 2025):
    d = pd.read_csv(f"{V}/data/raw/bps/co{y}a.txt", skiprows=2, header=None, dtype=str, encoding="latin-1")
    d = d[d[1].str.strip() == "24"]
    for r in d.itertuples(index=False):
        cty = 24000 + int(r[2]); u1, u2, u34, u5 = (float(r[i]) for i in (7, 10, 13, 16))
        rows.append(dict(county=cty, year=y, units_1=u1, units_2_4=u2 + u34, units_5plus=u5, units_total=u1 + u2 + u34 + u5))
T = pd.DataFrame(rows); T.to_csv(f"{V}/data/silo_target_permits_by_county_year.csv", index=False)
print(T.groupby("year").units_total.sum().astype(int).to_string()); print("six-county 2016-2024 mean per year:", int(T[T.county.isin([24003, 24005, 24013, 24025, 24027, 24510])].groupby("year").units_total.sum().mean()))
