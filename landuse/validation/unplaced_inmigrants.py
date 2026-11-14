#!/usr/bin/env python3
"""Unplaced in-migrant households by target region and year, parsed from the engine log of each seed (InOutMigrationImpl WARN line,
engine 3066ca9).  Writes data/silo_final_unplaced_inmigrants.csv (seed, year, region, n) and prints the seed mean by year (MD / other).
Usage: unplaced_inmigrants.py [n_seeds=5]"""
import re, sys, pandas as pd
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; S = f"{V}/2_silo"; n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
rows = []
for k in range(1, n + 1):
    for line in open(f"{S}/run/logs/oos_s{k}.log", errors="ignore"):
        m = re.search(r"Unplaced in-migrant households (\d{4}) by target region \(-1 = none\): \{(.*)\}", line)
        if m:
            for kv in filter(None, m.group(2).split(",")):
                r, c = kv.strip().split("="); rows.append(dict(seed=k, year=int(m.group(1)), region=int(r), n=int(c)))
D = pd.DataFrame(rows); D.to_csv(f"{V}/data/silo_final_unplaced_inmigrants.csv", index=False)
D["area"] = D.region.map(lambda r: "MD" if r > 24000 else "other")
T = D.groupby(["seed", "year", "area"]).n.sum().unstack(fill_value=0); T["total"] = T.sum(axis=1)
print(T.groupby("year").mean().round(0).astype(int).to_string())
M = D[D.area == "MD"].groupby(["year", "region"]).n.sum().div(n).round(0)
print("MD counties, seed mean, largest:"); print(M[M > 0].groupby("year").nlargest(3).droplevel(0).to_string())
