# Calibrated ABIT Maryland coefficient set (stage 3, 2026-10-22)

Copy of the pristine reference `ABIT/input/maryland/coef/` (its `PROVENANCE.md` is kept here unchanged) with the files below
replaced or added by `3_abit/calibrate_abit.py` (`coef_tools.init_coef`, update rules in `calibrate_abit.update`), calibrated to
the ESTIMATION half of the 2017/18 Regional Travel Survey (`data/rts_split.csv`, `3_abit/targets_estimation.csv`); the history of
every iteration's parameter files is in `3_abit/coef_history/it<K>/`, the log in `3_abit/calibration_log.csv`, the report in
`3_abit/VALIDATION_REPORT.md`.  `pipeline/run_chain.py` copies this directory into every ABIT run (`ABIT_COEF`, overridable with
the environment variable `ABIT_COEF_DIR`); `3_abit/run_abit.py --coef <dir>` does the same for stand-alone runs.

| file | content | origin |
|---|---|---|
| `rt_freq_rates.csv` | purpose, rate (survey tours per traveller-day), segment (worker, student_<band>, nonworker, retiree, all), factor (calibrated weekly multiplier; EDUCATION: multiplier of the school-day probability) | survey rates + calibration |
| `run_params.csv` | `wfh.attendance.dayfactor` (calibrated), `workplace.silo = true`, `edu.time.from.targets = true`; appended to the properties by `make_abit_properties.py` | calibration / stage-3 switches |
| `dest_friction_power.csv` | `b_time`, `b2` of the discretionary purposes rescaled to the survey trip-length means (WORK row unchanged, not used with SILO workplaces) | calibration |
| `stopfreq_offsets.csv` | offsets per stop specification and half, calibrated to the survey stops per tour (spread unchanged) | calibration |
| `rt_mode_by_purpose.csv` | tour main-mode shares by purpose = the ASC re-anchor targets of `MarylandFullModeChoice` (survey estimation half, corrected for the tour-to-trip difference) | survey + calibration |
| `tod_rts.csv` | 15-min distribution of the arrival at the primary activity by purpose | survey estimation half |
| `duration.distributions.csv` | 15-min distribution of the primary-activity duration by purpose | survey estimation half |
| `rt_dist_by_purpose.csv` | exp-mean distance per purpose (median / ln 2) for the ASC pre-anchor sample | survey estimation half |
| `targets_education.csv` | school-day probability, arrival quantiles, duration, distance and mode shares by band (non-working students) | `education_targets.py --split estimation` |
| `modechoice_full_*.csv` | re-anchored ASC sets as shipped; ABIT re-anchors them again at every start and writes into the run's copy | pristine |
| `CALIBRATION_STATE.json` | last iteration and its criteria counts | `calibrate_abit.py` |

Second pass (2026-10-22, iterations 13 onward; `coef_tools.upgrade_pass2`, first-pass set in `coef_history/it12/`):

