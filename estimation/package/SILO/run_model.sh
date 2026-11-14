#!/bin/bash
# Run one SILO model: log-likelihood at the article coefficients, full Biogeme estimation, comparison with the article.
# Usage: ./run_model.sh 03_residential_dwelling        (from manual_estimation/SILO; the log also goes to <model>/output/run_log.txt)
set -e
PY=~/.venvs/biogeme/bin/python
M="${1:?model folder}"
cd "$(dirname "$0")/$M/model"
mkdir -p ../output
{
  echo "=================================================================="
  echo " $M    started $(date '+%Y-%m-%d %H:%M:%S')"
  echo "=================================================================="
  echo "--- 1. Log-likelihood at the article coefficients"
  $PY -u estimate_*.py --check 2>&1 | grep -v -i 'warn'
  echo
  echo "--- 2. Biogeme estimation (report: $M/output/)"
  START=$(date +%s)
  $PY -u estimate_*.py 2>&1 | grep -v -i 'warn'
  echo "    estimation time: $(( $(date +%s) - START )) s"
  echo
  echo "--- 3. Comparison with the article table"
  $PY -u compare_with_reference.py 2>&1
  echo
  echo " $M    finished $(date '+%Y-%m-%d %H:%M:%S')"
  echo
} 2>&1 | tee ../output/run_log.txt
