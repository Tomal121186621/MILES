# Raw data of 03_stop_recreation

- `dc_rec_<half>_taz.parquet`: one row per primary destination or stop of the discretionary tours (all four purposes), chooser attributes, modal anchors. Copied from `3_abit/tasha_estimation/work/` (the files the estimation read).
- `dc_cand_<half>_taz.parquet`: possible zones of each destination (survey traffic zone, or tract split by jobs) and weights.
- `dc_cfg_<half>_taz.parquet`: anchor configurations (previous location a, next anchor b) and weights.

Built by `../code/prep_dc_taz.py` from the shared sources in `../../../../00_shared_data`: survey (`rts_2017_18`), traffic-zone crosswalks (`taz_crosswalks`), zones, skims.
