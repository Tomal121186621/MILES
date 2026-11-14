# SILO engine changes

ORIOLE runs on SILO ([msmobility/silo](https://github.com/msmobility/silo)), commit `3066ca9`. Its changes are
shipped as `landuse/java/engine_uncommitted_changes.patch` (modified files) and `landuse/java/engine/` (new files at
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
| `engine_check/e01_resloc_files.py` | `resloc_region_mnl_respec.csv`, `resloc_dwelling_mnl_respec.csv`, attributes |
| `engine_check/e02_car_files.py` | `car_ownership_coefficients_respec.csv`, PUMA file |
| `engine_check/e03_workplace_files.py` | `job_choice_coefficients_respec*.csv` |
| `engine_check/e04_school_files.py` | school coefficients |
| `engine_check/e05_zone_attributes.py` | zone attributes |

Checks: `c01`–`c05` recompute utilities in the engine and compare them with $X\beta$ from the estimation; the
verifiers are switched on with `-Dsilo.resloc.respec.dump` and `-Dsilo.jobchoice.verify`.

## Adding a model

1. Estimate it and write its coefficients to a CSV in `landuse/input/`.
2. Read the file in a properties class and add a switch key.
3. Implement the utility in a pure class (as `ReslocRespecUtility`), so the engine and a verifier share it.
4. Add a unit check that compares engine utilities with the estimation.
