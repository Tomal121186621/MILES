#!/usr/bin/env python3
"""Estimation engine of the RTS school location choice: the likelihood and optimiser of jobchoice/rts_21_engine.py (FullModel /
Model), written for one segment (sc_common.SEG) and both choice-set modes.

Rows = (student, possible home zone) pairs with a positive weight (all of them, at most 4).  Entries per row:
  'sampled': the student's possible school zones (up to 4) + ND zones drawn with replacement, q_j proportional to
             size_j exp(-DECAY t_hj) from the most likely home zone over the zones with enrolment of the student's band (seed 20261029,
             second draw 20261030), McFadden correction -ln q_j on every entry;
  'full':    every zone with enrolment of the segment's bands (no sampling, no correction); entries without enrolment of the
             student's own band (K-8: elementary vs middle) are unavailable.
log L_n = lse_rows [log w_h + lse_c (log w_c + V_hc) - lse_j V_hj]  (location mixture of rts_11_data_v2 / rts_21_engine).
Utility V_hj = mu ln S_hj + sum_k b_k x_k,hj (+ corr), size S_hj = sum_c exp(g_c + h_c' x_n) N_c,hj with the components
  K-12: pub_out (reference), pub_in, priv: public enrolment of the band outside / inside the home's attendance boundary
        (pub_in_hj = sum_{s in j} a_hs N_s, sc_00_sabs.py; 0 where the home's district has no SABS boundary), private enrolment.
        Without the SABS term g_in is fixed at 0, so pub_out + pub_in = all public enrolment;
  college: pub4 (reference), priv4, cc (IPEDS sector).
Terms are 'base*var*...' strings.  Bases: t (car peak time, min), lt (ln(1+t)), ls (school-tour mode-choice logsum of the student's
  segment x car availability x income group, sc_02_logsum.py), intra (same zone), cc (other county), cs (other state), ccpub (other
  county x public share of the zone's band enrolment).  Person variables: female, g1, g3, g4 (income <40k, 75-125k, >=125k; base
  40-75k), car0 (no car), carlow (fewer cars than drivers), agec (age - segment reference age 10 / 16 / 25), a25 (age >= 25).
Size interactions: 'comp:var' -> parameter h_compXvar (person-specific component weight).
Maximisation: analytic gradient, L-BFGS-B with restarts; robust sandwich covariance from analytic per-record scores and a
central-difference Hessian of the analytic gradient."""
import os, sys, numpy as np, pandas as pd
from scipy.optimize import minimize
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sc_common as C   # noqa: E402
z = C.zones(); NZ = len(z); ST = z.state.values; CT = z.county.values; TT = C.tt().astype(np.float32); zi = C.zidx()
LSUM = np.load(f"{C.W}/logsum.npy", mmap_mode="r")
SIZE = C.size()
REF_AGE = {"k8": 10, "hs": 16, "col": 25}; DECAY = {"k8": 0.15, "hs": 0.10, "col": 0.05}; ND = 50; NC = 4; HS = 4
COMPS = {"k8": ["pub_out", "pub_in", "priv"], "hs": ["pub_out", "pub_in", "priv"], "col": ["pub4", "priv4", "cc"]}
BANDS = {"k8": ["elementary", "middle"], "hs": ["high"], "col": ["postsec"]}
_ain = {}


def ain(band):
    """(in-boundary public enrolment matrix NZ x NZ, in-boundary housing-unit share matrix NZ x NZ, coverage by home zone)"""
    if band in _ain: return _ain[band]
    A = pd.read_parquet(f"{C.W}/sabs_home_school.parquet"); A = A[A.band == band]
    cap = pd.read_parquet(f"{C.W}/school_points.parquet").set_index("id").capacity
    M = np.zeros((NZ, NZ), np.float32); B = np.zeros((NZ, NZ), np.float32)
    np.add.at(M, (zi[A.zone].values, zi[A.school_zone].values), (A.a * A.school_id.map(cap)).values)
    np.add.at(B, (zi[A.zone].values, zi[A.school_zone].values), A.a.values)
    cv = pd.read_parquet(f"{C.W}/sabs_zone_cov.parquet"); cv = cv[cv.band == band]; cov = np.zeros(NZ); cov[zi[cv.zone].values] = cv["cov"].values
    _ain[band] = (M, B, cov); return _ain[band]


