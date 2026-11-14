# Raw data of model 07

- `loc_records_estimation.parquet`, `loc_records_validation.parquet`: episodes of the anchored activity types (work business, work trips of home workers, school without a record, daycare), one row per episode, with chooser attributes. Copied from `3_abit/tasha_estimation/work/` (the files the estimation read); built by `estimate_locations.records(half)`.
- `loc_cand_estimation.parquet`, `loc_cand_validation.parquet`: possible zones of each destination tract and their weights.

Shared sources (in `../../../../00_shared_data`): survey episodes (`rts_2017_18/episodes`), survey population (`rts_2017_18/survey_pop`), half split (`rts_2017_18/split`), tract-to-zone overlay (`zones/tract_zone_overlay.parquet`), zone attributes (`zones`), car skims (`skims/abit_base_2016`).
