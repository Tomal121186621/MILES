# Raw inputs: dwelling level

Copies of the original run: `original_estimates.csv` (estimates of both levels: level, param, coef, robust_se, t, label),
`original_fit.csv` (N, K, LL0, LL, BIC, hold-out N and LL of both levels), `original_vif.csv` (variance inflation factors),
`original_estimate_correlation_dwelling.csv` (robust correlation of the dwelling-level estimates). The build script reads the
dwelling rows for its check.

Shared sources (`../../../../00_shared_data/resloc_work`): `pums_movers_est.parquet` (movers, estimation and validation halves),
`pums_pool_est.parquet` (dwellings occupied by households that moved in within 12 months: the sampled alternatives). They come
from ACS PUMS 2014-2018 (`00_shared_data/acs_pums_2014_2018_5yr`) through `s03_pums.py`.
