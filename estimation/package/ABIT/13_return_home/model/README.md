# Model 13: Return home between consecutive out-of-home episodes (binary logit)

y = 1 if the person went home between two consecutive out-of-home episodes (pairs of two work episodes excluded). Constant, detour via home (km and ln(1 + km)), distance from home, person type (reference non-worker), female, licence, household size, child under 16, cars, income, purposes of the preceding and following episode (reference other individual discretionary), both joint, joint next to work or school, number of out-of-home episodes, end time of the preceding episode (reference 9-15). The project estimated it with statsmodels Logit (HC0 robust covariance): the same likelihood and the same sandwich estimator as Biogeme.

Reference: est_return.tex (tab:est_return). `reference_estimates.csv`: coefficients and robust s.e. at full precision (project output), the article values, LL(0), LL, N, K.

Run (Biogeme 3.3.5 venv):

    ~/.venvs/biogeme/bin/python estimate_return_home.py --evaluate            # LL at the reference estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_return_home.py                       # estimation; results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py            # ../output/comparison.csv

Options: `--half holdout` evaluates the hold-out half; `--at full` uses the full-precision estimates instead of the article's rounded ones; `--outdir DIR` puts the Biogeme files elsewhere.

Special handling: none (unweighted, all alternatives in one formula, robust s.e. = Biogeme's sandwich).

Verification (2026-11-13):

| | Biogeme | reference |
|---|---|---|
| LL at the article estimates, estimation half (N 28,349, K 33) | -13696.9567 | -13697.0 (article) |
| LL at the full-precision estimates | -13696.9511 | -13696.9511 (project) |
| LL hold-out half, article estimates | -13771.5506 | -13771.8 (article) |

A full Biogeme estimation (run into a scratch folder, then deleted) converged to the reference estimates (largest |difference| / s.e. below 1e-5) and the same LL.
