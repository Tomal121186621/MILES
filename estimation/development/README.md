# Estimation of the re-specified models
RESPEC_PROTOCOL.md: rules (one specification rule per model family, hold-out checks). Run order per family, scripts numbered inside each folder.
- step_by_step/car_ownership: SILO car ownership (s00-s08, tables t*)
- step_by_step/residential: SILO dwelling, region, zone choice (r01-r12, run_residential_chain_1110.sh)
- step_by_step/workplace: workplace destination choice (w01-w05)
- step_by_step/accessibility_new: accessibility and mode logsums
- step_by_step/locations, dest_primary, dest_stop, dest_pooled, destination: ABIT destination choice, school and stop locations
- step_by_step/mode_choice, mode_pooled: ABIT tour mode choice (m01-m11)
- step_by_step/activity: outing, mode and return-home models
- step_by_step/collinearity: correlation of estimates; c_heatmaps_pdf.py builds collinearity_heatmaps.pdf
- step_by_step/tables_new, run_logsum_chain.sh: table helpers, logsum chain
- abit/: ABIT model selection (loc_*, mode_choice/mc_*, make_outputs.py, report_tables.py)
- final_tables/dev_tables.py, make_pdf.py, spec_summary.py, estimation_pdf_make_pdf.py: build estimation_tables_silo/abit.pdf, model_development.pdf, model_specification_summary.pdf
