# Repository layout

Code, coefficients and parameters live in the repository. Data and run outputs live in a **workspace** folder that you
set in `miles.toml`.

```text
MILES/
├── miles_cli.py            the `miles` command
├── miles_env.py            configured locations (repository, workspace, external checkouts)
├── miles.example.toml      configuration template → copy to miles.toml
├── population/              Synthetic population
│   ├── cvae/                generator: vaelib/ library, steps/00–09, run_all.py
│   ├── base_year/           fit_controls, zone_weights, jobs_2016, vacancies, external_workplaces, export_base_year
│   └── validation/          validate_population, validate_by_puma, figures
├── landuse/                 Land use (SILO) and school location
│   ├── engine/              SILO engine changes: silo_changes.patch, src/ (new classes)
│   ├── engine_inputs/       coefficient files and small tables read by the engine
│   ├── inputs/              builders of the engine inputs; assign_base_workplaces
│   ├── coefficients/        write_residential_location, write_car_ownership, write_workplace_choice, write_school_location, write_zone_attributes
│   ├── checks/              check_* : engine utilities against the Biogeme estimates
│   ├── calibration/         calibrate.py, calibrated_parameters.json
│   ├── run/                 write_properties, run_silo.sh, run_seeds, choose_seed
│   ├── schools/             school inventory, school-choice estimation, assign_schools, assign_all_seeds
│   ├── lib/                 residential-location and workplace libraries
│   └── validation/          validate_landuse, aggregate_seeds, final_tables
├── activity/                Activities (MILES-Day)
│   ├── engine/ABIT/         engine source (package abm.models.maryland); abit_changes.patch
│   ├── parameters/          coefficients and survey distributions of the current models
│   ├── build_parameters.py  writes parameters/ from the estimation results
│   ├── write_properties.py, run_activity_model.py, run_replications.py, choose_replication.py
│   ├── distributions/       build_distributions (survey frequency, start, duration, joint tables)
│   ├── survey/              runs on the observed survey households
│   ├── lib/                 mode choice, destination choice, survey helpers, metrics
│   ├── checks/              engine-utility check, smoke test, joint tours, decompositions
│   └── validation/          validate_survey, validate_schedules, validate_mode_choice, report_2024
├── assignment/              Traffic assignment (MATSim)
│   ├── engine/matsim-run/   RunBaltimoreToll; engine/transit-mapping/ (pt2matsim)
│   ├── network/             OpenStreetMap network, speeds and capacities, count matching, tolls
│   ├── transit/             GTFS merge and mapping
│   ├── run_seeds.sh         five seeds of the 2024 assignment
│   └── validation/          counts, screenlines, continuous counters, regional checks, validation map
├── pipeline/                run_chain.py, activities_to_matsim, snap_to_network, skims_from_matsim, transit_skim, accessibility
├── estimation/
│   ├── development/         specification search by model family
│   └── package/             one folder per model: Biogeme script, notebook, instructions
├── reports/                 validation reports and figures
└── docs/                    this website
```

## Where to look for…

| I want to… | Go to |
|---|---|
| Change a land-use coefficient | `landuse/engine_inputs/`, written by `landuse/coefficients/write_*.py` |
| Change an activity-model coefficient | `activity/parameters/` |
| Change the network or a toll | `assignment/network/` |
| Re-estimate a model | `miles estimate <model>` or `estimation/package/<stage>/<model>/` |
| Run the full chain | `miles chain …` (`pipeline/run_chain.py`) |
