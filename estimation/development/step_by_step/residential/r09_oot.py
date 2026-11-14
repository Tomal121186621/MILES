#!/usr/bin/env python3
"""Out-of-time test, used once, of the frozen county and dwelling parts: ACS PUMS movers 2019-2021 (not used in any estimation or
selection).  County: final model of r05_region_sequence.py (inclusive values of r07_county_iv.py, oot) against the model of record
(its out-of-time log-likelihood from 2_silo/resloc/tables/region_validation_final.csv).  Dwelling: final model of
r06_dwelling_income.py against the model of record (work/dwelling_beta.npy), on the same sampled choice sets (chosen + 29 dwellings
of the 2019-2021 pool).
    python3 r09_oot.py   ->  r09_oot.csv"""
import os, sys, pickle, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r05_region_sequence as S   # noqa: E402
import r06_dwelling_income as R6   # noqa: E402
DW = R6.DW
from mnl import MNL   # noqa: E402

TAB = f"{S.RL}/tables"


def county():
    D = S.add_growth(pickle.load(open(f"{HERE}/county_data_oot.pkl", "rb")))
    f = pd.read_csv(f"{HERE}/r05_fit.csv"); fin = f[f.final].iloc[0]
    c = pd.read_csv(f"{HERE}/r05_coef.csv"); c = c[c.step == fin.step]
    fixed = [x for x in str(fin.fixed_at_1).split(";") if x and x != "nan"]
    names = c.parameter.tolist() + fixed; b = np.r_[c.estimate.values, np.ones(len(fixed))]
    X = S.RV.X_of(D, names); _, _, ll = MNL(X, names, D["av"], D["C"], weights=D["w"])._logs(b)
    rec = pd.read_csv(f"{TAB}/region_validation_final.csv").set_index("sample").loc["oot"]
    ll0 = float((D["w"] * np.log(D["C"].sum(1) / D["av"].sum(1))).sum())
    return [dict(model="county", version="final", N=len(D["h"]), LL=float((D["w"] * ll).sum()), LL0=ll0),
            dict(model="county", version="model of record", N=int(rec.N), LL=float(rec.LL), LL0=float(rec.LL0))]


def dwelling():
    oot = pd.read_parquet(f"{S.WORK}/pums_movers_oot.parquet"); pool = pd.read_parquet(f"{S.WORK}/pums_pool_oot.parquet")
    DW.RNG = np.random.default_rng(2019)
    alt, av = DW.sample_alts(oot, pool, 30); C = np.zeros_like(av); C[:, 0] = True
    out = []
    df = pd.read_csv(f"{HERE}/r06_fit.csv"); fin = df[df.validation_LL.notna()].iloc[0]; best = fin.model
    cf = pd.read_csv(f"{HERE}/r06_coef.csv"); cf = cf[cf.model == best].set_index("parameter").estimate
    sp = set(fin.spec.split(";")) if isinstance(fin.get("spec"), str) else {"type_inter", "age_bands", "income_slope"}
    DW.build_X = R6.build_X; X, nm = DW.build_X(oot, alt, sp); assert not cf.reindex(nm).isna().any()
    out.append(dict(model="dwelling", version="final", N=len(oot), LL=float(MNL(X, nm, av, C).loglik_obs(cf.reindex(nm).values).sum())))
    DW.build_X = R6.R4._build
    b0 = np.load(f"{S.WORK}/dwelling_beta.npy"); n0 = pd.read_csv(f"{S.WORK}/dwelling_names.csv").iloc[:, 0].tolist()
    sp0 = set(json.load(open(f"{S.WORK}/dwelling_final.json"))["spec"]); X0, nm0 = DW.build_X(oot, alt, sp0); assert nm0 == n0
    out.append(dict(model="dwelling", version="model of record", N=len(oot), LL=float(MNL(X0, nm0, av, C).loglik_obs(b0).sum())))
    ll0 = float(np.log(1.0 / av.sum(1)).sum())
    for r in out: r["LL0"] = ll0
    return out


def main():
    rows = county() + dwelling()
    for r in rows: r["LL_per_obs"] = r["LL"] / r["N"]; r["rho2"] = 1 - r["LL"] / r["LL0"]
    pd.DataFrame(rows).to_csv(f"{HERE}/r09_oot.csv", index=False); print(pd.DataFrame(rows).round(4).to_string())


if __name__ == "__main__":
    main()
