#!/usr/bin/env python3
"""Free-car rule of the car-driver availability (the rule DAYMAP applies when it draws the leg modes of a transit tour).

Car driver is available only with a licence, age 16+, at least one household car, AND a free household car. A car is free when
the number of the household's car-driver tours overlapping the transit tour's window (leave home .. arrive home) is below the
household's car count, at any instant of the window: at its start and at each start of an overlapping car-driver tour within it.
Car-driver tours are the survey tours whose tour mode is car driver (choice CD in tours_<half>.parquet).

apply(X, half): X = estimate_transit_legs.features(legs(half)); adds carfree, multiplies av_CD by it and recomputes chosen_av.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd
import mc_common as M      # noqa: E402  (tours_<half>.parquet in ../data/raw)


def overlap(held, t0, t1):
    """largest number of the intervals in held covering an instant of [t0, t1)"""
    pts = [t0] + [a for a, b in held if a < t1 and t0 < b and a > t0]
    return max(sum(1 for a, b in held if a <= s < b) for s in pts) if held else 0


def apply(X, half):
    tours = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet")
    tt = tours[tours.choice.isin(["TW", "TD"])].reset_index(drop=True)      # numbering of legs(): tour = row of tt
    cd = tours[tours.choice.eq("CD")].groupby("household_id")[["leave", "arrive"]].apply(lambda g: list(zip(g.leave, g.arrive))).to_dict()
    free = {k: bool(r.autos > 0 and overlap(cd.get(r.household_id, []), r.leave, r.arrive) < r.autos) for k, r in tt.iterrows()}
    X = X.copy()
    X["carfree"] = X.tour.map(free).astype(float)
    X["av_CD"] = X.av_CD * X.carfree
    X["chosen_av"] = [X[f"av_{m}"].iat[i] > 0 for i, m in enumerate(X["mode"].values)]
    return X
