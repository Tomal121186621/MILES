#!/usr/bin/env python3
"""Check of the zone arrays the engine builds for the re-specified residential model in a run (ReslocModel.prepareYear, dumped with
-Dsilo.resloc.respec.dump): dwellings by zone x structure type, ln mean monthly cost of the zone, share of the zone's households in
each income group, county of the zone, against the arrays of the estimation (2016 synthetic stock 2_silo/input/microData/dd_2016.csv,
households hh_2016.csv for the own-group share, r01_income_similarity.SH).  The engine base population uses hh_2016_v2.csv
(run/base_v4), so the own-group shares are also compared with that file.
    python3 landuse/checks/check_zone_arrays.py <dump dir>   ->  c05_zone_arrays_check.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
V = f"{WORKSPACE}"; MICRO = f"{V}/2_silo/input/microData"
HERE = f"{V}/side_experiments/respec_2026-11/engine_check"; DUMP = sys.argv[1]   # HERE: outputs (workspace)
G = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]; CT = ["SFD", "SFA", "MF", "MH"]


def shares(hhfile, dd, zones):
    hh = pd.read_csv(hhfile, usecols=["dwelling", "income"]); hh["zone"] = hh.dwelling.map(dd.set_index("id").zone)
    hh["g"] = np.array(G)[np.searchsorted([40000, 75000, 125000], hh.income.clip(lower=1).values, side="right")]
    return pd.crosstab(hh.zone, hh.g, normalize="index").reindex(index=zones, columns=G).fillna(0.0)


def main():
    e = pd.read_csv(f"{DUMP}/resloc_respec_zones_2016.csv").set_index("zone"); zones = e.index.values
    dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["id", "zone", "type", "monthlyCost"]); dd["ct"] = dd.type.replace({"MF234": "MF", "MF5plus": "MF"})
    Dm = dd.groupby(["zone", "ct"]).size().unstack(fill_value=0).reindex(index=zones, columns=CT, fill_value=0)
    lc = np.log(np.maximum(dd.groupby("zone").monthlyCost.mean().reindex(zones), 100.0)); has = Dm.sum(axis=1) > 0
    z = pd.read_csv(f"{V}/2_silo/resloc/work/geo_zone.csv").set_index("zone").region.reindex(zones)
    res = [dict(part="dwellings by zone x type", n=Dm.size, max_abs_diff=float(np.abs(e[[f"D_{c}" for c in CT]].values - Dm.values).max())),
           dict(part="ln mean monthly cost (zones with dwellings)", n=int(has.sum()), max_abs_diff=float((e.lncost[has] - lc[has]).abs().max())),
           dict(part="county of the zone", n=len(zones), max_abs_diff=float((e.region - z).abs().max()))]
    for lab, f in (("own-group share vs estimation (hh_2016.csv)", "hh_2016.csv"), ("own-group share vs engine base (hh_2016_v2.csv)", "hh_2016_v2.csv")):
        S = shares(f"{MICRO}/{f}", dd, zones); d = np.abs(e[[f"sh_{g}" for g in G]].values - S.values)
        res.append(dict(part=lab, n=d.size, max_abs_diff=float(d.max()), mean_abs_diff=float(d.mean())))
    if "lnddens" in e.columns:   # 2026-11-10 land use, recomputed by the engine from its dwellings and jobs
        L = pd.read_csv(f"{ESTIMATION_RESULTS}/residential/zone_landuse_2016.csv").set_index("zone").reindex(zones)
        for k in ["lnddens", "lnjden", "lnretden", "mix", "park"]:
            m = has if k == "lnddens" else np.ones(len(zones), bool)
            res.append(dict(part=f"land use: {k}", n=int(m.sum()), max_abs_diff=float((e[k][m] - L[k][m]).abs().max())))
    r = pd.DataFrame(res); print(r.to_string(index=False)); r.to_csv(f"{HERE}/c05_zone_arrays_check.csv", index=False)


if __name__ == "__main__":
    main()
