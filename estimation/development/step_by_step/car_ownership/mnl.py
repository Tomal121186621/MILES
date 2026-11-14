"""Multinomial logit for car ownership: alternatives 0, 1, 2, 3+ cars, reference 0. Every household variable gets its own
coefficient in alternatives 1, 2 and 3+. Maximum likelihood with analytic gradient and Hessian; robust (sandwich) s.e."""
import numpy as np


ALTS = ["1", "2", "3+"]


def design(d, vars_):
    """N x V matrix of household variables, constant first."""
    return np.column_stack([np.ones(len(d))] + [d[v].values.astype(float) for v in vars_])


def probs(b, X):
    V = X @ b.reshape(X.shape[1], 3, order="F")                    # N x 3 (alternatives 1, 2, 3+)
    V = np.column_stack([np.zeros(len(X)), V]); V -= V.max(1, keepdims=True)
    e = np.exp(V); return e / e.sum(1, keepdims=True)


def fit(d, vars_, y="cars", w=None):
    X = design(d, vars_); Y = np.eye(4)[d[y].values]; N, K = X.shape
    w = np.ones(N) if w is None else w / w.mean()

    def nll(b):
        P = probs(b, X); r = (Y[:, 1:] - P[:, 1:]) * w[:, None]
        return -(w * np.log((P * Y).sum(1))).sum(), -(X.T @ r).ravel(order="F")

    def info(b):
        P = probs(b, X); H = np.zeros((3 * K, 3 * K))            # information matrix (minus the Hessian of the LL)
        for a in range(3):
            for c in range(3):
                s = w * P[:, a + 1] * ((a == c) - P[:, c + 1])
                H[a * K:(a + 1) * K, c * K:(c + 1) * K] = (X * s[:, None]).T @ X
        return H

    # Newton-Raphson with step halving (the MNL log-likelihood is concave)
    b = np.zeros(3 * K); f, g = nll(b); conv = False
    for it in range(100):
        step = np.linalg.solve(info(b), -g); t = 1.0
        while True:
            f2, g2 = nll(b + t * step)
            if f2 <= f + 1e-10 or t < 1e-6: break
            t /= 2
        b, df, f, g = b + t * step, f - f2, f2, g2
        if np.abs(g).max() < 1e-5 or df < 1e-9: conv = np.abs(g).max() < 1e-3; break
    r = type("R", (), dict(x=b, fun=f, success=conv))
    P = probs(b, X); H = info(b)
    G = np.concatenate([X * ((Y[:, a + 1] - P[:, a + 1]) * w)[:, None] for a in range(3)], axis=1)
    Hi = np.linalg.inv(H); cov = Hi @ (G.T @ G) @ Hi
    names = [f"{v}|{a}" for a in ALTS for v in ["constant"] + list(vars_)]
    LL = -r.fun; k = 3 * K
    return dict(b=b, se=np.sqrt(np.diag(cov)), names=names, LL=LL, K=k, N=N, BIC=-2 * LL + k * np.log(N),
                conv=r.success, cond=np.linalg.cond(H), P=P)


def ll_at(res, d, vars_, y="cars"):
    """log-likelihood of an estimated model on other data (hold-out)."""
    P = probs(res["b"], design(d, vars_)); return np.log(P[np.arange(len(d)), d[y].values]).sum()