def persons(seg, half):
    P = pd.read_parquet(f"{C.W}/students.parquet"); P = P[(P.seg == seg) & (P.half == half)].reset_index(drop=True)
    P["car_seg"] = np.select([P.car0 == 1, P.carlow == 1], [0, 1], 2)
    pos = pd.Series(np.arange(len(P)), index=P.person_id)
    def mat(f, k):
        Lx = pd.read_parquet(f"{C.W}/{f}"); Lx = Lx[Lx.person_id.isin(P.person_id)].sort_values(["person_id", "w"], ascending=[True, False]).copy()
        Lx["r"] = Lx.groupby("person_id").cumcount(); Lx = Lx[Lx.r < k]
        Z_ = np.full((len(P), k), -1); Wt = np.zeros((len(P), k)); Z_[pos[Lx.person_id].values, Lx.r.values] = zi[Lx.zone].values; Wt[pos[Lx.person_id].values, Lx.r.values] = Lx.w.values
        return Z_, Wt / Wt.sum(axis=1, keepdims=True)
    return P, mat("loc_home.parquet", HS), mat("loc_school.parquet", NC)


def pvar(name, P, rec):
    if name in ("female", "car0", "carlow"): return P[name].values[rec].astype(float)
    if name in ("g1", "g3", "g4"): return (P.g.values[rec] == int(name[1])).astype(float)
    if name == "agec": return (P.age.values[rec] - REF_AGE[P.seg.values[0]]).astype(float)
    if name == "a25": return (P.age.values[rec] >= 25).astype(float)
    raise KeyError(name)


class Design:
    def __init__(self, seg, half="estimation", mode="sampled", seed=20261029):
        self.seg, self.half, self.mode = seg, half, mode
        P, (Hz, Hw), (Sz, Sw) = persons(seg, half); self.P = P; self.N = N = len(P); self.Hz, self.Hw, self.Sz, self.Sw = Hz, Hw, Sz, Sw
        band = P.band.values; self.band = band; comps = COMPS[seg]; self.comps = comps
        tot = {b: sum(SIZE[b].values()) for b in BANDS[seg]}
        self.alts = np.flatnonzero(sum(tot.values()) > 0)
        r_, s_ = np.nonzero(Hw > 0); self.rec = r_; self.h = Hz[r_, s_]; self.lw = np.log(Hw[r_, s_]); self.R = R = len(r_)
        if mode == "full":
            pos = np.full(NZ, -1); pos[self.alts] = np.arange(len(self.alts)); Arec = np.broadcast_to(self.alts, (N, len(self.alts)))
            cpos = np.where(Sz >= 0, pos[np.maximum(Sz, 0)], 0); corr = np.zeros(Arec.shape, np.float32)
        else:
            rng = np.random.default_rng(seed); h0 = Hz[:, 0]; Arec = np.empty((N, NC + ND), int); corr = np.empty((N, NC + ND), np.float32)
            for b in BANDS[seg]:
                m = np.flatnonzero(band == b); J = np.flatnonzero(tot[b] > 0)
                lq = np.log(tot[b][J])[None] - DECAY[seg] * TT[h0[m]][:, J]; q = np.exp(lq - lq.max(1, keepdims=True)); q /= q.sum(1, keepdims=True); cq = np.cumsum(q, 1)
                D = np.minimum((cq[:, None, :] < rng.random((len(m), ND))[:, :, None]).sum(2), len(J) - 1)
                Arec[m, :NC] = np.where(Sz[m] >= 0, Sz[m], Sz[m, :1]); Arec[m, NC:] = J[D]
                qf = np.zeros((len(m), NZ)); qf[:, J] = q; corr[m] = -np.log(qf[np.arange(len(m))[:, None], Arec[m]])
            cpos = np.tile(np.arange(NC), (N, 1))
        self.A = np.ascontiguousarray(Arec[r_]); self.corr = corr[r_].astype(np.float32)
        self.cand = cpos[r_]; self.lwc = np.where(Sz >= 0, np.log(np.maximum(Sw, 1e-300)), -np.inf)[r_]
        J = self.A.shape[1]; NK = np.zeros((len(comps), R, J), np.float32); rb = band[r_]
        for b in BANDS[seg]:
            m = rb == b; Am = self.A[m]
            if seg == "col":
                for k, c in enumerate(comps): NK[k][m] = SIZE[b].get(c, np.zeros(NZ))[Am]
            else:
                pub = SIZE[b]["pub"][Am]; pin = np.minimum(ain(b)[0][self.h[m][:, None], Am], pub)
                NK[0][m] = pub - pin; NK[1][m] = pin; NK[2][m] = SIZE[b].get("priv", np.zeros(NZ))[Am]
        self.NK = NK; self.av = NK.sum(0) > 0
        if mode == "sampled": self.av[:, :NC] &= (Sz >= 0)[r_]
        self.order = np.argsort(self.rec, kind="stable"); self.starts = np.r_[0, np.flatnonzero(np.diff(self.rec[self.order])) + 1]
        self.cache = {}

    def base(self, name):
        h = self.h[:, None]; A = self.A
        if name == "t": return TT[h, A]
        if name == "lt": return np.log1p(TT[h, A])
        if name == "ls":
            si = C.SEG.index(self.seg); cs = self.P.car_seg.values[self.rec]; g = self.P.g.values[self.rec] - 1; out = np.empty(A.shape, np.float32)
            for c in range(3):
                for gg in range(4):
                    m = (cs == c) & (g == gg)
                    if m.any(): L = np.asarray(LSUM[si, c, gg]); out[m] = L[self.h[m][:, None], A[m]]
            return out
        if name == "intra": return (A == h).astype(np.float32)
        if name == "cc": return (CT[A] != CT[h]).astype(np.float32)
        if name == "cs": return (ST[A] != ST[h]).astype(np.float32)
        if name == "ccpub":
            S_ = self.NK.sum(0); pubsh = np.where(S_ > 0, (self.NK[0] + self.NK[1]) / np.maximum(S_, 1e-9), 0) if self.seg != "col" else np.zeros(A.shape)
            return ((CT[A] != CT[h]) * pubsh).astype(np.float32)
        raise KeyError(name)

    def X(self, spec):
        if spec not in self.cache:
            p = spec.split("*"); x = self.base(p[0]).astype(np.float32)
            for q in p[1:]: x = x * pvar(q, self.P, self.rec)[:, None].astype(np.float32)
            self.cache[spec] = x
        return self.cache[spec]


