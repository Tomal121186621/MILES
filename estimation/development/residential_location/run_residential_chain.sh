#!/bin/bash
# Residential location re-estimated in dependency order with the accessibility of the re-estimated destination and mode models:
#   zone sequence (steps 1-10, car-based accessibility) -> accessibility form (car-based vs multimodal) -> 5-fold CV of the form
#   -> county inclusive values (estimation, validation, out-of-time movers) -> county sequence -> out-of-time test -> tables.
# The scripts are in this folder; logs and results are written to ESTIMATION_RESULTS/residential (terp.toml).
set -e
CODE="$(cd "$(dirname "$0")" && pwd)"; DEV="$(dirname "$CODE")"; TERP_HOME="$(cd "$DEV/../.." && pwd)"
ER="$(cd "$TERP_HOME" && python3 -c 'from terp_env import ESTIMATION_RESULTS; print(ESTIMATION_RESULTS)')"
cd "$ER/residential"
A="$ER/accessibility_new"
export ACC_CAR="$A/accessibility_2016_new.csv" ACC_MM="$A/accessibility_2016_new_multimodal.csv"
test -f "$ACC_CAR" && test -f "$ACC_MM"
for f in r03_fit.csv r03_coef.csv r08_fit.csv r08_coef.csv r10_cv.csv r05_fit.csv r05_coef.csv r09_oot.csv; do cp "$f" "${f%.csv}_pre1108r.csv"; done
python3 "$CODE/r03_sequence.py"      > r03.log 2>&1
python3 "$CODE/r08_zone_multimodal.py" > r08.log 2>&1
python3 "$CODE/r10_zone_cv.py"       > r10.log 2>&1
python3 "$CODE/r07_county_iv.py" est val oot > r07.log 2>&1
python3 "$CODE/r05_region_sequence.py" final newiv > r05.log 2>&1
python3 "$CODE/r09_oot.py"           > r09.log 2>&1
python3 "$CODE/t_region_table.py" && python3 "$CODE/t_zone_dwelling_tables.py"
python3 "$DEV/reports/dev_tables.py" && python3 "$DEV/reports/make_pdf.py"
echo chain done
