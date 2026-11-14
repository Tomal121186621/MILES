#!/usr/bin/env python3
"""Compare the regenerated TASHA distributions (default ../output) with ../data/reference_outputs (the files of
3_abit/coef_respec/tasha used by the 2024 runs).

    python3 compare_with_reference.py [--outdir ../output]
Per file: identical bytes, or else rows only in one of the two and the largest numeric difference among matching rows (keys =
the non-numeric / id columns; probability lists 'a;b;c' are compared element by element).  Writes comparison.csv in outdir.
Files the regeneration does not write (see README) are listed as 'not regenerated'.
"""
import argparse, filecmp, os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "data", "reference_outputs")
GEN = ["tasha_frequency.csv", "tasha_start.csv", "tasha_duration.csv", "tasha_joint_propensity_mand.csv", "tasha_location_bands.csv",
       "tasha_joint_participants.csv", "tasha_joint_propensity.csv", "tasha_params.csv"]


def tok(x):
    out = []
    for v in str(x).split(";"):
        try: out.append(float(v))
        except ValueError: out.append(v)
    return out


def cell_diff(x, y):
    a, b = tok(x), tok(y)
    if len(a) != len(b): return np.inf
    d = 0.0
    for u, v in zip(a, b):
        if isinstance(u, float) and isinstance(v, float): d = max(d, abs(u - v))
        elif u != v: return np.inf
    return d


def numeric_diff(a, b, keys):
    m = a.merge(b, on=keys, how="outer", suffixes=("_gen", "_ref"), indicator=True)
    only_gen = int((m._merge == "left_only").sum()); only_ref = int((m._merge == "right_only").sum()); m = m[m._merge == "both"]
    mx = 0.0
    for c in [c for c in a.columns if c not in keys and c in b.columns]:
        for x, y in zip(m[f"{c}_gen"], m[f"{c}_ref"]): mx = max(mx, cell_diff(x, y))
    return only_gen, only_ref, mx


KEYS = {"tasha_frequency.csv": ["level", "type", "seg", "hh", "prior"], "tasha_start.csv": None, "tasha_duration.csv": None,
        "tasha_joint_propensity_mand.csv": ["seg"], "tasha_joint_propensity.csv": ["seg"], "tasha_location_bands.csv": ["type", "origin"],
        "tasha_joint_participants.csv": None, "tasha_params.csv": ["key"]}


ap = argparse.ArgumentParser(); ap.add_argument("--outdir", default=os.path.join(HERE, "..", "output")); a = ap.parse_args()
rows = []
for f in sorted(os.listdir(REF)):
    if not f.endswith(".csv"): continue
    g, r = os.path.join(a.outdir, f), os.path.join(REF, f)
    if f not in GEN or not os.path.exists(g): rows.append(dict(file=f, result="not regenerated")); continue
    if filecmp.cmp(g, r, shallow=False): rows.append(dict(file=f, result="identical")); continue
    A, Bf = pd.read_csv(g, dtype=str), pd.read_csv(r, dtype=str)
    keys = KEYS[f] or [c for c in A.columns if c not in ("probs", "n", "mean", "members", "participants", "propensity")]
    og, orf, mx = numeric_diff(A, Bf, keys)
    if f == "tasha_params.csv":     # the reference also holds the engine settings appended by 3_abit/build_coef_tasha / build_coef_respec
        orf = f"{orf} (engine settings appended by the coefficient build, not written by tasha_distributions.py)"
    rows.append(dict(file=f, result="differs", rows_only_regenerated=og, rows_only_reference=orf, max_abs_difference=mx))
out = pd.DataFrame(rows); pd.set_option("display.width", 200); print(out.to_string(index=False))
out.to_csv(os.path.join(a.outdir, "comparison.csv"), index=False)
