# Validation PDFs
Run from `Validation_2026/5_reports/validation_pdfs` (common.py, matsim_compute.py, preamble.tex are shared helpers; ../paperstyle.py, ../composites/*.py draw the figures).
- build_vae.py: stage 1 (population) validation PDF
- build_silo.py: stage 2 (SILO) validation PDF; scenarios oos_respec_s1..5, calibration calib_respecF_r4
- build_abit.py: stage 3 (ABIT) validation PDF; runs 3_abit/final_2024/run_respec (use --single-form, --survey-runs)
- build_matsim.py: stage 4 (MATSim) validation PDF; --runs pipeline/runs_respec/matsim/2024_s1..s5 (link hours in 4_matsim/validation/data/link_hours_respec)
Order: vae, silo, abit, matsim (independent). Check each script's docstring for the arguments.
- ../figures_validation.py, tasha_stage3.py, composites/: shared figure code

## Article tables and figures (switches select the final runs; defaults reproduce the earlier runs)
Run in this order after the validation PDFs:
1. `2_silo/validation/final_tables.py` with `SILO_SEEDS=oos_respec_s SILO_OUT_SUFFIX=_respec` (land-use table values);
   `2_silo/schoolchoice/sc_14_seed_summary.py` with the same variables (school summaries).
2. `3_abit/mode_choice/mc_validation.py tables` with `MC_VARIANTS=respec MC_OUT_SUFFIX=_respec`; `3_abit/sched_validation.py survey --sets respec --tag _respec` (survey-household checks).
3. `5_reports/composites/abit_tasha_data.py` with `ABIT_SETTINGS=verification_respec,validation_respec,chain_respec`, then `fig_abit_tasha.py validation verification` with `ABIT_SUFFIX=_respec` (TASHA-form figures).
4. `5_reports/article/s3_tables.py` with `ABIT_SUFFIX=_respec` (activity frequency tables); `5_reports/article/make_stage_validation.py 2 3` with `ARTICLE_RUNS=respec` (stage figures).
5. `5_reports/validation_tracts/silo_extract.py`, `abit_extract.py`, `tract_validation.py` with `TRACT_CACHE`, `TRACT_OUT`, `SILO_SEEDS=oos_respec_s`, `SILO_BASE=microData_v5respec`, `ABIT_RUN_DIR=.../run_respec`, `ABIT_REP_PREFIX=fin24_s` (small-area and destination tests).
6. Network tables and figures: `validation_pdfs/matsim_compute.py` outputs, then `4_matsim/validation/gap_routes.py`, `gap_triplength.py`, `gap_tables.py` (with and without `--figure`).
7. `5_reports/article/build.sh` (or `tectonic -X compile main.tex` in `article/source`).
