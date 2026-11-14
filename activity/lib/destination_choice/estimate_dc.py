#!/usr/bin/env python3
"""Maximum-likelihood estimation of the destination-choice MNLs on the ESTIMATION half of the 2017/18 RTS (stage 3, 2026-10-22).

    python3 activity/lib/destination_choice/estimate_dc.py search [--segments SHOPPING_primary,...]   # specification search, segmentation and sampling tests
    ~/.venvs/biogeme/bin/python activity/lib/destination_choice/estimate_dc.py biogeme                 # re-estimate the final models with Biogeme (reported)
    python3 activity/lib/destination_choice/estimate_dc.py export                                      # coef_calibrated/dest_choice_mnl.csv + tables

Segments: purpose (SHOPPING, RECREATION, ACCOMPANY, OTHER) x kind (primary destination of a home-based tour; intermediate stop),
and WORK_primary (home -> usual workplace; for the accessibility measures, not used by ABIT, whose workplaces come from SILO).
Specification search (per segment, nested sequence, likelihood-ratio test against the previous model):
  S1 ln size (weights estimated) + linear distance;  S2 piecewise-linear distance (knots 1, 2, 5, 10, 20, 50 km; stops: detour,
  knots 1, 2, 5, 10, 20 km);  S3 + intrazonal (stops: in the zone of either anchor);  S4 + area dummies (Baltimore City, DC,
  Virginia, other states, central business districts);  S5 + land use (retail density, land-use mix);  S6 + county / state
  boundary;  S7 + ln-distance interactions with income, cars, children, age, worker (stops: + tour mode, tour purpose, inbound);
  S8 + time of day x ln distance;  S9 + mode-choice logsum of ABIT, S9t + car generalized time instead (non-nested, AIC),
  S9b + both (the best of S9 / S9t / S9b by AIC is carried on);
  S10 + transit availability for households without a car;  F final: backward elimination of the non-significant terms of
  S10 (|robust t| < 1.96; distance pieces and the size term are kept), size components with a zero weight dropped (LR test).
Then: mu = 1 test, segmentation tests (separate models by income class, car availability, person type, time of day; LR
against the pooled final model), sampling tests (20 / 40 / 80 importance-sampled alternatives, 40 uniform, full choice set on a
subsample).  Results: destination_choice/work/search_<segment>.pkl, destination_choice/results/*.csv.
"""
import argparse, os, pickle, sys, time
import numpy as np
import pandas as pd
from scipy.stats import chi2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_common as C

RES = f"{C.DCD}/results"; os.makedirs(RES, exist_ok=True)
SEGMENTS = [f"{p}_{k}" for p in C.DISC for k in ["primary", "stop"]] + ["WORK_primary"]
SIZE_BASE = {"SHOPPING": "ret", "RECREATION": "pop", "ACCOMPANY": "pop", "OTHER": "pop", "WORK": "oth"}
AREA = ["bc", "dcz", "va", "othst", "cbd"]
SOCIO = ["inc0", "inc2", "car0", "car1", "child", "kid", "senior", "worker"]
STOPX = ["nonauto", "worktour", "inbound"]
TOD = ["am", "pm", "ev"]
R_BASE = 40


def load(half, segment):
    pur, kind = segment.split("_")
    if pur == "WORK":
        rec = pd.read_parquet(f"{C.WORK}/work_records_{half}.parquet"); cand = pd.read_parquet(f"{C.WORK}/work_cand_{half}.parquet")
        rec["tour_purpose"] = "WORK"; rec["position"] = ""
    else:
        rec = pd.read_parquet(f"{C.WORK}/dc_records_{half}.parquet"); cand = pd.read_parquet(f"{C.WORK}/dc_cand_{half}.parquet")
        rec = rec[(rec.purpose == pur) & (rec.kind == kind)]
    rec = rec.reset_index(drop=True); cand = cand[cand.rec.isin(rec.rec.values)]
    return rec, cand


def size_comps(pur):
    b = SIZE_BASE[pur]; comps = ["ret", "off", "oth"] if pur == "WORK" else ["pop", "ret", "off", "oth", "stu"]
    return b, [c for c in comps if c != b]


