#!/usr/bin/env python3
"""Location-choice engine of the ABIT re-specification (2026-11-06): full choice set (1,588 zones), location mixture over the
survey's traffic zones (destinations) or tract-to-zone weights (other locations), chunked exact-gradient maximum likelihood,
robust sandwich covariance, hold-out log-likelihood and trip-length distribution.  Reuses the data and utility variables of
3_abit/tasha_estimation (records, configurations, dc_model.features), read only; adds the candidate zone attributes of
respec/abit/zone_extras.csv.

Specification object:  Spec(lin=[...utility columns...], base=<size base component>, comps=[...other size components...])
Parameter vector: beta (lin) + theta (comps, size weight exp(theta) relative to the base) + mu (ln size).
"""
import os, sys, time
import numpy as np
import pandas as pd
os.environ.setdefault("TAZ_THREADS", "5")
V = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026"
TE = f"{V}/3_abit/tasha_estimation"; RESPEC = f"{V}/side_experiments/respec_2026-11/abit"
sys.path.insert(0, TE)
import estimate_dc_taz as Z          # noqa: E402  (threads, wraps dc_model with the location mixture)
import dc_taz_engine as X            # noqa: E402
import dc_model as M                 # noqa: E402
import dc_common as C                # noqa: E402
from estimate_complexity import multi_flag   # noqa: E402
from rts_common import DIST_BINS             # noqa: E402
import torch                         # noqa: E402
from scipy.optimize import minimize  # noqa: E402

torch.set_num_threads(int(os.environ["TAZ_THREADS"]))
CHUNK = 250
EXTRA_ZONE = ["rail", "lnstopden"]
EXTRA_SIZE = ["leis", "hlth"]
ALL_COMPS = ["pop", "ret", "off", "oth", "stu", "leis", "hlth"]
_z_done = False


def zones_plus():
    global _z_done
    z = C.zones()
    if not _z_done:
        e = pd.read_csv(f"{RESPEC}/zone_extras.csv")
        assert (e.id.values == z.id.values).all()
        for c in EXTRA_ZONE + EXTRA_SIZE: z[c] = e[c].values.astype(float)
        for c in EXTRA_ZONE:
            if c not in M.ZONE_VARS: M.ZONE_VARS.append(c)
        _z_done = True
    return z


class Spec:
    def __init__(self, lin, base, comps):
        self.lin, self.base, self.comps = list(lin), base, list(comps)

    def params(self):
        return list(self.lin) + [f"theta_{c}" for c in self.comps] + ["mu_size"]

    def copy(self, lin=None, comps=None):
        return Spec(self.lin if lin is None else lin, self.base, self.comps if comps is None else comps)


# ------------------------------------------------------------------------------------------------ data
SEG_PUR = {"WORK_wbwork": "WORK", "WORK_wbhome": "WORK", "WORK_wahb": "WORK", "EDUCATION_nonstud": "EDUCATION",
           "EDUCATION_daycare": "EDUCATION", "OTHER_wbs": "OTHER"}


def load(seg, half):
    """records, destination candidates (rec, zidx, b) and anchor configurations (rec, home_idx, anchor_b, w) of a segment"""
    if seg.split("_")[1] in ("primary", "stop") and seg.split("_")[0] in C.DISC:
        rec, cand, cfg = Z.load_taz(half, seg)
        if seg.endswith("primary"): rec["multi"] = multi_flag(rec, half)
        else: rec["multi"] = 0.0
        return rec, cand, cfg
    import estimate_locations as L
    if seg == "OTHER_wbs":
        rec = pd.read_parquet(f"{TE}/work/wbs_dest_records_{half}.parquet"); cand = pd.read_parquet(f"{TE}/work/wbs_dest_cand_{half}.parquet")
        rec["home_idx"] = rec.home_zone_idx.astype(int); rec["kind"] = "primary"; rec["anchor_b"] = rec.anchor_b.astype(int)
        rec = rec.reset_index(drop=True)
    else:
        rec, cand = L.load(half, seg, "stop" if seg == "WORK_wbwork" else "primary")
    rec["multi"] = 0.0
    return rec, cand, X.single_cfg(rec)


