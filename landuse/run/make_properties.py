#!/usr/bin/env python3
"""Write a SILO run configuration for the rebuilt engine and set up the run base directory (symlinks to the inputs).
Usage: make_properties.py <scenario_name> <start_year> <end_year> [skim_years=-1] [seed=1] [spec=record|respec]
spec = respec (2026-11-09, author approval): the re-specified models of side_experiments/respec_2026-11 (residential location,
car ownership, workplace choice; coefficient files *_respec.csv); record (default) writes the configuration unchanged.
Produces run/base/ (base.directory with input/, microData/ links) and run/<scenario_name>.properties.
All values are observed-data inputs built by 2_silo/input_build and 1_vae; model parameters start at the open-source
defaults (or the earlier study's values where the notes give them) and are then set by the calibration loop."""
import os, sys
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; S = f"{V}/2_silo"; R = f"{S}/run"; B = f"{R}/base"
name, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); skim_years = sys.argv[4] if len(sys.argv) > 4 else "-1"; seed = sys.argv[5] if len(sys.argv) > 5 else "1"
spec = sys.argv[6] if len(sys.argv) > 6 else "record"; assert spec in ("record", "respec"), spec
os.makedirs(B, exist_ok=True)
# 2026-10-28: run/base/microData points to run/base_v4/microData (workplaces with rts3; earlier base_v3, link kept as
# run/base/microData_link_base_v3_until_2026-10-28) (the consistent 2016 base: pp_2016_v3, jj_2016_v3, hh_2016_v2,
# dd_2016); the earlier link to input/microData is kept as run/base/microData_link_input_until_2026-10-28
for link, target in [("input", f"{S}/input"), ("microData", f"{R}/base_v4/microData"), ("skims", f"{S}/input/skims")]:
    p = f"{B}/{link}"
    if not os.path.exists(p): os.symlink(target, p)
shp = f"{S}/input/zones"
if not os.path.exists(shp + ".shp"):
    src = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/ABIT/input/mito_los/Zonal/SMZ_RMZ_02152011inMSTM_EPSG26918"
    for ext in ["shp", "shx", "dbf", "prj"]: os.symlink(f"{src}.{ext}", f"{shp}.{ext}")
