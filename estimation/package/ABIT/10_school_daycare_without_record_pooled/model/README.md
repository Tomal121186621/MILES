# 10_school_daycare_without_record_pooled

School episodes of persons without a school record and daycare of children under 5, pooled with purpose scale (location choice, multinomial logit over 1,588 zones). Article table: est_loc_edu.

## Model
Two purposes from home in one likelihood: non-student school (567 records, scale 1) and daycare (279 records, free scale). Shared: ln distance, car generalised time, ln(zone area), land-use mix, outside the home county, outside the home state. Each purpose has its own coefficient of ln(1 + school enrolment) (B_ln_school_enrolment_nonstudent_school, B_ln_school_enrolment_daycare).

Likelihood (full choice set, no sampling of alternatives): L_n = sum_k b_k exp(V_z_k) / sum_j exp(V_j), the sum in the numerator over the zones z_k overlapping the survey's destination tract (b_k = overlap area / zone area); one anchor configuration per record. Zone area in km², at least 0.05 km²; no bounds except the scale. Unweighted; robust (sandwich) standard errors. Full equations in the docstring of `estimate_school_daycare_without_record_pooled.py`.

## Files
- `estimate_school_daycare_without_record_pooled.py`: Biogeme 3.3.5 script (descriptive parameter names).
- `reference_estimates.csv`: article coefficients (rounded) and project output (full precision), robust s.e., p; rows LL0, LL_beta, N, K.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

## Run (Biogeme venv)
    ~/.venvs/biogeme/bin/python estimate_school_daycare_without_record_pooled.py --evaluate              # LL at the article estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_school_daycare_without_record_pooled.py                         # estimation, results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py
Options: `--half holdout`, `--at full` (full-precision coefficients), `--outdir DIR`. Data: `../input/data/estimation/biogeme_part*.parquet` (rebuild: `../input/code`, see its README; project Python with torch).

## Special handling
- U_pj = mu_p V_pj with mu = 1 for non-student school and SCALE_daycare estimated (lower bound 0.01).
- All coefficients, including those of ln(1 + school enrolment), are in V units and multiplied by the purpose scale (daycare utility: SCALE_daycare x V).
- Interactions the pooling held at 0 (ln distance x cars, age, children, worker, time of day) are left out; the purpose of a row is the column `purpose_id` (0 non-student school, 1 daycare).

## Verification (Biogeme log-likelihood at the published coefficients, no estimation)
| | Biogeme | Article / project |
|---|---|---|
| Estimation half, article coefficients (4 decimals) | -3798.4568 | -3798.5 |
| Estimation half, full-precision coefficients | -3798.4566 | -3798.4566 (project) |
| Hold-out half, full-precision coefficients | -3688.3259 (validation half, N 839; project -3688.33) | |
N 846, K 9. Evaluation: about 1.0 min, 0.7 GB (eager, `use_jit=False`).

The hold-out half was also used in the specification search, so its log-likelihood is not a fully independent test.

## Estimation feasibility
The likelihood is exact (full choice set, destination mixture) and small in data (one configuration per record, about 1,200-1,500 records), so Biogeme estimation is expected to fit in memory on a normal workstation; the cost is the size of the expression (1,588 utilities plus up to 13 candidate utilities per record), which Biogeme compiles with JAX before the first iteration. The eager log-likelihood evaluation (`--evaluate`) needs under 1 GB. A full Biogeme estimation was not run here: the machine was short of memory (other jobs), and the test estimation of the smaller model 09 was stopped after 56 minutes (45 min CPU, about 3 GB) without finishing compilation. If memory is short, set `calculating_second_derivatives = "never"` (BFGS, robust s.e. from finite differences) or `analytical_hessian_mode = "chunked"` in `../output/biogeme.toml`.
