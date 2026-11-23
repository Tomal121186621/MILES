# Shared preparation chain (raw data to 00_shared_data)

This folder rebuilds the shared inputs of the models of DAYMAP (Daily Activity Model for Agent Plans; folder ABIT) from the raw data. Everything it would produce already ships in `../00_shared_data`, so each step can be skipped.

- `DATA_SOURCES.json`: every raw input, with provider, URL, what to download and where to put it (`../00_shared_data/raw/<folder>/`). Status `documented` means the URL is taken from the project's download logs or scripts. Status `verify` means no URL is documented, so the provider's landing page is given.
- `SHARED_STEPS.json`: the steps in run order. Each has its command, inputs, outputs, runtime, memory and whether the output is provided. Commands are run from a model folder (`cwd` = `../00_shared_prep/code`).
- `code/`: copies of the project scripts (paths rewritten, lines marked `PATH`) and small wrappers.
  - Outputs go to `../00_shared_data/rebuilt/` (or `$ABIT_REBUILT`); provided files are never overwritten.
  - Raw inputs are read from `../00_shared_data/raw/` (or `$ABIT_RAW`).
  - Compare a rebuilt file with the provided one using `check_against_provided.py`.

## Run order

| Step | Script (code/) | Python |
|---|---|---|
| S00 download | `fetch_gtfs.sh`, `fetch_gtfs_regional.sh`; other sources by hand (DATA_SOURCES.json) | sh |
| S01 survey cleaning | not available (01_clean_rts.py of the tour-based MITO); cleaned files provided | - |
| S02 split | `make_rts_split.py` | venv |
| S03 tract to zone, zone population | `build_survey_population.py --rebuild-zone-files` | project (geopandas) |
| S04 survey population | `build_survey_population.py` | venv |
| S05 episodes | `build_episodes.py` | venv |
| S06 MSTM skims | `convert_mstm_skims.py` | venv |
| S07 GTFS merge | `merge_gtfs_full.py` | project |
| S08 GTFS to MATSim schedule | pt2matsim (Java), command in SHARED_STEPS.json | java 21 |
| S09 transit skims by period | `transit_period_skims.py` (+ `TransitSkim.java`) | project + java 21 |
| S10 car times by period | `car_period_skims.py` (MATSim events) | project (geopandas) |
| S11 2024 door-to-door transit | `transit_skim.py` | project (geopandas) + java 21 |
| S12 tract-to-zone overlay | `build_tract_zone_overlay.py` | project (geopandas) |
| S13 zone table, jobs | `build_zone_tables.py --jobs-from-raw` | venv |
| S14 TAZ crosswalks | `taz_crosswalk.py` | project (geopandas) |
| S15 tract splits | `rts_11_data_v2.py` | project (geopandas) |
| S16 tours, parking share | `prep_tours.py` | venv |
| S17 WESML weights | `wesml_targets.py` | venv |
| S18 logsum coefficients | the estimations of models 14 to 17 | venv |
| S19 input check | `check_against_provided.py` | venv |

- venv: `~/.venvs/biogeme/bin/python`.
- project: a Python with geopandas, such as `/opt/homebrew/anaconda3/bin/python3` here.
- Always set `PYTHONDONTWRITEBYTECODE=1`.

## Checked on 2026-11-13

Each of these was rebuilt into a scratch folder and found identical to the provided file. Raw inputs were the project's own copies.
- S02 split
- S03 tract_zone and zone population
- S04 survey population (both halves, all five files)
- S05 episodes
- S06 skims (distance agrees to 1e-4 m because of rounding)
- S12 overlay
- S13 zone table and jobs extract
- S16 tours and parking share
- S17 WESML targets and weights

Not re-run:
- S07 to S11: they need Java, the MATSim jar and MATSim runs.
- S14, S15: they need the SILO workplace work files.
- S01: the script is not available.

## Cannot be rebuilt from public data alone
- The survey: it must be requested from BMC or MWCOG, and the cleaning script is not on this machine.
- The MSTM skims and zones: MDOT provides them.
- The 2016 synthetic population and jobs: these are products of the VAE and SILO stages.
- The MATSim network, schedule mapping and resident run: products of the MATSim stage.
- The current GTFS feeds: they differ from the 2026-10-21/22 downloads.
