#!/usr/bin/env python3
"""Estimated return-home rule of the TASHA generator (stage 3 finalisation, 2026-10-23): a binary logit of returning home
between two consecutive out-of-home episodes, estimated by maximum likelihood on the ESTIMATION half of the 2017/18 RTS
(unweighted; robust sandwich standard errors), validated on the validation half.  No calibration factor.

    python3 activity/lib/tasha_estimation/estimate_return_home.py estimate     # specification A (with the gap): results/rh_search.csv, rh_estimates.csv, rh_heldout.csv,
                                                 #   rh_sample.csv, tasha_return_home_gap.csv
    python3 activity/lib/tasha_estimation/estimate_return_home.py nogap        # specification B (model of record): results/rh_nogap_*.csv, tasha_return_home.csv
    python3 activity/lib/tasha_estimation/estimate_return_home.py check RUN... # returns home by person type and number of out-of-home episodes: survey vs model runs

Observation: a pair (a, e) of consecutive out-of-home episodes of a person-day (episodes as in build_distributions.py: one per
trip destination); y = 1 if the person went home between them (any home episode between a and e).  Excluded:
  - pairs of two work episodes (a home episode between two work episodes is the RHW activity type, generated separately);
  - pairs with an unknown zone of a, e or home, or an unknown end of a;
  - pairs whose time at home would be shorter than home.return.min.slack (5 min) on the car skims (infeasible in the model,
    which never sends a person home then); their share of returns home is reported.
Variables (MarylandTashaGenerator.returnHomeProb computes the same quantities from the scheduled episodes):
  slack = e.start - a.end - car minutes a -> home - car minutes home -> e (the time at home if the person went home; car skim of
          the 2016 base, whole minutes, at least 1 min between different zones), piecewise-linear in hours (knots 0.5, 1, 2, 4)
          and ln(minutes); detour via home d(a,home) + d(home,e) - d(a,e) and ln(1 + detour) (km, car-distance skim, intrazonal
          0.5 sqrt(area)); d(a, home); purposes of a and e (work: WB, WAHB, PW, SW; school; accompany; shopping; joint; base:
          other individual discretionary); person segment (worker, student K-12, post-secondary, retiree, toddler; base:
          non-worker); out-of-home episodes of the person-day (3, 4, 5+; base 2); time of day of the end of a (before 9:00,
          15-19, from 19; base 9-15).
Specification search: nested sequence R1 .. R5 with LR tests, then backward elimination of the terms with |robust t| < 1.96
(the constant and the slack terms are kept).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import te_common as T                    # noqa: E402
import dc_common as C                    # noqa: E402
from activity_metrics import dist_matrix     # noqa: E402

MIN_SLACK = 5.0
WORKT = {"WB", "WAHB", "PW", "SW"}; JOINT = {"JO_REC", "JO_OTH", "JS"}
VARS = ["const", "sl_0_05", "sl_05_1", "sl_1_2", "sl_2_4", "sl_4_inf", "lnslack", "detour_km", "lndetour", "dhome_km",
        "a_work", "a_school", "a_acc", "a_shop", "a_joint", "e_work", "e_school", "e_acc", "e_shop", "e_joint",
        "worker", "stud_k12", "stud_ps", "retiree", "toddler", "nep3", "nep4", "nep5", "am", "pm", "ev", "jj", "jmand"]
STEPS = [("R1", ["const", "sl_0_05", "sl_05_1", "sl_1_2", "sl_2_4", "sl_4_inf"], "constant + piecewise-linear slack (h)"),
         ("R2", ["lnslack", "detour_km", "lndetour", "dhome_km"], "+ ln slack, detour via home, distance to home"),
         ("R3", ["a_work", "a_school", "a_acc", "a_shop", "a_joint", "e_work", "e_school", "e_acc", "e_shop", "e_joint"], "+ purposes of the two episodes"),
         ("R4", ["worker", "stud_k12", "stud_ps", "retiree", "toddler"], "+ person segment"),
         ("R5", ["nep3", "nep4", "nep5", "am", "pm", "ev"], "+ number of out-of-home episodes, time of day")]
KEEP = {"const", "sl_0_05", "sl_05_1", "sl_1_2", "sl_2_4", "sl_4_inf"}
PTYPE = {"worker_usual": "worker", "worker_home": "worker", "worker_none": "worker", "student_elementary": "student 5-17", "student_middle": "student 5-17",
         "student_high": "student 5-17", "student_postsec": "student 18+", "nonworker": "non-worker", "retiree": "retiree", "toddler": "toddler"}


def tt_matrix():
    t = C.skims()["t"].astype(float); t = np.where(np.isfinite(t), t, 999.0); return np.maximum(t, 1.0)


def pairs(half):
    """One row per pair of consecutive out-of-home episodes of a person-day."""
    f = f"{T.WORK}/rh_pairs_wbs_{half}.parquet"
    if os.path.exists(f): return pd.read_parquet(f)
    e = T.episodes(half).sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    # work-based subtours (2026-11-03): the outing and the return to the workplace are generated by the subtour model and chained
    # directly; they leave the pairs, and the work episode they belong to ends at the end of its last continuation (the next
    # remaining row's departure)
    import build_distributions as TD
    e = TD.subtours(e); e = e[~(e.wbs | e.wbs_cont)].reset_index(drop=True)
    m = C.id2idx(); dm = dist_matrix(); tm = tt_matrix()
    e["home"] = e.is_home
    e["end"] = e.groupby("person_id").dep_min.shift(-1)          # departure of the next trip = end of the episode
    out = e[~e.home].copy()
    out["nep"] = out.groupby("person_id").tripno.transform("size")
    out["k"] = out.groupby("person_id").cumcount()
    rows = []
    idx = e.index.values; pid = e.person_id.values; home = e.home.values
    # position of every out-of-home episode in the full sequence, and the next out-of-home episode of the same person
    pos = out.index.values; nxt = np.r_[pos[1:], -1]; same = np.r_[out.person_id.values[1:] == out.person_id.values[:-1], False]
    a = out[same].copy(); b = out.loc[nxt[same]].copy()
    ia, ib = a.index.values, b.index.values
    a = a.reset_index(drop=True); b = b.reset_index(drop=True); a["ia"] = ia; b["ia"] = ib
    p = pd.DataFrame({"person_id": a.person_id, "household_id": a.household_id, "seg": a.seg, "nep": a.nep, "a_type": a.type, "e_type": b.type,
                      "a_purpose": a.purpose, "e_purpose": b.purpose, "a_end": a.end, "e_start": b.arr_min, "az": a.dz, "ez": b.dz, "hz": a.hz,
                      "y": (b.ia - a.ia > 1).astype(int), "w": a.wttrdfin})
    p["a_joint"] = p.a_type.isin(JOINT).astype(int); p["e_joint"] = p.e_type.isin(JOINT).astype(int)
    ok = p.az.gt(0) & p.ez.gt(0) & p.hz.gt(0) & p.a_end.notna() & p.a_type.notna() & p.e_type.notna()
    p = p[ok].copy()
    ai, ei, hi = m[p.az.values], m[p.ez.values], m[p.hz.values]
    p["slack"] = (p.e_start - p.a_end) - tm[ai, hi] - tm[hi, ei]
    dah, dhe, dae = dm[p.az.values, p.hz.values], dm[p.hz.values, p.ez.values], dm[p.az.values, p.ez.values]
    p["detour"] = np.maximum(0.0, dah + dhe - dae); p["dah"] = dah
    p["workwork"] = p.a_type.isin(WORKT) & p.e_type.isin(WORKT)
    p.to_parquet(f, index=False); return p


def design(p):
    h = p.slack.values / 60.0; X = pd.DataFrame(index=p.index)
    X["const"] = 1.0; X["sl_0_05"] = np.minimum(h, 0.5); X["sl_05_1"] = np.clip(h - 0.5, 0, 0.5); X["sl_1_2"] = np.clip(h - 1, 0, 1)
    X["sl_2_4"] = np.clip(h - 2, 0, 2); X["sl_4_inf"] = np.maximum(h - 4, 0); X["lnslack"] = np.log(np.maximum(1.0, p.slack.values))
    X["detour_km"] = p.detour.values; X["lndetour"] = np.log1p(p.detour.values); X["dhome_km"] = p.dah.values
    for s_, col in [("a", "a"), ("e", "e")]:
        ty = p[f"{col}_type"]; pu = p[f"{col}_purpose"]
        X[f"{s_}_work"] = ty.isin(WORKT).astype(float); X[f"{s_}_school"] = ty.eq("SCH").astype(float)
        X[f"{s_}_acc"] = pu.eq("ACCOMPANY").astype(float); X[f"{s_}_shop"] = pu.eq("SHOPPING").astype(float); X[f"{s_}_joint"] = p[f"{col}_joint"].astype(float)
    sg = p.seg.astype(str)
    X["worker"] = sg.str.startswith("worker").astype(float); X["stud_k12"] = sg.isin(["student_elementary", "student_middle", "student_high"]).astype(float)
    X["stud_ps"] = sg.eq("student_postsec").astype(float); X["retiree"] = sg.eq("retiree").astype(float); X["toddler"] = sg.eq("toddler").astype(float)
    X["nep3"] = p.nep.eq(3).astype(float); X["nep4"] = p.nep.eq(4).astype(float); X["nep5"] = p.nep.ge(5).astype(float)
    ae = p.a_end.values % 1440
    X["am"] = (ae < 540).astype(float); X["pm"] = ((ae >= 900) & (ae < 1140)).astype(float); X["ev"] = (ae >= 1140).astype(float)
    # 2026-11-03: joint episodes are linked to each other far more often than to individual or mandatory episodes (travel together)
    X["jj"] = X.a_joint * X.e_joint
    mand_a = (X.a_work + X.a_school).clip(upper=1); mand_e = (X.e_work + X.e_school).clip(upper=1)
    X["jmand"] = (X.a_joint * mand_e + X.e_joint * mand_a).clip(upper=1)
    return X[VARS]


def sample(half):
    p = pairs(half); q = p[~p.workwork]
    inf = q[q.slack < MIN_SLACK]
    info = dict(half=half, pairs=len(p), workwork=int(p.workwork.sum()), infeasible=len(inf), infeasible_returns=int(inf.y.sum()),
                infeasible_return_share_w=float(np.average(inf.y, weights=inf.w)) if len(inf) else np.nan,
                returns_total_w=float((q.y * q.w).sum()), returns_infeasible_w=float((inf.y * inf.w).sum()))
    return q[q.slack >= MIN_SLACK].copy(), info


def fit(X, y, cols):
    m = sm.Logit(y, X[cols]).fit(disp=0, maxiter=200, cov_type="HC0")
    return m


def estimate():
    est, ie = sample("estimation"); val, iv = sample("validation")
    print("sample", ie, iv, sep="\n")
    X = design(est); y = est.y.values; L0 = len(y) * np.log(0.5)
    rows = []; cols = []; prev = None
    for name, add, note in STEPS:
        cols = cols + [c for c in add if X[c].std() > 0 or c == "const"]
        m = fit(X, y, cols)
        r = dict(model=name, note=note, K=len(cols), N=len(y), LL=m.llf, rho2_0=1 - m.llf / L0, AIC=2 * len(cols) - 2 * m.llf, BIC=np.log(len(y)) * len(cols) - 2 * m.llf)
        if prev is not None: st = 2 * (m.llf - prev.llf); df = len(cols) - len(prev.params); r.update(LR=st, LR_df=df, LR_p=float(chi2.sf(st, df)))
        rows.append(r); prev = m
    full = prev; elim = []
    while True:
        t = full.tvalues; cand = t[[c for c in t.index if c not in KEEP]].abs()
        cand = cand[cand < 1.96]
        if len(cand) == 0: break
        drop = cand.idxmin(); cols = [c for c in cols if c != drop]; m = fit(X, y, cols)
        elim.append(dict(dropped=drop, t=float(full.tvalues[drop]), LL_before=full.llf, LL_after=m.llf)); full = m
    st = 2 * (prev.llf - full.llf); df = len(prev.params) - len(full.params)
    Lc = sm.Logit(y, X[["const"]]).fit(disp=0).llf
    rows.append(dict(model="F", note="final (backward elimination)", K=len(cols), N=len(y), LL=full.llf, rho2_0=1 - full.llf / L0, rho2_c=1 - full.llf / Lc,
                     AIC=2 * len(cols) - 2 * full.llf, BIC=np.log(len(y)) * len(cols) - 2 * full.llf, LR=-st, LR_df=-df, LR_p=float(chi2.sf(st, df)) if df > 0 else np.nan))
    pd.DataFrame(rows).to_csv(f"{T.RES}/rh_search.csv", index=False); pd.DataFrame(elim).to_csv(f"{T.RES}/rh_elimination.csv", index=False)
    tab = pd.DataFrame({"variable": full.params.index, "value": full.params.values, "rob_se": full.bse.values, "rob_t": full.tvalues.values, "p": full.pvalues.values})
    tab.to_csv(f"{T.RES}/rh_estimates.csv", index=False)
    tab[["variable", "value"]].to_csv(f"{T.RES}/tasha_return_home_gap.csv", index=False)   # specification A (with the gap): not the model of record
    # held-out: predictive LL and predicted vs observed return shares by person type x out-of-home episodes, slack band
    Xv = design(val); pv = full.predict(Xv[cols]); pe = full.predict(X[cols])
    ho = []
    for half, d, pr, info in [("estimation", est, pe, ie), ("validation", val, pv, iv)]:
        d = d.assign(p=np.asarray(pr)); yy = d.y.values; pp = np.clip(d.p.values, 1e-12, 1 - 1e-12)
        ll = float((yy * np.log(pp) + (1 - yy) * np.log(1 - pp)).sum())
        base = float(np.average(est.y)); llb = float((yy * np.log(base) + (1 - yy) * np.log(1 - base)).sum())
        ho.append(dict(group="all", level="all", half=half, N=len(d), obs=np.average(d.y, weights=d.w), pred=np.average(d.p, weights=d.w), LL_per_obs=ll / len(d), LL_const_per_obs=llb / len(d)))
        d["ptype"] = d.seg.map(PTYPE); d["nepc"] = np.where(d.nep >= 5, "5+", d.nep.astype(str)); d["slb"] = pd.cut(d.slack, [5, 30, 60, 120, 240, 1e9], right=False).astype(str)
        for g in ["ptype", "nepc", "slb"]:
            for lev, x in d.groupby(g):
                ho.append(dict(group=g, level=lev, half=half, N=len(x), obs=np.average(x.y, weights=x.w), pred=np.average(x.p, weights=x.w)))
    pd.DataFrame(ho).to_csv(f"{T.RES}/rh_heldout.csv", index=False)
    pd.DataFrame([ie, iv]).to_csv(f"{T.RES}/rh_sample.csv", index=False)
    print(pd.DataFrame(rows).round(3).to_string()); print(tab.round(3).to_string()); print(pd.DataFrame(ho).round(3).to_string())


# ------------------------------------------------------------------------------------------------ check against runs
def model_pairs(run_dir, name, pop):
    """Pairs of consecutive out-of-home activities in the Monday legs of a run with the flag of a home activity between them."""
    l = pd.read_csv(f"{run_dir}/output/legs_{name}.csv", usecols=["person_id", "start_time_min", "next_purpose", "end_time"], engine="pyarrow")
    l = l[(l.start_time_min >= 0) & (l.start_time_min < 1440) & l.person_id.isin(pop.index)].sort_values(["person_id", "start_time_min"], kind="stable")
    l["home"] = l.next_purpose.astype(str).eq("HOME"); o = l[~l.home].copy(); o["k"] = np.arange(len(o)); o["pos"] = np.arange(len(l))[~l.home.values]
    o["nep"] = o.groupby("person_id").k.transform("size")
    same = np.r_[o.person_id.values[1:] == o.person_id.values[:-1], False]
    a = o[same]; b_pos = np.r_[o.pos.values[1:], -1][same]
    return pd.DataFrame({"person_id": a.person_id.values, "nep": a.nep.values, "y": (b_pos - a.pos.values > 1).astype(int)})


def frequency_table(runs):
    """Share of consecutive out-of-home pairs with a return home and returns home per person, by person type x out-of-home
    episodes: survey halves (persons 5+) and the given survey-population runs (name -> (dir, half))."""
    rows = []
    for half in ["estimation", "validation"]:
        p = pairs(half); p = p[p.seg.map(PTYPE).ne("toddler")]
        p["ptype"] = p.seg.map(PTYPE); p["nepc"] = np.where(p.nep >= 5, "5+", p.nep.astype(str))
        for (pt, nc), x in p.groupby(["ptype", "nepc"]): rows.append(dict(source=f"survey {half}", ptype=pt, nep=nc, pairs=len(x), share=np.average(x.y, weights=x.w)))
        for pt, x in p.groupby("ptype"): rows.append(dict(source=f"survey {half}", ptype=pt, nep="all", pairs=len(x), share=np.average(x.y, weights=x.w)))
        rows.append(dict(source=f"survey {half}", ptype="all", nep="all", pairs=len(p), share=np.average(p.y, weights=p.w)))
    for label, (d, name, half) in runs.items():
        pm = pd.read_csv(f"{C.A3}/survey_pop/{half}/persons_map.csv").set_index("id"); pm = pm[pm.age >= 5]
        q = model_pairs(d, name, pm); q["w"] = q.person_id.map(pm.w)
        occ, age = q.person_id.map(pm.occ), q.person_id.map(pm.age)
        q["ptype"] = np.select([occ == 1, (occ == 3) & (age < 18), occ == 3, occ == 4], ["worker", "student 5-17", "student 18+", "retiree"], "non-worker")
        q["nepc"] = np.where(q.nep >= 5, "5+", q.nep.astype(str))
        for (pt, nc), x in q.groupby(["ptype", "nepc"]): rows.append(dict(source=label, ptype=pt, nep=nc, pairs=len(x), share=np.average(x.y, weights=x.w)))
        for pt, x in q.groupby("ptype"): rows.append(dict(source=label, ptype=pt, nep="all", pairs=len(x), share=np.average(x.y, weights=x.w)))
        rows.append(dict(source=label, ptype="all", nep="all", pairs=len(q), share=np.average(q.y, weights=q.w)))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    if sys.argv[1] == "estimate": estimate()
    elif sys.argv[1] == "check":
        runs = {}
        for r in sys.argv[2:]:
            label, name = r.split("=") if "=" in r else (r, r)
            half = "estimation" if "_est_" in name else "validation"
            runs[label] = (f"{C.A3}/run_survey/{name}", name, half)
        t = frequency_table(runs); t.to_csv(f"{T.RES}/rh_frequency_check.csv", index=False)
        print(t.pivot_table(index=["ptype", "nep"], columns="source", values="share").round(3).to_string())


# ------------------------------------------------------------------------------------------------ specification without the gap
NOGAP = ["const", "detour_km", "lndetour", "dhome_km", "a_work", "a_school", "a_acc", "a_shop", "a_joint", "e_work", "e_school", "e_acc", "e_shop", "e_joint",
         "worker", "stud_k12", "stud_ps", "retiree", "toddler", "nep3", "nep4", "nep5", "am", "pm", "ev"]
NOGAP_J = NOGAP + ["jj", "jmand"]   # 2026-11-03: joint-episode interactions


def estimate_nogap():
    """The same decision without the slack terms, on every pair (no slack restriction): the observed gap between two episodes
    is partly an outcome of the decision (a chained pair has a short gap because it is chained), so this specification uses
    only what is known before the episodes are linked.  -> results/rh_nogap_*.csv, tasha_return_home_nogap.csv"""
    out = {}
    for half in ["estimation", "validation"]:
        p = pairs(half); out[half] = p[~p.workwork].copy()
    est, val = out["estimation"], out["validation"]
    X = design(est); y = est.y.values; cols = [c for c in (NOGAP_J if JOINT_TERMS else NOGAP) if c == "const" or X[c].std() > 0]
    m = fit(X, y, cols); elim = []
    while True:
        t = m.tvalues.drop("const").abs(); t = t[t < 1.96]
        if len(t) == 0: break
        d = t.idxmin(); cols = [c for c in cols if c != d]; m2 = fit(X, y, cols); elim.append(dict(dropped=d, t=float(m.tvalues[d]), LL_before=m.llf, LL_after=m2.llf)); m = m2
    Lc = sm.Logit(y, X[["const"]]).fit(disp=0).llf
    tab = pd.DataFrame({"variable": m.params.index, "value": m.params.values, "rob_se": m.bse.values, "rob_t": m.tvalues.values, "p": m.pvalues.values})
    tab.to_csv(f"{T.RES}/rh_nogap_estimates.csv", index=False); tab[["variable", "value"]].to_csv(f"{T.RES}/tasha_return_home.csv", index=False)   # specification B: the model of record
    pd.DataFrame(elim).to_csv(f"{T.RES}/rh_nogap_elimination.csv", index=False)
    ho = []
    for half, d in [("estimation", est), ("validation", val)]:
        pr = m.predict(design(d)[cols]); d = d.assign(p=np.asarray(pr)); pp = np.clip(d.p.values, 1e-12, 1 - 1e-12); yy = d.y.values
        ho.append(dict(group="all", level="all", half=half, N=len(d), obs=np.average(d.y, weights=d.w), pred=np.average(d.p, weights=d.w),
                       LL_per_obs=float((yy * np.log(pp) + (1 - yy) * np.log(1 - pp)).mean())))
        d["ptype"] = d.seg.map(PTYPE); d["nepc"] = np.where(d.nep >= 5, "5+", d.nep.astype(str))
        for g in ["ptype", "nepc"]:
            for lev, x in d.groupby(g): ho.append(dict(group=g, level=lev, half=half, N=len(x), obs=np.average(x.y, weights=x.w), pred=np.average(x.p, weights=x.w)))
    pd.DataFrame(ho).to_csv(f"{T.RES}/rh_nogap_heldout.csv", index=False)
    print(f"N {len(y)} LL {m.llf:.1f} LL(const) {Lc:.1f} rho2_c {1 - m.llf / Lc:.3f}"); print(tab.round(3).to_string()); print(pd.DataFrame(ho).round(3).to_string())


JOINT_TERMS = False
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("nogap", "nogap_joint"):
    JOINT_TERMS = sys.argv[1] == "nogap_joint"; estimate_nogap()
