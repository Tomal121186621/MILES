# Raw inputs: workplace choice

Copies: `data.npz` (workers, zone attributes, car skim; written by `w01_data.py`, checked identical when rebuilt from the files
below), `workers_v2.parquet`, `zone_attrs_v2x.parquet` (`Validation_2026/2_silo/jobchoice/work_rts/`), `zones.parquet` (`Validation_2026/2_silo/jobchoice/work/`),
`w04_fit.csv`, `w04_coef.csv`, `w04.log` (original run; final = step 'final').
Not copied: `Validation_2026/2_silo/jobchoice/work_rts/logsum.npy` (work-tour logsums, not in the final model; loaded by `wdc.py` at import).
Shared sources: `00_shared_data/skims`, `accessibility/accessibility_2016.csv`, `rts_2017_18/RTS_raw_flat_data.csv` (licence), `zone_system`.

- Files shipped (2026-11-17): logsum.npy (121 MB), copied from Validation_2026/2_silo/jobchoice/work_rts/.

Final model (24 parameters): `final_model_estimates.csv` (param, coef, se and p of the original estimator, robust_se_g_fixed and
p_g_fixed: the sandwich over the estimated parameters only) and `final_model_fit.csv` (K, LL, BIC, hold-out LL, terms). The steps
of its specification search: `specification_steps_size_area_time.csv` (former model, equal size weights, without the area
dummies, without the time interactions that are not significant, without the job-mix x person terms),
`specification_steps_candidates.csv` (transit time without a car, paid parking, own-race share of the workers),
`specification_steps_cars.csv` (time x household without a car, time x fewer cars than workers),
`specification_steps_drop_office_125k.csv` (the 25-term model with office share x income 125k+, and the final model without it;
LR test, BIC, hold-out LL). `w04_*.csv`: the former model.
