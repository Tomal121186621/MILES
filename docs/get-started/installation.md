# Installation

## Requirements

| Software | Version | Used by |
|---|---|---|
| Python | 3.10 or later | every step |
| Java (JDK) | 21 | SILO, TERP-Day, MATSim |
| Maven | 3.9 or later | building the Java engines |
| Memory | 32 GB or more | SILO (24–28 GB heap), TERP-Day (13 GB), MATSim (32 GB) |

## 1. Get the code and the `terp` command

```bash
git clone https://github.com/Tomal121186621/TERP.git
cd TERP
python -m venv .venv && source .venv/bin/activate
pip install -e ".[population,docs]"
terp --help
```

`pip install -e .` installs the `terp` command from your clone, so it always runs the code you have checked out.

## 2. Configure

```bash
cp terp.example.toml terp.toml
```

Set `paths.workspace` to the folder that holds the data and receives the runs, and the locations of the external
checkouts (ABIT resources, MATSim inputs). Then check:

```bash
terp config
```

## 3. Estimation environment

```bash
python -m venv ~/.venvs/biogeme
~/.venvs/biogeme/bin/pip install biogeme==3.3.5 pandas pyarrow matplotlib ipykernel nbformat
~/.venvs/biogeme/bin/python -m ipykernel install --user --name biogeme --display-name "Python (biogeme)"
```

Set `python.biogeme` in `terp.toml` to this interpreter.

## 4. The Java engines

=== "SILO"

    ```bash
    git clone https://github.com/msmobility/silo.git && cd silo
    git checkout 3066ca9
    git apply ../TERP/landuse/engine/silo_changes.patch
    cp -R ../TERP/landuse/engine/src/* .
    mvn compile -pl siloCore,extensions/schools,useCases/maryland
    ```

=== "TERP-Day"

    ```bash
    cd activity/engine/ABIT
    mvn compile                     # main class abm.RunAbitMarylandLos
    ```

    The engine reads its zone resources from the ABIT checkout set as `paths.abit_home`.

=== "MATSim runner"

    ```bash
    cd assignment/engine/matsim-run
    mvn package                     # → target/baltimore-matsim-1.0.jar (MATSim 2024.0)
    ```

## 5. Data

TERP ships no data. Download the public sources and request the restricted ones as listed in
[Input data](../inputs-outputs/inputs.md), into the workspace. After the land-use coefficients are written, copy the
engine input files into the workspace with:

```bash
terp sync
```
