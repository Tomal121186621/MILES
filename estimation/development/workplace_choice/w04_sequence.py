#!/usr/bin/env python3
"""Workplace choice, model development for reporting: blocks added in a fixed order to the size-only model; a block is kept when
the likelihood-ratio test is significant at 5 %, BIC falls and the signs are the expected ones.  Each step starts from the
estimates of the current model and ends with Newton steps (wdc.Model.fit), so every reported model has converged (max |gradient|
reported); a block whose estimates reach a bound of the estimator (size weights |g| or |d| near 10) is not kept, as its
maximum is not finite.  Estimation half (chosen + 99 sampled zones); the validation half (all zones) is used once, for the final model and,
for comparison, the current model.
  W1 size term   W2 car time, ln(1 + time)   W3 mode-choice logsum   W4 same zone, other county, other state
  W5 time x person (gender, age, income group, licence, household size, children, two or more workers, rural home); the person
     variables centred at their estimation-half means (wdc 'x_c'), so time is the effect at the mean person (same fit)
  W6 size weights by income group   W7 non-work accessibility of the workplace   W8 DC workplace (home outside DC)
  W9 area of the workplace (Baltimore City, Montgomery/Prince George's, Northern Virginia, other Maryland, other; no DC area
     dummy: collinear with the DC workplace term W8, collinearity/silo_notes.md)
  W10 workplace composition (high-earning jobs, office / retail / industrial shares) x person
    python3 estimation/development/workplace_choice/w04_sequence.py   ->  w04_fit.csv, w04_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from scipy.stats import chi2
import wdc
from w03_steps import TPER, CURRENT

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/workplace"   # results of this step (data); CODE = this folder
SIGN = {"ls": 1, "intra": 1, "cc": -1, "cs": -1, "t*lic_c": 1}
TPERC = [f"{x}_c" for x in TPER]
BLOCKS = [("W2", "+ car time and ln(1 + time)", ["t", "lt"], False),
          ("W3", "+ mode-choice logsum", ["ls"], False),
          ("W4", "+ same zone, other county, other state", ["intra", "cc", "cs"], False),
          ("W5", "+ time $\\times$ person (gender, age, income, licence, household size, children, workers, rural home)", TPERC, False),
          ("W6", "+ size weights by income group", [], True),
          ("W7", "+ non-work accessibility of the workplace", ["accw"], False),
          ("W8", "+ DC workplace (home outside DC)", ["dcw"], False),
          ("W9", "+ area of the workplace", ["reg_bc", "reg_mopg", "reg_nvc", "reg_nvo", "reg_mdo", "reg_oth"], False),
          ("W10", "+ workplace composition $\\times$ person", ["z_off_sh*g1", "z_off_sh*g4", "z_ret_sh*young", "z_ind_sh*female", "z_hiearn",
                                                              "z_hiearn*g1", "z_hiearn*g3", "z_hiearn*g4"], False)]


def start(prev, m):
    if prev is None: return None
    d = dict(zip(prev.names, prev.th)); th = np.array([d.get(n, 0.0) for n in m.names]); th[m.names.index("mu")] = d.get("mu", 0.8)
    return th


def main():
    rows, coefs = [], []

    def run(code, label, terms, seg, prev, dec_fn=None):
        m = wdc.Model(terms, seg=seg); m.fit(start(prev, m)); m.robust()
        r = dict(step=code, label=label, K=m.K, LL=m.LL, BIC=m.BIC, max_grad=m.conv)
        if prev is not None and m.K > prev.K:
            lr = 2 * (m.LL - prev.LL); df = m.K - prev.K; r.update(LR=lr, df=df, p=float(chi2.sf(lr, df)))
        bad = [n for n, b in zip(m.names, m.th) if n in SIGN and np.sign(b) != SIGN[n]]
        atb = [n for n, b in zip(m.names, m.th) if (n.startswith(("g_", "d_")) and abs(b) > 9.9) or (n == "mu" and (b < 0.011 or b > 2.99))]
        r["decision"] = dec_fn(r, bad, atb) if dec_fn else "kept"
        rows.append(r)
        for n, b, s, t in m.table(): coefs.append(dict(step=code, param=n, coef=b, se=s, t=t))
        print(f"{code} K {m.K} LL {m.LL:.1f} BIC {m.BIC:.1f} grad {m.conv:.2g} {r['decision']}", flush=True)
        return m, r

    rule = lambda r, bad, atb: ("kept" if r.get("p", 1) < 0.05 and r["BIC"] < cur.BIC and not bad and not atb else
                           "not kept: estimate at bound" if atb else "not kept: sign" if bad else "not kept: BIC" if r["BIC"] >= cur.BIC else "not kept: LR")
    cur, _ = run("W1", "size term only (four job types)", [], False, None); terms, seg = [], False
    for code, label, add, sg in BLOCKS:
        m, r = run(code, label, terms + add, seg or sg, cur, rule)
        if r["decision"] == "kept": cur, terms, seg = m, terms + add, seg or sg
    m, r = run("final", "final model", terms, seg, cur); r["terms"] = " ".join(terms); r["seg"] = seg
    r["validation_LL"] = m.holdout_ll(); r["validation_LL_per_worker"] = m.HO_per
    c = wdc.Model(CURRENT); c.fit(); r0 = dict(step="record", label="current model (article), same data handling", K=c.K, LL=c.LL, BIC=c.BIC, max_grad=c.conv)
    r0["validation_LL"] = c.holdout_ll(); rows.append(r0)
    print(f"final validation {r['validation_LL']:.1f}; current model {r0['validation_LL']:.1f} (grad {c.conv:.2g})", flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/w04_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/w04_coef.csv", index=False)


if __name__ == "__main__":
    main()
