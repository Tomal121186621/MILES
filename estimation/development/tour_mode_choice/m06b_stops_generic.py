#!/usr/bin/env python3
"""Shopping and school tours: tour with stops as one coefficient on every mode other than car driver (5 mode-specific terms
did not lower BIC in m06_literature.py). On top of the m06 selection (+ park).   -> m06b_fit.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
import m06_literature as L   # noqa: E402
G = L.G
from biogeme.expressions import Beta, Variable as X

base_ll = L.loglike


def loglike(df, alts, blocks, **kw):
    """m06 utilities; 'stops1' adds one stops term to the car-driver utility (equivalent to one common term on the other modes)"""
    ll_blocks = [b for b in blocks if b != "stops1"]
    if "stops1" not in blocks: return base_ll(df, alts, blocks=ll_blocks, **kw)
    import biogeme.models as models
    orig = models.loglogit
    def patched(U, AV, y):
        U = dict(U); U[G.NUM["CD"]] = U[G.NUM["CD"]] + Beta("stops_CD", 0, None, None, 0) * X("stops")
        return orig(U, AV, y)
    models.loglogit = patched
    try:
        return base_ll(df, alts, blocks=ll_blocks, **kw)
    finally:
        models.loglogit = orig


def main():
    L.loglike = loglike; os.chdir(f"{HERE}/bio"); rows = []
    for seg in ["shopping", "school"]:
        df, ho = L.data("estimation", seg), L.data("validation", seg)
        alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        t0, a = L.estimate(seg, df, ho, alts, ["park"], f"{seg}_park_b"); t1, b = L.estimate(seg, df, ho, alts, ["park", "stops1"], f"{seg}_park_stops1")
        lr = 2 * (b["LL"] - a["LL"]); p = float(chi2.sf(lr, b["K"] - a["K"]))
        b.update(added="stops1", LR=lr, p=p, kept=bool(p < 0.05 and b["BIC"] < a["BIC"] and t1.Value["stops_CD"] > 0)); rows += [a, b]
        print(seg, f"LL {a['LL']:.1f} -> {b['LL']:.1f}, LR {lr:.1f}, p {p:.2g}, BIC {a['BIC']:.1f} -> {b['BIC']:.1f}, hold-out {a['holdout_LL']:.1f} -> {b['holdout_LL']:.1f}, "
              f"stops_CD {t1.Value['stops_CD']:.3f} (t {t1['Robust t-stat.']['stops_CD']:.2f}); kept {b['kept']}", flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/m06b_fit.csv", index=False)


if __name__ == "__main__":
    main()
