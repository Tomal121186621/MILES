#!/usr/bin/env python3
"""Car ownership: writes the estimation and hold-out tables used by model/estimate_car_ownership.py.
Same steps as s08_oldest_age.py ('final' step): raw/hh.parquet (s01_data.py), estimation / hold-out split of s01_data.py,
worker counts capped at 6, age of the oldest member (s06_age.oldest_age, PUMS person file), density centred at the
estimation-sample mean, piecewise ln income (s04_form.pieces); persons aged 16+ (workers + nonworking_adults) as dummies
for 2, 3 and 4+ (reference 0-1) and the Baltimore City dummy (PUMA 2400801-2400805).
    python3 build_estimation_data.py   ->  ../data/estimation/car_ownership_estimation.csv, ../data/holdout/car_ownership_holdout.csv"""
import os
import pandas as pd
from s04_form import pieces
from s06_age import oldest_age, prep
from s01_data import RAWD

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(f"{HERE}/../data")
VARS = ["workers", "nonworking_adults", "children", "single_person", "sfd", "multifamily", "bedrooms", "ln_density", "acc_gain",
        "inc_lt25", "inc_25_50", "inc_50_100", "inc_gt100", "age10", "age10_sq", "inc_x_dens",
        "p16_2", "p16_3", "p16_4p", "city"]   # final spec; nonworking_adults is kept only as the source of the persons-16+ dummies


def add_p16_city(d):
    p16 = d.workers + d.nonworking_adults
    d["p16_2"] = (p16 == 2).astype(int); d["p16_3"] = (p16 == 3).astype(int); d["p16_4p"] = (p16 >= 4).astype(int)
    d["city"] = d.puma7.between(2400801, 2400805).astype(int)
    return d


def main():
    h = pd.read_parquet(f"{RAWD}/hh.parquet"); ages = oldest_age()
    e = h[h.half == "estimation"].reset_index(drop=True); o = h[h.half == "holdout"].reset_index(drop=True)
    md = e.ln_density.mean(); e = prep(e, md, ages); o = prep(o, md, ages); pieces(e); pieces(o); add_p16_city(e); add_p16_city(o)
    cols = ["serial", "puma7", "cars"] + VARS
    for d, f in ((e, "estimation/car_ownership_estimation.csv"), (o, "holdout/car_ownership_holdout.csv")):
        assert d[cols].notna().all().all()
        d[cols].to_csv(f"{OUT}/{f}", index=False, float_format="%.10g")
        print(f, len(d))
    print("density centring constant (estimation mean of ln density):", md)


if __name__ == "__main__":
    main()
