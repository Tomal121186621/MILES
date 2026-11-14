# Reports: validation PDFs, article tables and figures

The code is here; report outputs stay in the workspace (`WORKSPACE/5_reports/...`, `WORKSPACE/data`). Run every script from the
repository root.

Shared figure code: `paperstyle.py` (style), `figures_validation.py`, `tasha_stage3.py`, `composites/` (multi-panel figures).

## Validation PDFs (`validation_pdfs/`)
`common.py`, `matsim_compute.py` and `preamble.tex` are shared helpers; the PDFs and work folders are written to
`WORKSPACE/5_reports/validation_pdfs` (options `--out`, `--work`).
- `build_vae.py`: stage 1 (population) validation PDF
- `build_silo.py`: stage 2 (land use) validation PDF; the five out-of-sample seed runs and the calibration run
- `build_abit.py`: stage 3 (activity model) validation PDF; the 2024 replications (options `--single-form`, `--survey-runs`)
- `build_matsim.py`: stage 4 (traffic assignment) validation PDF; `--runs` the MATSim seed folders (hourly link volumes in
  `WORKSPACE/4_matsim/validation/data`)

Order: vae, silo, abit, matsim (independent). Each script's docstring lists its arguments; the defaults select the final runs.

## Article tables and figures
Run in this order after the validation PDFs (environment variables select the final runs; without them the earlier runs are used):
1. `landuse/validation/final_tables.py` with `SILO_SEEDS=oos_respec_s SILO_OUT_SUFFIX=_respec` (land-use table values);
   `landuse/schools/summarize_seeds.py` with the same variables (school summaries).
2. `activity/validation/validate_mode_choice.py tables` with `MC_VARIANTS=respec MC_OUT_SUFFIX=_respec`;
   `activity/validation/validate_schedules.py survey --sets respec --tag _respec` (survey-household checks).
3. `reports/composites/abit_tasha_data.py` with `ABIT_SETTINGS=verification_respec,validation_respec,chain_respec`, then
   `reports/composites/fig_abit_tasha.py validation verification` with `ABIT_SUFFIX=_respec` (TASHA-form figures).
4. `reports/article/s3_tables.py` with `ABIT_SUFFIX=_respec` (activity frequency tables);
   `reports/article/make_stage_validation.py 2 3` with `ARTICLE_RUNS=respec` (stage figures).
5. `reports/validation_tracts/silo_extract.py`, `abit_extract.py`, `tract_validation.py` with `TRACT_CACHE`, `TRACT_OUT`,
   `SILO_SEEDS=oos_respec_s`, `SILO_BASE=microData_v5respec`, `ABIT_RUN_DIR=<the replication folder>`, `ABIT_REP_PREFIX=fin24_s`
   (small-area and destination tests).
6. Network tables and figures: `validation_pdfs/matsim_compute.py` outputs, then `assignment/validation/gap_routes.py`,
   `gap_triplength.py`, `gap_tables.py` (with and without `--figure`).
7. `reports/article/build.sh`: compile the article and the supplementary material in `WORKSPACE/5_reports/article`.
