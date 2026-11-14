#!/usr/bin/env python3
"""Pooled full-set location-choice estimator with purpose-specific scale (shared by dp_pooled.py and sp_pooled.py).

Each purpose p has its own records, location mixture and specification Spec_p (the common specification, minus the size
components fixed out for p).  The utility of zone j is U_pj = mu_p V_pj, with
    V_pj = mu_size,p ln(1 + S_pj(theta_p)) + sum_k beta_pk x_pjk
so mu_p multiplies every linear coefficient and the size coefficient mu_size (when mu_size is held at a value, the scale does not multiply it); the size weights theta (inside the logarithm)
are not scaled.  A parameter of purpose p maps to a global parameter: its own (purpose specific) or a shared one (same value
in V_p of every purpose of the group).  Scales: one scale per group of purposes connected by shared SCALED parameters is
normalised to 1 (shopping's if shopping is in the group, otherwise the first purpose of the group); the others are free
(lower bound 0.01).  Shared theta do not identify scales.  With nothing shared the model is the separate models side by side
(LL = sum of the separate LLs).
Engine per purpose: estimate_fullset_taz.Chunk (full choice set, chunked mixture likelihood, float32 storage); the chunks of
every purpose are built ONCE (the specification of a purpose does not change across the pooling steps).  Optimiser: L-BFGS-B
with the options and bounds of d_primary / s_stops (theta in [-30, 15], mu_size in [0, 3]).  Hessian and per-record scores per
purpose on the sub-vector of global parameters that purpose uses; robust sandwich covariance H^-1 (G'G) H^-1 over all records.
ParEngine (used for the pooled models): the same likelihood with each purpose in its own worker process (local gradient,
Hessian and scores; chain rule in the master) and purpose-specific scaled coefficients estimated as gamma = mu_p beta
(reported as beta, delta method); Engine (single process) was used for the separate models.
Revision 2026-11-09: Structure.fixed = {global parameter: value} holds a parameter at a value (ParEngine: L-BFGS-B bounds
lo = hi; not counted in K, no standard error).  Used for the joint tests of band sets (whole set at 0), for distance pieces
fixed at 0 and for the size coefficient on its bound (mu = 1).  A purpose-specific scaled parameter of a purpose with a free
scale can only be fixed at 0.  ABBR may be extended by a family (location pairs); a family module may define
val_ll(p, spec, x, sk) for its validation LL (default: location mixture of the TAZ records).
"""
# COPY of Validation_2026/side_experiments/respec_2026-11/step_by_step/dest_pooled/pool_core.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import sys, time
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import torch
from torch.func import jvp
from scipy.optimize import minimize
from scipy.stats import chi2

FTOL = 1e-11      # pooled models: stop when the relative LL gain per iteration < 1e-11 (about 5e-7 in LL); the separate
                  # models used 1e-13, whose tail moved the pooled LL by < 0.001 over hundreds of iterations (first B1a attempt)
ABBR = {"SHOPPING": "S", "RECREATION": "R", "ACCOMPANY": "A", "OTHER": "O"}


def scaled(q):
    return not q.startswith("theta_")


class Structure:
    """share: dict param -> list of groups (tuples of purposes) sharing it; a purpose not in any group of the param keeps
    its own value."""
    def __init__(self, purposes, specs, share=None, fixed=None):
        self.P = list(purposes); self.specs = specs; self.share = {q: [tuple(g) for g in gs] for q, gs in (share or {}).items()}
        self.fixed = dict(fixed or {})

    def copy(self, add=None, fix=None, share=None, unfix=()):
        s = {q: list(gs) for q, gs in (self.share if share is None else share).items()}
        for q, g in (add or {}).items(): s.setdefault(q, []).append(tuple(g))
        f = {k: v for k, v in self.fixed.items() if k not in unfix}; f.update(fix or {})
        return Structure(self.P, self.specs, s, f)

    def has(self, p, q):
        return q in self.specs[p].params()

    def group_of(self, p, q):
        for g in self.share.get(q, []):
            if p in g: return g
        return None

    def gname(self, g, q):
        hold = [p for p in self.P if p in g and self.has(p, q)]
        return "shared" if hold == [p for p in self.P if self.has(p, q)] and len(hold) > 2 else "+".join(ABBR.get(p, p) for p in hold)

    def key(self, p, q):
        g = self.group_of(p, q)
        if g is None: return f"{p}|{q}"
        return f"{self.gname(g, q)}|{q}"

    def free_scales(self):
        parent = {p: p for p in self.P}
        def find(a):
            while parent[a] != a: a = parent[a]
            return a
        for q, gs in self.share.items():
            if not scaled(q): continue
            for g in gs:
                g = [p for p in g if self.has(p, q)]
                if g and self.fixed.get(self.key(g[0], q), 1.0) == 0.0: continue      # held at 0: does not identify a scale
                for a in g[1:]: parent[find(a)] = find(g[0])
        comp = {}
        for p in self.P: comp.setdefault(find(p), []).append(p)
        free = []
        for ps in comp.values():
            ref = "SHOPPING" if "SHOPPING" in ps else ps[0]
            free += [p for p in ps if p != ref]
        return [p for p in self.P if p in free]

    def names(self):
        out = []
        for p in self.P:
            for q in self.specs[p].params():
                k = self.key(p, q)
                if k not in out: out.append(k)
        return out + [f"scale|{p}" for p in self.free_scales()]

    def describe(self):
        return {q: [self.gname(g, q) for g in gs] for q, gs in self.share.items()}


