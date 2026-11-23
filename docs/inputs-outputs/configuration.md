# Configuration

Each engine reads one properties file. The keys below are the ones that switch on MILES's models; the values are
those of the final runs. The SILO settings of the final runs are collected in `landuse/run/adopted_settings.sh`, and
`miles landuse …` sets the model switches for you.

## Land use (SILO)

Written by `landuse/run/write_properties.py <scenario> <start> <end> [skim_years] [seed] [spec]`.

=== "General"

    | Key | Value |
    |---|---|
    | `base.year`, `start.year`, `end.year` | 2016, 2016, 2024 |
    | `random.seed` | 1 to 5 |
    | `number.of.threads` | 12 |
    | `travel.time` | `SKIM` (fixed skims) |
    | `auto.peak.sov.skim.2016` | `auto_peak_time.csv.gz` |
    | `transit.peak.time.2016` | `transit_peak_time.csv.gz` |
    | `household.file.ascii` … `job.file.ascii` | the 2016 base `hh`, `pp`, `dd`, `jj` |

=== "Residential location"

    | Key | Value |
    |---|---|
    | `resloc.twolevel` | `true` (PUMA, then dwelling) |
    | `resloc.twolevel.puma.coefficients` | `input/residential_puma_coefficients.csv` |
    | `resloc.twolevel.dwelling.coefficients` | `input/residential_dwelling_coefficients.csv` |
    | `resloc.twolevel.puma.zone.file`, `resloc.twolevel.mig.zone.file` | zones of each PUMA and migration PUMA |
    | `resloc.twolevel.zone.attributes.file`, `resloc.twolevel.zone.core.file` | zone attributes; DC and Baltimore City zones |
    | `resloc.twolevel.puma.adjacency.file` | PUMA adjacency |
    | `resloc.marketsize`, `resloc.turnover.file` | `stock_turnover`; turnover rate by PUMA |
    | `resloc.puma.vacancy.availability` | `true` (PUMA weight scaled by its vacancy rate relative to 2016) |
    | `resloc.race.share.fixed2016` | `false` (own-race shares recomputed every year) |
    | `population.control.until.no.vacancy` | `true` |
    | `resloc.move.duration` | −0.982 |
    | `resloc.iv.dwelling.sample` | 200 |

=== "Car ownership"

    | Key | Value |
    |---|---|
    | `car.ownership.coefficients.file` | `input/car_ownership_estimated_coefficients.csv` |
    | `car.ownership.region.constants.file` | `input/car_ownership_county_constants.csv` (the estimated Baltimore City term; 0 elsewhere) |

=== "Jobs and schools"

    | Key | Value |
    |---|---|
    | `job.choice.coefficients.file` | `input/workplace_choice_coefficients.csv` (24 terms; District term as estimated) |
    | `job.choice.size` | `jobs` (all job types weighted equally) |
    | `job.change.rate` | 0.252 |
    | `job.control.total` | QCEW-based job controls |
    | `employment.types` | `RET,OFF,IND,OTH` |
    | `school.choice.coef.k8`, `.hs`, `.college` | `input/school_location_coefficients_{k8,hs,college}.csv` |
    | `school.seat.release` | `true` (seat released when a student leaves school or the population) |

=== "Demography and calibration"

    | Key | Calibrated value |
    |---|---|
    | `demographics.local.birth.rate.adjuster` | 2.1724 |
    | `demographics.local.marriage.rate.adjuster` | 1.3436 |
    | `demographics.local.divorce.rate.adjuster` | 0.6867 |
    | `demographics.local.leave.parents.adjuster` | 2.7775 |
    | `move.or.not.binomial.log.shift.parameter` | 1.1114 |
    | `construct.dwelling.demand.scaler` | 0.2871 |
    | `marriage.partner.distance.decay` | 0.0462 |
    | `population.control.total` | `region` (county controls) |

    The levers are kept in `landuse/calibration/calibrated_parameters.json`.

## Activities (DAYMAP)

Properties of DAYMAP (Daily Activity Model for Agent Plans), written by `activity/write_properties.py <name> <silo_scenario> <year> [sample] [skims]`; the switches of the
coefficient set (`activity/parameters/run_params.csv`) are appended.

| Key | Value | Meaning |
|---|---|---|
| `tasha.generation` | `true` | survey-distribution generation and scheduling |
| `tasha.dir` | `coef/tasha` | distributions, scheduler parameters, return-home, outing and transit-leg models |
| `dest.choice.model` | `mnl` | estimated destination and stop models |
| `dest.mnl.file` | `dest_choice_mnl.csv` | their coefficients |
| `mode.choice.model` | `tour_nl` | tour mode choice, nested or multinomial |
| `mc.coef.file` | `tour_mode_choice.csv` | its coefficients by segment |
| `mc.vot.share` | 0.5 | value of time = 0.5 × hourly household income |
| `mc.car.allocation` | `tasha` | household car allocation |
| `mc.joint.rule`, `mc.joint.model` | `representative`, `group` | joint-tour mode |
| `mc.park.share.file` | `parking_paid_share.csv` | paid-parking share by area |
| `workplace.silo` | `true` | workplaces from the land-use model |
| `sample.fraction` | 0.1 | share of households simulated |
| `number.of.threads` | 6 | |
| `auto.toll` | 0 | |

The seed is set with `-Dabit.seed=N`.

## Assignment (MATSim)

The runner builds its configuration in code; each run writes the resolved `output_config.xml`.

```bash
java -Xmx32g -Dseed=1 -Dthreads=12 -Dincome.vot.form=usdot -cp baltimore-matsim-1.0.jar \
     de.umd.matsim.RunBaltimoreToll <network> <plans> <schedule> <vehicles> <outDir> <iterations> <flowCap> [storageCap] [tollFile|NONE]
```

| System property | Default | Meaning |
|---|---|---|
| `seed`, `threads` | 4711, 8 | random seed, threads |
| `modechoice` | false | modes fixed from the activity model |
| `reroute.weight`, `tam.weight`, `tam.range` | 0.15, 0.10, 1800 s | re-routing and departure-time mutation |
| `income.vot.form` | `power` (`usdot` in the runs) | value of time per person |
| `vot.share`, `vot.hours`, `vot.income.floor` | 0.5, 2080, 5000 | value of time = 0.5 × income / 2,080, income at least \$5,000 |
| `asc.car`, `asc.pt`, `asc.ride`, `asc.walk`, `asc.bike` | | mode constants of the scoring |
| `walk.maxdist`, `bike.maxdist` | 2000 m, 5000 m | |
| `trucks` | false | optional truck layer |

Transit settings of the final runs: transfer penalty `-Dpt.lineswitch=-0.13` (about 10 in-vehicle minutes) and
transfer walks up to `-Dpt.beeline=300` m, set by `pipeline/run_chain.py` with `MATSIM_PT=berlin MATSIM_PT_LIT=1`.

Chain settings: flow capacity = sample (0.1), storage capacity = sample^0.75 (0.178), 100 iterations.
