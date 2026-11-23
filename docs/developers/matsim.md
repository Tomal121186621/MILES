# MATSim runner

`assignment/engine/matsim-run` is a Maven project on MATSim 2024.0 with the road-pricing contrib.

| Class | Role |
|---|---|
| `de.umd.matsim.RunBaltimoreToll` | main runner: configuration, scoring, value of time, tolls |
| `DistanceConstrainedPermissibleModes` | removes walk and bike beyond a maximum distance when mode choice is on |
| `RunBaltimore` | earlier runner without tolls |

```bash
java -Xmx32g -Dseed=1 -Dthreads=12 -Dincome.vot.form=usdot -cp baltimore-matsim-1.0.jar \
  de.umd.matsim.RunBaltimoreToll network.xml.gz plans.xml.gz transitSchedule.xml.gz transitVehicles.xml.gz out/ 100 0.1 0.178 roadpricing.xml
```

## Built-in settings

| Setting | Value |
|---|---|
| Simulation | QSim 0–36 h, car as main mode, stuck time 120 s |
| Replanning | re-route 0.15, departure-time mutation 0.10 (±30 min), plan selection the rest; plan memory 5 |
| Modes | fixed from DAYMAP (Daily Activity Model for Agent Plans); ride routed on the car network; walk and bike teleported (beeline × 1.3) |
| Transit | SwissRailRaptor; search radius 4,000 m |
| Scoring | performing 0.78 utils/h; per-person marginal utility of money = 0.78 / value of time |
| Value of time | `usdot`: 0.5 × household income / 2,080 h, income at least \$5,000 |
| Monetary distance rate | car and ride \$0.075/km |
| Activities | duration bins per type; shops open 8:00–20:00 |
| Coordinate system | EPSG:26985 |

## Tolls

Toll schemes are MATSim road-pricing files passed as the last argument, for example
`assignment/network/roadpricing_HARB_2024.xml` (\$3.00 per crossing of the two harbour tunnels).
`toll.discount.factor` and `toll.discount.threshold` give income-based discounts.
