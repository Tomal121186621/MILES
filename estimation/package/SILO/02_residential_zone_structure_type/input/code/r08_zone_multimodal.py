#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/residential/r08_zone_multimodal.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Zone x structure-type part: accessibility with car-based impedance (A, current) against multimodal impedance (A_ls: the
destination models with the ABIT mode-choice logsum as impedance, so transit, walk and bike count), in the final specification
of r03_sequence.py.  Same households and sampled choice sets; non-nested forms compared by BIC on the estimation half; the
validation half (full choice set) is used once, for the chosen form.
    python3 r08_zone_multimodal.py   ->  r08_fit.csv, r08_coef.csv"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r03_sequence as R3   # noqa: E402  (zone part with the r01/r02 extensions)
Z = R3.Z
from mnl import MNL   # noqa: E402

V = os.environ.get("TERP_WORKSPACE", "") + ""


def main():
    car = os.environ.get("ACC_CAR", f"{V}/data/accessibility_2016.csv")
    if os.environ.get("ACC_MM"):
        mm = os.environ["ACC_MM"]; return compare(car, mm)
    d = pd.read_csv(f"{V}/data/accessibility_2016_detail.csv")
    d = d[d.purpose.isin(["work", "nonwork"])]
    ref = pd.read_csv(f"{V}/data/accessibility_2016.csv").merge(d[["zone", "segment", "purpose", "A"]], on=["zone", "segment", "purpose"])
    assert np.allclose(ref.A_x, ref.A_y, atol=1e-3), "detail file differs from the accessibility file"
    mm = f"{HERE}/accessibility_2016_multimodal.csv"
    d.assign(A=d.A_ls)[["zone", "segment", "purpose", "A", "hansen"]].to_csv(mm, index=False)
    return compare(car, mm)


def compare(car, mm):
    spec = pd.read_csv(f"{HERE}/../data/raw/r03_fit.csv")   # PATH (package);
    spec = spec.query("step == 'final'").spec.iloc[0].split()
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0)]
    est = h[h.half == "estimation"].copy(); val = h[h.half == "validation"].copy()
    rows, coef, res = [], [], {}
    drawn = None
    for lab, f in [("car-based accessibility (current)", car), ("multimodal accessibility", mm)]:
        Z.ACC_FILE = f; zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1])
        if drawn is None: drawn = Z.draw(est, zd, cells, 30)
        X, names, av, C, ok, _ = Z.build(est, zd, cells, spec, 30, drawn=drawn)
        w = est.wthhfin.values[ok]; w = w / w.mean(); m = MNL(X, names, av, C, weights=w).fit()
        r = dict(model=lab, N=int(ok.sum()), K=m.k, LL=m.ll, BIC=m.k * np.log(ok.sum()) - 2 * m.ll); rows.append(r); res[lab] = (m, zd, cells)
        t = m.table(); t.insert(0, "model", lab); coef.append(t)
        print(r, flush=True); print(t[t.parameter.str.startswith("acc")].round(3).to_string(), flush=True)
    best = min(rows, key=lambda r: r["BIC"]); m, zd, cells = res[best["model"]]
    fd = Z.draw(val, zd, cells, 30, full=True); Xf, nf, avf, Cf, okf, _ = Z.build(val, zd, cells, spec, 30, full=True, drawn=fd)
    best["validation_LL_fullset"] = float(MNL(Xf, nf, avf, Cf).loglik_obs(m.b).sum()); best["chosen"] = True
    print("chosen", best["model"], "validation LL (full set)", round(best["validation_LL_fullset"], 1), flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/r08_fit.csv", index=False); pd.concat(coef).to_csv(f"{HERE}/r08_coef.csv", index=False)


if __name__ == "__main__":
    main()
