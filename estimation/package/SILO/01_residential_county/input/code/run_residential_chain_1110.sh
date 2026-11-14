#!/bin/bash
# Copy of side_experiments/respec_2026-11/step_by_step/residential/run_residential_chain_1110.sh
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
# 2026-11-10: residential chain with the land-use block of the zone part (r03), backups *_pre1110a made by hand beforehand:
#   zone sequence -> accessibility form (r08) -> accessibility split (r12) -> 5-fold CV (r10) -> county IVs (r07) -> county (r05) -> OOT (r09) -> tables
set -e
cd "$(dirname "$0")"
A=../accessibility_new
export ACC_CAR="$PWD/$A/accessibility_2016_new.csv" ACC_MM="$PWD/$A/accessibility_2016_new_multimodal.csv"
test -f "$ACC_CAR" && test -f "$ACC_MM"
[ "$1" == "downstream" ] || { python3 -B r03_sequence.py > r03.log 2>&1; python3 -B r08_zone_multimodal.py > r08.log 2>&1; SCRATCH=/private/tmp/claude-501/-Users-raassarkertomal-Documents-SILO-MITO-Chayan/837e84a8-8fbb-40fe-bdce-10485bd485a4/scratchpad python3 -B r12_zone_acc_split.py > r12.log 2>&1; }
python3 -B r10_zone_cv.py       > r10.log 2>&1
python3 -B r07_county_iv.py est val oot > r07.log 2>&1
python3 -B r05_region_sequence.py final newiv > r05.log 2>&1
python3 -B r09_oot.py           > r09.log 2>&1
echo chain done
