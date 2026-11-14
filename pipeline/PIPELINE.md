# Orchestration of the integrated loop (`run_chain.py`)

Written 2026-10-22. Implements the loop of `0_framework/FRAMEWORK.md` ("The integrated loop"): SILO, the activity model and the
assignment are run as one sequence in two-year steps from 2016 to 2026, travel times are fed back at every step, and the two
validation years (2024, 2026) are iterated to convergence. Everything a run reads and writes is recorded with a content hash.

## Stages

| stage | command | what it does | output |
|---|---|---|---|
| SILO step | `run_chain.py silo-step Y0 Y1 [--iter K] [--skims TAG]` | run base directory `<runs>/silo/<scen>/` with `input/` (link to `2_silo/input`), `microData/` (the Y0 restart files of the previous step, hash-checked against that step's done marker) and `skims/` (skims of Y0); properties from `2_silo/run/make_properties.py` with the calibrated parameters of `2_silo/calibration/params.json` (applied as `calibrate.py` does), the start-year skim keys and `school.file.ascii = microData/schools`; engine via `2_silo/run/run_silo.sh` | `<runs>/silo/<scen>/scenOutput/<scen>/microData/futureYears/{hh,pp,dd,jj,schools}_Y1.csv`, `resultFileSpatial.csv` |
| ABIT | `run_chain.py abit Y [--iter K] [--skims TAG]` | properties from `3_abit/make_abit_properties.py` (SILO population of Y, skims TAG), ABIT compiled with javac into `3_abit/classes` (`compile_abit`), run with java 21, `abm.RunAbitMarylandLos`; the mode-choice re-anchoring writes into a per-run copy of the coefficient directory (`<run>/coef`) so the shared inputs do not drift | `<runs>/abit/<name>/output/{activities,legs}_<name>.csv` |
| population | `run_chain.py matsim-pop Y [--iter K]` | `abit_to_matsim_pop.py`: one weekday per person, BMR subarea cut, cordon gateways, POI and building microlocations, SILO attributes (port of `ABIT/validation/build_studyarea.py`) | `<runs>/matsim_pop/<tag>/population_<tag>.xml.gz` |
| MATSim | `run_chain.py matsim Y NETWORK SEED [--iter K] [--iterations N] [--sample F] [--toll F]` | `de.umd.matsim.RunBaltimoreToll` from `Updated MATSim/code/matsim-run/target/baltimore-matsim-1.0.jar` (MATSim 2024.0), the run set-up of `I695_pricing/02_run/run_matsim.sh` and `config.py` (route and departure-time replanning, mode choice off = hybrid design, innovation off at 0.9, income-scaled value of time, frozen ASCs), flow capacity = sample, storage = sample^0.75, transit on the year's schedule (`4_matsim/transit/transitSchedule_<Y>`, all operators; run network `network_<Y>_pt` = the car links of `network_<Y>` + transit links; link ids checked first; vehicle capacity and PCE scaled to the sample in `<run>/transitVehicles_scaled.xml.gz`), 36 h simulation | `<runs>/matsim/<tag>_s<seed>/output_events.xml.gz`, plans, linkstats |
| skims | `run_chain.py skims Y [--iter K] [--seeds a,b]` | `matsim_to_skim.py` per seed (AM peak 07-09, car vehicles only, prior = 2016 base skim for pairs beyond the network), mean over the seeds, csv.gz for SILO and csv.gz + omx for ABIT; transit skims of the year's network (`transit_skim.py`: SwissRailRaptor, AM peak, 1,600 m walk, cached per network year in `<runs>/skims/transit_<Y>/`) for SILO `transit_peak_time` and ABIT `bus_tt`, `rail_tt00`; distance skims linked from the base | `2_silo/input/skims/<tag>/`, `3_abit/skims/<tag>/` (test: `pipeline/test/skims/<tag>/{silo,abit}`) |
| loop | `run_chain.py loop [--skip-2016-base] [--max-inner 3] [--seeds-validation 1,2,3,4,5]` | 2016 base (ABIT, MATSim, skims on the 2016 population), then for Y = 2018 … 2026: SILO Y-2 → Y with skims(Y-2), ABIT Y, population, MATSim Y (network 2024 up to 2024, 2026 for 2026; five seeds in 2024 and 2026, one otherwise), skims Y; in 2024 and 2026 the five stages are repeated with skims(Y) until the SILO result changes by less than 0.5 % in every county's population and 2 % in every zone's auto accessibility (`convergence()`, from `resultFileSpatial.csv`), at most three repeats; the repeat that meets the criterion is completed (ABIT, MATSim, skims), so the converged state has its assignment | `<runs>/state.json` (which scenario and skim tag belong to each year), `<runs>/convergence_<Y>.jsonl` |
| status | `run_chain.py [--test] status` | the done markers and the state | |

Scenario names: `chain_<Y0>_<Y1>` and `chain_<Y0>_<Y1>_it<K>` (test: `test_…`); ABIT runs `chain_abit_<Y>[_itK]`; skim tags `<Y>[_itK]`,
`base` = the MSTM-derived 2016 skims in `2_silo/input/skims/` and `3_abit/skims/`.

Resumability: every stage writes `<stage dir>/.done.json` (inputs and outputs with size, mtime and a sha256 of the first and last MiB,
duration, the run constants) and is skipped when the marker exists; `--force` reruns. Every completed stage is appended to
`<runs>/registry.jsonl`. Logs: `pipeline/logs/run_chain.log` (every command and exit code) and `pipeline/logs/<stage>_<tag>.log`;
the SILO engine log stays in `2_silo/run/logs/<scen>.log` (written by `run_silo.sh`). `--dry-run` prints the whole command
sequence without running anything (the loop sequence was checked this way: 2016 base, five steps, 5 seeds in 2024/2026, three
repeats each, every repeat restarting from the Y-2 microdata).

Production run: `python3 pipeline/run_chain.py loop` (10 % ABIT sample, 100 MATSim iterations, 32 g for MATSim, 28 g for SILO, 12 threads;
all overridable: `--sample --iterations --xmx --silo-xmx --threads --seed`). Runs land under `pipeline/runs/`.

## The test (2026-10-22, `run_chain.py test`, everything under `pipeline/test/`, 265 s)

| stage | input | result | time |
|---|---|---|---|
| ABIT 2016 | 1 % household sample of the 2016 base microdata (`2_silo/input/microData`), base skims, 6 threads, 10 g | 47,045 households, 124,740 persons, 62,980 jobs, 6,749 schools read; 23,400 students with their SILO school; plans written | 52 s |
| population | ABIT plans + SILO hh/pp 2016 | 26,045 persons touching the BMR (22,180 intra, 1,887 inflow, 1,978 outflow; 0 dropped at the cordon), 97,025 legs on one weekday (car 68,662, ride 21,018, walk 4,311, pt 2,137, bike 897), 92.1 % of non-home activities on a real POI, every attribute 100 % except workZone 57 % (non-workers) | 26 s |
| MATSim 2016 | `network_2024.xml.gz`, 2 iterations, seed 1, flow 0.01 / storage 0.0316, transit on (30,449 schedule link refs, 0 missing in the network), toll NONE | finished, events and plans written (`pipeline/test/matsim/2016_s1/`) | 136 s |
| skims 2016 | events of seed 1, prior = base skim | 20.1 % of car links observed 07-09 h; 39.8 % of the 1,588 x 1,588 pairs from MATSim (mean 48.1 min), 60.2 % from the prior (501 zones are more than 4 km from the network: the MSTM zone system covers six states, the network the Baltimore region); BMR-internal pairs: mean 40.7 min against 43.6 min in the base skim, median ratio 0.93, correlation 0.948 | 50 s |
| SILO 2016 → 2018 | not started (a calibration run occupies the engine) | properties and run base written: `pipeline/test/silo/test_2016_2018.properties`, `pipeline/test/silo/test_2016_2018/{input,microData,skims}`; the command printed: `bash 2_silo/run/run_silo.sh pipeline/test/silo/test_2016_2018.properties 28g` | |

Defects found by the test and fixed in `matsim_to_skim.py`:
1. The pending `entered link` of a trip's last link was closed by the `left link` of the vehicle's next trip from the same link, so activity
   durations were counted as link travel times (realised/free-flow 45 on observed links). Fixed: `vehicle leaves traffic` clears the entry (ratio 6.2 after the fix; the rest is the 1 % sample with 2 iterations, see below).
2. Transit vehicles (4,841, 12 % of the entered-link events at 1 %) were counted as cars; their stop dwell times are not car travel times. Fixed: vehicles of `TransitDriverStarts` are skipped.
3. Zone pairs beyond the network or without a path were 999 min (30 % of the pairs); they now keep the prior skim (the base), as the earlier chain's `skim_from_events.py` did.

## Open items (not solved by the orchestration)

- Transit (closed 2026-10-22, `4_matsim/transit/TRANSIT_BUILD.md`): the MATSim schedule is now built from the GTFS of all 18 feeds in the
  network area (MTA local/commuter bus, Light Rail, Metro, MARC, Charm City Circulator, Harbor Connector, Towson Loop, RTA, AACT, Annapolis,
  Harford, Carroll, WMATA Metrorail and Metrobus, Ride On, TheBus, Amtrak) for Wednesday 2026-10-21, mapped with pt2matsim 24.4 (shape-guided
  router `MapWithShapes`) onto `network_2024` and `network_2026` (`4_matsim/transit/{transitSchedule,transitVehicles,network_*_pt}_<Y>`); the
  transit skims (`transit_peak_time`, `bus_tt`, `rail_tt00`) are routed per network year with SwissRailRaptor (`pipeline/transit_skim.py`).
  Open: the base transit skims are not door-to-door times (new/base median ratio 6.1): recalibration or convention decision
  (TRANSIT_BUILD.md 8.3); five operator feeds are stale; no 2024 GTFS (2024 uses the 2026 service).
- The MSTM zones outside the network (554 of 1,588 since the run network is `network_<Y>_pt` without the earlier chain's artificial `pt_` nodes; 501 before) keep base travel times; the integrated effect is therefore confined to the Baltimore
  region, which is where SILO's feedback matters for the study. A six-state network would remove the prior.
- MATSim config choices to confirm for the validation runs: harbor tolls (`I695_pricing/01_designs/designs/roadpricing_HARB.xml`, `--toll`;
  its two Key Bridge link ids do not exist in the new networks), the 2016–2022 years on `network_2024` (no earlier network built), one
  SILO seed per step (FRAMEWORK step B asks for 5 SILO seeds; `--seed`), and the sample-size artefact of the test (flow capacity 0.01 gives
  few vehicles per link and long queues in 2 iterations; the production runs are 10 % and 100 iterations).
- ABIT: the run re-anchors its mode-choice constants against its own tours and writes them (`writeReanchored`); the pipeline isolates this
  per run, so no re-anchoring carries over between years. Whether the chain should carry constants forward is a stage-3 decision.
- The population converter drops external-external travellers and caps inflow at the cordon budgets of the 2023 count stations
  (`cordon_stations_expanded_anchored.csv`), as in the earlier chain; these budgets are 2023 values in every year.
- SILO schools: a SILO step reads `microData/schools_<Y0>.csv`; when the previous step wrote no final school file (the calibration runs so far
  have none), the 2016 inventory is linked (ids stable, occupancy of 2016).

## Coefficient set of the ABIT stage (stage 3, 2026-10-22)

The abit stage copies `ABIT_COEF` (constant at the top of `run_chain.py`; environment variable `ABIT_COEF_DIR` overrides it) into
`<run>/coef` and passes the copy to `3_abit/make_abit_properties.py` as `ABIT_COEF_DIR`, so every coefficient property, the
mode-choice directory, `education.targets.file` (`<set>/targets_education.csv`) and the run parameters of the set
(`<set>/run_params.csv`: `wfh.attendance.dayfactor`, `workplace.silo`) come from one directory.  Default since 2026-10-23: the
behavioural TASHA-style set `3_abit/coef_tasha/` (see "Model of record of the abit stage" below); until then the calibrated set
`3_abit/coef_calibrated/` (estimation half of the 2017/18 survey, `3_abit/calibrate_abit.py`, `3_abit/VALIDATION_REPORT.md`);
the pristine reference `ABIT/input/maryland/coef/` is never written and can be selected with `ABIT_COEF_DIR=<path>`.
`workplace.silo = true` makes ABIT take the work zone of every employed person from the SILO job file (`jobs.file`, personId ->
zone), which is the contract of the loop (before, every worker got a home-gravity draw unless `workplace.reassign.file` was set).
Replications: `-Dabit.seed=N` (`AbitUtils`); the household sample of a run is deterministic, so seeds change only the model draws.
ABIT was recompiled into `3_abit/classes` on 2026-10-22 (`AbitUtils`, `MarylandFrequencyGenerator`, `MarylandLosDataReader`).

Second pass of stage 3 (2026-10-22, `3_abit/VALIDATION_REPORT.md` section 7; recompiled into `3_abit/classes`):

- `make_abit_properties.py` also sets `stop.purpose.file`, `dest.attraction.file` and `dest.distance.bands` when the coefficient set
  carries `stop_purpose.csv`, `dest_attraction.csv` and `dest_distance_bands.csv` (the calibrated set does; the pristine reference
  does not, and the model then keeps its fixed splits), and `run_params.csv` now carries `disc.monday.weight` and
  `disc.freeday.weight` (the discretionary day-of-week assignment).
- The representative weekday handed to MATSim is Monday for every person (`ABIT/validation/abit_day.pick_day`, rule `fixed`,
  `REP_DAY = 0`); a person without legs on Monday gets a home-only plan.  The earlier rule (earliest complete weekday with legs)
  is kept as rule `best` for comparison.  `abit_to_matsim_pop.py` is unchanged apart from taking the work zone of a person
  from the MANDATORY work activity (stops may now carry the purpose WORK).
- Persons under 5 travel (discretionary tours at the survey rates, segment `toddler` of `rt_freq_rates.csv`, 84 % car
  passenger in the survey); their legs reach MATSim as `ride` / `walk` legs, which add no vehicles to the network.
- Java classes changed: `MarylandStopModel` (stop purpose by tour purpose and position; stop offsets by tour purpose),
  `MarylandDestinationChoice` (attraction weights by purpose, distance-band constants), `MarylandDayOfWeekDiscretionaryAssignment`
  (Monday and free-day weights from the properties), `MarylandFrequencyGenerator` (segment `toddler`), and in the reader
  `MarylandLosDataReader` the jobs of the full job file by zone and SILO type (`jj.retail`, `jj.office`, `jj.other`) as attraction sizes.

TASHA-style activity generation (2026-10-22, `3_abit/ROORDA_VALIDATION.md` section 9):

- `run_params.csv` key `tasha.generation = true` makes `RunAbitMarylandLos` generate the plans with
  `abm.models.maryland.MarylandTashaGenerator` instead of `PlanGenerator` and skip `MarylandStopModel`. The generator draws
  activity episodes from joint frequency / start-time / duration distributions, schedules them with TASHA's conflict rules and
  forms tours from the schedule. It generates Monday only (`tasha.days`, default 1), the representative day of the chain.
  Without the key nothing changes, and `coef_calibrated/` does not set it.
- `make_abit_properties.py` sets `tasha.dir = <set>/tasha` when the set has a `tasha/` directory, and `tasha.freq.factors` when
  it has `tasha_freq_factors.csv`.
- Sets: `3_abit/coef_tasha/` is behavioural (distributions of the estimation half, estimated destination MNL, no calibration).
  `3_abit/coef_tasha_cal/` is the same set calibrated on the estimation half (`calibrate_abit.py --tasha`). Using either in
  the loop means pointing `ABIT_COEF_DIR` at it. The runs of section 9 use the skims `3_abit/skims/base_transit2024`, the skims
  the MNL was estimated with.
- Plans handed to MATSim keep their format: activity purposes WORK, EDUCATION, SHOPPING, RECREATION, ACCOMPANY, OTHER, HOME.
  The main activity of a tour is MANDATORY / PRIMARY and its chained episodes are ON_MANDATORY_TOUR stops, as before.
  Persons under 5 now also have EDUCATION (daycare / preschool) episodes.

### Model of record of the abit stage (2026-10-23, `3_abit/ROORDA_VALIDATION.md` section 10)

The abit stage now runs the behavioural TASHA-style model with the estimated destination MNL by default.

How `run_chain.py abit Y` selects it:
1. `ABIT_COEF` (top of `run_chain.py`) = `3_abit/coef_tasha/` unless `ABIT_COEF_DIR` is set. Alternatives:
   - `3_abit/coef_tasha_cal/`: calibrated variant;
   - `3_abit/coef_calibrated/`: earlier weekly generator;
   - `ABIT/input/maryland/coef/`: pristine.
2. The stage copies the set to `<run>/coef` and calls `make_abit_properties.py` with `ABIT_COEF_DIR=<run>/coef`. That script
   adds:
   - `tasha.dir = <run>/coef/tasha` (the set has a `tasha/` directory);
   - `dest.mnl.file = <run>/coef/dest_choice_mnl.csv`;
   - the keys of `<run>/coef/run_params.csv`: `workplace.silo = true`, `tasha.generation = true` (selects
     `MarylandTashaGenerator` in `RunAbitMarylandLos`) and `dest.choice.model = mnl`.
3. Everything else of the model is in `<run>/coef/tasha/tasha_params.csv`:
   - the estimated return-home logit (`home.return.file`);
   - work attendance (`attendance.file` = the base-year ACS 2017–19 table, `attendance.k`, `attendance.q0`);
   - the scheduling constants.
   The estimated location segments are in `dest_choice_mnl.csv` (`WORK_wbwork_stop`, `WORK_wbhome`, `WORK_wahb`,
   `EDUCATION_nonstud`, `EDUCATION_daycare`, `<PURPOSE>_primary` with the tour-complexity term, `<PURPOSE>_seq_stop`).
   Provenance: `3_abit/coef_tasha/README_CALIBRATED.md`, `3_abit/tasha_estimation/ESTIMATION_REPORT.md`; content hashes:
   `3_abit/coef_tasha/TASHA_STATE.json`.
4. Optional: `ABIT_ATTENDANCE_FILE=<countyfips,p csv>` gives the attendance step the work-at-home shares of the simulated year
   (`tasha.attendance.file`), e.g. `3_abit/temporal_2024/telework/wfh_attendance_2024.csv`. Unset, every year uses the
   base-year table (frozen attendance).
5. Skims: the ABIT side of the skim tag `base` (the 2016 base step) is now `3_abit/skims/base_transit2024`, i.e. the base car
   skims with the 2024 door-to-door transit skims, the skims the MNLs were estimated and validated with. `ABIT_BASE_SKIM_DIR`
   restores `3_abit/skims`. Later years read the skims the loop produces.

Classes: `MarylandTashaGenerator` and `MarylandDestinationChoice` were recompiled into `3_abit/classes` on 2026-10-23. The
earlier sets run unchanged on these classes: every new behaviour is switched on by keys or segments that only `coef_tasha` /
`coef_tasha_cal` carry.

## Changes to existing files

- `3_abit/make_abit_properties.py`: optional environment variables `SILO_SCEN_DIR`, `ABIT_RUN_ROOT`, and an absolute skim directory as the
  skim tag; defaults unchanged.
- `pipeline/matsim_to_skim.py`: the three fixes above and the optional sixth argument (prior skim).
- `3_abit/classes/`: ABIT compiled with javac (200 classes, `3_abit/classes_build.log`).

## Transit build and skims (2026-10-22)

`4_matsim/transit/TRANSIT_BUILD.md`. Changes to `run_chain.py`: constants `TRANSIT`, `TRANSIT_SKIM_ARGS`, `TRANSIT_SKIMS` (transit set per network
year; `ABIT_BASE_SKIMS` now distance only), `network_year()`, `check_transit(cfg, net, sched)` (cache per network and schedule), the matsim stage
(run network `network_<Y>_pt`, schedule and vehicles of the year, vehicles scaled to the sample by `4_matsim/transit/vehicle_types.py`, marker
fields `network_base`, `network_year`, `schedule`, `vehicles`, `vehicles_unscaled`, `vehicle_scale`; `--iterations`/`--sample` also accepted after
the stage name), the new stage function `transit_skims()` (marker stage `transit-skims`, stats in the marker) called by `skims` (links
`transit_peak_time`, `bus_tt`, `rail_tt00` of the year; marker field `transit_skim` = network year, directory, schedule, files).
Tests: `--test --force matsim 2016 2024 1 --iterations 1` 101 s; `matsim 2016 2026 2 --iterations 1` 102 s; `--test --force skims 2016` 129 s
(car 34 s, transit 90 s).

## Estimated destination choice and accessibility measures (stage 3, 2026-10-22)

`3_abit/destination_choice/ESTIMATION_REPORT.md`. The discretionary destination choice of ABIT is now an estimated MNL
(primary destinations and stops by purpose; estimation half of the 2017/18 RTS, Biogeme), applied over the full choice set:
`MarylandDestinationChoice` (property `dest.choice.model = mnl | gravity`, coefficient file `dest.mnl.file`) and
`MarylandStopModel` (discretionary stops; persons processed in parallel with per-person seeded generators in MNL mode).
Both classes were recompiled with javac into `3_abit/classes` (`javac -nowarn -d 3_abit/classes -cp 3_abit/classes:<abit_classpath.txt>
ABIT/src/main/java/abm/models/maryland/MarylandDestinationChoice.java ABIT/src/main/java/abm/models/maryland/MarylandStopModel.java`).
`make_abit_properties.py` sets `dest.mnl.file` when the coefficient set holds `dest_choice_mnl.csv`; `coef_calibrated/run_params.csv`
carries `dest.choice.model = mnl`.
- Skims: the stop models contain ABIT's mode-choice logsum, which reads `bus_tt` / `rail_tt00`; the models were estimated with
  the 2024 door-to-door transit skims. The chain's 2016 base ABIT step still reads the MSTM transit skims (`base`); to make it
  consistent, point its transit skims at the 2024 set (`3_abit/skims/base_transit2024` holds base car + 2024 transit).
- Cost: a 5 % chain ABIT run takes longer with the MNL (stops); see the report, section 10.
- `pipeline/accessibility.py --year Y --car-skims <dir> --transit-skims <dir> --micro <SILO microdata dir>` writes
  `data/accessibility_<Y>.csv` (zone x SILO income group x car availability x purpose: log-sum accessibility of the estimated
  models in utils and dollars, logsum-specification version, Hansen jobs accessibility) for the SILO residential-location and
  car-ownership models; column contract in the report, section 9. `data/accessibility_2016.csv` is written. In the loop, call it
  after the `skims` stage of year Y with that year's ABIT skim directory and the SILO scenario's `microData/futureYears`.

## MATSim 2024 validation runs (2026-11-02)

Author decisions: residents only, USDOT value of time, network 2024 with the Key Bridge closed, harbor tunnel tolls, fixed modes,
five seeds. Runner: `4_matsim/validation/run_seeds.sh` (seeds 1-5 one after the other), validation `4_matsim/validation/validate_counts.py`,
report `4_matsim/REPORT.md`.

- Input plans: ABIT 2024 replication `fin24_tw_s01` (`3_abit/final_2024/matsim_input_choice.csv`, parquet), SILO oos_s5 2024 persons
  (schools step) and households. `run_chain.py matsim-pop 2024 --residents-only --activities --legs --pp --hh` (new options).
- `abit_to_matsim_pop.py`: reads parquet as well as CSV; `hhIncome` = 12 x sum over all household members of int(annual income)/12
  (the hh file of the rebuilt chain has no income column; ABIT's arithmetic); new flag `--residents-only`: persons with a home outside
  the BMR are dropped (26,788 at 10 %), the cordon gateways and their count-derived budgets are off, outside activities keep their
  ABIT coordinates. Result: 225,241 residents, 866,159 legs. The default behaviour (flag off) is unchanged.
- `pop_scc_links.py` (new): activities whose nearest car link is one of the 7 car links outside the strongly connected component (dead
  ends of the I-95 Express Toll Lanes) get the nearest connected link (885 of 1,091,400 activities); without it MATSim stops with
  "No route found".
- Value of time: `MATSIM_STRAT` now `income.vot.form=usdot, vot.share=0.5, vot.hours=2080, vot.income.floor=5000` (was power form,
  elasticity 0.6, median 84,216). `RunBaltimoreToll` (Updated MATSim/code/matsim-run, jar rebuilt; old jar kept as
  `target/baltimore-matsim-1.0.jar.bak_pre_usdot`): VOT_n = 0.5 x max(hhIncome_n, 5000) / 2080 $/h, the definition of ABIT's
  `MarylandTourNestedModeChoice`; per-person marginal utility of money = performing (0.78 utils/h) / VOT_n; the global value (used
  by the toll router) = 0.78 / VOT of the median household income ($23.48/h at 2024 -> 0.0332 utils/$). VOT over the residents:
  p5 $3.61, median $23.48, mean $29.02, p95 $71.43 per hour. The rebuild also brings in source changes made after the previous jar
  (truck layer, hazmat bans, truck toll factors, shop hours as properties): all off or identical at their defaults.
- Output volume: `-Dwrite.events.interval`, `-Dwrite.plans.interval`, `-Dlinkstats.interval`, `-Dlinkstats.average` (new properties,
  defaults unchanged); `run_chain.py matsim` sets them to the iteration count (events/plans at iteration 0 and the last, link stats of
  the last iteration averaged over its last 5).
- Tolls: `4_matsim/network/roadpricing_HARB_2024.xml` = `roadpricing_HARB.xml` without the two Key Bridge links ($3.00 per crossing,
  2-axle E-ZPass Maryland, Fort McHenry and Baltimore Harbor tunnels; the six link ids exist in network_2024). No link of network_2024
  crosses the Patapsco at the Key Bridge site.
- Known detail: MATSim deletes the run directory at start, so `transitVehicles_scaled.xml.gz` named in the done marker is gone after
  the run; MATSim's `output_transitVehicles.xml.gz` is the same set.
- Correction (2026-11-02, coordinator): "residents only" = no synthetic or fitted traffic, not fewer chain persons. New converter flag
  `--no-gateways` (run_chain `matsim-pop --no-gateways`): every SILO/ABIT person touching the BMR is kept (intra 202,209, inflow 26,788,
  outflow 23,032 = 252,029 persons; legs 766,734 / 114,563 / 99,425; car legs 421,973 / 80,372 / 61,678 = 564,023), gateways and the
  inflow cap off, outside activities at their ABIT coordinates; `pop_scc_links.py` sets 954 activity links. The first population
  (`--residents-only`, BMR homes only, 225,241 persons) and its seed-1 run are kept as `runs/matsim_pop/2024_bmronly`,
  `runs/matsim/2024_s1_bmronly`, `4_matsim/validation/data/link_hours/link_hours_s1_bmronly.csv.gz` for comparison.
