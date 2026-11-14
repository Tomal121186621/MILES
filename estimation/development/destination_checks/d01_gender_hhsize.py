#!/usr/bin/env python3
"""Destination and stop choice: ln distance (stops: ln(1 + detour)) x woman and x household size, added to the final model of
each segment (search_<segment>.pkl, F).  Same sampled choice sets as the search (40 alternatives, seed 2026); the validation
half with its own sampled sets (seed 2027).  A term is kept when the likelihood-ratio test is significant at 5 % and BIC falls.
    python3 estimation/development/destination_checks/d01_gender_hhsize.py   ->  d01_fit.csv, d01_coef.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle
import numpy as np, pandas as pd
from scipy.stats import chi2
DCD = f"{TERP_HOME}/activity/lib/destination_choice"
HERE = f"{ESTIMATION_RESULTS}/destination"   # results of this check (data)
sys.path.insert(0, DCD)
import dc_common as C, dc_model as M, estimate_dc as E   # noqa: E402
import torch

_chooser = M.chooser
def chooser(rec):
    a = _chooser(rec); a["female"] = 1.0 - rec.male.values.astype(float); a["hhs"] = np.minimum(rec.hhsize.values, 6).astype(float) - 1
    return a
M.chooser = chooser
SEGS = [f"{p}_{k}" for k in ["primary", "stop"] for p in ["SHOPPING", "OTHER", "RECREATION", "ACCOMPANY"]]


def holdout(spec, res, seg, pur, sk):
    rec, cand = E.load("validation", seg); sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2027)
    D = M.Data(rec, *sets, spec, pur, sk)
    with torch.no_grad(): return float(M.ll_obs(res["x"], spec, D).sum())


def main():
    sk = C.skims(); fit, coef = [], []
    for seg in SEGS:
        pur, kind = seg.split("_"); ln = "lndt" if kind == "stop" else "lnd"
        o = pickle.load(open(f"{C.WORK}/search_{seg}.pkl", "rb")); F = o["models"]["F"]["spec"]
        rec, cand = E.load("estimation", seg); sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026); N = len(rec)
        def run(name, lin, x0):
            s = M.Spec(name, lin, F.size_base, F.size_comps); r = E.fit(s, rec, *sets, pur, sk, x0=x0)
            r["BIC"] = np.log(N) * r["K"] - 2 * r["LL"]; r["hold"] = holdout(s, r, seg, pur, sk); return s, r
        sb, b = run("F", F.linear, None); warm = dict(zip(sb.params(), b["x"].numpy()))
        fit.append(dict(segment=seg, model="final", K=b["K"], LL=b["LL"], BIC=b["BIC"], holdout_LL=b["hold"]))
        print(f"{seg}: N {N}, final LL {b['LL']:.1f} BIC {b['BIC']:.1f} hold-out {b['hold']:.1f}", flush=True)
        for x in ["female", "hhs"]:
            nm = f"{ln}_{x}"; s, r = run(nm, F.linear + [nm], warm)
            lr = 2 * (r["LL"] - b["LL"]); p = float(chi2.sf(lr, 1)); t = r["table"].set_index("param")
            ok = p < 0.05 and r["BIC"] < b["BIC"]
            fit.append(dict(segment=seg, model=f"+ {nm}", K=r["K"], LL=r["LL"], BIC=r["BIC"], holdout_LL=r["hold"], LR=lr, p=p, kept=ok,
                            coef=t.value[nm], t=t.rob_t[nm]))
            for pn, row in t.iterrows(): coef.append(dict(segment=seg, model=nm, param=pn, coef=row.value, t=row.rob_t))
            print(f"   + {nm}: {t.value[nm]:+.3f} (t {t.rob_t[nm]:.2f}), LR {lr:.1f}, p {p:.2g}, BIC {b['BIC']:.1f} -> {r['BIC']:.1f}, "
                  f"hold-out {b['hold']:.1f} -> {r['hold']:.1f}{'  kept' if ok else ''}", flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/d01_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/d01_coef.csv", index=False)


if __name__ == "__main__":
    main()
