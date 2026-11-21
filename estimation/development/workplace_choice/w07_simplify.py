#!/usr/bin/env python3
"""Workplace choice simplification (2026-11-17, user: simplify).  Same workers, sampled choice sets (seed 20261106), estimator and
hold-out (validation half, full choice set) as w06_respec.py; each step removes one group from the previous one:
  B   w06 final model (35)
  S1  size term with equal weights for all job types: mu ln(total jobs) (job-type log weights held at 0)
  S2  S1 without the six area dummies (Baltimore City, Montgomery / Prince George's, Northern Virginia x2, rest of MD, other states)
  S3  S2 without the time interactions that are not significant (children, two or more workers)
  S4  S3 without the job-type share x person terms (office share x income <40k / 125k+, retail share x age <30, industrial x woman)
    WDC_LOGSUM=logsum_new.npy python3 w07_simplify.py   ->  w07_fit.csv, w07_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import norm
from scipy.optimize import minimize
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import wdc   # noqa: E402


class Equal(wdc.Model):
    """size term with the job-type log weights held at 0 (ln of total jobs)"""
    def fit(self, th0=None):
        n = len(self.names); K = len(self.terms)
        th0 = np.r_[np.zeros(K), 0.8, np.zeros(3)] if th0 is None else th0; th0[K + 1:] = 0.0
        free = np.r_[np.ones(K + 1, bool), np.zeros(3, bool)]
        def f(x):
            th = np.r_[x, np.zeros(3)]; ll, g = self.ll_grad(th); return -ll, -g[free]
        r = minimize(f, th0[free], jac=True, method="L-BFGS-B", bounds=[(None, None)] * K + [(0.01, 3)], options={"maxiter": 5000, "ftol": 1e-12, "gtol": 1e-6})
        self.th = np.r_[r.x, np.zeros(3)]; self.LL = -float(r.fun); self.conv = float(np.abs(self.ll_grad(self.th)[1][free]).max())
        self.K = int(free.sum()); self.BIC = -2 * self.LL + self.K * np.log(self.N); self.free = free
        return self

    def robust(self):
        super().robust(); return self


def main():
    f6 = pd.read_csv(f"{HERE}/w06_fit.csv"); terms = f6[f6.step == "B"].terms.iloc[0].split()
    c6 = pd.read_csv(f"{HERE}/w06_coef.csv"); c6 = c6[c6.step == "B"].drop_duplicates("param", keep="last").set_index("param").coef
    AREA = [t for t in terms if t.startswith("reg_")]; NS = ["t*kids_c", "t*w2_c"]; SH = ["z_off_sh*g1", "z_off_sh*g4", "z_ret_sh*young", "z_ind_sh*female"]
    steps = [("B", "w06 final model", terms, wdc.Model), ("S1", "+ size: equal weights (ln total jobs)", terms, Equal)]
    t2 = [t for t in terms if t not in AREA]; t3 = [t for t in t2 if t not in NS]; t4 = [t for t in t3 if t not in SH]
    steps += [("S2", "S1 without area dummies", t2, Equal), ("S3", "S2 without the n.s. time interactions", t3, Equal), ("S4", "S3 without job-type share x person", t4, Equal)]
    rows, coefs = [], []
    for code, lab, tm, cls in steps:
        m = cls(tm); th0 = np.array([c6.get(n, 0.0) if n != "mu" else c6.get("mu", 0.8) for n in m.names]); m.fit(th0); m.robust(); ho = m.holdout_ll()
        rows.append(dict(step=code, label=lab, K=m.K, N=m.N, LL=m.LL, BIC=m.BIC, validation_LL=ho, terms=" ".join(tm)))
        for n, b, s, t in m.table():
            if cls is Equal and n.startswith("g_"): continue
            coefs.append(dict(step=code, param=n, coef=b, se=s, t=t, p=2 * norm.sf(abs(t))))
        print(f"{code} {lab}: K {m.K} LL {m.LL:.2f} BIC {m.BIC:.1f} hold-out {ho:.2f}", flush=True)
        pd.DataFrame(rows).to_csv(f"{HERE}/w07_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/w07_coef.csv", index=False)


if __name__ == "__main__":
    main()
