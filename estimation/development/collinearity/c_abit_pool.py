"""Collinearity check of a POOLED location model (primary_destination_pooled/pool_core.py: purposes p with U_pj = mu_p V_pj, coefficients shared
across purposes or purpose specific, parameters held at a value).  Used by c_abit_dprimary.py (dp_pooled) and c_abit_loc.py (lp_edu).
Estimation half only.  Same method as the other checks (abit_notes.md):
  (a) variables: per purpose, the free linear terms of the purpose (terms held at 0 are not in the model and are left out),
      demeaned within each choice situation over its 1,588 zones (all available); a situation is one (record, configuration) row
      of the location mixture weighted by its configuration weight (rows of a record sum to 1), records unweighted as estimated.
      ln(1 + size component) and ln S at the purpose's final weights are shown with the variables (information only).
      VIF per purpose over its free linear coefficients, and POOLED VIF over the global free linear coefficients: the
      within-situation cross products of the purposes are added, purpose p's columns multiplied by its scale mu_p, a column
      mapped to its global parameter (shared or purpose specific) - the design of the pooled model as estimated.
  (b) estimates: correlations from the robust covariance of the pooled model (V units, delta method of pool_core.ParEngine),
      over the free parameters (held parameters and estimates on a bound excluded).
  (d)-(e) flags |r| >= 0.7 (variables, per purpose), VIF >= 10 (per purpose and pooled), |r| >= 0.8 (estimates); STRUCTURAL vs
      SUBSTANTIVE; refit of the pooled model without each member of a substantive pair (its global parameter held at 0: for a
      shared parameter in every purpose that shares it), LR and BIC against the final pooled model (BIC with the pooled N)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, time, pickle
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; SB = os.path.dirname(HERE)
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, CODE); sys.path.insert(0, os.path.join(DEV, "primary_destination_pooled"))
import c_abit_common as CA   # noqa: E402
CC = CA.CC
import pool_core as PC   # noqa: E402


def is_size_par(q): return q.startswith("theta_") or q == "mu_size"
def is_size_col(q): return q == "lnS" or q.startswith("ln1p_")
def is_piece(q): return re.match(r"^dt?_\d", q) is not None
def is_dist(q): return is_piece(q) or q in ("d", "dt")
def is_lnd(q): return q in ("lnd", "lndt")
def is_lndx(q): return q.startswith("lnd_") or q.startswith("lndt_")
def par(n): return n.split("|", 1)[1] if "|" in n else n
def grp(n): return n.split("|", 1)[0] if "|" in n else None


def kind(a, b, pieces, has_main):
    """(type, why, refit?) of a flagged pair; a, b local names (variables) or global keys (estimates)"""
    if grp(a) == "scale" or grp(b) == "scale":
        return "STRUCTURAL", "purpose scale vs a coefficient (the scale is identified only through the shared coefficients)", False
    qa, qb = par(a), par(b)
    if is_size_par(qa) and is_size_par(qb): return "STRUCTURAL", "size-term parameters", False
    if is_size_col(qa) and is_size_col(qb): return "STRUCTURAL", "size-term columns (ln S and ln(1 + its components), information only)", False
    if is_size_col(qa) or is_size_col(qb): return "SIZE", "size-term column vs a variable (information; theta / mu vs land use)", False
    if (is_size_par(qa) and qb in ("lnretden", "mix")) or (is_size_par(qb) and qa in ("lnretden", "mix")):   # 2026-11-09, coordinator
        return "STRUCTURAL", "size-term parameter vs land-use density (size term / density trade-off, see the mu vs retail density check)", False
    if qa == qb: return "STRUCTURAL", "same variable in two purpose groups (linked through the purpose scales)", False
    if is_piece(qa) and is_piece(qb):
        i, j = sorted(pieces.index(v) for v in (qa, qb))
        return "STRUCTURAL", "adjacent piecewise segments of the distance" if j - i == 1 else "piecewise segments of the distance (non-adjacent)", False
    if is_lndx(qa) and is_lndx(qb):
        return ("STRUCTURAL", "two interactions of ln distance" + ("" if has_main else " (no main effect in the model: centring not applicable)"), False)
    if (is_lnd(qa) and is_lndx(qb)) or (is_lnd(qb) and is_lndx(qa)): return "STRUCTURAL", "main effect vs its own interaction", False
    if (is_dist(qa) or is_lnd(qa) or is_lndx(qa)) and (is_dist(qb) or is_lnd(qb) or is_lndx(qb)):
        return "STRUCTURAL", "functional form of one variable (distance: pieces, linear, log, ln distance interactions)", True
    return "SUBSTANTIVE", "", True


def purpose_cov(chunks, spec, theta):
    """unnormalised within-situation cross products (weights: configuration weight / J per cell, a record sums to 1) of the
    linear columns, ln(1 + component) of every size component and ln S at the purpose's weights; formula of c_silo_common.within_corr"""
    comps = [spec.size_base] + list(spec.size_comps); w = np.r_[1.0, [np.exp(theta[c]) for c in spec.size_comps]]; Cm = 0.0
    for c in chunks:
        X = c.X32.double().numpy(); Sz = c.S32.double().numpy(); n, J = X.shape[:2]
        gi, lw = c.gidx.numpy(), c.logw.numpy(); rw = np.zeros(n); ok = np.isfinite(lw); rw[gi[ok]] = np.exp(lw[ok])
        Xa = np.concatenate([X, np.log1p(np.maximum(Sz, 0.0)), np.log1p((Sz * w).sum(-1))[..., None]], -1); del X
        Z = (Xa - Xa.mean(1, keepdims=True)).reshape(n * J, -1); cw = np.repeat(rw / J, J)
        Cm = Cm + (Z * cw[:, None]).T @ Z; del Xa, Z
    return Cm, list(spec.linear) + [f"ln1p_{c}" for c in comps] + ["lnS"]


