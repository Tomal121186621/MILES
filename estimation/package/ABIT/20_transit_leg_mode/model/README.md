# Model 20: Mode of the legs of transit tours (multinomial logit; not in the article)

Mode of each linked trip of a transit tour: TR transit (reference), WK walk, CP car passenger, CD car driver, BK bike. Terms: constants; first / last leg, leg at the main activity; walk and bike km, ln(1 + km) for CP and CD; transit minutes / 10 and no-path dummy on TR; previous-leg mode, car-driver first leg on the last leg; no car, fewer cars than drivers, age, licence; work / school tour, peak, Washington region. Availability: WK <= 8 km, BK <= 30 km, CD with licence, age 16+ and a household car. Final model after backward elimination (|robust t| < 1.96) of the full search (results/tleg_search.csv). The coefficients equal coef_respec/tasha/tasha_transit_legs.csv (checked to 1e-12).

Reference: not in the article; reference = 3_abit/coef_respec/tasha/tasha_transit_legs.csv and 3_abit/tasha_estimation/results/tleg_estimates.csv, tleg_search.csv (row F). `reference_estimates.csv`: coefficients and robust s.e. at full precision (project output), LL(0), LL, N, K.

Run (Biogeme 3.3.5 venv):

    ~/.venvs/biogeme/bin/python estimate_transit_leg_mode.py --evaluate            # LL at the reference estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_transit_leg_mode.py                       # estimation; results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py            # ../output/comparison.csv

Options: `--half holdout` evaluates the hold-out half; `--at full` uses the full-precision estimates instead of the article's rounded ones; `--outdir DIR` puts the Biogeme files elsewhere.

Special handling: none (unweighted, all alternatives in one formula, robust s.e. = Biogeme's sandwich).

Verification (2026-11-13):

| | Biogeme | reference |
|---|---|---|
| LL estimation half (N 6792, K 35) | -3501.8128 | -3501.8128 (results/tleg_search.csv) |
| LL hold-out half (N 6,438) | -3366.7280 | -3366.7280 |

A full Biogeme estimation (run into a scratch folder, then deleted) converged to the reference estimates (largest |difference| / s.e. below 1e-5) and the same LL.
