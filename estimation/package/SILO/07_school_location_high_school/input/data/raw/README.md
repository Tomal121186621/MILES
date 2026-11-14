# Raw inputs: school location (hs)

Copies: `l07_school_hs_fit.csv`, `_coef.csv`, `.log` (original run; final = step 'final').
Shared sources: `../../../../00_shared_data/school_choice_work/` (students, home and school location mixtures, attendance
boundaries, school points, enrolment by zone and band; outputs of `sc_00_sabs.py` and `sc_01_data.py`), `skims/`, `zone_system/`.
Not copied: `Validation_2026/2_silo/schoolchoice/work/logsum.npy` (363 MB, school-tour logsums, not in the final models; loaded by
`sc_03_engine.py` at import).
