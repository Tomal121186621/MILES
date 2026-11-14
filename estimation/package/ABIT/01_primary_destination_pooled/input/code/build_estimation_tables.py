#!/usr/bin/env python3
"""Estimation tables of model 01 (pooled primary destination of shopping, recreation, accompanying and other tours), exactly
as the estimation used them: estimate_fullset_taz.load("<PURPOSE>_primary", half) on the record files of input/data/raw (the
files the project estimation read: 3_abit/tasha_estimation/work/dc_{rec,cand,cfg}_<half>_taz.parquet, built by
prep_dc_taz.py); load() adds the flag `multi` (tour with at least one stop, estimate_complexity.multi_flag).

    python3 build_estimation_tables.py        (project Python: numpy, pandas, pyarrow, torch)

Writes input/data/{estimation,holdout}/<PURPOSE>/records.parquet          one row per record (chooser attributes)
                                                 candidates.parquet       rec, zidx, b: possible zones of the destination
                                                                          (survey traffic zone spread over model zones by jobs)
                                                 configurations.parquet   rec, home_idx, anchor_b, w: possible home zones
                                                                          (spread by housing units), weights w
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import estimate_fullset_taz as FS       # noqa: E402  (copy; reads input/data/raw)

PURPOSES = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
OUT = {"estimation": f"{HERE}/../data/estimation", "validation": f"{HERE}/../data/holdout"}

if __name__ == "__main__":
    for half, od in OUT.items():
        for p in PURPOSES:
            rec, cand, cfg = FS.load(f"{p}_primary", half)
            d = f"{od}/{p}"; os.makedirs(d, exist_ok=True)
            rec.to_parquet(f"{d}/records.parquet", index=False); cand.to_parquet(f"{d}/candidates.parquet", index=False)
            cfg.to_parquet(f"{d}/configurations.parquet", index=False)
            print(f"{half} {p}: {len(rec)} records, {len(cand)} candidate rows, {len(cfg)} configurations", flush=True)