def sequence(segment):
    import dc_model as M
    pur, kind = segment.split("_"); stop = kind == "stop"; base, comps = size_comps(pur)
    pre = "dt" if stop else "d"; pieces = C.pw_names(pre, C.DKNOTS if stop else C.KNOTS); ln = "lndt" if stop else "lnd"
    intra = ["intra_a", "intra_b"] if stop else ["intra"]
    socio = SOCIO + (STOPX if stop else [])
    tod = [] if pur == "WORK" else TOD
    L = []
    L.append(M.Spec("S1", [pre], base, comps, note="ln size (weights estimated) + linear distance" if not stop else "ln size + linear detour"))
    s = pieces; L.append(M.Spec("S2", s, base, comps, note="piecewise-linear distance" if not stop else "piecewise-linear detour"))
    s = s + intra; L.append(M.Spec("S3", s, base, comps, note="+ intrazonal" if not stop else "+ stop in an anchor zone"))
    s = s + AREA; L.append(M.Spec("S4", s, base, comps, note="+ area dummies"))
    s = s + ["lnretden", "mix"]; L.append(M.Spec("S5", s, base, comps, note="+ retail density, land-use mix"))
    s = s + ["xcounty", "xstate"]; L.append(M.Spec("S6", s, base, comps, note="+ county and state boundary"))
    s = s + [f"{ln}_{x}" for x in socio]; L.append(M.Spec("S7", s, base, comps, note="+ ln-distance x household / person / tour"))
    if tod: s = s + [f"{ln}_{x}" for x in tod]; L.append(M.Spec("S8", s, base, comps, note="+ ln-distance x time of day"))
    L.append(M.Spec("S9", s + ["ls"], base, comps, note="+ mode-choice logsum of ABIT"))
    L.append(M.Spec("S9t", s + ["cgt"], base, comps, note="+ car generalized time instead (non-nested with S9)"))
    L.append(M.Spec("S9b", s + ["ls", "cgt"], base, comps, note="+ logsum and car generalized time"))
    return L


def lr(a, b):
    """LR test of b against the nested a."""
    st = 2 * (b["LL"] - a["LL"]); df = b["K"] - a["K"]
    return st, df, float(chi2.sf(st, df)) if df > 0 else np.nan


def row(res, prev=None, LL0=None):
    r = dict(model=res["spec"].name, note=res["spec"].note, K=res["K"], N=res["N"], LL=res["LL"], AIC=2 * res["K"] - 2 * res["LL"],
             BIC=np.log(res["N"]) * res["K"] - 2 * res["LL"], maxgrad=res["maxgrad"])
    if LL0 is not None: r["rho2"] = 1 - res["LL"] / LL0; r["rho2_adj"] = 1 - (res["LL"] - res["K"]) / LL0
    if prev is not None:
        st, df, p = lr(prev, res); r.update(LR_vs=prev["spec"].name, LR=st, LR_df=df, LR_p=p)
    return r


def fit(spec, rec, alts, lnc, logb, pur, sk, x0=None):
    """x0: tensor in the order of spec.params() or a dict name -> start value (warm start from a previous model)."""
    import dc_model as M
    D = M.Data(rec, alts, lnc, logb, spec, pur, sk)
    res = M.estimate(spec, D, x0=x0); res["LL0"] = M.ll_zero(D)
    return res


def drop_zero_size(spec, res, rec, sets, pur, sk):
    """Size components whose log weight ran to the boundary (weight < 1e-4 of the base) are removed."""
    import dc_model as M
    t = res["table"].set_index("param").value
    keep = [c for c in spec.size_comps if t.get(f"theta_{c}", 0) > np.log(1e-4)]
    if keep == spec.size_comps: return spec, res
    s2 = M.Spec(spec.name, spec.linear, spec.size_base, keep, note=spec.note); return s2, fit(s2, rec, *sets, pur, sk)


