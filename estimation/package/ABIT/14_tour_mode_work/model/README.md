# 14_tour_mode_work: tour mode choice, work tours

Article table `est_mc_work.tex` (tab:est_mc_work). Multinomial logit (the nested forms did not pass the selection).  Level of service: generalised cost of the round trip gc_<mode> = time + 60 x cost / VOT (VOT = 0.5 x household income / 2,080 h, income floored at $5k) on car driver, car passenger, bus and train; round-trip km on every non-reference mode.

Weighted: WESML choice-based sample weights (column wesml) to the ACS 2015-19 commute-mode shares by home-county stratum; weighted pseudo-log-likelihood (Biogeme 'weight' formula); the LL is the weighted one. Multinomial logit; generalised cost on car driver, car passenger, bus and train; round-trip km on every non-reference mode.
Reference mode car driver (no constant). Licence normalised to 0 on walk (car driver needs a licence): walk has no licence term. Availability: columns av_<mode> (car driver also blocked when the household's cars are used by overlapping car-driver tours of other members: m10_car_availability.py). No fixed parameters. Robust (sandwich) standard errors.

Files
- `estimate_tour_mode_work.py`: Biogeme 3.3.5 script; parameter names descriptive (project names in `reference_estimates.csv`, column project_name).
- `reference_estimates.csv`: coefficients and robust s.e. of the project output (full precision), the article's rounded values, p (nest parameters: against 1), and rows LL0, LL_beta, N, K, LL_holdout.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

Run (from this folder)
- `~/.venvs/biogeme/bin/python estimate_tour_mode_work.py --evaluate [--half holdout] [--at full]`: LL at the article (or full-precision) estimates; writes nothing.
- `~/.venvs/biogeme/bin/python estimate_tour_mode_work.py`: estimation, output in `../output` (or `--outdir DIR`).
- `~/.venvs/biogeme/bin/python compare_with_reference.py`

Verification (Biogeme, 2026-11-13)

| | article | Biogeme at article estimates | Biogeme at full-precision estimates |
|---|---|---|---|
| LL estimation half (N 9126, K 51) | -4313.1 | -4313.0986 | -4313.0969 |
| LL hold-out half | -4284.0 | -4283.9559 | -4283.9503 |

Biogeme estimation run on 2026-11-13 (output deleted): LL -4313.097, coefficients equal to the reference (max |difference / s.e.| < 0.1).
Every published coefficient equals the project output (`m08_coef.csv`, final rows) to 4 decimals, with the same robust s.e.
