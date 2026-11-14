#!/usr/bin/env python3
"""Biogeme estimation of the final destination-choice models (the reported estimates).

    ~/.venvs/biogeme/bin/python activity/lib/destination_choice/estimate_biogeme.py [SEGMENT,...]

Reads destination_choice/work/bio_<segment>.parquet and bio_<segment>.json (written by `estimate_dc.py biodata` in the main
environment: the importance-sampled choice sets of the estimation half, seed 2026, R = 40 draws, with the variables of the
final specification in wide format, one column per variable and alternative slot) and maximises
    LL = sum_n [ ln sum_j b_nj av_nj exp(V_nj + c_nj) - ln sum_j av_nj exp(V_nj + c_nj) ],
    V_nj = mu ln(1 + x_nj,base + sum_c exp(theta_c) x_nj,c) + sum_k beta_k x_njk,
c_nj = ln(k_nj / q_nj) the sampling correction, b_nj the measurement weight of zone j for the observed tract (0 for the
sampled zones that are not candidates), av_nj = 0 for padding slots.  Biogeme 3.3.5 (Bierlaire 2023), BFGS with trust
region (default 'automatic' algorithm), robust (sandwich) standard errors.  Output: destination_choice/results/
biogeme_<segment>.csv (parameters), biogeme_<segment>_stats.json, biogeme_<segment>.html (Biogeme report).
Runs in its own environment (~/.venvs/biogeme: biogeme 3.3.5 needs pandas < 3, the main environment has pandas 3).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, os, sys
import numpy as np
import pandas as pd

HERE = f"{WORKSPACE}/3_abit/destination_choice"; WORK = f"{HERE}/work"; RES = f"{HERE}/results"


def estimate(seg):
    import biogeme.database as db
    import biogeme.biogeme as bio
    from biogeme.expressions import Beta, Variable, exp, log, MultipleSum
    meta = json.load(open(f"{WORK}/bio_{seg}.json")); df = pd.read_parquet(f"{WORK}/bio_{seg}.parquet")
    J = meta["J"]; lin = meta["linear"]; base = meta["size_base"]; comps = meta["size_comps"]; start = meta["start"]
    d = db.Database(seg, df)
    B = {k: Beta(k, start.get(k, 0.0), None, None, 0) for k in lin}
    TH = {c: Beta(f"theta_{c}", start.get(f"theta_{c}", 0.0), -30, 15, 0) for c in comps}
    MU = Beta("mu_size", start.get("mu_size", 1.0), 0, 3, 0)
    num, den = [], []
    for j in range(J):
        S = Variable(f"{base}_{j}") + sum([exp(TH[c]) * Variable(f"{c}_{j}") for c in comps], 0) if comps else Variable(f"{base}_{j}")
        V = MU * log(1 + S) + sum([B[k] * Variable(f"{k}_{j}") for k in lin], 0) + Variable(f"lnc_{j}")
        e = exp(V)
        num.append(Variable(f"b_{j}") * e); den.append(Variable(f"av_{j}") * e)
    ll = log(MultipleSum(num)) - log(MultipleSum(den))
    os.makedirs(f"{WORK}/biogeme", exist_ok=True); cwd = os.getcwd(); os.chdir(f"{WORK}/biogeme")
    try:
        y = f"{WORK}/biogeme/dc_{seg}.yaml"
        if os.path.exists(y) and "--force" not in sys.argv:      # results of a previous estimation of the same data
            from biogeme.results_processing import EstimationResults
            r = EstimationResults.from_yaml_file(y)
        else:
            m = bio.BIOGEME(d, ll); m.model_name = f"dc_{seg}"
            r = m.estimate()
    finally:
        os.chdir(cwd)
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))
    t.to_csv(f"{RES}/biogeme_{seg}.csv", index=False)
    stats = dict(segment=seg, LL=float(r.final_loglikelihood), N=int(len(df)), K=int(r.number_of_free_parameters), J=J,
                 converged=bool(r.algorithm_has_converged), gradient_norm=float(r.gradient_norm), AIC=float(r.akaike_information_criterion),
                 BIC=float(r.bayesian_information_criterion), smallest_eigenvalue=float(r.smallest_eigenvalue), condition_number=float(r.condition_number))
    json.dump(stats, open(f"{RES}/biogeme_{seg}_stats.json", "w"), indent=1)
    rc = r.robust_variance_covariance_matrix; names = list(t.Name) if "Name" in t else list(t.index)
    pd.DataFrame(np.asarray(rc)).to_csv(f"{RES}/biogeme_{seg}_robust_cov.csv", index=False)
    for f in os.listdir(f"{WORK}/biogeme"):
        if f.startswith(f"dc_{seg}") and f.endswith(".html"): os.replace(f"{WORK}/biogeme/{f}", f"{RES}/biogeme_{seg}.html")
    print(f"{seg}: LL {stats['LL']:.3f} K {stats['K']} converged {stats['converged']}", flush=True)
    return stats


def main(segs):
    for s in segs:
        if os.path.exists(f"{WORK}/bio_{s}.parquet"): estimate(s)
        else: print(f"{s}: no Biogeme data (run estimate_dc.py biodata)")


if __name__ == "__main__":
    segs = sys.argv[1].split(",") if len(sys.argv) > 1 else sorted(f[4:-8] for f in os.listdir(WORK) if f.startswith("bio_") and f.endswith(".parquet"))
    main(segs)
