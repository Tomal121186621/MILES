#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/residential/r06_dwelling_income.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Residential location, dwelling part: income-group coefficients (four per term) against one continuous income interaction per
term (term and term x ln(income / $50k)), on the model with age bands (r04).  Forms compared by BIC on the estimation half (same
draws).  Then, on the chosen form (collinearity/silo_notes.md): cost share below 30 % x ln income dropped (est r -0.82 with
ln cost x ln income, t 0.16); single-family attached x household size, mobile home x household size and mobile home x children
each dropped if BIC falls (in that order).  The validation half is used once, for the final model ('spec' column: its terms).
    python3 r06_dwelling_income.py   ->  r06_fit.csv, r06_coef.csv"""
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r04_dwelling_age as R4   # noqa: E402
DW = R4.DW

PRICE = ["bur_lo", "bur_mid", "bur_hi", "lncost", "bed_short", "bed_extra", "new5"]


def build_X(h, alt, spec):
    X, names = R4.build_X(h, alt, spec)
    if "income_slope" in spec:
        lninc = DW.hh_terms(h)["lninc"][:, None]
        X = np.concatenate([X] + [X[:, :, names.index(v)][:, :, None] * lninc[:, :, None] for v in PRICE], axis=2)
        names = names + [f"{v}_x_lninc" for v in PRICE]
    keep = [i for i, n in enumerate(names) if "-" + n not in spec]
    return X[:, :, keep], [names[i] for i in keep]


def main():
    DW.build_X = build_X
    mv = pd.read_parquet(f"{R4.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R4.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    drawn = DW.sample_alts(est, pool, 30); rows, coef, ms = [], [], {}
    base = {"type_inter", "age_bands"}
    for lab, sp in [("Common price, bedroom and new-dwelling terms", base),
                    ("Income-group terms (four groups)", base | {"group_price", "pool_bur_hi_top"}),
                    ("Terms and terms x ln income", base | {"income_slope"})]:
        m, _ = DW.estimate(est, pool, 30, sp, lab, drawn); ms[lab] = (m, sp)
        s = m.stats(lab); rows.append(s); t = m.table(); t.insert(0, "model", lab); coef.append(t)
        print(lab, f"K {m.k} LL {m.ll:.1f} BIC {s['BIC']:.1f}", flush=True)
        print(t[t.parameter.str.match("|".join(PRICE))].round(3).to_string(), flush=True)
    best = min(rows[1:], key=lambda r: r["BIC"])["model"]
    m, sp = ms[best]; cur = next(r for r in rows if r["model"] == best); cur["spec"] = ";".join(sorted(sp))
    for d, forced in [("bur_lo_x_lninc", True), ("SFA_x_size", False), ("MH_x_size", False), ("MH_x_child", False)]:
        lab = f"{best}, without {d}" if forced else f"previous without {d}"; sp2 = sp | {"-" + d}
        m2, _ = DW.estimate(est, pool, 30, sp2, lab, drawn); s = m2.stats(lab); t = m2.table(); t.insert(0, "model", lab); coef.append(t)
        lr = 2 * (m.ll - m2.ll); ok = forced or s["BIC"] < cur["BIC"]
        s.update(LR=lr, df=m.k - m2.k, p=float(chi2.sf(lr, m.k - m2.k)), decision=("dropped (collinearity)" if forced else "dropped: BIC") if ok else "not dropped: BIC",
                 spec=";".join(sorted(sp2))); rows.append(s)
        print(lab, f"K {m2.k} LL {m2.ll:.1f} BIC {s['BIC']:.1f} LR {lr:.2f}", s["decision"], flush=True)
        if ok: m, sp, cur = m2, sp2, s
    ll, *_ = DW.predictive_ll(m, val, pool, 30, sp)
    cur["validation_LL"] = ll; print(cur["model"], "validation LL", round(ll, 1), flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/r06_fit.csv", index=False); pd.concat(coef).to_csv(f"{HERE}/r06_coef.csv", index=False)


if __name__ == "__main__":
    main()
