#!/usr/bin/env python3
"""Mean and seed standard deviation of the validation tables over the out-of-sample runs (data/silo_validation_oos_s<k>.parquet)
-> data/silo_validation_oos_mean.parquet with the same columns (model = seed mean, observed) plus seed_sd and n_seeds; the
figure script reads it like a single scenario.  Usage: python3 landuse/validation/aggregate_seeds.py [n_seeds] [suffix, e.g. _pass3: oos_s<k>_pass3 -> oos_mean_pass3]"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, sys, os
V = f"{WORKSPACE}"; n = int(sys.argv[1]) if len(sys.argv) > 1 else 5; sfx = sys.argv[2] if len(sys.argv) > 2 else ""
fs = [f"{V}/data/silo_validation_oos_s{k}{sfx}.parquet" for k in range(1, n + 1) if os.path.exists(f"{V}/data/silo_validation_oos_s{k}{sfx}.parquet")]
R = pd.concat([pd.read_parquet(f).assign(seed=i + 1) for i, f in enumerate(fs)]); keys = ["section", "year", "geo", "table", "bin"]
g = R.groupby(keys, sort=False); M = g.agg(model=("model", "mean"), seed_sd=("model", "std"), observed=("observed", "first"), n_seeds=("model", "size")).reset_index()
M["diff_pp"] = (M.model - M.observed) * 100; M["ratio"] = M.model / M.observed.replace(0, np.nan)
M.to_parquet(f"{V}/data/silo_validation_oos_mean{sfx}.parquet", index=False); print(f"{len(fs)} seeds -> {len(M)} rows; data/silo_validation_oos_mean{sfx}.parquet")
