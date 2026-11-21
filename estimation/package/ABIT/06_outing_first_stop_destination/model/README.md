# 06_outing_first_stop_destination

Outings from the workplace: destination of the first stop (location choice, multinomial logit over 1,588 zones). Article table: est_subtour_dest (second table in est_subtour.tex).

## Model
Location of the first stop of an outing from the usual workplace; anchor = the workplace zone. Distance from the workplace in pieces (0-1, 1-2, 2-5, 5-10, 10-20, 20-50 km; slope per km), car generalised time, intrazonal, outside the workplace county, attraction ln(1 + retail jobs).

Likelihood (full choice set, no sampling of alternatives): L_n = sum_k b_k exp(V_z_k) / sum_j exp(V_j), the sum in the numerator over the zones z_k overlapping the survey's destination tract (b_k = overlap area / zone area); one anchor configuration per record. Attraction B_ln_retail_jobs ln(1 + retail jobs_j); no bounds. Unweighted; robust (sandwich) standard errors. Full equations in the docstring of `estimate_outing_first_stop_destination.py`.

## Files
- `estimate_outing_first_stop_destination.py`: Biogeme 3.3.5 script (descriptive parameter names).
- `reference_estimates.csv`: article coefficients (rounded) and project output (full precision), robust s.e., p; rows LL0, LL_beta, N, K.
- `compare_with_reference.py`: compares a run in `../output` with the reference.

## Run (Biogeme venv)
    ~/.venvs/biogeme/bin/python estimate_outing_first_stop_destination.py --evaluate              # LL at the article estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_outing_first_stop_destination.py                         # estimation, results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py
Options: `--half holdout`, `--at full` (full-precision coefficients), `--outdir DIR`. Data: `../input/data/estimation/biogeme_part*.parquet` (rebuild: `../input/code`, see its README; project Python with torch).

## Special handling
- The distance piece above 50 km is held at 0 (dropped in the final stage, rule C, with car generalised time in the model); it is left out of the utility.
- Record files `wbs_dest_records_*`: the anchor is in column `home_idx` (= the workplace zone) as in the project code.

## Verification (Biogeme log-likelihood at the published coefficients, no estimation)
| | Biogeme | Article / project |
|---|---|---|
| Estimation half, article coefficients (4 decimals) | -3112.2733 | -3112.3 |
| Estimation half, full-precision coefficients | -3112.2733 | -3112.2733 (project) |
| Hold-out half, full-precision coefficients | -3126.0990 (validation half, N 1155; project -3126.10) | |
N 1180, K 10. Evaluation: about 1.2 min, 0.7 GB (eager, `use_jit=False`).

The hold-out half was also used in the specification search, so its log-likelihood is not a fully independent test.

## Estimation feasibility
The likelihood is exact (full choice set, destination mixture) and small in data (one configuration per record, about 1,200-1,500 records), so Biogeme estimation is expected to fit in memory on a normal workstation; the cost is the size of the expression (1,588 utilities plus up to 13 candidate utilities per record), which Biogeme compiles with JAX before the first iteration. The eager log-likelihood evaluation (`--evaluate`) needs under 1 GB. A full Biogeme estimation was not run here: the machine was short of memory (other jobs), and the test estimation of the smaller model 09 was stopped after 56 minutes (45 min CPU, about 3 GB) without finishing compilation. If memory is short, set `calculating_second_derivatives = "never"` (BFGS, robust s.e. from finite differences) or `analytical_hessian_mode = "chunked"` in `../output/biogeme.toml`.
