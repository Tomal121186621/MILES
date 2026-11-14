# engine_check: re-specified SILO models in the engine (2026-11-09)

e01-e04 write the engine input files of the re-specified models; c01-c05 are the unit checks (engine utility vs estimation X beta);
s01/s02 summarise the smoke runs; w01 anchors the workplace DC term and re-assigns the base workplaces (base_v5_respec).

- Own-group share of the zone part: estimated with the 2016 shares of `2_silo/input/microData/hh_2016.csv`, while the engine computes them from its base population `hh_2016_v2.csv` (mean |difference| 0.009); accepted as is by the author (2026-11-09), nothing changed.

## Progress log (2026-11-10)
- accW dropped from the zone part (author, 2026-11-10); re-run of the residential chain started (backups *_pre1110d). Calibration rounds of the 11-10 zone model (calib_respec_r1, r2) kept, to be archived as calib_respec1110a_*.
- 2026-11-10 21:40: STOPPED after the zone re-run without accW (r03/r08/r12 done, backups *_pre1110d). Finding: non-work accessibility alone
  fails at Z1 (p 0.48) but is strongly significant in the final model (+0.527, t 6.7; adding it lowers BIC by 64), and without it the
  accN x children sign flips. Waiting for the author before the county IVs (r07), county (r05), r09, collinearity, tables, engine files,
  smoke, calibration and seeds. 11-10 calibration rounds archived as calib_respec1110a_r*; 11-09 rounds as calib_respec1109_r*.
- 2026-11-10 22:00: option (a) adopted (accN base term + final backward check); residential chain re-run started (run_residential_chain_1110.sh, chain_1110e.out).
- 2026-11-10 21:50: zone chain (option a) done, engine files + checks + smoke done; calibration started: CALIB_SPEC=respec CALIB_TAG=F calibrate.py 4 1 (scenarios calib_respecF_r*, log run/logs/calibrate_respecF.log).
- 2026-11-10: calibration F finished (round 4: moves 1.000, 0-car 0.0684 vs 0.0681, cars 100 %); params snapshot calibration/params_respecF.json. Five seeds started: OOS_SPEC=respec run_oos.py 5 2 (log run/logs/oos_respec.log, scenarios oos_respec_s1..5); schools: SCHOOL_SPEC=respec sc_13_run_seeds.py 1 2 3 4 5 (schoolchoice/runs/driver_respec.log). Next: engine_check/p01_respec_seeds.py, collinearity cars.
- 2026-11-10 03:40: seeds 1-2 finished (SILO); seeds 3-4 running, then 5; school step polling.
- 2026-11-10: five seeds, school seeds, oos_respec_mean, scorecard and seed choice DONE (engine_check/tables/p01_*). Chosen seed: 1.
