#!/usr/bin/env python3
"""Collinearity of the group-level mode models of the joint household tours (2026-11-10, tour_mode_choice/m11_joint_group.py:
shopping_joint MNL, other_joint NL auto + transit; final rows of m11_joint_coef.csv, LL of m11_joint_fit.csv).
Same method as c_abit_mode.py (imported: Model.fit / design, labels, pair classification, centring), on the estimation-half
groups of m11_joint_group.groups (one row per joint group, the representative's tour), unweighted as in the estimation; the
modes no estimation group chose are unavailable, as in m11.
(a) Variables: utility column of every free coefficient demeaned within the group over the available modes, alternative constants
    partialled out; VIF over those columns.  (b) Estimates: robust covariance of the Biogeme re-fit of the final specification
    (LL checked against m11_joint_fit.csv to 0.1).  (d) Pairs classified as in c_abit_mode.classify; centring of the constant
    pairs.  (e) Refits without each member of a substantive pair.  No cars / licence checks (only constants and level of
    service on the rare modes; licence only on car passenger in other_joint).
    ~/.venvs/biogeme/bin/python estimation/development/collinearity/c_abit_mode_joint.py [shopping other]  ->  mj_<seg>_var_corr.png, mj_<seg>_est_corr.png, ..."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"   # results of this step (data); CODE = this folder
sys.path.insert(0, CODE)
import c_abit_mode as CM   # noqa: E402
CA, CC, MC, G = CM.CA, CM.CC, CM.MC, CM.G
import m11_joint_group as J   # noqa: E402

TITLE = {"shopping": "Tour mode choice, joint shopping tours (group model)", "other": "Tour mode choice, joint other tours (group model, nested logit)"}


class JModel(CM.Model):
    def __init__(self, seg):
        self.seg = f"{seg}_joint"; df = J.groups("estimation", seg).reset_index(drop=True); df["one"] = 1.0
        self.alts = [a for a in CM.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        for a in CM.ALTS:
            if a not in self.alts: df[f"av_{a}"] = 0.0
        C = pd.read_csv(f"{MC}/m11_joint_coef.csv"); C = C[(C.segment == self.seg) & (C.step == "final")]
        F = pd.read_csv(f"{MC}/m11_joint_fit.csv"); fin = F[(F.segment == self.seg) & (F.step == "final")].iloc[-1]
        self.params, self.b0, self.LLrep = list(C.param), dict(zip(C.param, C.coef)), float(fin.LL)
        self.nests = J.spec_of(seg)[1]
        self.df = df; self.w = np.ones(len(df)); self.N = len(df)
        self.av = np.stack([df[f"av_{a}"].values > 0 for a in self.alts], 1)


def one(seg):
    model = f"mj_{seg}"; M = JModel(seg); df, w, av = M.df, M.w, M.av
    base = M.fit(tag="final"); print(seg, "N", M.N, "alts", M.alts, "LL", base["LL"], "reported", M.LLrep, flush=True)
    assert abs(base["LL"] - M.LLrep) < 0.1 and sorted(base["names"]) == sorted(M.params)
    order = list(M.params); ix = [base["names"].index(p) for p in order]
    base.update(names=order, b=base["b"][ix], se=base["se"][ix], cov=base["cov"][np.ix_(ix, ix)])
    se_rep = pd.read_csv(f"{MC}/m11_joint_coef.csv"); se_rep = se_rep[(se_rep.segment == M.seg) & (se_rep.step == "final")].set_index("param")
    t_dev = float(np.nanmax(np.abs(base["b"] / base["se"] / se_rep.loc[order, "t"].values - 1)))
    at_bound = [p for p, b in zip(order, base["b"]) if p.startswith("mu_") and b <= 1.0 + 1e-6]
    vn = [p for p in order if not p.startswith(("ASC_", "mu_"))]; asc = [p for p in order if p.startswith("ASC_")]
    R, _ = CA.within_corr_partial(M.design(vn), av, w, M.design(asc)); vf = CC.vif(R)
    vf = np.where((vf < 0) | (vf > 1e8), np.inf, vf)
    labels = {p: CM.lab(p) for p in order}
    CC.heatmap(R, [labels[v] for v in vn], f"{HERE}/{model}_var_corr.png",
               f"{TITLE[seg]}, final model: correlations of the explanatory variables\nwithin group (demeaned over the available modes, constants partialled out), estimation half",
               "Correlation (within group, net of the constants)")
    Re = CC.est_corr(base["cov"])
    CC.heatmap(Re, [labels[n] for n in order], f"{HERE}/{model}_est_corr.png",
               f"{TITLE[seg]}, final model: correlations of the estimates (robust covariance)\nestimation half, LL {base['LL']:,.1f}, {base['K']} parameters, {M.N} groups",
               "Correlation of the estimates")
    pd.DataFrame(R, index=vn, columns=vn).round(3).to_csv(f"{HERE}/{model}_var_corr.csv")
    pd.DataFrame(Re, index=order, columns=order).round(3).to_csv(f"{HERE}/{model}_est_corr.csv")
    T = np.eye(len(order)); bi = {n: i for i, n in enumerate(order)}
    for p in order:
        v, a = CM.split(p)
        if a is None or v == "ASC": continue
        for m_ in (("BUS", "TRAIN") if a == "PT" else (a,)):
            c = CM.columns(p, M.alts)[m_]; ok = df[f"av_{m_}"].values > 0; mu = float(np.sum(w[ok] * df[c].values[ok]) / np.sum(w[ok]))
            if f"ASC_{m_}" in bi: T[bi[f"ASC_{m_}"], bi[p]] += mu
    Rc = CC.est_corr(T @ base["cov"] @ T.T)
    vi = {n: i for i, n in enumerate(vn)}; rows = []
    for a, b, r in CC.pairs(R, vn, CC.R_VAR):
        t, why, _ = CM.classify(a, b, M.nests)
        rows.append(dict(model=model, pair=f"{labels[a]} / {labels[b]}", p1=a, p2=b, source="variables", type=t, why=why, var_r=r, est_r=Re[bi[a], bi[b]],
                         est_r_centred=Rc[bi[a], bi[b]]))
    for v, x in zip(vn, vf):
        if x >= CC.VIF_MAX: rows.append(dict(model=model, pair=labels[v], p1=v, source="VIF", VIF=x))
    for a, b, r in CC.pairs(Re, order, CC.R_EST):
        t, why, cen = CM.classify(a, b, M.nests)
        rows.append(dict(model=model, pair=f"{labels[a]} / {labels[b]}", p1=a, p2=b, source="estimates", type=t, why=why, est_r=r,
                         var_r=R[vi[a], vi[b]] if a in vi and b in vi else np.nan, est_r_centred=Rc[bi[a], bi[b]] if cen else np.nan))
    Pp = pd.DataFrame(rows)
    for c in ["est_r_centred", "why", "type", "var_r", "p2", "p1", "source"]:
        if c not in Pp: Pp[c] = np.nan
    if len(Pp):
        Pp["centring_removes"] = np.where(Pp.why.astype(str).str.startswith("constant"), Pp.est_r_centred.abs() < CC.R_EST, np.nan)
        Pp["VIF_p1"] = [vf[vi[x]] if x in vi else np.nan for x in Pp.p1]; Pp["VIF_p2"] = [vf[vi[x]] if isinstance(x, str) and x in vi else np.nan for x in Pp.p2]
        print(Pp.drop(columns=["pair"]).round(3).to_string(), flush=True)
    else: print("no flags", flush=True)
    ref, cache, done = [], {}, set()
    for _, q in Pp[(Pp.source != "VIF") & (Pp.type == "SUBSTANTIVE")].iterrows():
        if frozenset((q.p1, q.p2)) in done: continue
        done.add(frozenset((q.p1, q.p2)))
        for d, f in ((q.p1, q.p2), (q.p2, q.p1)):
            if d.startswith("mu_") or d in at_bound: continue
            if d not in cache: cache[d] = M.fit(drop=[d], tag=f"r{len(cache)}")
            rr = CC.refit_row(base, cache[d], f, f"without {d}"); rr.update(model=model, pair=q.pair); ref.append(rr)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rr.items()}, flush=True)
    sh = df.choice.value_counts().to_dict()
    CA.save_part(model, Pp.to_dict("records") + ref,
                 dict(LL=base["LL"], LL_reported=M.LLrep, K=base["K"], N=M.N, alternatives=M.alts, chosen=sh, nest_parameters_at_bound=at_bound,
                      max_rel_dev_t_vs_reported=t_dev, max_vif=float(np.nanmax(vf)), vif=dict(zip(vn, np.round(vf, 2)))))


if __name__ == "__main__":
    WD = os.environ.get("BIO_WD", "/private/tmp/claude-501/c_abit_mode_bio"); os.makedirs(WD, exist_ok=True)
    import shutil; shutil.copy(f"{MC}/bio/biogeme.toml", WD); os.chdir(WD)
    for s in sys.argv[1:] or ["shopping", "other"]: one(s)
