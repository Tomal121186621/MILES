#!/usr/bin/env python3
"""Smoke test analysis: SILO 2016-2018 with the estimated residential location model (scenario resloc_smoke, branch resloc)
against the run with the inherited MSTM utilities (calib_r19 of the baltimore-2026 branch, same inputs and parameters, years
2016-2017) and against observed mover flows (ACS county-to-county 2016-2020; PUMS 2014-2018 movers, persons).
Region-to-region flows of the households that moved (siloResults/relocation/relocation<year>.csv.gz, old and new zone).
Outputs tables/smoke_region_shares.csv, smoke_flow_stats.csv, smoke_move_rate.csv."""
import sys, io
import numpy as np, pandas as pd
from rc import *
import s07_region_validation as RV

RUNS = {"resloc_smoke": f"{RL}/run_smoke/base/scenOutput/resloc_smoke", "mstm_calib_r19": f"{S2}/run/base/scenOutput/calib_r19"}
YEARS = [2016, 2017]
z = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone")


def households(path, year):
    t = open(f"{path}/resultFile.csv").read().split("\n")
    i = t.index(f"Year {year}"); j = i + 1
    while not t[j].startswith("hhByType"): j += 1
    k = j + 1; n = 0
    while k < len(t) and t[k].startswith("SIZE_"):
        n += float(t[k].split(",")[1]); k += 1
    return n


def main():
    c2r = RV.county_region()
    acs = RV.acs_flows(f"{RAW}/CtyxCty_US_2016_2020.txt", c2r)
    fl = pd.read_csv(f"{TAB}/region_flows_prov.csv"); pums = fl[fl["sample"] == "est"].set_index(["orig", "dest"]).pums_obs
    regs = np.sort(z.region.unique())
    rate, shares, stats = [], [], []
    ref = {"acs_2016_2020": acs, "pums_2014_2018": pums}
    for run, path in RUNS.items():
        for y in YEARS:
            r = pd.read_csv(f"{path}/siloResults/relocation/relocation{y}.csv.gz")
            r["o"] = r.oldZone.map(z.region); r["d"] = r.newZone.map(z.region)
            nh = households(path, y)
            rate.append(dict(run=run, year=y, households=nh, moved=len(r), move_rate=len(r) / nh, within_region=(r.o == r.d).mean(),
                             within_zone=(r.oldZone == r.newZone).mean()))
            f = r.groupby(["o", "d"]).size()
            dsh = r.groupby("d").size().reindex(regs, fill_value=0) / len(r)
            shares.append(pd.DataFrame({"run": run, "year": y, "region": regs, "share": dsh.values}))
            idx = pd.MultiIndex.from_product([regs, regs])
            m = f.reindex(idx, fill_value=0).values.astype(float); m /= m.sum()
            for nm, o in ref.items():
                ov = o.reindex(idx, fill_value=0).values.astype(float); ov /= ov.sum()
                off = idx.get_level_values(0) != idx.get_level_values(1)
                stats.append(dict(run=run, year=y, reference=nm, corr_all=np.corrcoef(m, ov)[0, 1], corr_offdiag=np.corrcoef(m[off], ov[off])[0, 1],
                                  within_region_model=m[~off].sum(), within_region_ref=ov[~off].sum(), srmse=np.sqrt(((m - ov) ** 2).mean()) / ov.mean()))
    for nm, o in ref.items():
        d = o.groupby(level=1).sum().reindex(regs, fill_value=0); shares.append(pd.DataFrame({"run": nm, "year": 0, "region": regs, "share": (d / d.sum()).values}))
    pd.DataFrame(rate).to_csv(f"{TAB}/smoke_move_rate.csv", index=False)
    sh = pd.concat(shares); sh.to_csv(f"{TAB}/smoke_region_shares.csv", index=False)
    pd.DataFrame(stats).to_csv(f"{TAB}/smoke_flow_stats.csv", index=False)
    print(pd.DataFrame(rate).to_string()); print(pd.DataFrame(stats).round(3).to_string())
    w = sh.pivot_table(index="region", columns=["run", "year"], values="share")
    print((w * 100).round(2).loc[[24003, 24005, 24013, 24025, 24027, 24510, 24031, 24033, 13]].to_string())
    d = (w[("resloc_smoke", 2017)] - w[("acs_2016_2020", 0)]) * 100
    print("largest deviations resloc 2017 - ACS (pp):"); print(d.reindex(d.abs().sort_values(ascending=False).index).head(10).round(2).to_string())


if __name__ == "__main__":
    main()
