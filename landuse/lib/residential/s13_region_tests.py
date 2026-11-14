#!/usr/bin/env python3
"""Specification tests of the county level of the residential location model (2026-11-04), against the model of record R8c
(s06b_region_constrained.py, tag final).  Same data (work/region_data_{est,val,oot}_final.pkl), estimator (mnl.MNL) and lambda <= 1
rule (fit_constrained); each test changes one part of the specification:
  T1  car time to another county below 20 min dropped (piece fixed at 0)
  T2a commute by income group only (commute x ln income dropped)
  T2b one commute slope + commute x ln income (no income-group slopes)
  T3a school achievement main effect dropped (school x children kept)
  T3b both school terms dropped
Output: tables/region_tests_final.csv (LL, K, BIC, LR against R8c, predictive rho2 on the held-out 20 % and the 2019-21 movers,
key coefficients).   Usage: python3 landuse/lib/residential/s13_region_tests.py"""
import pickle
import numpy as np, pandas as pd
from rc import *
from mnl import MNL, lr_test
import s06_region as RG

TAG = "final"
BASE = RG.SPECS[RG.FINAL]
INTER = ["IV_B", "IV_A", "d1", "d2", "d3", "same_region", "commute_log"]
TESTS = {"R8c (model of record)": (BASE, INTER),
         "T1 no car-time piece below 20 min": ([v for v in BASE if v != "d1"], INTER),
         "T2a commute by income group only": ([v for v in BASE if v != "commute_log_x_inc"], INTER),
         "T2b one commute slope x ln income": (BASE, [v for v in INTER if v != "commute_log"]),
         "T3a no school main effect": ([v for v in BASE if v != "school"], INTER),
         "T3b no school terms": ([v for v in BASE if v not in ("school", "school_x_child")], INTER)}


def fit(D, vs, inter_vars):
    g = D["h"].inc_group.values; inter = {v: g for v in inter_vars}
    X, names = RG.design(D, vs, inter=inter); fixed = {}
    for _ in range(4):
        keep = [i for i, n in enumerate(names) if n not in fixed]; off = np.zeros(D["av"].shape)
        for n, val in fixed.items(): off += val * X[:, :, names.index(n)]
        m = MNL(X[:, :, keep], [names[i] for i in keep], D["av"], D["C"], weights=D["w"], offset=off).fit()
        viol = [n for n, b in zip(m.names, m.b) if n.startswith(("IV_A", "IV_B")) and b > 1.0]
        if not viol: break
        for n in viol: fixed[n] = 1.0
    b = np.array([fixed.get(n, np.nan) for n in names], float); k = [i for i, n in enumerate(names) if n not in fixed]; b[k] = m.b
    se = np.zeros(len(names)); se[k] = np.sqrt(np.diag(m.cov_robust))
    return m, names, b, se, fixed, inter


def predictive(D, vs, inter_vars, names, b):
    g = D["h"].inc_group.values; X, nm = RG.design(D, vs, inter={v: g for v in inter_vars})
    assert nm == names, (nm, names)
    m = MNL(X, names, D["av"], D["C"], weights=D["w"]); P, Q, ll = m._logs(b)
    ll0 = np.log(D["C"].sum(axis=1) / D["av"].sum(axis=1))
    return float(1 - (D["w"] * ll).sum() / (D["w"] * ll0).sum())


def main():
    De, Dv, Do = (pickle.load(open(f"{WORK}/region_data_{s}_{TAG}.pkl", "rb")) for s in ("est", "val", "oot"))
    rows, base = [], None
    for lab, (vs, iv) in TESTS.items():
        m, names, b, se, fixed, _ = fit(De, vs, iv)
        N = len(De["h"]); K = m.k
        r = dict(model=lab, LL=m.ll, K=K, BIC=np.log(N) * K - 2 * m.ll, fixed_at_1=";".join(fixed),
                 rho2_heldout=predictive(Dv, vs, iv, names, b), rho2_2019_21=predictive(Do, vs, iv, names, b))
        if base is None: base = (m.ll, K)
        else:
            df = abs(base[1] - K); lr = lr_test(min(m.ll, base[0]), max(m.ll, base[0]), df) if df else (np.nan, 0, np.nan)
            r.update(LR=lr[0], df=lr[1], p=lr[2])
        co = dict(zip(names, zip(b, se)))
        for n in names:
            if n.startswith(("school", "commute_log", "d1", "crime")): r[n] = f"{co[n][0]:.4f} ({co[n][0] / co[n][1]:.2f})" if co[n][1] > 0 else f"{co[n][0]:.4f} (fixed)"
        rows.append(r); print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    pd.DataFrame(rows).to_csv(f"{TAB}/region_tests_{TAG}.csv", index=False)


if __name__ == "__main__":
    main()
