# Get started

ORIOLE runs as five stages. Each stage can be run on its own from the outputs of the previous one, or the whole chain
can be driven by the pipeline.

<div class="grid cards" markdown>

-   :material-download: **[Installation](installation.md)**

    Python environments, Java 21, Maven and the three engines.

-   :material-file-tree: **[Repository layout](repository.md)**

    Where each component lives.

-   :material-play-circle: **[Run the chain](running.md)**

    The commands, stage by stage.

-   :material-timer-sand: **[Runtime and storage](runtime.md)**

    How long each stage takes and how much memory and disk it needs.

</div>

## The chain in one view

```mermaid
flowchart LR
  A[ACS PUMS<br/>census blocks] --> P[Synthetic population<br/>CVAE, 2016]
  P --> L[Land use<br/>SILO, 2016 → 2024]
  L --> S[School location<br/>every year]
  S --> D[Activities<br/>ORIOLE-Day, 2024]
  K[(Fixed skims<br/>car, transit)] --> L
  K --> D
  D --> X[Plans converter]
  X --> M[Traffic assignment<br/>MATSim, 2024]
  M --> V[Link volumes<br/>travel times, boardings]
```
