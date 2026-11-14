"""Multinomial logit by maximum likelihood (numpy / scipy), linear in the parameters, with
  - availability per alternative,
  - an observed outcome that may be a set of alternatives (P(obs) = sum of the probabilities of the set; used where a PUMA
    covers several regions),
  - observation weights (expected in-area share of origin and destination),
  - robust (sandwich) standard errors.
Used for the specification search and the sensitivity runs; the final models are re-estimated in Biogeme (bg.py) and the two
are compared (est_compare_*.csv)."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize


class MNL:
    def __init__(self, X, names, avail, chosen, weights=None, offset=None):
        """X (N, J, K); avail (N, J) bool; chosen (N, J) bool mask of the observed set; offset (N, J) fixed utility term."""
        self.X = np.asarray(X, dtype=np.float64); self.names = list(names)
        self.av = np.asarray(avail, dtype=bool); self.C = np.asarray(chosen, dtype=bool) & self.av
        N = self.X.shape[0]
        self.w = np.ones(N) if weights is None else np.asarray(weights, dtype=np.float64)
        self.off = np.zeros(self.av.shape) if offset is None else np.asarray(offset, dtype=np.float64)
        ok = self.C.any(axis=1)
        if not ok.all():
            raise ValueError(f"{(~ok).sum()} observations have no available chosen alternative")

    def _probs(self, b):
        V = self.X @ b + self.off
        V = np.where(self.av, V, -np.inf)
        m = V.max(axis=1, keepdims=True)
        e = np.exp(V - m); e[~self.av] = 0
        S = e.sum(axis=1, keepdims=True)
        return e / S

    def _logs(self, b):
        """log P_j, log P(observed set), and Q_j = P_j / P(set) on the set, computed stably."""
        V = self.X @ b + self.off
        Va = np.where(self.av, V, -np.inf); Vc = np.where(self.C, V, -np.inf)
        ma = Va.max(axis=1, keepdims=True); mc = Vc.max(axis=1, keepdims=True)
        lse_a = np.log(np.exp(Va - ma).sum(axis=1, keepdims=True)) + ma
        lse_c = np.log(np.exp(Vc - mc).sum(axis=1, keepdims=True)) + mc
        P = np.exp(Va - lse_a); Q = np.exp(Vc - lse_c)
        return P, Q, (lse_c - lse_a)[:, 0]

    def loglik_obs(self, b):
        return self._logs(b)[2]

    def _fg(self, b):
        P, Q, ll = self._logs(b)                       # Q: probability within the observed set
        g_n = np.einsum("nj,njk->nk", Q - P, self.X)  # per-observation score
        return -(self.w * ll).sum(), -(self.w[:, None] * g_n).sum(axis=0), g_n, P, Q

    def fit(self, b0=None, maxiter=500):
        K = self.X.shape[2]
        b0 = np.zeros(K) if b0 is None else np.asarray(b0, float)
        r = minimize(lambda b: self._fg(b)[:2], b0, jac=True, method="BFGS", options={"maxiter": maxiter, "gtol": 1e-6})
        b = r.x
        # Newton polishing with the analytic information matrix (BFGS stops early on flat directions)
        for _ in range(30):
            f, g, g_n, P, Q = self._fg(b)
            H = self.hessian(b, P, Q)
            if np.max(np.abs(g)) < 1e-5 * max(1.0, abs(f)) ** 0 * 1e-1:
                break
            try:
                step = np.linalg.solve(H, -g)
            except np.linalg.LinAlgError:
                break
            t = 1.0
            while t > 1e-4 and self._fg(b + t * step)[0] > f:
                t /= 2
            b = b + t * step
        f, g, g_n, P, Q = self._fg(b)
        H = self.hessian(b, P, Q)
        self.max_grad = float(np.max(np.abs(g)))
        try:
            Hi = np.linalg.inv(H)
        except np.linalg.LinAlgError:
            Hi = np.linalg.pinv(H)
        Bm = (g_n * self.w[:, None] ** 2).T @ g_n
        Vr = Hi @ Bm @ Hi
        self.b = b; self.ll = -f; self.converged = self.max_grad < 1e-3
        self.se = np.sqrt(np.clip(np.diag(Hi), 0, None)); self.rse = np.sqrt(np.clip(np.diag(Vr), 0, None))
        self.cov_robust = Vr
        n = self.w.sum()
        self.ll0 = (self.w * np.log(np.where(self.C, 1.0, 0).sum(axis=1) / self.av.sum(axis=1))).sum()
        self.k = K; self.n = n
        return self

    def hessian(self, b, P, Q):
        # information of the set-outcome logit:  sum_n w_n [ Cov_P(x) - Cov_Q(x) ]   (positive definite for the full-choice case)
        X = self.X
        mP = np.einsum("nj,njk->nk", P, X); mQ = np.einsum("nj,njk->nk", Q, X)
        CP = np.einsum("nj,njk,njl->nkl", P, X, X) - np.einsum("nk,nl->nkl", mP, mP)
        CQ = np.einsum("nj,njk,njl->nkl", Q, X, X) - np.einsum("nk,nl->nkl", mQ, mQ)
        return np.einsum("n,nkl->kl", self.w, CP - CQ)

    def table(self):
        t = pd.DataFrame({"parameter": self.names, "estimate": self.b, "se": self.se, "robust_se": self.rse})
        t["robust_t"] = t.estimate / t.robust_se
        return t

    def stats(self, label=""):
        aic = -2 * self.ll + 2 * self.k; bic = -2 * self.ll + self.k * np.log(self.n)
        return {"model": label, "N": int(round(self.n)), "K": self.k, "LL0": self.ll0, "LL": self.ll, "rho2": 1 - self.ll / self.ll0,
                "rho2_adj": 1 - (self.ll - self.k) / self.ll0, "AIC": aic, "BIC": bic, "converged": bool(self.converged)}


def lr_test(ll_r, ll_u, df):
    from scipy.stats import chi2
    s = 2 * (ll_u - ll_r)
    return s, df, float(chi2.sf(s, df))
