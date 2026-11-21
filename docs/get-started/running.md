# Run the chain

Every step is one `miles` command. Add `--dry-run` to any command to see what it would run.

```mermaid
flowchart LR
  s1[1 Population] --> s2[2 Coefficients] --> s3[3 Calibrate] --> s4[4 Land use] --> s5[5 Schools] --> s6[6 Activities] --> s7[7 Traffic]
```

## 1. Synthetic population (2016)

```bash
miles population all            # preprocess, targets, train, generate, workplaces, export, validate
miles population base-year      # fit to ACS controls, place in zones, external workplaces, export for SILO
miles population validate
```

Train or generate on their own: `miles population train --tag full`, `miles population generate --tag full`.

**Output:** `hh_2016.csv`, `pp_2016.csv`, `dd_2016.csv`, `jj_2016.csv`.

## 2. Estimated coefficients into the engines

```bash
miles landuse coefficients      # residential location, car ownership, workplace, schools, zone attributes; then sync
miles landuse base-workplaces   # 2016 workplaces with the estimated workplace model
miles landuse check             # engine utilities against the Biogeme estimates
miles activity parameters       # the MAST parameter set (activity/parameters)
miles activity distributions    # survey distributions of frequency, start time and duration
```

## 3. Calibrate the land-use model (2016–2020)

```bash
miles landuse calibrate --rounds 4
```

The calibrated levers are written to `landuse/calibration/calibrated_parameters.json`.

## 4. Land use 2016–2024

```bash
miles landuse seeds --seeds 5 --parallel 2      # five seeds, out of sample, validated year by year
miles landuse run --seed 1 --end 2024           # one run
```

## 5. School location

```bash
miles landuse schools --seeds 5                 # every year of every seed
```

## 6. Activities (MAST, 2024)

```bash
miles activity replications --seeds 1-10        # ten replications on 10 % of households; picks the one closest to the mean
miles activity run --seed 1 --sample 0.1        # one run
```

## 7. Traffic assignment (MATSim, 2024)

```bash
miles assignment plans --activities activities.csv --legs legs.csv --pp pp_2024.csv --hh hh_2024.csv --out population_2024.xml.gz
miles assignment seeds                          # seeds 1–5, 100 iterations, 10 % sample
miles assignment run --seed 1 --toll assignment/network/roadpricing_HARB_2024.xml --plans population_2024.xml.gz
miles assignment validate
```

## The pipeline

`miles chain` runs the orchestrator with resumable bookkeeping (a marker per stage, a registry of completed stages and
one log per stage):

| Stage | Command |
|---|---|
| Land-use step | `miles chain silo-step Y0 Y1 [--skims TAG]` |
| Activities | `miles chain abit Y [--skims TAG]` |
| MATSim plans | `miles chain matsim-pop Y [--residents-only] [--no-gateways]` |
| Assignment | `miles chain matsim Y NETWORK SEED [--toll FILE] [--plans FILE]` |
| Skims from MATSim | `miles chain skims Y [--seeds a,b]` |
| Full loop with feedback | `miles chain loop [--max-inner 3]` |
| Smoke test (1 % sample) | `miles chain test` |
| Status | `miles chain status` |

Global options: `--sample --iterations --threads --xmx --silo-xmx --seed --dry-run --force`.

!!! note "Feedback loop"
    `miles chain loop` feeds MATSim travel times back to land use and activities in two-year steps. The results in
    Calibration and validation use fixed skims.

## Re-estimate a model

```bash
miles estimate list
miles estimate car_ownership --check    # log-likelihood at the published estimates
miles estimate car_ownership            # full Biogeme estimation and comparison
```
