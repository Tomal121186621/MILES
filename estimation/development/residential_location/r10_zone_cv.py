#!/usr/bin/env python3
"""Zone x structure-type part: 5-fold cross-validation of the final specification with car-based and with multimodal
accessibility (r08_zone_multimodal.py).  The survey has no later sample, and its validation half was used to compare forms, so
the comparison is repeated on five folds of all households (both halves): estimate on four folds (30 sampled cells), evaluate the
held-out fold on the full choice set.
    python3 estimation/development/residential_location/r10_zone_cv.py   ->  r10_cv.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/residential"   # results of this step (data); CODE = this folder
import r03_sequence as R3   # noqa: E402
Z = R3.Z
from mnl import MNL   # noqa: E402

V = f"{WORKSPACE}"


def main():
    spec = pd.read_csv(f"{HERE}/r03_fit.csv").query("step == 'final'").spec.iloc[0].split()
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0)].reset_index(drop=True)
    fold = np.random.default_rng(5).integers(0, 5, len(h)); rows = []
    forms = [("car-based", os.environ.get("ACC_CAR", f"{V}/data/accessibility_2016.csv")), ("multimodal", os.environ.get("ACC_MM", f"{HERE}/accessibility_2016_multimodal.csv"))]
    zds = {}
    for lab, f in forms:
        Z.ACC_FILE = f; zd = Z.zone_data(); zds[lab] = (zd, Z.cells_of_region(zd[0], zd[1]))
    for k in range(5):
        tr, te = h[fold != k].copy(), h[fold == k].copy()
        zd0, cells0 = zds["car-based"]; drawn = Z.draw(tr, zd0, cells0, 30); fd = Z.draw(te, zd0, cells0, 30, full=True)
        for lab, _ in forms:
            zd, cells = zds[lab]
            X, names, av, C, ok, _ = Z.build(tr, zd, cells, spec, 30, drawn=drawn)
            w = tr.wthhfin.values[ok]; m = MNL(X, names, av, C, weights=w / w.mean()).fit()
            Xf, nf, avf, Cf, okf, _ = Z.build(te, zd, cells, spec, 30, full=True, drawn=fd)
            ll = float(MNL(Xf, nf, avf, Cf).loglik_obs(m.b).sum())
            rows.append(dict(fold=k, form=lab, N_train=int(ok.sum()), N_test=int(okf.sum()), LL_test=ll))
            print(k, lab, round(ll, 1), flush=True)
    r = pd.DataFrame(rows); r.to_csv(f"{HERE}/r10_cv.csv", index=False)
    s = r.pivot(index="fold", columns="form", values="LL_test"); s["diff"] = s["multimodal"] - s["car-based"]
    print(s.round(1).to_string()); print("total", s.sum().round(1).to_dict())


if __name__ == "__main__":
    main()
