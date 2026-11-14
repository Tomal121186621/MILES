# Calibration

Calibration is confined to three groups of land-use and workplace parameters. The calibration window is
**2017–2020**; the years **2021–2024** are kept for the out-of-sample test. Traffic counts play no role.

## Demographic levers

Five levers scale the event rates of SILO: births, marriages, divorces, the shift \(a_m\) of the moving decision and
leaving the parental home. Targets come from the Census components of change and the ACS PUMS. In each round the
model is run from 2016 to 2020 and every lever is updated by the damped ratio

\[
\theta^{(k+1)} = \theta^{(k)} \big(y^{\text{obs}} / y^{\text{model}}\big)^{\omega},
\]

where \(y\) are the window means of 2017–2020 and \(\omega\) is a damping exponent between 0.5 and 1.0.

| Lever | Model / target, final round |
|---|---:|
| Births | 1.002 |
| Marriages | 1.000 |
| Divorces | 1.000 |
| Moves | 1.000 |
| Leaving home | 0.988 |

The levers are then frozen, and the model is run from 2016 to 2024 with five seeds.

## Car ownership

The county constants of the car-ownership model are updated by the damped log-ratio of observed to modelled shares.
In the final round every county × car-ownership cell is within 5 percentage points of the ACS.

## District of Columbia workplace term

The travel survey has more Maryland workers commuting to the District than the ACS: the estimated model gives 13.1 %
against 9.8 %. For application, the District workplace term is shifted by −0.387 (from 1.097 to 0.710), so that
9.82 % of Maryland-resident base-year workers work in the District, the ACS 2016–2020 share. This share is therefore
not a test of the model.

## Not calibrated

- ORIOLE-Day is applied without frequency factors or constant adjustments.
- None of the other choice models is calibrated.
- The choice-based weights of the work tour mode choice are part of its estimator.
- The road network is not calibrated to counts.