def backward(spec, res, rec, sets, pur, sk, log):
    """Backward elimination: drop the least significant non-protected term while |robust t| < 1.96."""
    import dc_model as M
    protected = lambda p: p.startswith("d_") or p.startswith("dt_") or p in ("mu_size", "d", "dt") or p.startswith("theta_")
    while True:
        t = res["table"]; cand = t[~t.param.map(protected) & (t.rob_t.abs() < 1.96)]
        if len(cand) == 0: break
        worst = cand.loc[cand.rob_t.abs().idxmin(), "param"]
        s2 = M.Spec("F", [p for p in spec.linear if p != worst], spec.size_base, spec.size_comps, note="final")
        x0 = res["x"].numpy(); keep = [i for i, p in enumerate(res["spec"].params()) if p != worst]
        import torch
        r2 = fit(s2, rec, *sets, pur, sk, x0=torch.tensor(x0[keep]))
        log.append(dict(dropped=worst, t=float(cand.set_index("param").rob_t[worst]), LL_before=res["LL"], LL_after=r2["LL"]))
        spec, res = s2, r2
    # size components: LR test of each remaining component (drop if not significant)
    changed = True
    while changed and spec.size_comps:
        changed = False
        for c in list(spec.size_comps):
            s2 = M.Spec("F", spec.linear, spec.size_base, [x for x in spec.size_comps if x != c], note="final")
            r2 = fit(s2, rec, *sets, pur, sk)
            if 2 * (res["LL"] - r2["LL"]) < 3.84:
                log.append(dict(dropped=f"size:{c}", t=np.nan, LL_before=res["LL"], LL_after=r2["LL"])); spec, res, changed = s2, r2, True; break
    spec.name = "F"; spec.note = "final (backward elimination)"; res["spec"] = spec
    return spec, res


def search(segment, half="estimation"):
    import dc_model as M
    t0 = time.time(); pur = segment.split("_")[0]; sk = C.skims()
    rec, cand = load(half, segment)
    sets = M.sample_sets(rec, cand, pur, R=R_BASE, seed=2026)
    out = dict(segment=segment, N=len(rec), J=sets[0].shape[1], models={}, rows=[])
    prev = None; LL0 = None
    # normalisation of the size term: the component with the largest estimated weight in S1 becomes the base (weight 1)
    s1 = sequence(segment)[0]; r1 = fit(s1, rec, *sets, pur, sk)
    w = {s1.size_base: 1.0, **{c: float(np.exp(v)) for c, v in zip(s1.size_comps, r1["table"].set_index("param").value[[f"theta_{c}" for c in s1.size_comps]])}}
    base = max(w, key=w.get); out["size_base"] = base; out["size_weights_S1"] = w
    SIZE_BASE[pur] = base
    for spec in sequence(segment):
        warm = dict(zip(prev["spec"].params(), prev["x"].numpy())) if prev is not None else None
        res = fit(spec, rec, *sets, pur, sk, x0=warm)
        LL0 = res["LL0"]
        s8 = out["models"].get("S8", out["models"].get("S7"))
        nested_prev = s8 if spec.name in ("S9", "S9t") else out["models"]["S9"] if spec.name == "S9b" else prev
        out["rows"].append(row(res, nested_prev, LL0)); out["models"][spec.name] = res
        if spec.name not in ("S9", "S9t", "S9b"): prev = res
        if spec.name == "S9b": out["rows"][-1]["LR_vs_S9t"] = 2 * (res["LL"] - out["models"]["S9t"]["LL"])
        print(f"  {segment} {spec.name}: LL {res['LL']:.1f} K {res['K']} ({time.time() - t0:.0f} s)", flush=True)
    # logsum vs car time (non-nested): keep the better by AIC
    aic = lambda m: 2 * m["K"] - 2 * m["LL"]
    top = min([out["models"][k] for k in ("S9", "S9t", "S9b")], key=aic)
    s10 = M.Spec("S10", top["spec"].linear + ["ptav_car0"], top["spec"].size_base, top["spec"].size_comps, note=f"{top['spec'].name} + transit availability, households without a car")
    r10 = fit(s10, rec, *sets, pur, sk, x0=dict(zip(top["spec"].params(), top["x"].numpy()))); out["rows"].append(row(r10, top, LL0)); out["models"]["S10"] = r10
    best = r10 if lr(top, r10)[2] < 0.05 else top
    spec, res = drop_zero_size(best["spec"], best, rec, sets, pur, sk)
    elim = []; spec, res = backward(M.Spec("F", spec.linear, spec.size_base, spec.size_comps), res, rec, sets, pur, sk, elim)
    out["rows"].append(row(res, None, LL0)); out["models"]["F"] = res; out["elimination"] = elim
    st, df, p = lr(res, best); out["rows"][-1].update(LR_vs=best["spec"].name, LR=-st, LR_df=-df, LR_p=p)
    # constants-only reference (area dummies + intrazonal, no size, no impedance): LL(c)
    cons = [v for v in spec.linear if v in AREA + ["intra", "intra_a", "intra_b"]]
    rc = fit(M.Spec("C", cons or ["intra"], spec.size_base, [], mu_fixed=0.0, note="constants only (area, intrazonal)"), rec, *sets, pur, sk)
    out["LLc"] = rc["LL"]; out["LL0"] = LL0
    # mu = 1
    r1 = fit(M.Spec("F_mu1", spec.linear, spec.size_base, spec.size_comps, mu_fixed=1.0, note="final with mu = 1"), rec, *sets, pur, sk)
    out["mu1"] = dict(LL=r1["LL"], LR=2 * (res["LL"] - r1["LL"]), p=float(chi2.sf(2 * (res["LL"] - r1["LL"]), 1)))
    print(f"  {segment} final: LL {res['LL']:.1f} K {res['K']} ({time.time() - t0:.0f} s)", flush=True)
    out["segmentation"] = segmentation(segment, spec, res, rec, cand, sets, pur, sk)
    out["sampling"] = sampling_tests(segment, spec, res, rec, cand, pur, sk)
    out["time_s"] = time.time() - t0
    for m in out["models"].values(): m.pop("x_grad", None)
    pickle.dump(out, open(f"{C.WORK}/search_{segment}.pkl", "wb"))
    print(f"{segment}: done in {time.time() - t0:.0f} s", flush=True)
    return out


