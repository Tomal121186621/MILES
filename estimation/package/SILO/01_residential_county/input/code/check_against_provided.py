#!/usr/bin/env python3
"""Compare your rebuilt estimation / hold-out tables with the provided ones, before estimating.
Before rebuilding, keep a copy of the provided tables (RUN.json, step 'input_check'):
    cp -R ../data/estimation ../data/provided_estimation; cp -R ../data/holdout ../data/provided_holdout
then run build_estimation_data.py (it rewrites ../data/estimation and ../data/holdout) and
    python check_against_provided.py
For every table: rows and columns, sum of each numeric column (provided / rebuilt), largest absolute difference of a value,
number of differing text values. 'MATCH' when the columns agree and the largest difference is below 1e-9 (relative to the value)."""
import os, sys, glob
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.abspath(f"{HERE}/../data")


def read(f):
    return pd.read_parquet(f) if f.endswith(".parquet") else pd.read_csv(f, low_memory=False)


ok_all = True
for sub in ("estimation", "holdout"):
    for f in sorted(glob.glob(f"{D}/provided_{sub}/*.parquet") + glob.glob(f"{D}/provided_{sub}/*.csv")):
        name = os.path.basename(f); g = f"{D}/{sub}/{name}"
        if name == "data_dictionary.csv": continue
        if not os.path.exists(g):
            print(f"{sub}/{name}: MISSING in the rebuild"); ok_all = False; continue
        a, b = read(f), read(g)
        print(f"{sub}/{name}: rows provided {len(a)}, rebuilt {len(b)}; columns {a.shape[1]} / {b.shape[1]}")
        same_cols = list(a.columns) == list(b.columns) and len(a) == len(b)
        if not same_cols:
            print("   columns or rows differ:", sorted(set(a.columns) ^ set(b.columns))[:10]); ok_all = False; continue
        num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]; txt = [c for c in a.columns if c not in num]
        diff = 0.0; worst = ""
        for c in num:
            x, y = a[c].to_numpy(float), b[c].to_numpy(float)
            d = np.nanmax(np.abs(x - y) / np.maximum(1.0, np.abs(x))) if len(x) else 0.0
            if (np.isnan(x) != np.isnan(y)).any(): d = np.inf
            if d > diff: diff, worst = d, c
        ntxt = sum(int((a[c].astype(str) != b[c].astype(str)).sum()) for c in txt)
        sums = pd.DataFrame({"provided": a[num].sum(), "rebuilt": b[num].sum()})
        print(f"   largest relative difference of a value: {diff:.3g}{' (' + worst + ')' if worst else ''}; differing text values: {ntxt}")
        print("   column sums (first 8 numeric columns):"); print(sums.head(8).to_string(float_format=lambda v: f"{v:.6g}"))
        m = diff < 1e-9 and ntxt == 0; ok_all &= m; print("   MATCH" if m else "   DIFFERENT")
if not glob.glob(f"{D}/provided_*"):
    sys.exit("no ../data/provided_estimation: copy the provided tables first (see the docstring)")
print("\nALL TABLES MATCH" if ok_all else "\nSOME TABLES DIFFER: check the inputs before estimating")