class Chunk:
    def __init__(self, sub, cand, cfg, cols, pur, sk):
        alts, lnc, logb = M.full_sets(sub, cand)
        spec = M.Spec("ALL", cols, "pop", [c for c in ALL_COMPS if c != "pop"])
        D = X.MixData(sub, cfg, alts, lnc, logb, spec, pur, sk)
        b = D.base
        self.X = b.X.float(); self.S = b.S.float(); self.logb = b.logb; self.gidx, self.logw = D.gidx, D.logw
        self.N = D.N; self.rp = D.rp; self.rw = D.rw; self.orig = D.rows.home_idx.values.astype(np.int64)
        del D, b

    def V(self, theta, s, ix, sx):
        K = len(ix); C_ = len(sx) - 1
        beta = theta[:K]; th = theta[K:K + C_]; mu = theta[K + C_]
        w = torch.cat([torch.ones(1, dtype=theta.dtype), torch.exp(th)])
        lnS = torch.log1p((self.S[:, :, sx].double() * w).sum(-1))
        v = mu * lnS
        if K: v = v + self.X[:, :, ix].double() @ beta
        return v

    def Vc(self, theta, Xd, Sd):
        K = 0 if Xd is None else Xd.shape[-1]; C_ = Sd.shape[-1] - 1
        beta = theta[:K]; th = theta[K:K + C_]; mu = theta[K + C_]
        w = torch.cat([torch.ones(1, dtype=theta.dtype), torch.exp(th)])
        v = mu * torch.log1p((Sd * w).sum(-1))
        return v if Xd is None else v + Xd @ beta

    def llc(self, theta, Xd, Sd):
        v = self.Vc(theta, Xd, Sd)
        l = torch.logsumexp(v + self.logb, 1) - torch.logsumexp(v, 1)
        return torch.logsumexp(l[self.gidx] + self.logw, 1)

    def ll(self, theta, s, ix, sx):
        v = self.V(theta, s, ix, sx)
        l = torch.logsumexp(v + self.logb, 1) - torch.logsumexp(v, 1)
        return torch.logsumexp(l[self.gidx] + self.logw, 1)

    def ll0(self):
        l = torch.logsumexp(self.logb, 1) - np.log(self.logb.shape[1])
        return float(torch.logsumexp(l[self.gidx] + self.logw, 1).sum())


class SegData:
    """chunks of one half of a segment with every column in `cols` (float32)"""
    def __init__(self, seg, half, cols, sk):
        self.seg, self.half = seg, half
        self.pur = SEG_PUR.get(seg, seg.split("_")[0])
        rec, cand, cfg = load(seg, half); self.rec = rec
        self.cols = list(cols); t0 = time.time()
        self.chunks = [Chunk(rec.iloc[i:i + CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + CHUNK])], cfg, self.cols, self.pur, sk)
                       for i in range(0, len(rec), CHUNK)]
        self.N = len(rec); self.hh = rec.household_id.values; self.w = rec.w.values.astype(float)
        self._ll0 = None
        print(f"  data {seg} {half}: N {self.N}, {sum(len(c.rp) for c in self.chunks)} rows, {len(self.cols)} columns, {time.time() - t0:.0f} s", flush=True)

    def idx(self, spec):
        return [self.cols.index(c) for c in spec.lin], [ALL_COMPS.index(c) for c in [spec.base] + spec.comps]

    def ll0(self):
        if self._ll0 is None: self._ll0 = sum(c.ll0() for c in self.chunks)
        return self._ll0

    def subset(self, recs):
        """not used (bootstrap is linearised)"""
        raise NotImplementedError


BOUNDS = {"theta": (-30.0, 15.0), "mu": (0.0, 3.0)}


def bounds_of(names):
    return [BOUNDS["theta"] if p.startswith("theta_") else BOUNDS["mu"] if p == "mu_size" else (None, None) for p in names]


def cache(D, spec):
    ix, sx = D.idx(spec)
    return [(c.X[:, :, ix].double() if len(ix) else None, c.S[:, :, sx].double()) for c in D.chunks]


