# SILO Java (engine)
Repo: `VAE-SILO-MITO-MATSIM/Validation_2026/2_silo/engine` (origin https://github.com/msmobility/silo.git), branch `baltimore-2026`, base commit 3066ca9.
The re-specification changes are NOT committed; they are in the working tree on top of 3066ca9:
- `engine/` here: the changed and new files with their package paths (CarOwnershipModelMd, CarOwnershipRespec, ReslocModel, ReslocProperties, ReslocRespecUtility, ReslocRespecVerify, JobDataManagerImpl, JobDataProperties) and the pom.xml files.
- `engine_uncommitted_changes.patch`: `git diff HEAD` of the modified tracked files (new files are the copies in `engine/`).
Rebuild: take commit 3066ca9, apply the patch, add the new files, `mvn compile -pl siloCore,extensions/schools,useCases/maryland` (as used by run/run_silo.sh).
The sibling checkout `2_silo/engine_rts` (branch jobchoice-rts) is an earlier variant and was not used for the final runs.
