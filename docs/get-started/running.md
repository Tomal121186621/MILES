# Run the chain

The chain runs in seven steps. Each step can be repeated on its own; later steps read the outputs of earlier ones.

```mermaid
flowchart LR
  s1[1 Base population] --> s2[2 Engine coefficients] --> s3[3 Calibrate land use] --> s4[4 Land use 2016–2024] --> s5[5 Schools] --> s6[6 ORIOLE-Day 2024] --> s7[7 MATSim 2024]
```

## 1. Base population (2016)

```bash
cd population/cvae
python run_all.py                    # steps 00 → 07: preprocess, targets, train, generate, workplaces, export, validate
python steps/03_train.py --tag full --latent 24 --hidden 256 --free-bits 0.5   # train on its own
python steps/04_generate.py --tag full
cd ../post
python rebalance_population.py       # redraw to ACS household and age controls, place in zones
python workplace_balanced.py         # workplaces of residents outside the workplace-model area
python export_silo_base.py           # hh, pp, dd, jj 2016 in SILO format
```

Output: `hh_2016.csv`, `pp_2016.csv`, `dd_2016.csv`, `jj_2016.csv`.

## 2. Coefficients into the engines

```bash
python landuse/engine_check/e01_resloc_files.py      # residential location
python landuse/engine_check/e02_car_files.py         # car ownership
python landuse/engine_check/e03_workplace_files.py   # workplace choice
python landuse/engine_check/e04_school_files.py      # school location
python landuse/engine_check/w01_base_respec.py       # reassign 2016 workplaces with the estimated model
python activity/build_coef_respec.py                 # activity-model coefficient set
```

The unit checks `landuse/engine_check/c01`–`c05` compare engine utilities with the Biogeme estimates.

## 3. Calibrate the land-use model (2016–2020)

```bash
CALIB_SPEC=respec CALIB_TAG=F python landuse/calibration/calibrate.py 4 1     # 4 rounds from round 1
```

Writes the calibrated levers to `landuse/calibration/params_respec.json` and a log per round.

## 4. Land use 2016–2024 (five seeds)

```bash
OOS_SPEC=respec SILO_XMX=24g python landuse/run/run_oos.py 5 2     # 5 seeds, 2 in parallel
```

A single run:

```bash
python landuse/run/make_properties.py myscenario 2016 2024 -1 1 respec
bash landuse/run/run_silo.sh landuse/run/myscenario.properties 28g
```

## 5. School location (every year, every seed)

```bash
SCHOOL_SPEC=respec python landuse/schoolchoice/sc_13_run_seeds.py 1 2 3 4 5
```

## 6. ORIOLE-Day (2024)

```bash
python activity/final_2024/runs_respec24.py snapshot
python activity/final_2024/runs_respec24.py run --jobs 2 --seeds 1-10   # ten replications, 10 % households
python activity/final_2024/runs_respec24.py choose                       # replication closest to the mean
```

A single run:

```bash
python activity/run_abit.py myrun --coef activity/coef_respec --seed 1 --sample 0.1 --threads 6 --xmx 13g --year 2024
```

## 7. MATSim (2024)

```bash
python pipeline/abit_to_matsim_pop.py --activities activities.csv --legs legs.csv \
       --pp pp_2024.csv --hh hh_2024.csv --out population_2024.xml.gz --no-gateways
python pipeline/pop_scc_links.py network_2024.xml.gz population_2024.xml.gz population_2024_scc.xml.gz
bash assignment/validation/run_seeds_respec.sh 1 5          # seeds 1–5, 100 iterations, 10 % sample
```

Or directly through the pipeline:

```bash
python pipeline/run_chain.py --sample 0.1 --iterations 100 --threads 12 --xmx 32g \
       matsim 2024 2024 1 --toll assignment/network/roadpricing_HARB_2024.xml --plans population_2024_scc.xml.gz
```

## The pipeline

`pipeline/run_chain.py` runs every stage with resumable bookkeeping (a `.done.json` marker per stage, a registry of
completed stages and one log per stage).

| Stage | Command |
|---|---|
| Land-use step | `run_chain.py silo-step Y0 Y1 [--skims TAG]` |
| Activities | `run_chain.py abit Y [--skims TAG]` |
| MATSim plans | `run_chain.py matsim-pop Y [--residents-only] [--no-gateways]` |
| Assignment | `run_chain.py matsim Y NETWORK SEED [--toll FILE] [--plans FILE]` |
| Skims from MATSim | `run_chain.py skims Y [--seeds a,b]` |
| Full loop with feedback | `run_chain.py loop [--max-inner 3]` |
| Smoke test (1 % sample) | `run_chain.py test` |
| Status | `run_chain.py status` |

Global options: `--sample --iterations --threads --xmx --silo-xmx --seed --dry-run --force`.

!!! note "Feedback loop"
    The `loop` stage feeds MATSim travel times back to land use and activities in two-year steps. The results
    reported in Calibration and validation use fixed skims.
