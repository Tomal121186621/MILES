#!/usr/bin/env python3
"""Zone x structure-type level of the residential location model: writes the estimation and hold-out tables of
model/estimate_residential_zone_structure_type.py, with exactly the sampled choice sets of the original estimation.

Same calls as r12_zone_acc_split.py (final model = its 'pooled non-work accessibility' row, identical to the chosen form of
r08_zone_multimodal.py): RTS households with a known age (s05_zone.load_rts), estimation / validation halves, multimodal
accessibility (ACC_MM, default 00_shared_data/accessibility/accessibility_2016_new_multimodal.csv), s05_zone module imported
fresh (random generator seed 1022, unused before), one draw of 30 cells for the estimation half (Z.draw(est, ..., 30)); the
validation half on the full choice set (all cells of the household's county; no random draw).  Design columns: those of
r03_sequence.hh_cell_X for the final specification (r03_fit.csv, step 'final').  Weights: RTS household weight wthhfin,
divided by its mean over the estimation households used (WESML).
Check: weighted log-likelihood at the estimates of r12_coef.csv with the original estimator (mnl.MNL) = r12_fit.csv.
    python3 build_estimation_data.py   ->  ../data/estimation/zone_estimation.parquet, ../data/holdout/zone_holdout_fullset.parquet"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
SHD = os.path.abspath(f"{HERE}/../../../00_shared_data")
os.environ.setdefault("ACC_CAR", f"{SHD}/accessibility/accessibility_2016_new.csv")          # as run_residential_chain_1110.sh
os.environ.setdefault("ACC_MM", f"{SHD}/accessibility/accessibility_2016_new_multimodal.csv")
import r03_sequence as R3   # noqa: E402  (zone part with the r01 / r02 / land-use extensions)
from mnl import MNL   # noqa: E402
from rc import ZONE_IDS   # noqa: E402
Z = R3.Z
OUT = os.path.abspath(f"{HERE}/../data"); RAWD = f"{OUT}/raw"
J = 30


def main():
    spec = pd.read_csv(f"{RAWD}/r03_fit.csv").query("step == 'final'").spec.iloc[0].split()
    fit = pd.read_csv(f"{RAWD}/r12_fit.csv"); row = fit[fit.chosen].iloc[0]
    coef = pd.read_csv(f"{RAWD}/r12_coef.csv"); coef = coef[coef.model == row.model].set_index("parameter").estimate
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0)]
    est = h[h.half == "estimation"].copy(); val = h[h.half == "validation"].copy()
    Z.ACC_FILE = os.environ["ACC_MM"]; zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1])
    drawn = Z.draw(est, zd, cells, J)                          # = r12 main: first draw of the generator
    X, names, av, C, ok, meta = Z.build(est, zd, cells, spec, J, drawn=drawn)
    w = est.wthhfin.values[ok]; w = w / w.mean()
    b = coef.reindex(names).values; assert not np.isnan(b).any()
    ll = (w * MNL(X, names, av, C, weights=w).loglik_obs(b)).sum()
    print(f"estimation: N {ok.sum()}, K {len(names)}, weighted LL at r12 estimates {ll:.4f} (log {row.LL:.4f})"); assert abs(ll - row.LL) < 1e-6
    e2 = est[ok]
    d = {"household": e2.index.values, "weight": w, "weight_rts_wthhfin": e2.wthhfin.values, "region": zd[0].region.values[[Z.ZIDX[x] for x in e2.zone]],
         "income_2016usd": e2.income.values, "inc_group": e2.inc_group.values, "car": e2.car.values, "children": e2.children.values,
         "age_oldest": e2.age_max.values, "hhsize": e2.hhsize.values, "choice": np.zeros(len(e2), int)}
    for j in range(J):
        d[f"av_{j}"] = av[:, j].astype(int)
        d[f"zone_{j}"] = np.array([ZONE_IDS[zi[j]] if j < len(zi) else -1 for zi, ti in meta])
        d[f"stype_{j}"] = np.array([Z.CT[ti[j]] if j < len(ti) else "NA" for zi, ti in meta])
        for k, n in enumerate(names): d[f"{n}_{j}"] = X[:, j, k]
    pd.DataFrame(d).to_parquet(f"{OUT}/estimation/zone_estimation.parquet", index=False)
    pd.Series(names, name="design_column").to_csv(f"{OUT}/estimation/design_columns.csv", index=False)
    # hold-out: validation half, full choice set (long format: one row per household x cell, chosen cell first)
    fd = Z.draw(val, zd, cells, J, full=True); Xf, nf, avf, Cf, okf, metaf = Z.build(val, zd, cells, spec, J, full=True, drawn=fd)
    llv = MNL(Xf, nf, avf, Cf).loglik_obs(b).sum()
    print(f"validation (full set, unweighted): N {okf.sum()}, LL {llv:.4f} (log {row.validation_LL_fullset:.4f})"); assert abs(llv - row.validation_LL_fullset) < 1e-6
    v2 = val[okf]; rows = []
    for i, (zi, ti) in enumerate(metaf):
        r = pd.DataFrame({"household": v2.index.values[i], "alt": np.arange(len(zi)), "chosen": (np.arange(len(zi)) == 0).astype(int),
                          "zone": ZONE_IDS[zi], "stype": np.array(Z.CT)[ti], "weight_rts_wthhfin": v2.wthhfin.values[i]})
        for k, n in enumerate(nf): r[n] = Xf[i, :len(zi), k]
        rows.append(r)
    pd.concat(rows).to_parquet(f"{OUT}/holdout/zone_holdout_fullset.parquet", index=False)


if __name__ == "__main__":
    main()
