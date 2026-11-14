#!/bin/bash
# Workplace and school location re-estimated with the mode-choice logsums of the re-estimated mode models, after the logsum files
# are written (workplace_choice/w05_logsum.py, other_locations/l08_school_logsum.py); then the coefficient and development tables.
# The scripts are in this folder; results are read from and written to ESTIMATION_RESULTS (miles.toml).
set -e
DEV="$(cd "$(dirname "$0")" && pwd)"; MILES_HOME="$(cd "$DEV/../.." && pwd)"
ER="$(cd "$MILES_HOME" && python3 -c 'from miles_env import ESTIMATION_RESULTS; print(ESTIMATION_RESULTS)')"
cd "$ER"
until [ -f workplace/logsum_new.npy ] && [ -f locations/school_logsum_new.npy ]; do sleep 60; done
for f in workplace/w04_fit.csv workplace/w04_coef.csv workplace/w04.log; do cp "$f" "${f%.*}_pre1108s.${f##*.}"; done
for b in k8 hs college; do for x in fit.csv coef.csv log; do cp "locations/l07_school_${b}_$x" "locations/l07_school_${b}_pre1108s_$x" 2>/dev/null || true; done; done
(cd workplace && WDC_LOGSUM="$PWD/logsum_new.npy" python3 "$DEV/workplace_choice/w04_sequence.py" > w04.log 2>&1)
(cd locations && SCHOOL_LOGSUM="$PWD/school_logsum_new.npy" python3 -B "$DEV/other_locations/l07_school.py" > l07_rerun.out 2>&1)
(cd tables_new && python3 "$DEV/tables/t_new_tables.py" > t_new_tables.out 2>&1)
python3 "$DEV/reports/dev_tables.py" && python3 "$DEV/reports/make_pdf.py"
echo logsum chain done
