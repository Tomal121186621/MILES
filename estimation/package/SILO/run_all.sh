#!/bin/bash
# Run all SILO models in dependency order. The dwelling level comes first because the PUMA level
# reads its inclusive value. Live log: manual_estimation/SILO/run_all.log
cd "$(dirname "$0")"
ORDER="02_residential_dwelling 01_residential_puma 04_car_ownership
05_workplace_choice 06_school_location_K8 07_school_location_high_school 08_school_location_college"
for M in $ORDER; do
  ./run_model.sh "$M" || echo "!!! $M failed"
done 2>&1 | tee run_all.log
