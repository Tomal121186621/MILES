#!/usr/bin/env python3
"""Biogeme estimation of the tour mode choice on the estimation half of the RTS (work/bio_<segment>.parquet, written by
`python3 prep_tours.py biodata` in the main environment).

    ~/.venvs/biogeme/bin/python activity/lib/mode_choice/estimate_mc.py [work,school,shopping,other] [--force]

Per segment:
  1. constants only (MNL with the availability conditions): LL(c)
  2. MNL with the full specification (SPEC), then backward elimination of the socio-demographic and land-use terms with
     |robust t| < 1.96 (one at a time, smallest |t| first); level-of-service, cost, lambda and constants are kept
  3. nested logit with the final MNL specification: nests auto (CD, CP), transit (TW, TD), non-motorised (WK, BK); Biogeme's
     nest parameter mu_m >= 1 (scale of the nest relative to the root; 1 / mu_m is the logsum coefficient in (0, 1])
  4. income-group variant of the chosen structure: cost x low (< $50k), mid, high (>= $100k) income instead of cost / income^lambda
Utility (reference: car driver):
  V_CD = b_tcar car_min + b_cost c_CD / r^lambda + b_park park
  V_CP = ASC_CP + b_tcar car_min + socio
  V_TW = ASC_TW + b_ivt ivt + b_wait wait + b_walk walk + b_trf trf + b_cost fare / r^lambda + socio
  V_TD = ASC_TD + b_ivt ivt + b_wait wait + b_drive drive + b_walk walk + b_trf trf + b_cost (fare + drive cost) / r^lambda
  V_WK = ASC_WK + b_kmwalk km + socio;   V_BK = ASC_BK + b_kmbike km + socio
  r = household income / $84,216 (floor $5,000).  Value of time b_t / b_cost x r^lambda x 60 ($/h).
Weights: none (the RTS samples households exogenously; maximum likelihood without the survey weights); robust (sandwich)
standard errors.  Outputs in results/: mc_<seg>_<model>.html / .yaml (Biogeme), mc_<seg>_<model>.csv (parameters),
mc_<seg>_<model>_cov.csv (robust covariance), mc_summary.csv (fit statistics of every model).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, os, sys
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/mode_choice"; WORK = f"{HERE}/work"; RES = f"{HERE}/results"; BIO = f"{WORK}/biogeme"
ALTS = ["CD", "CP", "TW", "TD", "WK", "BK"]; NUM = {a: i + 1 for i, a in enumerate(ALTS)}
# socio-demographic and land-use terms (variable, alternative) of the full specification, by segment
SOCIO_ALL = [("zero_car", "CP"), ("car_def", "CP"), ("child", "CP"), ("teen", "CP"), ("senior", "CP"), ("hhsize", "CP"), ("male", "CP"), ("stops", "CP"),
             ("zero_car", "TW"), ("car_def", "TW"), ("lnden_h", "TW"), ("lnden_m", "TW"), ("cbd_m", "TW"), ("stops", "TW"), ("senior", "TW"), ("child", "TW"),
             ("car_def", "TD"), ("lnden_m", "TD"),
             ("zero_car", "WK"), ("car_def", "WK"), ("lnden_h", "WK"), ("lnden_m", "WK"), ("stops", "WK"), ("child", "WK"), ("senior", "WK"),
             ("male", "BK"), ("zero_car", "BK"), ("lnden_m", "BK"), ("child", "BK"),
             ("lnkm", "CP"), ("lnkm", "TW"), ("lnkm", "TD")]
SPEC = {"work": SOCIO_ALL, "school": SOCIO_ALL, "shopping": SOCIO_ALL,
        "other": SOCIO_ALL + [("rec", "CP"), ("esc", "CP"), ("rec", "WK"), ("esc", "WK"), ("rec", "BK"), ("rec", "TW"), ("esc", "TW")]}
NESTS = {"auto": ["CD", "CP"], "transit": ["TW", "TD"], "nonmot": ["WK", "BK"]}
LOS = {"b_tprior", "prior_TW", "prior_TD", "b_tcar", "b_ivt", "b_wait", "b_walk", "b_trf", "b_drive", "b_cost", "lambda", "b_park", "b_kmwalk", "b_kmbike", "b_cost_lo", "b_cost_mid", "b_cost_hi"}


def model(seg, df, terms, nested=False, asc_only=False, incgroup=False, name="m"):
    import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
    from biogeme.expressions import Beta, Variable
    from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit
    av_alts = [a for a in ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
    d = db.Database(f"{seg}_{name}", df.select_dtypes(include=[np.number, bool]).astype(float)); X = lambda k: Variable(k)
    asc = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in ALTS}
    V = {a: asc[a] for a in ALTS}
    if not asc_only:
        bt, bivt, bw, bwalk, btrf, bdr = (Beta(n, 0, None, None, 0) for n in ["b_tcar", "b_ivt", "b_wait", "b_walk", "b_trf", "b_drive"])
        if incgroup:
            bl, bm, bh = Beta("b_cost_lo", -0.1, None, None, 0), Beta("b_cost_mid", -0.1, None, None, 0), Beta("b_cost_hi", -0.1, None, None, 0)
            cf = lambda c: (bl * X("inc_lo") + bh * X("inc_hi") + bm * (1 - X("inc_lo") - X("inc_hi"))) * X(c)
        else:
            bc, lam = Beta("b_cost", -0.1, None, None, 0), Beta("lambda", 0.5, -1.0, 3.0, 0)
            cf = lambda c: bc * X(c) / (X("inc_r") ** lam)
        V["CD"] = V["CD"] + bt * X("car_min") + cf("cost_cd") + Beta("b_park", 0, None, None, 0) * X("park")
        V["CP"] = V["CP"] + bt * X("car_min")
        V["TW"] = V["TW"] + bivt * X("tw_ivt") + bw * X("tw_wait") + bwalk * X("tw_walk") + btrf * X("tw_trf") + cf("tw_cost")
        V["TD"] = V["TD"] + bivt * X("td_ivt") + bw * X("td_wait") + bdr * X("td_drive") + bwalk * X("td_walk") + btrf * X("td_trf") + cf("td_cost")
        bp, dp = Beta("b_tprior", 0, None, None, 0), Beta("prior_TW", 0, None, None, 0)
        V["TW"] = V["TW"] + bp * X("pr_time") + dp * X("prior")
        V["TD"] = V["TD"] + bp * X("pr_time") + Beta("prior_TD", 0, None, None, 0) * X("prior")
        V["WK"] = V["WK"] + Beta("b_kmwalk", -1, None, None, 0) * X("km")
        V["BK"] = V["BK"] + Beta("b_kmbike", -0.2, None, None, 0) * X("km")
        for var, a in terms:
            if a in av_alts: V[a] = V[a] + Beta(f"{var}_{a}", 0, None, None, 0) * X(var)
    U = {NUM[a]: V[a] for a in av_alts}; AV = {NUM[a]: X(f"av_{a}") for a in av_alts}
    if nested:
        ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.5, 1.0, 10.0, 0), [NUM[a] for a in v if a in av_alts], name=k) for k, v in NESTS.items() if sum(a in av_alts for a in v) >= 2]
        single = [NUM[a] for k, v in NESTS.items() if sum(x in av_alts for x in v) < 2 for a in v if a in av_alts]
        for s in single: ns.append(OneNestForNestedLogit(1.0, [s], name=f"single_{s}"))
        ll = models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    else:
        ll = models.loglogit(U, AV, X("y"))
    os.makedirs(BIO, exist_ok=True); cwd = os.getcwd(); os.chdir(BIO)
    try:
        m = bio.BIOGEME(d, {"log_like": ll, "weight": X("wn")}, save_iterations=False, generate_html=True, generate_yaml=True)
        m.model_name = f"mc_{seg}_{name}"
        r = m.estimate()
    finally:
        os.chdir(cwd)
    return r, av_alts


def table(r):
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))
    return t.set_index("Name")


def ll0(df, alts):
    nav = df[[f"av_{a}" for a in alts]].sum(1).clip(lower=1)
    return float(-(df.wn * np.log(nav)).sum())


def save(seg, name, r, df, alts, llc, extra=None):
    t = table(r); t.to_csv(f"{RES}/mc_{seg}_{name}.csv")
    names = list(t.index); cov = np.asarray(r.robust_variance_covariance_matrix)
    pd.DataFrame(cov, index=names, columns=names).to_csv(f"{RES}/mc_{seg}_{name}_cov.csv")
    for ext in ["html", "yaml"]:
        src = f"{BIO}/mc_{seg}_{name}.{ext}"
        if os.path.exists(src): os.replace(src, f"{RES}/mc_{seg}_{name}.{ext}")
    L0 = ll0(df, alts); LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
    st = dict(segment=seg, model=name, N=N, K=K, LL0=L0, LLc=llc, LL=LL, rho2_0=1 - LL / L0, rho2bar_0=1 - (LL - K) / L0,
              rho2_c=(1 - LL / llc) if llc else np.nan, AIC=2 * K - 2 * LL, BIC=K * np.log(N) - 2 * LL, converged=bool(r.algorithm_has_converged),
              gradient_norm=float(r.gradient_norm), sum_w=float(df.wn.sum()))
    if extra: st.update(extra)
    return st, t


def eliminate(seg, df, terms):
    """backward elimination of the socio-demographic / land-use terms (MNL)"""
    terms = list(terms); log = []
    while True:
        r, alts = model(seg, df, terms, name="search")
        t = table(r); tt = t["Robust t-stat."] if "Robust t-stat." in t else t.iloc[:, 3]
        cand = [(abs(tt[f"{v}_{a}"]), (v, a)) for v, a in terms if f"{v}_{a}" in tt.index]
        drop = [(x, k) for x, k in cand if not np.isfinite(x) or x < 1.96]
        missing = [k for k in terms if f"{k[0]}_{k[1]}" not in tt.index]
        terms = [k for k in terms if k not in missing]
        if not drop: return terms, log
        x, k = min(drop, key=lambda z: z[0] if np.isfinite(z[0]) else -1); terms.remove(k); log.append(dict(segment=seg, dropped=f"{k[0]}_{k[1]}", abs_t=x, LL=float(r.final_loglikelihood)))
        print(f"  {seg}: drop {k[0]}_{k[1]} (|t| {x:.2f})", flush=True)


def run(seg, force=False):
    df = pd.read_parquet(f"{WORK}/bio_{seg}.parquet")
    out = []
    # terms identified in the segment: the variable varies among the tours where the alternative is available and chosen
    spec = [(v, a) for v, a in SPEC[seg] if df.loc[(df[f"av_{a}"] > 0) & (df.choice == a), v].std() > 0 and df.loc[df[f"av_{a}"] > 0, v].std() > 0]
    rc, alts = model(seg, df, [], asc_only=True, name="constants"); llc = float(rc.final_loglikelihood)
    s, _ = save(seg, "constants", rc, df, alts, llc); out.append(s)
    fs = f"{RES}/mc_{seg}_terms.json"
    if os.path.exists(fs) and not force: terms = [tuple(x) for x in json.load(open(fs))]; elog = []
    else:
        terms, elog = eliminate(seg, df, spec); json.dump(terms, open(fs, "w")); pd.DataFrame(elog).to_csv(f"{RES}/mc_{seg}_elimination.csv", index=False)
    for name, kw in [("mnl", {}), ("nl", {"nested": True})]:
        r, alts = model(seg, df, terms, name=name, **kw); s, _ = save(seg, name, r, df, alts, llc); out.append(s)
        print(f"{seg} {name}: LL {s['LL']:.1f}, rho2_c {s['rho2_c']:.3f}, K {s['K']}", flush=True)
    for name, kw in [("mnl_incgroup", {"incgroup": True}), ("nl_incgroup", {"nested": True, "incgroup": True})]:
        r, alts = model(seg, df, terms, name=name, **kw); s, _ = save(seg, name, r, df, alts, llc); out.append(s)
    return out


def pooled():
    """pooled model (every coefficient common to the four segments, the union of their final terms) for the LR test of the
    segmentation: LR = 2 (sum_s LL_s - LL_pooled), df = sum_s K_s - K_pooled; MNL and NL"""
    segs = ["work", "school", "shopping", "other"]
    df = pd.concat([pd.read_parquet(f"{WORK}/bio_{s}.parquet") for s in segs], ignore_index=True)
    for c in ["rec", "esc"]: df[c] = df[c].fillna(0.0)
    terms = sorted({tuple(x) for s in segs for x in json.load(open(f"{RES}/mc_{s}_terms.json"))})
    summ = pd.read_csv(f"{RES}/mc_summary.csv"); rows = []
    rc, alts = model("pooled", df, [], asc_only=True, name="constants"); llc = float(rc.final_loglikelihood)
    for name, kw in [("mnl", {}), ("nl", {"nested": True})]:
        r, alts = model("pooled", df, terms, name=name, **kw); st, _ = save("pooled", name, r, df, alts, llc)
        seg = summ[summ.model.eq(name) & summ.segment.isin(segs)]
        lr = 2 * (seg.LL.sum() - st["LL"]); dof = int(seg.K.sum() - st["K"])
        from scipy.stats import chi2
        st.update(dict(LR_segmented_vs_pooled=lr, df_LR=dof, p_LR=float(chi2.sf(lr, dof)))); rows.append(st)
        print(f"pooled {name}: LL {st['LL']:.1f} K {st['K']}; segmented LL {seg.LL.sum():.1f} K {int(seg.K.sum())}; LR {lr:.1f} df {dof} p {chi2.sf(lr, dof):.3g}", flush=True)
    pd.DataFrame(rows).to_csv(f"{RES}/mc_pooled_test.csv", index=False)


if __name__ == "__main__":
    if sys.argv[-1] == "pooled": pooled(); sys.exit()
    segs = sys.argv[1].split(",") if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ["work", "school", "shopping", "other"]
    rows = []
    for s in segs: rows += run(s, "--force" in sys.argv)
    f = f"{RES}/mc_summary.csv"; old = pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()
    new = pd.DataFrame(rows)
    if len(old): old = old[~old.segment.isin(segs)]
    pd.concat([old, new]).to_csv(f, index=False); print(new.to_string())
