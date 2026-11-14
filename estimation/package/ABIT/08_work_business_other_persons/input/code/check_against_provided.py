#!/usr/bin/env python3
"""Input check: compare the estimation data you rebuilt (input/data/estimation, input/data/holdout) with the data provided.

    ~/.venvs/biogeme/bin/python input/code/check_against_provided.py          (run from the model folder)

- Tables (parquet / csv, except biogeme_part*.parquet) are compared value by value with the provided copy in
  input/data/provided_reference/<estimation|holdout>/...: row counts, columns, per numeric column the sums and the largest
  absolute difference, per text column the number of differing values.
- Biogeme parts (biogeme_part*.parquet, large) are compared with input/data/provided_reference/biogeme_parts_manifest.csv:
  per column the row count, sum, minimum, maximum and sum of squares of the provided file.
Tolerance: absolute 1e-9 for tables; relative 1e-6 for the part statistics (the parts are float32).  Exit code 1 on a difference.
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
REF = os.path.join(DATA, "provided_reference")
TOL, RTOL = 1e-9, 1e-6


def read(p):
    return pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p, low_memory=False)


def tables(half):
    root = os.path.join(DATA, half)
    for d, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.endswith((".parquet", ".csv", ".csv.gz")) and f != "data_dictionary.csv":
                yield os.path.relpath(os.path.join(d, f), DATA)


def compare_table(rel):
    r, p = read(os.path.join(DATA, rel)), read(os.path.join(REF, rel)); ok = len(r) == len(p) and list(r.columns) == list(p.columns)
    n = min(len(r), len(p)); worst = 0.0; ndiff = 0
    for c in [c for c in p.columns if c in r.columns]:
        x, y = r[c].iloc[:n], p[c].iloc[:n]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv, yv = x.to_numpy(float), y.to_numpy(float)
            d = np.where(np.isnan(xv) & np.isnan(yv), 0.0, np.abs(xv - yv)); d = np.where(np.isnan(d), np.inf, d)
            m = float(d.max()) if n else 0.0; worst = max(worst, m); ndiff += int((d > TOL).sum())
        else:
            ndiff += int((x.astype(str).values != y.astype(str).values).sum())
    ok = ok and ndiff == 0
    print(f"{'OK  ' if ok else 'DIFF'} {rel}: rows {len(r):,} / provided {len(p):,}; columns {len(r.columns)} / {len(p.columns)}; "
          f"max |difference| {worst:.3g}; differing values {ndiff}")
    return ok


def compare_part(rel, man):
    m = man[man.file == rel].set_index("column")
    if m.empty: print(f"DIFF {rel}: not in the manifest"); return False
    r = pd.read_parquet(os.path.join(DATA, rel)); ok = len(r) == int(m.rows.iloc[0]) and set(r.columns) == set(m.index); bad = []
    for c in m.index.intersection(r.columns):
        v = r[c].to_numpy(np.float64)
        for stat, val in (("sum", v.sum()), ("min", v.min()), ("max", v.max()), ("sumsq", (v * v).sum())):
            ref = float(m.loc[c, stat])
            if abs(val - ref) > RTOL * max(1.0, abs(ref)): bad.append((c, stat, val, ref))
    ok = ok and not bad
    print(f"{'OK  ' if ok else 'DIFF'} {rel}: rows {len(r):,} / provided {int(m.rows.iloc[0]):,}; columns {r.shape[1]} / {len(m)}; "
          f"statistics differing: {len(bad)}" + (f" (first: {bad[0]})" if bad else ""))
    return ok


def main():
    if not os.path.isdir(REF): sys.exit(f"no provided reference in {REF}")
    man_f = os.path.join(REF, "biogeme_parts_manifest.csv"); man = pd.read_csv(man_f) if os.path.exists(man_f) else pd.DataFrame(columns=["file"])
    ok = True; seen = 0
    for half in ("estimation", "holdout"):
        for rel in tables(half):
            seen += 1
            if os.path.basename(rel).startswith("biogeme_part"): ok &= compare_part(rel, man)
            elif os.path.exists(os.path.join(REF, rel)): ok &= compare_table(rel)
            else: print(f"SKIP {rel}: no provided copy");
    print("all inputs agree with the provided data" if ok and seen else "DIFFERENCES FOUND (see above)")
    sys.exit(0 if ok and seen else 1)


if __name__ == "__main__":
    main()
