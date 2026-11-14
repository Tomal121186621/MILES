#!/usr/bin/env python3
"""Shared forward-block procedure of the activity models (a01_outing, a02_outing_mode, a03_return).

Rule (the same as for every other model of the re-specification):
  - start from the constant only; add blocks in the pre-stated order;
  - a block is KEPT when the LR test against the current model is significant at 5 %, BIC falls and every newly added term
    with a prior has the expected sign (point estimate); otherwise "not kept: LR" / "not kept: BIC" / "not kept: sign";
  - competing functional forms of one term are lettered alternatives of one step (3a, 3b, ...); each is tested against the
    current model by the same rule and, among those that pass, the lowest BIC is "chosen", the others "not chosen: BIC";
  - final check: a kept term whose sign reversed after later blocks and whose |robust t| < 1.96 is dropped (one step per term,
    smallest |t| first, with the LR of dropping it); no other backward elimination.  A member of a band set (dummies sharing one
    reference: income, cars, age, time-of-day, purpose, person-type bands; `bands`) is never dropped alone: the whole set is
    dropped when the joint LR test of dropping it has p >= 0.05, else the whole set is kept (tested once).  Piecewise-linear
    segments are not band sets;
  - the validation half is used once: final model and the current specification (re-estimated on the estimation half).
fit(cols) must return dict(LL, K, N, b, se, t, conv) with b, se, t pandas Series indexed by the column names.
"""
# COPY of Validation_2026/side_experiments/respec_2026-11/step_by_step/activity/stepwise.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import numpy as np
import pandas as pd
from scipy.stats import chi2


def bic(r): return np.log(r["N"]) * r["K"] - 2 * r["LL"]


