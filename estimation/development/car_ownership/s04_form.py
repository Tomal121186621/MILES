#!/usr/bin/env python3
"""Car ownership, step 4: functional form, on the M6 variables. Estimation sample only.
(a) income: ln income straight line against piecewise linear in ln income (knots $25k, $50k, $100k);
(b) multinomial logit against ordered logit (one latent car propensity, three thresholds);
(c) unweighted against weighted by the PUMS household weight.
Outputs: s04_income.csv, s04_ordered.csv, s04_weights.csv.   Usage: python3 estimation/development/car_ownership/s04_form.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from mnl import fit, probs, design

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
REST = ["workers", "nonworking_adults", "children", "any_65plus", "single_person", "sfd", "multifamily", "bedrooms", "ln_density", "acc_gain"]
KN = np.log(np.array([25000, 50000, 100000]) / 50000)


def pieces(d):
    x = d.ln_income.values
    d["inc_lt25"] = np.minimum(x, KN[0]); d["inc_25_50"] = np.clip(x - KN[0], 0, KN[1] - KN[0])
    d["inc_50_100"] = np.clip(x - KN[1], 0, KN[2] - KN[1]); d["inc_gt100"] = np.maximum(x - KN[2], 0)
    return ["inc_lt25", "inc_25_50", "inc_50_100", "inc_gt100"]


def ordered(d, vars_):
    """ordered logit: P(cars <= k) = F(tau_k - x b), k = 0, 1, 2"""
    X = d[vars_].values.astype(float); y = d.cars.values; N, K = X.shape

    def nll(p):
        b, c = p[:K], p[K:]; tau = np.cumsum(np.r_[c[0], np.exp(c[1:])])
        cdf = np.column_stack([np.zeros(N), expit(tau[None, :] - (X @ b)[:, None]), np.ones(N)])
        pr = np.clip(cdf[np.arange(N), y + 1] - cdf[np.arange(N), y], 1e-300, None); return -np.log(pr).sum()

    r = minimize(nll, np.r_[np.zeros(K), -1.0, 0.0, 0.0], method="BFGS", options={"maxiter": 5000, "gtol": 1e-5})
    return dict(LL=-r.fun, K=K + 3, BIC=2 * r.fun + (K + 3) * np.log(N), b=r.x[:K], conv=r.success)


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    for c in ["workers", "nonworking_adults", "children"]: d[c] = d[c].clip(upper=6)
    P = pieces(d)
    lin = fit(d, REST + ["ln_income"]); pw = fit(d, REST + P)
    rows = [dict(form="ln income, straight line (M6)", K=lin["K"], LL=lin["LL"], BIC=lin["BIC"]),
            dict(form="ln income, piecewise (knots 25k, 50k, 100k)", K=pw["K"], LL=pw["LL"], BIC=pw["BIC"])]
    for n, b, s in zip(pw["names"], pw["b"], pw["se"]):
        if n.split("|")[0].startswith("inc_"): rows.append(dict(form=f"  slope {n}", coef=b, t=b / s))
    pd.DataFrame(rows).to_csv(f"{HERE}/s04_income.csv", index=False); print(pd.DataFrame(rows).round(3).to_string())
    o = ordered(d, REST + P)
    O = pd.DataFrame([dict(model="multinomial logit (piecewise income)", K=pw["K"], LL=pw["LL"], BIC=pw["BIC"]),
                      dict(model="ordered logit (piecewise income)", K=o["K"], LL=o["LL"], BIC=o["BIC"], conv=o["conv"])])
    O.to_csv(f"{HERE}/s04_ordered.csv", index=False); print(O.round(1).to_string())
    w = fit(d, REST + P, w=d.w.values.astype(float))
    W = []
    for n, b, s, bw, sw in zip(pw["names"], pw["b"], pw["se"], w["b"], w["se"]):
        W.append(dict(param=n, unweighted=b, se_u=s, weighted=bw, se_w=sw, z_diff=(bw - b) / np.sqrt(sw ** 2 + s ** 2)))
    W = pd.DataFrame(W); W.to_csv(f"{HERE}/s04_weights.csv", index=False)
    print(W.round(3).to_string()); print("max |z| of differences:", W.z_diff.abs().max().round(2), " n |z|>1.96:", (W.z_diff.abs() > 1.96).sum())
    # unweighted model: does it reproduce the population (weighted) car shares?
    for nm, r in [("unweighted", pw), ("weighted", w)]:
        Pm = probs(r["b"], design(d, REST + P))
        print(nm, "predicted weighted shares", np.round((Pm * d.w.values[:, None]).sum(0) / d.w.sum() * 100, 2))
    print("observed weighted shares", np.round(np.bincount(d.cars, weights=d.w, minlength=4) / d.w.sum() * 100, 2))


if __name__ == "__main__":
    main()
