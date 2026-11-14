# Calibration and validation

<div class="grid cards" markdown>

-   :material-function-variant: **[Estimation](estimation.md)**

    28 choice models: sample, fit and hold-out of each.

-   :material-tune: **[Calibration](calibration.md)**

    The few land-use parameters that are calibrated, and on what.

-   :material-check-all: **[Validation](validation.md)**

    Every stage against data it never saw.

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
