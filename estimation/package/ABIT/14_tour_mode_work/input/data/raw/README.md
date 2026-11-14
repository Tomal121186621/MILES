# Raw data of 14_tour_mode_work

Copied from `3_abit/mode_choice/work/` (the files the estimation read):
- `tours_estimation.parquet`, `tours_validation.parquet`: survey tours of each half with level of service, availability and chosen mode (prep_tours.py).
- `gc_bio_work_s50.parquet`, `gc_hold_work_s50.parquet`: the earlier model data of the segment; `data()` asserts that its rows match them (consistency check only).
- `wesml_est.parquet`, `wesml_hold.parquet`: WESML weights of the work tours (wesml_targets.py).

Shared sources (`../../../../00_shared_data`): survey episodes (`rts_2017_18/episodes`, joint travel groups), parking shares (`mode_choice_inputs/parking_paid_share.csv`), WESML targets (`mode_choice_inputs/wesml`), zones, skims.