def fit(D, spec, x0=None, cov=True, maxiter=3000, tol=(1e-14, 1e-6)):
    """ML on the chunks of D.  x0: dict name -> start.  Returns dict(table, x, LL, K, N, cov, H, G, converged, at_bound)"""
    names = spec.params(); ix, sx = D.idx(spec)
    start = {"mu_size": 1.0}
    x0 = np.array([(x0 or {}).get(p, start.get(p, -2.0 if p.startswith("theta_") else 0.0)) for p in names], float)
    bnds = bounds_of(names)
    x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bnds)])
    t0 = time.time(); CA = cache(D, spec)

    def fg(v):
        t = torch.tensor(v, requires_grad=True); tot = 0.0
        for c, (Xd, Sd) in zip(D.chunks, CA):
            l = -c.llc(t, Xd, Sd).sum(); l.backward(); tot += float(l.detach())
        if not np.isfinite(tot): return 1e15, np.zeros_like(v)
        return tot, t.grad.numpy().copy()
    r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bnds, options=dict(maxiter=maxiter, maxfun=4 * maxiter, ftol=tol[0], gtol=tol[1], maxcor=30))
    x = torch.tensor(r.x); K = len(x); LL = -float(r.fun)
    at_bound = [p for p, v, (lo, hi) in zip(names, r.x, bnds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
    out = dict(spec=spec, names=names, x=r.x.copy(), LL=LL, K=K, N=D.N, converged=bool(r.success), nit=int(r.nit), at_bound=at_bound, time=time.time() - t0)
    print(f"      fit K {K}: LL {LL:.3f}, {r.nit} it, {time.time() - t0:.0f} s", flush=True)
    if cov: out.update(covariance(D, spec, r.x, at_bound, CA))
    del CA
    out["table"] = pd.DataFrame({"param": names, "value": r.x, "rob_se": out.get("se", np.full(K, np.nan)),
                                 "rob_t": r.x / out.get("se", np.full(K, np.nan))})
    return out


def scores(D, spec, x, CA=None):
    """per-record scores G (N x K) and Hessian H (K x K) at x"""
    from torch.func import jvp
    CA = CA or cache(D, spec); xt = torch.tensor(np.asarray(x, float)); K = len(xt)
    H = torch.zeros((K, K), dtype=torch.float64); G = []
    for c, (Xd, Sd) in zip(D.chunks, CA):
        H += torch.autograd.functional.hessian(lambda t: c.llc(t, Xd, Sd).sum(), xt)
        G.append(torch.stack([jvp(lambda t: c.llc(t, Xd, Sd), (xt,), (e,))[1] for e in torch.eye(K, dtype=torch.float64)], 1))
    return torch.cat(G).numpy(), H.numpy()


def covariance(D, spec, x, at_bound=(), CA=None):
    names = spec.params(); G, H = scores(D, spec, x, CA); K = len(names)
    free = np.array([p not in at_bound for p in names])
    cov = np.full((K, K), np.nan); covh = cov.copy()
    Hi = np.linalg.inv(-H[np.ix_(free, free)]); Gf = G[:, free]
    cov[np.ix_(free, free)] = Hi @ (Gf.T @ Gf) @ Hi; covh[np.ix_(free, free)] = Hi
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    try: cond = float(np.linalg.cond(-H[np.ix_(free, free)]))
    except Exception: cond = np.nan
    return dict(cov=cov, cov_hess=covh, se=se, G=G, H=H, free=free, cond=cond)


def heldout(D, spec, x):
    """per-record predictive LL (full set, mixture), predicted / observed trip-length distribution (DIST_BINS, trip weights),
    mean km (weighted) from the origin of the configuration"""
    ix, sx = D.idx(spec); th = torch.tensor(np.asarray(x, float)); sk = C.skims()
    nb = len(DIST_BINS) - 1; ll = []; hp = np.zeros(nb); ho = np.zeros(nb); kp = []; ko = []
    i0 = 0
    for c in D.chunks:
        with torch.no_grad():
            v = c.V(th, spec, ix, sx); P = torch.softmax(v, 1).numpy()
            l = (torch.logsumexp(v + c.logb, 1) - torch.logsumexp(v, 1))
            ll.append(torch.logsumexp(l[c.gidx] + c.logw, 1).numpy())
        B = np.exp(c.logb.numpy()); dist = sk["d"][c.orig].astype(np.float64)
        bins = np.clip(np.searchsorted(DIST_BINS, dist, side="right") - 1, 0, nb - 1)
        w = D.w[i0 + c.rp] * c.rw
        for k in range(nb):
            m = bins == k; hp[k] += float((w[:, None] * P * m).sum()); ho[k] += float((w[:, None] * B * m).sum())
        kpr = np.zeros(c.N); kob = np.zeros(c.N)
        np.add.at(kpr, c.rp, c.rw * (P * dist).sum(1)); np.add.at(kob, c.rp, c.rw * (B * dist).sum(1))
        kp.append(kpr); ko.append(kob); i0 += c.N
    LL = np.concatenate(ll); kp = np.concatenate(kp); ko = np.concatenate(ko)
    tp, to = hp / hp.sum(), ho / ho.sum()
    return dict(LL=LL, LL_sum=float(LL.sum()), LL_obs=float(LL.mean()), KS=float(np.max(np.abs(np.cumsum(tp) - np.cumsum(to)))),
                km_pred=float(np.average(kp, weights=D.w)), km_obs=float(np.average(ko, weights=D.w)), tld_pred=tp, tld_obs=to)


def within_corr(D, spec, x, cols, max_chunks=12):
    """within-choice-set (demeaned over the 1,588 zones) correlation of the utility columns `cols`, rows weighted by the
    configuration weight; the ln size term at the estimates is added as 'ln_size'.  A subsample of chunks."""
    ix, sx = D.idx(spec); K = len(spec.lin); C_ = len(sx) - 1
    w_ = np.concatenate([[1.0], np.exp(np.asarray(x)[K:K + C_])])
    acc = None; n = 0.0
    for c in D.chunks[:max_chunks]:
        Xc = c.X[:, :, [D.cols.index(k) for k in cols]].numpy().astype(np.float64)
        lnS = np.log1p((c.S[:, :, sx].numpy().astype(np.float64) * w_).sum(-1))
        A = np.concatenate([Xc, lnS[..., None]], -1)
        A = A - A.mean(1, keepdims=True); rw = c.rw[:, None, None]
        m = (A * rw).reshape(-1, A.shape[-1]); a2 = A.reshape(-1, A.shape[-1])
        cv = m.T @ a2; acc = cv if acc is None else acc + cv; n += float(c.rw.sum() * A.shape[1])
    cov = acc / n; sd = np.sqrt(np.diag(cov)); keep = sd > 1e-12; nm = cols + ["ln_size"]
    R = cov[np.ix_(keep, keep)] / np.outer(sd[keep], sd[keep]); nm = [a for a, k in zip(nm, keep) if k]
    try: vif = np.diag(np.linalg.inv(R))
    except np.linalg.LinAlgError: vif = np.diag(np.linalg.pinv(R))
    return pd.DataFrame(R, index=nm, columns=nm), pd.Series(vif, index=nm)


def onestep_bootstrap(fitres, hh, B=200, seed=11):
    """linearised household-cluster bootstrap: theta*_b = theta + (-H)^-1 sum_n (m_{b,c(n)} - 1) g_n, clusters drawn with
    replacement.  Returns the bootstrap s.e. per parameter (NaN for parameters at a bound)."""
    G, H, free = fitres["G"], fitres["H"], fitres["free"]
    Hi = np.linalg.inv(-H[np.ix_(free, free)]); Gf = G[:, free]
    u, inv = np.unique(hh, return_inverse=True); Gc = np.zeros((len(u), Gf.shape[1])); np.add.at(Gc, inv, Gf)
    rng = np.random.default_rng(seed); draws = []
    for _ in range(B):
        m = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u)).astype(float) - 1.0
        draws.append(Hi @ (m @ Gc))
    se = np.full(len(free), np.nan); se[free] = np.std(np.array(draws), axis=0, ddof=1)
    return se


def cluster_se(fitres, hh):
    """household-cluster sandwich s.e."""
    G, H, free = fitres["G"], fitres["H"], fitres["free"]
    Hi = np.linalg.inv(-H[np.ix_(free, free)]); u, inv = np.unique(hh, return_inverse=True)
    Gc = np.zeros((len(u), int(free.sum()))); np.add.at(Gc, inv, G[:, free])
    se = np.full(len(free), np.nan); se[free] = np.sqrt(np.clip(np.diag(Hi @ (Gc.T @ Gc) @ Hi), 0, None))
    return se


class Pooled:
    """both halves as one sample (for the LR test of equal coefficients)"""
    def __init__(self, A, B):
        self.chunks = A.chunks + B.chunks; self.cols = A.cols; self.N = A.N + B.N
        self.hh = np.concatenate([A.hh, B.hh]); self.w = np.concatenate([A.w, B.w]); self.idx = A.idx
