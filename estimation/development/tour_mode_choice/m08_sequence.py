#!/usr/bin/env python3
"""Tour mode choice, model development for reporting: from constants only, blocks added in a fixed order; a block is kept when
the likelihood-ratio test against the current model is significant at 5 %, BIC falls and the signs are the expected ones
(checked from m08_coef.csv).  Selection uses the estimation half only; the validation half is used once, for the final model.
  M0  constants
  M1  level of service: work generalised cost; shopping and other time + cost; school time; km on walk and bike (work: on every mode)
  M2  person: age, male, driving licence
  M3  household: household size, cars, members under 18 (2026-11-09: fewer cars than drivers removed; car availability follows the household car allocation of the application)
  M4a location: home zone core city / rural          M4b main-activity zone core city / rural
  M5  tour: joint household tour, purpose accompany / recreation (other tours), tour with stops (car driver)
  M6  paid-parking share at the destination (car driver)
  M7  out-of-vehicle time of bus and train
  M8  nesting: auto, transit, non-motorised nests (or auto and transit only), MNL otherwise
  H   (shopping) household size off car passenger (collinearity/abit_notes.md): dropped if BIC falls.  Other tours keep
      household size on every mode (dropping it lowered BIC but worsened the validation LL by 5.4).
Then the cost form of the final model (generalised cost / time + cost / time) by BIC.  Work: WESML weights.
Licence: car driver needs a licence, so licence on every other mode is identified only up to a common shift against the
constants; it is normalised to 0 on walk (licence terms are contrasts with walk).
    ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice/m08_sequence.py   ->  m08_fit.csv, m08_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
import m07_children as K7   # noqa: E402
L6 = K7.L6; G, T3 = L6.G, L6.T3
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
from biogeme.expressions import Beta, Variable as X
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit

FORM = {"work": "GC", "shopping": "TC", "other": "TC", "school": "T"}
BLOCKS = [("M1", "level of service", dict(los=True)),
          ("M2", "person: age, male, driving licence", dict(socio=["age", "male", "lic"])),
          ("M3", "household: size, cars, members under 18", dict(socio=["hhsize", "autos", "kids"])),
          ("M4a", "location: home zone core city / rural", dict(socio=["core_o", "rural_o"])),
          ("M4b", "location: main-activity zone core city / rural", dict(socio=["core_d", "rural_d"])),
          ("M5", "tour: joint, accompany / recreation, stops", dict(socio=["joint", "acc", "rec"], stops=True)),
          ("M6", "paid-parking share (car driver)", dict(park=True)),
          ("M7", "out-of-vehicle time, bus and train", dict(ovt=True))]
HHS = {"shopping": ["CP"], "other": []}
NESTS = {"three nests": G.NESTS, "auto and transit nests": {k: v for k, v in G.NESTS.items() if k != "nonmot"}}


def merge(a, b):
    s = dict(a); s["socio"] = a.get("socio", []) + b.get("socio", [])
    for k in ("los", "stops", "park", "ovt"): s[k] = a.get(k, False) or b.get(k, False)
    return s


def loglike(df, alts, form, s, nests=None):
    V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}
    km = (G.ALTS[1:] if form == "GC" else ["WK", "BK"]) if s.get("los") else []
    for a in alts:
        if a == "CD": continue
        for v in s.get("socio", []):
            if a == "WK" and v in ("rural_d", "lic") or f"{v}_{a}" in s.get("drop", ()): continue
            if df.loc[df[f"av_{a}"] > 0, v].std() > 0: V[a] = V[a] + Beta(f"{v}_{a}", 0, None, None, 0) * X(v)
        if a in km: V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
    if s.get("los"):
        bg, bt, bc = Beta("gc", 0, None, None, 0), Beta("time", 0, None, None, 0), Beta("cost", 0, None, None, 0)
        for a in T3.MOT:
            if a in alts: V[a] = V[a] + (bg * X(f"gc_{a}") if form == "GC" else bt * X(f"t_{a}") + (bc * X(f"c_{a}") if form == "TC" else 0))
    if s.get("ovt"):
        for a in ("BUS", "TRAIN"):
            if a in alts: V[a] = V[a] + Beta("ovt", 0, None, None, 0) * X(f"ovt_{a}")
    if "CD" in alts:
        if s.get("park"): V["CD"] = V["CD"] + Beta("park_CD", 0, None, None, 0) * X("park")
        if s.get("stops"): V["CD"] = V["CD"] + Beta("stops_CD", 0, None, None, 0) * X("stops")
    U = {G.NUM[a]: V[a] for a in alts}; AV = {G.NUM[a]: X(f"av_{a}") for a in alts}
    if nests:
        ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0), [G.NUM[a] for a in v if a in alts], name=k) for k, v in nests.items()]
        return models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    return models.loglogit(U, AV, X("y"))


def num(x): return x.select_dtypes(include=[np.number, bool]).astype(float)


def estimate(seg, df, alts, form, s, nests, name, start=None):
    ll = loglike(df, alts, form, s, nests); w = seg == "work"
    m = bio.BIOGEME(db.Database(name, num(df)), {"loglike": ll, "weight": X("wesml")} if w else ll, save_iterations=False, generate_html=False, generate_yaml=False)
    m.model_name = f"m08_{name}"
    if start: m.change_init_values(start)
    r = m.estimate(); t = G.table(r)
    LL = float(r.final_loglikelihood); Kp = int(r.number_of_free_parameters); N = len(df)
    return t, dict(segment=seg, model=name, K=Kp, LL=LL, BIC=Kp * np.log(N) - 2 * LL, converged=bool(r.algorithm_has_converged))


def holdout(seg, ho, alts, form, s, nests, b):
    sim = bio.BIOGEME(db.Database("h", num(ho)), {"ll": loglike(ho, alts, form, s, nests)}, save_iterations=False, generate_html=False, generate_yaml=False)
    lh = sim.simulate(the_beta_values=b)["ll"].values
    return float((lh * ho.wesml.values).sum() if seg == "work" else lh.sum())


def main():
    os.chdir(f"{HERE}/bio"); fit, coef = [], []
    segs = sys.argv[1].split(",") if len(sys.argv) > 1 else ["work", "shopping", "other", "school"]
    for seg in segs:
        df = K7.data("estimation", seg); form = FORM[seg]
        alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        def add(code, label, t, x, ref, kept):
            if ref is not None:
                lr = 2 * (x["LL"] - ref["LL"]); k = x["K"] - ref["K"]
                x.update(LR=lr, df=k, p=float(chi2.sf(lr, k)) if k > 0 else np.nan)
            x.update(step=code, label=label, kept=kept); fit.append(x)
            for n, y in t.iterrows(): coef.append(dict(segment=seg, step=code, param=n, coef=y.Value, t=y["Robust t-stat."]))
            print(f"{seg} {code} {label}: K {x['K']} LL {x['LL']:.1f} BIC {x['BIC']:.1f} LR {x.get('LR', np.nan):.1f} p {x.get('p', np.nan):.2g} "
                  f"{'kept' if kept else 'not kept'} {'' if x['converged'] else 'NOT CONVERGED'}", flush=True)
        t, cur = estimate(seg, df, alts, form, {}, None, f"{seg}_M0"); add("M0", "constants", t, cur, None, True); spec = {}
        for code, label, blk in BLOCKS:
            s2 = merge(spec, blk); t, x = estimate(seg, df, alts, form, s2, None, f"{seg}_{code}")
            p = float(chi2.sf(2 * (x["LL"] - cur["LL"]), x["K"] - cur["K"]))
            ok = p < 0.05 and x["BIC"] < cur["BIC"]
            if code == "M1" and form != "T": ok = ok and t.Value.get("gc", t.Value.get("cost", -1)) < 0 and t.Value.get("time", -1) < 0
            if code == "M1" and form == "T": ok = ok and t.Value["time"] < 0
            if code == "M6": ok = ok and t.Value["park_CD"] < 0
            if code == "M7": ok = ok and t.Value["ovt"] < 0
            add(code, label, t, x, cur, ok)
            if ok: spec, cur = s2, x
        best, bn = cur, None
        for nm, ne in NESTS.items():
            t, x = estimate(seg, df, alts, form, spec, ne, f"{seg}_M8_{nm.split()[0]}")
            mus = [t.Value[i] for i in t.index if i.startswith("mu_")]
            ok = x["BIC"] < best["BIC"] and all(1.0001 < m < 9.99 for m in mus) and float(chi2.sf(2 * (x["LL"] - cur["LL"]), x["K"] - cur["K"])) < 0.05
            add("M8", f"nesting: {nm}", t, x, cur, ok)
            if ok: best, bn = x, ne
        final = best; ffit = fit[-1] if bn is not None else None
        for a in HHS.get(seg, []):
            s2 = dict(spec, drop=spec.get("drop", []) + [f"hhsize_{a}"]); t, x = estimate(seg, df, alts, form, s2, bn, f"{seg}_H_{a}")
            ok = x["BIC"] < final["BIC"]; lr = 2 * (final["LL"] - x["LL"]); k = final["K"] - x["K"]
            add("H", f"without household size on {a}", t, x, None, ok); fit[-1].update(LR=lr, df=k, p=float(chi2.sf(lr, k)) if k > 0 else np.nan)
            if ok: spec, final = s2, x
        for f2 in [f for f in ["GC", "TC", "T"] if f != form]:
            t, x = estimate(seg, df, alts, f2, spec, bn, f"{seg}_form_{f2}")
            add("F", f"cost form {f2} instead of {form}", t, x, None, False)
            fit[-1]["dBIC_vs_final"] = x["BIC"] - final["BIC"]
            fit[-1]["signs_ok"] = all(t.Value[k] < 0 for k in ("gc", "time", "cost") if k in t.index)
            fit[-1]["los_coef"] = "; ".join(f"{k} {t.Value[k]:.4f} (t {t['Robust t-stat.'][k]:.1f})" for k in ("gc", "time", "cost") if k in t.index)
        # final model: re-estimate to get its coefficients, then the validation half once
        t, x = estimate(seg, df, alts, form, spec, bn, f"{seg}_final")
        x["los_coef"] = "; ".join(f"{k} {t.Value[k]:.4f} (t {t['Robust t-stat.'][k]:.1f})" for k in ("gc", "time", "cost") if k in t.index)
        ho = K7.data("validation", seg); x["holdout_LL"] = holdout(seg, ho, alts, form, spec, bn, t.Value.to_dict()); x["nests"] = str(bn)
        add("final", "final model", t, x, None, True)
        print(f"{seg} final: hold-out LL {x['holdout_LL']:.1f}", flush=True)
        pd.DataFrame(fit).to_csv(f"{HERE}/m08_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m08_coef.csv", index=False)


if __name__ == "__main__":
    main()
