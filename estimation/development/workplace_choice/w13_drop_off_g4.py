#!/usr/bin/env python3
"""Workplace choice: the adopted 25-term model (w09_cars.py step C0) without office share x income 125k+ (z_off_sh*g4), which is not
significant (2026-11-20).  Same estimation-half workers, sampled choice sets (seed 20261106), estimator and hold-out (validation half,
all 1,587 zones with jobs) as w09_cars.py / w10_race_fix.py.
  C0  adopted model (25 terms), re-estimated here as the reference
  D   C0 without z_off_sh*g4 (24 terms)
Robust s.e.: sandwich over the estimated parameters only (the job-type log weights g are fixed at 0 and are left out of the
sandwich; the wdc estimator's Equal.robust counts them, which inflates the s.e. of the job-mix terms; column se_wdc).
LR test of D against C0 (1 d.f.); largest coefficient change |b_D - b_C0| / se_C0.
    WDC_LOGSUM=logsum_new.npy python3 w13_drop_off_g4.py   ->  w13_fit.csv, w13_coef.csv, w13_cov_D.csv (robust covariance of D)"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import norm, chi2
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import wdc, w07_simplify as W7   # noqa: E402


def robust_free(m, e=1e-5):
    """sandwich over the free parameters (terms and mu); g fixed at 0 is not a parameter"""
    th = m.th; fr = np.where(m.free)[0]; n = len(fr); H = np.zeros((n, n))
    for i, k in enumerate(fr):
        d = np.zeros(len(th)); d[k] = e
        H[:, i] = (m.ll_grad(th + d)[1][fr] - m.ll_grad(th - d)[1][fr]) / (2 * e)
    H = (H + H.T) / 2; Sc = m.ll_grad(th, per=True)[1][:, fr]; Hi = np.linalg.inv(-H)
    cov = Hi @ (Sc.T @ Sc) @ Hi
    return [m.names[k] for k in fr], cov


def main():
    f7 = pd.read_csv(f"{HERE}/w07_fit.csv"); c0 = f7[f7.step == "S3"].terms.iloc[0].split() + ["t*car0_c"]
    d = [t for t in c0 if t != "z_off_sh*g4"]; assert len(c0) == 24 and len(d) == 23   # + mu: K 25 and 24
    st = pd.read_csv(f"{HERE}/w09_coef.csv"); st = st[st.step == "C0"].set_index("param").coef.to_dict()
    rows, coefs, M = [], [], {}
    for code, lab, tm in [("C0", "adopted model (25 terms)", c0), ("D", "C0 without office share x income 125k+", d)]:
        m = W7.Equal(tm); m.fit(np.array([st.get(n, 0.0) for n in m.names])); m.robust(); se_wdc = dict(zip(m.names, m.se))
        names, cov = robust_free(m); se = np.sqrt(np.diag(cov)); ho = m.holdout_ll()
        M[code] = m; rows.append(dict(step=code, label=lab, K=m.K, N=m.N, LL=m.LL, BIC=m.BIC, validation_LL=ho, max_grad=m.conv, terms=" ".join(tm)))
        b = dict(zip(m.names, m.th))
        for n, s in zip(names, se):
            coefs.append(dict(step=code, param=n, coef=b[n], se=s, t=b[n] / s, p=2 * norm.sf(abs(b[n] / s)), se_wdc=se_wdc[n]))
        if code == "D": pd.DataFrame(cov, index=names, columns=names).to_csv(f"{HERE}/w13_cov_D.csv")
        print(f"{code} {lab}: K {m.K} LL {m.LL:.4f} BIC {m.BIC:.2f} hold-out {ho:.4f} (max |grad| {m.conv:.1e})", flush=True)
    F = pd.DataFrame(rows); C = pd.DataFrame(coefs)
    lr = 2 * (F.LL[0] - F.LL[1]); F["LR_vs_C0"] = [np.nan, lr]; F["LR_p"] = [np.nan, chi2.sf(lr, 1)]
    F.to_csv(f"{HERE}/w13_fit.csv", index=False); C.to_csv(f"{HERE}/w13_coef.csv", index=False)
    w = C.pivot(index="param", columns="step", values="coef"); s0 = C[C.step == "C0"].set_index("param").se
    w["se_C0"] = s0; w["change_in_se"] = (w.D - w.C0) / s0
    print(f"LR test D vs C0: {lr:.3f} (1 d.f., p {chi2.sf(lr, 1):.3f}); dBIC {F.BIC[1] - F.BIC[0]:.2f}; d hold-out LL {F.validation_LL[1] - F.validation_LL[0]:.3f}")
    print(C[C.param == "z_off_sh*g4"].round(4).to_string(index=False))
    print(w.reindex(w.change_in_se.abs().sort_values(ascending=False).index).round(4).to_string())


if __name__ == "__main__":
    main()
