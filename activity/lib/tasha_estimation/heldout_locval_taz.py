#!/usr/bin/env python3
"""Held-out table of the discretionary destination models of record (TAZ, 2026-10-29) against the former gravity model, both on
the TAZ records of the validation half (location mixture), full choice set: LL per record, binned KS and coincidence ratio of the
trip length (from home), mean distance.  -> results/locval_taz.csv, heldout_tld_taz.csv (trip-length shares, primaries with gravity; stops from seq_tld_taz.csv)"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import estimate_dc_taz as Z, dc_taz_engine as X, dc_model as M, dc_common as C   # noqa: E402
from estimate_complexity import multi_flag, final_spec                           # noqa: E402
from validate_dc import gravity_matrix, ks_cr                                    # noqa: E402
from rts_common import DIST_BINS                                                 # noqa: E402
from rts_common import DIST_LABELS                                               # noqa: E402
sk = C.skims(); E = pd.read_csv(f"{Z.RES}/cx_estimates_taz.csv"); rows = []; tld = []; nb = len(DIST_BINS) - 1
for p in C.DISC:
    seg = f"{p}_primary"; spec, _ = final_spec(seg); spec = M.Spec("FX", spec.linear + ["lnd_multi"], spec.size_base, spec.size_comps)
    x = E[E.segment == seg].set_index("param").value[spec.params()].values
    rec, cand, cfg = Z.load_taz("validation", seg); rec["multi"] = multi_flag(rec, "validation")
    h = X.heldout(rec, cand, cfg, spec, x, p, sk, obs="mix")
    G = gravity_matrix(p, sk); pos = pd.Series(np.arange(len(rec)), index=rec.rec.values)
    cf = cfg.assign(p=pos[cfg.rec.values].values); cd = cand.assign(p=pos[cand.rec.values].values)
    ll = np.zeros(len(rec)); hg = np.zeros(nb); w = rec.w.values; kg = np.zeros(len(rec))
    for r in cf.itertuples():
        dz = cd[cd.p == r.p]; ll[r.p] += r.w * float((G[r.home_idx, dz.zidx.values] * dz.b.values).sum())
        d = sk["d"][r.home_idx].astype(float); b = np.clip(np.searchsorted(DIST_BINS, d, side="right") - 1, 0, nb - 1)
        hg += np.bincount(b, weights=w[r.p] * r.w * G[r.home_idx], minlength=nb); kg[r.p] += r.w * float((G[r.home_idx] * d).sum())
    hg /= hg.sum(); ksm, crm = ks_cr(h["tld_pred"], h["tld_obs"]); ksg, crg = ks_cr(hg, h["tld_obs"])
    rows.append(dict(segment=seg, N=len(rec), LL_mnl=float(h["LL"].mean()), LL_gravity=float(np.log(np.clip(ll, 1e-12, None)).mean()), KS_mnl=ksm, KS_gravity=ksg, CR_mnl=crm, CR_gravity=crg,
                     km_mnl=float(np.average(h["km_pred"], weights=w)), km_obs=float(np.average(h["km_obs"], weights=w)), km_gravity=float(np.average(kg, weights=w))))
    for mdl, hh in [("observed", h["tld_obs"]), ("mnl", h["tld_pred"]), ("gravity", hg)]:
        tld += [dict(segment=seg, half="validation", model=mdl, bin=b_, share=float(v_)) for b_, v_ in zip(DIST_LABELS, hh)]
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
pd.DataFrame(rows).to_csv(f"{Z.RES}/locval_taz.csv", index=False)
S = pd.read_csv(f"{Z.RES}/seq_tld_taz.csv"); S = S[(S.half == "validation") & (S.model == "new (TAZ)")]
S = S.assign(model=np.where(S.kind == "obs", "observed", "mnl"))[["segment", "half", "model", "bin", "share"]]
pd.concat([pd.DataFrame(tld), S], ignore_index=True).to_csv(f"{Z.RES}/heldout_tld_taz.csv", index=False)   # input of 5_reports/composites/fig_activity_location.py
