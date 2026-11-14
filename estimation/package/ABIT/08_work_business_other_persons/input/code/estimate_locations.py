#!/usr/bin/env python3
"""Estimated location of the anchored TASHA activity types (stage 3 finalisation, 2026-10-23), with the multinomial-logit
machinery of the discretionary destination choice (destination_choice/dc_model.py: importance-sampled choice sets of R = 40
draws with the McFadden correction, the tract-to-zone measurement model, exact gradients and robust sandwich covariance;
destination_choice/estimate_dc.py: nested specification search with LR tests and backward elimination), on the ESTIMATION half
of the 2017/18 RTS; the validation half is used only for the held-out test.  No calibration factor.

    python3 estimate_locations.py records      # work/loc_records_<half>.parquet, loc_cand_<half>.parquet
    python3 estimate_locations.py search       # specification search per segment -> work/locsearch_<segment>.pkl
    python3 estimate_locations.py heldout      # full-choice-set predictions on both halves -> results/loc_heldout.csv
    python3 estimate_locations.py export       # results/loc_estimates_<segment>.csv, results/loc_search.csv, results/dest_choice_loc.csv

Segments (replace the distance-band model of MarylandTashaGenerator.bandLocation):
  WORK_wbwork   work business (WB) of a worker with a usual work tract: two forms are estimated and compared by AIC,
                (a) the primary form from the usual workplace (impedance = car distance from the work zone), and
                (b) the two-anchor form (impedance = detour via the zone between home and the usual workplace,
                    d(home, j) + d(j, work) - d(home, work); the stop form of the discretionary MNL with the anchors home and work)
  WORK_wbhome   WB of every other person (workplace varies / no work tract, non-workers, students, retirees): from home
  WORK_wahb     work trips of a worker whose usual workplace is home (WAHB): from home
  EDUCATION_nonstud  school episodes of persons without a school record in the model (enrolled workers, non-workers,
                retirees): from home
  EDUCATION_daycare  daycare / preschool of persons under 5: from home
Records: the episodes of these types (te_common.episodes; types of tasha_distributions.py) whose destination tract and anchor
zones lie in the zone system; chooser attributes as ABIT sees them (destination_choice/prep_dc_data.people); time of day of the
arrival.
"""
# COPY of Validation_2026/3_abit/tasha_estimation/estimate_locations.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import argparse, os, pickle, sys, time
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import te_common as T                                   # noqa: E402
import dc_common as C                                   # noqa: E402
import dc_model as M                                    # noqa: E402
import estimate_dc as E                                 # noqa: E402
import prep_dc_data as PD                               # noqa: E402

SEGS = {"WORK_wbwork": dict(purpose="WORK", forms=["primary", "stop"]), "WORK_wbhome": dict(purpose="WORK", forms=["primary"]),
        "WORK_wahb": dict(purpose="WORK", forms=["primary"]), "EDUCATION_nonstud": dict(purpose="EDUCATION", forms=["primary"]),
        "EDUCATION_daycare": dict(purpose="EDUCATION", forms=["primary"])}
M.SAMPLING_SIZE["EDUCATION"] = {"stu": 1.0, "pop": 0.1}
M.SAMPLING_SIZE["WORK"] = {"ret": 1.0, "off": 1.0, "oth": 1.0, "pop": 0.1}
COMPS = ["pop", "ret", "off", "oth", "stu"]
SOCIO = ["inc0", "inc2", "car0", "car1", "child", "kid", "senior", "worker"]


