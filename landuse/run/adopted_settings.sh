#!/bin/bash
# Adopted SILO setup (used for the final runs). Source this file, then run the seeds with
#   OOS_SPEC=respec OOS_SET="$ADOPTED_SET" SILO_MICRODATA=v8 python landuse/run/run_seeds.py <n_seeds> [parallel]
# (and CAL_SET="$ADOPTED_SET" for landuse/calibration/calibrate_moveshift.py).
# Contents: two-level residential location (PUMA, then dwelling; market size = dwelling stock x turnover, PUMA vacancy rule on,
# county vacancy factor off, own-race share of the PUMA updated every year, exact live vacancies, population control until no vacancy),
# school location with seat release, workplace choice with 24 terms (job.choice.size = jobs), car ownership with persons-16+ dummies
# and the Baltimore City term, structural vacancy 2016, end-of-year population control, pricing after the control, gross in-migration.
# Calibrated adjusters (move shift recalibrated for the two-level model): landuse/calibration/calibrated_parameters.json.
# The files named below are the ones in landuse/engine_inputs; copy them to WORKSPACE/2_silo/input. The population and job control
# totals (input/assumptions/*_v8.csv) and the base-year microdata (SILO_MICRODATA=v8) are built by landuse/inputs/base_year.
# The engine must be built with landuse/engine (patch and sources); SILO_CP_PREPEND is not needed then.
export SILO_MICRODATA=v8
ADOPTED_SET="resloc.region.vacancy.availability=true;drivers.license.targets.file=input/drivers_license_targets_md.csv"
ADOPTED_SET="$ADOPTED_SET;car.ownership.coefficients.file=input/car_ownership_estimated_coefficients.csv;car.ownership.region.constants.file=input/car_ownership_county_constants.csv"
ADOPTED_SET="$ADOPTED_SET;population.control.total.by.region.file=input/assumptions/populationControlTotalByRegion_v8.csv;job.control.total=input/assumptions/jobControlTotals_qcew_v8.csv"
ADOPTED_SET="$ADOPTED_SET;structural.vacancy.file=input/structural_vacancy_2016.csv;population.control.end.of.year.only=true;pricing.after.population.control=true;population.control.inmigration.rate.file=input/inmigration_rate_2014_18.csv"
ADOPTED_SET="$ADOPTED_SET;resloc.puma.vacancy.availability=true;resloc.county.vacancy.factor=false;resloc.race.share.fixed2016=false;population.control.until.no.vacancy=true;resloc.marketsize=stock_turnover;resloc.turnover.file=input/residential_puma_turnover.csv"
ADOPTED_SET="$ADOPTED_SET;resloc.twolevel.puma.zone.file=input/residential_puma_zones.csv;resloc.twolevel.mig.zone.file=input/residential_migration_puma_zones.csv;resloc.twolevel.zone.attributes.file=input/residential_twolevel_zone_attributes.csv;resloc.twolevel.puma.adjacency.file=input/residential_puma_adjacency.csv"
ADOPTED_SET="$ADOPTED_SET;resloc.twolevel.puma.coefficients=input/residential_puma_coefficients.csv;resloc.twolevel.dwelling.coefficients=input/residential_dwelling_coefficients.csv;resloc.twolevel.zone.core.file=input/residential_zone_core_city.csv"
ADOPTED_SET="$ADOPTED_SET;resloc.twolevel=true;job.choice.coefficients.file=input/workplace_choice_coefficients.csv;job.choice.size=jobs"
# school location: the engine's switch value is respec1118 (a name in SchoolDataMd.java); coefficient files by property
ADOPTED_SET="$ADOPTED_SET;school.choice.model=respec1118;school.seat.release=true;school.choice.coef.k8=input/school_location_coefficients_k8.csv;school.choice.coef.hs=input/school_location_coefficients_hs.csv;school.choice.coef.college=input/school_location_coefficients_college.csv"
# school location data files (written by estimation/development/other_locations/l11_export_silo.py; not in engine_inputs)
ADOPTED_SET="$ADOPTED_SET;school.choice.records.file=input/school_location_records.csv;school.choice.inboundary.file=input/school_location_inboundary.csv;school.choice.zone.attributes.file=input/school_location_zone_attributes.csv"
export ADOPTED_SET
