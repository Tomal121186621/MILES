# SILO engine changes

MILES runs on SILO ([msmobility/silo](https://github.com/msmobility/silo)), commit `3066ca9`. Its changes are
shipped as `landuse/engine/silo_changes.patch` (modified files) and `landuse/engine/src/` (new files at
their package paths).

## Classes

| Class | Module | Status | Role |
|---|---|---|---|
| `ReslocModel` | useCases/maryland | changed | residential location; with `resloc.twolevel=true` it uses the two-level model |
| `ReslocTwoLevel` | useCases/maryland | new | two-level model: PUMA (market size, own-race share, vacancy rule), then dwelling among 30 vacant dwellings |
| `ReslocProperties` | useCases/maryland | changed | reads the `resloc.*` keys |
| Utility and verifier classes | useCases/maryland | new | utilities of the estimated residential and car-ownership models, shared by engine and verifier |
| `CarOwnershipModelMd` | useCases/maryland | changed | 0/1/2/3+ car logit with coefficients from file |
| `SchoolDataMd` | useCases/maryland | changed | school location with the estimated K–8, high-school and college models; seat release |
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
| `estimation/development/residential_location/` (final step) | `residential_puma_coefficients.csv`, `residential_dwelling_coefficients.csv` and the PUMA and zone files |
| `coefficients/export_car_ownership.py` | `car_ownership_estimated_coefficients.csv`, `car_ownership_county_constants.csv` |
| `estimation/development/workplace_choice/w13_*.py` | `workplace_choice_coefficients.csv` |
| `estimation/development/other_locations/l11_export_silo.py` | `school_location_coefficients_{k8,hs,college}.csv` and the school data files |
| `coefficients/write_zone_attributes.py` | zone attributes |

Checks: `landuse/checks/check_*.py` recompute utilities in the engine and compare them with $X\beta$ from the estimation;
the engine verifiers are switched on with system properties (see `landuse/engine/README.md`).

## Adding a model

1. Estimate it and write its coefficients to a CSV in `landuse/engine_inputs/`.
2. Read the file in a properties class and add a switch key.
3. Implement the utility in a pure class, so the engine and a verifier share it.
4. Add a unit check that compares engine utilities with the estimation.
