#!/bin/bash
cd "$(dirname "$0")"; D=../dest_primary; todo="shop rec oth"
for i in $(seq 1 700); do
  left=""
  for p in $todo; do
    if grep -q "^final," $D/d_${p}_fit.csv 2>/dev/null; then python3 accessibility_new.py --purposes d_$p --est-only > run_est_$p.out 2>&1; echo "est $p $? $(date)" >> waiter2.status
    else left="$left $p"; fi
  done
  todo=$left; [ -z "$(echo $todo)" ] && break; sleep 15
done
python3 accessibility_new.py --skip-est > run_all.out 2>&1
echo "done $? $(date)" >> waiter2.status
