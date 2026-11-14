# Raw data of model 20

- tlegs_<half>.parquet (legs of the observed transit tours, linked around change-mode activities), tours_<half>.parquet (tours of the tour mode choice, input of legs()). Copied from `3_abit/mode_choice/work (tours) and 3_abit/tasha_estimation/work (tlegs)` (the files the estimation read).
- If deleted, the code in `../../code` rebuilds them from the shared sources in `00_shared_data`: survey episodes (`rts_2017_18/episodes`), survey population (`rts_2017_18/survey_pop`), RTS files (`rts_2017_18/raw`), zones and skims.
