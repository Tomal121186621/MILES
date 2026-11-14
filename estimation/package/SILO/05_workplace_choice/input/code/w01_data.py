#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/workplace/w01_data.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Workplace choice, step by step: data. Same workers, zones and attributes as the current model (2_silo/jobchoice,
workers_v2.parquet: RTS 2017/18 workers with a usual workplace outside the home; estimation half 9,707, validation half 9,749).
Simplification against the current model: one home zone and one workplace zone per worker (hz, wz: the most likely zone),
instead of the location mixture. Output: data.npz (small).   Usage: python3 w01_data.py"""
import os
import numpy as np, pandas as pd

ROOT = os.environ.get("MILES_PROJECT_ROOT", "") + ""
V = f"{ROOT}/Validation_2026"; JC = f"{V}/2_silo/jobchoice"
HERE = os.path.dirname(os.path.abspath(__file__))
RAWD = os.path.abspath(f"{HERE}/../data/raw"); SHD = os.path.abspath(f"{HERE}/../../../00_shared_data")   # PATH (package)
GROUPS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]; CARS = ["nocar", "carlt", "carge"]


def main():
    zs = pd.read_csv(f"{SHD}/zone_system/zoneSystem.csv").sort_values("ZoneId").reset_index(drop=True)
    zi = pd.Series(np.arange(len(zs)), index=zs.ZoneId.values)
    J = pd.read_parquet(f"{RAWD}/zones.parquet").set_index("zone").reindex(zs.ZoneId.values)
    ZA = pd.read_parquet(f"{RAWD}/zone_attrs_v2x.parquet").set_index("zone").reindex(zs.ZoneId.values)
    out = {f"jobs_{k}": J[k].fillna(0).values.astype(float) for k in ["RET", "OFF", "IND", "OTH"]}
    for k in ["hiearn", "off_sh", "ret_sh", "ind_sh", "lnden", "rural"]: out[f"z_{k}"] = ZA[k].values.astype(float)
    out["z_state"] = zs.STFIPS.values; out["z_county"] = zs.COUNTYFIPS.values
    out["z_km2"] = zs.AREA_SQMI.values * 2.58999
    # non-work accessibility (logsum) of every zone by segment (income group x car class), for the accessibility of the workplace
    acc = pd.read_csv(f"{SHD}/accessibility/accessibility_2016.csv"); acc = acc[acc.purpose == "nonwork"]
    A = np.zeros((3, 4, len(zs)))
    for c, cn in enumerate(CARS):
        for g, gn in enumerate(GROUPS):
            A[c, g] = acc[acc.segment == f"{gn}_{cn}"].set_index("zone").A.reindex(zs.ZoneId.values).values
    out["acc_nonwork"] = A
    sk = pd.read_csv(f"{SHD}/skims/auto_peak_time.csv.gz"); T = np.full((len(zs), len(zs)), np.nan, np.float32)
    T[zi[sk.FROM].values, zi[sk.TO].values] = sk.VALUE.values; out["tt"] = T
    P = pd.read_parquet(f"{RAWD}/workers_v2.parquet")
    lic = pd.read_csv(f"{SHD}/rts_2017_18/RTS_raw_flat_data.csv", usecols=["person_id", "license"], low_memory=False).drop_duplicates("person_id").set_index("person_id").license
    P["lic"] = (P.person_id.map(lic) == 1).astype(int)
    for k, v in {"hidx": zi[P.hz].values, "widx": zi[P.wz].values, "g": P.g.values, "female": P.female.values, "age": P.age.values,
                 "kids": (P.children.values > 0).astype(int), "workers": P.workers.values, "car_seg": P.car_seg.values, "lic": P.lic.values,
                 "hhsize": P.hhsize.values, "state_h": P.state_h.values, "est": (P.half == "estimation").values.astype(int)}.items():
        out[f"p_{k}"] = np.asarray(v)
    np.savez_compressed(os.environ.get("W01_OUT", f"{RAWD}/data.npz"), **out)
    print("workers", len(P), "estimation", int(out["p_est"].sum()), "zones", len(zs), "zones with jobs", int((sum(out[f'jobs_{k}'] for k in ['RET','OFF','IND','OTH']) > 0).sum()))


if __name__ == "__main__":
    main()