| file | content | origin |
|---|---|---|
| `stop_purpose.csv` | purpose of an intermediate stop by tour purpose and position (out / in): probabilities of WORK, EDUCATION, SHOPPING, RECREATION, ACCOMPANY, OTHER and the number of survey stops (`MarylandStopModel`, property `stop.purpose.file`) | `build_targets.stop_purpose_split`, estimation half (`estimation_distributions/stop_purpose.csv`); not calibrated |
| `dest_attraction.csv` | attraction weights of the destination choice by purpose over the zone attributes the reader builds (hh.total = sampled persons, scaled by 1/sample.fraction in the model; jj.total, jj.retail, jj.office, jj.other = jobs of the full SILO job file by zone and type; students = school occupancy of the SILO assignment): shopping = retail jobs + 0.1 population, other = population + all jobs, recreation = population + 0.5 retail + 0.25 all jobs, accompany = population + students (`MarylandDestinationChoice`, property `dest.attraction.file`) | `coef_tools.ATTR0`; fixed, not calibrated |
| `dest_distance_bands.csv` | distance-band constants per discretionary purpose (bands of `rts_common.DIST_BINS` on the car-distance skim, intrazonal 0.5 sqrt(area)): the friction of a pair is multiplied by exp(constant) (`MarylandDestinationChoice`, property `dest.distance.bands`) | calibration (second pass) to the survey trip-length distributions by purpose |
| `rt_freq_rates.csv` | + rows of the segment `toddler` (persons under 5: survey tours per travelling under-5 by discretionary purpose, factor calibrated); EDUCATION factor = share of students that travel in the estimation half (0.824, `travellers / traveller_share_group / student` of the targets), fixed: the weekly school-day probability of all students is the survey share of travelling students with a school tour times that share | survey + calibration |
| `run_params.csv` | + `disc.monday.weight` (4.0, fixed; the Monday weight of the discretionary day assignment, equal to the former `abit.disc.pmon = 0.5`) and `disc.freeday.weight` (calibrated: weight of a weekday without a mandatory tour; the lever of the EDUCATION tours per travelling student) | calibration |
| `run_params.csv` (cont.) | + `disc.sameday.penalty` (C, calibrated, 11.83 at iteration 30): the weight of a weekday in the discretionary day assignment is divided by (1 + C n_d), n_d = the person's discretionary tours already on that day; the lever of the traveller share of the members other than workers and students (a Poisson-thinned Monday count fixes the non-traveller share at e^-lambda; VALIDATION_REPORT.md section 7.1) | calibration (iterations 23-30) |
| `stopfreq_offsets.csv` | + `HBO_RECREATION_*`, `HBO_ACCOMPANY_*`, `HBO_OTHER_*`: the offsets of the pooled HBO specification by tour purpose (a purpose row takes precedence over `HBO_out` / `HBO_in`) | calibration |

Everything else is the pristine file.  The NTD transit re-anchoring of July 2026 (`PROVENANCE.md`, `rt_mode_by_purpose.csv`)
is superseded in this set by the survey shares of the estimation half (FRAMEWORK principle 4: ridership is a stage-4 test, not
a target); the pristine file keeps the NTD-scaled row.

Estimated destination choice (2026-10-22, `3_abit/destination_choice/ESTIMATION_REPORT.md`):

| file | content | origin |
|---|---|---|
| `dest_choice_mnl.csv` | segment (`<PURPOSE>_primary`, `<PURPOSE>_stop` for SHOPPING, RECREATION, ACCOMPANY, OTHER), variable, value: `mu_size`, size weights `size_<pop/ret/off/oth/stu>` (base 1; absent = 0) and the linear terms of the final MNLs (piecewise distance / detour, car generalized time `cgt`, mode-choice logsum `ls`, intrazonal and area constants, retail density, land-use mix, county / state boundary, ln-distance interactions); read by `MarylandDestinationChoice` (property `dest.mnl.file`, set by `make_abit_properties.py` when the file exists) | maximum likelihood (Biogeme 3.3.5) on the estimation half of the 2017/18 RTS, importance-sampled choice sets with the McFadden correction, tract measurement model; validated on the validation half; not calibrated |
| `run_params.csv` | + `dest.choice.model = mnl`: the estimated MNL replaces the gravity form for primary discretionary destinations and discretionary stops (the corridor rule remains for WORK / EDUCATION stops). `gravity` restores the calibrated form of the second pass (`dest_attraction.csv`, `dest_friction_power.csv`, `dest_distance_bands.csv`, which stay in the set) | switch |

The MNL reads the mode-choice coefficients `modechoice_full_<purpose>.csv` of this set for its logsum (as shipped, before the
run re-anchors them) and the skims of the run; it was estimated with the 2016 base car skims and the 2024 door-to-door transit
skims (`3_abit/skims/base_transit2024`).

## Model of record (2026-10-23): the files added to this TASHA set

This directory (`3_abit/coef_tasha/`) is the behavioural TASHA-style set, and the model of record of the abit stage
(`pipeline/run_chain.py`, `pipeline/PIPELINE.md`). It is `coef_tools.init_tasha()` followed by `coef_tools.finalize_tasha()`.
Every file or key below is estimated on the ESTIMATION half of the 2017/18 RTS (`data/rts_split.csv`, seed 2026) by the
scripts of `3_abit/tasha_estimation/` (report: `tasha_estimation/ESTIMATION_REPORT.md`). Nothing is calibrated. Content hashes
of the sources are in `TASHA_STATE.json` (`final_components`). The set before this step is kept in
`3_abit/coef_history/tasha_behavioural_pre_final/`.

