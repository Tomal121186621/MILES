# Installation

## Requirements

| Software | Version | Used by |
|---|---|---|
| Python | 3.10 or later | population synthesis, data preparation, estimation, pipeline, reports |
| PyTorch | 2.0 or later | population synthesis |
| Java (JDK) | 21 | SILO, ORIOLE-Day, MATSim |
| Maven | 3.9 or later | building the Java engines |
| Biogeme | 3.3 | estimation of the choice models |
| Memory | 32 GB or more | SILO (24–28 GB heap), ORIOLE-Day and MATSim (32 GB heap) |

## 1. Get the code

```bash
git clone https://github.com/Tomal121186621/ORIOLE.git
cd ORIOLE
```

## 2. Python environments

=== "Population synthesis"

    ```bash
    python -m venv ~/.venvs/oriole
    ~/.venvs/oriole/bin/pip install -r population/cvae/requirements.txt
    ~/.venvs/oriole/bin/pip install geopandas shapely statsmodels openmatrix pyarrow
    ```

    `requirements.txt` holds numpy, pandas, torch, scipy, scikit-learn, matplotlib, openmatrix and pyarrow.

=== "Estimation"

    ```bash
    python -m venv ~/.venvs/biogeme
    ~/.venvs/biogeme/bin/pip install biogeme==3.3.5 pandas pyarrow matplotlib ipykernel
    ~/.venvs/biogeme/bin/python -m ipykernel install --user --name biogeme --display-name "Python (biogeme)"
    ```

## 3. The Java engines

=== "SILO"

    ORIOLE's land-use models are changes to the SILO engine
    ([msmobility/silo](https://github.com/msmobility/silo)), kept as a patch and new files in `landuse/java/`.

    ```bash
    git clone https://github.com/msmobility/silo.git && cd silo
    git checkout 3066ca9
    git apply ../ORIOLE/landuse/java/engine_uncommitted_changes.patch
    cp -R ../ORIOLE/landuse/java/engine/* .          # the new classes, at their package paths
    mvn compile -pl siloCore,extensions/schools,useCases/maryland
    ```

=== "ORIOLE-Day"

    The full Java source of the activity engine is in `activity/java/ABIT` (Maven project on the ABIT engine,
    MATSim 14, SILO core). The changes against the ABIT repository are also kept as a patch,
    `activity/java/ABIT_uncommitted_changes.patch`.

    ```bash
    cd activity/java/ABIT
    mvn compile
    ```

    Main class: `abm.RunAbitMarylandLos`. Runs use JDK 21 and the OMX native library of the ABIT resources
    (`-Djava.library.path=.../ABIT/src/main/resources/lib/macosx64`).

=== "MATSim runner"

    ```bash
    cd assignment/java/matsim-run
    mvn package                     # → target/baltimore-matsim-1.0.jar (MATSim 2024.0, roadpricing contrib)
    ```

    Main class: `de.umd.matsim.RunBaltimoreToll`. Transit mapping uses pt2matsim 24.4 (`assignment/java/transit_mapping`).

## 4. Data

ORIOLE ships no data. Download the public sources and request the two restricted ones as listed in
[Input data](../inputs-outputs/inputs.md).

!!! warning "Project paths"
    The scripts were written for the project's working folder and keep its absolute path in a constant at the top of
    each script (`ROOT` or `V`). Set it to your own folder before running a stage.
