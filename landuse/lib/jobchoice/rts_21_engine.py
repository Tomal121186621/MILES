#!/usr/bin/env python3
"""Estimation engine of the extended RTS workplace choice (rts_22_stepwise.py, rts_23_diagnostics.py, rts_24_final_checks.py).

Likelihood: version 2 exactly (rts_13_estimate_v2.py): records of rts_11_data_v2.py, location mixture over up to 3 home zones and
4 possible work zones, entries = the possible work zones + 99 zones drawn with q_j proportional to jobs_j exp(-0.05 t) from the most
likely home zone (seed 20261027; a second draw uses 20261028), correction -ln q, size term mu ln(sum_k e^g_k N_jk), DC-home x state
term fixed at 0.  The logsum enters as b_ls * ls * (1 - car1) + c1 * ls * car1, where c1 = 1 (the V2c constraint) or a free
coefficient ('free_car1').  Utility terms are 'base*var*...' strings:
  bases  t, lt, ls, intra, cs, cc, dc, reg_<r> (rts_common); piecewise time t1 = min(t,15), t2 = 15..30, t3 = 30..45, t4 = above 45
         (each the minutes inside the band); zone attributes of the workplace (rts_20_zone_attrs.py): hiearn, ba, young_sh, off_sh,
         ret_sh, ind_sh, lnden, core_w, rural_w
  vars   female, young, old, kids, w2, car0, car1, notcar1, g1, g3, g4, hva (rts_common), lic (driving licence, RTS license = 1),
         hhs (household size), rurh (home zone rural, area type 40; depends on the home zone of the slot)
Maximisation: analytic gradient, L-BFGS-B (Biogeme's optimiser did not converge on this likelihood, ESTIMATION_REPORT_RTS.md
section 12); robust sandwich covariance from analytic per-record scores and a central-difference Hessian of the gradient."""
import os, sys, numpy as np, pandas as pd
from scipy.optimize import minimize
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import rts_common as R   # noqa: E402
import rts_13_estimate_v2 as E2   # noqa: E402
z = R.zones(); az = E2.az; st = z.state.values; ct = z.county.values; TT = R.tt().astype(float); NZ = len(z)
ZA = pd.read_parquet(f"{R.W}/zone_attrs_v2x.parquet").set_index("zone").reindex(z.zone.values)
ZATTR = {"hiearn": ZA.hiearn.values, "ba": ZA.ba.values, "young_sh": ZA.young_sh.values, "off_sh": ZA.off_sh.values, "ret_sh": ZA.ret_sh.values,
         "ind_sh": ZA.ind_sh.values, "lnden": ZA.lnden.values, "core_w": ZA.core.values, "rural_w": ZA.rural.values}
RURAL = ZA.rural.values
# wage-proxy check (rts_26): the high-wage share outside DC only, and inside DC only
ZATTR["hiearn_nodc"] = ZA.hiearn.values * (st != 11); ZATTR["hiearn_dc"] = ZA.hiearn.values * (st == 11)
_lic = None
def lic_of(pid):
    global _lic
    if _lic is None:
        r = pd.read_csv(f"{R.ABIT_HOME}/input/rts/RTS_raw_flat_data.csv", usecols=["person_id", "license"], low_memory=False).drop_duplicates("person_id")
        _lic = r.set_index("person_id").license
    return (pid.map(_lic) == 1).astype(float).values

V2C = [t for t in E2.TERMS if t not in ("ls", "ls*car1")] + ["ls*notcar1"]   # V2c in this parameterisation (offset ls*car1, coefficient 1)


def pvar(name, P, rec, h):
    if name == "lic": return P.lic.values[rec].astype(float)
    if name == "hhs": return P.hhsize.values[rec].astype(float)
    if name == "rurh": return RURAL[h].astype(float)
    if name == "notcar1": return (P.car_seg.values[rec] != 1).astype(float)
    return R.pvar(name, P, rec, P.g.values[rec])


