#!/usr/bin/env python3
"""Estimation / hold-out split of the 2017/18 RTS households: build_targets.make_split (seed 2026, stratified by home county x
household size 1..5+, alternate assignment inside each stratum after a seeded shuffle), unchanged.

    python3 make_rts_split.py        reads raw survey files (rts_common.load_households); writes rebuilt/rts_2017_18/split/rts_split.csv
"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pkg_paths import out
import rts_common as R          # noqa: E402
import build_targets as B       # noqa: E402

h = R.load_households()
s = B.make_split(h)
f = out("rts_2017_18/split/rts_split.csv"); s.rename("half").reset_index().to_csv(f, index=False)
print("wrote", f, s.value_counts().to_dict())
