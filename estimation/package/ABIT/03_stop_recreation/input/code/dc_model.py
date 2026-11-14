#!/usr/bin/env python3
"""Multinomial-logit destination choice: choice-set sampling, utility variables, maximum-likelihood estimation (PyTorch, exact
gradients and Hessian, robust sandwich covariance) and full-choice-set prediction.  estimate_dc.py runs the specification
search with this engine and re-estimates every final model with Biogeme (estimate_dc.biogeme_estimate), whose estimates are
the reported ones; validate_dc.py and pipeline/accessibility.py use the prediction functions.

Utility of zone j for observation n (segment = purpose x primary/stop):
    V_nj = mu ln(1 + S_j) + sum_k beta_k x_njk ,      S_j = x_j,base + sum_c exp(theta_c) x_jc
size components c of {pop, ret, off, oth, stu} (dc_common.zones), base component with weight 1 (purpose-specific).
Likelihood of an observation with destination tract t (measurement weights b_zt, prep_dc_data.py):
    sampled set D_n:  L_n = sum_{z in C_n} b_zt exp(V_nz + ln(k_nz / q_nz)) / sum_{j in D_n} exp(V_nj + ln(k_nj / q_nj))
    full set:         L_n = sum_z b_zt P_n(z),  P_n(z) = exp(V_nz) / sum_j exp(V_nj)
with importance sampling (McFadden 1978): R draws with replacement from q_nj (size x exp(-distance / D0) mixed with 10 %
uniform), k_nj = number of draws (+1 for the candidate zones of the observed tract, which are always included).
"""
# COPY of Validation_2026/3_abit/destination_choice/dc_model.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import numpy as np
import pandas as pd
import torch
import dc_common as C

torch.set_default_dtype(torch.float64)
SIZE_COMPS = ["pop", "ret", "off", "oth", "stu"]
SAMPLING_SIZE = {"SHOPPING": {"ret": 1.0, "pop": 0.1}, "OTHER": {"pop": 1.0, "ret": 1.0, "off": 1.0, "oth": 1.0},
                 "RECREATION": {"pop": 1.0, "ret": 0.75, "off": 0.25, "oth": 0.25}, "ACCOMPANY": {"pop": 1.0, "stu": 1.0},
                 "WORK": {"ret": 1.0, "off": 1.0, "oth": 1.0}}       # the attraction of the former gravity model (dest_attraction.csv)
INTERACT = ["inc0", "inc2", "car0", "car1", "child", "kid", "senior", "worker", "am", "pm", "ev", "nonauto", "worktour", "inbound", "multi"]
ZONE_VARS = ["bc", "dcz", "va", "othst", "cbd", "lnretden", "mix"]


# ------------------------------------------------------------------------------------------------ chooser attributes
def chooser(rec):
    r = rec
    a = dict(inc0=(r.inc_cls == 0), inc2=(r.inc_cls == 2), car0=(r.car_cls == 0), car1=(r.car_cls == 1), child=(r.children > 0),
             kid=(r.age < 18), senior=(r.age >= 65), worker=(r.occ == 1), am=(r.tod == 0), pm=(r.tod == 2), ev=(r.tod == 3),
             nonauto=(r.mode_auto < 0.5) & (r.kind == "stop"), worktour=r.tour_purpose.isin(["WORK", "EDUCATION"]) & (r.kind == "stop"),
             inbound=(r.position == "in"),
             # 2026-10-23 (TASHA finalisation): primary destination of a tour with at least one stop (column multi; 0 when absent)
             multi=(r.multi > 0) if "multi" in r else np.zeros(len(r), bool))
    return {k: np.asarray(v, float) for k, v in a.items()}


def person(rec):
    return dict(age=rec.age.values.astype(float), male=rec.male.values.astype(float), lic=rec.lic.values.astype(float),
                hhsize=rec.hhsize.values.astype(float), autos=rec.autos.values.astype(float), inc_month=rec.inc_month.values.astype(float))


# ------------------------------------------------------------------------------------------------ variables
def impedance(rec, alts, sk):
    """(primary) distance from home, (stop) detour via j relative to the direct path between the two anchors."""
    o = rec.home_idx.values[:, None]
    if (rec.kind.values == "stop").all():
        b = rec.anchor_b.values[:, None]
        dt = sk["d"][o, alts] + sk["d"][alts, b] - sk["d"][o, b]
        return np.maximum(dt, 0.0).astype(np.float64)
    return sk["d"][o, alts].astype(np.float64)


