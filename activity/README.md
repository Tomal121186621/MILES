# Stage 3: MAST activity-based model (Maryland Activity Scheduling and Travel model, built on the ABIT code base)

Engine changes and build notes: `engine/README.md`. Coefficients of the final models: `parameters/` (built by `build_parameters.py`).
Two files of `parameters/tasha/` were re-estimated after that build and replace its output: `tasha_transit_legs.csv` (leg modes of
transit tours, 35 terms, estimated with the model's own car-free rule in the car-driver availability; the fewer-cars-than-drivers term
is kept) and `tasha_subtour.csv` (outings from the workplace; outing-mode logit with 7 terms, without the fewer-cars term).
`dest_choice_mnl.csv` holds the destination models with one attraction variable each (`build_parameters_single_attraction.py`).
Scripts are run from the repository root (for example `python3 activity/run_activity_model.py ...`); inputs, runs and outputs stay
in the workspace (`<workspace>/3_abit/...`, set in miles.toml). `abit_classpath.txt` lists the engine's jar dependencies; `$HOME`
in it is expanded when it is read.

Order:
1. `build_parameters.py`: build `parameters/` from the estimation results (helpers in `lib/coef_tools.py`). Paths in
   `parameters/run_params.csv` use the placeholders `{PARAMETERS}` (the coefficient folder of a run) and `{WORKSPACE}`;
   `write_properties.py` fills them in.
2. `run_replications.py snapshot | run --jobs 2 | persons | choose`: freeze coefficients and classes, run 10 replications (MAST seeds
   1-10, 10 % of households) on the SILO seed 1 population after the schools step, collect the persons table, choose the replication
   for MATSim (rule of `choose_replication.py`; replication 8)
   - `lib/replications.py`: run helper used by `run_replications.py`; `write_properties.py`: writes the MAST properties file;
     `run_activity_model.py`: a single run
3. `validation/validate_survey.py` (with `distributions/build_distributions.py`, `survey/survey_runs.py`, `lib/rts_common.py`,
   `survey/survey_population.py`, `survey/run_survey_households.py`): TASHA-style validation against the 2017/18 survey

Other folders:
- `checks/`: checks of the re-specified models (mode-share decomposition, joint tours, engine utilities, person frequencies, survey
  mode shares), the smoke test and the education check
- `validation/`: mode shares and report of the 2024 runs (`mode_shares_2024.py`, `report_2024.py`), survey, schedule and
  mode-choice validation
- `lib/`: shared code: `activity_metrics.py`, `build_targets.py`, `education_targets.py` (targets and metrics of the validation),
  `representative_day.py` (representative-day picker imported by `pipeline/activities_to_matsim.py`), and the estimation and
  reporting libraries `mode_choice/`, `destination_choice/`, `tasha_estimation/` and `reporting_2024/`
