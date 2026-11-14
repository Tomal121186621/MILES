#!/usr/bin/env python3
"""Estimation tables of model 06 (first stop of an outing from the usual workplace, OTHER_wbs; anchor = workplace), exactly as the estimation
used them: estimate_subtour_dest.load(half, "OTHER_wbs") on the record files of input/data/raw (the files the project
estimation read: 3_abit/tasha_estimation/work/wbs_dest_records_<half>.parquet, wbs_dest_cand_<half>.parquet).

    python3 build_estimation_tables.py        (project Python: numpy, pandas, pyarrow, torch)

Writes input/data/{estimation,holdout}/records.parquet     one row per record (chooser attributes, anchor zone home_idx)
                                       candidates.parquet  rec, zidx, b: destination zones of the record's tract and their
                                                           weights (tract-to-zone measurement model, area overlap)
                                       configurations.parquet  rec, home_idx, anchor_b, w: anchor configurations (here one
                                                           per record, weight 1: dc_taz_engine.single_cfg)
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd
import estimate_subtour_dest as W       # noqa: E402  (copy; reads input/data/raw)

SEG = "OTHER_wbs"
OUT = {"estimation": f"{HERE}/../data/estimation", "validation": f"{HERE}/../data/holdout"}

for half, od in OUT.items():
    rec, cand = W.load(half, SEG)
    cfg = pd.DataFrame({"rec": rec.rec.values, "home_idx": rec.home_idx.values.astype(int), "anchor_b": rec.anchor_b.values.astype(int), "w": 1.0})
    os.makedirs(od, exist_ok=True)
    rec.to_parquet(f"{od}/records.parquet", index=False); cand.to_parquet(f"{od}/candidates.parquet", index=False)
    cfg.to_parquet(f"{od}/configurations.parquet", index=False)
    print(f"{half}: {len(rec)} records, {len(cand)} candidate rows, {len(cfg)} configurations")