def groups_of(rec):
    pt = np.select([rec.occ == 1, rec.occ == 3, rec.occ == 4], ["worker", "student", "retiree"], "other")
    return {"income class": rec.inc_cls.map({0: "low", 1: "middle", 2: "high"}).values, "car availability": rec.car_cls.map({0: "no car", 1: "cars < drivers", 2: "cars >= drivers"}).values,
            "person type": pt, "time of day": rec.tod.map({0: "AM 6-9", 1: "midday 9-15", 2: "PM 15-19", 3: "evening 19-6"}).values}


def segmentation(segment, spec, res, rec, cand, sets, pur, sk):
    import dc_model as M
    out = []
    alts, lnc, logb = sets
    for dim, g in groups_of(rec).items():
        if pur == "WORK" and dim == "time of day": continue
        LLs, Ks, ns, ok = 0.0, 0, {}, True
        for lev in sorted(set(g)):
            m = g == lev; ns[lev] = int(m.sum())
            if m.sum() < 150: ok = False; break
            try:
                r = fit(M.Spec("G", spec.linear, spec.size_base, spec.size_comps), rec[m].reset_index(drop=True), alts[m], lnc[m], logb[m], pur, sk, x0=res["x"].clone())
                LLs += r["LL"]; Ks += r["K"]
            except Exception: ok = False; break
        if not ok:
            out.append(dict(dimension=dim, groups=ns, tested=False)); continue
        st = 2 * (LLs - res["LL"]); df = Ks - res["K"]
        out.append(dict(dimension=dim, groups=ns, tested=True, LL_segmented=LLs, K_segmented=Ks, LR=st, df=df, p=float(chi2.sf(st, df)),
                        AIC_pooled=2 * res["K"] - 2 * res["LL"], AIC_segmented=2 * Ks - 2 * LLs,
                        BIC_pooled=np.log(len(rec)) * res["K"] - 2 * res["LL"], BIC_segmented=np.log(len(rec)) * Ks - 2 * LLs))
    return out


def sampling_tests(segment, spec, res, rec, cand, pur, sk):
    import dc_model as M
    rows = []
    for R, prot, seed in [(20, "importance", 11), (40, "importance", 12), (80, "importance", 13), (40, "uniform", 14)]:
        sets = M.sample_sets(rec, cand, pur, R=R, seed=seed, protocol=prot)
        r = fit(spec, rec, *sets, pur, sk, x0=res["x"].clone())
        rows.append(dict(R=R, protocol=prot, seed=seed, J=sets[0].shape[1], LL=r["LL"], **{p: v for p, v in zip(r["table"].param, r["table"].value)},
                         **{f"se_{p}": v for p, v in zip(r["table"].param, r["table"].rob_se)}))
    # full choice set on a subsample (memory), with the base sampling on the same subsample for comparison
    n = min(len(rec), 1500); sub = rec.sample(n, random_state=7).reset_index(drop=True); cs = cand[cand.rec.isin(sub.rec)]
    fs = M.full_sets(sub, cs); r = fit(spec, sub, *fs, pur, sk, x0=res["x"].clone())
    rows.append(dict(R=1588, protocol="full set (subsample)", seed=0, J=1588, N=n, LL=r["LL"], **{p: v for p, v in zip(r["table"].param, r["table"].value)},
                     **{f"se_{p}": v for p, v in zip(r["table"].param, r["table"].rob_se)}))
    ss = M.sample_sets(sub, cs, pur, R=R_BASE, seed=15); r = fit(spec, sub, *ss, pur, sk, x0=res["x"].clone())
    rows.append(dict(R=40, protocol="importance (same subsample)", seed=15, J=ss[0].shape[1], N=n, LL=r["LL"], **{p: v for p, v in zip(r["table"].param, r["table"].value)},
                     **{f"se_{p}": v for p, v in zip(r["table"].param, r["table"].rob_se)}))
    return pd.DataFrame(rows)


