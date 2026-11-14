#!/usr/bin/env python3
"""Nested / multinomial logit of the tour mode choice in PyTorch (re-specification 2026-11-06): exact gradients and Hessian,
robust sandwich covariance (WESML sandwich H^-1 (sum w^2 g g') H^-1 for the weighted work segment), household-cluster bootstrap.
The utility is that of MarylandTourNestedModeChoice / activity/lib/mode_choice/mc_apply.py; a model is a list of parameter names:
  ASC_<A>            constant of alternative A (reference CD)
  gc                 generalised cost (min) on CD, CP, BUS, TRAIN (column gc_<A>);  gc_<A> mode-specific
  time               car minutes (CD, CP) and transit in-vehicle minutes (BUS, TRAIN);  time_car, time_pt separately
  ovt                transit out-of-vehicle minutes (BUS, TRAIN)
  cost_inc           money ($) / (household income / $84,216): CD operating cost, BUS / TRAIN fare (+ drive-access cost)
  park               paid-parking share at the destination area (CD)
  stops_nonauto      stops of the tour on WK, BK, BUS, TRAIN;   lnden_nonmot  ln density of the main zone on WK, BK
  <var>_<A>          column <var> on alternative A (km, age, male, lic, hhsize, autos, core_o, rural_o, core_d, rural_d, short,
                     joint, acc, rec, wash, inc_hi)
  mu_auto, mu_transit, mu_nonmot   nest parameters (>= 1); absent -> MNL
"""
import numpy as np
import pandas as pd
import torch
from scipy.optimize import minimize

torch.set_default_dtype(torch.float64); torch.set_num_threads(int(__import__("os").environ.get("MC_THREADS", "3")))
ALTS = ["CD", "WK", "BK", "CP", "BUS", "TRAIN"]; AI = {a: i for i, a in enumerate(ALTS)}
NEST = {"mu_auto": ["CD", "CP"], "mu_transit": ["BUS", "TRAIN"], "mu_nonmot": ["WK", "BK"]}
NONREF = ["WK", "BK", "CP", "BUS", "TRAIN"]


def design(f, names):
    """N x 6 x K design for the non-nest parameters"""
    N = len(f); cols = []
    g = lambda c: f[c].values.astype(float)
    for p in names:
        x = np.zeros((N, 6))
        if p.startswith("mu_"): continue
        if p.startswith("ASC_"): x[:, AI[p[4:]]] = 1
        elif p == "gc":
            for a in ["CD", "CP", "BUS", "TRAIN"]: x[:, AI[a]] = g(f"gc_{a}")
        elif p == "time": x[:, AI["CD"]] = g("car_min"); x[:, AI["CP"]] = g("car_min"); x[:, AI["BUS"]] = g("bus_ivt"); x[:, AI["TRAIN"]] = g("train_ivt")
        elif p == "time_car": x[:, AI["CD"]] = g("car_min"); x[:, AI["CP"]] = g("car_min")
        elif p == "time_pt": x[:, AI["BUS"]] = g("bus_ivt"); x[:, AI["TRAIN"]] = g("train_ivt")
        elif p == "ovt": x[:, AI["BUS"]] = g("bus_ovt"); x[:, AI["TRAIN"]] = g("train_ovt")
        elif p == "cost_inc":
            r = g("inc_r"); x[:, AI["CD"]] = g("cost_CD") / r; x[:, AI["BUS"]] = g("bus_c") / r; x[:, AI["TRAIN"]] = g("train_c") / r
        elif p == "park": x[:, AI["CD"]] = g("park")
        elif p == "stops_nonauto":
            for a in ["WK", "BK", "BUS", "TRAIN"]: x[:, AI[a]] = g("stops")
        elif p == "lnden_nonmot":
            for a in ["WK", "BK"]: x[:, AI[a]] = g("lnden_m")
        else:
            var, a = p.rsplit("_", 1)
            if a not in AI: raise KeyError(p)
            if var == "gc": x[:, AI[a]] = g(f"gc_{a}")
            else: x[:, AI[a]] = g(var)
        cols.append(x)
    X = np.stack(cols, -1) if cols else np.zeros((N, 6, 0))
    av = np.stack([f[f"av_{a}"].values > 0 for a in ALTS], 1)
    y = np.array([AI[c] for c in f.choice.values])
    return X, av, y


class Data:
    def __init__(self, f, names, weight=None):
        X, av, y = design(f, names)
        self.X = torch.tensor(X); self.av = torch.tensor(av); self.y = torch.tensor(y)
        self.w = torch.tensor(f[weight].values.astype(float) if weight else np.ones(len(f)))
        self.N = len(f); self.hh = f.household_id.values; self.f = f
        self.nests = [k for k in names if k.startswith("mu_")]
        self.lin = [p for p in names if not p.startswith("mu_")]
        self.names = self.lin + self.nests