# ------------------------------------------------------------------------------------------------ records
def records(half):
    e = T.episodes(half); P = PD.people(half); ov = PD.overlay(); m = C.id2idx()
    x = e[e.type.isin(["WB", "WAHB", "SCH"])].copy()
    x = x[~(x.type.eq("SCH") & x.seg.str.startswith("student"))]
    x["segment"] = np.select([x.type.eq("WB") & x.seg.eq("worker_usual") & (x.wz > 0), x.type.eq("WB"), x.type.eq("WAHB"), x.seg.eq("toddler")],
                             ["WORK_wbwork", "WORK_wbhome", "WORK_wahb", "EDUCATION_daycare"], "EDUCATION_nonstud")
    x = x[x.person_id.isin(P.index) & (x.hz > 0) & x.d_geoid.isin(ov.geoid.unique())].copy()
    x = x[~x.segment.eq("WORK_wbwork") | (x.wz > 0)]
    x["home_zone_idx"] = m[x.hz.values]; x["work_idx"] = np.where(x.wz > 0, m[x.wz.clip(lower=0).values], -1)
    x["dzone_pt"] = np.where(x.dz > 0, m[x.dz.clip(lower=0).values], -1)
    x["purpose"] = x.segment.str.split("_").str[0]
    x["tod"] = PD.tod_cls(x.arr_min); x["mode_auto"] = 1.0; x["tour_purpose"] = ""; x["position"] = ""; x["anchor_b"] = -1
    x["w"] = x.wttrdfin; x["geoid"] = x.d_geoid; x["km_rep"] = np.where(x.distance >= 0, x.distance * 1.60934, np.nan)
    x = x.rename(columns={"tripid": "tripid"})[["tripid", "person_id", "household_id", "segment", "purpose", "type", "seg", "home_zone_idx", "work_idx", "dzone_pt", "tod",
                                                "mode_auto", "tour_purpose", "position", "anchor_b", "w", "geoid", "km_rep", "arr_min"]]
    x = PD.chooser_cols(x, P)
    x = x.reset_index(drop=True); x["rec"] = np.arange(len(x))
    cand = x[["rec", "geoid"]].merge(ov, on="geoid")[["rec", "zidx", "b"]]
    x.to_parquet(f"{T.WORK}/loc_records_{half}.parquet", index=False); cand.to_parquet(f"{T.WORK}/loc_cand_{half}.parquet", index=False)
    print(half, x.segment.value_counts().to_dict())


def load(half, segment, form="primary"):
    rec = pd.read_parquet(f"{T.WORK}/loc_records_{half}.parquet"); cand = pd.read_parquet(f"{T.WORK}/loc_cand_{half}.parquet")
    rec = rec[rec.segment == segment].copy()
    if segment == "WORK_wbwork" and form == "primary":
        rec["home_idx"] = rec.work_idx; rec["kind"] = "primary"          # anchor = the usual workplace
    elif form == "stop":
        rec["home_idx"] = rec.home_zone_idx; rec["anchor_b"] = rec.work_idx; rec["kind"] = "stop"   # anchors home and workplace
    else:
        rec["home_idx"] = rec.home_zone_idx; rec["kind"] = "primary"
    rec["home_idx"] = rec.home_idx.astype(int); rec["anchor_b"] = rec.anchor_b.astype(int)
    rec = rec.reset_index(drop=True); cand = cand[cand.rec.isin(rec.rec.values)]
    return rec, cand


# ------------------------------------------------------------------------------------------------ search
def informative_flags(rec, flags):
    """chooser flags that vary in the sample and are not identical to an earlier flag (others make the Hessian singular)"""
    ch = M.chooser(rec); keep = []
    for x in flags:
        v = ch[x]
        if v.min() == v.max(): continue
        if any(np.array_equal(v, ch[k]) for k in keep): continue
        keep.append(x)
    return keep


