# Raw inputs: workplace choice

Copies: `data.npz` (workers, zone attributes, car skim; written by `w01_data.py`, checked identical when rebuilt from the files
below), `workers_v2.parquet`, `zone_attrs_v2x.parquet` (`Validation_2026/2_silo/jobchoice/work_rts/`), `zones.parquet` (`Validation_2026/2_silo/jobchoice/work/`),
`w04_fit.csv`, `w04_coef.csv`, `w04.log` (original run; final = step 'final').
Not copied: `Validation_2026/2_silo/jobchoice/work_rts/logsum.npy` (work-tour logsums, not in the final model; loaded by `wdc.py` at import).
Shared sources: `00_shared_data/skims`, `accessibility/accessibility_2016.csv`, `rts_2017_18/RTS_raw_flat_data.csv` (licence), `zone_system`.