def base(name, h, A, P, rec):
    if name in ZATTR: return ZATTR[name][A].astype(float)
    if name == "t": return TT[h[:, None], A]
    if name == "lt": return np.log1p(TT[h[:, None], A])
    if name in ("t1", "t2", "t3", "t4"):
        t = TT[h[:, None], A]; lo = {"t1": 0, "t2": 15, "t3": 30, "t4": 45}[name]; hi = {"t1": 15, "t2": 30, "t3": 45, "t4": 1e9}[name]
        return np.clip(t - lo, 0, hi - lo)
    return R.base_feat(name, h, A, P, rec, P.g.values[rec])


def feat(spec, h, A, P, rec):
    p = spec.split("*"); x = base(p[0], h, A, P, rec)
    for q in p[1:]: x = x * pvar(q, P, rec, h)[:, None]
    return x


class Data:
    """estimation-half design: entries, corrections, availabilities, location weights"""
    def __init__(self, half="estimation", seed=20261027):
        P, (Hz4, Hw4), (Wz, Ww) = E2.persons_v2(half); P["lic"] = lic_of(P.person_id)
        self.P, self.Hz4, self.Hw4, self.Wz, self.Ww = P, Hz4, Hw4, Wz, Ww; N = len(P); self.N = N
        Hz = Hz4[:, :E2.HS].copy(); Hw = Hw4[:, :E2.HS].copy(); Hw /= Hw.sum(axis=1, keepdims=True)
        for k in range(1, E2.HS): Hz[:, k] = np.where(Hw[:, k] > 0, Hz[:, k], Hz[:, 0])
        self.Hz, self.Hw = Hz, Hw
        q, D = E2.design(P, Hz, seed); pos = np.full(NZ, -1); pos[az] = np.arange(len(az))
        self.A = np.concatenate([np.where(Wz >= 0, Wz, Wz[:, :1]), az[D]], axis=1); self.corr = -np.log(q[np.arange(N)[:, None], pos[self.A]])
        self.av = np.ones(self.A.shape); self.av[:, :E2.NC] = (Wz >= 0); self.NK = np.stack([z[s].values[self.A] for s in R.SEC]).astype(float)
        self.cache = {}

    def X(self, spec):
        if spec not in self.cache:
            rec = np.arange(self.N)
            self.cache[spec] = np.stack([feat(spec, self.Hz[:, h], self.A, self.P, rec) for h in range(E2.HS)]).astype(np.float32)
        return self.cache[spec]


SIZE_K = {"OFF": 1, "IND": 2, "OTH": 3}   # job types of the size term (retail = 0, the reference)


