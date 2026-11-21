#!/usr/bin/env python3
"""Workplace choice: writes the estimation and hold-out tables of model/estimate_workplace_choice.py, with exactly the sampled
choice sets of the original estimation.

Same calls as w04_sequence.py (step 'final'): wdc.Model(terms) draws, for each estimation-half worker, the chosen zone plus
99 zones sampled uniformly without replacement from the other zones with jobs (numpy generator, seed 20261106, the default of
wdc.Model).  The base variables of every sampled zone are written per alternative (<variable>_<j>, j = 0..99, chosen = 0), the
person variables once per worker (the time interactions use them centred at the estimation-half means, wdc.MEAN).
Checks with the original estimator (wdc.Model.ll_grad): the log-likelihood of the earlier 35-term model at its estimates
(w04_*.csv, step 'final') and of the final 25-term model at its estimates (final_model_*.csv; size term ln of total jobs, the
job-type log weights at 0); the Biogeme script must reproduce the latter from the exported columns.
Hold-out: validation-half workers (person table); their choice set is all 1,587 zones with jobs (zone table zones_with_jobs.csv,
car times from 00_shared_data/skims/auto_peak_time.csv.gz).
    python3 build_estimation_data.py   ->  ../data/estimation/workplace_estimation.parquet, ../data/holdout/*.csv"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import wdc   # noqa: E402
OUT = os.path.abspath(f"{HERE}/../data"); RAWD = f"{OUT}/raw"
BASE = ["t", "lt", "intra", "cc", "cs", "dcw", "accw", "reg_bc", "reg_mopg", "reg_nvc", "reg_nvo", "reg_mdo", "reg_oth",
        "z_off_sh", "z_ret_sh", "z_ind_sh", "z_hiearn"]
PERSON = ["female", "young", "old", "g1", "g3", "g4", "lic", "hhs", "rurh", "kids", "w2", "car0"]
ZID = pd.read_csv(f"{wdc.HERE}/../../../00_shared_data/zone_system/zoneSystem.csv").sort_values("ZoneId").ZoneId.values


def persons_table(P):
    d = {"worker": np.arange(len(P["g"])), "home_zone": ZID[P["hidx"]], "work_zone": ZID[P["widx"]], "income_group": P["g"],
         "car_seg": P["car_seg"], "age": P["age"]}
    for v in PERSON:
        d[v] = wdc.pvar(v, P); d[f"{v}_c"] = wdc.pvar(f"{v}_c", P)
    return d


def main():
    fit = pd.read_csv(f"{RAWD}/w04_fit.csv"); row = fit[fit.step == "final"].iloc[0]; terms = row.terms.split()
    coef = pd.read_csv(f"{RAWD}/w04_coef.csv"); coef = coef[coef.step == "final"].set_index("param").coef
    m = wdc.Model(terms)                                     # seed 20261106, M = 100: the draws of w04_sequence.py
    th = coef.reindex(m.names).values; assert not np.isnan(th).any()
    ll = m.ll_grad(th)[0]
    print(f"estimation: N {m.N}, K {len(th)}, LL at w04 estimates {ll:.4f} (log {row.LL:.4f})"); assert abs(ll - row.LL) < 1e-6
    # final model (25 terms, size term ln of total jobs: job-type log weights g = 0): same draws, LL at its estimates
    ff = pd.read_csv(f"{RAWD}/final_model_fit.csv").iloc[0]; cf = pd.read_csv(f"{RAWD}/final_model_estimates.csv").set_index("param").coef
    mf = wdc.Model(ff.terms.split()); assert (mf.A == m.A).all()
    thf = np.array([cf.get(n, 0.0) for n in mf.names]); llf = mf.ll_grad(thf)[0]
    print(f"final model: K {int(ff.K)}, LL at its estimates {llf:.4f} (original {ff.LL:.4f})"); assert abs(llf - ff.LL) < 1e-6
    P = m.P; A = m.A; d = persons_table(P); d["choice"] = np.zeros(m.N, int)
    for j in range(A.shape[1]):
        a = A[:, j:j + 1]; d[f"zone_{j}"] = ZID[A[:, j]]
        for v in BASE: d[f"{v}_{j}"] = wdc.base(v, P["hidx"], a, P)[:, 0]
        for k, c in enumerate(["RET", "OFF", "IND", "OTH"]): d[f"jobs_{c}_{j}"] = m.Nj[:, j, k]
    df = pd.DataFrame(d); df.to_parquet(f"{OUT}/estimation/workplace_estimation.parquet", index=False)
    pd.DataFrame({"variable": list(wdc.MEAN), "estimation_half_mean": list(wdc.MEAN.values())}).to_csv(f"{OUT}/estimation/centring_constants.csv", index=False)
    # hold-out: validation-half workers and the zone table of their full choice set
    pd.DataFrame(persons_table(wdc.persons(False))).to_csv(f"{OUT}/holdout/workplace_holdout_workers.csv", index=False)
    Z = pd.DataFrame({"zone": ZID[wdc.AZ], "state_fips": wdc.ST[wdc.AZ], "county_fips": wdc.CT[wdc.AZ], "area": wdc.REG[wdc.AZ],
                      "jobs_RET": wdc.JOBS[wdc.AZ, 0], "jobs_OFF": wdc.JOBS[wdc.AZ, 1], "jobs_IND": wdc.JOBS[wdc.AZ, 2], "jobs_OTH": wdc.JOBS[wdc.AZ, 3]})
    for k in ["z_off_sh", "z_ret_sh", "z_ind_sh", "z_hiearn"]: Z[k] = wdc.D[k][wdc.AZ]
    Z.to_csv(f"{OUT}/holdout/zones_with_jobs.csv", index=False)
    print("validation workers", len(wdc.persons(False)["g"]), "zones with jobs", len(Z), "; validation LL (log)", row.validation_LL)


if __name__ == "__main__":
    main()
