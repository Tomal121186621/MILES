# Data preparation code

Copies of the project scripts. Only file paths were changed (lines marked `# PATH (package)`), so that they read
`../../../00_shared_data` and `../data/raw`. Run from this folder:

    ~/.venvs/biogeme/bin/python build_estimation_data.py

The estimation tables are already in `../data`; running it again rewrites the same files.

| File | Original location | Role |
|---|---|---|
| `build_estimation_data.py` | new | **new for this package**: writes ../data/estimation and ../data/holdout from the copies below, with the same calls (and random draws) as the original run, and checks the log-likelihood at the original estimates |
| `w01_data.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/workplace/w01_data.py` | workplace: data.npz (workers, zones, skim, accessibility) |
| `w03_steps.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/workplace/w03_steps.py` | workplace: term lists |
| `w04_sequence.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/workplace/w04_sequence.py` | workplace: specification sequence; final step |
| `wdc.py` | `Validation_2026/side_experiments/respec_2026-11/step_by_step/workplace/wdc.py` | workplace: estimator; sampling of the 99 zones (seed 20261106) |
