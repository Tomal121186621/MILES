#!/usr/bin/env python3
"""Provisional destination-choice logsum accessibility by zone, segment and purpose (until pipeline/accessibility.py writes
data/accessibility_<year>.csv; same schema: zone, segment, purpose, A, hansen).

  A_i^{s,p} = ln sum_j S_j^p exp(LS_ij^s),   LS_ij^s = ln( a_s exp(b_p * g_car_ij^s) + exp(c_pt + b_p * g_pt_ij^s) )
  g_car = car peak time + operating cost / VOT_s  (cost 8.4 cents per mile at an assumed 0.5 mi per minute of peak time)
  g_pt  = transit door-to-door time + fare $2 / VOT_s
  a_s   = car availability weight: 0 (no car), 0.5 (fewer cars than workers), 1 (cars >= workers or no workers)
  b_work = -0.04 /min, b_nonwork = -0.08 /min, c_pt = -1.0 (transit constant against car)
  S^work = all jobs of the zone; S^nonwork = retail jobs + 0.5 x other jobs + 0.1 x households
  VOT_s (2016 $/h, 50 % of the wage rate of the income group): LOW 6, MEDIUM 11, HIGH 17, VERY_HIGH 30
  hansen: the engine's measure  sum_j jobs_j^1.2 exp(-0.3 t_car_ij), scaled to max 100 (comparison only)
Parameters are literature values, not estimated: this file is a stand-in with the right structure.  Two transit variants:
  d2d  = door-to-door transit skim (pipeline/test/skims/transit_2024)   -> work/accessibility_provisional_2016.csv  (main)
  base = MSTM 2016 transit skim (2_silo/input/skims)                    -> work/accessibility_provisional_2016_basept.csv
"""
import numpy as np, pandas as pd
from rc import *

z = pd.read_csv(f"{WORK}/geo_zone.csv").sort_values("zone")
jj = pd.read_csv(f"{MICRO}/jj_2016.csv", usecols=["zone", "type"])
jt = jj.groupby(["zone", "type"]).size().unstack(fill_value=0).reindex(z.zone, fill_value=0)
S = {"work": jt.sum(axis=1).values.astype(float),
     "nonwork": (jt.get("RET", 0) + 0.5 * jt.get("OTH", 0) + 0.1 * z.set_index("zone").households.reindex(jt.index)).values.astype(float)}
B = {"work": -0.04, "nonwork": -0.08}
VOT = {"LOW": 6.0, "MEDIUM": 11.0, "HIGH": 17.0, "VERY_HIGH": 30.0}
CAR = {"nocar": 0.0, "carlt": 0.5, "carge": 1.0}
car = read_skim(SKIM_CAR)
car = np.where(np.isnan(car), 300.0, car)
hans = (np.power(S["work"], 1.2)[None, :] * np.exp(-0.3 * car)).sum(axis=1); hans = 100 * hans / hans.max()


def build(pt_path, out):
    pt = read_skim(pt_path)
    rows = []
    for inc, vot in VOT.items():
        gcar = car + (0.084 * 0.5 * car) / (vot / 60.0)
        gpt = pt + 2.0 / (vot / 60.0)
        for cname, a in CAR.items():
            for p, b in B.items():
                ecar = a * np.exp(b * gcar)
                ept = np.where(np.isnan(gpt), 0.0, np.exp(-1.0 + b * np.nan_to_num(gpt, nan=999)))
                tot = ecar + ept
                with np.errstate(divide="ignore"):
                    # sum_j S_j * exp(LS_ij) = sum_j S_j * (ecar + ept)
                    A = np.log((S[p][None, :] * tot).sum(axis=1))
                A = np.where(np.isfinite(A), A, np.nan)
                rows.append(pd.DataFrame({"zone": z.zone.values, "segment": f"{inc}_{cname}", "purpose": p, "A": A, "hansen": hans}))
    d = pd.concat(rows)
    # zones without any reachable destination (no car, no transit): floor at the minimum of the segment-purpose minus 1
    d["A"] = d.A.fillna(d.groupby(["segment", "purpose"]).A.transform("min") - 1.0)
    d.to_csv(out, index=False, float_format="%.5f")
    print(out, d.groupby(["purpose", "segment"]).A.describe()[["mean", "std", "min", "max"]].round(2).head(30).to_string())


build(SKIM_PT_D2D, f"{WORK}/accessibility_provisional_2016.csv")
build(SKIM_PT_BASE, f"{WORK}/accessibility_provisional_2016_basept.csv")
