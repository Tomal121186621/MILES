# Copy of side_experiments/respec_2026-11/step_by_step/workplace/wdc.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Workplace choice estimator for the step-by-step work (multinomial logit over zones with a size term).

U_ij = sum_k b_k x_ijk + mu ln S_ij,   S_ij = RET_j + sum_{c in OFF, IND, OTH} exp(g_c + d_{c,s(i)}) N_jc
d_{c,s} (optional, 'segmented size'): shift of the log weight of job type c for the worker's income group s (base: $40-75k).
Estimation on the chosen zone plus 99 zones drawn at random (uniform) from the other zones with jobs; with uniform sampling the
MNL likelihood needs no correction. Analytic gradient, L-BFGS-B; robust (sandwich) s.e. with a numerical Hessian of the gradient.
The held-out log-likelihood uses the full choice set (all 1,587 zones with jobs).
Person variable 'x_c' (in 't*x_c'): x minus its estimation-half mean (MEAN), the same constant on both halves."""
import os
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
RAWD = os.path.abspath(f"{HERE}/../data/raw"); SHD = os.path.abspath(f"{HERE}/../../../00_shared_data")   # PATH (package)
D = dict(np.load(f"{RAWD}/data.npz"))
LS = np.load(os.environ.get("WDC_LOGSUM", "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026/2_silo/jobchoice/work_rts/logsum.npy"), mmap_mode="r")   # WDC_LOGSUM: work-tour mode-choice logsums
JOBS = np.column_stack([D["jobs_RET"], D["jobs_OFF"], D["jobs_IND"], D["jobs_OTH"]])
AZ = np.where(JOBS.sum(1) > 0)[0]
TT = D["tt"].astype(float)
ST, CT = D["z_state"], D["z_county"]
REGIONS = {"bc": [24510], "mopg": [24031, 24033], "dcr": [11001], "nvc": [51013, 51510],
           "nvo": [51919, 51107, 51942, 51059, 51600, 51610, 51153, 51683, 51685]}
BMC = [24003, 24005, 24013, 24025, 24027]
REG = np.full(len(ST), "oth", dtype=object); REG[np.isin(CT, BMC)] = "bmc"
for k, v in REGIONS.items(): REG[np.isin(CT, v)] = k
REG[(ST == 24) & (REG == "oth")] = "mdo"


def persons(est=True):
    m = D["p_est"] == (1 if est else 0)
    return {k[2:]: v[m] for k, v in D.items() if k.startswith("p_")}


def pvar(name, P):
    if name.endswith("_c"): return pvar(name[:-2], P) - MEAN[name[:-2]]       # centred: minus the estimation-half mean
    if name == "female": return P["female"].astype(float)
    if name == "young": return (P["age"] < 30).astype(float)
    if name == "old": return (P["age"] >= 55).astype(float)
    if name in ("g1", "g2", "g3", "g4"): return (P["g"] == int(name[1])).astype(float)
    if name == "lic": return P["lic"].astype(float)
    if name == "hhs": return P["hhsize"].astype(float)
    if name == "kids": return P["kids"].astype(float)
    if name == "w2": return (P["workers"] >= 2).astype(float)
    if name == "car0": return (P["car_seg"] == 0).astype(float)
    if name == "rurh": return D["z_rural"][P["hidx"]]
    if name == "hva": return (P["state_h"] == 51).astype(float)
    raise KeyError(name)


_PE = persons(True)
MEAN = {k: float(pvar(k, _PE).mean()) for k in ["female", "young", "old", "g1", "g2", "g3", "g4", "lic", "hhs", "kids", "w2", "car0", "rurh", "hva"]}


def base(key, h, A, P):
    hh = h[:, None]
    if key == "t": return TT[hh, A]
    if key == "lt": return np.log1p(TT[hh, A])
    if key.startswith("tpw"):                                 # piecewise time: tpw_a_b = clip(t - a, 0, b - a)
        a, b = (float(x) for x in key[4:].split("_")); return np.clip(TT[hh, A] - a, 0, b - a)
    if key == "ls": return np.asarray(LS[P["car_seg"][:, None], (P["g"] - 1)[:, None], hh, A], dtype=float)
    if key == "intra": return (A == hh).astype(float)
    if key == "cs": return (ST[A] != ST[hh]).astype(float)
    if key == "cc": return (CT[A] != CT[hh]).astype(float)
    if key == "dcw": return ((ST[A] == 11) & (ST[hh] != 11)).astype(float)
    if key.startswith("reg_"): return (REG[A] == key[4:]).astype(float)
    if key == "accw": return D["acc_nonwork"][P["car_seg"][:, None], (P["g"] - 1)[:, None], A]
    if key.startswith("z_"): return D[key][A]
    raise KeyError(key)


def feat(key, h, A, P):
    parts = key.split("*"); x = base(parts[0], h, A, P)
    for q in parts[1:]: x = x * pvar(q, P)[:, None]
    return x


class Model:
    """terms: linear terms; seg: True = size weights shifted by income group"""
    def __init__(self, terms, seg=False, est=True, seed=20261106, M=100):
        self.terms, self.seg = list(terms), seg
        P = persons(est); self.P = P; N = len(P["g"]); rng = np.random.default_rng(seed)
        A = np.empty((N, M), int); A[:, 0] = P["widx"]
        for i in range(N):
            c = rng.choice(len(AZ) - 1, M - 1, replace=False); z = AZ[AZ != P["widx"][i]]; A[i, 1:] = z[c]
        self.A, self.N = A, N
        self.X = np.stack([feat(k, P["hidx"], A, P) for k in self.terms], axis=2) if self.terms else np.zeros((N, M, 0))
        self.Nj = JOBS[A]                                         # N x M x 4
        self.G = np.eye(4)[P["g"] - 1]                            # N x 4 income group
        self.names = self.terms + ["mu", "g_OFF", "g_IND", "g_OTH"] + (
            [f"d_{c}_g{s}" for c in ["OFF", "IND", "OTH"] for s in (1, 3, 4)] if seg else [])

    def _w(self, th):
        """log weights per record and job type (N x 4; RET = 0)"""
        K = len(self.terms); g = th[K + 1:K + 4]; lw = np.zeros((self.N, 4)); lw[:, 1:] = g
        if self.seg:
            d = th[K + 4:].reshape(3, 3)                          # job type x group (1, 3, 4)
            for j, s in enumerate((0, 2, 3)): lw[:, 1:] += self.G[:, [s]] * d[:, j][None, :]
        return lw

    def ll_grad(self, th, per=False):
        K = len(self.terms); b, mu = th[:K], th[K]
        lw = self._w(th); W = np.exp(lw)[:, None, :] * self.Nj   # N x M x 4
        S = np.maximum(W.sum(2), 1e-300); lS = np.log(S)
        U = self.X @ b + mu * lS; U -= U.max(1, keepdims=True); E = np.exp(U); Pr = E / E.sum(1, keepdims=True)
        ll = np.log(np.maximum(Pr[:, 0], 1e-300))
        dif = -Pr; dif[:, 0] += 1                                 # (y - p), chosen first
        sc = [np.einsum("nm,nmk->nk", dif, self.X), (dif * lS).sum(1)[:, None]]
        share = W / S[:, :, None]                                 # N x M x 4
        dg = mu * np.einsum("nm,nmc->nc", dif, share[:, :, 1:])   # N x 3
        sc.append(dg)
        if self.seg:
            for s in (0, 2, 3): sc.append(dg * self.G[:, [s]])
            sc = sc[:3] + [np.column_stack([sc[3][:, c], sc[4][:, c], sc[5][:, c]]) for c in range(3)]
        Sc = np.concatenate(sc, axis=1)
        return (ll, Sc) if per else (ll.sum(), Sc.sum(0))

    def fit(self, th0=None):
        n = len(self.names); th0 = np.r_[np.zeros(len(self.terms)), 0.8, np.zeros(n - len(self.terms) - 1)] if th0 is None else th0
        f = lambda th: tuple(-x for x in self.ll_grad(th))
        bounds = [(None, None)] * len(self.terms) + [(0.01, 3)] + [(-10, 10)] * (n - len(self.terms) - 1)
        r = minimize(f, th0, jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": 5000, "maxfun": 10000, "ftol": 1e-12, "gtol": 1e-6})
        th = r.x; ll, g = self.ll_grad(th)
        # Newton polish with the Hessian of the analytic gradient (L-BFGS-B stops early on badly scaled problems)
        for _ in range(30):
            if np.abs(g).max() < 1e-4: break
            H = self.hess(th)
            try: step = np.linalg.solve(H, -g)
            except np.linalg.LinAlgError: step = np.linalg.lstsq(H, -g, rcond=None)[0]
            a = 1.0
            while a > 1e-4:
                t2 = th + a * step
                for i, (lo, hi) in enumerate(bounds): t2[i] = np.clip(t2[i], -np.inf if lo is None else lo, np.inf if hi is None else hi)
                l2, g2 = self.ll_grad(t2)
                if l2 >= ll - 1e-9: th, ll, g = t2, l2, g2; break
                a /= 2
            else: break
        self.th, self.LL, self.conv = th, ll, float(np.abs(g).max())
        self.K = n; self.BIC = -2 * self.LL + n * np.log(self.N)
        return self

    def hess(self, th, e=1e-5):
        n = len(th); H = np.zeros((n, n))
        for k in range(n):
            d = np.zeros(n); d[k] = e
            H[:, k] = (self.ll_grad(th + d)[1] - self.ll_grad(th - d)[1]) / (2 * e)
        return (H + H.T) / 2

    def robust(self):
        th = self.th; n = len(th); H = np.zeros((n, n)); e = 1e-5
        for k in range(n):
            d = np.zeros(n); d[k] = e
            H[:, k] = (self.ll_grad(th + d)[1] - self.ll_grad(th - d)[1]) / (2 * e)
        H = (H + H.T) / 2; _, Sc = self.ll_grad(th, per=True); Hi = np.linalg.inv(-H)
        self.cov = Hi @ (Sc.T @ Sc) @ Hi; self.se = np.sqrt(np.diag(self.cov)); self.cond = np.linalg.cond(-H)
        return self

    def holdout_ll(self, chunk=250, est=False):
        """full-set log-likelihood (all zones with jobs) with the estimated coefficients; validation half unless est=True"""
        P = persons(est=est); N = len(P["g"]); K = len(self.terms); b, mu = self.th[:K], self.th[K]; tot = 0.0
        g = self.th[K + 1:K + 4]
        for s in range(0, N, chunk):
            r = np.arange(s, min(s + chunk, N)); Q = {k: v[r] for k, v in P.items()}
            A = np.broadcast_to(AZ, (len(r), len(AZ)))
            U = sum(bk * feat(k, Q["hidx"], A, Q) for bk, k in zip(b, self.terms)) if K else 0
            lw = np.zeros((len(r), 4)); lw[:, 1:] = g
            if self.seg:
                d = self.th[K + 4:].reshape(3, 3)
                for j, sg in enumerate((1, 3, 4)): lw[:, 1:] += (Q["g"] == sg)[:, None] * d[:, j][None, :]
            S = np.einsum("mc,nc->nm", JOBS[AZ], np.exp(lw)); U = U + mu * np.log(np.maximum(S, 1e-300))
            U = U - U.max(1, keepdims=True); lse = np.log(np.exp(U).sum(1))
            ch = np.searchsorted(AZ, Q["widx"]); tot += (U[np.arange(len(r)), ch] - lse).sum()
        if est: self.FS, self.FS_per = tot, tot / N
        else: self.HO, self.HO_per = tot, tot / N
        return tot

    def table(self):
        return [(n, b, s, b / s) for n, b, s in zip(self.names, self.th, self.se)]