def sequence(segment, form, base, comps, rec=None):
    stop = form == "stop"; pre = "dt" if stop else "d"; ln = "lndt" if stop else "lnd"
    socio = informative_flags(rec, SOCIO) if rec is not None else SOCIO; tod = informative_flags(rec, E.TOD) if rec is not None else E.TOD
    pieces = C.pw_names(pre, C.DKNOTS if stop else C.KNOTS); intra = ["intra_a", "intra_b"] if stop else ["intra"]
    L = []; s = [pre]
    L.append(M.Spec("S1", s, base, comps, note="ln size (weights estimated) + linear " + ("detour" if stop else "distance")))
    s = pieces; L.append(M.Spec("S2", s, base, comps, note="piecewise-linear " + ("detour" if stop else "distance")))
    s = s + intra; L.append(M.Spec("S3", s, base, comps, note="+ intrazonal" if not stop else "+ in the home / workplace zone"))
    s = s + E.AREA; L.append(M.Spec("S4", s, base, comps, note="+ area dummies"))
    s = s + ["lnretden", "mix"]; L.append(M.Spec("S5", s, base, comps, note="+ retail density, land-use mix"))
    s = s + ["xcounty", "xstate"]; L.append(M.Spec("S6", s, base, comps, note="+ county and state boundary"))
    s = s + [f"{ln}_{x}" for x in socio]; L.append(M.Spec("S7", s, base, comps, note="+ ln-distance x household / person"))
    s = s + [f"{ln}_{x}" for x in tod]; L.append(M.Spec("S8", s, base, comps, note="+ ln-distance x time of day"))
    L.append(M.Spec("S9t", s + ["cgt"], base, comps, note="+ car generalized time"))
    return L


def search(segment, form):
    t0 = time.time(); pur = SEGS[segment]["purpose"]; sk = C.skims()
    rec, cand = load("estimation", segment, form)
    sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
    out = dict(segment=segment, form=form, N=len(rec), J=sets[0].shape[1], models={}, rows=[])
    # size normalisation: the component with the largest S1 weight is the base (weight 1)
    base0 = "stu" if pur == "EDUCATION" else "off"; comps0 = [c for c in COMPS if c != base0]
    s1 = sequence(segment, form, base0, comps0, rec)[0]; r1 = E.fit(s1, rec, *sets, pur, sk)
    tv = r1["table"].set_index("param").value
    w = {base0: 1.0, **{c: float(np.exp(tv[f"theta_{c}"])) for c in comps0}}
    base = max(w, key=w.get); comps = [c for c in COMPS if c != base]; out["size_base"] = base; out["size_weights_S1"] = w
    prev = None
    for spec in sequence(segment, form, base, comps, rec):
        warm = dict(zip(prev["spec"].params(), prev["x"].numpy())) if prev is not None else None
        res = E.fit(spec, rec, *sets, pur, sk, x0=warm); LL0 = res["LL0"]
        out["rows"].append(E.row(res, prev, LL0)); out["models"][spec.name] = res
        if spec.name != "S9t": prev = res
        print(f"  {segment}/{form} {spec.name}: LL {res['LL']:.1f} K {res['K']} ({time.time() - t0:.0f} s)", flush=True)
    top = min([out["models"]["S8"], out["models"]["S9t"]], key=lambda m: 2 * m["K"] - 2 * m["LL"])
    spec, res = E.drop_zero_size(top["spec"], top, rec, sets, pur, sk)
    elim = []; spec, res = E.backward(M.Spec("F", spec.linear, spec.size_base, spec.size_comps), res, rec, sets, pur, sk, elim)
    # re-normalise the size term on the component with the largest final weight (a base with a negligible weight leaves the
    # scale of the size term unidentified), then re-estimate the final specification
    for _ in range(3):
        tv = res["table"].set_index("param").value
        w = {spec.size_base: 1.0, **{c: float(np.exp(tv[f"theta_{c}"])) for c in spec.size_comps}}
        nb = max(w, key=w.get)
        if nb == spec.size_base or w[nb] < 2.0: break
        spec = M.Spec("F", spec.linear, nb, [c for c in w if c != nb], note="final (backward elimination)")
        res = E.fit(spec, rec, *sets, pur, sk); res["spec"] = spec
        elim.append(dict(dropped=f"size base -> {nb}", t=np.nan, LL_before=np.nan, LL_after=res["LL"]))
        spec, res = E.drop_zero_size(spec, res, rec, sets, pur, sk)
        spec, res = E.backward(M.Spec("F", spec.linear, spec.size_base, spec.size_comps), res, rec, sets, pur, sk, elim)
    out["size_base"] = spec.size_base
    out["rows"].append(E.row(res, None, LL0)); out["models"]["F"] = res; out["elimination"] = elim; out["LL0"] = LL0
    st, df, p = E.lr(res, top); out["rows"][-1].update(LR_vs=top["spec"].name, LR=-st, LR_df=-df, LR_p=p)
    cons = [v for v in spec.linear if v in E.AREA + ["intra", "intra_a", "intra_b"]]
    rc = E.fit(M.Spec("C", cons or (["intra_a"] if form == "stop" else ["intra"]), spec.size_base, [], mu_fixed=0.0, note="constants only"), rec, *sets, pur, sk)
    out["LLc"] = rc["LL"]
    out["time_s"] = time.time() - t0
    pickle.dump(out, open(f"{T.WORK}/locsearch_{segment}_{form}.pkl", "wb"))
    print(f"{segment}/{form}: final LL {res['LL']:.1f} K {res['K']}, AIC {2 * res['K'] - 2 * res['LL']:.1f} ({time.time() - t0:.0f} s)", flush=True)
    return out