def features(rec, alts, names, sk, purpose):
    """N x J arrays of the requested variables (names as in MarylandDestinationChoice.variable)."""
    z = C.zones(); o = rec.home_idx.values; stop = (rec.kind.values == "stop").all()
    out = {}; cache = {}
    def imp():
        if "imp" not in cache: cache["imp"] = impedance(rec, alts, sk)
        return cache["imp"]
    ch = None
    for nm in names:
        if nm in out: continue
        if nm.startswith("d_") or nm.startswith("dt_"):
            knots = C.DKNOTS if stop else C.KNOTS
            pre = "dt" if stop else "d"
            for n2, v in zip(C.pw_names(pre, knots), C.pw(imp(), knots)): out[n2] = v
            if nm not in out: raise KeyError(nm)
        elif nm in ("d", "dt"): out[nm] = imp()
        elif nm in ("lnd", "lndt"): out[nm] = np.log(imp()) if not stop else np.log1p(imp())
        elif nm.startswith("lnd_") or nm.startswith("lndt_"):
            base, x = nm.split("_", 1)
            if ch is None: ch = chooser(rec)
            out[nm] = (np.log(imp()) if not stop else np.log1p(imp())) * ch[x][:, None]
        elif nm == "ctime":
            if stop:
                b = rec.anchor_b.values[:, None]; oo = o[:, None]
                out[nm] = np.maximum(sk["t"][oo, alts] + sk["t"][alts, b] - sk["t"][oo, b], 0.0).astype(np.float64)
            else: out[nm] = sk["t"][o[:, None], alts].astype(np.float64)
        elif nm == "cgt":
            im = rec.inc_month.values.astype(float)
            if stop:
                b = rec.anchor_b.values
                g1 = C.car_gt(o, alts, im, sk); g2 = C.car_gt(alts, np.broadcast_to(b[:, None], alts.shape), im, sk); g0 = C.car_gt(o, b[:, None], im, sk)
                out[nm] = np.maximum(g1 + g2 - g0, 0.0)
            else: out[nm] = C.car_gt(o, alts, im, sk)
        elif nm == "ls":
            mp = purpose if purpose in C.DISC + ["WORK"] else "OTHER"
            p = person(rec)
            if stop:
                b = rec.anchor_b.values
                l1 = C.mode_logsum(mp, o, alts, p, sk)
                # logsum from j to the second anchor: origin j varies -> evaluate per alternative column
                l2 = np.empty_like(l1)
                for jj in range(alts.shape[1]):
                    l2[:, jj] = C.mode_logsum(mp, alts[:, jj], b[:, None], p, sk)[:, 0]
                l0 = C.mode_logsum(mp, o, b[:, None], p, sk)
                out[nm] = l1 + l2 - l0
            else: out[nm] = C.mode_logsum(mp, o, alts, p, sk)
        elif nm == "intra": out[nm] = (alts == o[:, None]).astype(float)
        elif nm == "intra_a": out[nm] = (alts == o[:, None]).astype(float)
        elif nm == "intra_b": out[nm] = (alts == rec.anchor_b.values[:, None]).astype(float)
        elif nm in ZONE_VARS: out[nm] = z[nm].values[alts].astype(float)
        elif nm == "xcounty":
            cz = z.countyfips.values
            x = cz[alts] != cz[o][:, None]
            if stop: x &= cz[alts] != cz[rec.anchor_b.values][:, None]
            out[nm] = x.astype(float)
        elif nm == "xstate":
            st = z.state.values; x = st[alts] != st[o][:, None]
            if stop: x &= st[alts] != st[rec.anchor_b.values][:, None]
            out[nm] = x.astype(float)
        elif nm == "ptav_car0":
            if ch is None: ch = chooser(rec)
            out[nm] = (sk["bus"][o[:, None], alts] < 120).astype(float) * ch["car0"][:, None]
        elif nm == "ptav":
            out[nm] = (sk["bus"][o[:, None], alts] < 120).astype(float)
        else: raise KeyError(nm)
    return {k: out[k] for k in names}


def size_arrays(alts, comps):
    z = C.zones(); return {c: z[c].values[alts].astype(float) for c in comps}


