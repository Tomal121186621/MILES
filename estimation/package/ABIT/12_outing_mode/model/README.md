# Model 12: Outings from the usual workplace: mode (walk against the mode of the work tour, binary logit)

y = 1 if the outing is on foot, 0 if it keeps the mode of the work tour; outings with a known work-tour mode and first-stop zone. Constant (walk), ln(1 + km workplace -> first stop), work tour as car driver / car passenger (reference other modes), more than one stop, workplace zone with at least 10,000 jobs per km2, no car (reference: household with a car).

The fewer-cars-than-drivers term is not included: it is not significant (likelihood-ratio test p = 0.34) and BIC is lower without it.

Reference: est_subtour.tex, third table (tab:est_subtour_mode). `reference_estimates.csv`: coefficients and robust s.e. at full precision (project output), the article values, LL(0), LL, N, K.

Run (Biogeme 3.3.5 venv):

    ~/.venvs/biogeme/bin/python estimate_outing_mode.py --evaluate            # LL at the reference estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_outing_mode.py                       # estimation; results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py            # ../output/comparison.csv

Options: `--half holdout` evaluates the hold-out half; `--at full` uses the full-precision estimates instead of the article's rounded ones; `--outdir DIR` puts the Biogeme files elsewhere.

Special handling: none (unweighted, all alternatives in one formula, robust s.e. = Biogeme's sandwich).

Verification (2026-11-20):

| | Biogeme | reference |
|---|---|---|
| LL at the article estimates, estimation half (N 1,177, K 7) | -360.6073 | -360.6 (article) |
| LL at the full-precision estimates | -360.6073 | -360.6073 (project) |
| LL hold-out half (N 1,153), full-precision estimates | -299.8185 | -299.8185 (project) |

A full Biogeme estimation converged to the reference estimates (largest |difference| / s.e. below 1e-11) and the same LL; its files are in `../output`.
