#!/bin/bash
cd "$(dirname "$0")"; D=../dest_primary
for i in $(seq 1 600); do ok=1; for p in shop rec oth acc; do grep -q "^final," $D/d_${p}_fit.csv 2>/dev/null || ok=0; done; [ $ok = 1 ] && break; sleep 10; done
echo "ready=$ok $(date)" > waiter.status
[ $ok = 1 ] && python3 accessibility_new.py --purposes d_shop,d_rec,d_oth > run_all.out 2>&1
echo "done $? $(date)" >> waiter.status
