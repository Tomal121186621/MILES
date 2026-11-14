#!/usr/bin/env python3
"""Write the ABIT properties file for one chain year.  Usage: python3 activity/write_properties.py <name> <silo_scenario> <year> [sample_fraction] [skim_tag]

Inputs are taken from the rebuilt chain: SILO microdata of <year> (run/base/scenOutput/<silo_scenario>, files resolved across
microData/ and microData/futureYears/), gzipped-CSV skims from <workspace>/3_abit/skims/<skim_tag>/ (default: the base skims in
3_abit/skims/; later years use the MATSim-derived skims written by pipeline/skims_from_matsim.py), and the coefficient files of the
ABIT Maryland use case.  Workplaces come from the SILO persons file (stage 1 assignment carried through the land-use model), so no
workplace re-assignment file is set.  Output: 3_abit/run/<name>.properties; ABIT writes to 3_abit/run/<name>/output/.
Orchestration overrides (pipeline/run_chain.py, 2026-10-22), all optional environment variables:
  SILO_SCEN_DIR  the SILO scenario output directory (…/scenOutput/<scen>) when the run does not live under 2_silo/run/base
  ABIT_RUN_ROOT  directory that holds <name>.properties and <name>/ (default 3_abit/run)
  <skim_tag> may also be an absolute directory (the test runs keep their skims under pipeline/test/).
  ABIT_COEF_DIR  the coefficient directory (default ABIT/input/maryland/coef, the pristine reference); stage 3 (2026-10-22) keeps
                 the calibrated set in <workspace>/3_abit/coef_calibrated; the re-specified set is activity/parameters.  If
                 <coef dir>/run_params.csv exists (key,value), its rows are appended as properties (wfh.attendance.dayfactor,
                 workplace.silo, ...), with {PARAMETERS} replaced by the coefficient directory and {WORKSPACE} by the workspace.
  ABIT_EDU_TARGETS  the education targets file (default <coef dir>/targets_education.csv if present, else 3_abit/targets_education.csv)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys, os
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; A = f"{ABIT_HOME}/input/maryland"
COEF = os.environ.get("ABIT_COEF_DIR") or f"{A}/coef"
name, scen, year = sys.argv[1], sys.argv[2], int(sys.argv[3]); frac = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
skims = (sys.argv[5] if os.path.isabs(sys.argv[5]) else f"{V}/3_abit/skims/{sys.argv[5]}") if len(sys.argv) > 5 else f"{V}/3_abit/skims"
scen_dir = os.environ.get("SILO_SCEN_DIR") or f"{V}/2_silo/run/base/scenOutput/{scen}"; run_root = os.environ.get("ABIT_RUN_ROOT") or f"{V}/3_abit/run"
def micro(kind):
    for d in [f"{V}/2_silo/input/microData"] if year == 2016 else [f"{scen_dir}/microData", f"{scen_dir}/microData/futureYears"]:
        if os.path.exists(f"{d}/{kind}_{year}.csv"): return f"{d}/{kind}_{year}.csv"
    raise SystemExit(f"{kind}_{year}.csv not found for scenario {scen} ({scen_dir})")
def schools():
    """School records (stage 2b): the 2016 inventory with the SILO assignment for the base year; a later year takes the
    file SILO writes at the end of its run (scenOutput/<scen>/microData/futureYears/schools_<year>.csv, same ids), else
    the 2016 file (ids are stable, only occupancy differs)."""
    for f in [f"{V}/2_silo/input/schools_{year}.csv", f"{scen_dir}/microData/futureYears/schools_{year}.csv"]:
        if os.path.exists(f): return f
    print(f"warning: no schools_{year}.csv for scenario {scen}; using the 2016 inventory"); return f"{V}/2_silo/input/schools_2016.csv"
base = f"{run_root}/{name}"; os.makedirs(base, exist_ok=True)
for f in ["traveltime_auto", "distance_auto", "bus_tt", "rail_tt00"]:
    if not os.path.exists(f"{skims}/{f}.csv.gz"): raise SystemExit(f"skim missing: {skims}/{f}.csv.gz")
edu_targets = os.environ.get("ABIT_EDU_TARGETS") or (f"{COEF}/targets_education.csv" if os.path.exists(f"{COEF}/targets_education.csv") else f"{V}/3_abit/targets_education.csv")
extra = ""
# second pass of stage 3 (2026-10-22): the stop-purpose split, the attraction weights and the distance-band constants of the
# coefficient set, when the set carries them (the pristine reference does not: the model then keeps its fixed splits)
# estimated destination MNL (2026-10-22, 3_abit/destination_choice): the coefficient file; the model is switched on by
# dest.choice.model = mnl in run_params.csv (default gravity)
for key, fn in [("stop.purpose.file", "stop_purpose.csv"), ("dest.attraction.file", "dest_attraction.csv"), ("dest.distance.bands", "dest_distance_bands.csv"),
                ("dest.mnl.file", "dest_choice_mnl.csv")]:
    if os.path.exists(f"{COEF}/{fn}"): extra += f"{key} = {COEF}/{fn}\n"
# TASHA-style generation (2026-10-22, MarylandTashaGenerator): the distribution directory <coef>/tasha and, in the calibrated
# variant, the frequency factors; the generator itself is switched on by tasha.generation = true in run_params.csv
if os.path.isdir(f"{COEF}/tasha"): extra += f"tasha.dir = {COEF}/tasha\n"
if os.path.exists(f"{COEF}/tasha_freq_factors.csv"): extra += f"tasha.freq.factors = {COEF}/tasha_freq_factors.csv\n"
if os.path.exists(f"{COEF}/run_params.csv"):
    # placeholders in the values: {PARAMETERS} = this run's coefficient directory (COEF), {WORKSPACE} = the configured workspace
    def _value(v): return v.strip().replace("{PARAMETERS}", COEF).replace("{WORKSPACE}", V)
    extra += "\n# run parameters of the coefficient set (" + COEF + "/run_params.csv)\n" + "".join(
        f"{k.strip()} = {_value(v)}\n" for k, v in (l.split(",", 1) for l in open(f"{COEF}/run_params.csv").read().splitlines()[1:] if l.strip()))
props = f"""# ABIT {name}: year {year}, SILO scenario {scen}, skims {skims}, coefficients {COEF}
base.directory = {base}
zone.attributes.file = {A}/zone_attributes.csv
households.file = {micro('hh')}
persons.file    = {micro('pp')}
jobs.file       = {micro('jj')}
dwellings.file  = {micro('dd')}
# schools (stage 2b): records the person column schoolId points at; EDUCATION tour targets from the survey
schools.file = {schools()}
education.targets.file = {edu_targets}
county.fips = ALL
sample.fraction = {frac}
max.households = 100000000
number.of.threads = 8
output.suffix = _{name}