def ll_obs(theta, D):
    K = len(D.lin); beta = theta[:K]
    V = D.X @ beta
    V = torch.where(D.av, V, torch.full_like(V, -1e9))
    if not D.nests:
        return torch.log_softmax(V, 1)[torch.arange(D.N), D.y]
    mu = {k: theta[K + i] for i, k in enumerate(D.nests)}
    lp = torch.zeros_like(V); I = []
    groups = []
    for k, mem in NEST.items():
        idx = [AI[a] for a in mem]; m = mu.get(k, torch.tensor(1.0))
        Vk = V[:, idx] * m; S = torch.logsumexp(Vk, 1)
        lp[:, idx] = Vk - S[:, None]; I.append(S / m); groups.append(idx)
    I = torch.stack(I, 1); top = I - torch.logsumexp(I, 1, keepdim=True)
    for g_, idx in enumerate(groups): lp[:, idx] = lp[:, idx] + top[:, g_:g_ + 1]
    return lp[torch.arange(D.N), D.y]


def fit(D, x0=None, cov=True, w=None):
    """weighted ML (weights D.w, or w if given: bootstrap multiplicities x weights)"""
    names = D.names; K = len(names); ww = D.w if w is None else torch.tensor(w)
    x0 = np.array([(x0 or {}).get(p, 1.2 if p.startswith("mu_") else 0.0) for p in names], float)
    bnds = [(1.0, 10.0) if p.startswith("mu_") else (None, None) for p in names]
    x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bnds)])

    def fg(v):
        t = torch.tensor(v, requires_grad=True); l = -(ww * ll_obs(t, D)).sum()
        if not torch.isfinite(l): return 1e15, np.zeros_like(v)
        l.backward(); return float(l), t.grad.numpy().copy()
    r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bnds, options=dict(maxiter=5000, maxfun=20000, ftol=1e-15, gtol=1e-7, maxcor=50))
    out = dict(names=names, x=r.x.copy(), LL=-float(r.fun), K=K, N=D.N, converged=bool(r.success),
               at_bound=[p for p, v, (lo, hi) in zip(names, r.x, bnds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)])
    if cov: out.update(covariance(D, r.x, out["at_bound"]))
    return out


def covariance(D, x, at_bound=()):
    names = D.names; K = len(names); xt = torch.tensor(np.asarray(x, float))
    H = torch.autograd.functional.hessian(lambda t: (D.w * ll_obs(t, D)).sum(), xt).numpy()
    from torch.func import jvp
    G = torch.stack([jvp(lambda t: ll_obs(t, D), (xt,), (e,))[1] for e in torch.eye(K)], 1).numpy()
    free = np.array([p not in at_bound for p in names])
    Hi = np.linalg.inv(-H[np.ix_(free, free)]); wg = G[:, free] * D.w.numpy()[:, None]
    cov = np.full((K, K), np.nan); cov[np.ix_(free, free)] = Hi @ (wg.T @ wg) @ Hi
    covh = np.full((K, K), np.nan); covh[np.ix_(free, free)] = Hi
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    return dict(cov=cov, cov_hess=covh, se=se, G=G, H=H, free=free, cond=float(np.linalg.cond(-H[np.ix_(free, free)])))


def table(r):
    return pd.DataFrame({"param": r["names"], "value": r["x"], "rob_se": r["se"], "rob_t": r["x"] / r["se"]})


def loglik(D, x):
    with torch.no_grad(): l = ll_obs(torch.tensor(np.asarray(x, float)), D).numpy()
    return float((D.w.numpy() * l).sum()), l


def probs(D, x):
    """N x 6 probabilities"""
    K = len(D.lin); th = torch.tensor(np.asarray(x, float))
    with torch.no_grad():
        V = D.X @ th[:K]; V = torch.where(D.av, V, torch.full_like(V, -1e9))
        if not D.nests: return torch.softmax(V, 1).numpy()
        mu = {k: th[K + i] for i, k in enumerate(D.nests)}; P = torch.zeros_like(V); I = []; groups = []
        for k, mem in NEST.items():
            idx = [AI[a] for a in mem]; m = mu.get(k, torch.tensor(1.0)); Vk = V[:, idx] * m; S = torch.logsumexp(Vk, 1)
            P[:, idx] = torch.softmax(Vk, 1); I.append(S / m); groups.append(idx)
        T = torch.softmax(torch.stack(I, 1), 1)
        for g_, idx in enumerate(groups): P[:, idx] = P[:, idx] * T[:, g_:g_ + 1]
        return P.numpy()


def cluster_bootstrap(D, r, B=100, seed=7):
    """household-cluster bootstrap with re-estimation (warm start at the estimates); returns the s.e. and the draws"""
    rng = np.random.default_rng(seed); u, inv = np.unique(D.hh, return_inverse=True); draws = []
    x0 = dict(zip(r["names"], r["x"]))
    for b in range(B):
        m = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u)).astype(float)[inv]
        rb = fit(D, x0=x0, cov=False, w=m * D.w.numpy()); draws.append(rb["x"])
    d = np.array(draws); return d.std(0, ddof=1), d
