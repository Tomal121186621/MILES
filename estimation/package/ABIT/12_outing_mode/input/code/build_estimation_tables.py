#!/usr/bin/env python3
"""Estimation table of model 12_outing_mode: a02_outing_mode.load(half) (the copy in this folder), i.e. exactly the data frame the estimation
passed to the estimator, for the estimation half (input/data/estimation) and the hold-out half (input/data/holdout).

    python3 build_estimation_tables.py        (any Python with numpy, pandas, pyarrow)

Reads the intermediate files of ../data/raw (copied from 3_abit/tasha_estimation/work, the files the estimation read) and the
survey population of 00_shared_data/rts_2017_18/survey_pop.  Writes estimation_table.parquet (one row per observation; y = choice).
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd
import a02_outing_mode as A                      # noqa: E402  (copy)

for half, sub in [("estimation", "estimation"), ("validation", "holdout")]:
    out = A.load(half)
    if isinstance(out, tuple):                                   # a03_return.load returns (X, y)
        X, y = out; X = X.copy(); X["y"] = y
    else:
        X = out
    X = X.reset_index().rename(columns={"index": "row_index"})
    od = f"{HERE}/../data/{sub}"; os.makedirs(od, exist_ok=True)
    X.to_parquet(f"{od}/estimation_table.parquet", index=False)
    print(half, X.shape)
