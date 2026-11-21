# SILO Java (engine)

Base: SILO (https://github.com/msmobility/silo.git), branch `baltimore-2026`, commit 3066ca9. The Baltimore changes are not committed
upstream; they are given here in two forms.

## Sources
- `src/`: every changed or new Java file of the adopted setup, with its package path, and the pom.xml files.
  New files: ReslocTwoLevel (two-level residential location: PUMA, then dwelling), SchoolChoiceMd (school location), StructuralVacancy,
  CarOwnershipRespec, DriversLicenseModelMd, ReslocRespecUtility, ReslocRespecVerify.
  Changed files: ReslocModel, ReslocProperties, HousingStrategyMstm, MovesModelMd, RealEstateDataManagerMstm, SchoolDataMd,
  EducationModelMd, PersonMstm, CarOwnershipModelMd, ModelBuilderMstm (useCases/maryland); HouseholdDataManagerImpl,
  InOutMigrationImpl, MovesProperties, RealEstateProperties, PricingModelImpl, Simulator, JobDataManagerImpl, JobDataProperties
  (siloCore).
- `silo_changes.patch`: `git diff HEAD` of the changed tracked files (the new files are the copies in `src/`).

Rebuild: check out commit 3066ca9, apply the patch, add the new files from `src/`, then
`mvn compile -pl siloCore,extensions/schools,useCases/maryland`. `run/run_silo.sh` expects the checkout in `WORKSPACE/2_silo/engine`
(or set `SILO_ENGINE`).

The input file names written in the Java sources are only defaults; the adopted setup sets every file by a property
(`run/adopted_settings.sh`), with the names used in `engine_inputs/`.

## Switches
Two switches were added for sensitivity tests and are off by default (`false` in ReslocTwoLevel.java and in `run/adopted_settings.sh`):
- `resloc.race.share.fixed2016`: hold the own-race share of every PUMA at its value of the first simulated year (robustness check).
- `resloc.county.vacancy.factor`: an extra county vacancy factor in the PUMA choice (tested and not adopted).
