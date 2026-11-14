#!/usr/bin/env python3
"""Collinearity of the final location models l01_daycare ... l06_outing_dest (other_locations/l_locations.py through
l_locations_newls.py, which produced the current finals <name>_coef.csv / _fit.csv 'final'; l05 with the new mode logsum in
block 14, where car generalised time won), estimation half, full choice set (1,588 zones, all available), unweighted as estimated.
Records, features and the chunked likelihood are those of the estimation (l_locations_newls -> estimate_fullset_loc /
estimate_fullset_taz.Chunk, dc_model.utility); fit_cov repeats estimate_fullset_loc.fit and also returns the robust covariance.
(a) within-situation correlations of the linear terms, with ln(1 + size component) of every final component and ln S at the
final weights (coefficient mu) shown as extra columns; (b) robust estimate correlations; (c) heatmaps with the labels of the
tables_new/est_loc_*_new.tex / est_subtour_new.tex rows; (d)-(e) flags and refits (c_silo_common.run_alt_model);
explicit checks: mu > 1 vs retail density, theta < -10 (refit without the component), positive first / last distance segment
vs the same-zone dummies (refit with the segment at 0).
    TAZ_THREADS=6 python3 estimation/development/collinearity/c_abit_loc.py [l03_wahb ...]  ->  <name>_var_corr.png, <name>_est_corr.png, <name>_pairs.csv, <name>_facts.json
Updated 2026-11-09 for the revised finals (l_locations.py final stage, rules B, C, A, D).  l01_daycare and l02_nonstud are superseded
by the pooled model lp_edu (other_locations/lp_pooled.py, adopted): checked as pooled by c_abit_pool.py,
    POOL_THREADS=3 python3 estimation/development/collinearity/c_abit_loc.py lp_edu  ->  lp_edu_nonstud|daycare_var_corr.png/.csv, lp_edu_var_corr.png (side by side),
    lp_edu_est_corr.png/.csv, lp_edu_pairs.csv, lp_edu_facts.json, loc_lp_edu.log
(the 2026-11-08 outputs of l01 / l02 separate are left as they were)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, ast, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "6")
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; SB = os.path.dirname(HERE); LOC = os.path.join(SB, "locations")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, os.path.join(DEV, "other_locations")); sys.path.insert(0, CODE); sys.path.insert(0, os.path.join(DEV, "tables"))
import c_abit_common as CA   # noqa: E402
import l_locations_newls as LN   # noqa: E402  (patches l_locations.Run.load and dc_model.features: new mode logsum)
import t_new_tables as TT   # noqa: E402  (label table of the est_loc_*_new.tex rows)
LL_, M, C = LN.LL, LN.M, LN.C
FL = LL_.FL; F_ = FL.F_; X_ = FL.X
import torch   # noqa: E402
from scipy.optimize import minimize   # noqa: E402

TEX = {"l01_daycare": "est_loc_daycare_new.tex", "l02_nonstud": "est_loc_nonstud_new.tex", "l03_wahb": "est_loc_wahb_new.tex",
       "l04_wbhome": "est_loc_wbhome_new.tex", "l05_wbwork": "est_loc_wbwork_new.tex", "l06_outing_dest": "est_subtour_new.tex"}
TITLE = {"l01_daycare": "Daycare location (l01)", "l02_nonstud": "School location without a school record (l02)",
         "l03_wahb": "Work location of at-home workers (l03)", "l04_wbhome": "Work business from home (l04)",
         "l05_wbwork": "Work business of a worker with a usual workplace (l05)", "l06_outing_dest": "Outing destination from the workplace (l06)"}
ANCHOR = {"l06_outing_dest": "workplace"}
COMPL = {"pop": "population", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school pupils"}


def final_spec(name):
    line = [l for l in open(f"{LOC}/{name}.log") if l.startswith("final specification:")][-1]
    lin = ast.literal_eval(line[len("final specification: "):line.index("]") + 1])
    base = line.split("size base ")[1].split(",")[0].strip(); comps = ast.literal_eval(line[line.index("components ") + 11:line.rindex("]") + 1])
    co = pd.read_csv(f"{LOC}/{name}_coef.csv"); co = co[co.step == "final"].set_index("param")
    spec = M.Spec("final", lin, base, comps); assert spec.params() == list(co.index), (spec.params(), list(co.index))
    fr = pd.read_csv(f"{LOC}/{name}_fit.csv"); fin = fr[fr.step == "final"].iloc[0]
    return spec, co, fin


def fit_cov(spec, rec, cand, pur, sk, x0):
    """estimate_fullset_loc.fit (same chunks, bounds, optimiser, Hessian and scores), returning the robust covariance as well"""
    names = spec.params(); cfg = X_.single_cfg(rec)
    chunks = [F_.Chunk(rec.iloc[i:i + F_.CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + F_.CHUNK])], cfg, spec, pur, sk) for i in range(0, len(rec), F_.CHUNK)]
    bounds = [(-30.0, 15.0) if p.startswith("theta_") else (0.0, 3.0) if p == "mu_size" else (None, None) for p in names]
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
    return dict(LL=-float(r.fun), K=K, N=len(rec), names=list(names), b=r.x.copy(), se=se, cov=cov, at_bound=at_bound, converged=bool(r.success))


def labels(name, stop):
    lab = {}
    for _, terms in TT.loc_groups(ANCHOR.get(name, "home"), stop):
        for t in terms:
            if isinstance(t, tuple) and isinstance(t[0], str) and isinstance(t[1], str): lab[t[0]] = CA.plain(t[1])
    return lab


def one(name, log):
    t0 = time.time(); spec, co, fin = final_spec(name)
    r = LL_.Run.__new__(LL_.Run); r.seg, r.pur = LL_.MODELS[name]; sk = C.skims()
    stop = any(p.startswith("dt") or p.startswith("intra_") for p in spec.linear); form = "stop" if stop else "primary"
    rec, cand = r.load("estimation", form); pur = r.pur
    lab = labels(name, stop); tex = CA.tex_labels(f"{SB}/tables_new/{TEX[name]}")
    for p in spec.params(): assert lab[p] in tex, (p, lab[p])          # labels are the table's row labels
    comps = [spec.size_base] + spec.size_comps
    for c in comps: lab[f"ln1p_{c}"] = f"ln(1 + {COMPL[c]}) (size component)"
    lab["lnS"] = "ln size S (final weights, coefficient μ)"
    cache = {}

    def run(drop=(), dropcomp=(), replace=None):
        assert not replace
        key = (tuple(sorted(drop)), tuple(sorted(dropcomp)))
        if key not in cache:
            sp = M.Spec("c", [p for p in spec.linear if p not in drop], spec.size_base, [c for c in spec.size_comps if c not in dropcomp])
            x0 = np.array([co.coef[p] for p in sp.params()]); t1 = time.time()
            cache[key] = fit_cov(sp, rec, cand, pur, sk, x0)
            log(f"  fit drop {list(drop)} comps {list(dropcomp)}: LL {cache[key]['LL']:.3f} K {cache[key]['K']} at bound {cache[key]['at_bound']} "
                f"converged {cache[key]['converged']} {time.time() - t1:.0f} s")
        return {k: v for k, v in cache[key].items()}

    base = run(); log(f"{name}: LL {base['LL']:.4f} reported {fin.LL:.4f} diff {base['LL'] - fin.LL:.2e}")
    assert abs(base["LL"] - fin.LL) < 0.1
    # (a) design of the final model on the full choice set (one configuration per record, as estimated)
    alts, lnc, logb = M.full_sets(rec, cand); D = M.Data(rec, alts, lnc, logb, spec, pur, sk)
    X = D.X.numpy().astype(float); S = D.S.numpy().astype(float); av = np.ones(X.shape[:2], bool); w = np.ones(len(rec))
    bi = dict(zip(base["names"], base["b"]))
    wts = np.r_[1.0, [np.exp(bi[f"theta_{c}"]) for c in spec.size_comps]]; lnS = np.log1p((S * wts).sum(-1))
    extra = CA.size_extra(S, comps, lnS); del D
    names = list(spec.linear)
    dist = [p for p in names if p.startswith(("d_", "dt_")) or p in ("d", "dt", "lnd", "lndt")]
    sets = [(set(dist), "functional form of one variable (distance / detour: pieces, linear, log)"),
            ({p for p in base["names"] if p.startswith(("theta_", "mu_"))}, "size-term parameters"),
            ({n for n, _ in extra}, "size-term columns (ln S and ln(1 + its components), information only)")]
    protect = [n for n in base["names"] if n.startswith(("mu_", "theta_"))] + [n for n, _ in extra]   # extra columns: no refit
    P, ref = CA.run_alt_model(name, f"{TITLE[name]}, final model", X, names, av, w, lab, {}, sets, base,
                              lambda drop, replace: run(drop, replace=replace), protect=protect, extra_vars=extra)
    ex = {n for n, _ in extra}; pf = f"{CA.OUT}/{name}_pairs.csv"; Pp = pd.read_csv(pf)
    m_ = (Pp.p1.isin(ex) ^ Pp.p2.isin(ex)) & Pp.refit.isna() if "refit" in Pp else (Pp.p1.isin(ex) ^ Pp.p2.isin(ex))
    Pp.loc[m_, "type"] = "SIZE"; Pp.loc[m_, "why"] = "size-term column vs a variable (information; theta / mu vs land use, see CHECK rows)"
    Pp.to_csv(pf, index=False)
    R = pd.read_csv(f"{CA.OUT}/{name}_var_corr.csv", index_col=0); Re = pd.read_csv(f"{CA.OUT}/{name}_est_corr.csv", index_col=0)
    rows, checks = [], []
    # size components and ln S vs the land-use terms of the model
    lu = [p for p in ("lnretden", "mix") if p in names]
    for v in [f"ln1p_{c}" for c in comps] + ["lnS"]:
        checks.append(dict(check="size vs land use", var=v, **{f"r_{u}": float(R.loc[v, u]) for u in lu},
                           **{f"r_{p}": float(R.loc[v, p]) for p in dist[:1] + [q for q in ("intra", "intra_a") if q in names]}))
    # (1) mu > 1
    if bi["mu_size"] > 1:
        if "lnretden" in names:
            m = run(drop=["lnretden"]); mi = dict(zip(m["names"], m["b"])); ms = dict(zip(m["names"], m["se"]))
            row = CA.check_row(name, "size mu > 1 vs retail density", "without retail density", base, m, "mu_size",
                               var_r_lnS_retden=float(R.loc["lnS", "lnretden"]), est_r_mu_retden=float(Re.loc["mu_size", "lnretden"]))
            rows.append(row)
            checks.append(dict(check="mu > 1", mu_final=bi["mu_size"], se_final=float(base["se"][base["names"].index("mu_size")]),
                               r_lnS_retden=float(R.loc["lnS", "lnretden"]), est_r_mu_retden=float(Re.loc["mu_size", "lnretden"]),
                               mu_without_retden=mi["mu_size"], se_without=ms["mu_size"], LL_without=m["LL"], dLL=m["LL"] - base["LL"],
                               LR_p=row["p"], dBIC=row["dBIC"], sign_changes=row["sign_changes"]))
        else: checks.append(dict(check="mu > 1", mu_final=bi["mu_size"], note="no retail density term in the model"))
    # (2) theta < -10: not identified -> refit without the component
    for c in spec.size_comps:
        if bi[f"theta_{c}"] < -10:
            m = run(dropcomp=[c]); row = CA.check_row(name, f"theta_{c} < -10 (unidentified)", f"without size component {c}", base, m, "mu_size",
                                                     theta=bi[f"theta_{c}"])
            rows.append(row)
            checks.append(dict(check="theta < -10", comp=c, theta=bi[f"theta_{c}"], LL_without=m["LL"], dLL=m["LL"] - base["LL"],
                               LR=row["LR"], LR_p=row["p"], dBIC=row["dBIC"], max_abs_coef_change=float(max(abs(dict(zip(m["names"], m["b"]))[p] - bi[p])
                                                                                                          for p in m["names"]))))
    # (3) positive first (0-1 km) or last (> 50 km) distance / detour segment vs the same-zone dummies
    dums = [q for q in ("intra", "intra_a", "intra_b") if q in names]
    for sg in [p for p in names if p in ("d_0_1", "dt_0_1", "d_50_inf", "dt_20_inf")]:
        if bi[sg] <= 0: continue
        m = run(drop=[sg]); mi = dict(zip(m["names"], m["b"])); ms = dict(zip(m["names"], m["se"]))
        row = CA.check_row(name, f"positive segment {sg}", f"{sg} fixed at 0", base, m, dums[0] if dums else None)
        rows.append(row)
        checks.append(dict(check="positive segment", seg=sg, b=bi[sg], se=float(base["se"][base["names"].index(sg)]),
                           **{f"var_r_{q}": float(R.loc[sg, q]) for q in dums}, **{f"est_r_{q}": float(Re.loc[sg, q]) for q in dums},
                           **{f"{q}_final": bi[q] for q in dums}, **{f"{q}_fixed0": mi[q] for q in dums}, **{f"{q}_se_fixed0": ms[q] for q in dums},
                           LL_fixed0=m["LL"], dLL=m["LL"] - base["LL"], LR_p=row["p"], dBIC=row["dBIC"], sign_changes=row["sign_changes"],
                           next_seg=(lambda n: (n, mi[n]) if n else None)(next((p for p in names[names.index(sg) + 1:] if p in dist), None)) if sg.endswith("0_1") else None))
    CA.append_checks(name, rows, checks)
    log(f"{name}: checks {checks}"); log(f"{name}: done in {time.time() - t0:.0f} s")


def pooled_edu(log):
    """lp_edu = l02_nonstud (scale reference) + l01_daycare, final of lp_pooled.py (lp_edu_final.pkl, row 'final' of lp_edu_fit.csv)"""
    import c_abit_pool as CP
    import lp_pooled as LPP
    P = LPP.PAIRS["lp_edu"]; fit = pd.read_csv(f"{LOC}/lp_edu_fit.csv"); fin = fit[fit.step == "final"].iloc[0]
    lab = labels("l02_nonstud", False); lab.update(labels("l01_daycare", False)); lab = {k: v.replace("theta ", "θ ") for k, v in lab.items()}
    pword = {"l02_nonstud": "non-student school", "l01_daycare": "daycare"}; tags = {"l02_nonstud": "lp_edu_nonstud", "l01_daycare": "lp_edu_daycare"}
    CP.run("lp_edu", "lp_pooled", LPP, P, f"{LOC}/lp_edu_final.pkl", float(fin.LL), int(fin.K), lambda q: lab[q], pword, tags,
           "Non-student school and daycare, pooled model", COMPL, threads=int(os.environ.get("POOL_THREADS", "3")), log=log)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(12, 22))
    for a, p in zip(ax, P):
        a.imshow(plt.imread(f"{HERE}/{tags[p]}_var_corr.png")); a.axis("off")
    fig.tight_layout(); fig.savefig(f"{HERE}/lp_edu_var_corr.png", dpi=200); plt.close(fig)


if __name__ == "__main__":
    for n in sys.argv[1:] or [k for k in TEX if k not in ("l01_daycare", "l02_nonstud")] + ["lp_edu"]:
        if n == "lp_edu":
            lf = open(f"{HERE}/loc_lp_edu.log", "w")
            def log(s, lf=lf): print(s, flush=True); lf.write(str(s) + "\n"); lf.flush()
            pooled_edu(log); continue
        lf = open(f"{HERE}/loc_{n}.log", "w")
        def log(s, lf=lf): print(s, flush=True); lf.write(str(s) + "\n"); lf.flush()
        one(n, log)
