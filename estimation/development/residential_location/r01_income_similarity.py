#!/usr/bin/env python3
"""Residential location, level 2 (zone x dwelling type): income similarity, a standard variable of the literature (households
sort by income; Lee and Waddell 2010, Guevara 2010), added to the current model (2_silo/resloc/s05_zone.py, Z7, final inputs).
  sim     share of the zone's households in the household's own income group (2016 synthetic population; groups under $40k,
          $40-75k, $75-125k, $125k+), so each household sees the share of its own group
Same estimation households, same 30-cell choice sets (one set of draws), same weights as s05_zone.py.  Fit: estimation half;
log-likelihood over the full choice set on both halves (as s05_zone.py validates).
    python3 estimation/development/residential_location/r01_income_similarity.py   ->  r01_fit.csv, r01_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/residential"   # results of this step (data); CODE = this folder
V = f"{WORKSPACE}"
sys.argv = [sys.argv[0], os.environ.get("ACC_CAR", f"{V}/data/accessibility_2016.csv"), "final"]   # ACC_CAR: car-based accessibility file
sys.path.insert(0, f"{MILES_HOME}/landuse/lib/residential"); os.chdir(f"{MILES_HOME}/landuse/lib/residential")
import s05_zone as Z   # noqa: E402
from rc import MICRO, ZONE_IDS, INC_GROUPS, inc_group   # noqa: E402
from mnl import MNL, lr_test   # noqa: E402


def own_group_share():
    hh = pd.read_csv(f"{MICRO}/hh_2016.csv", usecols=["dwelling", "income"]); dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["id", "zone"])
    hh["zone"] = hh.dwelling.map(dd.set_index("id").zone); hh["g"] = inc_group(hh.income.clip(lower=1))
    S = pd.crosstab(hh.zone, hh.g, normalize="index").reindex(index=ZONE_IDS, columns=INC_GROUPS).fillna(0.0)
    return S.values


SH = own_group_share()
base_X = Z.hh_cell_X


def hh_cell_X(hh, zi, ti, zd, spec):
    X, names = base_X(hh, zi, ti, zd, spec)
    if "sim" in spec:
        X = np.column_stack([X, SH[zi, INC_GROUPS.index(hh.inc_group)]]); names = names + ["sim"]
    return X, names


def main():
    Z.hh_cell_X = hh_cell_X
    h, _ = Z.load_rts(); zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1])
    est = h[h.half == "estimation"].copy(); val = h[h.half == "validation"].copy()
    drawn = Z.draw(est, zd, cells, 30)
    full = {nm: Z.draw(hs, zd, cells, 30, full=True) for nm, hs in (("estimation", est), ("validation", val))}
    base = Z.SPECS[Z.FINAL]; fit, coef = [], []; prev = None
    for lab, sp in [("Z7 current model", base), ("Z7 + income similarity", base + ["sim"])]:
        X, names, av, C, ok, _ = Z.build(est, zd, cells, set(sp), 30, drawn=drawn)
        w = est.wthhfin.values[ok]; w = w / w.mean(); m = MNL(X, names, av, C, weights=w).fit()
        row = dict(model=lab, K=m.k, LL=m.ll, BIC=m.k * np.log(ok.sum()) - 2 * m.ll, converged=m.converged)
        if prev is not None: row.update(zip(["LR", "df", "p"], lr_test(prev.ll, m.ll, m.k - prev.k)))
        for nm, hs in (("estimation", est), ("validation", val)):
            Xf, nf, avf, Cf, okf, _ = Z.build(hs, zd, cells, set(sp), 30, full=True, drawn=full[nm])
            assert nf == names
            row[f"fullset_LL_{nm}"] = float(MNL(Xf, nf, avf, Cf).loglik_obs(m.b).sum())
        fit.append(row); prev = m
        t = m.table(); t.insert(0, "model", lab); coef.append(t)
        print(row, flush=True); print(t.to_string(), flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/r01_fit.csv", index=False); pd.concat(coef).to_csv(f"{HERE}/r01_coef.csv", index=False)


if __name__ == "__main__":
    main()