def chosen_form(segment):
    forms = SEGS[segment]["forms"]; best = None
    for f in forms:
        p = f"{T.WORK}/locsearch_{segment}_{f}.pkl"
        if not os.path.exists(p): continue
        o = pickle.load(open(p, "rb")); F = o["models"]["F"]; aic = 2 * F["K"] - 2 * F["LL"]
        if best is None or aic < best[1]: best = (f, aic, o)
    return best


# ------------------------------------------------------------------------------------------------ held-out test
def heldout():
    """Full-choice-set predictions: predictive LL per record, mean zone-skim distance from the anchor and from home (predicted
    vs observed), for both halves; the band model (MarylandTashaGenerator.bandLocation) for comparison."""
    sk = C.skims(); z = C.zones(); rows = []
    bands = pd.read_csv(f"{C.A3}/coef_tasha/tasha/tasha_location_bands.csv"); prm = pd.read_csv(f"{C.A3}/coef_tasha/tasha/tasha_params.csv").set_index("key").value
    lo = np.array([float(v) for v in prm["dist.bins"].split(";")])
    attr = {"WB": z.jobs.values, "SCH": z.stu.values, "DAYCARE": z["pop"].values + z.jobs.values}
    for seg in SEGS:
        b = chosen_form(seg)
        if b is None: continue
        form, _, o = b; F = o["models"]["F"]; spec = F["spec"]; x = F["x"].numpy(); pur = SEGS[seg]["purpose"]
        for half in ["estimation", "validation"]:
            rec, cand = load(half, seg, form)
            if len(rec) == 0: continue
            ll = 0.0; dh_p = []; da_p = []; ll_band = 0.0; dh_b = []
            for sub, P, logb in M.predict_full(rec, cand, spec, x, pur, sk):
                lb = np.where(np.isfinite(logb), np.exp(logb), 0.0)
                ll += float(np.log(np.clip((P * lb).sum(1), 1e-300, None)).sum())
                hz = sub.home_zone_idx.values; an = sub.work_idx.values if seg == "WORK_wbwork" else hz
                dh_p.append((P * sk["d"][hz]).sum(1)); da_p.append((P * sk["d"][an]).sum(1))
                # band model probabilities
                ltype, origin = ("DAYCARE", "home") if seg == "EDUCATION_daycare" else ("SCH", "home") if seg == "EDUCATION_nonstud" else \
                    ("WAHB", "home") if seg == "WORK_wahb" else ("WB", "work") if seg == "WORK_wbwork" else ("WB", "home")
                pr = bands[(bands.type == ltype) & (bands.origin == origin)]
                pb = np.array([float(v) for v in pr.probs.iloc[0].split(";")]); a = attr["DAYCARE" if ltype == "DAYCARE" else "SCH" if ltype == "SCH" else "WB"]
                ob = an; dd = sk["d"][ob]; bb = np.clip(np.searchsorted(lo, dd, side="right") - 1, 0, len(pb) - 1)
                Pb = np.zeros_like(P)
                for k in range(len(sub)):
                    tot = np.bincount(bb[k], weights=a, minlength=len(pb)); wq = np.where(tot > 0, pb, 0); wq = wq / wq.sum()
                    Pb[k] = wq[bb[k]] * a / np.where(tot[bb[k]] > 0, tot[bb[k]], 1)
                ll_band += float(np.log(np.clip((Pb * lb).sum(1), 1e-300, None)).sum()); dh_b.append((Pb * sk["d"][hz]).sum(1))
            w = rec.w.values; okp = rec.dzone_pt.values >= 0
            dh_o = sk["d"][rec.home_zone_idx.values[okp], rec.dzone_pt.values[okp]]
            dh_p = np.concatenate(dh_p); da_p = np.concatenate(da_p); dh_b = np.concatenate(dh_b)
            rows.append(dict(segment=seg, form=form, half=half, N=len(rec), LL=ll, LL_per_obs=ll / len(rec), LL_band=ll_band, LL_band_per_obs=ll_band / len(rec),
                             km_from_home_obs=np.average(dh_o, weights=w[okp]), km_from_home_mnl=np.average(dh_p, weights=w), km_from_home_band=np.average(dh_b, weights=w)))
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{T.RES}/loc_heldout.csv", index=False)