| File / key | Content | Source |
|---|---|---|
| `dest_choice_mnl.csv`, segments `WORK_wbwork_stop`, `WORK_wbhome`, `WORK_wahb`, `EDUCATION_nonstud`, `EDUCATION_daycare` | location MNLs of work business (usual-workplace workers: detour between home and workplace; others: from home), work trips of at-home workers, school of persons without a school record, daycare; replace the distance-band model (`tasha_location_bands.csv`, kept but no longer read for these types) | `estimate_locations.py` → `results/dest_choice_loc.csv`; ML, importance-sampled choice sets (R = 40), tract measurement model, robust s.e.; held-out test `results/loc_heldout.csv` |
| `dest_choice_mnl.csv`, segments `SHOPPING/RECREATION/ACCOMPANY/OTHER_primary` | the final primary MNLs of `destination_choice/` + ln(distance) × tour with stops (`lnd_multi`), re-estimated; replace the rows of the pooled models | `estimate_complexity.py` → `results/dest_choice_primary_cx.csv`; LR tests `results/cx_tests.csv` |
| `dest_choice_mnl.csv`, segments `<PURPOSE>_seq_stop` | the final stop MNLs re-estimated with sequential anchors (previous location → next anchor); the `<PURPOSE>_stop` rows stay (used for the household-level relocation of joint episodes) | `estimate_stops_seq.py` → `results/dest_choice_stop_seq.csv`; held-out test `results/seq_heldout.csv` |
| `tasha/tasha_return_home.csv` | binary logit of a return home between two consecutive out-of-home episodes (specification B, without the outcome-dependent gap) | `estimate_return_home.py nogap` → `results/tasha_return_home.csv`; estimates `results/rh_nogap_estimates.csv` |
| `tasha/tasha_wfh_2017_19.csv` | ACS work-at-home share of workers by home county, interview years 2017-2019 (the base-year attendance input) | `temporal_2024/build_telework.py` (`telework/wfh_attendance_2017_19.csv`), ACS PUMS |
| `tasha/tasha_params.csv`: `attendance.file`, `attendance.k` (1.2473), `attendance.q0` (0.2340), `attendance.cap` (0.6) | work attendance of usual-workplace workers, (1 − min(cap, k p_c)) (1 − q0) | `estimate_attendance.py` → `results/tasha_attendance.csv`; k = moment ratio of the usual telework days (RTS j1_telecommute_days) to the county share, q0 by ML |
| `tasha/tasha_params.csv`: `home.return.file`, `home.return.min.slack` (5) | the logit above; a return home is infeasible below 5 min at home | `coef_tools.FINAL_PARAMS` |
| `tasha/tasha_params.csv`: `regen.conditional`, `regen.band.first` (true) | a conflicting episode is regenerated from its own start-time distribution restricted to the free windows of the schedule (first within the start band of the original draw), with its duration truncated to the room | scheduling rule (TASHA reject-and-regenerate) |
| `tasha/tasha_params.csv`: `relocate.joint` (true), `relocate.joint.mode` (anystop) | a joint episode that is a stop in a participant's chain is located on the stop MNL, anchors home and that chain's main activity | scheduling rule |
| `tasha/tasha_params.csv`: `chain.slack.to.next` (1.0, was 0.5) | on a direct link the episode of lower precedence moves by the whole gap | operational constant, re-fixed in single-seed runs on the estimation half (ESTIMATION_REPORT.md section 4) |

Not used by this set: `tasha_return_home_gap.csv` (specification A, documented only) and `home.stay.factor` (the former rule;
kept in `tasha_params.csv`, inactive while `home.return.file` is set).

The calibrated variant `3_abit/coef_tasha_cal/` is this set copied by `calibrate_abit.py --tasha --tag tfcal --init`. The loop
then changes, on the estimation half only:
- `tasha_freq_factors.csv` (frequency factors);
- the constant of its own copy of `tasha/tasha_return_home.csv`;
- the mode anchors in `rt_mode_by_purpose.csv`.

Log: `3_abit/calibration_log_tfcal.csv`; history: `3_abit/coef_history/tfcal_it*`.
