# Estimation of the re-specified models

RESPEC_PROTOCOL.md: rules (one specification rule per model family, hold-out checks). Run order per family, scripts numbered inside each folder.

The scripts live here; their inputs and results stay in the estimation results folder (`ESTIMATION_RESULTS` in oriole.toml), one
subfolder per family under its original name (shown in brackets). Run a script from the repository root, for example
`python3 estimation/development/car_ownership/s01_data.py`; it reads and writes `ESTIMATION_RESULTS/car_ownership`.

- car_ownership (car_ownership): SILO car ownership (s00-s08, tables t*)
- residential_location (residential): SILO dwelling, county and zone choice (r01-r12, run_residential_chain.sh)
- workplace_choice (workplace): workplace destination choice (w01-w05)
- accessibility (accessibility_new): accessibility and mode-choice logsums
- other_locations (locations), primary_destination (dest_primary), stop_location (dest_stop), primary_destination_pooled (dest_pooled),
  destination_checks (destination): ABIT destination choice, school and stop locations
- tour_mode_choice (mode_choice), tour_mode_choice_pooled (mode_pooled): ABIT tour mode choice (m01-m11)
- tour_formation (activity): outing, outing mode and return-home models
- collinearity (collinearity): correlation of estimates; c_heatmaps_pdf.py builds collinearity_heatmaps.pdf
- tables (tables_new) and run_logsum_chain.sh: table helpers, logsum chain
- selection: ABIT model selection (loc_*, mode_choice/mc_*, make_outputs.py, report_tables.py); results in
  `<workspace>/side_experiments/respec_2026-11/abit`
- reports/dev_tables.py, make_pdf.py, spec_summary.py and estimation_pdf_make_pdf.py: build estimation_tables_silo/abit.pdf,
  model_development.pdf and model_specification_summary.pdf in `<workspace>/side_experiments/respec_2026-11/final_tables`
  (and estimation_pdf)
