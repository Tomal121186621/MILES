#!/usr/bin/env python3
"""Residential location, level 3 (dwelling): age of the oldest member in full instead of the member-65+ dummy, in the
structure-type interactions of the current model (s04_dwelling.py, D4p).  Forms compared by BIC on the estimation half (same
draws): member 65+ (current), age linear ((age - 50) / 10), bands under 35 / 50-64 / 65+ (reference 35-49).  The validation
half is used once, for the chosen model and the current model.
    python3 r04_dwelling_age.py   ->  r04_fit.csv, r04_coef.csv"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"
sys.path.insert(0, f"{V}/2_silo/resloc"); os.chdir(f"{V}/2_silo/resloc")
import s04_dwelling as DW   # noqa: E402
from rc import WORK   # noqa: E402

D4P = {"type_inter", "group_price", "pool_bur_hi_top"}
_build = DW.build_X


def build_X(h, alt, spec):
    X, names = _build(h, alt, spec); a = h.age_max.values.astype(float)
    if "age_linear" in spec or "age_bands" in spec:
        keep = [i for i, n in enumerate(names) if not n.endswith("_x_age65")]
        X = X[:, :, keep]; names = [names[i] for i in keep]; add = []
        for ty in DW.TYPES:
            d = (alt["dtype"] == ty).astype(float)
            if "age_linear" in spec: add.append((f"{ty}_x_age", d * ((a - 50) / 10)[:, None]))
            else:
                for nm, m in [("ageU35", a < 35), ("age50_64", (a >= 50) & (a < 65)), ("age65", a >= 65)]: add.append((f"{ty}_x_{nm}", d * m[:, None]))
        X = np.concatenate([X] + [v[:, :, None] for _, v in add], axis=2); names = names + [n for n, _ in add]
    return X, names


def main():
    DW.build_X = build_X
    mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    drawn = DW.sample_alts(est, pool, 30); rows, coef, ms = [], [], {}
    for lab, sp in [("D4p current model (member 65+)", D4P), ("age linear instead of 65+", D4P | {"age_linear"}),
                    ("age bands instead of 65+", D4P | {"age_bands"})]:
        m, _ = DW.estimate(est, pool, 30, sp, lab, drawn); ms[lab] = (m, sp)
        s = m.stats(lab); rows.append(s); t = m.table(); t.insert(0, "model", lab); coef.append(t)
        print(lab, f"K {m.k} LL {m.ll:.1f} BIC {s['BIC']:.1f}", flush=True)
        print(t[t.parameter.str.contains("_x_age")].round(3).to_string(), flush=True)
    best = min(rows, key=lambda r: r["BIC"])["model"]
    for lab in dict.fromkeys(["D4p current model (member 65+)", best]):
        m, sp = ms[lab]; ll, ll0, *_ = DW.predictive_ll(m, val, pool, 30, sp)
        next(r for r in rows if r["model"] == lab)["validation_LL"] = ll; print(lab, "validation LL", round(ll, 1), flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/r04_fit.csv", index=False); pd.concat(coef).to_csv(f"{HERE}/r04_coef.csv", index=False)


if __name__ == "__main__":
    main()
