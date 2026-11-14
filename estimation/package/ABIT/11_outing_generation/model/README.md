# Model 11: Outings from the usual workplace: generation (binary logit)

y = 1 if the worker made at least one outing during the (merged) work episode at the usual workplace. Constant, work duration 0-4 h and 4-7 h (per h; above 7 h has slope 0, not in the model), secondary work episode, arrival before 7:00 / from 10:00 (reference 7-10), workplace zone with at least 10,000 jobs per km2, ln(1 + home-workplace km).

Reference: est_subtour.tex, first table (tab:est_subtour_gen). `reference_estimates.csv`: coefficients and robust s.e. at full precision (project output), the article values, LL(0), LL, N, K.

Run (Biogeme 3.3.5 venv):

    ~/.venvs/biogeme/bin/python estimate_outing_generation.py --evaluate            # LL at the reference estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_outing_generation.py                       # estimation; results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py            # ../output/comparison.csv

Options: `--half holdout` evaluates the hold-out half; `--at full` uses the full-precision estimates instead of the article's rounded ones; `--outdir DIR` puts the Biogeme files elsewhere.

Special handling: none (unweighted, all alternatives in one formula, robust s.e. = Biogeme's sandwich).

Verification (2026-11-13):

| | Biogeme | reference |
|---|---|---|
| LL at the article estimates, estimation half (N 8,613, K 8) | -3061.4936 | -3061.5 (article) |
| LL at the full-precision estimates | -3061.4936 | -3061.4936 (project) |
| LL hold-out half, article estimates | -3093.2372 | -3093.2 (article) |

A full Biogeme estimation (run into a scratch folder, then deleted) converged to the reference estimates (largest |difference| / s.e. below 1e-5) and the same LL.
