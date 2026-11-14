#!/usr/bin/env python3
"""Dwelling level of the residential location model: writes the estimation and hold-out tables of
model/estimate_residential_dwelling.py, with exactly the sampled choice sets of the original estimation.

Same calls as r06_dwelling_income.py: s04_dwelling module imported fresh (its random generator, seed 20261022, unused before),
one draw of 30 alternatives for the estimation sample (DW.sample_alts(est, pool, 30)), then one draw for the validation
sample (the draw of DW.predictive_ll, the next call of the same generator).  Final specification: the 'spec' column of the
last row of r06_fit.csv ("previous without MH_x_child").  The design columns are those of r06_dwelling_income.build_X.
Check: the log-likelihood at the estimates of r06_coef.csv is recomputed with the original estimator (mnl.MNL) on the exported
data and compared with r06_fit.csv (estimation) and the validation value.
    python3 build_estimation_data.py   ->  ../data/estimation/dwelling_estimation.parquet, ../data/holdout/dwelling_holdout.parquet"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r06_dwelling_income as R6   # noqa: E402  (imports r04_dwelling_age -> s04_dwelling: generator seeded, not used yet)
from mnl import MNL   # noqa: E402
DW = R6.DW
OUT = os.path.abspath(f"{HERE}/../data"); RAWD = f"{OUT}/raw"
J = 30


def table(h, alt, av, spec):
    X, names = DW.build_X(h, alt, spec)
    d = {"household": h.SERIALNO.values, "puma7": h.puma7.values, "income_2016usd": h.income.values, "persons": h.NP.values,
         "children_any": (h.n_child.values > 0).astype(int), "age_oldest": h.age_max.values, "choice": np.zeros(len(h), int)}
    for j in range(J):
        d[f"av_{j}"] = av[:, j].astype(int)
        d[f"cost_{j}"] = alt["cost"][:, j]; d[f"bedrooms_{j}"] = alt["bed"][:, j]; d[f"type_{j}"] = alt["dtype"][:, j].astype(str)
        for k, n in enumerate(names):
            d[f"{n}_{j}"] = X[:, j, k]
    return pd.DataFrame(d), X, names


def main():
    DW.build_X = R6.build_X
    mv = pd.read_parquet(f"{DW.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{DW.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    fit = pd.read_csv(f"{RAWD}/r06_fit.csv"); fin = fit[fit.validation_LL.notna()].iloc[0]; spec = set(fin.spec.split(";"))
    coef = pd.read_csv(f"{RAWD}/r06_coef.csv"); coef = coef[coef.model == fin.model].set_index("parameter").estimate
    drawn = DW.sample_alts(est, pool, J)        # = r06 main: first draw
    drawn_val = DW.sample_alts(val, pool, J)    # = DW.predictive_ll(m, val, pool, 30, sp): second draw
    for nm, h, (alt, av), f, ref in (("estimation", est, drawn, "estimation/dwelling_estimation.parquet", fin.LL),
                                    ("validation", val, drawn_val, "holdout/dwelling_holdout.parquet", fin.validation_LL)):
        df, X, names = table(h, alt, av, spec)
        b = coef.reindex(names).values; assert not np.isnan(b).any()
        C = np.zeros_like(av); C[:, 0] = True
        ll = MNL(X, names, av, C).loglik_obs(b).sum()
        print(f"{nm}: N {len(h)}, K {len(names)}, LL at r06 estimates {ll:.4f} (log {ref:.4f}), min available {av.sum(1).min()}")
        assert abs(ll - ref) < 1e-6
        df.to_parquet(f"{OUT}/{f}", index=False)
    pd.Series(names, name="design_column").to_csv(f"{OUT}/estimation/design_columns.csv", index=False)


if __name__ == "__main__":
    main()
