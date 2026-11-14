# 18_tour_mode_joint_shopping: tour mode choice, joint shopping tours

Article table `est_mc_joint.tex` (tab:est_mc_shopping_joint). Joint household shopping tours: one observation per joint household group (the representative member's tour; car driver chosen when a member drove, available when a member has it available; m11_joint_group.groups). Multinomial logit; train is not available (no group chose it).  Alternatives chosen by fewer than 20 groups keep only their constant and level-of-service terms.  Time and cost as the individual shopping model.

One observation per joint household group (representative: the oldest member with car driver available, else the oldest); car driver chosen if a member drove and available if a member has it available. Train not available (no estimation group chose it); 1 validation group that chose train is left out of the hold-out. Modes chosen by fewer than 20 groups keep only constant and level-of-service terms.
Reference mode car driver (no constant). Licence normalised to 0 on walk (car driver needs a licence): walk has no licence term. Availability: columns av_<mode> (car driver also blocked when the household's cars are used by overlapping car-driver tours of other members: m10_car_availability.py). No fixed parameters. Robust (sandwich) standard errors.

Files
- `estimate_tour_mode_joint_shopping.py`: Biogeme 3.3.5 script; parameter names descriptive (project names in `reference_estimates.csv`, column project_name).
- `reference_estimates.csv`: coefficients and robust s.e. of the project output (full precision), the article's rounded values, p (nest parameters: against 1), and rows LL0, LL_beta, N, K, LL_holdout.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

Run (from this folder)
- `~/.venvs/biogeme/bin/python estimate_tour_mode_joint_shopping.py --evaluate [--half holdout] [--at full]`: LL at the article (or full-precision) estimates; writes nothing.
- `~/.venvs/biogeme/bin/python estimate_tour_mode_joint_shopping.py`: estimation, output in `../output` (or `--outdir DIR`).
- `~/.venvs/biogeme/bin/python compare_with_reference.py`

Verification (Biogeme, 2026-11-13)

| | article | Biogeme at article estimates | Biogeme at full-precision estimates |
|---|---|---|---|
| LL estimation half (N 452, K 15) | -112.8 | -112.8374 | -112.8374 |
| LL hold-out half | -94.0 | -94.0325 | -94.0292 |

Not estimated here (same code path as models 14, 15, 17, 19, which reproduced the article).
Every published coefficient equals the project output (`m11_joint_coef.csv`, final rows) to 4 decimals, with the same robust s.e.
