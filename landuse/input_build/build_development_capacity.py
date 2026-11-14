#!/usr/bin/env python3
"""Development capacity by zone (Baltimore 2026). Starts from the MSTM development file (input/development_mstm.csv: allowed
dwelling types and developable acres DevLandUse by zone) and checks, for every Maryland county, the developable acres against
the land the permitted units need (Building Permits Survey 2016-2024 by structure type, extrapolated to 2026 at the 2016-2024
mean; acres per dwelling of the engine: 1 unit 0.25 (SFD), 2-4 units 0.07, 5+ units 0.03). Counties with less than 1.5 times the
needed land get their zones' developable acres scaled up proportionally to 1.5 times the need (infill and redevelopment, which
the vacant-land inventory does not contain). In 2026 this concerns only Baltimore City (313 acres against 777 needed); every
other county has at least 2.4 times its need. Output: input/development_2026.csv, data/silo_development_capacity_check.csv."""
import pandas as pd
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; S = f"{V}/2_silo"
dev = pd.read_csv(f"{S}/input/development_mstm.csv"); z = pd.read_csv(f"{S}/input/zoneSystem.csv").set_index("ZoneId")
dev["county"] = dev.Zone.map(z.COUNTYFIPS)
P = pd.read_csv(f"{V}/data/silo_target_permits_by_county_year.csv"); g = P.groupby("county")[["units_1", "units_2_4", "units_5plus", "units_total"]].sum()
need = (g.units_1 * 0.25 + g.units_2_4 * 0.07 + g.units_5plus * 0.03) * 11 / P.year.nunique()   # 2016-2026
cap = dev.groupby("county").DevLandUse.sum()
T = pd.DataFrame({"permits_2016_2024": g.units_total, "acres_needed_2016_2026": need, "developable_acres": cap.reindex(g.index)})
T["ratio"] = T.developable_acres / T.acres_needed_2016_2026; T["factor"] = (1.5 / T.ratio).clip(lower=1.0)
for c, f in T.factor.items():
    if f > 1: dev.loc[dev.county == c, "DevLandUse"] *= f
T["developable_acres_new"] = dev.groupby("county").DevLandUse.sum().reindex(T.index)
dev.drop(columns="county").to_csv(f"{S}/input/development_2026.csv", index=False)
T.round(3).to_csv(f"{V}/data/silo_development_capacity_check.csv"); print(T.round(2).to_string())
