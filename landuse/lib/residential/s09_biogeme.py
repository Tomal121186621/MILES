#!/usr/bin/env python3
"""Re-estimation of the three final models in Biogeme (3.3.5) on exactly the same data arrays as the numpy estimator
(mnl.py), and comparison of estimates, robust standard errors and LL: tables/biogeme_<model>.csv, tables/est_compare_<model>.csv.
  dwelling  D4 (s04): 15,163 movers x 30 sampled dwellings
  zone      Z7 (s05): 10,667 RTS households x 30 sampled cells, WESML weights
  region    R8c (s06b): 15,163 movers x 44 regions, observed set outcome (PUMA spanning regions), coverage weights,
            lam_A fixed at 1 for HIGH and VERY_HIGH (offset)
Run from work/biogeme (Biogeme writes its own output files there)."""
import os, sys, pickle, json
import numpy as np, pandas as pd
from rc import *
from mnl import MNL
import biogeme.biogeme as bio
import biogeme.database as db
from biogeme.expressions import Beta, Variable, exp, log, bioMultSum
from biogeme import models

OUT = f"{WORK}/biogeme"; os.makedirs(OUT, exist_ok=True); os.chdir(OUT)


def biogeme_mnl(label, X, names, av, C, w=None, off=None, start=None):
    N, J, K = X.shape
    cols = {}
    for j in range(J):
        for k in range(K):
            cols[f"x{k}_{j}"] = X[:, j, k]
        cols[f"av{j}"] = av[:, j].astype(float)
        cols[f"c{j}"] = C[:, j].astype(float)
        if off is not None:
            cols[f"o{j}"] = off[:, j]
    cols["w"] = np.ones(N) if w is None else w
    df = pd.DataFrame(cols)
    d = db.Database(label, df)
    B = [Beta(n, 0.0 if start is None else float(start[k]), None, None, 0) for k, n in enumerate(names)]   # 2026-10-27: optional start values
    V = {j: bioMultSum([B[k] * Variable(f"x{k}_{j}") for k in range(K)] + ([Variable(f"o{j}")] if off is not None else [])) for j in range(J)}
    avd = {j: Variable(f"av{j}") for j in range(J)}
    if C.sum(axis=1).max() == 1:
        choice = sum(Variable(f"c{j}") * j for j in range(J))
        ll = models.loglogit(V, avd, choice)
    else:
        # observed set: log sum_{j in set} P_j  =  logsumexp_set(V) - logsumexp_av(V)
        num = bioMultSum([Variable(f"c{j}") * Variable(f"av{j}") * exp(V[j]) for j in range(J)])
        den = bioMultSum([Variable(f"av{j}") * exp(V[j]) for j in range(J)])
        ll = log(num) - log(den)
    b = bio.BIOGEME(d, {"log_like": ll, "weight": Variable("w")}, generate_html=False, generate_yaml=False)
    b.model_name = label
    r = b.estimate()
    bv = r.get_beta_values(); Vr = np.asarray(r.robust_variance_covariance_matrix)
    t = pd.DataFrame({"Name": names, "Value": [bv[n] for n in names],
                      "Robust std err.": [np.sqrt(Vr[r.get_parameter_index(n), r.get_parameter_index(n)]) for n in names]})
    t["Robust t-stat."] = t.Value / t["Robust std err."]
    return r, t


def compare(label, t_bg, m):
    t = m.table().set_index("parameter")
    tb = t_bg.copy()
    namecol = "Name" if "Name" in tb.columns else None
    tb = tb.set_index(namecol) if namecol else tb
    vcol = [c for c in tb.columns if c.lower().startswith("value")][0]
    scol = [c for c in tb.columns if "robust" in c.lower() and "err" in c.lower()][0]
    out = pd.DataFrame({"numpy_estimate": t.estimate, "biogeme_estimate": tb[vcol].reindex(t.index), "numpy_robust_se": t.robust_se,
                        "biogeme_robust_se": tb[scol].reindex(t.index)})
    out["abs_diff"] = (out.numpy_estimate - out.biogeme_estimate).abs()
    out.to_csv(f"{TAB}/est_compare_{label}.csv")
    tb.to_csv(f"{TAB}/biogeme_{label}.csv")
    return out


