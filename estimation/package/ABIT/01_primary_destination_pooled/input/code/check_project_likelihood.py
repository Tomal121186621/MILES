#!/usr/bin/env python3
"""The project's own likelihood (estimate_fullset_taz.Chunk, the engine of dp_pooled.py / pool_core.py) at the reference
estimates, per purpose and per number of home configurations, for comparison with the Biogeme evaluation.

    python3 check_project_likelihood.py [--at full|article]        (project Python with torch)

Local (effective) coefficients of purpose p as pool_core.ParEngine.loc_v: every coefficient except theta times SCALE_p.
"""
import os, sys, argparse
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd, torch
import d_primary                        # noqa: F401  (copy: adds the features lnd_male, lnd_hh1 to dc_model)
import estimate_fullset_taz as FS       # noqa: E402
import dc_model as M, dc_common as C    # noqa: E402

P = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
LIN = ["d_0_1", "d_1_2", "d_2_5", "d_5_10", "d_10_20", "d_20_50", "d_50_inf", "intra", "bc", "dcz", "cbd", "va", "othst", "lnretden", "mix",
       "xcounty", "xstate", "lnd_car0", "lnd_car1", "lnd_worker", "lnd_kid", "lnd_senior", "lnd_child", "lnd_male", "lnd_hh1", "lnd_am", "lnd_pm",
       "lnd_ev", "lnd_multi", "cgt"]
COMPS = {"SHOPPING": ["pop", "off"], "RECREATION": ["pop", "off", "stu"], "ACCOMPANY": ["pop", "off", "oth", "stu"], "OTHER": ["off", "oth"]}
GROUP = {"cgt": {"SHOPPING": "S+O", "OTHER": "S+O"}, "mu_size": {"SHOPPING": "S+R+O", "RECREATION": "S+R+O", "OTHER": "S+R+O"}}
SHARED = {q for q in LIN if q.startswith(("d_", "lnd_")) or q in ("xcounty", "xstate")}


def local(p, x):
    sc = x.get(f"scale|{p}", 1.0); out = []
    for q in LIN + [f"theta_{c}" for c in COMPS[p]] + ["mu_size"]:
        if q == "d_50_inf": v = 0.0
        elif q in SHARED: v = x[f"shared|{q}"]
        elif q in GROUP and p in GROUP[q]: v = x[f"{GROUP[q][p]}|{q}"]
        else: v = x[f"{p}|{q}"]
        out.append(v if q.startswith("theta_") else v * sc)
    return np.array(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--at", default="full", choices=["full", "article"]); ap.add_argument("--half", default="estimation")
    a = ap.parse_args()
    r = pd.read_csv(f"{HERE}/../../model/reference_estimates.csv"); r = r[r.project_name.notna()]
    x = dict(zip(r.project_name, r.coefficient if a.at == "full" else r.article_coefficient))
    sk = C.skims(); tot = 0.0; rows = []
    for p in P:
        rec, cand, cfg = FS.load(f"{p}_primary", a.half)
        spec = M.Spec("pool", LIN, "ret", COMPS[p]); th = torch.tensor(local(p, x))
        ncf = rec.rec.map(cfg.groupby("rec").size())
        for g in sorted(ncf.unique()):
            rg = rec[ncf.values == g]; ll = 0.0
            for i in range(0, len(rg), FS.CHUNK):
                sub = rg.iloc[i:i + FS.CHUNK]
                ch = FS.Chunk(sub, cand[cand.rec.isin(sub.rec.values)], cfg, spec, p, sk)
                with torch.no_grad(): ll += float(ch.ll(th, spec).sum())
            rows.append(dict(purpose=p, n_cfg=int(g), N=len(rg), LL=ll)); tot += ll
            print(rows[-1], flush=True)
    d = pd.DataFrame(rows); print(d.groupby("n_cfg")[["N", "LL"]].sum()); print(f"{a.half}: LL at the {a.at} estimates = {tot:.4f}")
