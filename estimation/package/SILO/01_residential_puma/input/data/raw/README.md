# Raw inputs: PUMA level

Copies of the original run:

| File | Content |
|---|---|
| `original_estimates.csv` | estimates of both levels (level, param, coef, robust_se, t, label) |
| `original_fit.csv` | N, K, LL0, LL, BIC and the hold-out N and LL of both levels |
| `original_estimates_without_race.csv`, `original_fit_without_race.csv` | the same model without the own-race share (robustness) |
| `original_vif.csv` | variance inflation factors of the explanatory variables (within-choice-set correlation) |
| `original_estimate_correlation_puma.csv` | robust correlation of the PUMA-level estimates |

The build script reads the dwelling-level rows of `original_estimates.csv` for the inclusive values and the PUMA-level rows
and `original_fit.csv` for its check.

Shared sources (`../../../../00_shared_data`): `resloc_work/pums_movers_est.parquet` (movers, estimation and validation halves),
`resloc_work/pums_pool_est.parquet` (dwellings occupied by households that moved in within 12 months: the market of each PUMA),
`resloc_work/geo_puma_zone_all.csv`, `geo_mig_zone_all.csv` (zone -> PUMA / migration PUMA, every zone; from `geo_puma_zone.csv`,
`geo_mig_zone.csv` by `../code/crosswalk.py`), `geo_puma_region.csv` (coverage of the PUMAs: market size), `geo_zone.csv` (PUMA, migration-PUMA and zone
geography), `resloc_work/zone_landuse_2016.csv` (ln dwelling density of the zones), `zone_system/crimeIndex.csv`,
`zone_system/zones.shp` (bordering PUMAs), `skims/` (car and transit times), `synthetic_population_2016/hh_2016.csv`,
`dd_2016.csv` (households by race and zone for the own-race share). The movers and the market come from ACS PUMS 2014-2018
(`00_shared_data/acs_pums_2014_2018_5yr`) through `s03_pums.py`.
