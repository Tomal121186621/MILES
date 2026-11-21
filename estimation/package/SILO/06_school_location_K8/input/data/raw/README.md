# Raw inputs: school location (k8)

Copies of the original run outputs:
- `l10_school_k8_fit.csv`, `_coef.csv`, `.log`: final specification sequence; the final model is step `final`, the same model without
  the own-race share is `final_no_race`; `_final_coef.csv`: final estimates (full precision); `_collin.csv`: correlations and VIF of
  the final model's attributes. `build_estimation_data.py` reads `_fit.csv` and `_coef.csv`.
- `l09_school_k8_fit.csv`, `_coef.csv`, `.log`: earlier tests (see ../../model/README.md, development).
- `l07_school_k8_fit.csv`, `_coef.csv`, `.log`: previous models (final = step 'final').

Shared sources: `../../../../00_shared_data/school_choice_work/` (students, home and school location mixtures, attendance
boundaries, school points, enrolment by zone and band; outputs of `sc_00_sabs.py` and `sc_01_data.py`; school attributes
`school_zone_attr.parquet`, `school_student_race.parquet` and others from `school_attributes_data.py`), `school_attributes_raw/` (public downloads read by `school_attributes_data.py`), `skims/`, `zone_system/`,
`rts_2017_18/` (student race). The school-tour logsums `logsum.npy` (363 MB, not in the final models) are in `school_choice_work/`.
