#!/usr/bin/env python3
"""RTS workplace choice, version 2 (rts_11_data_v2.py records): the final specification of version 1
(R9_logsum_t_lt_inter_reg+mu, rts_03_estimate.py) re-estimated with
  - one income group per survey class (class midpoint in 2016 $), so no income mixing;
  - home and work locations from the survey traffic zones (or the tract split), and the likelihood averaged over the possible
    home zones h (weights w_h) and the possible chosen work zones j (weights w_j):  P = sum_h w_h sum_j w_j P(j | h).
Choice set: the record's possible work zones (up to 4, each one entry) plus 99 zones drawn with replacement from the 1,587 zones
with jobs with q_j proportional to jobs_j exp(-0.05 t_{h* j}), h* = the record's most likely home zone (seed 20261027); every entry's
utility is corrected by -ln q_j, as in version 1.  P(j | h) is the logit over these 103 entries with the utility of home h (padded
candidate entries unavailable).  Home zones: the 3 most likely (re-normalised; the 4th carries 0.01 % of the mass, 18 records).
Biogeme 3.3.5, robust s.e., unweighted (the version-1 choice).  The full-choice-set log-likelihood (all 1,587 zones, all home
zones and candidates) is computed with numpy; also for the version-1 coefficients on the same records.
Outputs: tables_rts/estimates_V2.csv, cov_V2.csv, fit_v2.csv, work_rts/biogeme_v2/V2.html.   Usage: python3 landuse/lib/jobchoice/rts_13_estimate_v2.py [V2]"""
import os, sys, numpy as np, pandas as pd
import biogeme.biogeme as bio, biogeme.database as db
from biogeme.expressions import Beta, Variable, exp, log
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rts_common as R   # noqa: E402
FIN1 = "R9_logsum_t_lt_inter_reg+mu"
TERMS = [k[2:].replace("X", "*") for k in pd.read_csv(f"{R.T}/estimates_{FIN1}.csv").parameter if k.startswith("b_")]
# Normalisation (2026-10-27): the DC constant (reg_dc), the DC term (dc) and 'another state x DC home' (cs*hdc) are not separately
# identified: adding a to reg_dc and to cs*hdc and subtracting a from dc leaves every probability unchanged (for a DC home every
# non-DC zone is in another state; for any other home a DC zone carries both reg_dc and dc).  The version-1 Hessian was singular in
# that direction (smallest eigenvalue of its covariance ~ -2e-15), so its three values were one arbitrary point of a ridge.
# Version 2 fixes cs*hdc = 0; reg_dc is then the DC preference of DC residents relative to the state-crossing penalty and
# reg_dc + dc that of everyone else.  The fit is the same.
TERMS = [t for t in TERMS if t != "cs*hdc"]
NC, HS, ND = 4, 3, 99; J = NC + ND
z = R.zones(); az = np.where(z.jobs.values > 0)[0]; zi = R.zidx()


def persons_v2(half):
    P = pd.read_parquet(f"{R.W}/workers_v2.parquet"); P = P[P.half == half].reset_index(drop=True)
    P["hidx"] = zi[P.hz].values; P["widx"] = zi[P.wz].values
    LH = pd.read_parquet(f"{R.W}/loc_home_v2.parquet"); LW = pd.read_parquet(f"{R.W}/loc_work_v2.parquet")
    pos = pd.Series(np.arange(len(P)), index=P.person_id)
    def mat(Lx, k):
        Lx = Lx[Lx.person_id.isin(P.person_id)].sort_values(["person_id", "w"], ascending=[True, False]).copy(); Lx["r"] = Lx.groupby("person_id").cumcount()
        Z_ = np.full((len(P), k), -1); Wt = np.zeros((len(P), k)); m = Lx.r < k
        Z_[pos[Lx.person_id[m]].values, Lx.r[m].values] = zi[Lx.zone[m]].values; Wt[pos[Lx.person_id[m]].values, Lx.r[m].values] = Lx.w[m].values
        return Z_, Wt
    return P, mat(LH, 4), mat(LW, NC)


def design(P, Hz, seed=20261027):
    TT = R.tt(); rng = np.random.default_rng(seed); h = Hz[:, 0]
    lq = np.log(z.jobs.values[az])[None, :] - 0.05 * TT[h][:, az]; q = np.exp(lq - lq.max(axis=1, keepdims=True)); q /= q.sum(axis=1, keepdims=True); cq = np.cumsum(q, axis=1)
    D = np.empty((len(P), ND), int)
    for k in range(ND): D[:, k] = np.minimum((cq < rng.random(len(P))[:, None]).sum(axis=1), len(az) - 1)
    return q, D


