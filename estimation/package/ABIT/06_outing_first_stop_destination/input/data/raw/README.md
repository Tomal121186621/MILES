# Raw data of model 06

- `wbs_dest_records_estimation.parquet`, `wbs_dest_records_validation.parquet`: first stops of outings from the usual workplace, one row per outing, with chooser attributes (anchor `home_zone_idx` = the workplace zone). Copied from `3_abit/tasha_estimation/work/` (the files the estimation read); built by `estimate_subtour_dest.records(half)`.
- `wbs_dest_cand_estimation.parquet`, `wbs_dest_cand_validation.parquet`: possible zones of each destination tract and their weights.

Shared sources (in `../../../../00_shared_data`): survey episodes (`rts_2017_18/episodes`), survey population (`rts_2017_18/survey_pop`), half split (`rts_2017_18/split`), tract-to-zone overlay (`zones/tract_zone_overlay.parquet`), zone attributes (`zones`), car skims (`skims/abit_base_2016`).
