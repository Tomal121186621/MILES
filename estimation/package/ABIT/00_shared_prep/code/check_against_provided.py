#!/usr/bin/env python3
"""Compare a rebuilt table with the provided one.

    python check_against_provided.py <rebuilt> <provided> [--key col ...] [--tol 1e-9] [--ignore col ...]

Files: .parquet, .csv, .csv.gz.  Reports row counts, column sets, per numeric column the sums and the largest absolute
difference, per other column the number of differing values.  Rows are aligned on --key columns (sorted) if given, else by
position.  Exit code 0 when everything agrees within --tol (absolute, numeric), 1 otherwise.
"""
import argparse, sys
import numpy as np, pandas as pd


def read(p):
    return pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p, low_memory=False)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("rebuilt"); ap.add_argument("provided")
    ap.add_argument("--key", nargs="*", default=[]); ap.add_argument("--tol", type=float, default=1e-9); ap.add_argument("--ignore", nargs="*", default=[])
    a = ap.parse_args()
    r, p = read(a.rebuilt), read(a.provided); ok = True
    r = r.drop(columns=[c for c in a.ignore if c in r]); p = p.drop(columns=[c for c in a.ignore if c in p])
    print(f"rows: rebuilt {len(r):,}  provided {len(p):,}")
    if len(r) != len(p): ok = False
    only_r, only_p = sorted(set(r.columns) - set(p.columns)), sorted(set(p.columns) - set(r.columns))
    if only_r or only_p: ok = False; print(f"columns only in rebuilt: {only_r}\ncolumns only in provided: {only_p}")
    cols = [c for c in p.columns if c in r.columns]
    if a.key:
        r = r.sort_values(a.key, kind="stable").reset_index(drop=True); p = p.sort_values(a.key, kind="stable").reset_index(drop=True)
    n = min(len(r), len(p)); r, p = r.iloc[:n], p.iloc[:n]
    rows = []
    for c in cols:
        x, y = r[c], p[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv, yv = x.to_numpy(float), y.to_numpy(float)
            both_nan = np.isnan(xv) & np.isnan(yv); d = np.where(both_nan, 0.0, np.abs(xv - yv)); d = np.where(np.isnan(d), np.inf, d)
            mx = float(d.max()) if len(d) else 0.0
            rows.append(dict(column=c, kind="numeric", sum_rebuilt=float(np.nansum(xv)), sum_provided=float(np.nansum(yv)), max_abs_diff=mx, n_diff=int((d > a.tol).sum())))
        else:
            dif = int((x.astype(str).values != y.astype(str).values).sum())
            rows.append(dict(column=c, kind="other", sum_rebuilt=np.nan, sum_provided=np.nan, max_abs_diff=np.nan, n_diff=dif))
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200); pd.set_option("display.max_rows", 500)
    print(t.to_string(index=False))
    if (t.n_diff > 0).any(): ok = False
    print("RESULT:", "identical within tolerance" if ok else "DIFFERENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
