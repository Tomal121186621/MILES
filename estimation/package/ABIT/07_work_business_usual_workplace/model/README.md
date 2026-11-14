# 07_work_business_usual_workplace

Work business of a worker with a usual workplace (location choice, detour form, multinomial logit over 1,588 zones). Article table: est_loc_wbwork.

## Model
Location of work-business episodes of workers with a usual workplace; two anchors, home (a) and the workplace (b); impedance = detour max(0, d(a,j) + d(j,b) - d(a,b)) in pieces (0-1, 1-2, 2-5, 5-10, 10-20, > 20 km), detour of car generalised time, home zone, workplace zone, retail density, land-use mix, outside the counties of both anchors, ln(1 + detour) x no car / fewer cars than drivers / AM / PM / evening, size term over retail (base), office, population, other jobs, school pupils.

Likelihood (full choice set, no sampling of alternatives): L_n = sum_k b_k exp(V_z_k) / sum_j exp(V_j), the sum in the numerator over the zones z_k overlapping the survey's destination tract (b_k = overlap area / zone area); one anchor configuration per record. Size term MU_size ln(1 + S_j), S_j = base + sum_c exp(THETA_c) x_jc, THETA in [-30, 15], MU_size in [0, 3]. Unweighted; robust (sandwich) standard errors. Full equations in the docstring of `estimate_work_business_usual_workplace.py`.

## Files
- `estimate_work_business_usual_workplace.py`: Biogeme 3.3.5 script (descriptive parameter names).
- `reference_estimates.csv`: article coefficients (rounded) and project output (full precision), robust s.e., p; rows LL0, LL_beta, N, K.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

## Run (Biogeme venv)
    ~/.venvs/biogeme/bin/python estimate_work_business_usual_workplace.py --evaluate              # LL at the article estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_work_business_usual_workplace.py                         # estimation, results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py
Options: `--half holdout`, `--at full` (full-precision coefficients), `--outdir DIR`. Data: `../input/data/estimation/biogeme_part*.parquet` (rebuild: `../input/code`, see its README; project Python with torch).

## Special handling
- The detour form was chosen over the distance from the workplace by BIC in block 1 of the model development (l_locations.py).
- Records are loaded with form `stop`: home_idx = home zone, anchor_b = workplace zone.

## Verification (Biogeme log-likelihood at the published coefficients, no estimation)
| | Biogeme | Article / project |
|---|---|---|
| Estimation half, article coefficients (4 decimals) | -8402.1978 | -8402.2 |
| Estimation half, full-precision coefficients | -8402.1967 | -8402.1967 (project) |
| Hold-out half, full-precision coefficients | -8472.7180 (validation half, N 1529; project -8472.72) | |
N 1539, K 22. Evaluation: about 1.8 min, 0.8 GB (eager, `use_jit=False`).

## Estimation feasibility
The likelihood is exact (full choice set, destination mixture) and small in data (one configuration per record, about 1,200-1,500 records), so Biogeme estimation is expected to fit in memory on a normal workstation; the cost is the size of the expression (1,588 utilities plus up to 13 candidate utilities per record), which Biogeme compiles with JAX before the first iteration. The eager log-likelihood evaluation (`--evaluate`) needs under 1 GB. A full Biogeme estimation was not run here: the machine was short of memory (other jobs), and the test estimation of the smaller model 09 was stopped after 56 minutes (45 min CPU, about 3 GB) without finishing compilation. If memory is short, set `calculating_second_derivatives = "never"` (BFGS, robust s.e. from finite differences) or `analytical_hessian_mode = "chunked"` in `../output/biogeme.toml`.
