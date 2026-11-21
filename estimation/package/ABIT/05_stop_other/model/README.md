# 05 Stop location: other-errand stops

Article table: est_stop_OTHER_stop (Stop location, other errands). N 8,055, K 20.

## Model
Multinomial logit over all 1,588 zones (no sampling of alternatives) with sequential anchors: a = the location the person comes from, b = the next anchor of the tour (primary destination or home).

V_j = B_ln_retail_jobs ln(1 + retail jobs_j) + detour pieces + mode-choice logsum of the detour + car generalised detour time + stop in the zone of a / of b + area dummies + ln(zone area, km²) + land-use mix + outside the counties (states) of both anchors + ln(1 + detour) × person / tour flags

- detour t = max(0, d(a,j) + d(j,b) - d(a,b)), car distance of the 2016 skim (km, intrazonal 0.5 √area); pieces clip(t - lo, 0, hi - lo).
- Area dummies: Baltimore City, Washington DC, high job-density zone (at least 10,000 jobs per km²), Virginia, Delaware / Pennsylvania / West Virginia. The parameter `B_central_business_district` is the high job-density zone flag (zone column `cbd`).
- Attraction: one variable, retail jobs, entered as B_ln_retail_jobs ln(1 + retail jobs_j). Zone area: area_j in km², at least 0.05 km². No bounds.
- Location mixture (survey traffic zones spread over model zones): up to 4 anchor configurations c (zones of a and b, weight w_c) and up to 4 possible zones z_k of the stop (weight b_k):
  L_n = Σ_c w_c Σ_k b_k exp(V_c,z_k) / Σ_j exp(V_c,j), LL = Σ_n ln L_n. Exactly the likelihood of the estimation; no sampling, no approximation.
- Unweighted, robust (sandwich) standard errors.

## Mode-choice logsum (input from other models)
The variable `ls` = LS(a,j) + LS(j,b) - LS(a,b), LS = log-sum of the re-estimated tour mode model of the other purpose, with the person of the record, stops = 1, joint = 0, both periods = the arrival period. Coefficients: `00_shared_data/mode_choice_logsums/m08_coef.csv` (rows step "final"; the tour mode models 14-17 of this package); level of service: `00_shared_data/skims/mode_choice_periods`, `mode_choice_inputs/parking_paid_share.csv`; code: `input/code/mode_logsum_new.py`, `mc_common.py`, `s_stops_newls.py`. The values are stored in the Biogeme data (`ls_<c>_<j>`); if the tour mode models are re-estimated, rebuild the data (`input/code/build_biogeme_data.py`) with the new m08_coef.csv.

## Run (Biogeme 3.3.5 venv)
```
cd model
~/.venvs/biogeme/bin/python estimate_stop_other.py --evaluate --at article   # LL at the article estimates, writes nothing
~/.venvs/biogeme/bin/python estimate_stop_other.py                           # estimation -> ../output (see memory below)
~/.venvs/biogeme/bin/python compare_with_reference.py                       # estimates vs reference_estimates.csv
```
Options: `--half holdout`, `--at full` (full-precision estimates), `--outdir DIR`.
The data in `../input/data` is ready (798 MB estimation, 788 MB hold-out, float32 parquet in parts of 1,000 records); `../input/code` rebuilds it (project Python with torch).

## Files
- `reference_estimates.csv`: article coefficients and robust s.e. (rounded), the project output at full precision, p-values, LL(0), LL, N, K.
- `compare_with_reference.py`: compares a run in `../output` with it.

## Verification (estimation half, all 8,055 records)
| | LL |
|---|---|
| Article LL(β) | -24,653.3 |
| Biogeme, article estimates | not run |
| Biogeme, full-precision estimates | not run |
| Project likelihood, full precision | -24,653.3007 |
| Project likelihood, hold-out half, full precision | -24,256.6397 |

Biogeme evaluation: eager (`use_jit=False`), rows grouped by their number of anchor configurations (1-4); not run for these estimates (about 30-70 min and under 2 GB on these data).

The hold-out half was also used in the specification search, so its log-likelihood is not a fully independent test.

## Estimation memory
Measured (shopping stops, Biogeme 3.3.5 default JIT): compiling and evaluating the log-likelihood, its gradient and the BHHH matrix on 20 records with ONE anchor configuration took 29 min and 6.1 GB peak memory (compile dominated; the machine was under memory pressure). The estimation expression has up to 4 configurations (4 x 1,588 utilities plus the candidate zones, about 4 times larger), so compiling alone is expected to need about 25 GB or more and several hours, and the reverse-mode intermediates at run time about (expression nodes x records x 8 bytes), i.e. roughly 10-30 GB more (4,000-8,000 records); with the default analytical Hessian more again. Expected total: about 30-50 GB. This does not fit on this machine (48 GB, about 45 GB used by other jobs): the exact full-set mixture estimation in Biogeme is infeasible here and was not run. It needs a machine with about 64 GB free; in biogeme.toml set calculating_second_derivatives = "never" (BHHH) or analytical_hessian_mode = "chunked" to limit the Hessian. The likelihood is not changed or approximated. The evaluation at given coefficients (--evaluate, use_jit=False) needs under 2 GB.
