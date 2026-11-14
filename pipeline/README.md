# Chain orchestration and converters

The code is here; chain runs, logs and skims stay in the workspace (`WORKSPACE/pipeline/runs`, `WORKSPACE/pipeline/logs`,
`WORKSPACE/2_silo/input/skims`, `WORKSPACE/3_abit/skims`).

- `run_chain.py`: the integrated loop, with the stages `silo-step`, `abit`, `matsim-pop`, `matsim`, `skims`, `loop`, `test`
  and `status` (`python pipeline/run_chain.py --help`). The final assignment runs used `matsim` per seed through
  `assignment/run_seeds.sh`.
- `activities_to_matsim.py`: activity-model activities and legs plus the land-use persons -> MATSim population
  (one representative weekday per person, `activity/lib/representative_day.py`).
- `snap_to_network.py`: move activities off dead-end car links (applied after the population is built).
- `skims_from_matsim.py`: congested car skims from the MATSim events.
- `transit_skim.py` (with `TransitSkim.java`): transit skims on the mapped schedule of a network year.
- `accessibility.py`: logsum accessibility by zone for the land-use model.
