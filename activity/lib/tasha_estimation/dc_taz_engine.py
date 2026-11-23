#!/usr/bin/env python3
"""Location-mixture extension of destination_choice/dc_model.py for the TAZ variant (2026-10-28).

Every record n has destination weights b_nz (dc_cand_<half>_taz) and anchor configurations k with weights w_nk
(dc_cfg_<half>_taz: origin / anchor a in `home_idx`, anchor b in `anchor_b`).  The likelihood is the location mixture of the
workplace model (2_silo/jobchoice/rts_13_estimate_v2.py):
    L_n = sum_k w_nk  sum_{z in C_n} b_nz exp(V_nkz + c_nz) / sum_{j in D_n} exp(V_nkj + c_nj)
with one sampled set D_n per record, drawn by dc_model.sample_sets with the record's most likely configuration (R = 40,
seed 2026, same D0 and correction c = ln(k / R q)), shared by all configurations, as the workplace model does with h*.
With one configuration of weight 1 this is dc_model.ll_obs exactly.  The optimiser, the Hessian and the robust covariance are
those of dc_model.estimate (the module-level ll_obs is wrapped, nothing else changes).
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
import torch
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; A3 = os.path.dirname(HERE)
sys.path.insert(0, CODE); sys.path.insert(0, f"{MILES_HOME}/activity/lib"); sys.path.insert(0, f"{MILES_HOME}/activity/lib/destination_choice")
import dc_common as C     # noqa: E402
import dc_model as M      # noqa: E402

_ll_orig = M.ll_obs


class MixData:
    def __init__(self, rec, cfg, alts, lnc, logb, spec, pur, sk):
        pos = pd.Series(np.arange(len(rec)), index=rec.rec.values)
        c = cfg[cfg.rec.isin(rec.rec.values)].copy(); c["p"] = pos[c.rec.values].values
        c = c.sort_values(["p", "w"], ascending=[True, False]).reset_index(drop=True); c["k"] = c.groupby("p").cumcount()
        rows = rec.iloc[c.p.values].reset_index(drop=True).copy()
        rows["home_idx"] = c.home_idx.values.astype(int); rows["anchor_b"] = c.anchor_b.values.astype(int)
        self.rows, self.rp, self.rw = rows, c.p.values, c.w.values
        self.base = M.Data(rows, alts[c.p.values], lnc[c.p.values], logb[c.p.values], spec, pur, sk)
        N = len(rec); Kc = int(c.k.max()) + 1
        gi = np.zeros((N, Kc), np.int64); lw = np.full((N, Kc), -np.inf)
        gi[c.p.values, c.k.values] = np.arange(len(c)); lw[c.p.values, c.k.values] = np.log(c.w.values)
        self.gidx = torch.tensor(gi); self.logw = torch.tensor(lw); self.N = N; self.J = alts.shape[1]; self.Kc = Kc
        first = gi[:, 0]
        self.lnc = self.base.lnc[first]; self.logb = self.base.logb[first]


def ll_mix(theta, spec, D):
    if isinstance(D, MixData):
        l = _ll_orig(theta, spec, D.base)
        return torch.logsumexp(l[D.gidx] + D.logw, 1)
    return _ll_orig(theta, spec, D)


M.ll_obs = ll_mix


def fit(spec, rec, cfg, alts, lnc, logb, pur, sk, x0=None):
    D = MixData(rec, cfg, alts, lnc, logb, spec, pur, sk)
    res = M.estimate(spec, D, x0=x0); res["LL0"] = M.ll_zero(D); res["D"] = D
    return res


def single_cfg(rec):
    """one configuration of weight 1 (the tract-point records of the model of record)."""
    return pd.DataFrame({"rec": rec.rec.values, "home_idx": rec.home_idx.values.astype(int), "anchor_b": rec.anchor_b.values.astype(int), "w": 1.0})


def heldout(rec, cand, cfg, spec, xv, pur, sk, obs="mix", chunk=400):
    """Full choice set.  Per record: LL_n = ln sum_k w_k sum_z b_z P_k(z); predicted and observed distance from the origin of the
    configuration (primary: home; stop: anchor a), as a weighted binned distribution (rts_common.DIST_BINS) and mean.
    obs = 'mix': observed = sum_k w_k b_z (the TAZ mixture); obs = 'pt': observed = the zone of the tract internal point
    (dzone_pt) from the single configuration (the convention of the model-of-record checks)."""
    from rts_common import DIST_BINS
    nb = len(DIST_BINS) - 1; theta = torch.tensor(np.asarray(xv, float)); nz = len(C.zones())
    ll = np.zeros(len(rec)); kp = np.zeros(len(rec)); ko = np.full(len(rec), np.nan)
    hp = np.zeros(nb); ho = np.zeros(nb); w = rec.w.values.astype(float)
    for i0 in range(0, len(rec), chunk):
        sub = rec.iloc[i0:i0 + chunk]; cs = cand[cand.rec.isin(sub.rec.values)]
        alts, lnc, logb = M.full_sets(sub, cs)
        D = MixData(sub, cfg, alts, lnc, logb, spec, pur, sk)
        with torch.no_grad(): P = torch.softmax(M.utility(theta, spec, D.base), 1).numpy()
        B = np.exp(logb); p = D.rp; wr = D.rw; o = D.rows.home_idx.values
        dist = sk["d"][o].astype(np.float64)                                   # rows x zones
        lr = (P * B[p]).sum(1)
        np.add.at(ll, i0 + p, wr * lr)
        np.add.at(kp, i0 + p, wr * (P * dist).sum(1))
        bins = np.clip(np.searchsorted(DIST_BINS, dist, side="right") - 1, 0, nb - 1)
        ww = (w[i0 + p] * wr)[:, None]
        for k in range(nb): hp[k] += float((ww * P * (bins == k)).sum())
        if obs == "mix":
            kk = (B[p] * dist).sum(1); tmp = np.zeros(len(sub)); np.add.at(tmp, p, wr * kk); ko[i0:i0 + len(sub)] = tmp
            for k in range(nb): ho[k] += float((ww * B[p] * (bins == k)).sum())
        else:
            dz = sub.dzone_pt.values; okk = dz >= 0; oo = sub.home_idx.values
            ko[i0:i0 + len(sub)][okk] = sk["d"][oo[okk], dz[okk]]
            bo = np.clip(np.searchsorted(DIST_BINS, ko[i0:i0 + len(sub)][okk], side="right") - 1, 0, nb - 1)
            np.add.at(ho, bo, w[i0:i0 + len(sub)][okk])
    LL = np.log(np.clip(ll, 1e-300, None))
    return dict(LL=LL, km_pred=kp, km_obs=ko, tld_pred=hp / hp.sum(), tld_obs=ho / ho.sum())


def ks(p, q):
    return float(np.max(np.abs(np.cumsum(p) - np.cumsum(q))))


def collinearity(D, spec, res):
    """Within-choice-set demeaned correlation and VIFs of the utility variables of the final model (the sampled sets of the
    estimation, all configurations weighted by w_k; padding excluded).  The size term enters as ln(1 + S_j) at the estimates."""
    b = D.base; X = b.X.numpy().copy(); names = list(spec.linear)
    t = res["table"].set_index("param").value
    wts = np.concatenate([[1.0], [np.exp(t[f"theta_{c}"]) for c in spec.size_comps]])
    lnS = np.log1p((b.S.numpy() * wts).sum(-1))
    X = np.concatenate([X, lnS[..., None]], -1); names = names + ["ln_size"]
    av = np.isfinite(b.lnc.numpy())                                            # rows x J
    n = av.sum(1, keepdims=True)
    mu = (X * av[..., None]).sum(1, keepdims=True) / n[..., None]
    Z = (X - mu) * av[..., None]
    wr = np.repeat(D.rw[:, None], X.shape[1], 1) * av
    Zf = Z.reshape(-1, Z.shape[-1]); wf = wr.reshape(-1)
    m = wf > 0; Zf = Zf[m]; wf = wf[m]
    cov = (Zf * wf[:, None]).T @ Zf / wf.sum()
    sd = np.sqrt(np.diag(cov)); keep = sd > 1e-12
    R = cov[np.ix_(keep, keep)] / np.outer(sd[keep], sd[keep]); nm = [x for x, k in zip(names, keep) if k]
    try: vif = np.diag(np.linalg.inv(R))
    except np.linalg.LinAlgError: vif = np.diag(np.linalg.pinv(R))
    return pd.DataFrame(R, index=nm, columns=nm), pd.Series(vif, index=nm, name="VIF")


def bio_export(path, spec, rec, cfg, alts, lnc, logb, pur, sk, start):
    """wide-format Biogeme data of the mixture: for each configuration slot c (padding: a copy of slot 0, weight 0) and sampled
    slot j the configuration-dependent variables `<k>_<j>_c<c>`; the configuration-free variables, the size components, the
    correction, the destination weights and availability once per slot j; `w_c<c>` the configuration weights."""
    import json
    D = MixData(rec, cfg, alts, lnc, logb, spec, pur, sk); b = D.base; N, Kc, J = D.N, D.Kc, D.J
    gi = D.gidx.numpy(); lw = D.logw.numpy(); X = b.X.numpy()
    pad = ~np.isfinite(b.lnc.numpy()[gi[:, 0]])
    gi_f = np.where(np.isfinite(lw), gi, gi[:, :1])
    dep = [k for i, k in enumerate(spec.linear) if not np.allclose(X[gi_f[:, :], :, i], X[gi_f[:, :1], :, i])]
    cols = {}
    comps = [spec.size_base] + spec.size_comps; S = b.S.numpy()[gi[:, 0]]
    lnc0 = b.lnc.numpy()[gi[:, 0]]; lb0 = b.logb.numpy()[gi[:, 0]]
    for j in range(J):
        for i, k in enumerate(spec.linear):
            if k in dep:
                for c in range(Kc): cols[f"{k}_{j}_c{c}"] = X[gi_f[:, c], j, i]
            else: cols[f"{k}_{j}"] = X[gi[:, 0], j, i]
        for ci, c in enumerate(comps): cols[f"{c}_{j}"] = S[:, j, ci]
        cols[f"lnc_{j}"] = np.where(pad[:, j], 0.0, lnc0[:, j]); cols[f"b_{j}"] = np.where(pad[:, j], 0.0, np.exp(lb0[:, j]))
        cols[f"av_{j}"] = (~pad[:, j]).astype(float)
    for c in range(Kc): cols[f"w_c{c}"] = np.where(np.isfinite(lw[:, c]), np.exp(lw[:, c]), 0.0)
    pd.DataFrame(cols).to_parquet(f"{path}.parquet", index=False)
    json.dump(dict(J=J, N=N, Kc=Kc, linear=spec.linear, dep=dep, size_base=spec.size_base, size_comps=spec.size_comps, start=start), open(f"{path}.json", "w"), indent=1)


# ------------------------------------------------------------------------------------------------ merged distance pieces (2026-10-28)
# DAYMAP parses any d_<lo>_<hi> / dt_<lo>_<hi> as the piece clip(d - lo, 0, hi - lo) (MarylandDestinationChoice.loadMnl), so a merged
# top piece (e.g. d_20_inf = d_20_50 + d_50_inf with one slope) needs no Java change; dc_model.features knows only the standard
# knots, so the merged pieces are computed here and the rest is passed on unchanged.
_feat_orig = M.features


def features_x(rec, alts, names, sk, purpose):
    stop = (rec.kind.values == "stop").all()
    std = set(C.pw_names("dt" if stop else "d", C.DKNOTS if stop else C.KNOTS))
    custom = [n for n in names if (n.startswith("d_") or n.startswith("dt_")) and n not in std]
    rest = [n for n in names if n not in custom]
    out = dict(_feat_orig(rec, alts, rest, sk, purpose)) if rest else {}
    if custom:
        imp = M.impedance(rec, alts, sk)
        for n in custom:
            _, lo, hi = n.split("_"); lo = float(lo); hi = np.inf if hi == "inf" else float(hi)
            out[n] = np.clip(imp - lo, 0.0, hi - lo)
    return {k: out[k] for k in names}


M.features = features_x
