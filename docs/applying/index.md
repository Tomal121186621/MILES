# Applying MILES

MILES answers "what if" questions by changing an input of one stage and running the chain from that stage on.

| To test… | Change | Run from |
|---|---|---|
| A toll or road charge | a MATSim road-pricing file | assignment |
| A new road or lane change | the road network | assignment (and skims, for longer-run effects) |
| Transit service | the GTFS feeds → transit schedule and skims | activities |
| Housing or job growth in a zone | land-use inputs: development capacity, job controls | land use |
| Income-based discounts | `toll.discount.factor`, `toll.discount.threshold` | assignment |

<div class="grid cards" markdown>

-   :material-flask: **[Scenarios](scenarios.md)**

    How to set up and run a scenario, and how to read the results.

-   :material-highway: **[Case study: I-695 pricing](i695.md)**

    Toll designs on the Baltimore Beltway.

</div>
