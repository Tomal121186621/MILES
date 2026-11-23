# Model 20: Mode of the legs of transit tours (multinomial logit; not in the article)

Mode of each linked trip of a transit tour: TR transit (reference), WK walk, CP car passenger, CD car driver, BK bike. Terms: constants; first / last leg, leg at the main activity; walk and bike km, ln(1 + km) for CP and CD; transit minutes / 10 and no-path dummy on TR; previous-leg mode, car-driver first leg on the last leg; no car, fewer cars than drivers, age, licence; work / school tour, peak, Washington region.

Availability: WK <= 8 km, BK <= 30 km, CD with licence, age 16+, a household car and a household car free over the tour window. A car is free when the household's car-driver tours overlapping the window (leave home .. arrive home) are fewer than its cars at every instant of the window; this is the rule DAYMAP (Daily Activity Model for Agent Plans) applies when it draws the leg modes (`../input/code/free_car.py`). Legs whose observed mode is unavailable are dropped.

The fewer-cars-than-drivers term is kept: the car allocation runs before the leg choice but covers only part of the effect, and the term stays significant under the free-car rule (likelihood-ratio test p = 0.0001).

Reference: not in the article; reference = the coefficient file used by DAYMAP, `3_abit/tasha_estimation/results/tasha_transit_legs_1120h.csv`. `reference_estimates.csv`: coefficients and robust s.e. at full precision (project output), LL(0), LL, hold-out LL, N, K.

Run (Biogeme 3.3.5 venv):

    ~/.venvs/biogeme/bin/python estimate_transit_leg_mode.py --evaluate            # LL at the reference estimates (writes nothing)
    ~/.venvs/biogeme/bin/python estimate_transit_leg_mode.py                       # estimation; results in ../output
    ~/.venvs/biogeme/bin/python compare_with_reference.py            # ../output/comparison.csv

Options: `--half holdout` evaluates the hold-out half; `--outdir DIR` puts the Biogeme files elsewhere.

Special handling: none (unweighted, all alternatives in one formula, robust s.e. = Biogeme's sandwich).

Verification (2026-11-20):

| | Biogeme | reference |
|---|---|---|
| LL estimation half (N 6,773, K 35) | -3421.4993 | -3421.4993 |
| LL hold-out half (N 6,417) | -3290.9822 | -3290.9822 |

A full Biogeme estimation converged to the reference estimates (largest |difference| / s.e. 0) and the same LL; its files are in `../output`.
