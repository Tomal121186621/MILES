# About MILES

**MILES** stands for **Maryland Integrated Land-use and Everyday-travel Simulator**: it follows Maryland's households
from where they live and work to the miles they travel each day. It is an agent-based modelling platform that
links a deep-generative synthetic population, the SILO land-use model, the MILES-Day activity model and MATSim
traffic assignment for the Baltimore region and the state of Maryland.

## Where the parts come from

| Component | Based on | What MILES adds |
|---|---|---|
| Synthetic population | Conditional variational autoencoder (Borysov et al., 2019) | PUMA embedding and size conditioning, PUMA marginal loss, income within band, logical repair, zone placement, workplace assignment |
| Land use | SILO engine | Residential location, car ownership, workplace and school models estimated for the region; calibration and out-of-sample test |
| Activities | ABIT engine; TASHA scheduling | MILES-Day: survey distributions conditioned on the day, estimated destination, stop, outing, return-home and mode models; household car allocation; joint-tour representative |
| Traffic | MATSim | OpenStreetMap network with fixed speed and capacity rules; regional transit; income-based value of time; tolls |

## Principles

- **Estimated, not tuned.** Behavioural models are maximum-likelihood estimates on microdata.
- **Tested on unseen data.** Survey hold-out half, out-of-sample years, independent 2024 benchmarks.
- **Compared with standard methods** under the same inputs and measures.
- **Residents on the roads.** Trucks, commercial vehicles and through traffic are outside the model.

<div class="grid cards" markdown>
- :material-account-group: **[Team](team.md)**
- :material-file-document-multiple: **[Publications](publications.md)**
- :material-book-alphabet: **[Glossary](glossary.md)**
- :material-bookshelf: **[References](references.md)**
</div>
