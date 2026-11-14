#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/residential/r12_zone_acc_split.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Zone x structure-type part (2026-11-10): non-work accessibility split into shopping and services/other accessibility, replacing
the pooled non-work main term (its interactions with the household stay on the pooled term), on the chosen form of r08 (multimodal
impedance).  Per-purpose rows before pooling: accessibility_new/accessibility_2016_new_detail.csv, A_ls of the purposes 'shopping'
and 'other'.  Same households and draws; non-nested, compared by BIC on the estimation half among the forms whose accessibility terms have the
expected (+) sign; validation full-set LL of each.  A shopping-only form is reported for information.
    python3 r12_zone_acc_split.py   ->  r12_fit.csv, r12_coef.csv"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r03_sequence as R3   # noqa: E402
Z = R3.Z
from mnl import MNL   # noqa: E402
SCR = os.environ.get("SCRATCH", "/tmp")


def main():
    det = pd.read_csv(f"{V}/side_experiments/respec_2026-11/step_by_step/accessibility_new/accessibility_2016_new_detail.csv")   # PATH (package): per-purpose detail, not copied (used only by the split forms, not by the final model)
    mm = os.environ["ACC_MM"]; f = f"{SCR}/acc_split_2016.csv"
    a = pd.read_csv(mm); b = det[det.purpose.isin(["shopping", "other"])].assign(A=lambda d: d.A_ls)[["zone", "segment", "purpose", "A", "hansen"]]
    pd.concat([a, b]).to_csv(f, index=False)
    base_X = Z.hh_cell_X

    def hx(hh, zi, ti, zd, spec):
        X, names = base_X(hh, zi, ti, zd, spec); seg = f"{hh.inc_group}_{hh.car}"
        for k, p in (("accS", "shopping"), ("accO", "other")):
            if k in spec: X = np.column_stack([X, zd[3][(seg, p)][zi]]); names = names + [k]
        return X, names
    Z.hh_cell_X = hx
    spec = pd.read_csv(f"{HERE}/../data/raw/r03_fit.csv")   # PATH (package);
    spec = spec.query("step == 'final'").spec.iloc[0].split()
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0)]
    est = h[h.half == "estimation"].copy(); val = h[h.half == "validation"].copy()
    Z.ACC_FILE = f; zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1]); drawn = Z.draw(est, zd, cells, 30)
    fd = Z.draw(val, zd, cells, 30, full=True); rows, coef = [], []
    for lab, sp in [("pooled non-work accessibility (r08 chosen form)", spec), ("shopping + services/other accessibility", [v for v in spec if v != "accN"] + ["accS", "accO"]),
                    ("shopping accessibility only (reported, not one of the approved forms)", [v for v in spec if v != "accN"] + ["accS"])]:
        X, names, av, C, ok, _ = Z.build(est, zd, cells, sp, 30, drawn=drawn)
        w = est.wthhfin.values[ok]; m = MNL(X, names, av, C, weights=w / w.mean()).fit()
        Xf, nf, avf, Cf, okf, _ = Z.build(val, zd, cells, sp, 30, full=True, drawn=fd)
        r = dict(model=lab, N=int(ok.sum()), K=m.k, LL=m.ll, BIC=m.k * np.log(ok.sum()) - 2 * m.ll, validation_LL_fullset=float(MNL(Xf, nf, avf, Cf).loglik_obs(m.b).sum()))
        tt = dict(zip(m.names, m.b)); r["sign_ok"] = all(tt.get(k, 1) > 0 for k in ("accN", "accS", "accO"))
        rows.append(r); t = m.table(); t.insert(0, "model", lab); coef.append(t); print(r, flush=True); print(t[t.parameter.str.startswith("acc")].round(3).to_string(), flush=True)
    R = pd.DataFrame(rows); ok = R.sign_ok & ~R.model.str.contains("not one of"); R["chosen"] = ok & (R.BIC == R.BIC[ok].min())   # BIC among the approved forms with expected signs (+)
    R.to_csv(f"{HERE}/r12_fit.csv", index=False); pd.concat(coef).to_csv(f"{HERE}/r12_coef.csv", index=False)
    print("chosen:", R[R.chosen].model.iloc[0])


if __name__ == "__main__":
    main()
