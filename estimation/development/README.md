# Estimation of the re-specified models

RESPEC_PROTOCOL.md: rules (one specification rule per model family, hold-out checks). Run order per family, scripts numbered inside each folder.

The scripts live here; their inputs and results stay in the estimation results folder (`ESTIMATION_RESULTS` in miles.toml), one
subfolder per family under its original name (shown in brackets). Run a script from the repository root, for example
`python3 estimation/development/car_ownership/s01_data.py`; it reads and writes `ESTIMATION_RESULTS/car_ownership`.

- car_ownership (car_ownership): SILO car ownership (s00-s08, tables t*)
- residential_location (residential): SILO residential location. r01-r12 and run_residential_chain.sh: the earlier three-level model
  (dwelling, county, zone); r14-r22: the adopted two-level model (PUMA, then dwelling; ACS PUMS only; own-race share of the PUMA),
  see below; r18_sample_size.py: sampled-alternatives check of r17
- workplace_choice (workplace): workplace destination choice. w01-w05 and wdc.py (estimator); w06-w10: re-specification,
  simplification, candidate terms, cars, race (w10); w11_export_silo.py: engine file of the 25-term model
  (workplace_choice_coefficients_25terms.csv, with the inputs of the Java check); w13_drop_off_g4.py: the adopted 24-term model
  (office share x income 125k+ dropped, LR test); w13_export_silo.py: engine file `WORKSPACE/2_silo/input/workplace_choice_coefficients.csv`
  (= landuse/engine_inputs) and its check; w12_holdout_map.py: hold-out maps of the adopted model
- accessibility (accessibility_new): accessibility and mode-choice logsums
- other_locations (locations), primary_destination (dest_primary), stop_location (dest_stop), primary_destination_pooled (dest_pooled),
  destination_checks (destination): DAYMAP (Daily Activity Model for Agent Plans) destination choice, school and stop locations. SILO school location: l07_school.py
  (previous models), l09_school_data.py (school attributes: enrolment by race, charter, magnet, test scores, dormitory capacity),
  l09_school_ext.py (tests), l10_school.py (final models), l11_export_silo.py (engine files school_location_*.csv and the Java check)
- tour_mode_choice (mode_choice), tour_mode_choice_pooled (mode_pooled): DAYMAP tour mode choice (m01-m11)
- tour_formation (activity): outing, outing mode and return-home models
- collinearity (collinearity): correlation of estimates; c_heatmaps_pdf.py builds collinearity_heatmaps.pdf
- tables (tables_new) and run_logsum_chain.sh: table helpers, logsum chain
- selection: DAYMAP model selection (loc_*, mode_choice/mc_*, make_outputs.py, report_tables.py); results in
  `<workspace>/side_experiments/respec_2026-11/abit`
- reports/dev_tables.py, make_pdf.py, spec_summary.py and estimation_pdf_make_pdf.py: build estimation_tables_silo/abit.pdf,
  model_development.pdf and model_specification_summary.pdf in `<workspace>/side_experiments/respec_2026-11/final_tables`
  (and estimation_pdf)

## Residential location, two-level model (r14-r22)
Code only: no PUMS records and no survey records. Inputs: ACS PUMS 2014-2018 and 2017-2021 5-year files
(`PROJECT_ROOT/inputs/pums_<year>_5yr/`), Census geography (TIGER 2010 tracts and PUMAs, tract-to-PUMA file, tract gazetteer), the SILO
2016 base (`WORKSPACE/2_silo/input`), zone accessibility (`accessibility/accessibility_new.py`; override `RESLOC_ACC`) and
`zone_landuse_2016.csv` (r11_zone_landuse.py). Shared helpers: `landuse/lib/residential` (rc.py paths and PUMS reader, mnl.py, s01, s03,
s04, s06); data preparation in `WORKSPACE/2_silo/resloc/work`, results in `ESTIMATION_RESULTS/residential`.

    python3 landuse/lib/residential/s01_geography.py       # crosswalks -> work/geo_*.csv
    python3 landuse/lib/residential/s03_pums.py            # mover households and dwelling pools from PUMS
    python3 estimation/development/residential_location/r19_market_size.py   # market size of each PUMA (dwelling stock x turnover)
    python3 estimation/development/residential_location/r20_crosswalk.py     # corrected zone-PUMA crosswalk
    python3 estimation/development/residential_location/r20_final.py         # model r20 and its geography engine files
    python3 estimation/development/residential_location/r20_norace.py; r20_sample_size.py; r20_tex_rows.py   # r20 checks and table rows
    python3 estimation/development/residential_location/r22_city_bias.py     # city-vs-suburb check and candidate PUMA terms
    python3 estimation/development/residential_location/r22_final.py         # adopted model r22, hold-out map and tables
    python3 estimation/development/residential_location/r22_robust.py norace # r22 without the own-race share
    python3 estimation/development/residential_location/r22_robust.py ss     # sampled-alternatives check (J30, J60, J100)
    python3 estimation/development/residential_location/r22_export_silo.py   # coefficient engine files and the Java-check inputs
    python3 estimation/development/residential_location/r22_export_silo.py check DIR   # Java utilities in DIR against Python

r14_puma_two_level.py (data and estimator of both levels), r15-r17, r19_final.py and holdout_maps.py are modules imported by the
scripts above. The export scripts write into `ESTIMATION_RESULTS/residential` under the names of the original run; the engine copies
in landuse/engine_inputs have these names:

| Written by | File in ESTIMATION_RESULTS/residential | landuse/engine_inputs |
|---|---|---|
| r22_export_silo.py | resloc_puma_coef_1119g.csv | residential_puma_coefficients.csv |
| r22_export_silo.py | resloc_dwelling_coef_1119g.csv | residential_dwelling_coefficients.csv |
| r22_export_silo.py | resloc_zone_core_1119g.csv | residential_zone_core_city.csv |
| r22_export_silo.py | resloc_puma_core_1119g.csv (check only) | residential_puma_core_share_2016.csv |
| r20_final.py | resloc_puma_zone_1118m.csv | residential_puma_zones.csv |
| r20_final.py | resloc_mig_zone_1118m.csv | residential_migration_puma_zones.csv |
| r20_final.py | resloc_zone_attr_1118m.csv | residential_twolevel_zone_attributes.csv |
| r20_final.py | resloc_puma_adjacency_1118m.csv | residential_puma_adjacency.csv |
| r20_final.py | resloc_puma_turnover_1118m.csv | residential_puma_turnover.csv |