def main(which):
    rows = []
    if "dwelling" in which:
        import s04_dwelling as DW
        mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
        est = mv[mv.half == "estimation"].reset_index(drop=True)
        DW.RNG = np.random.default_rng(20261022)
        drawn = DW.sample_alts(est, pool, 30)
        sp = set(json.load(open(f"{WORK}/dwelling_final.json"))["spec"])
        X, names = DW.build_X(est, drawn[0], sp); av = drawn[1]; C = np.zeros_like(av); C[:, 0] = True
        m = MNL(X, names, av, C).fit()
        r, t = biogeme_mnl("dwelling_D4", X, names, av, C, start=m.b)
        c = compare("dwelling_D4", t, m); rows.append(dict(model="dwelling_D4", LL_numpy=m.ll, LL_biogeme=r.final_loglikelihood, max_abs_diff=c.abs_diff.max()))
        print(rows[-1], flush=True)
    if "zone" in which:
        import s05_zone as ZN
        h, _ = ZN.load_rts(); zd = ZN.zone_data(); cells = ZN.cells_of_region(zd[0], zd[1])
        est = h[h.half == "estimation"].copy()
        X, names, av, C, ok, _ = ZN.build(est, zd, cells, set(ZN.SPECS[ZN.FINAL]), 30)
        w = est.wthhfin.values[ok]; w = w / w.mean()
        m = MNL(X, names, av, C, weights=w).fit()
        r, t = biogeme_mnl("zone_Z7", X, names, av, C, w, start=m.b)
        c = compare("zone_Z7", t, m); rows.append(dict(model="zone_Z7", LL_numpy=m.ll, LL_biogeme=r.final_loglikelihood, max_abs_diff=c.abs_diff.max()))
        print(rows[-1], flush=True)
    if "region" in which:
        import s06_region as RG
        De = pickle.load(open(f"{WORK}/region_data_est_{TAG}.pkl", "rb"))
        g = De["h"].inc_group.values
        inter = {v: g for v in ["IV_B", "IV_A", "d1", "d2", "d3", "same_region", "commute_log"]}
        X, names = RG.design(De, RG.SPECS[RG.FINAL], inter=inter)
        _r = pd.read_csv(f"{TAB}/region_R8c_{TAG}.csv"); fixed = _r.loc[_r.iloc[:, -1].astype(str) == "True", "parameter"].tolist()   # lambdas fixed at 1 by s06b
        off = sum(X[:, :, names.index(n)] for n in fixed)
        keep = [i for i, n in enumerate(names) if n not in fixed]
        Xk = X[:, :, keep]; nk = [names[i] for i in keep]
        m = MNL(Xk, nk, De["av"], De["C"], weights=De["w"], offset=off).fit()
        r, t = biogeme_mnl("region_R8c", Xk, nk, De["av"], De["C"], De["w"], off, start=m.b)
        c = compare("region_R8c", t, m); rows.append(dict(model="region_R8c", LL_numpy=m.ll, LL_biogeme=r.final_loglikelihood, max_abs_diff=c.abs_diff.max()))
        print(rows[-1], flush=True)
    f = f"{TAB}/biogeme_summary.csv"
    old = pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()
    new = pd.DataFrame(rows)
    if len(old): old = old[~old.model.isin(new.model)]
    pd.concat([old, new]).to_csv(f, index=False)


if __name__ == "__main__":
    # 2026-10-27: --acc <accessibility csv> --tag <final|prov>: the data of the final models (s05 / s06 read ACC and TAG at import)
    a = sys.argv[1:]; ACC = a[a.index("--acc") + 1] if "--acc" in a else f"{WORK}/accessibility_provisional_2016.csv"; TAG = a[a.index("--tag") + 1] if "--tag" in a else "prov"
    which = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))] or ["dwelling", "zone", "region"]
    sys.argv = [sys.argv[0], ACC, TAG]
    main(which)