def full_ll(e, terms, P, Hz, Hw, Wz, Ww, chunk=300):
    """exact full-set log-likelihood per record: ln sum_h w_h sum_j w_j P(j | h)"""
    pos = np.full(len(z), -1); pos[az] = np.arange(len(az)); out = np.zeros(len(P)); g = P.g.values
    for s in range(0, len(P), chunk):
        r = np.arange(s, min(s + chunk, len(P))); acc = np.zeros(len(r))
        for k in range(Hz.shape[1]):
            m = Hw[r, k] > 0
            if not m.any(): continue
            rr = r[m]; A = np.broadcast_to(az, (len(rr), len(az)))
            U = R.utility(terms, e, Hz[rr, k], A, P, rr, g[rr]); U -= U.max(axis=1, keepdims=True); E = np.exp(U); Pm = E / E.sum(axis=1, keepdims=True)
            pj = sum(Ww[rr, c] * Pm[np.arange(len(rr)), np.maximum(pos[np.maximum(Wz[rr, c], 0)], 0)] * (Wz[rr, c] >= 0) for c in range(Wz.shape[1]))
            acc[m] += Hw[rr, k] * pj
        out[r] = np.log(np.maximum(acc, 1e-300))
    return out


def coef(name):
    e = pd.read_csv(f"{R.T}/estimates_{name}.csv").set_index("parameter").estimate.to_dict()
    return {(k[2:].replace("X", "*") if k.startswith("b_") else k): v for k, v in e.items()}


