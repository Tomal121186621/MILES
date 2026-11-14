#!/usr/bin/env python3
"""Smoke-run summary: Maryland tables of validate_silo.py for the re-specified run (default smoke_respec_1109) against the record
five-seed run oos_s1 and the observed values, year 2017: cars per household, persons who moved, moves within the county,
commute / home-county share, county totals.   python3 s01_smoke_summary.py [scenario]  ->  s01_smoke_summary.csv"""
import os, sys
import pandas as pd
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"; HERE = os.path.dirname(os.path.abspath(__file__))
NAME = sys.argv[1] if len(sys.argv) > 1 else "smoke_respec_1109"


def pick(R, y=2017):
    R = R[R.year == y]; g = R.geo.astype(str)
    out = [R[(R.table.str.startswith("cars")) & (g == "24")].assign(item=lambda d: "cars " + d["bin"].astype(str))]
    out.append(R[R.section.isin(["C events"])].assign(item=lambda d: d.table))
    out.append(R[R.section.isin(["E commute"]) & g.isin(["24", "Maryland"])].assign(item=lambda d: d.table + " " + d["bin"].astype(str)))
    a = R[(R.section == "A totals") & g.str.match(r"^24\d{3}$")]
    out.append(pd.DataFrame([dict(item="MD county totals: median ratio", model=a.ratio.median(), observed=1.0),
                             dict(item="MD county totals: min ratio", model=a.ratio.min(), observed=1.0),
                             dict(item="MD county totals: max ratio", model=a.ratio.max(), observed=1.0)]))
    return pd.concat(out)[["item", "model", "observed"]]


def main():
    a = pick(pd.read_parquet(f"{V}/data/silo_validation_{NAME}.parquet")); b = pick(pd.read_parquet(f"{V}/data/silo_validation_oos_s1.parquet"))
    m = a.rename(columns={"model": "respec"}).merge(b.rename(columns={"model": "record_oos_s1"})[["item", "record_oos_s1"]], on="item", how="outer")
    m = m[["item", "respec", "record_oos_s1", "observed"]]; pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
    print(m.to_string(index=False)); m.to_csv(f"{HERE}/s01_smoke_summary.csv", index=False)


if __name__ == "__main__":
    main()
