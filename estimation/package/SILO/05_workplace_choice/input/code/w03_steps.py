#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/workplace/w03_steps.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Workplace choice, step 0 (existing models) and step 3 (main effects in the order of the literature review).
All models on the estimation half; fit compared by BIC on the sampled choice sets and by the full-set log-likelihood per worker
on the estimation half (all 1,587 zones; comparable with the original SILO rule, which has no estimated coefficients).
The validation half is not used here (step 6).   Outputs: w03_fit.csv, w03_coef.csv.   Usage: python3 w03_steps.py"""
import os
import numpy as np, pandas as pd
import wdc

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.environ.get("MILES_WORKSPACE", "")
TPER = ["t*female", "t*young", "t*old", "t*g1", "t*g3", "t*g4", "t*lic", "t*hhs", "t*rurh", "t*kids", "t*w2"]
CURRENT = (["t", "lt", "t*female", "t*young", "t*old", "t*g1", "t*g3", "t*g4", "t*lic", "t*hhs", "t*rurh", "ls", "intra", "cc", "cs",
            "cs*g4", "cs*hva", "dcw", "reg_bc", "reg_mopg", "reg_dcr", "reg_nvc", "reg_nvo", "reg_mdo", "reg_oth",
            "z_off_sh*g1", "z_off_sh*g4", "z_ret_sh*young", "z_ind_sh*female", "z_hiearn", "z_hiearn*g1", "z_hiearn*g3", "z_hiearn*g4"])
STEPS = [("W1", "size term only (four job types)", [], False),
         ("W2", "+ car time and ln(1 + time)", ["t", "lt"], False),
         ("W3", "+ mode-choice logsum", ["t", "lt", "ls"], False),
         ("W4", "+ same zone, other county, other state", ["t", "lt", "ls", "intra", "cc", "cs"], False),
         ("W5", "+ time x person", ["t", "lt", "ls", "intra", "cc", "cs"] + TPER, False),
         ("W6", "+ size weights by income group", ["t", "lt", "ls", "intra", "cc", "cs"] + TPER, True),
         ("W7", "+ accessibility of the workplace", ["t", "lt", "ls", "intra", "cc", "cs"] + TPER + ["accw"], True),
         ("W8", "+ DC workplace (home outside DC)", ["t", "lt", "ls", "intra", "cc", "cs"] + TPER + ["accw", "dcw"], True)]


def silo_rule():
    """original SILO rule at zone level: P(j) proportional to f(t_hj) x jobs_j, f = 'Utility' column of the survey commute-time
    curve (0 beyond 200 min, as in the code; a floor of 1e-12 keeps the log finite)"""
    f = pd.read_csv(f"{V}/2_silo/input/hts_work_tripLengthFrequencyDistribution.csv").set_index("TravelTime").Utility
    fv = np.zeros(201); fv[f.index.values] = f.values
    P = wdc.persons(True); tot = 0.0; zero = 0; jobs = wdc.JOBS[wdc.AZ].sum(1)
    for s in range(0, len(P["g"]), 500):
        h = P["hidx"][s:s + 500]; t = np.clip(np.rint(np.maximum(wdc.TT[h][:, wdc.AZ], 1)).astype(int), 0, 201)
        w = np.where(t <= 200, fv[np.minimum(t, 200)], 0) * jobs[None, :]
        pr = w / w.sum(1, keepdims=True); ch = np.searchsorted(wdc.AZ, P["widx"][s:s + 500])
        p = pr[np.arange(len(h)), ch]; zero += int((p <= 0).sum()); tot += np.log(np.maximum(p, 1e-12)).sum()
    return tot / len(P["g"]), zero


def run(code, label, terms, seg, rows, coefs):
    m = wdc.Model(terms, seg=seg).fit(); m.robust(); m.holdout_ll(est=True)
    rows.append(dict(step=code, label=label, K=m.K, LL=m.LL, BIC=m.BIC, fullset_LL_per_worker=m.FS_per, max_grad=m.conv, cond=m.cond))
    for n, b, s, t in m.table(): coefs.append(dict(step=code, param=n, coef=b, se=s, t=t))
    print(f"{code} {label}: K {m.K} LL {m.LL:.1f} BIC {m.BIC:.1f} full-set {m.FS_per:.4f} grad {m.conv:.3g}", flush=True)
    return m


def main():
    rows, coefs = [], []
    ll, zero = silo_rule()
    rows.append(dict(step="S0a", label="original SILO rule: f(time) x jobs, survey commute-time curve", K=0, fullset_LL_per_worker=ll, note=f"{zero} chosen zones with probability 0"))
    print("S0a", ll, zero)
    run("S0b", "original rule re-estimated: car time + size term", ["t"], False, rows, coefs)
    run("S0c", "current model (article), same data handling", CURRENT, False, rows, coefs)
    for code, label, terms, seg in STEPS: run(code, label, terms, seg, rows, coefs)
    pd.DataFrame(rows).to_csv(f"{HERE}/w03_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/w03_coef.csv", index=False)


if __name__ == "__main__":
    main()
