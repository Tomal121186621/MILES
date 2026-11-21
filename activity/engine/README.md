# MAST Java source (ABIT code base)
Repo: `VAE-SILO-MITO-MATSIM/ABIT` (origin https://github.com/msmobility/abit.git), branch `maryland-2026`, HEAD 0af0df5.
The last changes are uncommitted in the working tree: MarylandDestinationChoice, MarylandTashaGenerator, MarylandTourNestedModeChoice (package `abm.models.maryland`).
- `ABIT/src/main/java`: the full source tree as used (including those changes) and `ABIT/pom.xml`; resources (22 MB of input data) are not copied.
- `abit_changes.patch`: `git diff HEAD` of the three files.
Build: `mvn compile` in ABIT, or javac into `WORKSPACE/3_abit/classes` as pipeline/run_chain.py `compile_abit` does; main class `abm.RunAbitMarylandLos`.
