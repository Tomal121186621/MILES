#!/usr/bin/env python3
"""Estimation tables of model 10 (pooled: school episodes of persons without a school record, EDUCATION_nonstud, and daycare /
pre-school of children under 5, EDUCATION_daycare; both from home), exactly as the estimation used them:
estimate_locations.load(half, segment, "primary") on the record files of input/data/raw (the files the project estimation read:
3_abit/tasha_estimation/work/loc_records_<half>.parquet, loc_cand_<half>.parquet).

    python3 build_estimation_tables.py        (project Python: numpy, pandas, pyarrow, torch)

Writes input/data/{estimation,holdout}/{nonstud,daycare}/records.parquet, candidates.parquet, configurations.parquet
(record ids are per purpose; one anchor configuration per record, weight 1).
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd
import estimate_locations as L          # noqa: E402  (copy; reads input/data/raw)

SEGS = {"nonstud": "EDUCATION_nonstud", "daycare": "EDUCATION_daycare"}
OUT = {"estimation": f"{HERE}/../data/estimation", "validation": f"{HERE}/../data/holdout"}

for half, od in OUT.items():
    for sub, seg in SEGS.items():
        rec, cand = L.load(half, seg, "primary")
        cfg = pd.DataFrame({"rec": rec.rec.values, "home_idx": rec.home_idx.values.astype(int), "anchor_b": rec.anchor_b.values.astype(int), "w": 1.0})
        d = f"{od}/{sub}"; os.makedirs(d, exist_ok=True)
        rec.to_parquet(f"{d}/records.parquet", index=False); cand.to_parquet(f"{d}/candidates.parquet", index=False)
        cfg.to_parquet(f"{d}/configurations.parquet", index=False)
        print(f"{half} {seg}: {len(rec)} records, {len(cand)} candidate rows")