# ------------------------------------------------------------------------------------------------ sampling
def sample_sets(rec, cand, purpose, R=40, seed=2026, protocol="importance", sk=None, D0=None):
    """Sampled choice sets: alts (N x J, -1 = padding), lncorr (ln k/q), logb (ln b for candidate zones, -inf else)."""
    sk = sk or C.skims(); z = C.zones(); nz = len(z); rng = np.random.default_rng(seed)
    N = len(rec); stop = (rec.kind.values == "stop").all()
    w = SAMPLING_SIZE.get(purpose, SAMPLING_SIZE["OTHER"]); s0 = sum(v * z[k].values for k, v in w.items()) + 1.0
    D0 = D0 or (3.0 if stop else 6.0)
    cg = cand.groupby("rec")
    cz = {r: (g.zidx.values, g.b.values) for r, g in cg}
    rows = []
    for i0 in range(0, N, 2000):
        sub = rec.iloc[i0:i0 + 2000]; allz = np.broadcast_to(np.arange(nz), (len(sub), nz))
        if protocol == "importance":
            dd = impedance(sub, allz, sk)
            q = s0[None, :] * np.exp(-dd / D0); q /= q.sum(1, keepdims=True); q = 0.9 * q + 0.1 / nz
        else:
            q = np.full((len(sub), nz), 1.0 / nz)
        cum = np.cumsum(q, 1)
        for k in range(len(sub)):
            r = sub.rec.values[k]
            dr = np.minimum(np.searchsorted(cum[k], rng.random(R) * cum[k, -1]), nz - 1)
            u, cnt = np.unique(dr, return_counts=True)
            cz_, cb = cz[r]
            kk = dict(zip(u.tolist(), cnt.tolist()))
            for zz in cz_: kk[int(zz)] = kk.get(int(zz), 0) + 1
            al = np.array(list(kk.keys())); kc = np.array(list(kk.values()), float)
            bb = np.zeros(len(al)); bmap = dict(zip(cz_.tolist(), cb.tolist()))
            for t_, a_ in enumerate(al): bb[t_] = bmap.get(int(a_), 0.0)
            rows.append((al, np.log(kc / (R * q[k, al])) if protocol == "importance" else np.zeros(len(al)), bb))
    J = max(len(r[0]) for r in rows)
    alts = np.full((N, J), -1, dtype=np.int64); lnc = np.zeros((N, J)); logb = np.full((N, J), -np.inf)
    for i, (al, lc, bb) in enumerate(rows):
        alts[i, :len(al)] = al; lnc[i, :len(al)] = lc
        with np.errstate(divide="ignore"): logb[i, :len(al)] = np.log(bb)
    return alts, lnc, logb


def full_sets(rec, cand):
    """Full choice set (all 1,588 zones): alts N x 1588, lncorr 0, logb from the candidates."""
    nz = len(C.zones()); N = len(rec)
    alts = np.broadcast_to(np.arange(nz), (N, nz)).copy(); logb = np.full((N, nz), -np.inf)
    pos = pd.Series(np.arange(N), index=rec.rec.values)
    with np.errstate(divide="ignore"): logb[pos.loc[cand.rec.values].values, cand.zidx.values] = np.log(cand.b.values)
    return alts, np.zeros((N, nz)), logb


# ------------------------------------------------------------------------------------------------ model
class Spec:
    def __init__(self, name, linear, size_base, size_comps=(), fix=None, mu_fixed=None, note=""):
        self.name, self.linear, self.size_base, self.size_comps = name, list(linear), size_base, list(size_comps)
        self.fix = dict(fix or {}); self.mu_fixed = mu_fixed; self.note = note

    def params(self):
        p = list(self.linear) + [f"theta_{c}" for c in self.size_comps]
        if self.mu_fixed is None: p.append("mu_size")
        return p


class Data:
    """Tensors of one estimation sample."""
    def __init__(self, rec, alts, lnc, logb, spec, purpose, sk):
        self.N, self.J = alts.shape
        pad = alts < 0; a = np.where(pad, 0, alts)
        F = features(rec, a, spec.linear, sk, purpose) if spec.linear else {}
        self.X = torch.tensor(np.stack([F[k] for k in spec.linear], -1)) if spec.linear else torch.zeros((self.N, self.J, 0))
        comps = [spec.size_base] + spec.size_comps
        S = size_arrays(a, comps); self.S = torch.tensor(np.stack([S[c] for c in comps], -1))
        self.lnc = torch.tensor(np.where(pad, -np.inf, lnc)); self.logb = torch.tensor(np.where(pad, -np.inf, logb))


def utility(theta, spec, D):
    K = len(spec.linear); C_ = len(spec.size_comps)
    beta = theta[:K]; th = theta[K:K + C_]
    mu = theta[K + C_] if spec.mu_fixed is None else torch.tensor(float(spec.mu_fixed))
    w = torch.cat([torch.ones(1), torch.exp(th)])
    lnS = torch.log1p((D.S * w).sum(-1))
    V = mu * lnS
    if K: V = V + D.X @ beta
    return V


