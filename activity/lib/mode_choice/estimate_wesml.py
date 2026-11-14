#!/usr/bin/env python3
"""Work tour mode choice re-estimated with choice-based sample weights (WESML, Manski & Lerman 1977), estimation half only.

    python3 wesml_targets.py                          -> the weights (work/wesml_est.parquet, wesml_hold.parquet)
    ~/.venvs/biogeme/bin/python activity/lib/mode_choice/estimate_wesml.py     -> results/gc_work_wesml.csv / _cov.csv / .html, results/wesml_fit.csv,
                                                         results/wesml_coef_change.csv, results/wesml_shares.csv
    ~/.venvs/biogeme/bin/python activity/lib/mode_choice/estimate_wesml.py export   -> results/gc_work_hh.csv = the WESML estimates (earlier file kept as
                                                         results/gc_work_hh_pre_rail.csv), read by export_mc.py

Why.  The survey's work tours over-represent rail commuters against the ACS of the same period (Montgomery 22 % of the estimation
half's work tours against 10 % of the ACS 2017-19 commuters, Prince George's 21 against 10 %, the District 34 against 24 %), and the
model reproduces the survey.  Sampling on the outcome (the chosen mode) makes the unweighted estimator inconsistent; WESML weights
each tour by Q(i|g) / H(i|g), the ACS population share of its mode in its home stratum over the sample share (wesml_targets.py).
Specification: the model of record of the work segment (estimate_gc.CHOSEN 'nl_dest_gen' + the fewer-cars-than-drivers term of
estimate_hh.py), unchanged: same variables, same nests, USDOT value of time (50 % of the household wage rate), no new constants.
Standard errors: the WESML sandwich H^-1 (sum_n w_n^2 g_n g_n') H^-1 (sandwich()), with H the Hessian of the weighted log-likelihood
(Biogeme's Rao-Cramer matrix) and g_n the observation scores (central differences of mc_apply's probabilities).  Biogeme's own 'robust'
matrix uses sum_n w_n g_n g_n' (checked: it scales with 1/sqrt(c) when the weights are multiplied by c, and the sandwich() matrix with
that B reproduces it to 4 digits), which is not the WESML covariance; it is kept in the column 'Biogeme robust std err.'.  The
correction for the sampling error of Q is not applied (Q comes from 143,507 ACS records, at least 1,929 per stratum).
Fit: log-likelihood, unweighted and WESML-weighted, on both halves (the hold-out half has its own weights to the same ACS shares),
and the weighted predicted mode shares against the ACS shares by stratum.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/mode_choice"   # data folder; CODE = this folder
import estimate_gc as G   # noqa: E402
import estimate_hh as HH  # noqa: E402
import mc_apply as A      # noqa: E402

RES = G.RES; BASE = G.CHOSEN["work"]; EXTRA = ["short"]
MODES = ["CD", "CP", "BUS", "TRAIN", "WK", "BK"]


def data(half):
    f = HH.prep(pd.read_parquet(f"{G.WORK}/{'gc_bio' if half == 'est' else 'gc_hold'}_work_s50.parquet"))
    w = pd.read_parquet(f"{G.WORK}/wesml_{half}.parquet")
    assert len(w) == len(f) and (w.person_id.values == f.person_id.values).all() and (w.choice.values == f.choice.values).all()
    return f.assign(wesml=w.wesml.values, stratum=w.stratum.values)


def estimate(df, name, weight):
    old = list(G.SOCIO)
    try:
        G.SOCIO[:] = old + EXTRA
        r, alts = G.model("work", df, nested=True, dest=True, generic=True, name=name, weight=weight)
    finally:
        G.SOCIO[:] = old
    t = G.table(r); cov = pd.DataFrame(np.asarray(r.robust_variance_covariance_matrix), index=t.index, columns=t.index)
    rc = pd.DataFrame(np.asarray(r.rao_cramer_variance_covariance_matrix), index=t.index, columns=t.index)
    t.to_csv(f"{RES}/gc_work_{name}.csv"); cov.to_csv(f"{RES}/gc_work_{name}_cov.csv"); rc.to_csv(f"{RES}/gc_work_{name}_rc.csv")
    for ext in ["html", "yaml"]:
        src = f"{G.BIO}/gc_work_{name}.{ext}"
        if os.path.exists(src): os.replace(src, f"{RES}/gc_work_{name}.{ext}")
    print(f"{name}: LL {float(r.final_loglikelihood):.2f}, K {int(r.number_of_free_parameters)}, converged {r.algorithm_has_converged}", flush=True)
    return t, cov, float(r.final_loglikelihood)


def probs(f, b):
    old = list(A.SOCIO)
    try:
        A.SOCIO[:] = old + [s for s in EXTRA if s not in old]; V, av = A.utilities(f, b)
    finally:
        A.SOCIO[:] = old
    return A.probs(V, av, b)


def fit(f, b, label, half):
    P = probs(f, b); y = np.array([A.ALTS.index(c) for c in f.choice.values]); lp = np.log(np.clip(P[np.arange(len(f)), y], 1e-300, None))
    w = f.wesml.values; rows = [dict(model=label, half=half, measure="LL unweighted", value=lp.sum()),
                                dict(model=label, half=half, measure="LL WESML-weighted", value=(w * lp).sum()),
                                dict(model=label, half=half, measure="N", value=len(f))]
    sh = []
    for scope, m in [("all", np.ones(len(f), bool)), ("Maryland", (f.county.values // 1000) == 24)] + [(s, f.stratum.values == s) for s in sorted(set(f.stratum))]:
        for j, alt in enumerate(A.ALTS):
            sh.append(dict(model=label, half=half, scope=scope, mode=alt, n=int(m.sum()),
                           predicted_unweighted=P[m, j].mean(), observed_unweighted=(y[m] == j).mean(),
                           predicted_wesml=np.average(P[m, j], weights=w[m]), target_wesml=np.average(y[m] == j, weights=w[m])))
    return rows, sh


def sandwich(f, t, rc, weight):
    """WESML covariance H^-1 (sum_n w_n^2 g_n g_n') H^-1 (Manski & Lerman 1977) over all parameters (an estimate on its bound, mu_transit
    = 1, is included as in Biogeme's matrices).  H^-1 = -(Rao-Cramer covariance of Biogeme, i.e. the inverse Hessian of the weighted log-likelihood);
    g_n = score of observation n, central differences of log P_n (mc_apply utilities and probabilities).  Also returns the sandwich
    with sum w_n g_n g_n', which must equal Biogeme's 'robust' matrix (check of the scores)."""
    free = list(t.index); b0 = t.Value.to_dict()
    y = np.array([A.ALTS.index(c) for c in f.choice.values]); idx = np.arange(len(f))
    lp = lambda b: np.log(np.clip(probs(f, b)[idx, y], 1e-300, None))
    Gm = np.zeros((len(f), len(free)))
    for k, name in enumerate(free):
        h = 1e-5 * max(1.0, abs(b0[name])); bp, bm = dict(b0), dict(b0); bp[name] += h; bm[name] -= h
        Gm[:, k] = (lp(bp) - lp(bm)) / (2 * h)
    Hi = rc.loc[free, free].values; w = f[weight].values
    B1 = (Gm * w[:, None]).T @ Gm; B2 = (Gm * (w ** 2)[:, None]).T @ Gm
    V1 = Hi @ B1 @ Hi; V2 = Hi @ B2 @ Hi
    return pd.DataFrame(V2, index=free, columns=free), pd.DataFrame(V1, index=free, columns=free), float(np.abs(Gm.T @ w).max())


def scale_check(df):
    """robust s.e. must not depend on the scale of the weights (sandwich), the BHHH-free 'non-robust' ones must"""
    a, ca, _ = estimate(df.assign(w2=df.wesml), "wesml_chk1", "w2"); b, cb, _ = estimate(df.assign(w2=2 * df.wesml), "wesml_chk2", "w2")
    r = (b["Robust std err."] / a["Robust std err."]).describe()
    print("robust s.e. ratio (weights x2 / x1):", r[["min", "max"]].round(4).to_dict(), "coef max |diff|", float((a.Value - b.Value).abs().max()))
    for n in ["wesml_chk1", "wesml_chk2"]:
        for ext in ["csv", "_cov.csv", "html", "yaml"]:
            p = f"{RES}/gc_work_{n}{'.' if not ext.startswith('_') else ''}{ext}"
            if os.path.exists(p): os.remove(p)


def run():
    E, H = data("est"), data("hold")
    if "--check" in sys.argv: scale_check(E)
    old = pd.read_csv(f"{RES}/gc_work_hh.csv" if not os.path.exists(f"{RES}/gc_work_hh_pre_rail.csv") else f"{RES}/gc_work_hh_pre_rail.csv").set_index("Name")
    new, cov, ll = estimate(E, "wesml", "wesml")
    rc = pd.read_csv(f"{RES}/gc_work_wesml_rc.csv", index_col=0)
    V2, V1, gmax = sandwich(E, new, rc, "wesml")
    se_bio = new.loc[V1.index, "Robust std err."]; se_chk = np.sqrt(np.diag(V1.values))
    print(f"score check: max |weighted score| {gmax:.3g}; Biogeme robust s.e. / sandwich with sum w g g': "
          f"{(se_bio.values / se_chk).min():.4f} - {(se_bio.values / se_chk).max():.4f}", flush=True)
    se = pd.Series(np.sqrt(np.diag(V2.values)), index=V2.index)
    new["Biogeme robust std err."] = new["Robust std err."]
    new["Robust std err."] = se.reindex(new.index).fillna(new["Robust std err."])
    new["Robust t-stat."] = new.Value / new["Robust std err."]
    from scipy.stats import norm
    new["Robust p-value"] = 2 * norm.sf(np.abs(new["Robust t-stat."]))
    full = cov.copy(); full.loc[V2.index, V2.index] = V2.values
    new.to_csv(f"{RES}/gc_work_wesml.csv"); full.to_csv(f"{RES}/gc_work_wesml_cov.csv")
    b_old, b_new = old.Value.to_dict(), new.Value.to_dict()
    rows, sh = [], []
    for lab, b in [("unweighted (earlier)", b_old), ("WESML", b_new)]:
        for half, f in [("estimation", E), ("hold-out", H)]:
            r, s = fit(f, b, lab, half); rows += r; sh += s
    F = pd.DataFrame(rows); F.to_csv(f"{RES}/wesml_fit.csv", index=False); S = pd.DataFrame(sh); S.to_csv(f"{RES}/wesml_shares.csv", index=False)
    tcol = "Robust t-stat." if "Robust t-stat." in new else [c for c in new if "t-stat" in c][0]
    C = pd.DataFrame(dict(unweighted=old.Value, t_unweighted=old[tcol], wesml=new.Value, t_wesml=new[tcol]))
    C["change"] = C.wesml - C.unweighted; C.to_csv(f"{RES}/wesml_coef_change.csv")
    pd.set_option("display.width", 220)
    print(F.pivot_table(index=["model", "half"], columns="measure", values="value").round(1).to_string())
    print(C.round(4).to_string())
    x = S[S.scope.isin(["all", "Maryland"])].pivot_table(index=["scope", "half", "model"], columns="mode", values=["predicted_wesml", "target_wesml", "predicted_unweighted", "observed_unweighted"])
    print((100 * x).round(1).to_string())
    print("mu:", {k: round(v, 3) for k, v in b_new.items() if k.startswith("mu_")}, "gc:", round(b_new["gc"], 5))


def export():
    if not os.path.exists(f"{RES}/gc_work_hh_pre_rail.csv"):
        for s in ["", "_cov"]: os.replace(f"{RES}/gc_work_hh{s}.csv", f"{RES}/gc_work_hh{s}_pre_rail.csv")
    for s in ["", "_cov"]:
        pd.read_csv(f"{RES}/gc_work_wesml{s}.csv", index_col=0).to_csv(f"{RES}/gc_work_hh{s}.csv")
    print("results/gc_work_hh.csv = WESML estimates (earlier: gc_work_hh_pre_rail.csv)")


if __name__ == "__main__":
    export() if sys.argv[-1] == "export" else run()
