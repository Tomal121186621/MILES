#!/usr/bin/env python3
"""Estimation tables of model 05_stop_other (stop location, OTHER_stop), exactly as the estimation used them:
estimate_fullset_taz.load("OTHER_stop", half) on the record files of input/data/raw (the files the project estimation read:
3_abit/tasha_estimation/work/dc_rec_<half>_taz.parquet, dc_cand_<half>_taz.parquet, dc_cfg_<half>_taz.parquet).

    python3 build_estimation_tables.py        (project Python: numpy, pandas, pyarrow, torch)

Writes input/data/{estimation,holdout}/records.parquet          one row per stop (chooser attributes, modal anchors)
                                       candidates.parquet       rec, zidx, b: possible zones of the stop (survey traffic zone or
                                                                tract spread over model zones by jobs) and their weights
                                       configurations.parquet   rec, home_idx (anchor a = previous location), anchor_b (next
                                                                anchor), w: anchor configurations (up to 4) and their weights
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import estimate_fullset_taz as F_       # noqa: E402  (copy; reads input/data/raw)

SEG = "OTHER_stop"
OUT = {"estimation": f"{HERE}/../data/estimation", "validation": f"{HERE}/../data/holdout"}

for half, od in OUT.items():
    rec, cand, cfg = F_.load(SEG, half)
    os.makedirs(od, exist_ok=True)
    rec.to_parquet(f"{od}/records.parquet", index=False); cand.to_parquet(f"{od}/candidates.parquet", index=False)
    cfg.to_parquet(f"{od}/configurations.parquet", index=False)
    print(f"{half}: {len(rec)} records, {len(cand)} candidate rows, {len(cfg)} configurations")
