# 16_tour_mode_shopping: tour mode choice, shopping tours

Article table `est_mc_shopping.tex` (tab:est_mc_shopping). Multinomial logit.  Level of service: travel time (min) and cost ($) of the round trip on car driver, car passenger, bus and train; round-trip km on walk and bike.  Household size is not on car passenger (dropped by BIC, rule H of m08).

Multinomial logit; travel time and cost on the motorised modes, km on walk and bike; household size not on car passenger (dropped by BIC).
Reference mode car driver (no constant). Licence normalised to 0 on walk (car driver needs a licence): walk has no licence term. Availability: columns av_<mode> (car driver also blocked when the household's cars are used by overlapping car-driver tours of other members: m10_car_availability.py). No fixed parameters. Robust (sandwich) standard errors.

Files
- `estimate_tour_mode_shopping.py`: Biogeme 3.3.5 script; parameter names descriptive (project names in `reference_estimates.csv`, column project_name).
- `reference_estimates.csv`: coefficients and robust s.e. of the project output (full precision), the article's rounded values, p (nest parameters: against 1), and rows LL0, LL_beta, N, K, LL_holdout.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

Run (from this folder)
- `~/.venvs/biogeme/bin/python estimate_tour_mode_shopping.py --evaluate [--half holdout] [--at full]`: LL at the article (or full-precision) estimates; writes nothing.
- `~/.venvs/biogeme/bin/python estimate_tour_mode_shopping.py`: estimation, output in `../output` (or `--outdir DIR`).
- `~/.venvs/biogeme/bin/python compare_with_reference.py`

Verification (Biogeme, 2026-11-13)

| | article | Biogeme at article estimates | Biogeme at full-precision estimates |
|---|---|---|---|
| LL estimation half (N 3206, K 44) | -1150.2 | -1150.249 | -1150.2475 |
| LL hold-out half | -1107.0 | -1106.9304 | -1106.9841 |

Not estimated here (same code path as models 14, 15, 17, 19, which reproduced the article).
Every published coefficient equals the project output (`m08_coef.csv`, final rows) to 4 decimals, with the same robust s.e.
