#!/usr/bin/env python3
"""Region model with the nesting condition imposed: the inclusive-value coefficients must lie in (0, 1] for the model to be
consistent with random utility maximisation (McFadden 1978).  The unconstrained R8 gives lam_A > 1 for the HIGH and VERY_HIGH
income groups; R8c fixes those at 1 (an offset) and re-estimates the rest; R9c adds the 43 region constants.  LR tests of the
restriction are written to tables/region_specification_search_<tag>.csv (appended rows)."""
import sys, pickle
import numpy as np, pandas as pd
from rc import *
from mnl import MNL, lr_test
import s06_region as RG

TAG = sys.argv[1] if len(sys.argv) > 1 else "prov"


def fit_constrained(D, vs, asc, start_names=None):
    g = D["h"].inc_group.values
    inter = {v: g for v in ["IV_B", "IV_A", "d1", "d2", "d3", "same_region", "commute_log"]}
    X, names = RG.design(D, vs, asc=asc, inter=inter)
    fixed = {}
    for it in range(4):
        keep = [i for i, n in enumerate(names) if n not in fixed]
        off = np.zeros(D["av"].shape)
        for n, val in fixed.items():
            off += val * X[:, :, names.index(n)]
        m = MNL(X[:, :, keep], [names[i] for i in keep], D["av"], D["C"], weights=D["w"], offset=off).fit()
        viol = [n for n, b in zip(m.names, m.b) if (n.startswith("IV_A") or n.startswith("IV_B")) and b > 1.0]
        if not viol:
            break
        for n in viol:
            fixed[n] = 1.0
    return m, fixed, X, names


def main():
    De = pickle.load(open(f"{WORK}/region_data_est_{TAG}.pkl", "rb"))
    Mods = pickle.load(open(f"{WORK}/region_models_{TAG}.pkl", "rb"))
    vs = RG.SPECS[RG.FINAL]
    rows = pd.read_csv(f"{TAB}/region_specification_search_{TAG}.csv").to_dict("records")
    rows = [r for r in rows if not str(r["model"]).startswith(("R8c", "R9c"))]
    ll8 = [r for r in rows if r["model"].startswith("R8")][0]["LL"]; ll9 = [r for r in rows if r["model"].startswith("R9")][0]["LL"]
    for lab, asc, ref in (("R8c R8 with lam <= 1 imposed", False, ll8), ("R9c R9 with lam <= 1 imposed", True, ll9)):
        m, fixed, X, names = fit_constrained(De, vs, asc)
        s = m.stats(lab); s["fixed_at_1"] = ";".join(fixed)
        lr = lr_test(m.ll, ref, len(fixed)); s.update(LR=lr[0], df=lr[1], p=lr[2], LR_reference="unconstrained (restriction test)")
        rows.append(s)
        # full parameter vector in the order of `names` (fixed values included, s.e. 0)
        b = np.array([fixed.get(n, np.nan) for n in names], float); Vfull = np.zeros((len(names), len(names)))
        k = [i for i, n in enumerate(names) if n not in fixed]
        b[k] = m.b; Vfull[np.ix_(k, k)] = m.cov_robust
        Mods["models"][lab] = (names, b, Vfull)
        t = pd.DataFrame({"parameter": names, "estimate": b, "robust_se": np.sqrt(np.diag(Vfull))})
        t["robust_t"] = np.where(t.robust_se > 0, t.estimate / t.robust_se, np.nan); t["fixed"] = [n in fixed for n in names]
        t.to_csv(f"{TAB}/region_{lab.split()[0]}_{TAG}.csv", index=False)
        print(lab, m.ll, "fixed", fixed, flush=True)
    pd.DataFrame(rows).to_csv(f"{TAB}/region_specification_search_{TAG}.csv", index=False)
    pickle.dump(Mods, open(f"{WORK}/region_models_{TAG}.pkl", "wb"))


if __name__ == "__main__":
    main()
