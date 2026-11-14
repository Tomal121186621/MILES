#!/usr/bin/env python3
"""Full-choice-set estimation of the eight activity-location models of record (2026-11-04).

    TAZ_THREADS=6 python3 estimate_fullset_taz.py [SEG,SEG,...]     # default: the four primaries and the four stop models

Same records (dc_rec_estimation_taz), same location mixture (dc_taz_engine), same specification of record (final_spec, primaries
+ ln d x multi) and warm start (the sampled-set estimates cx_/seq_estimates_taz.csv); the only change is the choice set: all
1,588 zones, no sampling correction.  The likelihood, gradient, Hessian and per-record scores are accumulated over chunks of
records (whole records per chunk, so the mixture over configurations stays inside a chunk); the utility variables of every
chunk are built once and kept in float32, cast to float64 for each evaluation.
Outputs: results/fullset_estimates_taz.csv (param, value, rob_se, rob_t, se, segment, N, LL, LL0, K, converged, maxgrad),
results/fullset_compare_taz.csv (sampled vs full, difference in sampled robust SE), results/fullset_heldout_taz.csv (predictive
LL per record on the validation half, full set, sampled and full-set coefficients), results/dest_choice_{primary_cx,stop_seq}_fullset_taz.csv.
"""
# COPY of Validation_2026/3_abit/tasha_estimation/estimate_fullset_taz.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import os, sys, time
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import estimate_dc_taz as Z       # noqa: E402  (sets the threads, wraps dc_model)
import dc_taz_engine as X         # noqa: E402
import dc_model as M              # noqa: E402
import dc_common as C             # noqa: E402
from estimate_complexity import multi_flag, final_spec   # noqa: E402
import torch                      # noqa: E402
from scipy.optimize import minimize   # noqa: E402

RES = Z.RES; CHUNK = 300


class Chunk:
    """MixData of a chunk of records on the full set; X and S stored as float32."""
    def __init__(self, sub, cand, cfg, spec, pur, sk):
        alts, lnc, logb = M.full_sets(sub, cand)
        D = X.MixData(sub, cfg, alts, lnc, logb, spec, pur, sk)
        b = D.base
        self.X32, self.S32 = b.X.float(), b.S.float(); self.logb = b.logb; self.gidx, self.logw = D.gidx, D.logw
        self.N = D.N; self.rows = len(D.rows)

    def ll(self, theta, spec):
        b = type("B", (), {})(); b.X = self.X32.double(); b.S = self.S32.double(); b.lnc = torch.zeros(()); b.logb = self.logb
        V = M.utility(theta, spec, b)
        l = torch.logsumexp(V + b.logb, 1) - torch.logsumexp(V, 1)
        return torch.logsumexp(l[self.gidx] + self.logw, 1)

    def ll0(self):
        nz = self.logb.shape[1]
        l = torch.logsumexp(self.logb, 1) - np.log(nz)
        return float(torch.logsumexp(l[self.gidx] + self.logw, 1).sum())


def spec_of(seg):
    spec, _ = final_spec(seg)
    if seg.endswith("primary"): spec = M.Spec("FX", spec.linear + ["lnd_multi"], spec.size_base, spec.size_comps)
    return spec


def load(seg, half):
    rec, cand, cfg = Z.load_taz(half, seg)
    if seg.endswith("primary"): rec["multi"] = multi_flag(rec, half)
    return rec, cand, cfg


def sampled_table(seg):
    f = f"{RES}/{'cx' if seg.endswith('primary') else 'seq'}_estimates_taz.csv"; t = pd.read_csv(f); return t[t.segment == seg].set_index("param")


