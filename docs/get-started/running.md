# Run the chain

Every step is one `terp` command. Add `--dry-run` to any command to see what it would run.

```mermaid
flowchart LR
  s1[1 Population] --> s2[2 Coefficients] --> s3[3 Calibrate] --> s4[4 Land use] --> s5[5 Schools] --> s6[6 Activities] --> s7[7 Traffic]
```

## 1. Synthetic population (2016)

```bash
terp population all            # preprocess, targets, train, generate, workplaces, export, validate
terp population base-year      # fit to ACS controls, place in zones, external workplaces, export for SILO
terp population validate
```

Train or generate on their own: `terp population train --tag full`, `terp population generate --tag full`.

**Output:** `hh_2016.csv`, `pp_2016.csv`, `dd_2016.csv`, `jj_2016.csv`.

## 2. Estimated coefficients into the engines

```bash
terp landuse coefficients      # residential location, car ownership, workplace, schools, zone attributes; then sync
terp landuse base-workplaces   # 2016 workplaces with the estimated workplace model
terp landuse check             # engine utilities against the Biogeme estimates
terp activity parameters       # the TERP-Day parameter set (activity/parameters)
terp activity distributions    # survey distributions of frequency, start time and duration
```

## 3. Calibrate the land-use model (2016–2020)

```bash
terp landuse calibrate --rounds 4
```

The calibrated levers are written to `landuse/calibration/calibrated_parameters.json`.

## 4. Land use 2016–2024

```bash
terp landuse seeds --seeds 5 --parallel 2      # five seeds, out of sample, validated year by year
terp landuse run --seed 1 --end 2024           # one run
```

## 5. School location

```bash
terp landuse schools --seeds 5                 # every year of every seed
```

## 6. Activities (TERP-Day, 2024)

```bash
terp activity replications --seeds 1-10        # ten replications on 10 % of households; picks the one closest to the mean
terp activity run --seed 1 --sample 0.1        # one run
```

## 7. Traffic assignment (MATSim, 2024)

```bash
terp assignment plans --activities activities.csv --legs legs.csv --pp pp_2024.csv --hh hh_2024.csv --out population_2024.xml.gz
terp assignment seeds                          # seeds 1–5, 100 iterations, 10 % sample
terp assignment run --seed 1 --toll assignment/network/roadpricing_HARB_2024.xml --plans population_2024.xml.gz
terp assignment validate
```

## The pipeline

`terp chain` runs the orchestrator with resumable bookkeeping (a marker per stage, a registry of completed stages and
one log per stage):

| Stage | Command |
|---|---|
| Land-use step | `terp chain silo-step Y0 Y1 [--skims TAG]` |
| Activities | `terp chain abit Y [--skims TAG]` |
| MATSim plans | `terp chain matsim-pop Y [--residents-only] [--no-gateways]` |
| Assignment | `terp chain matsim Y NETWORK SEED [--toll FILE] [--plans FILE]` |
| Skims from MATSim | `terp chain skims Y [--seeds a,b]` |
| Full loop with feedback | `terp chain loop [--max-inner 3]` |
| Smoke test (1 % sample) | `terp chain test` |
| Status | `terp chain status` |

Global options: `--sample --iterations --threads --xmx --silo-xmx --seed --dry-run --force`.

!!! note "Feedback loop"
    `terp chain loop` feeds MATSim travel times back to land use and activities in two-year steps. The results in
    Calibration and validation use fixed skims.

## Re-estimate a model

```bash
terp estimate list
terp estimate car_ownership --check    # log-likelihood at the published estimates
terp estimate car_ownership            # full Biogeme estimation and comparison
```
