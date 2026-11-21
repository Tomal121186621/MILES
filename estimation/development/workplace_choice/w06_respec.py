#!/usr/bin/env python3
"""Workplace choice, 2026-11-13: the final model of w04_sequence.py re-estimated after the review (C2: the non-work accessibility
of the workplace zone entered at W7 with +0.21 and ended at -0.089, t -3.1, in the final model; a base term with the wrong sign and
|t| > 2 is dropped by the protocol; M7: the high-wage share block is a composition proxy held at its 2017 value in every forecast
year and is kept only if BIC and hold-out LL support it).  Same workers, same sampled choice sets (wdc.Model, seed 20261106), same
estimator and robust s.e.; hold-out = validation half on the full choice set.
  A  w04 final model (reference)
  B  A without the non-work accessibility of the workplace zone
  C  B without the high-wage share block (z_hiearn, x <40k, x 75-125k, x 125k+)
  D  A without the high-wage share block (accessibility kept): does the accessibility sign depend on the block?
Final = B if BIC(B) < BIC(C) and hold-out LL(B) > hold-out LL(C), else C.  Signs of every term of the final model are listed.
The engine's uncentred time coefficient b_t - sum_x b_tx m_x (e03_workplace_files.py) is reported for the final model.
    WDC_LOGSUM=logsum_new.npy python3 w06_respec.py   ->  w06_fit.csv, w06_coef.csv, w06_signs.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2, norm
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import wdc   # noqa: E402

HI = ["z_hiearn", "z_hiearn*g1", "z_hiearn*g3", "z_hiearn*g4"]
# expected signs of the base terms (protocol: a base term with the wrong sign and |t| > 2 is dropped); interactions: no rule
EXP = {"t": -1, "lt": -1, "intra": 1, "cc": -1, "cs": -1, "accw": 1, "mu": 1}


def main():
    f4 = pd.read_csv(f"{HERE}/w04_fit.csv"); fin = f4[f4.step == "final"].iloc[0]; terms = fin.terms.split()
    c4 = pd.read_csv(f"{HERE}/w04_coef.csv"); c4 = c4[c4.step == "final"].drop_duplicates("param", keep="last").set_index("param").coef
    rows, coefs, M = [], [], {}

    def run(code, label, tm):
        m = wdc.Model(tm); m.fit(np.array([c4.get(n, 0.0) if n != "mu" else c4.get("mu", 0.8) for n in m.names])); m.robust()
        ho = m.holdout_ll(); r = dict(step=code, label=label, K=m.K, N=m.N, LL=m.LL, BIC=m.BIC, max_grad=m.conv, cond=m.cond, validation_LL=ho,
                                      validation_LL_per_worker=m.HO_per, terms=" ".join(tm)); rows.append(r); M[code] = m
        for n, b, s, t in m.table(): coefs.append(dict(step=code, param=n, coef=b, se=s, t=t, p=2 * norm.sf(abs(t))))
        print(f"{code} K {m.K} LL {m.LL:.2f} BIC {m.BIC:.1f} hold-out {ho:.2f} grad {m.conv:.2g}", flush=True); return m, r

    mA, rA = run("A", "w04 final model", terms)
    assert abs(mA.LL - fin.LL) < 0.05, (mA.LL, fin.LL)
    mB, rB = run("B", "A without the non-work accessibility of the workplace zone", [t for t in terms if t != "accw"])
    mC, rC = run("C", "B without the high-wage share block", [t for t in terms if t != "accw" and t not in HI])
    mD, rD = run("D", "A without the high-wage share block (accessibility kept)", [t for t in terms if t not in HI])
    for a, b in (("A", "B"), ("B", "C"), ("A", "D")):
        lr = 2 * (M[a].LL - M[b].LL); df = M[a].K - M[b].K
        rows[[r["step"] for r in rows].index(b)].update(LR_vs=a, LR=lr, df=df, p=float(chi2.sf(lr, df)))
    keep_hi = rB["BIC"] < rC["BIC"] and rB["validation_LL"] > rC["validation_LL"]
    final, lab = ("B", "final model: B (high-wage block kept: lower BIC and higher hold-out LL than C)") if keep_hi else ("C", "final model: C (high-wage block dropped)")
    m = M[final]; r = dict(rows[[x["step"] for x in rows].index(final)]); r.update(step="final", label=lab); rows.append(r)
    for n, b, s, t in m.table(): coefs.append(dict(step="final", param=n, coef=b, se=s, t=t, p=2 * norm.sf(abs(t))))
    # signs of the final model's terms
    sg = []
    for n, b, s, t in m.table():
        e = EXP.get(n); sg.append(dict(param=n, coef=b, se=s, t=t, expected=e, wrong_sign_t_gt_2=bool(e is not None and np.sign(b) != e and abs(t) > 2)))
    S = pd.DataFrame(sg); S.to_csv(f"{HERE}/w06_signs.csv", index=False)
    print("final:", final, "| base terms with the wrong sign and |t| > 2:", S[S.wrong_sign_t_gt_2].param.tolist(), flush=True)
    # engine time coefficient (uncentred) for the final model
    cf = dict(zip(m.names, m.th)); shift = sum(v * wdc.MEAN[p[2:-2]] for p, v in cf.items() if p.startswith("t*") and p.endswith("_c"))
    print(f"b_t centred {cf['t']:.4f} -> engine (uncentred) {cf['t'] - shift:.4f} (shift {shift:.4f})", flush=True)
    rows.append(dict(step="record", label="current model (article), same data handling", K=int(f4[f4.step == 'record'].K.iloc[0]), LL=float(f4[f4.step == 'record'].LL.iloc[0]),
                     BIC=float(f4[f4.step == 'record'].BIC.iloc[0]), validation_LL=float(f4[f4.step == 'record'].validation_LL.iloc[0])))
    rows[-1]["b_t_engine_final"] = cf["t"] - shift
    pd.DataFrame(rows).to_csv(f"{HERE}/w06_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/w06_coef.csv", index=False)
    print(pd.DataFrame(coefs).query("step == 'final'").round(4).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
