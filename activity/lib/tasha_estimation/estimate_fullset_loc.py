#!/usr/bin/env python3
"""Full-choice-set estimation of the anchored location models (estimate_locations.py segments and the outing first stop,
estimate_subtour_dest.py OTHER_wbs), 2026-11-04.  Same records, chosen form, final specification F and warm start as the
sampled-set models of record; only the choice set changes (all 1,588 zones, no sampling correction).  Chunked likelihood of
estimate_fullset_taz.py with one location configuration per record (tract-to-zone measurement model of the destination only).

    TAZ_THREADS=6 python3 activity/lib/tasha_estimation/estimate_fullset_loc.py
Outputs: results/fullset_loc_estimates.csv, results/fullset_loc_compare.csv, results/fullset_loc_heldout.csv.
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, time
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import estimate_fullset_taz as F_       # noqa: E402  (wraps dc_model, sets threads)
import dc_taz_engine as X               # noqa: E402
import dc_common as C                   # noqa: E402
import estimate_locations as L          # noqa: E402
import torch                            # noqa: E402
from scipy.optimize import minimize     # noqa: E402

RES = F_.RES


def fit(spec, rec, cand, pur, sk, x0):
    names = spec.params(); cfg = X.single_cfg(rec); t0 = time.time()
    chunks = [F_.Chunk(rec.iloc[i:i + F_.CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + F_.CHUNK])], cfg, spec, pur, sk) for i in range(0, len(rec), F_.CHUNK)]
    bounds = [(-30.0, 15.0) if p.startswith("theta_") else (0.0, 3.0) if p == "mu_size" else (None, None) for p in names]
    x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bounds)])
    def fg(v):
        t = torch.tensor(v, requires_grad=True); tot = 0.0
        for c in chunks:
            l = -c.ll(t, spec).sum(); l.backward(); tot += float(l.detach())
        return (tot, t.grad.numpy().copy()) if np.isfinite(tot) else (1e15, np.zeros_like(v))
    r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bounds, options=dict(maxiter=3000, maxfun=12000, ftol=1e-13, gtol=1e-6, maxcor=30))
    x = torch.tensor(r.x); K = len(x)
    from torch.func import jvp
    H = torch.zeros((K, K)); G = []
    for c in chunks:
        H += torch.autograd.functional.hessian(lambda t: c.ll(t, spec).sum(), x)
        G.append(torch.stack([jvp(lambda t: c.ll(t, spec), (x,), (e,))[1] for e in torch.eye(K)], 1))
    G = torch.cat(G)
    at_bound = [p for p, v, (lo, hi) in zip(names, r.x, bounds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
    free = torch.tensor([p not in at_bound for p in names]); cov = torch.full((K, K), float("nan"))
    Hi = torch.linalg.inv(-H[free][:, free]); Gf = G[:, free]; fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
    for a, ia in enumerate(fi): cov[ia, fi] = cf[a]
    se = torch.sqrt(torch.clamp(torch.diag(cov), min=0))
    tab = pd.DataFrame({"param": names, "value": x.numpy(), "rob_se": se.numpy(), "rob_t": (x / se).numpy()})
    LL = -float(r.fun); LL0 = sum(c.ll0() for c in chunks)
    print(f"  LL {LL:.2f} (sampled-set estimates on the full set: {-fg(x0)[0]:.2f}), LL0 {LL0:.2f}, converged {r.success}, "
          f"maxgrad {float(G.sum(0).abs().max()):.2e}, {time.time() - t0:.0f} s", flush=True)
    return tab.assign(N=len(rec), LL=LL, LL0=LL0, K=K, converged=bool(r.success), at_bound=" ".join(at_bound))


def heldout_ll(spec, rec, cand, pur, sk, x):
    h = X.heldout(rec, cand, X.single_cfg(rec), spec, x, pur, sk, obs="pt"); return float(h["LL"].sum())


def main():
    import estimate_subtour_dest as W      # rebinds L.load / L.SEGS for OTHER_wbs; keep the location segments separately
    segs = [("WORK_wbwork", "WORK"), ("WORK_wbhome", "WORK"), ("WORK_wahb", "WORK"), ("EDUCATION_nonstud", "EDUCATION"), ("EDUCATION_daycare", "EDUCATION"),
            ("OTHER_wbs", "OTHER")]
    sk = C.skims(); tabs, comp, ho = [], [], []
    for seg, pur in segs:
        if seg == "OTHER_wbs": L.SEGS = {seg: dict(purpose="OTHER", forms=["primary"])}; L.load = W.load
        else:
            import importlib; importlib.reload(L)
        b = L.chosen_form(seg)
        if b is None: print(seg, "no search result"); continue
        form, _, o = b; Fm = o["models"]["F"]; spec, xs = Fm["spec"], Fm["x"].numpy(); ts = Fm["table"].set_index("param")
        rec, cand = L.load("estimation", seg, form) if seg != "OTHER_wbs" else W.load("estimation", seg)
        print(f"{seg} ({form}): N {len(rec)}, K {len(xs)}", flush=True)
        t = fit(spec, rec, cand, pur, sk, xs).assign(segment=seg, form=form); tabs.append(t); tf = t.set_index("param")
        for p in tf.index:
            comp.append(dict(segment=seg, param=p, sampled=ts.value[p], se_sampled=ts.rob_se[p], full=tf.value[p], se_full=tf.rob_se[p],
                             diff_over_se=(tf.value[p] - ts.value[p]) / ts.rob_se[p]))
        for half in ["estimation", "validation"]:
            rv, cv = L.load(half, seg, form) if seg != "OTHER_wbs" else W.load(half, seg)
            for lab, xv in [("sampled", xs), ("full set", tf.value[spec.params()].values)]:
                ll = heldout_ll(spec, rv, cv, pur, sk, xv); ho.append(dict(segment=seg, half=half, coefficients=lab, N=len(rv), LL_total=ll, LL_per_obs=ll / len(rv)))
        c = pd.DataFrame(comp); c = c[c.segment == seg]
        print(f"  |diff|/SE median {c.diff_over_se.abs().median():.2f}, max {c.diff_over_se.abs().max():.2f} ({c.loc[c.diff_over_se.abs().idxmax(), 'param']}); "
              f"hold-out LL/obs sampled {ho[-2]['LL_per_obs']:.4f}, full {ho[-1]['LL_per_obs']:.4f}", flush=True)
        pd.concat(tabs).to_csv(f"{RES}/fullset_loc_estimates.csv", index=False); pd.DataFrame(comp).to_csv(f"{RES}/fullset_loc_compare.csv", index=False)
        pd.DataFrame(ho).to_csv(f"{RES}/fullset_loc_heldout.csv", index=False)


if __name__ == "__main__":
    main()
