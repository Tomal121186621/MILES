# Developers

ORIOLE combines Python stages with three Java engines. This section documents the code: which classes and scripts
ORIOLE adds or changes, how they are wired, and how to extend them.

<div class="grid cards" markdown>

-   :material-language-python: **[Population code](population.md)**

    The CVAE library and the post-processing steps.

-   :material-language-java: **[SILO engine changes](silo.md)**

    Residential location, car ownership and workplace choice in the engine.

-   :material-language-java: **[ORIOLE-Day engine](activity.md)**

    The `abm.models.maryland` package: generation, destinations, mode choice.

-   :material-language-java: **[MATSim runner](matsim.md)**

    `RunBaltimoreToll`: scoring, value of time, tolls.

-   :material-pipe: **[Pipeline](pipeline.md)**

    Orchestration, plans converter, skims and accessibility.

-   :material-function-variant: **[Estimation package](estimation-package.md)**

    One folder and notebook per model, with Biogeme.

</div>

## Conventions

- **Coordinate system:** EPSG:26985.
- **Skims:** gzipped CSV `FROM,TO,VALUE`.
- **Coefficients** live in CSV files read by the engines; every file is written by a script from the estimation
  results, never by hand.
- **Unit checks** compare engine utilities with Biogeme's $X\beta$ (`landuse/checks/check_*.py`,
  `activity/checks/check_engine_utilities.py`).
- **Paths:** each script keeps the project root in a constant at its top (`ROOT` or `V`).
