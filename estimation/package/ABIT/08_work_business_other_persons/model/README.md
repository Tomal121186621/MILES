# 08_work_business_other_persons

Work business of other persons, from home (location choice, multinomial logit over 1,588 zones). Article table: est_loc_wbhome.

## Model
Location of work-business episodes of persons without a usual workplace (and of non-workers, students, retirees), from home. Distance in pieces (1-2, 2-5, 5-10, 10-20, 20-50, > 50 km; 0-1 km held at 0), intrazonal, Baltimore City, Washington DC, Virginia, DE/PA/WV, outside the home county, ln distance x income < $50k / >= $100k / worker, size term over retail (base), office, other jobs, school pupils.

Likelihood (full choice set, no sampling of alternatives): L_n = sum_k b_k exp(V_z_k) / sum_j exp(V_j), the sum in the numerator over the zones z_k overlapping the survey's destination tract (b_k = overlap area / zone area); one anchor configuration per record. Size term MU_size ln(1 + S_j), S_j = base + sum_c exp(THETA_c) x_jc, THETA in [-30, 15], MU_size in [0, 3]. Unweighted; robust (sandwich) standard errors. Full equations in the docstring of `estimate_work_business_other_persons.py`.

## Files
- `estimate_work_business_other_persons.py`: Biogeme 3.3.5 script (descriptive parameter names).
- `reference_estimates.csv`: article coefficients (rounded) and project output (full precision), robust s.e., p; rows LL0, LL_beta, N, K.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

## Run (Biogeme venv)
    ~/.venvs/biogeme/bin/python estimate_work_business_other_persons.py --evaluate              # LL at the article estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_work_business_other_persons.py                         # estimation, results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py
Options: `--half holdout`, `--at full` (full-precision coefficients), `--outdir DIR`. Data: `../input/data/estimation/biogeme_part*.parquet` (rebuild: `../input/code`, see its README; project Python with torch).

## Special handling
- The 0-1 km distance piece is held at 0 (final stage, rule C: a positive first piece is fixed at 0); it is left out of the utility, so the slope below 1 km is 0.
- The area band set (Baltimore City, DC, Virginia, DE/PA/WV) is kept whole (whole-set band rule).

## Verification (Biogeme log-likelihood at the published coefficients, no estimation)
| | Biogeme | Article / project |
|---|---|---|
| Estimation half, article coefficients (4 decimals) | -6766.7249 | -6766.7 |
| Estimation half, full-precision coefficients | -6766.7248 | -6766.7248 (project) |
| Hold-out half, full-precision coefficients | -7533.0423 (validation half, N 1348; project -7533.04) | |
N 1259, K 19. Evaluation: about 0.8 min, 0.7 GB (eager, `use_jit=False`).

## Estimation feasibility
The likelihood is exact (full choice set, destination mixture) and small in data (one configuration per record, about 1,200-1,500 records), so Biogeme estimation is expected to fit in memory on a normal workstation; the cost is the size of the expression (1,588 utilities plus up to 13 candidate utilities per record), which Biogeme compiles with JAX before the first iteration. The eager log-likelihood evaluation (`--evaluate`) needs under 1 GB. A full Biogeme estimation was not run here: the machine was short of memory (other jobs), and the test estimation of the smaller model 09 was stopped after 56 minutes (45 min CPU, about 3 GB) without finishing compilation. If memory is short, set `calculating_second_derivatives = "never"` (BFGS, robust s.e. from finite differences) or `analytical_hessian_mode = "chunked"` in `../output/biogeme.toml`.
