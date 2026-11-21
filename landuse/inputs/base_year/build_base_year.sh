#!/usr/bin/env bash
# Base year 2016 of the adopted setup (microdata v8): the build order of the earlier base on the household-corrected population
# (population/ rebalance step, output_v8), then the car and licence correction (carfix/), then the control totals.
# Logs go to WORKSPACE/2_silo/input_build/base_v8. Run through the miles command or set MILES_WORKSPACE.
set -eu
: "${MILES_WORKSPACE:?run through the miles command, or set MILES_WORKSPACE}"
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; L="$MILES_WORKSPACE/2_silo/input_build/base_v8"; mkdir -p "$L/carfix/work"; cd "$D"
t() { echo "[$(date '+%F %T')] $*"; }
for s in b01_workplace_v8 b02_export_v8 b03_microdata_v8 b04_schools_v8 b05_base_v2_v8 b06_workplace_respec_v8; do t "$s"; python3 -u $s.py > "$L/${s%%_*}.log" 2>&1; done
cd carfix; for s in s01_extract s02_acs s05_fix; do t "$s"; python3 -u $s.py > "$L/carfix/work/$s.log" 2>&1; done
t s07_write; python3 -u s07_write.py pp_2016_v8d jj_2016_v8d v8 > "$L/carfix/work/s07.log" 2>&1
cd ..; for s in b07_population_controls_v8 b08_job_controls_v8; do t "$s"; python3 -u $s.py > "$L/${s%%_*}.log" 2>&1; done
t "build done"
