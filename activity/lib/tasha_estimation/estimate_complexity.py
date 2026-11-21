#!/usr/bin/env python3
"""Tour-complexity term of the primary discretionary destination MNLs (stage 3 finalisation, 2026-10-23).

    python3 activity/lib/tasha_estimation/estimate_complexity.py    -> results/cx_estimates.csv, cx_tests.csv, cx_heldout.csv, dest_choice_primary_cx.csv

The primary-destination MNLs of destination_choice/ (final specifications F, ESTIMATION_REPORT.md) pool the primary
destinations of simple tours (home - X - home) and of tours with stops.  In the survey the primary of a tour with stops lies
much farther from home (shopping 12.4 vs 8.6 km, recreation 17.2 vs 11.2 km; estimation half, zone skim).  The TASHA generator
applies the primary MNL to the main episode of every chain, so with the pooled model the mains of simple chains are too far and
those of chains with stops too near.  Here each final specification F is extended by ln(distance) x multi (multi = the tour has
at least one stop, rts_tours.n_stops > 0) and re-estimated by maximum likelihood on the estimation half with the same engine
and sampled choice sets (dc_model, R = 40, seed 2026; robust standard errors), warm-started at the F estimates; LR test against
F; held-out check on the validation half (mean distance from home by tour type, full choice set).  In MAST the flag is 0 for the
draw before scheduling and for the main of a single-episode chain, and 1 when the main discretionary episode of a chain with
stops is relocated after the chains are formed (MarylandTashaGenerator.buildTourObjects, MarylandDestinationChoice.selectPrimaryZoneMnl).
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, pickle, sys
import numpy as np
import pandas as pd
import torch
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import te_common as T            # noqa: E402
import dc_common as C            # noqa: E402
import dc_model as M             # noqa: E402
import estimate_dc as E          # noqa: E402
from rts_common import load_split, load_tours   # noqa: E402

SEGS = [f"{p}_primary" for p in C.DISC]


def multi_flag(rec, half):
    """n_stops > 0 of the tour of each record (tour_id as numbered in prep_dc_data.build)."""
    s = load_split(); tr = load_tours(); tr = tr[(tr.anchor == "home") & tr.household_id.map(s).eq(half)].copy()
    tr = tr[~tr.primary_act.isin([1, -9])]; tr["tour_id"] = np.arange(len(tr))
    return rec.tour_id.map(tr.set_index("tour_id").n_stops).fillna(0).gt(0).astype(float).values


def final_spec(seg):
    o = pickle.load(open(f"{C.WORK}/search_{seg}.pkl", "rb")); F = o["models"]["F"]; spec = F["spec"]
    x = dict(zip(F["table"].param, F["table"].value))
    b = f"{C.DCD}/results/biogeme_{seg}.csv"
    if os.path.exists(b): bb = pd.read_csv(b); x = dict(zip(bb.Name, bb.Value))
    return spec, x


def main():
    sk = C.skims(); rows, tests, ho, coef = [], [], [], []
    for seg in SEGS:
        pur = seg.split("_")[0]
        rec, cand = E.load("estimation", seg); rec["multi"] = multi_flag(rec, "estimation")
        sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
        spec, x0 = final_spec(seg)
        r0 = E.fit(spec, rec, *sets, pur, sk, x0=x0)
        spec1 = M.Spec("FX", spec.linear + ["lnd_multi"], spec.size_base, spec.size_comps, note="F + ln(distance) x tour with stops")
        r1 = E.fit(spec1, rec, *sets, pur, sk, x0={**x0, "lnd_multi": 0.0})
        lr = 2 * (r1["LL"] - r0["LL"])
        tests.append(dict(segment=seg, N=len(rec), share_multi=float(np.average(rec.multi, weights=rec.w)), LL_F=r0["LL"], LL_FX=r1["LL"], LR=lr, df=1, p=float(chi2.sf(lr, 1)),
                          AIC_F=2 * r0["K"] - 2 * r0["LL"], AIC_FX=2 * r1["K"] - 2 * r1["LL"], BIC_F=np.log(len(rec)) * r0["K"] - 2 * r0["LL"], BIC_FX=np.log(len(rec)) * r1["K"] - 2 * r1["LL"]))
        t = r1["table"].assign(segment=seg); rows.append(t)
        v = t.set_index("param").value
        coef += [dict(segment=seg, variable="mu_size", value=float(v["mu_size"])), dict(segment=seg, variable=f"size_{spec1.size_base}", value=1.0)]
        coef += [dict(segment=seg, variable=f"size_{c}", value=float(np.exp(v[f"theta_{c}"]))) for c in spec1.size_comps]
        coef += [dict(segment=seg, variable=k, value=float(v[k])) for k in spec1.linear]
        print(tests[-1], flush=True)
        # held-out: mean distance from home by tour type (validation half and estimation half), full choice set
        for half in ["estimation", "validation"]:
            rh, ch = E.load(half, seg); rh["multi"] = multi_flag(rh, half); okp = rh.dzone_pt.values >= 0
            for lab, spc, xx in [("pooled F", spec, r0["x"].numpy()), ("with complexity term", spec1, r1["x"].numpy())]:
                pd_ = []; ll = 0.0
                for sub, P, logb in M.predict_full(rh, ch, spc, xx, pur, sk):
                    lb = np.where(np.isfinite(logb), np.exp(logb), 0.0); ll += float(np.log(np.clip((P * lb).sum(1), 1e-300, None)).sum())
                    pd_.append((P * sk["d"][sub.home_idx.values]).sum(1))
                pd_ = np.concatenate(pd_)
                for m in [0.0, 1.0]:
                    s_ = rh.multi.values == m
                    ho.append(dict(segment=seg, half=half, model=lab, tour="with stops" if m else "simple", N=int(s_.sum()), LL_per_obs=ll / len(rh),
                                   km_obs=float(np.average(sk["d"][rh.home_idx.values[s_ & okp], rh.dzone_pt.values[s_ & okp]], weights=rh.w.values[s_ & okp])),
                                   km_pred=float(np.average(pd_[s_], weights=rh.w.values[s_]))))
    pd.concat(rows).to_csv(f"{T.RES}/cx_estimates.csv", index=False); pd.DataFrame(tests).to_csv(f"{T.RES}/cx_tests.csv", index=False)
    pd.DataFrame(ho).to_csv(f"{T.RES}/cx_heldout.csv", index=False); pd.DataFrame(coef).to_csv(f"{T.RES}/dest_choice_primary_cx.csv", index=False)
    print(pd.DataFrame(tests).round(3).to_string()); print(pd.DataFrame(ho).round(3).to_string())


if __name__ == "__main__":
    main()