class Model:
    """size_inter: person-specific size weights (coordinator 2026-10-28): size_nj = sum_k exp(g_k + h_k' x_n) N_jk, given as a list of
    'TYPE:var' (TYPE in OFF, IND, OTH; var a person variable); parameters h_TYPEXvar."""
    def __init__(self, D, terms, free_car1=False, size_inter=()):
        self.D, self.terms, self.free_car1, self.size_inter = D, list(terms), free_car1, list(size_inter)
        self.names = (["mu_size", "g_OFF", "g_IND", "g_OTH"] + [f"b_{t.replace('*', 'X')}" for t in self.terms] + (["c_lsXcar1"] if free_car1 else [])
                      + [f"h_{s.replace(':', 'X')}" for s in self.size_inter])
        self.Xs = np.stack([D.X(t) for t in self.terms]); self.off = D.X("ls*car1")
        rec = np.arange(D.N); self.SX = np.stack([pvar(s.split(":")[1], D.P, rec, D.Hz[:, 0]) for s in self.size_inter]) if self.size_inter else np.zeros((0, D.N))
        self.SK = np.array([SIZE_K[s.split(":")[0]] for s in self.size_inter], int)

    def _ew(self, th):
        """person-specific type weights exp(g_k + h_k' x_n): array 3 x N"""
        K = len(self.terms); i0 = 4 + K + (1 if self.free_car1 else 0); h = th[i0:]
        lw = np.repeat(th[1:4][:, None], self.D.N, axis=1)
        for j, k in enumerate(self.SK): lw[k - 1] += h[j] * self.SX[j]
        return np.exp(lw)

    def _V(self, th):
        D = self.D; mu = th[0]; K = len(self.terms); ew = self._ew(th)
        Sz = D.NK[0] + ew[0][:, None] * D.NK[1] + ew[1][:, None] * D.NK[2] + ew[2][:, None] * D.NK[3]; lnS = np.log(Sz + 1e-9)
        c1 = th[4 + K] if self.free_car1 else 1.0
        V = mu * lnS[None] + D.corr[None] + np.tensordot(th[4:4 + K], self.Xs, axes=1) + c1 * self.off
        return V, lnS, Sz, ew

    def scores(self, th):
        """per-record log-likelihood and scores, in log space (log-sum-exp): log num_h = lse_c(log w_c + V_hc) over the possible work
        zones, log den_h = lse_k V_hk over all entries, log L = lse_h(log w_h + log num_h - log den_h); no underflow to L = 0"""
        D = self.D; V, lnS, Sz, ew = self._V(th); NC = E2.NC; K = len(self.terms)
        V = np.where(D.av[None] > 0, V, -np.inf)
        m = V.max(axis=2, keepdims=True); lden = m[..., 0] + np.log(np.exp(V - m).sum(axis=2))                 # HS x N
        with np.errstate(divide="ignore"): lwc = np.log(D.Ww)[None] + V[:, :, :NC]                             # -inf for padded candidates
        mc = lwc.max(axis=2, keepdims=True); lnum = mc[..., 0] + np.log(np.exp(lwc - mc).sum(axis=2))
        with np.errstate(divide="ignore"): la = np.log(D.Hw.T) + lnum - lden                                    # log(w_h P_h); -inf for unused slots
        ma = la.max(axis=0); lL = ma + np.log(np.exp(la - ma).sum(axis=0)); self.n_bad = int((~np.isfinite(lL)).sum())
        p = np.exp(V - lden[..., None]); rc = np.zeros_like(p); rc[:, :, :NC] = np.exp(lwc - lnum[..., None])
        dW = np.exp(la - lL)[..., None] * (rc - p)
        L = np.exp(lL)
        s_b = np.einsum("khnj,hnj->nk", self.Xs, dW); s_mu = (dW * lnS[None]).sum(axis=(0, 2))
        dWs = dW.sum(axis=0)                                                   # N x J (lnS does not depend on the home slot)
        dk = [(dWs * (th[0] * ew[k][:, None] * D.NK[k + 1] / (Sz + 1e-9))).sum(axis=1) for k in range(3)]
        s_g = np.stack(dk, 1)
        S = [s_mu[:, None], s_g, s_b]
        if self.free_car1: S.append(np.einsum("hnj,hnj->n", self.off, dW)[:, None])
        if self.size_inter: S.append(np.stack([dk[k - 1] * self.SX[j] for j, k in enumerate(self.SK)], 1))
        return lL, np.concatenate(S, axis=1)

    def f(self, th):
        ll, S = self.scores(th); return -ll.sum(), -S.sum(0)

    def fit(self, th0=None, maxiter=4000):
        if th0 is None: th0 = np.r_[0.9, 1.0, 0.2, 0.2, np.zeros(len(self.terms)), [1.0] if self.free_car1 else [], np.zeros(len(self.size_inter))]
        r = minimize(self.f, th0, jac=True, method="L-BFGS-B", bounds=[(0.01, None)] + [(None, None)] * (len(th0) - 1),
                     options=dict(maxiter=maxiter, gtol=1e-6, ftol=1e-14, maxcor=30))
        for _ in range(5):   # L-BFGS-B can stop on the relative-reduction test far from the optimum: restart until the gradient is small
            if np.abs(r.jac).max() < 0.5: break
            r = minimize(self.f, r.x, jac=True, method="L-BFGS-B", bounds=[(0.01, None)] + [(None, None)] * (len(th0) - 1),
                         options=dict(maxiter=maxiter, gtol=1e-6, ftol=1e-15, maxcor=50))
        self.th, self.ll, self.res = r.x, -r.fun, r; return self

    def robust(self):
        th = self.th; ll, S = self.scores(th); K = len(th); H = np.zeros((K, K))
        for i in range(K):
            h = 1e-5 * max(1.0, abs(th[i])); tp = th.copy(); tp[i] += h; tm = th.copy(); tm[i] -= h
            H[:, i] = (self.scores(tp)[1].sum(0) - self.scores(tm)[1].sum(0)) / (2 * h)
        H = (H + H.T) / 2; self.H = H; Hi = np.linalg.inv(-H); self.V = Hi @ (S.T @ S) @ Hi; self.se = np.sqrt(np.diag(self.V))
        self.max_grad = float(np.abs(S.sum(0)).max()); self.hess_eig = np.linalg.eigvalsh(H); return self

    def table(self):
        t = pd.DataFrame({"parameter": self.names, "estimate": self.th, "robust_se": getattr(self, "se", np.nan)}); t["robust_t"] = t.estimate / t.robust_se; return t

    def coef_dict(self):
        return dict(zip(self.names, self.th))