# ------------------------------------------------------------------------------------------------ export
def export():
    coef, tabs, search_rows = [], [], []
    for seg in SEGS:
        for f in SEGS[seg]["forms"]:
            p = f"{T.WORK}/locsearch_{seg}_{f}.pkl"
            if not os.path.exists(p): continue
            o = pickle.load(open(p, "rb"))
            for r in o["rows"]: search_rows.append(dict(segment=seg, form=f, **r))
        b = chosen_form(seg)
        if b is None: continue
        form, aic, o = b; F = o["models"]["F"]; spec = F["spec"]; t = F["table"].copy()
        t["segment"] = seg; t["form"] = form; tabs.append(t)
        v = t.set_index("param").value
        coef += [dict(segment=seg if form == "primary" else seg + "_stop", variable="mu_size", value=float(v["mu_size"]))]
        key = coef[-1]["segment"]
        coef.append(dict(segment=key, variable=f"size_{spec.size_base}", value=1.0))
        for c in spec.size_comps: coef.append(dict(segment=key, variable=f"size_{c}", value=float(np.exp(v[f"theta_{c}"]))))
        for k in spec.linear: coef.append(dict(segment=key, variable=k, value=float(v[k])))
        st = dict(segment=seg, form=form, N=F["N"], K=F["K"], LL0=o["LL0"], LLc=o["LLc"], LL=F["LL"], rho2=1 - F["LL"] / o["LL0"], rho2_c=1 - F["LL"] / o["LLc"],
                  AIC=aic, BIC=np.log(F["N"]) * F["K"] - 2 * F["LL"], size_base=spec.size_base, converged=F["converged"], maxgrad=F["maxgrad"])
        pd.DataFrame([st]).to_csv(f"{T.RES}/loc_stats_{seg}.csv", index=False)
        t.to_csv(f"{T.RES}/loc_estimates_{seg}.csv", index=False)
    pd.DataFrame(search_rows).to_csv(f"{T.RES}/loc_search.csv", index=False)
    pd.DataFrame(coef).to_csv(f"{T.RES}/dest_choice_loc.csv", index=False)
    print(pd.DataFrame(coef).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["records", "search", "heldout", "export"]); ap.add_argument("--segments", default=",".join(SEGS))
    a = ap.parse_args()
    if a.cmd == "records":
        for h in ["estimation", "validation"]: records(h)
    elif a.cmd == "search":
        for s in a.segments.split(","):
            for f in SEGS[s]["forms"]: search(s, f)
    elif a.cmd == "heldout": heldout()
    else: export()