def ll_obs(theta, spec, D):
    V = utility(theta, spec, D) + D.lnc
    return torch.logsumexp(V + D.logb, 1) - torch.logsumexp(V, 1)


def start_values(spec):
    x = []
    for p in spec.params():
        if p == "mu_size": x.append(0.8)
        elif p.startswith("theta_"): x.append(-2.0)
        elif p in ("d_0_1", "dt_0_1"): x.append(-0.5)
        elif p.startswith("d_") or p.startswith("dt_") or p in ("d", "dt"): x.append(-0.1)
        else: x.append(0.0)
    return torch.tensor(x)


def estimate(spec, D, x0=None, maxiter=3000):
    """ML estimate (scipy L-BFGS-B on the exact torch gradient; log size weights bounded to [-30, 15], mu to [0, 3])."""
    from scipy.optimize import minimize
    names = spec.params(); sv = start_values(spec).numpy()
    if isinstance(x0, dict): x0 = np.array([x0.get(p, v) for p, v in zip(names, sv)])
    else: x0 = x0.clone().numpy() if x0 is not None else sv
    bounds = [(-30.0, 15.0) if p.startswith("theta_") else (0.0, 3.0) if p == "mu_size" else (None, None) for p in names]
    x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bounds)])
    def fg(v):
        t = torch.tensor(v, requires_grad=True); l = -ll_obs(t, spec, D).sum()
        if not torch.isfinite(l): return 1e15, np.zeros_like(v)
        l.backward(); return float(l), t.grad.numpy().copy()
    r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bounds, options=dict(maxiter=maxiter, maxfun=4 * maxiter, ftol=1e-13, gtol=1e-6, maxcor=30))
    x = torch.tensor(r.x)
    f = lambda t: ll_obs(t, spec, D).sum()
    H = torch.autograd.functional.hessian(f, x)
    # per-observation gradients (N x K) by forward mode, one parameter at a time (memory: one N x J pass)
    from torch.func import jvp
    G = torch.stack([jvp(lambda t: ll_obs(t, spec, D), (x,), (e,))[1] for e in torch.eye(len(x))], 1)
    LL = float(f(x)); g = G.sum(0)
    at_bound = [p for p, v, (lo, hi) in zip(names, r.x, bounds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
    free = torch.tensor([p not in at_bound for p in names]); K = len(x)
    cov = torch.full((K, K), float("nan")); covc = cov.clone()
    try:
        Hi = torch.linalg.inv(-H[free][:, free]); Gf = G[:, free]
        fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
        for a, ia in enumerate(fi):
            cov[ia, fi] = cf[a]; covc[ia, fi] = Hi[a]
    except Exception:
        pass
    names = spec.params()
    se = torch.sqrt(torch.clamp(torch.diag(cov), min=0)); sec = torch.sqrt(torch.clamp(torch.diag(covc), min=0))
    tab = pd.DataFrame({"param": names, "value": x.numpy(), "rob_se": se.numpy(), "rob_t": (x / se).numpy(), "se": sec.numpy()})
    sd = np.sqrt(np.clip(np.diag(cov.numpy()), 1e-300, None)); corr = cov.numpy() / np.outer(sd, sd)
    return dict(spec=spec, x=x, LL=LL, K=len(x), N=D.N, table=tab, cov=cov.numpy(), corr=pd.DataFrame(corr, index=names, columns=names),
                maxgrad=float(g.abs().max()), converged=bool(r.success), message=str(r.message), at_bound=at_bound)


def ll_zero(D):
    lnc = D.lnc
    return float((torch.logsumexp(lnc + D.logb, 1) - torch.logsumexp(lnc, 1)).sum())


# ------------------------------------------------------------------------------------------------ full-set prediction
def predict_full(rec, cand, spec, xvals, purpose, sk, chunk=1500, extra=None):
    """Iterate over chunks: yields (sub-records, P (n x 1588), logb (n x 1588)) under the full choice set."""
    theta = torch.tensor(np.asarray(xvals, float))
    for i0 in range(0, len(rec), chunk):
        sub = rec.iloc[i0:i0 + chunk]; cs = cand[cand.rec.isin(sub.rec.values)]
        alts, lnc, logb = full_sets(sub, cs)
        D = Data(sub, alts, lnc, logb, spec, purpose, sk)
        with torch.no_grad():
            V = utility(theta, spec, D); P = torch.softmax(V, 1).numpy()
        yield sub, P, logb
