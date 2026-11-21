# Calibration

Calibration is confined to the demographic levers of the land-use model. The calibration window is **2017–2020**;
the years **2021–2024** are kept for the out-of-sample test. Traffic counts play no role.

## Demographic levers

Five levers scale the event rates of SILO: births, marriages, divorces, the shift \(a_m\) of the moving decision and
leaving the parental home. Targets come from the Census components of change and the ACS PUMS. In each round the
model is run from 2016 to 2020 and every lever is updated by the damped ratio

\[
\theta^{(k+1)} = \theta^{(k)} \big(y^{\text{obs}} / y^{\text{model}}\big)^{\omega},
\]

where \(y\) are the window means of 2017–2020 and \(\omega = 0.8\) is a damping exponent.

| Lever | Model / target, final round |
|---|---:|
| Births | 1.001 |
| Marriages | 1.001 |
| Divorces | 0.999 |
| Leaving home | 0.988 |
| Moves<sup>1</sup> | 1.005 |

<p class='estnote'>1. The shift \(a_m\) was calibrated last, with the two-level residential location model, against the same target (12.39 % of persons aged one and over moved in the last 12 months, mean of 2017–2020): after three rounds it is 1.111. In that run leaving home (0.988) and construction (1.000) were on target and their levers were not changed.</p>

The levers are then frozen, and the model is run from 2016 to 2024.

## District of Columbia workplace term

The travel survey has more Maryland workers commuting to the District than the ACS, and the estimated workplace model
reproduces the survey. The District term is not calibrated: its estimate (0.83) is used without a shift, so the
District share of Maryland workers remains a test against the ACS.

## Not calibrated

- MAST is applied without frequency factors or constant adjustments.
- None of the other choice models is calibrated. The Baltimore City term of car ownership is estimated with the other
  coefficients.
- The choice-based weights of the work tour mode choice are part of its estimator.
- The road network is not calibrated to counts.
