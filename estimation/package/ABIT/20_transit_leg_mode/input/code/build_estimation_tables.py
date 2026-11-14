#!/usr/bin/env python3
"""Estimation table of model 20 (mode of the legs of transit tours), exactly as estimate_transit_legs.estimate() passed it to
Biogeme: features(legs(half)) restricted to the legs whose chosen mode is available (chosen_av), for the estimation half
(input/data/estimation) and the hold-out half (input/data/holdout).

    python3 build_estimation_tables.py        (any Python with numpy, pandas, pyarrow)

legs(half) reads ../data/raw/tlegs_<half>.parquet (the legs file the estimation read; rebuilt from ../data/raw/tours_<half>.parquet
and the survey episodes if it is deleted); features() adds the zone skims of 00_shared_data (car distance, period transit skims).
Writes estimation_table.parquet (y = 1 TR, 2 WK, 3 CP, 4 CD, 5 BK; av_* availability).
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import estimate_transit_legs as E      # noqa: E402  (copy)

for half, sub in [("estimation", "estimation"), ("validation", "holdout")]:
    X = E.features(E.legs(half)); X = X[X.chosen_av].reset_index(drop=True)
    od = f"{HERE}/../data/{sub}"; os.makedirs(od, exist_ok=True)
    X.to_parquet(f"{od}/estimation_table.parquet", index=False)
    print(half, X.shape)