def bound(name):
    q = name.split("|")[1]
    if name.startswith("scale|"): return (0.01, 50.0)
    return (-30.0, 15.0) if q.startswith("theta_") else (0.0, 3.0) if q == "mu_size" else (None, None)


class Engine:
    def __init__(self, purposes, specs, chunks, nrec, log=print):
        """chunks: dict p -> list of estimate_fullset_taz.Chunk built with specs[p]; nrec: dict p -> number of records"""
        self.P, self.specs, self.chunks, self.nrec, self.log = list(purposes), specs, chunks, nrec, log

    def maps(self, S, names):
        ix = {n: i for i, n in enumerate(names)}; out = {}
        for p in self.P:
            qs = self.specs[p].params()
            gi = torch.tensor([ix[S.key(p, q)] for q in qs]); sc = torch.tensor([scaled(q) for q in qs])
            mi = ix.get(f"scale|{p}", -1)
            out[p] = (gi, sc, mi)
        return out

    @staticmethod
    def local(t, m):
        gi, sc, mi = m; v = t[gi]
        if mi >= 0: v = torch.where(sc, v * t[mi], v)
        return v

    def local_x(self, S, x, p):
        names = S.names(); m = self.maps(S, names)[p]
        return self.local(torch.tensor([x[n] for n in names]), m).detach().numpy()

    def fit(self, S, x0, step, label):
        names = S.names(); K = len(names); mp = self.maps(S, names); t0 = time.time()
        bounds = [bound(n) for n in names]
        x0 = np.array([float(x0.get(n, np.nan)) for n in names])
        assert np.isfinite(x0).all(), [n for n, v in zip(names, x0) if not np.isfinite(v)]
        x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bounds)])
        def fg(v):
            t = torch.tensor(v, requires_grad=True); tot = 0.0
            for p in self.P:
                for c in self.chunks[p]:
                    l = -c.ll(self.local(t, mp[p]), self.specs[p]).sum(); l.backward(); tot += float(l.detach())
            if not np.isfinite(tot): return 1e15, np.zeros_like(v)
            return tot, t.grad.numpy().copy()
        r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bounds,
                     options=dict(maxiter=5000, maxfun=20000, ftol=1e-13, gtol=1e-6, maxcor=30))
        x = torch.tensor(r.x); H = torch.zeros((K, K)); G = []; LLp = {}
        for p in self.P:
            R = torch.unique(torch.cat([mp[p][0], torch.tensor([mp[p][2]] if mp[p][2] >= 0 else [], dtype=torch.long)]))
            s0 = x[R].clone(); spec = self.specs[p]; Gp = []; lp = 0.0
            def lp_rec(s, c):
                t = x.index_put((R,), s); return c.ll(self.local(t, mp[p]), spec)
            for c in self.chunks[p]:
                Hc = torch.autograd.functional.hessian(lambda s: lp_rec(s, c).sum(), s0)
                H[R.unsqueeze(1), R.unsqueeze(0)] += Hc
                sc = torch.stack([jvp(lambda s: lp_rec(s, c), (s0,), (e,))[1] for e in torch.eye(len(R))], 1)
                g = torch.zeros((sc.shape[0], K)); g[:, R] = sc; Gp.append(g)
                with torch.no_grad(): lp += float(lp_rec(s0, c).sum())
            G.append(torch.cat(Gp)); LLp[p] = lp
        G = torch.cat(G); g = G.sum(0)
        at_bound = [n for n, v, (lo, hi) in zip(names, r.x, bounds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
        free = torch.tensor([n not in at_bound for n in names]); cov = torch.full((K, K), float("nan"))
        try:
            Hi = torch.linalg.inv(-H[free][:, free])
        except Exception as e:
            self.log(f"  {step}: singular Hessian ({e})"); return None
        Gf = G[:, free]; fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
        for a, ia in enumerate(fi): cov[ia, fi] = cf[a]
        se = torch.sqrt(torch.clamp(torch.diag(cov), min=0))
        tab = pd.DataFrame({"param": names, "value": x.numpy(), "rob_se": se.numpy(), "rob_t": (x / se).numpy()})
        N = sum(self.nrec[p] for p in self.P); LL = -float(r.fun)
        res = dict(step=step, label=label, S=S, K=K, LL=LL, LLp=LLp, N=N, BIC=np.log(N) * K - 2 * LL, table=tab,
                   x=dict(zip(names, r.x)), converged=bool(r.success), maxgrad=float(g.abs().max()), at_bound=" ".join(at_bound),
                   cov=pd.DataFrame(cov.numpy(), index=names, columns=names))
        self.log(f"  {step} {label}: K {K} LL {LL:.2f} BIC {res['BIC']:.1f} converged {res['converged']} maxgrad {res['maxgrad']:.1e} "
                 f"({r.nit} it, {time.time() - t0:.0f} s)" + (f" at bound: {res['at_bound']}" if at_bound else ""))
        return res


# ------------------------------------------------------------------------------------------------ parallel engine
def worker(conn, fam, p, linear, base, comps, threads, part=0, nparts=1, mu_fixed=None):
    """one purpose (or part `part` of `nparts` of its chunks): builds its chunks (estimation half) once and answers fg / hess / val requests on LOCAL parameter vectors"""
    import os, sys, importlib
    sys.dont_write_bytecode = True
    os.environ["TAZ_THREADS"] = str(threads)
    for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"): os.environ[v] = str(threads)
    import torch as T_
    T_.set_num_threads(threads)
    F = importlib.import_module(fam)
    spec = F.M.Spec("pool", linear, base, comps, mu_fixed=mu_fixed); sk = F.C.skims()
    chunks, N = F.build(p, spec, sk=sk)
    chunks = [c for i, c in enumerate(chunks) if i % nparts == part]
    conn.send(("ready", sum(c.N for c in chunks)))
    while True:
        cmd, v = conn.recv()
        if cmd == "stop": break
        if cmd == "fg":
            t = T_.tensor(v, requires_grad=True); tot = 0.0
            for c in chunks:
                l = c.ll(t, spec).sum(); l.backward(); tot += float(l.detach())
            conn.send((tot, t.grad.numpy().copy()))
        elif cmd == "hess":
            x = T_.tensor(v); K = len(x); H = T_.zeros((K, K)); G = []; tot = 0.0
            for c in chunks:
                H += T_.autograd.functional.hessian(lambda s: c.ll(s, spec).sum(), x)
                G.append(T_.stack([jvp(lambda s: c.ll(s, spec), (x,), (e,))[1] for e in T_.eye(K)], 1))
                with T_.no_grad(): tot += float(c.ll(x, spec).sum())
            conn.send((tot, H.numpy(), T_.cat(G).numpy()))
        elif cmd == "val":
            if hasattr(F, "val_ll"): conn.send(F.val_ll(p, spec, np.asarray(v, float), sk)); continue
            rv, cv, gv = F.FS.load(F.SEG(p), "validation")
            h = F.X.heldout(rv, cv, gv, spec, np.asarray(v, float), p, sk, obs="mix")
            conn.send((float(h["LL"].sum()), len(rv)))


class ParEngine:
    """Purposes in worker processes (spawn), optimiser in the master.  Estimation parametrisation: a purpose-specific scaled
    coefficient is estimated as gamma = mu_p beta (so the scale enters only through the shared coefficients, which keeps the
    problem well conditioned); results are reported in V units (beta = gamma / mu_p, delta-method covariance)."""
    def __init__(self, fam, purposes, specs, threads=4, log=print, split=None):
        """split: dict purpose -> number of worker processes sharing its chunks (largest samples)"""
        import multiprocessing as mp
        torch.set_num_threads(1)                      # the master only maps parameters (idle OpenMP threads would spin)
        ctx = mp.get_context("spawn"); self.P, self.specs, self.log = list(purposes), specs, log; self.conn, self.proc = {}, {}
        split = split or {}
        for p in self.P:
            self.conn[p], self.proc[p] = [], []
            for k in range(split.get(p, 1)):
                a, b = ctx.Pipe()
                pr = ctx.Process(target=worker, args=(b, fam, p, specs[p].linear, specs[p].size_base, specs[p].size_comps, threads,
                                                      k, split.get(p, 1), getattr(specs[p], "mu_fixed", None)), daemon=True)
                pr.start(); self.conn[p].append(a); self.proc[p].append(pr)
        self.nrec = {}
        for p in self.P:
            ns = [c.recv()[1] for c in self.conn[p]]; self.nrec[p] = sum(ns); log(f"  worker(s) {p}: N {ns}")

    def close(self):
        for p in self.P:
            try: [c.send(("stop", None)) for c in self.conn[p]]
            except Exception: pass

    def maps(self, S, names):
        ix = {n: i for i, n in enumerate(names)}; out = {}
        for p in self.P:
            qs = self.specs[p].params()
            gi = torch.tensor([ix[S.key(p, q)] for q in qs])
            sc = torch.tensor([scaled(q) for q in qs])
            sh = torch.tensor([scaled(q) and S.group_of(p, q) is not None for q in qs])
            out[p] = (gi, sc, sh, ix.get(f"scale|{p}", -1))
        return out

    @staticmethod
    def loc_v(t, m):
        """V-unit global vector -> local (effective) parameters: every scaled parameter times mu_p"""
        gi, sc, sh, mi = m; v = t[gi]
        return torch.where(sc, v * t[mi], v) if mi >= 0 else v

    @staticmethod
    def loc_e(t, m):
        """estimation vector -> local: only shared scaled parameters times mu_p (purpose-specific ones are gamma already)"""
        gi, sc, sh, mi = m; v = t[gi]
        return torch.where(sh, v * t[mi], v) if mi >= 0 else v

    def ps_index(self, S, names):
        """index of each global purpose-specific scaled parameter -> index of its purpose's free scale"""
        ix = {n: i for i, n in enumerate(names)}; out = {}
        for n in names:
            g, q = n.split("|", 1)
            if g in self.P and scaled(q) and f"scale|{g}" in ix: out[ix[n]] = ix[f"scale|{g}"]
        return out

    def v2e(self, S, names, v):
        e = v.clone()
        for i, j in self.ps_index(S, names).items(): e[i] = v[i] * v[j]
        return e

    def e2v(self, S, names, e):
        ps = self.ps_index(S, names); v = e.clone()
        for i, j in ps.items(): v[i] = e[i] / e[j]
        return v

    def local_x(self, S, x, p):
        names = S.names(); m = self.maps(S, names)[p]
        return self.loc_v(torch.tensor([x[n] for n in names]), m).detach().numpy()

    def bounds(self, S, names):
        ps = self.ps_index(S, names); out = []
        for i, n in enumerate(names):
            lo, hi = bound(n)
            if i in ps and n.endswith("|mu_size"): hi = None      # gamma = mu_p mu_size: lower bound 0 only
            if n in S.fixed:
                assert i not in ps or S.fixed[n] == 0.0, n; lo = hi = float(S.fixed[n])
            out.append((lo, hi))
        return out

    def fit(self, S, x0, step, label):
        names = S.names(); K = len(names); mp_ = self.maps(S, names); t0 = time.time()
        bnds = self.bounds(S, names)
        v0 = torch.tensor([float(S.fixed[n]) if n in S.fixed else float(x0[n]) for n in names])
        e0 = self.v2e(S, names, v0).numpy()
        e0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(e0, bnds)])
        nev = [0]
        def fg(v):
            t = torch.tensor(v, requires_grad=True); locs = {p: self.loc_e(t, mp_[p]) for p in self.P}
            for p in self.P:
                for c in self.conn[p]: c.send(("fg", locs[p].detach().numpy()))
            tot = 0.0; acc = 0
            for p in self.P:
                for c in self.conn[p]:
                    l, g = c.recv(); tot += l; acc = acc + (locs[p] * torch.tensor(g)).sum()
            acc.backward(); nev[0] += 1
            if nev[0] % 100 == 0: print(f"    [{step}] evaluation {nev[0]}: LL {tot:.3f} ({time.time() - t0:.0f} s)", flush=True)
            if not np.isfinite(tot): return 1e15, np.zeros_like(v)
            return -tot, -t.grad.numpy().copy()
        r = minimize(fg, e0, jac=True, method="L-BFGS-B", bounds=bnds,
                     options=dict(maxiter=5000, maxfun=20000, ftol=FTOL, gtol=1e-6, maxcor=30))
        x = torch.tensor(r.x)
        # Hessian and scores: local blocks from the workers, chain rule to the estimation vector
        locs = {p: self.loc_e(x, mp_[p]).detach().numpy() for p in self.P}
        for p in self.P:
            for c in self.conn[p]: c.send(("hess", locs[p]))
        H = torch.zeros((K, K)); G = []; LLp = {}
        for p in self.P:
            parts = [c.recv() for c in self.conn[p]]
            LLp[p] = sum(q[0] for q in parts); Hl = torch.tensor(sum(q[1] for q in parts)); Gl = torch.tensor(np.concatenate([q[2] for q in parts]))
            J = torch.autograd.functional.jacobian(lambda t: self.loc_e(t, mp_[p]), x)          # K_p x K
            gl = Gl.sum(0)
            H2 = torch.autograd.functional.hessian(lambda t: (self.loc_e(t, mp_[p]) * gl).sum(), x)
            H += J.T @ Hl @ J + H2; G.append(Gl @ J)
        G = torch.cat(G); g = G.sum(0)
        at_bound = [n for n, v, (lo, hi) in zip(names, r.x, bnds) if n not in S.fixed and ((lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6))]
        free = torch.tensor([n not in at_bound and n not in S.fixed for n in names]); cov = torch.full((K, K), float("nan"))
        try:
            Hi = torch.linalg.inv(-H[free][:, free])
        except Exception as e:
            self.log(f"  {step}: singular Hessian ({e})"); return None
        Gf = G[:, free]; fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
        for a, ia in enumerate(fi): cov[ia, fi] = cf[a]
        g = g[torch.tensor([n not in S.fixed for n in names])]; K = K - sum(n in S.fixed for n in names)   # K: fixed parameters not counted
        # report in V units: beta = gamma / mu_p (delta method)
        Jv = torch.autograd.functional.jacobian(lambda e: self.e2v(S, names, e), x)
        covv = Jv @ torch.nan_to_num(cov) @ Jv.T
        nanrow = torch.isnan(torch.diag(cov)); covv[nanrow] = float("nan"); covv[:, nanrow] = float("nan")
        xv = self.e2v(S, names, x)
        se = torch.sqrt(torch.clamp(torch.diag(covv), min=0))
        tab = pd.DataFrame({"param": names, "value": xv.numpy(), "rob_se": se.numpy(), "rob_t": (xv / se).numpy()})
        N = sum(self.nrec[p] for p in self.P); LL = -float(r.fun)
        res = dict(step=step, label=label, S=S, K=K, LL=LL, LLp=LLp, N=N, BIC=np.log(N) * K - 2 * LL, table=tab,
                   x=dict(zip(names, xv.numpy())), converged=bool(r.success), maxgrad=float(g.abs().max()), at_bound=" ".join(at_bound),
                   cov=pd.DataFrame(covv.numpy(), index=names, columns=names))
        self.log(f"  {step} {label}: K {K} LL {LL:.2f} BIC {res['BIC']:.1f} converged {res['converged']} maxgrad {res['maxgrad']:.1e} "
                 f"({r.nit} it, {time.time() - t0:.0f} s)" + (f" at bound: {res['at_bound']}" if at_bound else ""))
        return res

    def validation(self, S, x):
        for p in self.P: self.conn[p][0].send(("val", self.local_x(S, x, p)))
        return {p: self.conn[p][0].recv() for p in self.P}


def lr_row(r, cur, decision, restriction=True):
    """restriction: LR = 2 (LL_cur - LL_r), df = K_cur - K_r"""
    d = dict(step=r["step"], label=r["label"], K=r["K"], LL=r["LL"], BIC=r["BIC"], LR=np.nan, df=np.nan, p=np.nan, decision=decision)
    if cur is not None:
        if restriction: lr = 2 * (cur["LL"] - r["LL"]); df = cur["K"] - r["K"]
        else: lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]
        d.update(LR=lr, df=df, p=float(chi2.sf(max(lr, 0), df)) if df > 0 else np.nan)
    return d


def coef_rows(r, step):
    """one row per parameter; a parameter held at 0 is left out, one held at another value (mu = 1) is kept without s.e."""
    out = []; fx = r["S"].fixed if "S" in r else {}
    for q in r["table"].itertuples():
        if fx.get(q.param, None) == 0.0: continue
        grp, par = q.param.split("|", 1)
        if grp == "scale": grp, par = par, "scale"
        out.append(dict(step=step, purpose=grp, param=par, coef=q.value, se=q.rob_se, t=q.rob_t))
    return out