def run(fit, val_ll, steps, prior, record_cols, log=print, names=None, bands=()):
    """steps: list of (step, [(letter, label, cols), ...]).  prior: {term: +1 / -1}.  val_ll(cols, b) -> validation LL.
    bands: band sets (tuples of columns sharing one reference)."""
    names = names or {}
    fit_rows, coef_rows = [], []

    def add_coef(step, r):
        for p in r["b"].index: coef_rows.append(dict(step=step, param=p, coef=r["b"][p], se=r["se"][p], t=r["t"][p]))

    cols = ["const"]; cur = fit(cols); add_coef("0", cur)
    fit_rows.append(dict(step="0", label="constant only", K=cur["K"], LL=cur["LL"], BIC=bic(cur), decision="kept"))
    log(f"0 constant only: K {cur['K']} LL {cur['LL']:.1f} BIC {bic(cur):.1f} conv {cur['conv']}")
    kept_sign = {}
    for step, alts in steps:
        res = []
        for letter, label, add in alts:
            sid = f"{step}{letter}"; new = [c for c in add if c not in cols]
            r = fit(cols + new); add_coef(sid, r)
            lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; p = float(chi2.sf(lr, df)) if df > 0 else np.nan
            bad = [c for c in new if c in prior and np.sign(r["b"][c]) != prior[c]]
            why = "LR" if not (p < 0.05) else ("BIC" if bic(r) >= bic(cur) else ("sign" if bad else None))
            res.append(dict(sid=sid, label=label, r=r, new=new, lr=lr, df=df, p=p, why=why, bad=bad))
            log(f"{sid} {label}: K {r['K']} LL {r['LL']:.1f} BIC {bic(r):.1f} LR {lr:.1f} ({df}) p {p:.3g} conv {r['conv']}"
                + (f" wrong sign: {', '.join(f'{c} {r['b'][c]:+.3f} (t {r['t'][c]:.2f})' for c in bad)}" if bad else ""))
        ok = [x for x in res if x["why"] is None]
        best = min(ok, key=lambda x: bic(x["r"])) if ok else None
        for x in res:
            if x["why"] is not None: dec = f"not kept: {x['why']}"
            elif len(res) == 1: dec = "kept"
            else: dec = "chosen" if x is best else "not chosen: BIC"
            fit_rows.append(dict(step=x["sid"], label=x["label"], K=x["r"]["K"], LL=x["r"]["LL"], BIC=bic(x["r"]), LR=x["lr"], df=x["df"], p=x["p"], decision=dec))
            log(f"   -> {x['sid']}: {dec}")
        if best is not None:
            cols = cols + best["new"]; cur = best["r"]
            for c in best["new"]: kept_sign[c] = np.sign(cur["b"][c])
    # final check: sign reversed after later blocks and no longer significant; band sets only as a whole (joint LR)
    k, done = 0, set()
    band = lambda c: next((tuple(x for x in b if x in cols) for b in bands if c in b), None)
    while True:
        cand = [c for c in cols if c != "const" and np.sign(cur["b"][c]) != kept_sign[c] and abs(cur["t"][c]) < 1.96 and band(c) not in done]
        if not cand: break
        c = min(cand, key=lambda c: abs(cur["t"][c])); k += 1; grp = band(c) or (c,)
        r = fit([x for x in cols if x not in grp]); lr = 2 * (cur["LL"] - r["LL"]); df = cur["K"] - r["K"]; p = float(chi2.sf(lr, df)); sid = f"D{k}"
        add_coef(sid, r); lab = ", ".join(names.get(x, x) for x in grp)
        if len(grp) == 1:
            fit_rows.append(dict(step=sid, label=f"- {lab} (sign reversed, not significant)", K=r["K"], LL=r["LL"], BIC=bic(r), LR=lr, df=df, p=p, decision="dropped"))
            log(f"{sid} drop {c}: coef {cur['b'][c]:+.3f} t {cur['t'][c]:.2f}; LR of dropping {lr:.2f}")
            cols = [x for x in cols if x != c]; cur = r; continue
        drop = p >= 0.05; done.add(grp)
        fit_rows.append(dict(step=sid, label=f"- band set {lab} ({names.get(c, c)}: sign reversed, not significant; joint LR)", K=r["K"], LL=r["LL"],
                             BIC=bic(r), LR=lr, df=df, p=p, decision="dropped" if drop else "not dropped: joint LR"))
        log(f"{sid} band set {grp} ({c}: coef {cur['b'][c]:+.3f} t {cur['t'][c]:.2f}); joint LR of dropping {lr:.2f} ({df}) p {p:.3g} -> "
            + ("dropped" if drop else "kept"))
        if drop: cols = [x for x in cols if x not in grp]; cur = r
    vf = val_ll(cols, cur["b"]); add_coef("final", cur)
    fit_rows.append(dict(step="final", label="final model", K=cur["K"], LL=cur["LL"], BIC=bic(cur), decision="", validation_LL=vf))
    rec = fit(record_cols); vr = val_ll(record_cols, rec["b"]); add_coef("record", rec)
    fit_rows.append(dict(step="record", label="current specification", K=rec["K"], LL=rec["LL"], BIC=bic(rec), decision="", validation_LL=vr))
    log(f"final: K {cur['K']} LL {cur['LL']:.1f} BIC {bic(cur):.1f} validation LL {vf:.1f}; terms {cols}")
    log(f"current specification: K {rec['K']} LL {rec['LL']:.1f} BIC {bic(rec):.1f} validation LL {vr:.1f}")
    weak = cur["t"].drop("const").abs(); weak = weak[weak < 1.96]
    if len(weak): log("final terms with |robust t| < 1.96: " + ", ".join(f"{c} {cur['t'][c]:.2f}" for c in weak.index))
    fit_df = pd.DataFrame(fit_rows, columns=["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"])
    return fit_df, pd.DataFrame(coef_rows, columns=["step", "param", "coef", "se", "t"]), cols


def binary_ll(X, y, cols, b):
    v = X[cols].values.astype(float) @ np.array([b[c] for c in cols]); p = np.clip(1 / (1 + np.exp(-v)), 1e-12, 1 - 1e-12)
    return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))


def person_attrs(half):
    """Per survey person (RTS person_id): age, female, driving licence and household size, cars, licensed drivers, income,
    child under 16 — the synthetic-population attributes of the survey population (3_abit/survey_pop/<half>)."""
    import te_common as T
    A = f"{T.A3}/survey_pop/{half}"
    pm = pd.read_csv(f"{A}/persons_map.csv").drop_duplicates("person_id").set_index("person_id")
    pp = pd.read_csv(f"{A}/pp.csv").set_index("id"); hh = pd.read_csv(f"{A}/hh.csv").set_index("id")
    lic = pp.driversLicense.astype(str).eq("True")
    hp = pd.DataFrame({"drivers": lic.groupby(pp.hhID).sum(), "minage": pp.age.groupby(pp.hhID).min(), "inc": pp.income.groupby(pp.hhID).sum()})
    pid = pm.id; hid = pid.map(pp.hhID)
    return pd.DataFrame({"age": pid.map(pp.age), "female": pid.map(pp.gender).eq(2).astype(float), "lic": pid.map(lic).fillna(False).astype(float),
                         "hhsize": hid.map(hh.hhSize), "autos": hid.map(hh.autos), "drivers": hid.map(hp.drivers),
                         "inc": hid.map(hp.inc), "kids": (hid.map(hp.minage) < 16).astype(float)}, index=pm.index)
