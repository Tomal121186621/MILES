#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/residential/r02_age_hhsize.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Residential location, level 2 (zone x dwelling type): age and household size, added to the current model (s05_zone.py, Z7).
Age is that of the oldest member (the RTS has no householder flag); the current model uses member 65+ x non-work accessibility.
  A1  65+ replaced by age, linear (x non-work accessibility)
  A2  65+ replaced by age bands covering all ages (under 35, 50-64, 65+; reference 35-49) x non-work accessibility
  H1  + (household size - 1) x non-work accessibility
  H2  + (household size - 1) x ln zone cost
Same households, draws and weights as s05_zone.py; fit on the estimation half, full-choice-set log-likelihood on both halves.
    python3 r02_age_hhsize.py   ->  r02_fit.csv, r02_coef.csv"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"
sys.argv = [sys.argv[0], f"{HERE}/../../../00_shared_data/accessibility/accessibility_2016.csv", "final"]   # PATH (package)
sys.path.insert(0, HERE)   # PATH (package): copies of the 2_silo/resloc modules are in this folder
import s05_zone as Z   # noqa: E402
from mnl import MNL, lr_test   # noqa: E402

base_X = Z.hh_cell_X


def hh_cell_X(hh, zi, ti, zd, spec):
    X, names = base_X(hh, zi, ti, zd, spec); an = zd[3][(f"{hh.inc_group}_{hh.car}", "nonwork")][zi]; a = hh.age_max; s = min(hh.hhsize, 6) - 1
    add = {"accN_x_age": an * (a - 50) / 10, "accN_x_ageU35": an * (a < 35), "accN_x_age50_64": an * ((a >= 50) & (a < 65)),
           "accN_x_hhs": an * s, "lncost_x_hhs": zd[2][zi] * s}
    for k, v in add.items():
        if k in spec: X = np.column_stack([X, v]); names = names + [k]
    return X, names


def main():
    Z.hh_cell_X = hh_cell_X
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0)]
    zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1])
    est = h[h.half == "estimation"].copy(); val = h[h.half == "validation"].copy()
    drawn = Z.draw(est, zd, cells, 30); full = {nm: Z.draw(hs, zd, cells, 30, full=True) for nm, hs in (("estimation", est), ("validation", val))}
    z7 = Z.SPECS[Z.FINAL]; no65 = [v for v in z7 if v != "accN_x_age65"]
    runs = [("Z7 current model", z7, None), ("A1 age linear instead of 65+", no65 + ["accN_x_age"], None),
            ("A2 age bands instead of 65+", no65 + ["accN_x_ageU35", "accN_x_age50_64", "accN_x_age65"], 0),
            ("H1 + household size x non-work accessibility", z7 + ["accN_x_hhs"], 0),
            ("H2 + household size x ln zone cost", z7 + ["lncost_x_hhs"], 0)]
    fit, coef, ms = [], [], []
    for lab, sp, ref in runs:
        X, names, av, C, ok, _ = Z.build(est, zd, cells, sp, 30, drawn=drawn)
        w = est.wthhfin.values[ok]; w = w / w.mean(); m = MNL(X, names, av, C, weights=w).fit(); ms.append(m)
        row = dict(model=lab, K=m.k, LL=m.ll, BIC=m.k * np.log(ok.sum()) - 2 * m.ll, converged=m.converged)
        if ref is not None and m.k > ms[ref].k: row.update(zip(["LR", "df", "p"], lr_test(ms[ref].ll, m.ll, m.k - ms[ref].k)))
        for nm, hs in (("estimation", est), ("validation", val)):
            Xf, nf, avf, Cf, okf, _ = Z.build(hs, zd, cells, sp, 30, full=True, drawn=full[nm])
            row[f"fullset_LL_{nm}"] = float(MNL(Xf, nf, avf, Cf).loglik_obs(m.b).sum())
        fit.append(row); t = m.table(); t.insert(0, "model", lab); coef.append(t)
        print(row, flush=True); print(t.to_string(), flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/r02_fit.csv", index=False); pd.concat(coef).to_csv(f"{HERE}/r02_coef.csv", index=False)


if __name__ == "__main__":
    main()
