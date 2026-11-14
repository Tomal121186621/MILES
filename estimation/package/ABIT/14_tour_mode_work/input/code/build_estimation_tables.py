#!/usr/bin/env python3
"""Estimation tables of model 14_tour_mode_work (work tours), exactly as the estimation passed them to Biogeme.

    PYTHONDONTWRITEBYTECODE=1 ~/.venvs/biogeme/bin/python build_estimation_tables.py      (run from this folder)

K7.data: tours of the segment with the chosen mode available, + WESML weights (column wesml)
Writes ../data/estimation/tours.parquet and ../data/holdout/tours.parquet: num(df), i.e. the numeric columns of the DataFrame given
to biogeme.database.Database (m08_sequence.num), one row per one row per tour (estimation half N 9,126); plus the choice label column `choice` (CD WK BK CP BUS TRAIN).
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.chdir(HERE)
import numpy as np, pandas as pd
import m08_sequence as M8          # noqa: E402  (copy; imports m07_children -> m06_literature -> m03_time_cost -> mc_common ...)


SEG = "work"
OUT = {"estimation": f"{HERE}/../data/estimation", "validation": f"{HERE}/../data/holdout"}


def tables():
    """K7.data(half, SEG) of m07_children (the data of m08_sequence.main / m09_school.main for both halves)"""
    return {"estimation": M8.K7.data("estimation", SEG), "validation": M8.K7.data("validation", SEG)}


if __name__ == "__main__":
    for half, df in tables().items():
        os.makedirs(OUT[half], exist_ok=True)
        out = M8.num(df); out["choice"] = df.choice.values
        out.to_parquet(f"{OUT[half]}/tours.parquet", index=False)
        print(f"{half}: {len(out)} rows, {out.shape[1]} columns")