# level of service (gzipped CSV FROM,TO,VALUE; minutes and km)
car.time.omx.file = {skims}/traveltime_auto.csv.gz
car.time.omx.matrix = mat1
car.dist.omx.file = {skims}/distance_auto.csv.gz
car.dist.omx.matrix = mat1
bus.time.omx.file = {skims}/bus_tt.csv.gz
bus.time.omx.matrix = mat1
train.time.omx.file = {skims}/rail_tt00.csv.gz
train.time.omx.matrix = mat1
auto.toll = 0

# coefficients (ABIT Maryland use case)
tod.dummy.file = {COEF}/tod_rts.csv
rt.freq.rates = {COEF}/rt_freq_rates.csv
rt.mode.by.band = {COEF}/rt_mode_by_band.csv
rt.dist.by.purpose = {COEF}/rt_dist_by_purpose.csv
rt.mode.by.purpose = {COEF}/rt_mode_by_purpose.csv
dest.friction.file = {COEF}/dest_friction.csv
dest.power.friction = {COEF}/dest_friction_power.csv
dest.time.scale = 1.0
stopfreq.coefs = {COEF}/stopfreq_coefs.csv
stopfreq.offsets = {COEF}/stopfreq_offsets.csv
modechoice.dir = {COEF}
duration.distributions = {COEF}/duration.distributions.csv
rt.dist.cdf = {COEF}/rts_distance_cdf.csv

# work-from-home attendance by home county (ACS PUMS usual-WFH share)
wfh.attendance.file = {A}/wfh_attendance_fips.csv
wfh.attendance.dayfactor = 1.0
dest.border.file = {A}/border_segments.csv
dest.border.lambda = 0.0
""" + extra
open(f"{run_root}/{name}.properties", "w").write(props); print(f"wrote {run_root}/{name}.properties  (year {year}, sample {frac}, skims {skims})")
