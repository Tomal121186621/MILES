#!/usr/bin/env python3
"""Biogeme check of the TAZ-variant destination models (2026-10-28).

    ~/.venvs/biogeme/bin/python activity/lib/tasha_estimation/biogeme_dc_taz.py [SEGMENT,...]

Reads tasha_estimation/work/bio_<segment>_taz.parquet / .json (estimate_dc_taz.py: the sampled sets of the estimation, the
variables of the final model per anchor configuration) and maximises the location-mixture log-likelihood
    LL = sum_n ln sum_c w_nc [ sum_j b_nj av_nj exp(V_ncj + c_nj) / sum_j av_nj exp(V_ncj + c_nj) ],
    V_ncj = mu ln(1 + x_nj,base + sum_k exp(theta_k) x_nj,k) + sum_k beta_k x_ncjk,
with Biogeme 3.3.5 (as destination_choice/estimate_biogeme.py: default algorithm, robust s.e.), started at the PyTorch
estimates.  Output: tasha_estimation/results/biogeme_<segment>_taz.csv, biogeme_<segment>_taz_stats.json, biogeme_check_taz.csv.
Threads: 4; second derivatives 'never' (BFGS; the analytical Hessian of the mixture exhausts memory), so Biogeme reports
no s.e. here and the check is on LL and the estimates; started at the warm start of the PyTorch fit (pooled Biogeme F).
(biogeme.toml in work/biogeme_taz).
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, os, sys
import numpy as np
import pandas as pd

SUF = os.environ.get("TAZ_BIO_SUFFIX", "")   # "_sub": the subsample check of estimate_dc_taz.py biosub
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; WORK = f"{HERE}/work"; RES = f"{HERE}/results"; BW = f"{WORK}/biogeme_taz"


def estimate(seg):
    import biogeme.database as db
    import biogeme.biogeme as bio
    from biogeme.expressions import Beta, Variable, exp, log, MultipleSum
    meta = json.load(open(f"{WORK}/bio_{seg}_taz{SUF}.json")); df = pd.read_parquet(f"{WORK}/bio_{seg}_taz{SUF}.parquet")
    J, Kc = meta["J"], meta["Kc"]; lin = meta["linear"]; dep = set(meta["dep"]); base = meta["size_base"]; comps = meta["size_comps"]
    # start: the warm start of the PyTorch fit (pooled Biogeme F of the model of record; lnd_multi 0), not the PyTorch optimum
    pb = pd.read_csv(f"{os.path.dirname(HERE)}/destination_choice/results/biogeme_{seg}.csv"); start = {**dict(zip(pb.Name, pb.Value)), "lnd_multi": 0.0}
    d = db.Database(seg, df)
    B = {k: Beta(k, start.get(k, 0.0), None, None, 0) for k in lin}
    TH = {c: Beta(f"theta_{c}", start.get(f"theta_{c}", 0.0), -30, 15, 0) for c in comps}
    MU = Beta("mu_size", start.get("mu_size", 1.0), 0, 3, 0)
    terms = []
    for c in range(Kc):
        num, den = [], []
        for j in range(J):
            S = Variable(f"{base}_{j}") + sum([exp(TH[k]) * Variable(f"{k}_{j}") for k in comps], 0) if comps else Variable(f"{base}_{j}")
            V = MU * log(1 + S) + sum([B[k] * Variable(f"{k}_{j}_c{c}" if k in dep else f"{k}_{j}") for k in lin], 0) + Variable(f"lnc_{j}")
            e = exp(V); num.append(Variable(f"b_{j}") * e); den.append(Variable(f"av_{j}") * e)
        terms.append(Variable(f"w_c{c}") * MultipleSum(num) / MultipleSum(den))
    ll = log(MultipleSum(terms) if len(terms) > 1 else terms[0])
    os.makedirs(BW, exist_ok=True); cwd = os.getcwd(); os.chdir(BW)
    try:
        m = bio.BIOGEME(d, ll); m.model_name = f"dc_{seg}_taz{SUF}"
        r = m.estimate()
    finally:
        os.chdir(cwd)
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))
    t.to_csv(f"{RES}/biogeme_{seg}_taz{SUF}.csv", index=False)
    stats = dict(segment=seg, LL=float(r.final_loglikelihood), N=int(len(df)), K=int(r.number_of_free_parameters), J=J, Kc=Kc,
                 converged=bool(r.algorithm_has_converged), gradient_norm=float(r.gradient_norm), AIC=float(r.akaike_information_criterion),
                 BIC=float(r.bayesian_information_criterion))
    for k in ("smallest_eigenvalue", "condition_number"):
        try: stats[k] = float(getattr(r, k))
        except Exception: stats[k] = None
    json.dump(stats, open(f"{RES}/biogeme_{seg}_taz{SUF}_stats.json", "w"), indent=1)
    print(f"{seg}: LL {stats['LL']:.3f} K {stats['K']} converged {stats['converged']}", flush=True)
    return stats, t


def main(segs):
    rows = []
    for s in segs:
        if not os.path.exists(f"{WORK}/bio_{s}_taz{SUF}.parquet"): print(f"{s}: no data"); continue
        if os.path.exists(f"{RES}/biogeme_{s}_taz{SUF}_stats.json") and "--force" not in sys.argv:
            st = json.load(open(f"{RES}/biogeme_{s}_taz{SUF}_stats.json")); t = pd.read_csv(f"{RES}/biogeme_{s}_taz{SUF}.csv")
        else: st, t = estimate(s)
        kind = "cx" if s.endswith("primary") else "seq"
        if SUF:
            pt = pd.read_csv(f"{RES}/{kind}_estimates_{s}_taz{SUF}.csv").set_index("param"); f = dict(LL=float(pt.LL.iloc[0]))
        else:
            pt = pd.read_csv(f"{RES}/{kind}_estimates_taz.csv"); pt = pt[pt.segment == s].set_index("param")
            tt = pd.read_csv(f"{RES}/{kind}_tests_taz.csv").set_index("segment"); f = dict(LL=float(tt.loc[s, "LL_FX" if kind == "cx" else "LL"]))
        name = "Name" if "Name" in t else t.columns[0]; bt = t.set_index(name)
        common = [p for p in pt.index if p in bt.index]
        dv = np.abs(pt.value[common].values - bt.Value[common].values); ds = np.abs(pt.rob_se[common].values - bt["Robust std err."][common].values) if "Robust std err." in bt else np.full(len(common), np.nan)
        rows.append(dict(segment=s, sample="subsample 1,500" if SUF else "full", N=int(st["N"]), LL_torch=f["LL"], LL_biogeme=st["LL"], dLL=st["LL"] - f["LL"], max_abs_dcoef=float(dv.max()),
                         max_abs_dcoef_over_se=float((dv / pt.rob_se[common].values).max()), max_abs_dse=float(np.nanmax(ds)) if np.isfinite(ds).any() else np.nan, converged=st["converged"],
                         gradient_norm=st["gradient_norm"]))
        print(rows[-1], flush=True); pd.DataFrame([rows[-1]]).to_csv(f"{RES}/biogeme_check_{s}_taz{SUF}.csv", index=False)
        prev = f"{RES}/biogeme_check_all_taz{SUF}.csv"
        old = pd.read_csv(prev) if os.path.exists(prev) else pd.DataFrame()
        out = pd.concat([old[~old.segment.isin([r["segment"] for r in rows])] if len(old) else old, pd.DataFrame(rows)])
        out.to_csv(prev, index=False)


if __name__ == "__main__":
    segs = sys.argv[1].split(",") if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else [f"{p}_{k}" for k in ["primary", "stop"] for p in ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]]
    main(segs)