def corr(C):
    s = np.sqrt(np.diag(C)); return C / np.outer(s, s)


def as_base(res, S):
    names = [n for n in S.names() if n not in S.fixed]; t = res["table"].set_index("param")
    return dict(LL=res["LL"], K=res["K"], N=res["N"], names=names, b=t.value[names].values, se=t.rob_se[names].values,
                cov=res["cov"].loc[names, names].values, at_bound=res["at_bound"])


def run(model, fam_name, fam, P, pkl, LLrep, Krep, label_of, pword, tags, title, comp_lab, threads=3, log=print, refit_ok=True, ref_rows=None):
    """label_of(q) -> plain label of a local parameter / column; pword {purpose: word}; tags {purpose: file prefix of its variable
    heatmap}; title: plain title of the model"""
    t0 = time.time(); fin = pickle.load(open(pkl, "rb")); M = fam.M
    specs = {p: M.Spec("pool", *fin["specs"][p][:3], mu_fixed=(fin["specs"][p][3] if len(fin["specs"][p]) > 3 else None)) for p in P}
    S = PC.Structure(P, specs, fin["S"], fin.get("fixed", {})); x = fin["x"]; held0 = {k for k, v in S.fixed.items() if v == 0.0}
    pieces = fam.C.pw_names("d", fam.C.KNOTS) + fam.C.pw_names("dt", fam.C.DKNOTS)
    has_main = any(q in ("lnd", "lndt") for p in P for q in specs[p].linear if S.key(p, q) not in held0)
    inv = {v: k for k, v in PC.ABBR.items()}

    def gword(g):
        if g == "shared": return "all purposes"
        if g in pword: return pword[g]
        ps = [inv[a] for a in g.split("+")]
        return "both purposes" if len(ps) == len(P) == 2 else " + ".join(pword[p] for p in ps)
    gl = lambda n: f"{label_of(par(n))} [{gword(grp(n))}]" if grp(n) != "scale" else f"scale, {pword[par(n)]}"
    # ---------------------------------------------------------------- (a) variables, purpose by purpose (before the workers start)
    sk = fam.C.skims(); Cp, vnp, free_lin = {}, {}, {}
    for p in P:
        t1 = time.time(); ch, N = fam.build(p, specs[p], sk=sk)
        th = {c: x[S.key(p, f"theta_{c}")] for c in specs[p].size_comps}
        Cp[p], vnp[p] = purpose_cov(ch, specs[p], th); del ch
        free_lin[p] = [q for q in specs[p].linear if S.key(p, q) not in held0]
        log(f"{model} {p}: N {N}, within-situation cross products {time.time() - t1:.0f} s; free linear terms {len(free_lin[p])} "
            f"(held at 0: {[q for q in specs[p].linear if q not in free_lin[p]]})")
    rows, facts = [], dict(purposes={})
    for p in P:
        keep = free_lin[p] + [v for v in vnp[p] if is_size_col(v)]; ix = [vnp[p].index(v) for v in keep]
        R = corr(Cp[p][np.ix_(ix, ix)]); k0 = len(free_lin[p]); vf = np.r_[CC.vif(R[:k0, :k0]), np.full(len(keep) - k0, np.nan)]
        lab = {v: (label_of(v) if not is_size_col(v) else ("ln size S (final weights)" if v == "lnS" else f"ln(1 + {comp_lab[v[5:]]}) (size component)")) for v in keep}
        tag = tags[p]
        CC.heatmap(R, [lab[v] for v in keep], f"{HERE}/{tag}_var_corr.png",
                   f"{title}, {pword[p]}:\ncorrelations of the explanatory variables within choice situation\n(demeaned over the 1,588 zones), estimation half",
                   "Correlation (within choice situation)")
        pd.DataFrame(R, index=keep, columns=keep).round(3).to_csv(f"{HERE}/{tag}_var_corr.csv")
        facts["purposes"][p] = dict(file=f"{tag}_var_corr.png", max_vif=float(np.nanmax(vf)), vif=dict(zip(keep[:k0], np.round(vf[:k0], 2))))
        for a, b, r in CC.pairs(R, keep, CC.R_VAR):
            t, why, _ = kind(a, b, pieces, has_main)
            rows.append(dict(model=model, purpose=p, pair=f"{lab[a]} / {lab[b]} ({pword[p]})", p1=S.key(p, a) if a in free_lin[p] else a,
                             p2=S.key(p, b) if b in free_lin[p] else b, source="variables", type=t, why=why, var_r=r,
                             VIF_p1=vf[keep.index(a)], VIF_p2=vf[keep.index(b)]))
        for v, z in zip(keep, vf):
            if z >= CC.VIF_MAX: rows.append(dict(model=model, purpose=p, pair=f"{lab[v]} ({pword[p]})", p1=S.key(p, v), source="VIF", VIF=z))
    # pooled VIF: global free linear parameters, purpose columns times the purpose scale
    G = []
    for p in P:
        for q in free_lin[p]:
            if S.key(p, q) not in G: G.append(S.key(p, q))
    CG = np.zeros((len(G), len(G)))
    for p in P:
        m = x.get(f"scale|{p}", 1.0); gi = [G.index(S.key(p, q)) for q in free_lin[p]]; li = [vnp[p].index(q) for q in free_lin[p]]
        CG[np.ix_(gi, gi)] += m * m * Cp[p][np.ix_(li, li)]
    RG = corr(CG); vG = CC.vif(RG)
    pd.DataFrame(RG, index=G, columns=G).round(3).to_csv(f"{HERE}/{model}_var_corr_pooled.csv")
    facts.update(max_vif=float(vG.max()), vif_pooled=dict(zip(G, np.round(vG, 2))))
    for g, z in zip(G, vG):
        if z >= CC.VIF_MAX: rows.append(dict(model=model, purpose="pooled", pair=f"{gl(g)} (pooled design)", p1=g, source="VIF (pooled)", VIF=z))
    log(f"{model}: pooled VIF max {vG.max():.2f} ({G[int(np.argmax(vG))]}); per purpose max " + ", ".join(f"{p} {facts['purposes'][p]['max_vif']:.2f}" for p in P))
    # ---------------------------------------------------------------- (b) estimates: re-fit of the final pooled model
    eng = PC.ParEngine(fam_name, P, specs, threads=threads, log=log)
    try:
        res = eng.fit(S, x, "C0", "re-fit of the final pooled model"); base = as_base(res, S)
        log(f"{model}: LL {base['LL']:.4f} reported {LLrep:.4f} diff {base['LL'] - LLrep:.2e}; K {base['K']} reported {Krep}")
        assert abs(base["LL"] - LLrep) < 0.1 and base["K"] == Krep
        en = [n for n in base["names"] if np.isfinite(base["se"][base["names"].index(n)]) and base["se"][base["names"].index(n)] > 0]
        ii = [base["names"].index(n) for n in en]; Re = CC.est_corr(base["cov"][np.ix_(ii, ii)])
        CC.heatmap(Re, [gl(n) for n in en], f"{HERE}/{model}_est_corr.png",
                   f"{title}:\ncorrelations of the estimates (robust covariance)\nestimation half, LL {base['LL']:,.1f}, {base['K']} parameters", "Correlation of the estimates")
        pd.DataFrame(Re, index=en, columns=en).round(3).to_csv(f"{HERE}/{model}_est_corr.csv")
        gv = {g: i for i, g in enumerate(G)}
        for a, b, r in CC.pairs(Re, en, CC.R_EST):
            t, why, _ = kind(a, b, pieces, has_main)
            rows.append(dict(model=model, purpose="pooled", pair=f"{gl(a)} / {gl(b)}", p1=a, p2=b, source="estimates", type=t, why=why, est_r=r,
                             var_r=RG[gv[a], gv[b]] if a in gv and b in gv else np.nan, VIF_p1=vG[gv[a]] if a in gv else np.nan,
                             VIF_p2=vG[gv[b]] if b in gv else np.nan))
        for q in rows:   # estimate correlation of every flagged variable pair (global parameters)
            if q["source"] == "variables" and q["p1"] in en and q["p2"] in en and q["p1"] != q["p2"]:
                q["est_r"] = float(Re[en.index(q["p1"]), en.index(q["p2"])])
        Pf = pd.DataFrame(rows); print(Pf.drop(columns=["pair"]).to_string(), flush=True)
        # ---------------------------------------------------------------- (e) refits
        ref, done, cache = list(ref_rows or []), set(), {}   # ref_rows: refit rows of an earlier run of the same model (no refit here)
        protect = lambda n: grp(n) == "scale" or is_size_par(par(n)) or is_size_col(par(n)) or n not in base["names"]
        need = Pf[(Pf.source.isin(["variables", "estimates"])) & Pf.apply(lambda q: kind(q.p1, q.p2, pieces, has_main)[2], axis=1)] if refit_ok and len(Pf) else Pf.iloc[:0]
        for _, q in need.iterrows():
            a, b = q.p1, q.p2
            if frozenset((a, b)) in done or a == b: continue
            done.add(frozenset((a, b)))
            for drop, follow in ((a, b), (b, a)):
                if protect(drop): continue
                if drop not in cache:
                    r = eng.fit(S.copy(fix={drop: 0.0}), x, f"C{len(cache) + 1}", f"without {drop}")
                    cache[drop] = as_base(r, S.copy(fix={drop: 0.0})) if r is not None else None
                if cache[drop] is None: continue
                rr = CC.refit_row(base, cache[drop], follow, f"without {drop}"); rr.update(model=model, purpose="pooled", pair=q.pair); ref.append(rr)
                log({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rr.items()})
    finally:
        eng.close()
    facts.update(LL=base["LL"], LL_reported=LLrep, K=base["K"], N=base["N"], minutes=(time.time() - t0) / 60)
    CA.save_part(model, Pf.to_dict("records") + ref, facts)
    log(f"{model}: done in {(time.time() - t0) / 60:.1f} min")
    return Pf, ref
