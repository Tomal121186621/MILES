#!/usr/bin/env python3
"""County level of the residential location model: writes the estimation and hold-out tables of
model/estimate_residential_county.py.

Same data as r05_region_sequence.py run with 'final newiv': county data of r07_county_iv.py (county_data_est.pkl /
county_data_val.pkl: ACS PUMS movers, origin variables, inclusive values IV_B (zone x structure type) and IV_A (dwelling) of the
final lower-level models) completed by r05_region_sequence.add_growth (school learning growth, age x previous county, adjacent
county, car time x ln income).  Final model: step 'Ja' of r05_fit.csv.  Choice set: all 44 counties; availability 'av'
(counties with dwellings and cells); observed outcome = the set of counties of the destination PUMA ('C', a PUMA can span
several counties: P = sum of their probabilities); weight = expected in-area share of destination and origin, divided by its
mean (column 'weight').  Inclusive values enter as data, exactly as estimated (no recomputation here).
Check: weighted log-likelihood at the estimates of r05_coef.csv (step Ja) with the original estimator (mnl.MNL) = r05_fit.csv,
and the validation value of r05.log.
    python3 build_estimation_data.py   ->  ../data/estimation/county_estimation.parquet, ../data/holdout/county_holdout.parquet"""
import os, sys, pickle
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], "final", "newiv"]   # the arguments of the original run (run_residential_chain_1110.sh); read by s06/s07 at import
import r05_region_sequence as R5   # noqa: E402  (module-level: county adjacency from zones.shp, car skim)
from mnl import MNL   # noqa: E402
OUT = os.path.abspath(f"{HERE}/../data"); RAWD = f"{OUT}/raw"
VAL_LL = -4027.4921561560977   # r05.log: "final Ja validation LL"


def table(D, names, b):
    X, nm = R5.RG.design(D, names); assert nm == names
    av, C, w = D["av"], D["C"], D["w"]
    ll = (w * MNL(X, names, av, C, weights=w).loglik_obs(b)).sum()
    d = {"household": D["h"].SERIALNO.values, "weight": w, "income_2016usd": D["h"].income.values, "children_any": (D["h"].n_child.values > 0).astype(int),
         "age_oldest": D["h"].age_max.values, "origin_migpuma": D["h"].mig7.values, "dest_puma": D["h"].puma7.values}
    for j, r in enumerate(D["regs"]):
        d[f"av_{j}"] = av[:, j].astype(int); d[f"chosen_set_{j}"] = (C[:, j] & av[:, j]).astype(int)
        for k, n in enumerate(names):
            x = X[:, j, k]; assert np.isfinite(x[av[:, j]]).all()
            d[f"{n}_{j}"] = np.where(av[:, j], x, 0.0)      # unavailable counties: value 0 (IV_B is -inf there); never used
        d[f"d1_{j}"] = np.where(av[:, j], D["F"]["d1"][:, j], 0.0)   # car time under 20 min: coefficient fixed at 0 in the model
    return pd.DataFrame(d), ll


def main():
    fit = pd.read_csv(f"{RAWD}/r05_fit.csv"); row = fit[fit.step == "Ja"].iloc[0]; assert bool(row.final)
    coef = pd.read_csv(f"{RAWD}/r05_coef.csv"); coef = coef[coef.step == "Ja"]
    names = coef.parameter.tolist(); b = coef.estimate.values
    print("county data from", R5.CD)
    for tag, f, ref in (("est", "estimation/county_estimation.parquet", row.LL), ("val", "holdout/county_holdout.parquet", VAL_LL)):
        D = R5.add_growth(pickle.load(open(f"{R5.CD}/county_data_{tag}.pkl", "rb")))
        df, ll = table(D, names, b)
        print(f"{tag}: N {len(df)}, counties {len(D['regs'])}, K {len(names)}, weighted LL at r05 estimates {ll:.4f} (log {ref:.4f})")
        assert abs(ll - ref) < 1e-6
        df.to_parquet(f"{OUT}/{f}", index=False)
        if tag == "est":
            z = pd.read_csv(f"{R5.WORK}/geo_zone.csv"); cf = z.groupby("region").COUNTYFIPS.agg(lambda s: ";".join(str(x) for x in sorted(set(s))))
            pd.DataFrame({"j": range(len(D["regs"])), "silo_region": D["regs"], "county_fips": cf.reindex(D["regs"]).values}).to_csv(
                f"{OUT}/estimation/county_index.csv", index=False)
    pd.Series(names, name="design_column").to_csv(f"{OUT}/estimation/design_columns.csv", index=False)


if __name__ == "__main__":
    main()
