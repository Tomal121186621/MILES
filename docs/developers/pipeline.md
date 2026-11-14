# Pipeline

| File | Role |
|---|---|
| `run_chain.py` | orchestrator: land-use step, activities, MATSim plans, MATSim, skims, loop |
| `activities_to_matsim.py` | MILES-Day output + land-use persons → MATSim plans |
| `snap_to_network.py` | moves activities off car links outside the connected network |
| `skims_from_matsim.py` | AM-peak car skims from MATSim events |
| `transit_skim.py`, `TransitSkim.java` | transit skims with SwissRailRaptor |
| `accessibility.py` | zone accessibility by year for the land-use models |

## Bookkeeping

Every stage writes `<stage>/.done.json` with its inputs, outputs, checksums, duration and settings, and is skipped
next time unless `--force` is given. Completed stages are appended to `registry.jsonl`; logs go to
`pipeline/logs/`. `--dry-run` prints the full command sequence.

## Plans converter

```bash
python pipeline/activities_to_matsim.py --activities A --legs L --pp pp_2024.csv --hh hh_2024.csv \
       --out population.xml.gz [--expansion 10] [--residents-only] [--no-gateways] [--seed 20260707]
```

One weekday per person; tours cut to the Baltimore region (internal, inbound, outbound); homes on residential
buildings and other activities on points of interest of the matching type in the zone.

## Feedback loop

`run_chain.py loop` runs land use, activities and MATSim in two-year steps from 2016 to 2026 and feeds MATSim travel
times back as skims, repeating a validation year until county population changes by less than 0.5 % and zone
accessibility by less than 2 % (at most three repeats).
