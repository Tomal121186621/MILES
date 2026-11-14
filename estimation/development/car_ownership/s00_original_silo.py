#!/usr/bin/env python3
"""Car ownership: the original SILO Maryland model (MSTM, Moeckel 2014; siloCore resource
autoOwnership/maryland/UpdateCarOwnershipMstmCalc) applied to the same PUMS households, with its own coefficients and
re-estimated with the same variables.
Variables as in MaryLandUpdateCarOwnershipModel: household size (max 8), workers (max 4), 12 income classes, transit
accessibility (SILO Hansen: sum_j jobs_j^1.2 exp(-0.3 t_ij), transit door-to-door minutes, scaled so the maximum is 100,
rounded), 10 job-density classes (thresholds 0, .143, .437, .865, 1.324, 1.8778, 2.664, 3.99105, 6, 12.7).
SILO divides jobs by square miles; the thresholds look like jobs per acre, so both are computed.
PUMS has no zone: the probability of a household is the mean over the zones of its PUMA, weighted by housing units.
Outputs: s00_original.csv.   Usage: python3 estimation/development/car_ownership/s00_original_silo.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from mnl import fit

ROOT = f"{PROJECT_ROOT}"
V = f"{WORKSPACE}"
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
INC = [0, 10000, 15000, 30000, 40000, 50000, 60000, 75000, 100000, 125000, 150000, 200000]
DENS = [0., .143, .437, .865, 1.324, 1.8778, 2.664, 3.99105, 6., 12.7]
I1 = [-3.783, -3.134, -2.423, -1.964, -1.374, -0.811, -0.996, -0.913, -0.716, -0.271, -0.236, 0]
I2 = [-6.348, -5.724, -4.734, -3.918, -3.027, -2.11, -2.168, -1.93, -1.376, -0.609, -0.432, 0]
I3 = [-7.007, -6.637, -5.315, -4.858, -3.639, -2.522, -2.589, -2.283, -1.706, -0.827, -0.382, 0]
D1 = [2.678, 2.306, 1.412, 1.461, 1.121, 0.762, 0.895, 0.471, 0.678, 0]
D2 = [4.72, 4.085, 2.742, 2.749, 2.213, 1.661, 1.713, 1.096, 1.196, 0]
D3 = [6.978, 5.802, 4.163, 3.909, 3.231, 2.927, 2.463, 1.92, 2.029, 0]


def inc_class(x):  # 1..12 as getIncomeCategory
    return np.searchsorted(INC, x, side="right")


def dens_class(x):  # 1..10 as getJobDensityCategoryOfZone
    return np.minimum(np.searchsorted(DENS, x, side="right"), 10)


def zone_inputs():
    zs = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv", usecols=["ZoneId", "AREA_SQMI"]).set_index("ZoneId")
    jobs = pd.read_csv(f"{V}/2_silo/input/microData/jj_2016.csv", usecols=["zone"]).zone.value_counts().reindex(zs.index).fillna(0)
    t = pd.read_csv(f"{V}/2_silo/resloc/work/transit_peak_time_d2d_2024.csv.gz")
    t = t[t.VALUE < 999]
    acc = (jobs.reindex(t.TO).values ** 1.2 * np.exp(-0.3 * t.VALUE.values))
    acc = pd.Series(acc).groupby(t.FROM.values).sum().reindex(zs.index).fillna(0)
    z = pd.DataFrame({"transitAcc": np.floor(acc / acc.max() * 100 + 0.5).astype(int),
                      "dens_sqmi": dens_class(jobs / zs.AREA_SQMI), "dens_acre": dens_class(jobs / (zs.AREA_SQMI * 640))})
    return z


def original_probs(hhsize, workers, ic, ta, dc):
    u1 = 2.258434 - 0.121 * hhsize + 0.327 * workers - 0.022 * ta + np.take(I1, ic - 1) + np.take(D1, dc - 1)
    u2 = 0.273337 + 0.689 * hhsize + 0.652 * workers - 0.051 * ta + np.take(I2, ic - 1) + np.take(D2, dc - 1)
    u3 = -3.26874 + 0.801 * hhsize + 1.378 * workers - 0.054 * ta + np.take(I3, ic - 1) + np.take(D3, dc - 1)
    e = np.exp(np.column_stack([np.zeros_like(u1), u1, u2, u3])); return e / e.sum(1, keepdims=True)


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    z = zone_inputs()
    pz = pd.read_csv(f"{V}/2_silo/resloc/work/geo_puma_zone.csv"); pz = pz[(pz.puma7 // 100000 == 24) & (pz.hu > 0)]
    pz = pz.join(z, on="zone"); pz["wt"] = pz.hu / pz.groupby("puma7").hu.transform("sum")
    print("share of Maryland housing units by density class (jobs per sq mile, as SILO):",
          (pz.groupby("dens_sqmi").hu.sum() / pz.hu.sum()).round(3).to_dict())
    print("                                    (jobs per acre):", (pz.groupby("dens_acre").hu.sum() / pz.hu.sum()).round(3).to_dict())
    hs = d.hhsize.clip(upper=8).values; wk = d.workers.clip(upper=4).values; ic = inc_class(d.income_k.values * 1000)
    rows = []
    for dv in ["dens_sqmi", "dens_acre"]:
        P = np.zeros((len(d), 4))
        for p, g in pz.groupby("puma7"):
            m = (d.puma7 == p).values
            if not m.any(): continue
            for _, r in g.iterrows():
                P[m] += r.wt * original_probs(hs[m], wk[m], ic[m], r.transitAcc, int(r[dv]))
        LL = np.log(P[np.arange(len(d)), d.cars.values]).sum()
        share = P.mean(0)
        rows.append(dict(model=f"original SILO coefficients, density {dv}", K=0, LL=LL, BIC=-2 * LL,
                         pred_shares=np.round(share, 3).tolist()))
        print(rows[-1])
    # re-estimated with the same variables (PUMA means of transit accessibility; PUMA job-density class per acre)
    g = pz.groupby("puma7")
    d["transitAcc"] = d.puma7.map(g.apply(lambda x: np.average(x.transitAcc, weights=x.hu))).values
    jobs_p = pd.read_csv(f"{V}/2_silo/input/microData/jj_2016.csv", usecols=["zone"]).zone.value_counts()
    zs = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv", usecols=["ZoneId", "AREA_SQMI"]).set_index("ZoneId")
    pz["jobs"] = pz.zone.map(jobs_p).fillna(0) * pz.hu / pz.groupby("zone").hu.transform("sum")
    pz["acres"] = pz.zone.map(zs.AREA_SQMI) * 640 * pz.hu / pz.groupby("zone").hu.transform("sum")
    dj = pz.groupby("puma7").jobs.sum() / pz.groupby("puma7").acres.sum(); dc = pd.Series(dens_class(dj.values), index=dj.index)
    d["dcls"] = d.puma7.map(dc).values; d["icls"] = ic
    d["hhsize8"] = hs.astype(float); d["workers4"] = wk.astype(float)
    dum = []
    for k in range(1, 12): d[f"inc_{k}"] = (d.icls == k).astype(float); dum.append(f"inc_{k}")
    present = sorted(d.dcls.unique())
    for k in present[:-1]: d[f"dens_{k}"] = (d.dcls == k).astype(float); dum.append(f"dens_{k}")
    r = fit(d, ["hhsize8", "workers4", "transitAcc"] + dum)
    rows.append(dict(model=f"original variables re-estimated (density classes present: {present})", K=r["K"], LL=r["LL"], BIC=r["BIC"],
                     pred_shares=np.round(r["P"].mean(0), 3).tolist()))
    print(rows[-1])
    rows.append(dict(model="observed shares", pred_shares=np.round(np.bincount(d.cars, minlength=4) / len(d), 3).tolist()))
    pd.DataFrame(rows).to_csv(f"{HERE}/s00_original.csv", index=False)


if __name__ == "__main__":
    main()
