# 00 TASHA distributions (not a Biogeme model)

Empirical distributions of the TASHA activity generator, built from the estimation half of the 2017/18 RTS by
`code/tasha_distributions.py` (copy of `3_abit/tasha_distributions.py`, paths rewritten; imports `rts_common.py`,
`survey_population.py`, `abit_metrics.py`, also copies): activity frequency, start time, duration, joint-episode participants and
propensities, location bands, scheduling parameters.

Regenerate (project Python with numpy and pandas), into `output/`:

    cd code
    PYTHONDONTWRITEBYTECODE=1 TASHA_JOINT_PB=1 TASHA_LIC_TYPES=IO_ACC,IS,IO_REC,IO_OTH python3 tasha_distributions.py
    python3 compare_with_reference.py          # output/comparison.csv

These are the settings of the build of 2026-11-10 (`3_abit/estimation_distributions/tasha_respec`, log in
`data/reference_outputs/build_log_tasha_respec_2026-11-10.txt`) from which `3_abit/build_coef_respec.py` took the files.
`data/reference_outputs` = the files of `3_abit/coef_respec/tasha` used by the 2024 runs.

Check (2026-11-13, regeneration into a scratch folder, about 10 s, 1 GB):
- identical: tasha_frequency, tasha_start, tasha_duration, tasha_joint_propensity_mand, tasha_location_bands.
- differ: tasha_joint_participants and tasha_joint_propensity. The coefficient set keeps these two files from the earlier
  build of 2026-10-22 (3_abit/coef_tasha); the current code removes the stops of work-based outings (2026-11-03), which
  changes a few joint episodes (counts by up to 3 episodes / 23 members, shares by up to 0.004).
- tasha_params: the reference also holds the engine settings appended by the coefficient builds (18 keys) and
  chain.slack.to.next = 1.0 (set by the coefficient build; the script writes 0.5). The other keys are identical.
- not written by this script: tasha_activity_targets, tasha_wfh_2017_19 (attendance), tasha_return_home and tasha_subtour
  (models 13, 11, 12: written by build_coef_respec.py from their estimates), tasha_transit_legs (model 20), tasha_params_pre1103l (old).