def biodata(segment, half="estimation"):
    """Wide-format data of the final specification for Biogeme (the sampled sets of the search: R = 40, seed 2026)."""
    import json, dc_model as M
    o = pickle.load(open(f"{C.WORK}/search_{segment}.pkl", "rb")); spec = o["models"]["F"]["spec"]; pur = segment.split("_")[0]
    rec, cand = load(half, segment); sk = C.skims()
    alts, lnc, logb = M.sample_sets(rec, cand, pur, R=R_BASE, seed=2026)
    pad = alts < 0; a = np.where(pad, 0, alts); J = alts.shape[1]
    F = M.features(rec, a, spec.linear, sk, pur); S = M.size_arrays(a, [spec.size_base] + spec.size_comps)
    cols = {}
    for j in range(J):
        for k in spec.linear: cols[f"{k}_{j}"] = F[k][:, j]
        for c in [spec.size_base] + spec.size_comps: cols[f"{c}_{j}"] = S[c][:, j]
        cols[f"lnc_{j}"] = np.where(pad[:, j], 0.0, lnc[:, j]); cols[f"b_{j}"] = np.where(pad[:, j], 0.0, np.exp(logb[:, j]))
        cols[f"av_{j}"] = (~pad[:, j]).astype(float)
    df = pd.DataFrame(cols); df.to_parquet(f"{C.WORK}/bio_{segment}.parquet", index=False)
    t = o["models"]["F"]["table"]
    json.dump(dict(segment=segment, J=J, N=len(rec), linear=spec.linear, size_base=spec.size_base, size_comps=spec.size_comps,
                   start={p: float(v) for p, v in zip(t.param, t.value)}, LL_torch=o["models"]["F"]["LL"]), open(f"{C.WORK}/bio_{segment}.json", "w"), indent=1)
    print(f"{segment}: Biogeme data {df.shape}")


def hansen():
    """alpha, beta of the Hansen measure sum_j (1 + E_j)^alpha exp(beta t_ij) by ML on the home -> work choices of the estimation
    half (E = all jobs, t = car minutes): the MNL P(j | i) ~ (1 + E_j)^alpha exp(beta t_ij) with the same sampled sets."""
    import json, dc_model as M
    rec, cand = load("estimation", "WORK_primary"); sk = C.skims()
    sets = M.sample_sets(rec, cand, "WORK", R=R_BASE, seed=2026)
    r = fit(M.Spec("H", ["ctime"], "jobs", [], note="Hansen: ln(1 + jobs) and car time"), rec, *sets, "WORK", sk)
    t = r["table"].set_index("param")
    out = dict(alpha=float(t.value["mu_size"]), alpha_se=float(t.rob_se["mu_size"]), beta=float(t.value["ctime"]), beta_se=float(t.rob_se["ctime"]),
               LL=r["LL"], LL0=r["LL0"], N=r["N"], note="P(j|i) ~ (1+E_j)^alpha exp(beta t_ij); E = all jobs of jj_2016, t = car minutes (2016 base skim); estimation half")
    json.dump(out, open(f"{RES}/hansen_work.json", "w"), indent=1); print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["search", "biodata", "biogeme", "export", "hansen"]); ap.add_argument("--segments", default=",".join(SEGMENTS))
    a = ap.parse_args()
    if a.cmd == "search":
        for s in a.segments.split(","): search(s)
    elif a.cmd == "hansen": hansen()
    elif a.cmd == "biodata":
        for s in a.segments.split(","): biodata(s)
    elif a.cmd == "biogeme":
        import estimate_biogeme; estimate_biogeme.main(a.segments.split(","))
    else:
        import export_dc; export_dc.main()
