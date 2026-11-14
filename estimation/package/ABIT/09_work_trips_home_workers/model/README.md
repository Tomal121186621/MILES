# 09 Work trips of at-home workers: location choice

Article table: est_loc_wahb (Location choice: work trips of at-home workers, from home). N 366, K 6.

## Model
Multinomial logit over all 1,588 zones (no sampling of alternatives), from home:

V_j = MU_size ln(1 + office jobs_j + exp(THETA_population) population_j) + B_distance_km d_hj + B_ln_distance ln d_hj + B_intrazonal [j = home zone] + B_outside_home_county [county_j ≠ home county]

d = car distance of the 2016 skim (km), intrazonal 0.5 √area. The survey gives the destination census tract; the likelihood of a record is Σ_k b_k exp(V_zk) / Σ_j exp(V_j) over the zones k overlapping the tract (b_k = overlap area / zone area). One home configuration per record.
Bounds as estimated: THETA in [-30, 15], MU_size in [0, 3]. Unweighted, robust standard errors.

## Run (Biogeme 3.3.5 venv)
```
cd model
~/.venvs/biogeme/bin/python estimate_work_trips_home_workers.py --evaluate --at article   # LL at the article estimates, writes nothing
~/.venvs/biogeme/bin/python estimate_work_trips_home_workers.py                           # estimation -> ../output
~/.venvs/biogeme/bin/python compare_with_reference.py                                     # estimates vs reference_estimates.csv
```
Options: `--half holdout` (hold-out half), `--at full` (full-precision estimates), `--outdir DIR`.
The data in `../input/data` is ready; `../input/code` rebuilds it (see its README).

## Files
- `reference_estimates.csv`: article coefficients and robust s.e. (rounded), the project output at full precision, p-values, and LL(0), LL, N, K.
- `compare_with_reference.py`: compares a run in `../output` with it.

## Verification
| | LL |
|---|---|
| Article LL(β) | -1,634.6 |
| Biogeme, article estimates (estimation half, 366 records) | -1,634.6358 |
| Biogeme, full-precision estimates | -1,634.6358 (project -1,634.6358) |
| Biogeme, hold-out half (427 records) | -1,867.9411 (article -1,867.9) |

Evaluation: 13 s, 0.5 GB (eager, `use_jit=False`).

## Estimation memory
A test estimation on this machine (Biogeme 3.3.5, default settings, JIT) was stopped after 56 minutes (45 min CPU, about 2.8 GB) without having finished compiling the likelihood and its derivatives; no iteration was reached. The machine had almost no free memory at the time (other jobs used about 45 of 48 GB), so the run time on a free machine is unknown. The evaluation at given coefficients (--evaluate, use_jit=False) takes 13 s and 0.5 GB. If the estimation is too slow, try in biogeme.toml calculating_second_derivatives = "finite_differences" or "never" (BHHH), or analytical_hessian_mode = "chunked"; the likelihood itself (1,588 utilities per record) does not change.
