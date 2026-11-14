#!/usr/bin/env python3
"""Destination of the first stop of an outing from the usual workplace (work-based subtour, 3 November 2026), estimated with the
location-MNL machinery of estimate_locations.py (importance-sampled choice sets R = 40 with the McFadden correction, tract-to-zone
measurement model, nested specification search with LR tests, backward elimination, robust standard errors) on the ESTIMATION
half; held-out test on the validation half.  Segment OTHER_wbs (all purposes pooled: 1,184 outings in the estimation half; purpose
label OTHER for the sampling of the choice set), primary form with the usual workplace as the anchor (impedance = car distance
from the work zone).

    python3 activity/lib/tasha_estimation/estimate_subtour_dest.py records|search|heldout|export

Why a separate segment: the home-based primary MNL anchored at the workplace put the first stop 8.5 km from the workplace on
average against 4.5 km observed (median 4.2 against 1.7 km): an outing during the working day is shorter than a tour from home.
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import te_common as T                                   # noqa: E402
import dc_common as C                                   # noqa: E402
import prep_dc_data as PD                               # noqa: E402
import build_distributions as TD                        # noqa: E402
import estimate_locations as L                          # noqa: E402

SEG = "OTHER_wbs"
L.SEGS = {SEG: dict(purpose="OTHER", forms=["primary"])}
_orig_load = L.load


def records(half):
    e = T.episodes(half).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    e = TD.subtours(e)
    prev_wbs = e.groupby("person_id").wbs.shift(1, fill_value=False)
    x = e[e.wbs & ~prev_wbs.values].copy()          # the first stop of each outing
    P = PD.people(half); ov = PD.overlay(); m = C.id2idx()
    root = e.loc[x.wbs_root.values]; x["wz"] = root.wz.values
    x = x[x.person_id.isin(P.index) & (x.wz > 0) & x.d_geoid.isin(ov.geoid.unique())].copy()
    x["segment"] = SEG; x["home_zone_idx"] = m[x.wz.values]; x["work_idx"] = m[x.wz.values]
    x["dzone_pt"] = np.where(x.dz > 0, m[x.dz.clip(lower=0).values], -1)
    x["purpose"] = "OTHER"; x["tod"] = PD.tod_cls(x.arr_min); x["mode_auto"] = 1.0; x["tour_purpose"] = ""; x["position"] = ""; x["anchor_b"] = -1
    x["w"] = x.wttrdfin; x["geoid"] = x.d_geoid; x["km_rep"] = np.where(x.distance >= 0, x.distance * 1.60934, np.nan)
    x = x[["tripid", "person_id", "household_id", "segment", "purpose", "type", "seg", "home_zone_idx", "work_idx", "dzone_pt", "tod",
           "mode_auto", "tour_purpose", "position", "anchor_b", "w", "geoid", "km_rep", "arr_min"]]
    x = PD.chooser_cols(x, P).reset_index(drop=True); x["rec"] = np.arange(len(x))
    cand = x[["rec", "geoid"]].merge(ov, on="geoid")[["rec", "zidx", "b"]]
    x.to_parquet(f"{T.WORK}/wbs_dest_records_{half}.parquet", index=False); cand.to_parquet(f"{T.WORK}/wbs_dest_cand_{half}.parquet", index=False)
    print(half, len(x), "first stops", x.type.value_counts().to_dict())


def load(half, segment, form="primary"):
    rec = pd.read_parquet(f"{T.WORK}/wbs_dest_records_{half}.parquet"); cand = pd.read_parquet(f"{T.WORK}/wbs_dest_cand_{half}.parquet")
    rec["home_idx"] = rec.home_zone_idx.astype(int); rec["kind"] = "primary"; rec["anchor_b"] = rec.anchor_b.astype(int)
    return rec.reset_index(drop=True), cand


L.load = load
_res, _work = T.RES, T.WORK


def heldout():
    """full choice set: predictive LL per record and mean km from the workplace, observed / segment / primary MNL of the purpose"""
    sk = C.skims(); rows = []
    form, _, o = L.chosen_form(SEG); F = o["models"]["F"]; spec, x = F["spec"], F["x"].numpy()
    import dc_model as M
    for half in ["estimation", "validation"]:
        rec, cand = load(half, SEG)
        ll = 0.0; dp = []
        for sub, P, logb in M.predict_full(rec, cand, spec, x, "OTHER", sk):
            lb = np.where(np.isfinite(logb), np.exp(logb), 0.0); ll += float(np.log(np.clip((P * lb).sum(1), 1e-300, None)).sum())
            dp.append((P * sk["d"][sub.home_zone_idx.values]).sum(1))
        okp = rec.dzone_pt.values >= 0; w = rec.w.values
        do = sk["d"][rec.home_zone_idx.values[okp], rec.dzone_pt.values[okp]]
        rows.append(dict(half=half, N=len(rec), LL=ll, LL_per_obs=ll / len(rec), km_obs=np.average(do, weights=w[okp]), km_pred=np.average(np.concatenate(dp), weights=w)))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{T.RES}/wbs_dest_heldout.csv", index=False)


def export():
    form, aic, o = L.chosen_form(SEG); F = o["models"]["F"]; spec = F["spec"]; t = F["table"].copy(); v = t.set_index("param").value
    coef = [dict(segment=SEG, variable="mu_size", value=float(v["mu_size"])), dict(segment=SEG, variable=f"size_{spec.size_base}", value=1.0)]
    for c in spec.size_comps: coef.append(dict(segment=SEG, variable=f"size_{c}", value=float(np.exp(v[f"theta_{c}"]))))
    for k in spec.linear: coef.append(dict(segment=SEG, variable=k, value=float(v[k])))
    pd.DataFrame(coef).to_csv(f"{T.RES}/dest_choice_wbs.csv", index=False); t.to_csv(f"{T.RES}/wbs_dest_estimates.csv", index=False)
    pd.DataFrame([dict(segment=SEG, **r) for r in o["rows"]]).to_csv(f"{T.RES}/wbs_dest_search.csv", index=False)
    pd.DataFrame(o.get("elimination", [])).to_csv(f"{T.RES}/wbs_dest_elimination.csv", index=False)
    st = dict(segment=SEG, N=F["N"], K=F["K"], LL0=o["LL0"], LLc=o["LLc"], LL=F["LL"], rho2=1 - F["LL"] / o["LL0"], rho2_c=1 - F["LL"] / o["LLc"], AIC=aic,
              BIC=np.log(F["N"]) * F["K"] - 2 * F["LL"], size_base=spec.size_base, converged=F["converged"])
    pd.DataFrame([st]).to_csv(f"{T.RES}/wbs_dest_stats.csv", index=False)
    print(pd.DataFrame(coef).to_string()); print(st)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "records":
        for h in ["estimation", "validation"]: records(h)
    elif cmd == "search": L.search(SEG, "primary")
    elif cmd == "heldout": heldout()
    else: export()
