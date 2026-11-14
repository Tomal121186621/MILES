#!/usr/bin/env python3
"""School tour mode choice, model development (replaces the school part of m08_sequence.py): the m08 blocks, with
  M1a/b/c  level of service: time on the motorised modes (m08) / round-trip distance on every mode / both
  P        person and household terms common to bus and train (one transit set) instead of one set per mode
  M4a', M4b'  the area-type blocks again with one transit set
Licence normalised to 0 on walk (as m08: not identified against the constants since car driver needs a licence).
Blocks kept by the m08 rule (LR at 5 %, BIC, signs); lettered rows are alternatives compared by BIC among those that pass.
Estimation half only; the validation half is used once, for the final model.
    ~/.venvs/biogeme/bin/python m09_school.py   ->  m09_fit.csv, m09_coef.csv"""
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import m08_sequence as M8   # noqa: E402
G, T3, K7 = M8.G, M8.T3, M8.K7
from biogeme.expressions import Beta, Variable as X   # noqa: E402
import biogeme.models as models   # noqa: E402

SEG = "school"


def loglike(df, alts, form, s, nests=None):
    """m08 utility with two options: s['km_all'] (distance on every non-reference mode), s['pool_pt'] (bus and train share the
    person and household coefficients)."""
    V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}
    los = s.get("los")
    km = (G.ALTS[1:] if s.get("km_all") else ["WK", "BK"]) if los else []
    for a in alts:
        if a == "CD": continue
        for v in s.get("socio", []):
            if a == "WK" and v in ("rural_d", "lic"): continue
            if df.loc[df[f"av_{a}"] > 0, v].std() > 0:
                tag = "PT" if s.get("pool_pt") and a in ("BUS", "TRAIN") else a
                V[a] = V[a] + Beta(f"{v}_{tag}", 0, None, None, 0) * X(v)
        if a in km: V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
    if los in ("time", True):
        bt = Beta("time", 0, None, None, 0)
        for a in T3.MOT:
            if a in alts: V[a] = V[a] + bt * X(f"t_{a}")
    if "CD" in alts:
        if s.get("park"): V["CD"] = V["CD"] + Beta("park_CD", 0, None, None, 0) * X("park")
        if s.get("stops"): V["CD"] = V["CD"] + Beta("stops_CD", 0, None, None, 0) * X("stops")
    if s.get("ovt"):
        for a in ("BUS", "TRAIN"):
            if a in alts: V[a] = V[a] + Beta("ovt", 0, None, None, 0) * X(f"ovt_{a}")
    U = {G.NUM[a]: V[a] for a in alts}; AV = {G.NUM[a]: X(f"av_{a}") for a in alts}
    if nests:
        from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit
        ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0), [G.NUM[a] for a in v if a in alts], name=k) for k, v in nests.items()]
        return models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    return models.loglogit(U, AV, X("y"))


M8.loglike = loglike
LOS = [("time on the motorised modes", dict(los="time")), ("round-trip distance on every mode", dict(los="km", km_all=True)),
       ("time and distance on every mode", dict(los="time", km_all=True))]
BLOCKS = [(c, l, b) for c, l, b in M8.BLOCKS if c not in ("M1", "M7")] + [("M7", "out-of-vehicle time, bus and train", dict(ovt=True))]


def los_ok(t):
    return all(t.Value[k] < 0 for k in t.index if k == "time" or k.startswith("km_"))


