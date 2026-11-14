"""Shared helpers of the ABIT half of the collinearity check (c_abit_*.py).  Builds on c_silo_common (same within-situation
correlations, VIF, robust estimate correlations, heatmap style, flags, pair classification and refit rows); adds
  - within_corr_partial: within-situation correlation after partialling out alternative constants (wide models with person
    variables in alternative-specific utilities: z_n 1[j = a] demeaned within the situation and net of the constants equals the
    centred person variable on the person rows where the alternative is available)
  - size_extra: ln(1 + component) and ln S columns of a size term, for the theta / mu vs land-use correlations
  - check_row: one row of an explicitly requested check (pair = "CHECK: ...") for <model>_pairs.csv
Estimation half only."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c_silo_common as CC   # noqa: E402
from c_silo_common import (OUT, SBS, R_VAR, VIF_MAX, R_EST, wcorr, within, within_corr, vif, est_corr, heatmap, pairs, lr,   # noqa: F401
                           refit_row, tex_labels, plain, classify, zratio, run_alt_model)


def within_corr_partial(X, av, w, P=None):
    """as c_silo_common.within_corr, after a weighted least-squares projection of the within-situation deviations of X (N, J, K)
    on those of P (N, J, L) (e.g. the alternative constants); cells weighted as in within_corr"""
    a = av.astype(float); cw = ((w / np.maximum(a.sum(1), 1.0))[:, None] * a).ravel()
    Z = within(np.asarray(X, float), av).reshape(-1, X.shape[2])
    if P is not None:
        Q = within(np.asarray(P, float), av).reshape(-1, P.shape[2])
        A = (Q * cw[:, None]).T @ Q; B = (Q * cw[:, None]).T @ Z
        Z = Z - Q @ np.linalg.lstsq(A, B, rcond=None)[0]
    C = (Z * cw[:, None]).T @ Z; s = np.sqrt(np.diag(C)); return C / np.outer(s, s), C


def size_extra(comp, names, lnS=None):
    """comp (N or 1, J, C) raw size components; returns [(name, (N, J, 1) ln(1 + component))] (+ ln S at the final weights)"""
    out = [(f"ln1p_{n}", np.log1p(np.maximum(comp[:, :, i], 0.0))[:, :, None]) for i, n in enumerate(names)]
    if lnS is not None: out.append(("lnS", lnS[:, :, None]))
    return out


def check_row(model, check, label, base, alt, member=None, **extra):
    """refit row of an explicit check (LR / BIC against the final model, the followed member's estimate and s.e.)"""
    r = refit_row(base, alt, member, label); r.update(model=model, pair=f"CHECK: {check}"); r.update(extra); return r


def save_part(model, rows, facts):
    pd.DataFrame(rows).to_csv(f"{OUT}/{model}_pairs.csv", index=False)
    json.dump(facts, open(f"{OUT}/{model}_facts.json", "w"), indent=1, default=float)


def append_checks(model, rows, checks):
    """after run_alt_model (which writes <model>_pairs.csv / _facts.json): add the explicit-check rows and a 'checks' entry
    (list of dicts with the numbers quoted in abit_notes.md) to the facts"""
    f = f"{OUT}/{model}_pairs.csv"; P = pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()
    pd.concat([P, pd.DataFrame(rows)], ignore_index=True).to_csv(f, index=False)
    fj = f"{OUT}/{model}_facts.json"; fx = json.load(open(fj)) if os.path.exists(fj) else {}
    fx["checks"] = fx.get("checks", []) + list(checks); json.dump(fx, open(fj, "w"), indent=1, default=float)
