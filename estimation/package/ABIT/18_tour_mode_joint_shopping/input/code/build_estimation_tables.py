#!/usr/bin/env python3
"""Estimation tables of model 18_tour_mode_joint_shopping (joint household shopping tours), exactly as the estimation passed them to Biogeme.

    PYTHONDONTWRITEBYTECODE=1 ~/.venvs/biogeme/bin/python build_estimation_tables.py      (run from this folder)

m11_joint_group.groups: one row per joint household group (representative member)
Writes ../data/estimation/tours.parquet and ../data/holdout/tours.parquet: num(df), i.e. the numeric columns of the DataFrame given
to biogeme.database.Database (m08_sequence.num), one row per joint household group; plus the choice label column `choice` (CD WK BK CP BUS TRAIN).
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.chdir(HERE)
import numpy as np, pandas as pd
import m08_sequence as M8          # noqa: E402  (copy; imports m07_children -> m06_literature -> m03_time_cost -> mc_common ...)
import m11_joint_group as M11   # noqa: E402

SEG = "shopping"
OUT = {"estimation": f"{HERE}/../data/estimation", "validation": f"{HERE}/../data/holdout"}


def tables():
    """m11_joint_group.main: groups of both halves; alternatives = modes chosen by some estimation group; a mode outside them is
    unavailable in both halves and validation groups that chose it are left out"""
    est, val = M11.groups("estimation", SEG), M11.groups("validation", SEG)
    alts = [a for a in M11.ALTS if est[f"av_{a}"].sum() > 0 and (est.choice == a).sum() > 0]
    val = val[val.choice.isin(alts)].reset_index(drop=True)
    for a in M11.ALTS:
        if a not in alts: est[f"av_{a}"] = 0.0; val[f"av_{a}"] = 0.0
    return {"estimation": est, "validation": val}


if __name__ == "__main__":
    for half, df in tables().items():
        os.makedirs(OUT[half], exist_ok=True)
        out = M8.num(df); out["choice"] = df.choice.values
        out.to_parquet(f"{OUT[half]}/tours.parquet", index=False)
        print(f"{half}: {len(out)} rows, {out.shape[1]} columns")
