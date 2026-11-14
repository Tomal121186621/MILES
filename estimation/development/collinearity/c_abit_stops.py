#!/usr/bin/env python3
"""Collinearity of the final stop-location models (stop_location/s_stops.py with s_stops_newls.py: mode-choice logsum of the
re-estimated mode models; spec and coefficients of the 'final' step of s_<p>_fit.csv / s_<p>_coef.csv, final specification line
of s_<p>.log), estimation half, full choice set (1,588 zones), location mixture.
Choice situation = (record, anchor configuration) row of the location mixture, weighted by its configuration weight w_nk (the
rows of one record sum to 1; records unweighted, as in the estimation).  All zones are available, so the within-situation
demeaning is over all 1,588 zones.  The within-situation correlation is accumulated chunk by chunk (the chunks of
estimate_fullset_taz.Chunk, imported), with the formula of c_silo_common.within_corr.  The size columns ln(1 + component) of every
size component and ln S at the final weights are shown with the variables (no VIF; coefficients theta / mu).
Updated 2026-11-09 for the revised finals (s_stops.py final stage, rules B, C, A, D): a size coefficient held at its bound
(final specification line '... mu fixed at 1 (bound)', s_rec) is held at 1 here too (not a parameter, as in the estimation).
Estimator: s_stops.fit_mix (L-BFGS-B, bounds, robust sandwich covariance), repeated here only to keep the covariance matrix.
    TAZ_THREADS=6 python3 estimation/development/collinearity/c_abit_stops.py [st_shop st_rec st_acc st_oth]
    -> st_<p>_var_corr.png/.csv, st_<p>_est_corr.png/.csv, st_<p>_pairs.csv, st_<p>_facts.json"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, ast, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "6")
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; SB = os.path.dirname(HERE); DS = os.path.join(SB, "dest_stop")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, os.path.join(DEV, "stop_location")); sys.path.insert(0, CODE)
import c_abit_common as A   # noqa: E402
CC = A.CC
import s_stops_newls as NL   # noqa: E402  (imports s_stops, patches the logsum feature to the new mode logsum)
import s_tables as ST   # noqa: E402
S = NL.S; M, F_, C = S.M, S.F_, S.C
import torch   # noqa: E402
from scipy.optimize import minimize   # noqa: E402

MODELS = {"st_shop": "s_shop", "st_rec": "s_rec", "st_acc": "s_acc", "st_oth": "s_oth"}
TITLE = {"st_shop": "Stop location, shopping", "st_rec": "Stop location, recreation", "st_acc": "Stop location, accompanying",
         "st_oth": "Stop location, other"}
COMPL = {"pop": "population", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school pupils"}


def table_labels(name):
    """param -> plain label, from the groups of s_tables.py, checked against the rows of est_stop_<P>_stop_new.tex"""
    lab = {}
    for _, rows in ST.GROUPS:
        for it in rows:
            if isinstance(it[0], str): lab[it[0]] = CC.plain(it[1])
    tex = CC.tex_labels(f"{DS}/est_stop_{ST.PUR[name][0]}_stop_new.tex")
    return lab, tex


def final_spec(name):
    line = [l for l in open(f"{DS}/{name}.log") if l.startswith("final specification:")][-1]
    m = re.match(r"final specification: (\[.*?\]), size base (\w+), components (\[.*?\]);", line)
    lin, base, comps = ast.literal_eval(m.group(1)), m.group(2), ast.literal_eval(m.group(3))
    co = pd.read_csv(f"{DS}/{name}_coef.csv"); co = co[co.step == "final"]
    fit = pd.read_csv(f"{DS}/{name}_fit.csv"); fin = fit[fit.step == "final"].iloc[0]
    mu = 1.0 if "mu fixed at 1" in line else None          # revision 2026-11-09 (rule D): size coefficient held at its bound
    return lin, base, comps, dict(zip(co.param, co.coef)), dict(zip(co.param, co.se)), float(fin.LL), int(fin.K), mu


def fit_full(spec, rec, cand, cfg, pur, sk, x0, keep=False):
    """s_stops.fit_mix (same chunks, bounds, optimiser, robust sandwich covariance), returning the covariance matrix as well"""
    names = spec.params(); t0 = time.time()
    chunks = [F_.Chunk(rec.iloc[i:i + F_.CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + F_.CHUNK])], cfg, spec, pur, sk)
              for i in range(0, len(rec), F_.CHUNK)]
    bounds = S.bounds_of(names)
    x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bounds)])

    def fg(v):
        t = torch.tensor(v, requires_grad=True); tot = 0.0
        for c in chunks:
            l = -c.ll(t, spec).sum(); l.backward(); tot += float(l.detach())
        return (tot, t.grad.numpy().copy()) if np.isfinite(tot) else (1e15, np.zeros_like(v))
    r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bounds, options=dict(maxiter=3000, maxfun=12000, ftol=1e-13, gtol=1e-6, maxcor=30))
    x = torch.tensor(r.x); K = len(x)
    from torch.func import jvp
    H = torch.zeros((K, K)); G = []
    for c in chunks:
        H += torch.autograd.functional.hessian(lambda t: c.ll(t, spec).sum(), x)
        G.append(torch.stack([jvp(lambda t: c.ll(t, spec), (x,), (e,))[1] for e in torch.eye(K)], 1))
    G = torch.cat(G)
    at_bound = [p for p, v, (lo, hi) in zip(names, r.x, bounds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
    free = torch.tensor([p not in at_bound for p in names]); cov = torch.full((K, K), float("nan"))
    Hi = torch.linalg.inv(-H[free][:, free]); Gf = G[:, free]; fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
    for a, ia in enumerate(fi): cov[ia, fi] = cf[a]
    cov = cov.numpy(); se = np.sqrt(np.clip(np.diag(cov), 0, None))
    out = dict(LL=-float(r.fun), K=K, N=len(rec), names=list(names), b=r.x.copy(), se=se, cov=cov, at_bound=at_bound,
               converged=bool(r.success), secs=time.time() - t0)
    print(f"    fit K {K} LL {out['LL']:.3f} conv {out['converged']} at bound {at_bound} ({out['secs']:.0f} s)", flush=True)
    if keep: out["chunks"] = chunks
    return out


def var_corr(chunks, spec, b):
    """within-situation correlation (c_silo_common.within_corr, all zones available) of the linear variables, ln(1 + component)
    of every size component and ln S at the estimates; situations weighted by their configuration weight"""
    K = len(spec.linear); comps = [spec.size_base] + spec.size_comps
    w = np.r_[1.0, [np.exp(b[f"theta_{c}"]) for c in spec.size_comps]]; Cm = 0.0
    for c in chunks:
        X = c.X32.double().numpy(); Sz = c.S32.double().numpy(); n, J = X.shape[:2]
        gi, lw = c.gidx.numpy(), c.logw.numpy(); rw = np.zeros(n); ok = np.isfinite(lw); rw[gi[ok]] = np.exp(lw[ok])
        Xa = np.concatenate([X, np.log1p(np.maximum(Sz, 0.0)), np.log1p((Sz * w).sum(-1))[..., None]], -1); del X
        Z = (Xa - Xa.mean(1, keepdims=True)).reshape(n * J, -1); cw = np.repeat(rw / J, J)
        Cm = Cm + (Z * cw[:, None]).T @ Z; del Xa, Z
    s = np.sqrt(np.diag(Cm)); vn = list(spec.linear) + [f"ln1p_{c}" for c in comps] + ["lnS"]
    return Cm / np.outer(s, s), vn


def kind(a, b, protect):
    da, db = a.startswith("dt_"), b.startswith("dt_")
    la, lb = a.startswith("lndt_"), b.startswith("lndt_")
    if a in protect and b in protect: return "STRUCTURAL", "size-term parameters", False
    if da and db:
        i, j = sorted(PIECES.index(v) for v in (a, b))
        return "STRUCTURAL", "adjacent piecewise segments of the detour" if j - i == 1 else "piecewise segments of the detour (non-adjacent)", False
    if la and lb: return "STRUCTURAL", "two interactions of ln(1 + detour) (no main effect in the model: centring not applicable)", True
    if (da and lb) or (db and la): return "STRUCTURAL", "functional form of one variable (detour segment vs ln(1 + detour) interaction)", True
    return "SUBSTANTIVE", "", True


PIECES = C.pw_names("dt", C.DKNOTS)


def one(model):
    name = MODELS[model]; seg = S.MODELS[name]; pur = seg.split("_")[0]; sk = C.skims()
    lin, base_c, comps, co, se_rep, LLrep, Krep, mu_fx = final_spec(name)
    lab, tex = table_labels(name)
    order = [p for _, rows in ST.GROUPS for it in rows if isinstance(it[0], str) for p in [it[0]] if p in lin]   # table order
    assert sorted(order) == sorted(lin), (order, lin)
    spec = M.Spec("final", order, base_c, comps, mu_fixed=mu_fx); names = spec.params()
    for p in names: assert lab[p] in tex, (p, lab[p])                       # labels are the table's row labels
    for c in [base_c] + comps: lab[f"ln1p_{c}"] = f"ln(1 + {COMPL[c]}) (size component)"
    lab["lnS"] = "ln size S (final weights)"
    rec, cand, cfg = F_.load(seg, "estimation")
    print(model, seg, "N", len(rec), "spec", names, flush=True)
    base = fit_full(spec, rec, cand, cfg, pur, sk, np.array([co[p] for p in names]), keep=True)
    print(model, "LL", base["LL"], "reported", LLrep, "diff", base["LL"] - LLrep, flush=True)
    assert abs(base["LL"] - LLrep) < 0.1 and base["K"] == Krep
    se_dev = max(abs(s / se_rep[p] - 1) for p, s in zip(names, base["se"]))
    bdict = dict(zip(names, base["b"]))
    R, vn = var_corr(base.pop("chunks"), spec, bdict)
    k0 = len(spec.linear); vf = np.r_[CC.vif(R[:k0, :k0]), np.full(len(vn) - k0, np.nan)]
    protect = [n for n in names if n.startswith(("theta_", "mu_"))]
    par_of = {f"ln1p_{c}": f"theta_{c}" for c in comps}; par_of["lnS"] = "mu_size"; par_of[f"ln1p_{base_c}"] = "mu_size"; par_of.update({v: v for v in spec.linear})   # base component: theta 0
    title = f"{TITLE[model]}, final model"
    CC.heatmap(R, [lab[v] for v in vn], f"{HERE}/{model}_var_corr.png",
               f"{title}: correlations of the explanatory variables\nwithin choice situation (demeaned over the 1,588 zones), estimation half",
               "Correlation (within choice situation)")
    Re = CC.est_corr(base["cov"])
    CC.heatmap(Re, [lab[n] for n in names], f"{HERE}/{model}_est_corr.png",
               f"{title}: correlations of the estimates (robust covariance)\nestimation half, LL {base['LL']:,.1f}, {base['K']} parameters",
               "Correlation of the estimates")
    pd.DataFrame(R, index=vn, columns=vn).round(3).to_csv(f"{HERE}/{model}_var_corr.csv")
    pd.DataFrame(Re, index=names, columns=names).round(3).to_csv(f"{HERE}/{model}_est_corr.csv")
    vi = {n: i for i, n in enumerate(vn)}; bi = {n: i for i, n in enumerate(names)}
    vrow = lambda a, b: float(R[vi[a], vi[b]]) if a in vi and b in vi else np.nan
    erow = lambda a, b: float(Re[bi[a], bi[b]]) if a in bi and b in bi else np.nan

    rows = []
    for a, b, r in CC.pairs(R, vn, CC.R_VAR):
        pa, pb = par_of[a], par_of[b]; t, why, _ = kind(pa, pb, protect)
        if a not in spec.linear or b not in spec.linear:
            if a in spec.linear or b in spec.linear: t, why = "SUBSTANTIVE", "variable vs size-term column"
            else: t, why = "STRUCTURAL", "size-term columns"
        rows.append(dict(model=model, pair=f"{lab[a]} / {lab[b]}", p1=a, p2=b, source="variables", type=t, why=why, var_r=r, est_r=erow(pa, pb)))
    for v, x in zip(vn, vf):
        if x >= CC.VIF_MAX: rows.append(dict(model=model, pair=lab[v], p1=v, source="VIF", VIF=x))
    for a, b, r in CC.pairs(Re, names, CC.R_EST):
        t, why, _ = kind(a, b, protect)
        rows.append(dict(model=model, pair=f"{lab[a]} / {lab[b]}", p1=a, p2=b, source="estimates", type=t, why=why, est_r=r, var_r=vrow(a, b)))
    P = pd.DataFrame(rows)
    if len(P):
        P["VIF_p1"] = [vf[vi[x]] if x in vi else np.nan for x in P.p1]; P["VIF_p2"] = [vf[vi[x]] if isinstance(x, str) and x in vi else np.nan for x in P.p2]
    print(P.drop(columns=["pair"]).to_string() if len(P) else "no flags", flush=True)

    cache = {}

    def refit(drop=(), comps_drop=()):
        key = (tuple(sorted(drop)), tuple(sorted(comps_drop)))
        if key not in cache:
            sp = M.Spec("r", [p for p in spec.linear if p not in drop], base_c, [c for c in comps if c not in comps_drop], mu_fixed=mu_fx)
            x0 = np.array([bdict[p] for p in sp.params()])
            print("  refit without", key, flush=True); cache[key] = fit_full(sp, rec, cand, cfg, pur, sk, x0)
        return cache[key]

    ref, done = [], set()
    need = P[(P.source != "VIF") & ~P.why.astype(str).str.contains("size-term|piecewise segments", regex=True)] if len(P) else P
    for _, q in need.iterrows():
        a, b = par_of.get(q.p1, q.p1), par_of.get(q.p2, q.p2)
        if frozenset((a, b)) in done: continue
        done.add(frozenset((a, b)))
        for drop, follow in ((a, b), (b, a)):
            if drop in protect: continue
            rr = CC.refit_row(base, refit([drop]), follow, f"without {drop}"); rr.update(model=model, pair=q.pair); ref.append(rr)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rr.items()}, flush=True)

    # ---- explicit checks
    checks, crow = [], []
    rdens = "lnretden" in vi
    for c in [base_c] + comps:   # size columns vs land use
        checks.append(dict(check="size column vs land use", column=f"ln(1 + {COMPL[c]})", theta=bdict.get(f"theta_{c}", 0.0),
                           r_lnretden=vrow(f"ln1p_{c}", "lnretden"), r_mix=vrow(f"ln1p_{c}", "mix")))
    checks.append(dict(check="size column vs land use", column="ln S", mu=bdict.get("mu_size", mu_fx), mu_fixed=mu_fx, r_lnretden=vrow("lnS", "lnretden"),
                       r_mix=vrow("lnS", "mix"), est_r_mu_lnretden=erow("mu_size", "lnretden"), est_r_mu_mix=erow("mu_size", "mix")))
    if mu_fx is None and bdict["mu_size"] > 1 and rdens:   # (1) size mu above 1: refit without retail density
        m = refit(["lnretden"]); i = m["names"].index("mu_size")
        r = A.check_row(model, "size mu > 1 vs retail density", "without lnretden", base, m, "mu_size"); crow.append(r)
        checks.append(dict(check="mu > 1: refit without retail density", mu_final=bdict["mu_size"], mu_refit=float(m["b"][i]),
                           se_mu_refit=float(m["se"][i]), mu_refit_le_1=bool(m["b"][i] <= 1), r_lnS_lnretden=vrow("lnS", "lnretden"),
                           est_r_mu_lnretden=erow("mu_size", "lnretden"), LL=m["LL"], dLL=m["LL"] - base["LL"], dBIC=r["dBIC"], LR_p=r["p"],
                           sign_changes=r["sign_changes"]))
    for c in comps:   # (2) theta below -10: refit without the component
        if bdict[f"theta_{c}"] < -10:
            m = refit(comps_drop=[c]); r = A.check_row(model, f"theta {c} < -10", f"without size component {c}", base, m, "mu_size"); crow.append(r)
            checks.append(dict(check=f"theta_{c} < -10: refit without the component", theta=bdict[f"theta_{c}"],
                               se_theta=float(base["se"][bi[f"theta_{c}"]]), LL=m["LL"], dLL=m["LL"] - base["LL"], dBIC=r["dBIC"], LR_p=r["p"],
                               mu_refit=float(m["b"][m["names"].index("mu_size")]) if "mu_size" in m["names"] else mu_fx, sign_changes=r["sign_changes"]))
    if "dt_0_1" in bdict and bdict["dt_0_1"] > 0:   # (3) positive first detour segment: refit with it fixed at 0
        m = refit(["dt_0_1"]); r = A.check_row(model, "positive 0-1 km detour slope", "dt_0_1 fixed at 0", base, m, "intra_a"); crow.append(r)
        mb = dict(zip(m["names"], zip(m["b"], m["se"])))
        checks.append(dict(check="dt_0_1 > 0: refit with the segment fixed at 0", b_dt_0_1=bdict["dt_0_1"], se_dt_0_1=float(base["se"][bi["dt_0_1"]]),
                           var_r_intra_a=vrow("dt_0_1", "intra_a"), var_r_intra_b=vrow("dt_0_1", "intra_b"),
                           est_r_intra_a=erow("dt_0_1", "intra_a"), est_r_intra_b=erow("dt_0_1", "intra_b"),
                           var_r_dt_1_2=vrow("dt_0_1", "dt_1_2"), est_r_dt_1_2=erow("dt_0_1", "dt_1_2"),
                           LL=m["LL"], dLL=m["LL"] - base["LL"], dBIC=r["dBIC"], LR_p=r["p"],
                           intra_a_before=bdict["intra_a"], intra_a_after=mb["intra_a"][0], intra_b_before=bdict["intra_b"], intra_b_after=mb["intra_b"][0],
                           dt_1_2_before=bdict["dt_1_2"], dt_1_2_after=mb["dt_1_2"][0], sign_changes=r["sign_changes"]))
    for ch in checks: print(ch, flush=True)
    A.save_part(model, P.to_dict("records") + ref + crow,
                dict(LL=base["LL"], LL_reported=LLrep, K=base["K"], N=base["N"], max_se_rel_dev_vs_reported=se_dev,
                     max_vif=float(np.nanmax(vf)), vif=dict(zip(vn[:k0], np.round(vf[:k0], 2))), checks=checks))


if __name__ == "__main__":
    for m in sys.argv[1:] or list(MODELS): one(m)
