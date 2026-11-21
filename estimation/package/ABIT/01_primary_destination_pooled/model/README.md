# 01 primary destination of discretionary tours, pooled (article Table est_dc_pooled)

Multinomial logit over all 1,588 zones for the main activity of shopping, recreation, accompanying and other tours, estimated jointly with a scale per purpose (shopping = 1). N 14,341 (shopping 5,058, recreation 4,159, accompanying 1,593, other 3,531), K 62, LL -49,427.4.

## Likelihood

- Location mixture: each record has up to 4 possible destination zones (survey traffic zone spread over model zones by jobs, weights b_k) and up to 4 possible home zones (spread by housing units, weights w_c). L_n = sum_c w_c [sum_k b_k exp(U_c,z_k)] / [sum_j exp(U_c,j)], over all 1,588 zones. No sampling of alternatives.
- U = SCALE_p x V_p. SCALE multiplies every coefficient. Coefficients are in V units as in the article (the effective coefficient of purpose p is SCALE_p times the value). The project optimised purpose-specific scaled coefficients as gamma = SCALE_p x beta for conditioning; this is a reparametrisation (same maximum).
- Shared: distance pieces, outside home county / state, all ln(distance) interactions; car generalised time shared by shopping and other. Purpose specific: intrazonal, area dummies, ln(zone area), land-use mix, the coefficient of ln(1 + x), car generalised time of recreation and of accompanying.
- Area dummies: Baltimore City, Washington DC, high job-density zone (at least 10,000 jobs per km²), Virginia, Delaware / Pennsylvania / West Virginia. The parameters `B_cbd_<purpose>` are the high job-density zone flag (zone column `cbd`).
- Fixed: distance > 50 km at 0 (`B_dist_50km_plus_shared`, status 1); SCALE_SHOPPING = 1.
- Attraction: one variable per purpose, entered as B_ln_x_p ln(1 + x_j): retail jobs for shopping, recreation and other (B_ln_retail_jobs_SHOPPING, _RECREATION, _OTHER), school enrolment for accompanying (B_ln_school_enrolment_ACCOMPANY). Zone area: B_ln_zone_area_km2_p ln(area_j), area in km², at least 0.05 km².
- Bounds as in the estimation: SCALE [0.01, 50]. Unweighted, robust s.e.
- One utility per zone with per-record coefficients (purpose dummies), so the expression is the size of one purpose's model.

## Run

```
~/.venvs/biogeme/bin/python estimate_primary_destination_pooled.py --evaluate [--at article|full] [--half holdout] [--groups 1,2]
~/.venvs/biogeme/bin/python estimate_primary_destination_pooled.py          # estimation, output in ../output
~/.venvs/biogeme/bin/python compare_with_reference.py
```
`--evaluate` computes the log-likelihood at the reference values without estimating (eager evaluation, records grouped by number of home configurations, writes nothing). The data are in `../input/data` (parts per purpose and number of configurations; the script pads to 4 configurations with weight 0 for estimation).

`reference_estimates.csv`: the 62 parameters (project output, full precision; article values), plus LL0, LL_beta, N, K. `p_value` is against 0; the article's p of the scales is against 1.

## Verification

| | estimation half |
|---|---|
| article LL(beta) | -49,427.4 |
| project likelihood, full-precision estimates | -49,427.4083 |
| Biogeme `--evaluate`, full-precision estimates | not run (about 67 min) |
| Biogeme `--evaluate`, article estimates | not run |

Hold-out half, project likelihood, full-precision estimates: -47,778.8003 (not evaluated with Biogeme: time). The hold-out half was also used in the specification search, so its log-likelihood is not a fully independent test.

## Estimation with Biogeme: memory

Not feasible on this machine (48 GB, about 45 GB used by other jobs); the script is exact and complete, but expect it to fail or swap.

- Evaluation only (`--evaluate`, eager, no gradient): about 67 minutes for the estimation half (groups of 1, 2, 3, 4 home configurations: about 3, 10, 19 and 35 minutes; time grows faster than the number of configurations), peak 2.4 GB.
- Estimation needs the compiled (JIT) value, gradient and BHHH: measured on 20 records with 1 home configuration and a reduced choice set, compile memory 1.2 GB (50 zones), 1.4 GB (100), 2.9 GB (200), compile time 38 / 72 / 174 s; memory does not depend on the number of records (200 records: same). Extrapolated to 1,588 zones: about 15-30 GB and 40+ minutes of compilation for one home configuration; the full data need 4 configurations per record (padding with weight 0), about 4 times the expression, so roughly 60-120 GB, plus the analytical Hessian for the robust s.e. Without JIT, reverse-mode gradients keep every intermediate: about 1.8 million nodes x 14,341 records x 8 bytes, roughly 200 GB.
- A machine with 128 GB or more might estimate it; alternatively restrict the check to evaluation (as done here) or estimate with the project's PyTorch code (`../input/code/dp_pooled.py`, `pool_core.py`), which reached these estimates.
