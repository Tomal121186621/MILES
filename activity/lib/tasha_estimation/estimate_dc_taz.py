#!/usr/bin/env python3
"""Re-estimation of the discretionary destination models of record with the survey's traffic-zone locations (TAZ variant,
2026-10-28; robustness check, nothing of the model of record is changed).

    python3 activity/lib/tasha_estimation/estimate_dc_taz.py primary     # the four primaries with the complexity term (as estimate_complexity.py)
    python3 activity/lib/tasha_estimation/estimate_dc_taz.py stop        # the four sequential stop models (as estimate_stops_seq.py)
    python3 activity/lib/tasha_estimation/estimate_dc_taz.py gender      # control: the sequential stop models on the tract records with male recoded only

Records: prep_dc_taz.py (TAZ locations, location mixture, male recoded).  Same specifications (the final F of the search,
+ ln d x multi for primaries), same sampling (dc_model.sample_sets, R = 40, D0 6 / 3 km, seed 2026), same warm starts (the
pooled Biogeme F estimates), same optimiser (dc_model.estimate: L-BFGS-B, exact Hessian, robust sandwich covariance);
the likelihood is the location mixture of dc_taz_engine.py.
Outputs (tasha_estimation/results/, new names): cx_estimates_taz.csv, cx_tests_taz.csv, cx_heldout_taz.csv, dest_choice_primary_cx_taz.csv,
seq_estimates_taz.csv, seq_tests_taz.csv, seq_heldout_taz.csv, dest_choice_stop_seq_taz.csv, seq_estimates_tract_male.csv,
collin_<seg>_taz.csv (demeaned correlation), vif_<seg>_taz.csv, heldout_tld_taz.csv; work/fit_<seg>_taz.pkl; Biogeme data
work/bio_<seg>_taz.parquet / .json (biogeme_dc_taz.py).
Held-out (validation and estimation half, full choice set): old = the model of record on its tract records (observed = tract
internal point), new = the TAZ model on the TAZ records (observed = the TAZ mixture); cross: old coefficients on the TAZ records,
new coefficients on the tract records (validation half), so that the predictive LL is compared on the same data.
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, pickle, sys
import numpy as np
import pandas as pd
NT = int(os.environ.get("TAZ_THREADS", "4"))
import torch                      # noqa: E402
torch.set_num_threads(NT)
from scipy.stats import chi2      # noqa: E402
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import te_common as T             # noqa: E402
import dc_common as C             # noqa: E402
import dc_taz_engine as X         # noqa: E402  (wraps dc_model.ll_obs)
import dc_model as M              # noqa: E402
import estimate_dc as E           # noqa: E402
from estimate_complexity import multi_flag, final_spec   # noqa: E402
from estimate_stops_seq import with_seq                  # noqa: E402
from rts_common import DIST_LABELS                       # noqa: E402

WORK, RES = T.WORK, T.RES


def load_taz(half, seg):
    pur, kind = seg.split("_")
    rec = pd.read_parquet(f"{WORK}/dc_rec_{half}_taz.parquet"); rec = rec[(rec.purpose == pur) & (rec.kind == kind)].reset_index(drop=True)
    cand = pd.read_parquet(f"{WORK}/dc_cand_{half}_taz.parquet"); cfg = pd.read_parquet(f"{WORK}/dc_cfg_{half}_taz.parquet")
    return rec, cand[cand.rec.isin(rec.rec)], cfg[cfg.rec.isin(rec.rec)]


def old_coef(seg, kind):
    f = f"{RES}/cx_estimates.csv" if kind == "primary" else f"{RES}/seq_estimates.csv"
    t = pd.read_csv(f); t = t[t.segment == seg]; return dict(zip(t.param, t.value))


def coef_rows(seg, spec, v):
    out = [dict(segment=seg, variable="mu_size", value=float(v["mu_size"])), dict(segment=seg, variable=f"size_{spec.size_base}", value=1.0)]
    out += [dict(segment=seg, variable=f"size_{c}", value=float(np.exp(v[f"theta_{c}"]))) for c in spec.size_comps]
    return out + [dict(segment=seg, variable=k, value=float(v[k])) for k in spec.linear]


def save_fit(seg, res, extra):
    D = res.pop("D", None)
    pickle.dump(dict(table=res["table"], cov=res["cov"], LL=res["LL"], LL0=res["LL0"], K=res["K"], N=res["N"], x=res["x"].numpy(), maxgrad=res["maxgrad"],
                     converged=res["converged"], message=res["message"], at_bound=res["at_bound"], spec=res["spec"], **extra), open(f"{WORK}/fit_{seg}_taz.pkl", "wb"))
    return D


def collin(seg, D, spec, res):
    R, vif = X.collinearity(D, spec, res)
    R.to_csv(f"{RES}/collin_{seg}_taz.csv"); vif.to_csv(f"{RES}/vif_{seg}_taz.csv")
    print(f"  {seg}: max |r| {np.abs(R.values - np.eye(len(R))).max():.3f}, max VIF {vif.max():.1f} ({vif.idxmax()})", flush=True)


def tld_rows(seg, half, model, tour, h, kind):
    return [dict(segment=seg, half=half, model=model, tour=tour, kind=kind, bin=lab, share=float(s)) for lab, s in zip(DIST_LABELS, h)]


def primary():
    sk = C.skims(); tabs, tests, ho, coef, tld = [], [], [], [], []
    for p_ in C.DISC:
        seg = f"{p_}_primary"; pur = p_
        rec, cand, cfg = load_taz("estimation", seg); rec["multi"] = multi_flag(rec, "estimation")
        sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
        spec, x0 = final_spec(seg)
        r0 = X.fit(spec, rec, cfg, *sets, pur, sk, x0=x0); r0.pop("D")
        spec1 = M.Spec("FX", spec.linear + ["lnd_multi"], spec.size_base, spec.size_comps, note="F + ln(distance) x tour with stops")
        r1 = X.fit(spec1, rec, cfg, *sets, pur, sk, x0={**x0, "lnd_multi": 0.0})
        # old coefficients on the TAZ sampled sets (same data): LL comparison
        xo = old_coef(seg, "primary"); xov = np.array([xo[p] for p in spec1.params()])
        with torch.no_grad(): LL_old_on_taz = float(M.ll_obs(torch.tensor(xov), spec1, r1["D"]).sum())
        lr = 2 * (r1["LL"] - r0["LL"]); N = len(rec)
        tests.append(dict(segment=seg, N=N, share_multi=float(np.average(rec.multi, weights=rec.w)), LL0=r1["LL0"], LL_F=r0["LL"], LL_FX=r1["LL"], LR=lr, df=1,
                          p=float(chi2.sf(lr, 1)), K=r1["K"], AIC_F=2 * r0["K"] - 2 * r0["LL"], AIC_FX=2 * r1["K"] - 2 * r1["LL"],
                          BIC_F=np.log(N) * r0["K"] - 2 * r0["LL"], BIC_FX=np.log(N) * r1["K"] - 2 * r1["LL"], LL_old_coef_on_taz=LL_old_on_taz,
                          maxgrad=r1["maxgrad"], converged=r1["converged"], J=sets[0].shape[1], n_cfg=len(cfg) / N))
        t = r1["table"].assign(segment=seg); tabs.append(t); v = t.set_index("param").value; coef += coef_rows(seg, spec1, v)
        collin(seg, r1["D"], spec1, r1)
        X.bio_export(f"{WORK}/bio_{seg}_taz", spec1, rec, cfg, *sets, pur, sk, {p: float(a) for p, a in zip(t.param, t.value)})
        save_fit(seg, r1, dict(sets_J=sets[0].shape[1]))
        print(tests[-1], flush=True)
        xn = r1["x"].numpy()
        for half in ["estimation", "validation"]:
            rn, cn, gn = load_taz(half, seg); rn["multi"] = multi_flag(rn, half)
            ro, co = E.load(half, seg); ro["multi"] = multi_flag(ro, half); go = X.single_cfg(ro)
            runs = [("old (tract)", "old", ro, co, go, xov, "pt"), ("new (TAZ)", "new", rn, cn, gn, xn, "mix")]
            if half == "validation": runs += [("old coef on TAZ records", "cross", rn, cn, gn, xov, "mix"), ("new coef on tract records", "cross", ro, co, go, xn, "pt")]
            for lab, kind_, r_, c_, g_, xv, om in runs:
                h = X.heldout(r_, c_, g_, spec1, xv, pur, sk, obs=om)
                for tour, m in [("simple", r_.multi.values == 0), ("with stops", r_.multi.values == 1), ("all", np.ones(len(r_), bool))]:
                    w = r_.w.values; ok = m & np.isfinite(h["km_obs"])
                    ho.append(dict(segment=seg, half=half, model=lab, data="TAZ" if om == "mix" else "tract", tour=tour, N=int(m.sum()), LL_per_obs=float(h["LL"][m].mean()),
                                   km_obs=float(np.average(h["km_obs"][ok], weights=w[ok])), km_pred=float(np.average(h["km_pred"][m], weights=w[m])),
                                   KS=X.ks(h["tld_pred"], h["tld_obs"]) if tour == "all" else np.nan))
                tld += tld_rows(seg, half, lab, "all", h["tld_pred"], "pred") + tld_rows(seg, half, lab, "all", h["tld_obs"], "obs")
                print("  ", ho[-1], flush=True)
        pd.concat(tabs).to_csv(f"{RES}/cx_estimates_taz.csv", index=False); pd.DataFrame(tests).to_csv(f"{RES}/cx_tests_taz.csv", index=False)
        pd.DataFrame(ho).to_csv(f"{RES}/cx_heldout_taz.csv", index=False); pd.DataFrame(coef).to_csv(f"{RES}/dest_choice_primary_cx_taz.csv", index=False)
        pd.DataFrame(tld).to_csv(f"{RES}/cx_tld_taz.csv", index=False)


def stop():
    sk = C.skims(); tabs, tests, ho, coef, tld = [], [], [], [], []
    for p_ in C.DISC:
        seg = f"{p_}_stop"; pur = p_; sseg = seg.replace("_stop", "_seq_stop")
        spec, x0 = final_spec(seg)
        rec, cand, cfg = load_taz("estimation", seg)
        sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
        r1 = X.fit(spec, rec, cfg, *sets, pur, sk, x0=x0)
        xo = old_coef(seg, "stop"); xov = np.array([xo[p] for p in spec.params()])
        with torch.no_grad(): LL_old_on_taz = float(M.ll_obs(torch.tensor(xov), spec, r1["D"]).sum())
        N = len(rec)
        tests.append(dict(segment=seg, N=N, LL0=r1["LL0"], LL=r1["LL"], K=r1["K"], AIC=2 * r1["K"] - 2 * r1["LL"], BIC=np.log(N) * r1["K"] - 2 * r1["LL"],
                          LL_old_coef_on_taz=LL_old_on_taz, maxgrad=r1["maxgrad"], converged=r1["converged"], J=sets[0].shape[1], n_cfg=len(cfg) / N))
        t = r1["table"].assign(segment=seg, N=N, LL=r1["LL"]); tabs.append(t); v = t.set_index("param").value; coef += coef_rows(sseg, spec, v)
        collin(seg, r1["D"], spec, r1)
        X.bio_export(f"{WORK}/bio_{seg}_taz", spec, rec, cfg, *sets, pur, sk, {p: float(a) for p, a in zip(t.param, t.value)})
        save_fit(seg, r1, dict(sets_J=sets[0].shape[1]))
        print(tests[-1], flush=True)
        xn = r1["x"].numpy()
        for half in ["estimation", "validation"]:
            rn, cn, gn = load_taz(half, seg)
            ro, co = E.load(half, seg); ro = with_seq(ro); co = co[co.rec.isin(ro.rec)]; go = X.single_cfg(ro)
            ro_fix = ro.assign(male=1.0 - ro.male)          # tract records with male recoded (for the cross evaluation of the new model)
            runs = [("old (tract)", ro, co, go, xov, "pt"), ("new (TAZ)", rn, cn, gn, xn, "mix")]
            if half == "validation": runs += [("old coef on TAZ records", rn, cn, gn, xov, "mix"), ("new coef on tract records", ro_fix, co, go, xn, "pt")]
            for lab, r_, c_, g_, xv, om in runs:
                h = X.heldout(r_, c_, g_, spec, xv, pur, sk, obs=om)
                for pos in ["out", "in", "all"]:
                    m = np.ones(len(r_), bool) if pos == "all" else (r_.position.values == pos)
                    w = r_.w.values; ok = m & np.isfinite(h["km_obs"])
                    ho.append(dict(segment=seg, half=half, model=lab, data="TAZ" if om == "mix" else "tract", position=pos, N=int(m.sum()), LL_per_obs=float(h["LL"][m].mean()),
                                   km_leg_obs=float(np.average(h["km_obs"][ok], weights=w[ok])), km_leg_pred=float(np.average(h["km_pred"][m], weights=w[m])),
                                   KS=X.ks(h["tld_pred"], h["tld_obs"]) if pos == "all" else np.nan))
                tld += tld_rows(seg, half, lab, "all", h["tld_pred"], "pred") + tld_rows(seg, half, lab, "all", h["tld_obs"], "obs")
                print("  ", ho[-1], flush=True)
        pd.concat(tabs).to_csv(f"{RES}/seq_estimates_taz.csv", index=False); pd.DataFrame(tests).to_csv(f"{RES}/seq_tests_taz.csv", index=False)
        pd.DataFrame(ho).to_csv(f"{RES}/seq_heldout_taz.csv", index=False); pd.DataFrame(coef).to_csv(f"{RES}/dest_choice_stop_seq_taz.csv", index=False)
        pd.DataFrame(tld).to_csv(f"{RES}/seq_tld_taz.csv", index=False)


def gender():
    """Control: the sequential stop models on the tract records of the model of record with male recoded only (attribution of
    the coefficient changes to the gender fix vs the TAZ locations)."""
    sk = C.skims(); tabs = []
    for p_ in C.DISC:
        seg = f"{p_}_stop"; pur = p_; spec, x0 = final_spec(seg)
        rec, cand = E.load("estimation", seg); rs = with_seq(rec); cs = cand[cand.rec.isin(rs.rec)]
        rs["male"] = 1.0 - rs.male                 # pp.gender == 2 (RTS male) = SILO male after the recode {1: 2, 2: 1}
        sets = M.sample_sets(rs, cs, pur, R=E.R_BASE, seed=2026)
        r = E.fit(spec, rs, *sets, pur, sk, x0=x0)
        tabs.append(r["table"].assign(segment=seg, N=len(rs), LL=r["LL"])); print(seg, "LL", round(r["LL"], 2), flush=True)
        pd.concat(tabs).to_csv(f"{RES}/seq_estimates_tract_male.csv", index=False)


def seconddraw(seed=2027):
    """second-draw stability: the final TAZ models (specification of record) re-estimated on a second set of sampled choice
    sets (seed 2027 instead of 2026, same R and D0, warm start at the first-draw estimates) -> results/seconddraw_taz.csv"""
    sk = C.skims(); rows = []
    for kind in ["primary", "stop"]:
        f = pd.read_csv(f"{RES}/{'cx' if kind == 'primary' else 'seq'}_estimates_taz.csv")
        for p_ in C.DISC:
            seg = f"{p_}_{kind}"; pur = p_; spec, _ = final_spec(seg)
            if kind == "primary": spec = M.Spec("FX", spec.linear + ["lnd_multi"], spec.size_base, spec.size_comps)
            t1 = f[f.segment == seg].set_index("param"); rec, cand, cfg = load_taz("estimation", seg)
            if kind == "primary": rec["multi"] = multi_flag(rec, "estimation")
            sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=seed)
            r = X.fit(spec, rec, cfg, *sets, pur, sk, x0=dict(zip(t1.index, t1.value))); r.pop("D"); t2 = r["table"].set_index("param")
            for p in t2.index:
                rows.append(dict(segment=seg, param=p, draw1=t1.value[p], se1=t1.rob_se[p], draw2=t2.value[p], se2=t2.rob_se[p], diff_over_se=(t2.value[p] - t1.value[p]) / t1.rob_se[p]))
            print(seg, "LL2", round(r["LL"], 2), flush=True)
            pd.DataFrame(rows).to_csv(f"{RES}/seconddraw_taz.csv", index=False)


def biosub(segs, n=1500):
    """Biogeme check on a subsample (the full mixture Hessian / expression of some segments exceeds the memory budget):
    n records (random_state 7, as the full-set sampling test of estimate_dc.py), the same sampling (R = 40, seed 2026), PyTorch
    fit from the pooled Biogeme F warm start -> results/<kind>_estimates_<seg>_taz_sub.csv, work/bio_<seg>_taz_sub.*"""
    sk = C.skims()
    for seg in segs:
        pur, kind = seg.split("_"); spec, x0 = final_spec(seg)
        rec, cand, cfg = load_taz("estimation", seg)
        if kind == "primary":
            rec["multi"] = multi_flag(rec, "estimation"); spec = M.Spec("FX", spec.linear + ["lnd_multi"], spec.size_base, spec.size_comps); x0 = {**x0, "lnd_multi": 0.0}
        rec = rec.sample(min(n, len(rec)), random_state=7).reset_index(drop=True); cand = cand[cand.rec.isin(rec.rec)]; cfg = cfg[cfg.rec.isin(rec.rec)]
        sets = M.sample_sets(rec, cand, pur, R=E.R_BASE, seed=2026)
        r = X.fit(spec, rec, cfg, *sets, pur, sk, x0=x0); r.pop("D")
        r["table"].assign(segment=seg, N=len(rec), LL=r["LL"]).to_csv(f"{RES}/{'cx' if kind == 'primary' else 'seq'}_estimates_{seg}_taz_sub.csv", index=False)
        X.bio_export(f"{WORK}/bio_{seg}_taz_sub", spec, rec, cfg, *sets, pur, sk, {})
        print(seg, "sub N", len(rec), "LL", round(r["LL"], 4), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "biosub": biosub(sys.argv[2].split(","))
    elif sys.argv[1] == "seconddraw": seconddraw()
    else: {"primary": primary, "stop": stop, "gender": gender}[sys.argv[1]]()