def full_set(terms, th, names, half="validation", free_car1=False, chunk=250, time_scale=1.0, size_inter=()):
    """full choice set over all zones with jobs: per-record LL (location mixture over all home and work zones), and the weighted
    predicted / observed shares and car-time distribution (location weights x wtperfin).  time_scale multiplies t (and the
    piecewise bands, not the logsum) for the elasticity check."""
    P, (Hz, Hw), (Wz, Ww) = E2.persons_v2(half); P["lic"] = lic_of(P.person_id); N = len(P); w = P.wtperfin.values
    c = dict(zip(names, th)); K = len(terms); b = np.array([c[f"b_{t.replace('*', 'X')}"] for t in terms]); c1 = c.get("c_lsXcar1", 1.0)
    ew = np.exp([c["g_OFF"], c["g_IND"], c["g_OTH"]]); S0 = z.RET.values + ew[0] * z.OFF.values + ew[1] * z.IND.values + ew[2] * z.OTH.values
    lnS = c["mu_size"] * np.log(np.maximum(S0, 1e-300)); pos = np.full(NZ, -1); pos[az] = np.arange(len(az))
    out = np.zeros(N); grid = np.linspace(0, 240, 4801); fine = np.zeros(len(grid) + 1); acc = {}; ttot = 0.0; wt = 0.0
    global TT
    T0 = TT
    for s in range(0, N, chunk):
        r = np.arange(s, min(s + chunk, N)); L = np.zeros(len(r))
        for a in range(Hz.shape[1]):
            m = Hw[r, a] > 0
            if not m.any(): continue
            rr = r[m]; h = Hz[rr, a]; A = np.broadcast_to(az, (len(rr), len(az)))
            TT = T0 * time_scale
            if size_inter:
                lw = np.repeat(np.log(ew)[:, None], len(rr), axis=1)
                for s_ in size_inter: lw[SIZE_K[s_.split(":")[0]] - 1] += c[f"h_{s_.replace(':', 'X')}"] * pvar(s_.split(":")[1], P, rr, h)
                e_ = np.exp(lw); lnSn = c["mu_size"] * np.log(np.maximum(z.RET.values[az][None] + e_[0][:, None] * z.OFF.values[az][None] + e_[1][:, None] * z.IND.values[az][None] + e_[2][:, None] * z.OTH.values[az][None], 1e-300))
            else:
                lnSn = lnS[az][None, :]
            U = lnSn + sum(b[k] * feat(t, h, A, P, rr) for k, t in enumerate(terms)) + c1 * feat("ls*car1", h, A, P, rr)
            TT = T0
            U -= U.max(axis=1, keepdims=True); Ex = np.exp(U); Pm = Ex / Ex.sum(axis=1, keepdims=True)
            L[m] += Hw[rr, a] * sum(Ww[rr, cc] * Pm[np.arange(len(rr)), np.maximum(pos[np.maximum(Wz[rr, cc], 0)], 0)] * (Wz[rr, cc] >= 0) for cc in range(Wz.shape[1]))
            Wm = (w[rr] * Hw[rr, a])[:, None] * Pm; t_ = T0[h[:, None], az[None, :]]; ttot += (Wm * t_).sum(); wt += Wm.sum()
            np.add.at(fine, np.clip(np.searchsorted(grid, t_, side="left"), 0, len(grid)).ravel(), Wm.ravel())
            same = ct[az][None, :] == ct[h][:, None]; ins = st[az][None, :] == st[h][:, None]
            for hn, hc in (("all", None), ("MD", 24), ("DC", 11), ("VA", 51)):
                mm = np.ones(len(rr), bool) if hc is None else P.state_h.values[rr] == hc; X = Wm[mm]
                for k_, v in ((f"{hn}_tot", X.sum()), (f"{hn}_si", (X * same[mm] * ins[mm]).sum()), (f"{hn}_ins", (X * ins[mm]).sum()),
                              (f"{hn}_MD", X[:, st[az] == 24].sum()), (f"{hn}_DC", X[:, st[az] == 11].sum()), (f"{hn}_VA", X[:, st[az] == 51].sum())):
                    acc[k_] = acc.get(k_, 0) + v
        out[r] = np.log(np.maximum(L, 1e-300))
    # observed
    oh, oj, ow = [], [], []
    for a in range(Hz.shape[1]):
        for cc in range(Wz.shape[1]):
            m = (Hw[:, a] > 0) & (Ww[:, cc] > 0); oh.append(Hz[m, a]); oj.append(Wz[m, cc]); ow.append(Hw[m, a] * Ww[m, cc] * w[m])
    oh, oj, ow = map(np.concatenate, (oh, oj, ow)); to = T0[oh, oj]; o_ = np.argsort(to); cdf_o = np.interp(grid, to[o_], np.cumsum(ow[o_]) / ow.sum(), left=0.0)
    cdf_m = np.cumsum(fine[:-1]) / fine.sum()
    sh = {f"{k}": v for k, v in acc.items()}
    res = dict(N=N, LL_per_record=out.mean(), LL_total=out.sum(), ks_car_time=float(np.abs(cdf_o - cdf_m).max()), ks_crit=1.36 / np.sqrt(w.sum() ** 2 / (w ** 2).sum()),
               mean_car_time=ttot / wt, obs_mean_car_time=(ow * to).sum() / ow.sum())
    for hn in ("all", "MD", "DC", "VA"):
        res[f"same_county_{hn}home_instate"] = acc[f"{hn}_si"] / acc[f"{hn}_ins"]
        for sn in ("MD", "DC", "VA"): res[f"share_{hn}home_work{sn}"] = acc[f"{hn}_{sn}"] / acc[f"{hn}_tot"]
    return res, out


