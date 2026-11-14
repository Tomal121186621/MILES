# Raw inputs: county level

In this folder (copies): `r05_fit.csv`, `r05_coef.csv`, `r05.log` (original county run; final = step Ja), `r06_*.csv` and
`r08_*.csv` (lower-level estimates used for the inclusive values), `r07.log`.

Not copied (large; read from the original location by `build_estimation_data.py` and `r05_region_sequence.py`):

| File | Location | Size | Content |
|---|---|---|---|
| `county_data_est.pkl` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/residential/` | 279 MB | county data of the estimation movers with the final inclusive values (r07_county_iv.py) |
| `county_data_val.pkl` | same | 70 MB | same, validation movers |
| `region_data_est_final.pkl`, `region_data_val_final.pkl` | `Validation_2026/2_silo/resloc/work/` | 266 MB, 67 MB | inputs of r07_county_iv.py (origin variables) |

If you rebuild the inclusive values with `r07_county_iv.py`, it writes `county_data_*.pkl` here and the build script uses them.
Shared sources: `../../../../00_shared_data` (resloc_work, county_attributes, zone_system, skims, accessibility).
