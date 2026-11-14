# Raw data of model 01

- `dc_rec_<half>_taz.parquet`: primary destinations of discretionary home-based tours and stops (all four purposes, both kinds), one row per record, with chooser attributes.
- `dc_cand_<half>_taz.parquet`: possible zones of each destination (survey traffic zone spread over model zones by jobs) and weights b.
- `dc_cfg_<half>_taz.parquet`: possible home zones of each record (spread by housing units) and weights w.

Copied from `3_abit/tasha_estimation/work/` (the files the estimation read, built 2026-11-04 by prep_dc_taz.py); `../code/prep_dc_taz.py` rebuilds them identically from `00_shared_data`.

Shared sources (`../../../../00_shared_data`): `rts_2017_18` (survey, half split, survey population), `taz_crosswalks`, `zones`, `skims/abit_base_2016`.
