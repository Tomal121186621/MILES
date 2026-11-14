# 15_tour_mode_school: tour mode choice, school tours

Article table `est_mc_school.tex` (tab:est_mc_school). Multinomial logit.  Level of service: round-trip km on every non-reference mode (no time).  Bus and train share the person and household coefficients (_TRANSIT); a shared term enters a mode only where the variable varies among the tours with that mode available (m09_school.loglike rule).

Multinomial logit; round-trip km on every non-reference mode, no travel time; bus and train share the person and household coefficients (B_*_TRANSIT).
Reference mode car driver (no constant). Licence normalised to 0 on walk (car driver needs a licence): walk has no licence term. Availability: columns av_<mode> (car driver also blocked when the household's cars are used by overlapping car-driver tours of other members: m10_car_availability.py). No fixed parameters. Robust (sandwich) standard errors.

Files
- `estimate_tour_mode_school.py`: Biogeme 3.3.5 script; parameter names descriptive (project names in `reference_estimates.csv`, column project_name).
- `reference_estimates.csv`: coefficients and robust s.e. of the project output (full precision), the article's rounded values, p (nest parameters: against 1), and rows LL0, LL_beta, N, K, LL_holdout.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

Run (from this folder)
- `~/.venvs/biogeme/bin/python estimate_tour_mode_school.py --evaluate [--half holdout] [--at full]`: LL at the article (or full-precision) estimates; writes nothing.
- `~/.venvs/biogeme/bin/python estimate_tour_mode_school.py`: estimation, output in `../output` (or `--outdir DIR`).
- `~/.venvs/biogeme/bin/python compare_with_reference.py`

Verification (Biogeme, 2026-11-13)

| | article | Biogeme at article estimates | Biogeme at full-precision estimates |
|---|---|---|---|
| LL estimation half (N 2651, K 34) | -972.5 | -972.5151 | -972.5149 |
| LL hold-out half | -1096.5 | -1096.5464 | -1096.5236 |

Biogeme estimation run on 2026-11-13 (output deleted): LL -972.5149, coefficients equal to the reference (max |difference / s.e.| < 0.1).
Every published coefficient equals the project output (`m09_coef.csv`, final rows) to 4 decimals, with the same robust s.e.
