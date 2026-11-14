#!/usr/bin/env python3
"""Tour mode choice: children under 16 in the household (dummy), alternative-specific on every non-reference mode, added to the
m06 model (work and other: + parking + stops; shopping and school: + parking).  Same test as m06: likelihood-ratio test at 5 %,
BIC, and the validation-half log-likelihood (work: WESML-weighted).
    ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice/m07_children.py   ->  m07_fit.csv, m07_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
import m06_literature as L6   # noqa: E402
M = L6.M
BLOCKS = {"work": ["park", "stops"], "shopping": ["park"], "other": ["park", "stops"], "school": ["park"]}


def data(half, seg):
    g = L6.data(half, seg)
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet"); f = M.features2(t, 0.5); f["choice"] = t.choice2.values
    ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(f.choice.values)])
    k = t.children.values[(t.segment.eq(seg) & ok).values]; assert len(k) == len(g)
    g["kids"] = (k > 0).astype(float); return g


def main():
    os.chdir(f"{HERE}/bio"); fit, coef = [], []
    for seg in ["work", "shopping", "other", "school"]:
        df, ho = data("estimation", seg), data("validation", seg)
        alts = [a for a in L6.G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        base = dict(L6.BASE[seg]); res = {}
        for tag, extra in [("base", base["extra"]), ("kids", base["extra"] + ["kids"])]:
            L6.BASE[seg] = dict(base, extra=extra)
            t, x = L6.estimate(seg, df, ho, alts, BLOCKS[seg], f"m07_{seg}_{tag}"); res[tag] = x
            for n, y in t.iterrows(): coef.append(dict(segment=seg, model=tag, param=n, coef=y.Value, t=y["Robust t-stat."]))
        L6.BASE[seg] = base
        b, k = res["base"], res["kids"]; lr = 2 * (k["LL"] - b["LL"]); dk = k["K"] - b["K"]; p = float(chi2.sf(lr, dk))
        k.update(LR=lr, p=p, kept=(p < 0.05) and (k["BIC"] < b["BIC"])); fit += [b, k]
        print(f"{seg}: share with children {df.kids.mean():.2f}; LL {b['LL']:.1f} -> {k['LL']:.1f}, LR {lr:.1f} ({dk}), p {p:.2g}, "
              f"BIC {b['BIC']:.1f} -> {k['BIC']:.1f}, hold-out {b['holdout_LL']:.1f} -> {k['holdout_LL']:.1f}", flush=True)
        print("   ", [(c["param"], round(c["coef"], 3), round(c["t"], 2)) for c in coef if c["segment"] == seg and c["model"] == "kids" and c["param"].startswith("kids")], flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/m07_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m07_coef.csv", index=False)


if __name__ == "__main__":
    main()