if not os.path.exists(f"{S}/input/crimeIndex.csv"): os.symlink(f"{S}/input/crimeIndex_mstm.csv", f"{S}/input/crimeIndex.csv")
P = f"""# SILO run configuration, Baltimore 2026 rebuild (written by make_properties.py)
base.directory           = {B}/
scenario.name            = {name}
base.year                = 2016
start.year               = {y0}
end.year                 = {y1}
random.seed              = {seed}
number.of.threads        = 12
track.time               = true
print.out.sp.final       = true
scale.factor             = 1.0
dwelling.quality.levels.distinguished = 4
# 2026-10-27: rounded quartiles of 2016 Maryland household income (2016 $); before 20000,40000,60000 (Munich default)
income.brackets.hh.types = 40000,75000,125000
create.presto.summary.file = false
summarize.hh.near.selected.metro.stp = false
run.synth.pop.generator  = false
run.silo.model           = true

# geography and base-year population (corrected synthetic population, stage 1)
zonal.data.file          = input/zoneSystem.csv
zones.shapefile          = input/zones.shp
crime.index              = input/crimeIndex.csv
household.file.ascii     = microData/hh
person.file.ascii        = microData/pp
dwelling.file.ascii      = microData/dd
job.file.ascii           = microData/jj
household.final.file.ascii = microData/futureYears/hh
person.final.file.ascii    = microData/futureYears/pp
dwelling.final.file.ascii  = microData/futureYears/dd
job.final.file.ascii       = microData/futureYears/jj
# schools (stage 2b): input/schools_<startYear>.csv from 2_silo/schools (build_schools.py, assign_students.py); the
# search tree envelope of the schools extension comes from the zone shapefile; final file with the end-year occupancy
school.file.ascii        = input/schools
school.final.file.ascii  = microData/futureYears/schools
school.shapefile         = input/zones.shp

# travel times: csv.gz skims (FROM,TO,VALUE), from the activity model's 1,588-zone skims; refreshed in the loop years
transport.model          = NONE
travel.time              = SKIM
skim.years               = {skim_years}
# the engine prepends base.directory + skims/ to the skim file names (run/base/skims -> input/skims); no inline comments in Java properties
auto.peak.sov.skim.2016  = auto_peak_time.csv.gz
transit.peak.time.2016   = transit_peak_time.csv.gz
auto.peak.sov.skim.matrix.name = HOVTime
transit.peak.time.matrix.name  = CheapJrnyTime
skims.factor.car         = 1.0
skims.factor.transit     = 1.0
auto.accessibility.alpha = 1.2
auto.accessibility.beta  = -0.3
transit.accessibility.a  = 1.2
transit.accessibility.b  = -0.3
auto.operating.costs     = 8.4

# jobs: observed control totals by zone, type and year (LODES 2016-2023, QCEW 2024-2026)
employment.types         = RET,OFF,IND,OTH
job.forecast.method      = interpolation
# 2026-10-28 (author decision): job totals from QCEW county growth x the state JOLTS openings rate (input_build/build_job_controls_qcew.py)
job.control.total        = input/assumptions/jobControlTotals_qcew.csv
interpol.empl.forecast   = interpolatedEmploymentForecast
vacancy.rate.by.type     = 0.01,0.03,0.05,0.04,0.03
# vacant-job choice: impedance by car travel time that reproduces the base-year commute-time distribution (input_build/build_job_search_impedance.py)
job.search.impedance.file = input/job_search_impedance.csv
# 2026-10-28: workplace choice estimated on the RTS 2017/18 (jobchoice/ESTIMATION_REPORT_RTS.md), with the ACS-anchored DC term;
# the LODES model of 2026-10-26 (job_choice_coefficients.csv, job.choice.model = lodes) is kept but not used
job.choice.model = rts3
job.choice.coefficients.file = input/job_choice_coefficients_rts3_dcacs.csv
job.choice.zone.attributes.file = input/job_choice_zone_attributes_rts3.csv
job.choice.zones.file = input/job_choice_zones_rts.csv
job.choice.logsum.dir = input/job_choice_logsums_rts
# 2026-10-28 (author decision): job-to-job change at the JOLTS Maryland quits rate 2017-19 (series JTS000000240000000QUR, monthly
# mean 2.10 % = 25.2 % a year; an upper bound, quits include exits from employment), independent of the commute; the new job is
# chosen from scratch with the workplace model. Replaces the commute-driven search of 2026-10-26/27 (job.change.base/gamma/tref/
# offers/vacancy.ref).
job.change.rate = 0.252
demographics.labor.participation.adjuster = 1.0
# 2026-10-28 (author decision): local marriage market, partner weight exp(-decay x car time between the homes); an ASSUMPTION, not
# estimated or tuned: ln 2 / 15 = 0.0462 per min puts half of the weight within 15 minutes
marriage.partner.distance.decay = 0.0462
# 2026-10-28 (author decision): end-of-year employment alignment pass (EmploymentModelImpl.alignEndOfYear): after the year's events the
# gap per age x sex against the ACS rates is closed with the same hire / quit draw; hires choose with the workplace model
employment.alignment.endofyear = true
# multipliers on the employment rates by age band and sex, calibrated on the statewide ACS employed share by age and sex (calibrate.py)
# 2026-10-28 (author decision): no participation multipliers; the ACS rates are used directly (the calibrated multipliers of
# input/labor_participation_adjusters.csv only compensated for hires blocked by empty vacancy pools); employment is a test, not a lever
demographics.labor.participation.adjusters.file =

# population: observed control totals by region (county) and year (Census PEP), REGION method
population.control.total = region
population.control.total.by.region.file = input/assumptions/populationControlTotalByRegion.csv

# income (freeze-and-grow), retirement, education transitions, car ownership (data files)
mean.change.of.yearly.income = 2000
# real wage growth: QCEW Maryland average annual pay 2016-2024, CPI-deflated, +0.3-0.5 % per year
real.wage.growth.rate    = 0.005
retiree.income.floor     = 15000
demographics.retirement.income.replacement = 0.8
demographics.education.transitions.file = input/education_transitions.csv
demographics.regional.scalers.file =
# car ownership with the non-work logsum gain of a car (build_car_ownership.py --logsum, final accessibility file)
car.ownership.coefficients.file = input/car_ownership_coefficients_logsum.csv
car.ownership.region.constants.file = input/car_ownership_region_constants.csv

# demographic parameters (open-source defaults; calibrated later)
demographics.proability.girl               = 0.488
demographics.birth.scaler.married          = 1.59
demographics.birth.scaler.single           = 0.34
demographics.local.birth.rate.adjuster     = 1.0
demographics.min.age.for.legal.marriage    = 18
demographics.age.diff.of.partners.absolute = 2.3
demographics.age.diff.of.partners.spreadfc = 0.5
demographics.local.marriage.rate.adjuster  = 1.1
demographics.local.divorce.rate.adjuster   = 1.0
demographics.local.leave.parents.adjuster  = 1.0
# leavers aged 18-34 who join a roommate household: ACS PUMS 2014-18, roomers/housemates among non-family persons 18-34
demographics.leave.parents.join.share      = 0.386
# employment rates by age and sex (ACS PUMS 2013-17, input_build/build_labor_participation.py), scaled by the adjuster
demographics.labor.participation.file = input/laborParticipationRates.csv
# 2026-10-28 (author decision): yearly ACS PUMS 1-year rates 2016-2024, model-area PUMAs (input_build/build_labor_participation_byyear.py)
demographics.labor.participation.file.byyear = input/laborParticipationRates_byYear.csv
# 2026-10-28 (author decision): rates by home state (MD, DC, DE; model-area PUMAs of PA, VA, WV); pooled rates for other or unknown homes
demographics.labor.participation.file.bystate = input/laborParticipationRates_byYearState.csv
demographics.single.pers.hh.marriage.bias  = 2
demographics.interracial.marriage.share    = 0.02
relevance.of.race.in.zone.of.dwelling      = 0.8

# real estate (open-source defaults; calibrated later)
construct.dwelling.use.overwrite     = false
trace.use.of.overwrite.dwellings     = false
make.new.dwellings.partly.affordable = false
share.of.affordable.dwellings        = 1.0
level.of.affordability.setting       = 0.3
provide.housing.subsidy.to.low.inc   = false
construct.dwelling.mn.log.model.beta = 0.5
construct.dwelling.mn.log.model.inflator = 1.5
construct.dwelling.demand.scaler = 1.0
# per-region multipliers on the construction demand, calibrated to permitted units by county (calibration/calibrate.py)
construct.dwelling.demand.scalers.file = input/construction_region_scalers.csv
# demand a region cannot build stays unbuilt (not spilled to rural counties); Baltimore City infill capacity (build_development_capacity.py)
construct.dwelling.reallocate.unrealized = false
# Maryland county shares of construction by dwelling type, permits 2016-2019 (input_build/build_construction_shares.py)
construct.dwelling.region.shares.file = input/construction_county_shares.csv
# 2026-10-29 (author decision): Maryland counties build each year's observed BPS permits (1-unit -> SFD/SFA/MH by the engine's demand,
# 2-4 -> MF234, 5+ -> MF5plus); replaces the fixed 2016-19 shares; the demand scaler then acts only on the regions outside Maryland
construct.dwelling.region.permits.file = input/construction_county_permits.csv
development.file         = input/development_2026.csv
move.or.not.binomial.log.model.parameter = 10
move.or.not.binomial.log.shift.parameter = 0.03

# events
event.all.demography     = true
event.birthday           = true
event.checkDeath         = true
event.checkBirth         = true
event.checkLeaveParentHh = true
event.checkMarriage      = true
event.checkDivorce       = true
event.checkSchoolUniv    = true
event.checkDriversLicense = false
event.startJob           = true
event.quitJob            = true
event.all.hhMoves        = true
event.inmigration        = true
event.outMigration       = true
event.all.developers     = true
event.ddChangeQual       = true
event.ddDemolition       = true
event.ddConstruction     = true
vacant.job.by.reg.array  = 100000
vacant.dd.by.reg.array   = 100000

# estimated residential location model (2_silo/resloc) with the destination-choice logsum accessibility (data/accessibility_<year>.csv);
# move-or-not on the estimated utilities (expected maximum utility of the search set vs the current dwelling, years in the dwelling)
resloc.model                 = mnl
resloc.region.coefficients   = input/resloc_region_mnl.csv
resloc.dwelling.coefficients = input/resloc_dwelling_mnl.csv
resloc.region.attributes     = input/resloc_region_attributes.csv
resloc.transit.skim          = {S}/resloc/work/transit_peak_time_d2d_2024.csv.gz
# better-dwelling rule on (compared with the estimated utility under resloc.model = mnl)
resloc.acceptance            = satisfaction
resloc.iv.dwelling.sample    = 200
resloc.move.scale            = 1.0
# logit slope of the moving hazard on ln(1 + years in the dwelling), ACS MV distribution 2014-18 (input_build/build_tenure.py)
resloc.move.duration         = -0.982
resloc.move.search.size      = 20
# gap relative to the gap at the start of the tenure (1) or absolute (0)
resloc.move.reference        = 1.0
resloc.tenure.file           = input/tenure_by_age.csv
accessibility.model          = logsum
accessibility.logsum.file    = {V}/data/accessibility_{{year}}.csv
"""
# 2026-11-09: re-specified models (side_experiments/respec_2026-11/engine_check, e01-e03); the record keys are replaced, the new
# switches are appended; the calibrated levers of the record model (car-ownership county constants, DC anchoring of the workplace
# term) do not carry over and must be re-calibrated before the five-seed runs (see the 2026-11-09 hand-back)
RESPEC = {"resloc.region.coefficients": "input/resloc_region_mnl_respec.csv", "resloc.dwelling.coefficients": "input/resloc_dwelling_mnl_respec.csv",
          "resloc.region.attributes": "input/resloc_region_attributes_respec.csv",
          "car.ownership.coefficients.file": "input/car_ownership_coefficients_respec.csv",
          "car.ownership.region.constants.file": "input/car_ownership_region_constants_respec.csv",
          "job.choice.model": "respec", "job.choice.coefficients.file": "input/job_choice_coefficients_respec_dcacs.csv",
          # 2026-11-09: DC term anchored to the ACS 9.82 % and base workplaces re-assigned with the respec model (engine_check/w01_base_respec.py)
          "household.file.ascii": "microData_v5respec/hh", "person.file.ascii": "microData_v5respec/pp",
          "dwelling.file.ascii": "microData_v5respec/dd", "job.file.ascii": "microData_v5respec/jj"}
RESPEC_NEW = f"""
# re-specified models (2026-11-09): residential location (county step Ja, zone multimodal, dwelling x ln income), car ownership, workplace
resloc.spec                  = respec
resloc.region.adjacency      = input/resloc_region_adjacency_respec.csv
resloc.respec.zone.attributes = input/resloc_zone_attributes_respec.csv
resloc.respec.accessibility.file = {V}/data/accessibility_multimodal_respec_{{year}}.csv
car.ownership.spec           = respec
car.ownership.respec.location.file = input/car_ownership_puma_respec.csv
job.choice.accessibility.file = {V}/data/accessibility_{{year}}.csv
"""
if spec == "respec":
    import re
    if not os.path.lexists(f"{B}/microData_v5respec"): os.symlink(f"{R}/base_v5_respec/microData", f"{B}/microData_v5respec")
    for k, v in RESPEC.items():
        P, n = re.subn(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", P, flags=re.M); assert n == 1, k
    P += RESPEC_NEW
open(f"{R}/{name}.properties", "w").write(P); print(f"{R}/{name}.properties written; base {B}; spec {spec}")
