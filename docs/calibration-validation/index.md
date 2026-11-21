# Calibration and validation

<div class="grid cards" markdown>

-   :material-function-variant: **[Estimation](estimation.md)**

    27 choice models: sample, fit and hold-out of each.

-   :material-table-large: **[Estimated models](estimates/index.md)**

    The full results of all 27 models: coefficients, robust standard errors, p-values.

-   :material-tune: **[Calibration](calibration.md)**

    The demographic levers of the land-use model, the only calibrated parameters.

-   :material-check-all: **[Validation](validation/index.md)**

    Every stage against data it never saw.

-   :material-map-marker-radius: **[Validation map](validation/map.md)**

    Interactive map of every count station against the simulated traffic.

-   :material-scale-balance: **[Against standard methods](baselines.md)**

    CVAE vs IPF and IPU, against the original land-use and activity models.

-   :material-alert-circle-outline: **[Known limitations](limitations.md)**

    What the model does not do, stated plainly.

</div>

## Headline results

| Stage | Test | Result |
|---|---|---|
| Synthetic population | ACS 2014–18, Maryland | every attribute class within 3.9 pp |
| Land use | out of sample, 2021–24 | commute flows correlate 0.995 with the ACS; household size and cars within 2.1 pp in 2024 |
| Activities | survey hold-out half | +1.2 % activities, start times within 2 pp per hour |
| Assignment | 2,308 count stations, 2024 | 0.77 of all counted vehicles carried by residents alone; R² = 0.89 |

The land-use, activity and traffic results are updated after the final runs of the chain with the current models.