def main():
    os.chdir(f"{HERE}/bio"); fit, coef = [], []
    df = K7.data("estimation", SEG); alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]

    def add(code, label, t, x, ref, dec):
        if ref is not None and x["K"] > ref["K"]:
            lr = 2 * (x["LL"] - ref["LL"]); k = x["K"] - ref["K"]; x.update(LR=lr, df=k, p=float(chi2.sf(lr, k)))
        x.update(step=code, label=label, decision=dec); fit.append(x)
        for n, y in t.iterrows(): coef.append(dict(segment=SEG, step=code, param=n, coef=y.Value, t=y["Robust t-stat."]))
        print(f"{code} {label}: K {x['K']} LL {x['LL']:.1f} BIC {x['BIC']:.1f} LR {x.get('LR', np.nan):.1f} {dec}", flush=True)

    t, cur = M8.estimate(SEG, df, alts, "T", {}, None, "s9_M0"); add("M0", "constants", t, cur, None, "kept"); spec = {}
    res = []
    for k, (lab, blk) in enumerate(LOS):
        t, x = M8.estimate(SEG, df, alts, "T", blk, None, f"s9_M1{'abc'[k]}")
        p = float(chi2.sf(2 * (x["LL"] - cur["LL"]), x["K"] - cur["K"])); ok = p < 0.05 and x["BIC"] < cur["BIC"] and los_ok(t)
        res.append((k, lab, blk, t, x, ok, "" if ok else ("sign" if not los_ok(t) else "BIC")))
    good = [r for r in res if r[5]]; best = min(good, key=lambda r: r[4]["BIC"]) if good else None
    for k, lab, blk, t, x, ok, why in res:
        add("M1" + "abc"[k], "level of service: " + lab, t, x, cur, "chosen" if best and k == best[0] else f"not chosen: {why or 'BIC'}")
    if best: spec, cur = dict(best[2]), best[4]
    for code, label, blk in BLOCKS:
        s2 = M8.merge(spec, blk); s2.update({k: v for k, v in spec.items() if k in ("los", "km_all")})
        t, x = M8.estimate(SEG, df, alts, "T", s2, None, f"s9_{code}")
        p = float(chi2.sf(2 * (x["LL"] - cur["LL"]), x["K"] - cur["K"])); ok = p < 0.05 and x["BIC"] < cur["BIC"]
        if code == "M6": ok = ok and t.Value["park_CD"] < 0
        if code == "M7": ok = ok and t.Value["ovt"] < 0
        add(code, label, t, x, cur, "kept" if ok else "not kept")
        if ok: spec, cur = s2, x
    # parsimony: one transit set of person and household coefficients
    s2 = dict(spec, pool_pt=True); t, x = M8.estimate(SEG, df, alts, "T", s2, None, "s9_P")
    lr = 2 * (cur["LL"] - x["LL"]); k = cur["K"] - x["K"]; p = float(chi2.sf(lr, k)) if k > 0 else 1.0
    dec = "kept (restriction)" if x["BIC"] < cur["BIC"] else "not kept: BIC"
    add("P", "bus and train share the person and household coefficients", t, x, None, dec); fit[-1].update(LR=lr, df=k, p=p)
    if dec.startswith("kept"): spec, cur = s2, x
    # area-type blocks again, now with one transit set (fewer parameters than in M4a/M4b)
    for code, label, extra in [("M4a'", "location: home zone core city / rural (one transit set)", ["core_o", "rural_o"]),
                               ("M4b'", "location: main-activity zone core city / rural (one transit set)", ["core_d", "rural_d"])]:
        s2 = dict(spec, socio=spec.get("socio", []) + extra); t, x = M8.estimate(SEG, df, alts, "T", s2, None, f"s9_{code[:-1]}p")
        p = float(chi2.sf(2 * (x["LL"] - cur["LL"]), x["K"] - cur["K"])); ok = p < 0.05 and x["BIC"] < cur["BIC"]
        add(code, label, t, x, cur, "kept" if ok else "not kept")
        if ok: spec, cur = s2, x
    bn = None
    for nm, ne in M8.NESTS.items():
        t, x = M8.estimate(SEG, df, alts, "T", spec, ne, f"s9_M8_{nm.split()[0]}")
        mus = [t.Value[i] for i in t.index if i.startswith("mu_")]
        ok = x["BIC"] < cur["BIC"] and all(1.0001 < m < 9.99 for m in mus)
        add("M8", f"nesting: {nm}", t, x, cur, "kept" if ok else "not kept")
        if ok and bn is None: bn, nb = ne, x
    t, x = M8.estimate(SEG, df, alts, "T", spec, bn, "s9_final")
    ho = K7.data("validation", SEG); x["holdout_LL"] = M8.holdout(SEG, ho, alts, "T", spec, bn, t.Value.to_dict()); x["spec"] = str(spec); x["nests"] = str(bn)
    add("final", "final model", t, x, None, "final"); print("validation LL", round(x["holdout_LL"], 1), flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/m09_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m09_coef.csv", index=False)


if __name__ == "__main__":
    main()