class FullModel:
    """the same likelihood on the FULL choice set (all zones with jobs, no sampling, no -ln q) (coordinator 2026-10-28).  Rows are
    the (worker, possible home zone) pairs with a positive weight (no truncation to 3 home zones); features are float32 arrays
    rows x 1,587 zones, built once.  log L_n = lse over the worker's rows of [log w_h + lse_c(log w_c + V_hc) - lse_j V_hj]."""
    def __init__(self, terms, free_car1=False, size_inter=(), half="estimation"):
        P, (Hz, Hw), (Wz, Ww) = E2.persons_v2(half); P["lic"] = lic_of(P.person_id); self.P = P; self.N = len(P)
        r_, s_ = np.nonzero(Hw > 0); self.rec = r_; self.h = Hz[r_, s_]; self.lw = np.log(Hw[r_, s_]); self.R = len(r_)
        pos = np.full(NZ, -1); pos[az] = np.arange(len(az))
        self.cand = np.where(Wz >= 0, pos[np.maximum(Wz, 0)], 0)[r_]; self.lwc = np.where(Wz >= 0, np.log(np.maximum(Ww, 1e-300)), -np.inf)[r_]
        self.terms, self.free_car1, self.size_inter = list(terms), free_car1, list(size_inter)
        self.names = (["mu_size", "g_OFF", "g_IND", "g_OTH"] + [f"b_{t.replace('*', 'X')}" for t in self.terms] + (["c_lsXcar1"] if free_car1 else [])
                      + [f"h_{s.replace(':', 'X')}" for s in self.size_inter])
        A = np.broadcast_to(az, (self.R, len(az)))
        self.Xs = np.stack([feat(t, self.h, A, P, self.rec).astype(np.float32) for t in self.terms]); self.off = feat("ls*car1", self.h, A, P, self.rec).astype(np.float32)
        self.NK = np.stack([z[s].values[az] for s in R.SEC]).astype(float)                    # 4 x J
        self.SX = np.stack([pvar(s.split(":")[1], P, self.rec, self.h) for s in self.size_inter]) if self.size_inter else np.zeros((0, self.R))
        self.SK = np.array([SIZE_K[s.split(":")[0]] for s in self.size_inter], int)
        self.order = np.argsort(self.rec, kind="stable"); self.starts = np.r_[0, np.flatnonzero(np.diff(self.rec[self.order])) + 1]

    def scores(self, th):
        K = len(self.terms); mu = th[0]; i0 = 4 + K + (1 if self.free_car1 else 0); hh = th[i0:]
        lw = np.repeat(th[1:4][:, None], self.R, axis=1)
        for j, k in enumerate(self.SK): lw[k - 1] += hh[j] * self.SX[j]
        ew = np.exp(lw); Sz = self.NK[0][None] + ew[0][:, None] * self.NK[1][None] + ew[1][:, None] * self.NK[2][None] + ew[2][:, None] * self.NK[3][None]
        lnS = np.log(Sz + 1e-9); c1 = th[4 + K] if self.free_car1 else 1.0
        V = mu * lnS + np.tensordot(th[4:4 + K], self.Xs, axes=1) + c1 * self.off             # R x J
        m = V.max(axis=1, keepdims=True); lden = m[:, 0] + np.log(np.exp(V - m).sum(axis=1))
        lc = self.lwc + np.take_along_axis(V, self.cand, axis=1); mc = lc.max(axis=1, keepdims=True); lnum = mc[:, 0] + np.log(np.exp(lc - mc).sum(axis=1))
        la = self.lw + lnum - lden
        lo = la[self.order]; mx = np.maximum.reduceat(lo, self.starts); lL = mx + np.log(np.add.reduceat(np.exp(lo - np.repeat(mx, np.diff(np.r_[self.starts, len(lo)]))), self.starts))
        recs = self.rec[self.order][self.starts]; LL = np.full(self.N, np.nan); LL[recs] = lL
        wrow = np.exp(la - LL[self.rec])                                                        # posterior weight of the row
        p = np.exp(V - lden[:, None]); rc = np.zeros_like(p)
        np.add.at(rc, (np.repeat(np.arange(self.R), self.cand.shape[1]), self.cand.ravel()), np.exp(lc - lnum[:, None]).ravel())   # padded candidates add 0
        dW = wrow[:, None] * (rc - p)                                                           # R x J
        sb = np.einsum("krj,rj->rk", self.Xs, dW); smu = (dW * lnS).sum(axis=1)
        dk = [(dW * (mu * ew[k][:, None] * self.NK[k + 1][None] / (Sz + 1e-9))).sum(axis=1) for k in range(3)]
        S = [smu[:, None], np.stack(dk, 1), sb]
        if self.free_car1: S.append((dW * self.off).sum(axis=1)[:, None])
        if self.size_inter: S.append(np.stack([dk[k - 1] * self.SX[j] for j, k in enumerate(self.SK)], 1))
        Srow = np.concatenate(S, axis=1); Sn = np.zeros((self.N, Srow.shape[1])); np.add.at(Sn, self.rec, Srow)
        self.n_bad = int((~np.isfinite(LL)).sum()); return LL, Sn

    f = Model.f; fit = Model.fit; robust = Model.robust; table = Model.table; coef_dict = Model.coef_dict
