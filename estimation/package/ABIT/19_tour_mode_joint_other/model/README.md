# 19_tour_mode_joint_other: tour mode choice, joint recreation and other tours

Article table `est_mc_joint.tex` (tab:est_mc_other_joint). Joint household recreation and other tours: one observation per joint household group (m11_joint_group.groups). Nested logit as the individual other model (auto nest {car driver, car passenger}, transit nest {bus, train}, mu >= 1).  Alternatives chosen by fewer than 20 groups keep only their constant and level-of-service terms.

One observation per joint household group (as model 18). Nested logit as model 17 (mu >= 1, bounds [1, 10]). MU_auto_nest sits on its lower bound 1 (active bound): Biogeme does not count it, so K = 25 of 26 parameters, as in the article.
Reference mode car driver (no constant). Licence normalised to 0 on walk (car driver needs a licence): walk has no licence term. Availability: columns av_<mode> (car driver also blocked when the household's cars are used by overlapping car-driver tours of other members: m10_car_availability.py). No fixed parameters. Robust (sandwich) standard errors.

Files
- `estimate_tour_mode_joint_other.py`: Biogeme 3.3.5 script; parameter names descriptive (project names in `reference_estimates.csv`, column project_name).
- `reference_estimates.csv`: coefficients and robust s.e. of the project output (full precision), the article's rounded values, p (nest parameters: against 1), and rows LL0, LL_beta, N, K, LL_holdout.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

Run (from this folder)
- `~/.venvs/biogeme/bin/python estimate_tour_mode_joint_other.py --evaluate [--half holdout] [--at full]`: LL at the article (or full-precision) estimates; writes nothing.
- `~/.venvs/biogeme/bin/python estimate_tour_mode_joint_other.py`: estimation, output in `../output` (or `--outdir DIR`).
- `~/.venvs/biogeme/bin/python compare_with_reference.py`

Verification (Biogeme, 2026-11-13)

| | article | Biogeme at article estimates | Biogeme at full-precision estimates |
|---|---|---|---|
| LL estimation half (N 1296, K 25) | -450.3 | -450.2606 | -450.2605 |
| LL hold-out half | -459.1 | -459.094 | -459.0902 |

Biogeme estimation run on 2026-11-13 (output deleted): LL -450.2605, coefficients equal to the reference (max |difference / s.e.| < 0.1).
Every published coefficient equals the project output (`m11_joint_coef.csv`, final rows) to 4 decimals, with the same robust s.e.
