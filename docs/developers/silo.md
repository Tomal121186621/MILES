# SILO engine changes

MILES runs on SILO ([msmobility/silo](https://github.com/msmobility/silo)), commit `3066ca9`. Its changes are
shipped as `landuse/engine/silo_changes.patch` (modified files) and `landuse/engine/src/` (new files at
their package paths).

## Classes

| Class | Module | Status | Role |
|---|---|---|---|
| `ReslocModel` | useCases/maryland | changed | three-level nested logit: county → zone × dwelling type → dwelling |
| `ReslocProperties` | useCases/maryland | changed | reads the `resloc.*` keys |
| `ReslocRespecUtility` | useCases/maryland | new | utilities of the estimated residential location model, shared by engine and verifier |
| `ReslocRespecVerify` | useCases/maryland | new | compares engine utilities with the estimation |
| `CarOwnershipModelMd` | useCases/maryland | changed | 0/1/2/3+ car logit with coefficients from file |
| `CarOwnershipRespec` | useCases/maryland | new | utility of the estimated car-ownership model |
| `JobDataManagerImpl` | siloCore | changed | vacant-job workplace choice with the estimated model |
| `JobDataProperties` | siloCore | changed | `job.choice.*`, `job.search.impedance.file` |

Main class: `de.tum.bgu.msm.run.SiloMstm`.

## Build and run

```bash
mvn compile -pl siloCore,extensions/schools,useCases/maryland
bash landuse/run/run_silo.sh landuse/run/<scenario>.properties 28g
```

`run_silo.sh` uses JDK 21, puts the compiled modules and `landuse/run/classpath.txt` on the class path and logs to
`run/logs/<scenario>.log`.

## From estimates to engine files

| Script | Writes |
|---|---|
| `coefficients/write_residential_location.py` | `residential_county_coefficients.csv`, `residential_zone_dwelling_coefficients.csv`, county and zone attributes |
| `coefficients/write_car_ownership.py` | `car_ownership_estimated_coefficients.csv`, `car_ownership_puma_attributes.csv` |
| `coefficients/write_workplace_choice.py` | `workplace_choice_coefficients.csv` |
| `coefficients/write_school_location.py` | school coefficients (`landuse/schools/parameters/`) |
| `coefficients/write_zone_attributes.py` | zone attributes |

Checks: `landuse/checks/check_*.py` recompute utilities in the engine and compare them with $X\beta$ from the estimation; the
verifiers are switched on with `-Dsilo.resloc.respec.dump` and `-Dsilo.jobchoice.verify`.

## Adding a model

1. Estimate it and write its coefficients to a CSV in `landuse/engine_inputs/`.
2. Read the file in a properties class and add a switch key.
3. Implement the utility in a pure class (as `ReslocRespecUtility`), so the engine and a verifier share it.
4. Add a unit check that compares engine utilities with the estimation.