def estimate(seg, sk):
    pur = seg.split("_")[0]; spec = spec_of(seg); names = spec.params()
    rec, cand, cfg = load(seg, "estimation"); t0 = time.time()
    chunks = [Chunk(rec.iloc[i:i + CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + CHUNK])], cfg, spec, pur, sk) for i in range(0, len(rec), CHUNK)]
    print(f"{seg}: N {len(rec)}, {sum(c.rows for c in chunks)} configuration rows, data {time.time() - t0:.0f} s", flush=True)
    ts = sampled_table(seg); x0 = np.array([ts.value[p] for p in names])
    bounds = [(-30.0, 15.0) if p.startswith("theta_") else (0.0, 3.0) if p == "mu_size" else (None, None) for p in names]
    def fg(v):
        t = torch.tensor(v, requires_grad=True); tot = 0.0
        for c in chunks:
            l = -c.ll(t, spec).sum(); l.backward(); tot += float(l)
        if not np.isfinite(tot): return 1e15, np.zeros_like(v)
        return tot, t.grad.numpy().copy()
    r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bounds, options=dict(maxiter=3000, maxfun=12000, ftol=1e-13, gtol=1e-6, maxcor=30))
    x = torch.tensor(r.x); K = len(x)
    from torch.func import jvp
    H = torch.zeros((K, K)); G = []
    for c in chunks:
        H += torch.autograd.functional.hessian(lambda t: c.ll(t, spec).sum(), x)
        G.append(torch.stack([jvp(lambda t: c.ll(t, spec), (x,), (e,))[1] for e in torch.eye(K)], 1))
    G = torch.cat(G); LL = -float(r.fun); g = G.sum(0)
    at_bound = [p for p, v, (lo, hi) in zip(names, r.x, bounds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
    free = torch.tensor([p not in at_bound for p in names]); cov = torch.full((K, K), float("nan")); covc = cov.clone()
    Hi = torch.linalg.inv(-H[free][:, free]); Gf = G[:, free]; fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
    for a, ia in enumerate(fi): cov[ia, fi] = cf[a]; covc[ia, fi] = Hi[a]
    se = torch.sqrt(torch.clamp(torch.diag(cov), min=0)); sec = torch.sqrt(torch.clamp(torch.diag(covc), min=0))
    LL0 = sum(c.ll0() for c in chunks)
    tab = pd.DataFrame({"param": names, "value": x.numpy(), "rob_se": se.numpy(), "rob_t": (x / se).numpy(), "se": sec.numpy()})
    tab = tab.assign(segment=seg, N=len(rec), LL=LL, LL0=LL0, K=K, converged=bool(r.success), maxgrad=float(g.abs().max()), at_bound=" ".join(at_bound))
    print(f"  LL {LL:.2f} (sampled-set estimates on the full set: {-fg(x0)[0]:.2f}), LL0 {LL0:.2f}, converged {r.success}, maxgrad {float(g.abs().max()):.2e}, "
          f"{r.nit} iterations, {time.time() - t0:.0f} s", flush=True)
    return spec, tab, -fg(x0)[0]


def main(segs):
    sk = C.skims(); tabs, comp, ho, coef = [], [], [], []
    for seg in segs:
        spec, tab, LL_sampled_on_full = estimate(seg, sk); tabs.append(tab); pur = seg.split("_")[0]
        ts = sampled_table(seg); tf = tab.set_index("param")
        for p in tf.index:
            comp.append(dict(segment=seg, param=p, sampled=ts.value[p], se_sampled=ts.rob_se[p], full=tf.value[p], se_full=tf.rob_se[p],
                             diff_over_se=(tf.value[p] - ts.value[p]) / ts.rob_se[p], t_sampled=ts.rob_t[p], t_full=tf.rob_t[p]))
        sseg = seg if seg.endswith("primary") else seg.replace("_stop", "_seq_stop")
        coef += Z.coef_rows(sseg, spec, tf.value)
        for half in ["estimation", "validation"]:
            rv, cv, gv = load(seg, half)
            for lab, xv in [("sampled", np.array([ts.value[p] for p in spec.params()])), ("full set", tf.value[spec.params()].values)]:
                h = X.heldout(rv, cv, gv, spec, xv, pur, sk, obs="mix"); w = rv.w.values
                ho.append(dict(segment=seg, half=half, coefficients=lab, N=len(rv), LL_total=float(h["LL"].sum()), LL_per_obs=float(h["LL"].mean()),
                               km_obs=float(np.average(h["km_obs"], weights=w)), km_pred=float(np.average(h["km_pred"], weights=w)), KS=X.ks(h["tld_pred"], h["tld_obs"])))
                print("  ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in ho[-1].items()}, flush=True)
        pd.concat(tabs).to_csv(f"{RES}/fullset_estimates_taz.csv", index=False); pd.DataFrame(comp).to_csv(f"{RES}/fullset_compare_taz.csv", index=False)
        pd.DataFrame(ho).to_csv(f"{RES}/fullset_heldout_taz.csv", index=False)
        C_ = pd.DataFrame(coef)
        C_[C_.segment.str.endswith("primary")].to_csv(f"{RES}/dest_choice_primary_cx_fullset_taz.csv", index=False)
        C_[C_.segment.str.endswith("stop")].to_csv(f"{RES}/dest_choice_stop_seq_fullset_taz.csv", index=False)
        c = pd.DataFrame(comp); c = c[c.segment == seg]
        print(f"  |diff|/SE median {c.diff_over_se.abs().median():.2f}, max {c.diff_over_se.abs().max():.2f} ({c.loc[c.diff_over_se.abs().idxmax(), 'param']})", flush=True)


if __name__ == "__main__":
    segs = sys.argv[1].split(",") if len(sys.argv) > 1 else [f"{p}_{k}" for k in ["primary", "stop"] for p in C.DISC]
    main(segs)