class Model:
    """free size weights: COMPS[seg][1:] that are active (K-12: 'priv' always, 'pub_in' only with the SABS term 'size:in')"""
    def __init__(self, D, terms, size_inter=(), sabs=False, fixed=None):
        self.D, self.terms, self.size_inter, self.sabs = D, list(terms), list(size_inter), sabs
        self.fixed = dict(fixed or {}); self.off = sum(v * D.X(k) for k, v in self.fixed.items()) if self.fixed else 0.0   # terms with a fixed coefficient
        comps = D.comps; self.gfree = [c for c in comps[1:] if not (c == "pub_in" and not sabs)]
        self.gidx = [comps.index(c) for c in self.gfree]
        self.names = ["mu_size"] + [f"g_{c}" for c in self.gfree] + [f"b_{t.replace('*', 'X')}" for t in self.terms] + [f"h_{s.replace(':', 'X')}" for s in self.size_inter]
        self.Xs = np.stack([D.X(t) for t in self.terms]) if self.terms else np.zeros((0,) + D.A.shape, np.float32)
        self.SX = np.stack([pvar(s.split(":")[1], D.P, D.rec) for s in self.size_inter]) if self.size_inter else np.zeros((0, D.R))
        self.SK = np.array([comps.index(s.split(":")[0]) for s in self.size_inter], int)
        self.ng = len(self.gfree); self.K = len(self.terms)

    def x0(self): return np.r_[0.8, np.zeros(self.ng), np.zeros(self.K), np.zeros(len(self.size_inter))]

    def scores(self, th, want_p=False):
        D = self.D; mu = th[0]; g = th[1:1 + self.ng]; b = th[1 + self.ng:1 + self.ng + self.K]; hh = th[1 + self.ng + self.K:]
        lw = np.zeros((len(D.comps), D.R))
        for j, k in enumerate(self.gidx): lw[k] += g[j]
        for j, k in enumerate(self.SK): lw[k] += hh[j] * self.SX[j]
        ew = np.exp(lw); WN = ew[:, :, None] * D.NK; Sz = WN.sum(0); lnS = np.log(Sz + 1e-12)
        V = mu * lnS + D.corr + (np.tensordot(b, self.Xs, axes=1) if self.K else 0.0) + self.off
        V = np.where(D.av, V, -np.inf)
        m = V.max(axis=1, keepdims=True); lden = m[:, 0] + np.log(np.exp(V - m).sum(axis=1))
        lc = D.lwc + np.take_along_axis(V, D.cand, axis=1); mc = lc.max(axis=1, keepdims=True); lnum = mc[:, 0] + np.log(np.exp(lc - mc).sum(axis=1))
        la = D.lw + lnum - lden
        lo = la[D.order]; mx = np.maximum.reduceat(lo, D.starts); lL = mx + np.log(np.add.reduceat(np.exp(lo - np.repeat(mx, np.diff(np.r_[D.starts, len(lo)]))), D.starts))
        recs = D.rec[D.order][D.starts]; LL = np.full(D.N, np.nan); LL[recs] = lL
        wrow = np.exp(la - LL[D.rec]); p = np.exp(V - lden[:, None])
        if want_p: return LL, p, wrow
        rc = np.zeros_like(p); np.add.at(rc, (np.repeat(np.arange(D.R), D.cand.shape[1]), D.cand.ravel()), np.where(np.isfinite(lc), np.exp(lc - lnum[:, None]), 0.0).ravel())
        dW = wrow[:, None] * (rc - p); dW = np.where(D.av, dW, 0.0)
        smu = (dW * lnS).sum(axis=1)
        dk = [(dW * (mu * WN[k] / (Sz + 1e-12))).sum(axis=1) for k in range(len(D.comps))]
        S = [smu[:, None]]
        if self.ng: S.append(np.stack([dk[k] for k in self.gidx], 1))
        if self.K: S.append(np.einsum("krj,rj->rk", self.Xs, dW))
        if self.size_inter: S.append(np.stack([dk[k] * self.SX[j] for j, k in enumerate(self.SK)], 1))
        Srow = np.concatenate(S, axis=1); Sn = np.zeros((D.N, Srow.shape[1])); np.add.at(Sn, D.rec, Srow)
        self.n_bad = int((~np.isfinite(LL)).sum()); return LL, Sn

    def f(self, th):
        ll, S = self.scores(th); return -ll.sum(), -S.sum(0)

    def fit(self, th0=None, maxiter=4000):
        th0 = self.x0() if th0 is None else th0; bnd = [(0.01, None)] + [(None, None)] * (len(th0) - 1)
        r = minimize(self.f, th0, jac=True, method="L-BFGS-B", bounds=bnd, options=dict(maxiter=maxiter, gtol=1e-7, ftol=1e-15, maxcor=30))
        for _ in range(5):
            if np.abs(r.jac).max() < 0.01: break
            r = minimize(self.f, r.x, jac=True, method="L-BFGS-B", bounds=bnd, options=dict(maxiter=maxiter, gtol=1e-8, ftol=1e-16, maxcor=50))
        self.th, self.ll, self.res = r.x, -r.fun, r; self.max_grad_fit = float(np.abs(r.jac).max()); return self

    def robust(self):
        th = self.th; ll, S = self.scores(th); K = len(th); H = np.zeros((K, K))
        for i in range(K):
            h = 1e-5 * max(1.0, abs(th[i])); tp = th.copy(); tp[i] += h; tm = th.copy(); tm[i] -= h
            H[:, i] = (self.scores(tp)[1].sum(0) - self.scores(tm)[1].sum(0)) / (2 * h)
        H = (H + H.T) / 2; self.H = H; Hi = np.linalg.inv(-H); self.V = Hi @ (S.T @ S) @ Hi; self.se = np.sqrt(np.diag(self.V))
        self.max_grad = float(np.abs(S.sum(0)).max()); self.hess_eig = np.linalg.eigvalsh(H); return self

    def table(self):
        t = pd.DataFrame({"parameter": self.names, "estimate": self.th, "robust_se": getattr(self, "se", np.nan)}); t["robust_t"] = t.estimate / t.robust_se; return t

    def coef_dict(self): return dict(zip(self.names, self.th))

    def at(self, coef):
        """parameter vector of this model from a coefficient dict (missing -> 0, mu -> 0.8)"""
        return np.array([coef.get(n, 0.8 if n == "mu_size" else 0.0) for n in self.names])
