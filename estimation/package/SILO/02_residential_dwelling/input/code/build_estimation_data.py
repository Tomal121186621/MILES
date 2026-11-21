#!/usr/bin/env python3
"""Dwelling level of the two-level residential location model: writes the estimation and hold-out tables of
model/estimate_residential_dwelling.py with exactly the sampled choice sets of the original estimation.

One generator, seed final_spec.SEED, reset before the first draw: the mover's dwelling plus 29 dwellings drawn uniformly from the
dwellings of the same PUMA occupied by households that moved in within 12 months, first for the estimation half, then for the
validation half (two_level.sample).  Design: final_spec.dw_final (18 columns).
Check: the log-likelihood at the original estimates (../data/raw/original_estimates.csv), recomputed with the original estimator
(mnl.MNL) on the exported arrays, equals the original fit (../data/raw/original_fit.csv), estimation and validation.
    ~/.venvs/biogeme/bin/python build_estimation_data.py
    ->  ../data/estimation/dwelling_estimation.parquet, design_columns.csv; ../data/holdout/dwelling_holdout.parquet"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import final_spec as F   # noqa: E402  (sets the switches of two_level and imports it)
R = F.R
from mnl import MNL      # noqa: E402
OUT = os.path.abspath(f"{HERE}/../data"); RAWD = f"{OUT}/raw"
J = R.J


def table(h, alt, av, X):
    lninc = np.log(np.maximum(h.income.values, 5000.0) / 50000.0)
    d = {"household": h.SERIALNO.values, "puma7": h.puma7.values, "survey_year": h.svy.values, "income_2016usd": h.income.values,
         "lninc": lninc, "persons": h.NP.values, "bedroom_need": np.where(h.NP.values <= 1, 1, np.minimum(h.NP.values - 1, 4)),
         "children_any": (h.n_child.values > 0).astype(int), "age_oldest": h.age_max.values, "choice": np.zeros(len(h), int)}
    for j in range(J):
        d[f"av_{j}"] = av[:, j].astype(int)
        d[f"cost_{j}"] = alt["cost"][:, j]; d[f"bedrooms_{j}"] = alt["bed"][:, j]; d[f"type_{j}"] = alt["dtype"][:, j].astype(str)
        for k, n in enumerate(F.DWF):
            d[f"{n}_{j}"] = X[:, j, k]
    return pd.DataFrame(d)


def main():
    mv = pd.read_parquet(f"{R.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    fit = pd.read_csv(f"{RAWD}/original_fit.csv").set_index("level").loc["dwelling within PUMA"]
    coef = pd.read_csv(f"{RAWD}/original_estimates.csv"); b = coef[coef.level == "dwelling"].set_index("param").coef.reindex(F.DWF).values
    R.RNG = np.random.default_rng(F.SEED)
    for nm, h, f, ref in (("estimation", est, "estimation/dwelling_estimation.parquet", fit.LL),
                          ("validation", val, "holdout/dwelling_holdout.parquet", fit.validation_LL)):
        alt, av = R.sample(h, pool); X = F.dw_final(h, alt)
        C = np.zeros_like(av); C[:, 0] = True
        ll = float(MNL(X, F.DWF, av, C).loglik_obs(b).sum())
        print(f"{nm}: N {len(h)}, K {len(F.DWF)}, LL at the original estimates {ll:.4f} (original {ref:.4f}), available {av.sum(1).min()}-{av.sum(1).max()}")
        assert abs(ll - ref) < 1e-6
        table(h, alt, av, X).to_parquet(f"{OUT}/{f}", index=False)
    pd.Series(F.DWF, name="design_column").to_csv(f"{OUT}/estimation/design_columns.csv", index=False)


if __name__ == "__main__":
    main()
