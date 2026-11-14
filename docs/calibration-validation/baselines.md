# Comparison with standard methods

Each stage is run against an established alternative. Every variant uses the same inputs, targets, hold-out data and
measures; baselines are calibrated with the same levers; no variant is fitted to traffic counts.

## Population synthesis: CVAE against IPF, IPU and weighted sampling

Baselines: iterative proportional fitting with a weighted draw, iterative proportional updating (PopulationSim) and
weighted sampling of the training households, all on the same training records and controls, five draws each.

- On fit to the held-out records, the classic methods are better: IPU reaches the noise level of the held-out data
  on one-way distributions.
- Reweighting methods copy whole training households, so they cannot produce a combination that is absent from the
  sample. The CVAE generates **62 % of the held-out combinations that the training data lack**, and copies fewer
  households than a fresh sample shares with the training data (11 % against 22 %).

The CVAE's gain is variety beyond the sample, not closer fit to it.

## Land use: against the original SILO Maryland model

Both models are calibrated with the same procedure and tested on 2021–2024.

| Measure | Original | ORIOLE |
|---|---:|---:|
| Out-of-sample cells within 5 pp | 86.8 % | **94.5 %** |
| Mover flows between counties, correlation with ACS | 0.625 | **0.946** |
| Movers staying in their county, share of observed | 0.260 | **0.986** |
| Mean travel time to work, ratio to ACS | 1.557 | **0.974** |

The gap of the original model lies in young adults living with their parents, age, cars, employment, household size
and income.

## Activities: against the original set-up and a standard tour-based model

- ORIOLE-Day beats both baselines on 58–73 % of the error measures and loses on 2–21 %, in all three survey settings;
  its mean normalised error is less than half of theirs.
- The gain comes mainly from the TASHA-type scheduler (durations, start times, school and work activity) and from the
  return-home and workplace-outing models: adding TASHA-type generation cuts the mean normalised error from 9.9 to
  6.8 on the estimation half, and the return-home and outing models bring it to 4.0.
- On the 2024 external data no variant is clearly best.

## Assignment: against the original activity demand

| Measure | Original demand | ORIOLE |
|---|---:|---:|
| %RMSE, all count stations | 86.5 | **58.5** |
| Model / count | 0.617 | **0.813** |
| I-695 model / count | 0.607 | **0.906** |
| Vehicle-miles, model / observed | 0.614 | **0.791** |
| Hourly flows with GEH < 5 | 4 % | **14 %** |
| Mean screenline deviation | 0.246 | **0.116** |

The original demand is closer on transit boardings and on the trip-length distribution of the survey.