def estimate(name="V2"):
    P, (Hz4, Hw4), (Wz, Ww) = persons_v2("estimation"); N = len(P); rec = np.arange(N)
    Hz = Hz4[:, :HS].copy(); Hw = Hw4[:, :HS].copy(); Hw /= Hw.sum(axis=1, keepdims=True)
    for k in range(1, HS): Hz[:, k] = np.where(Hw[:, k] > 0, Hz[:, k], Hz[:, 0])
    q, D = design(P, Hz)
    posaz = np.full(len(z), -1); posaz[az] = np.arange(len(az))
    A = np.concatenate([np.where(Wz >= 0, Wz, Wz[:, :1]), az[D]], axis=1)                       # entries: candidates then draws
    qa = q[np.arange(N)[:, None], posaz[A]]; corr = -np.log(qa)
    cols = {"av_c": None}; cols = {f"avc{c}": (Wz[:, c] >= 0).astype(float) for c in range(NC)}
    for c in range(NC): cols[f"wc{c}"] = Ww[:, c]
    for k in range(HS): cols[f"wh{k}"] = Hw[:, k]
    for k in range(J): cols[f"corr{k}"] = corr[:, k]
    for s in R.SEC:
        x = z[s].values[A]
        for k in range(J): cols[f"{s}{k}"] = x[:, k]
    hdep = [t for t in TERMS if not t.startswith("reg_")]; hind = [t for t in TERMS if t.startswith("reg_")]
    for t in hind:
        x = R.feat(t, Hz[:, 0], A, P, rec, P.g.values)
        for k in range(J): cols[f"{t}_{k}"] = x[:, k]
    for hs in range(HS):
        for t in hdep:
            x = R.feat(t, Hz[:, hs], A, P, rec, P.g.values); nm = t.replace("*", "X")
            for k in range(J): cols[f"{nm}_h{hs}_{k}"] = x[:, k]
    df = pd.DataFrame(cols); assert np.isfinite(df.values).all(); del cols
    d = db.Database(name, df)
    B = {t: Beta(f"b_{t.replace('*', 'X')}", 0.0, None, None, 0) for t in TERMS}
    G = {s: Beta(f"g_{s}", 0.0, None, None, 0) for s in ("OFF", "IND", "OTH")}; mu = Beta("mu_size", 1.0, 0.01, None, 0)
    base = []
    for k in range(J):
        sz = Variable(f"RET{k}") + exp(G["OFF"]) * Variable(f"OFF{k}") + exp(G["IND"]) * Variable(f"IND{k}") + exp(G["OTH"]) * Variable(f"OTH{k}")
        v = mu * log(sz + 1e-9) + Variable(f"corr{k}")
        for t in hind: v = v + B[t] * Variable(f"{t}_{k}")
        base.append(v)
    like = 0
    for hs in range(HS):
        V = []
        for k in range(J):
            v = base[k]
            for t in hdep: v = v + B[t] * Variable(f"{t.replace('*', 'X')}_h{hs}_{k}")
            V.append(v)
        den = sum((Variable(f"avc{k}") if k < NC else 1.0) * exp(V[k]) for k in range(J))
        num = sum(Variable(f"wc{c}") * Variable(f"avc{c}") * exp(V[c]) for c in range(NC))
        like = like + Variable(f"wh{hs}") * num / den
    os.makedirs(f"{R.W}/biogeme_v2", exist_ok=True); os.chdir(f"{R.W}/biogeme_v2")   # its biogeme.toml: finite-difference Hessian (the analytical one did not compile within 40 min), at most 2 iterations: Biogeme starts at
    # the maximum of the same likelihood found by rts_13b_start_values.py (analytic gradient; Biogeme's own BFGS wandered for 3 h) and computes
    # the estimates' statistics and robust covariance there; the Biogeme log-likelihood at that point equals the numpy one (-41,942.514)
    b = bio.BIOGEME(d, log(like), generate_html=True, generate_yaml=True); b.model_name = name
    # start from the numpy maximum (rts_13b_start_values.py, same likelihood), else from the version-1 estimates
    e1 = pd.read_csv(f"{R.T}/estimates_{FIN1}.csv").set_index("parameter").estimate.to_dict()
    if os.path.exists(f"{R.W}/start_V2.csv"): e1 = pd.read_csv(f"{R.W}/start_V2.csv").set_index("parameter").estimate.to_dict()   # rts_13b_start_values.py
    b.change_init_values(e1) if hasattr(b, "change_init_values") else None
    r = b.estimate(); bv = r.get_beta_values(); Vr = np.asarray(r.robust_variance_covariance_matrix); names = list(bv)
    t = pd.DataFrame({"parameter": names, "estimate": [bv[n] for n in names], "robust_se": [np.sqrt(Vr[r.get_parameter_index(n), r.get_parameter_index(n)]) for n in names]})
    t["robust_t"] = t.estimate / t.robust_se; t.to_csv(f"{R.T}/estimates_{name}.csv", index=False)
    ix = [r.get_parameter_index(n) for n in names]; pd.DataFrame(Vr[np.ix_(ix, ix)], index=names, columns=names).to_csv(f"{R.T}/cov_{name}.csv")
    ll, K = r.final_loglikelihood, len(names)
    # LL(0): equal probabilities over the sampled entries, averaged over the candidates: ln(sum_j w_j / n_available entries)
    nav = NC + ND - (Wz < 0).sum(axis=1); ll0 = float(-np.log(nav).sum())
    lf = full_ll(coef(name), TERMS, P, Hz4, Hw4, Wz, Ww).sum(); lf1 = full_ll(coef(FIN1), TERMS, P, Hz4, Hw4, Wz, Ww).sum()
    s0 = np.log(z.jobs.values[az]); p0 = np.exp(s0 - s0.max()); p0 /= p0.sum(); pos = np.full(len(z), -1); pos[az] = np.arange(len(az))
    lsz = float(np.log(sum(Ww[:, c] * p0[np.maximum(pos[np.maximum(Wz[:, c], 0)], 0)] * (Wz[:, c] >= 0) for c in range(NC))).sum())
    lf0 = -N * np.log(len(az))
    fit = dict(model=name, N=N, J=J, K=K, LL0=ll0, LL=ll, rho2=1 - ll / ll0, rho2_bar=1 - (ll - K) / ll0, AIC=2 * K - 2 * ll, BIC=K * np.log(N) - 2 * ll,
               LL_full=lf, LL_full0=lf0, LL_full_size_only=lsz, rho2_full=1 - lf / lf0, rho2_full_bar=1 - (lf - K) / lf0, AIC_full=2 * K - 2 * lf, BIC_full=K * np.log(N) - 2 * lf,
               LL_full_v1_coefficients_same_records=lf1, records_home_split=int((Hw4[:, 1] > 0).sum()), records_work_split=int((Ww[:, 1] > 0).sum()))
    pd.DataFrame([fit]).to_csv(f"{R.T}/fit_v2.csv", index=False)
    pd.set_option("display.width", 200); print(t.round(4).to_string(index=False)); print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in fit.items()}, flush=True)


if __name__ == "__main__":
    estimate(sys.argv[1] if len(sys.argv) > 1 else "V2")
