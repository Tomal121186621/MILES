# Repository layout

```text
ORIOLE/
├── population/            Synthetic population (CVAE)
│   ├── cvae/              generator: steps/ 00–09, vaelib/ library, run_all.py, requirements.txt
│   └── post/              rebalancing, zone placement, jobs, vacancies, workplaces, export for SILO
├── landuse/               Land use (SILO) and school location
│   ├── input_build/       observed-data inputs: zones, controls, jobs, permits, labour participation
│   ├── input/             coefficient files and small input tables read by the engine
│   ├── engine_check/      write the engine files of the estimated models; unit checks against Biogeme
│   ├── java/              SILO engine changes: patch + new classes
│   ├── run/               properties files, run_silo.sh, run_oos.py
│   ├── calibration/       calibrate.py, calibrated parameters, calibration log
│   ├── schoolchoice/      school location estimation and the yearly assignment step
│   ├── schools/           school inventory
│   └── validation/        land-use validation tables
├── activity/              Activities (ORIOLE-Day)
│   ├── java/ABIT/         engine source (package abm.models.maryland)
│   ├── coef_respec/       coefficients and survey distributions of the current models
│   ├── final_2024/        2024 runs: ten replications, seed choice, reports
│   ├── mode_choice/       tour mode validation
│   └── *.py               run helpers, distribution builder, survey-population runs, validation
├── assignment/            Traffic assignment (MATSim)
│   ├── java/matsim-run/   runner de.umd.matsim.RunBaltimoreToll
│   ├── java/transit_mapping/  pt2matsim shape-guided mapping
│   ├── network/           OpenStreetMap network build, speeds and capacities, count matching, tolls
│   ├── transit/           GTFS merge and mapping
│   └── validation/        counts, screenlines, continuous counters, regional checks
├── pipeline/              run_chain.py orchestration, plans converter, skim tools
├── estimation/
│   ├── development/       specification search of every model (Biogeme, PyTorch)
│   └── package/           one folder per model: Biogeme script, notebook, instructions
├── reports/               validation reports and figures
├── docs/                  this website (MkDocs Material)
└── mkdocs.yml
```

## Where to look for…

| I want to… | Go to |
|---|---|
| Change a land-use coefficient | `landuse/input/*_respec.csv`, written by `landuse/engine_check/e01`–`e05` |
| Change an activity-model coefficient | `activity/coef_respec/` |
| Change the network or a toll | `assignment/network/` |
| Re-estimate a model | `estimation/package/<stage>/<model>/` |
| Run the full chain | `pipeline/run_chain.py` |
