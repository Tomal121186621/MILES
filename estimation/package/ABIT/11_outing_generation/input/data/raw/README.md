# Raw data of model 11

- wbs_<half>.parquet (work episodes of workers with a usual workplace, one row each, with the model variables), wbs_out_<half>.parquet (outings), wbs_w_<half>.parquet (the episodes behind wbs). Copied from `3_abit/tasha_estimation/work` (the files the estimation read).
- If deleted, the code in `../../code` rebuilds them from the shared sources in `00_shared_data`: survey episodes (`rts_2017_18/episodes`), survey population (`rts_2017_18/survey_pop`), RTS files (`rts_2017_18/raw`), zones and skims.
