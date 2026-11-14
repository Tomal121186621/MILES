#!/bin/bash
# Workplace and school location re-estimated with the mode-choice logsums of the re-estimated mode models, after the logsum files
# are written (workplace/w05_logsum.py, locations/l08_school_logsum.py); then the coefficient and development tables.
set -e
cd "$(dirname "$0")"
until [ -f workplace/logsum_new.npy ] && [ -f locations/school_logsum_new.npy ]; do sleep 60; done
for f in workplace/w04_fit.csv workplace/w04_coef.csv workplace/w04.log; do cp "$f" "${f%.*}_pre1108s.${f##*.}"; done
for b in k8 hs college; do for x in fit.csv coef.csv log; do cp "locations/l07_school_${b}_$x" "locations/l07_school_${b}_pre1108s_$x" 2>/dev/null || true; done; done
(cd workplace && WDC_LOGSUM="$PWD/logsum_new.npy" python3 w04_sequence.py > w04.log 2>&1)
(cd locations && SCHOOL_LOGSUM="$PWD/school_logsum_new.npy" python3 -B l07_school.py > l07_rerun.out 2>&1)
(cd tables_new && python3 t_new_tables.py > t_new_tables.out 2>&1)
cd ../final_tables && python3 dev_tables.py && python3 make_pdf.py
echo logsum chain done
