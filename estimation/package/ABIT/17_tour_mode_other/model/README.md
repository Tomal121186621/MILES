# 17_tour_mode_other: tour mode choice, other tours

Article table `est_mc_other.tex` (tab:est_mc_other). Nested logit: car driver and car passenger in one nest, bus and train in another, walk and bike alone; Biogeme lognested, nest parameters mu >= 1 (bounds [1, 10]).  Level of service: travel time (min) and cost ($) of the round trip on the motorised modes; round-trip km on walk and bike.

Nested logit: auto nest {car driver, car passenger}, transit nest {bus, train}; walk and bike alone. Biogeme lognested, nest parameters mu >= 1, bounds [1, 10], start 1.2.
Reference mode car driver (no constant). Licence normalised to 0 on walk (car driver needs a licence): walk has no licence term. Availability: columns av_<mode> (car driver also blocked when the household's cars are used by overlapping car-driver tours of other members: m10_car_availability.py). No fixed parameters. Robust (sandwich) standard errors.

Files
- `estimate_tour_mode_other.py`: Biogeme 3.3.5 script; parameter names descriptive (project names in `reference_estimates.csv`, column project_name).
- `reference_estimates.csv`: coefficients and robust s.e. of the project output (full precision), the article's rounded values, p (nest parameters: against 1), and rows LL0, LL_beta, N, K, LL_holdout.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

Run (from this folder)
- `~/.venvs/biogeme/bin/python estimate_tour_mode_other.py --evaluate [--half holdout] [--at full]`: LL at the article (or full-precision) estimates; writes nothing.
- `~/.venvs/biogeme/bin/python estimate_tour_mode_other.py`: estimation, output in `../output` (or `--outdir DIR`).
- `~/.venvs/biogeme/bin/python compare_with_reference.py`

Verification (Biogeme, 2026-11-13)

| | article | Biogeme at article estimates | Biogeme at full-precision estimates |
|---|---|---|---|
| LL estimation half (N 10405, K 57) | -4916.7 | -4916.661 | -4916.651 |
| LL hold-out half | -5049.8 | -5050.0493 | -5049.8045 |

Biogeme estimation run on 2026-11-13 (output deleted): LL -4916.651, coefficients equal to the reference (max |difference / s.e.| < 0.1).
Every published coefficient equals the project output (`m08_coef.csv`, final rows) to 4 decimals, with the same robust s.e.
