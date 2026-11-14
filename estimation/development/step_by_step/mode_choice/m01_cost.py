#!/usr/bin/env python3
"""Tour mode choice, other and school tours: why the generalised-cost (GC) coefficient is near zero (other) or positive for bus and
train (school), and re-estimation without the duplicated distance term.
In the models of record, tour length (km) enters every non-reference mode next to GC; car GC and km correlate at 0.87-0.94, so on
car passenger, bus and train km absorbs the cost effect. Variants (same data, same extra terms as the models of record):
  R   model of record
  K   km kept only on walk and bike (no GC there); removed from car passenger, bus and train
  KG  K with one GC coefficient for all motorised modes (school only; other already generic)
Fit on the estimation half; log-likelihood of the validation half with the estimates.
    ~/.venvs/biogeme/bin/python m01_cost.py   ->  m01_fit.csv, m01_coef.csv"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
MC = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026/3_abit/mode_choice"
sys.path.insert(0, MC)
import estimate_gc as G, estimate_hh as H   # noqa: E402
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
from biogeme.expressions import Beta, Variable as X
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit

EXTRA = {"other": ["joint", "acc", "rec"], "school": []}
STRUCT = {"other": dict(nested=True, dest=True, generic=True), "school": dict(nested=False, dest=False, generic=False)}
VARIANTS = {"other": [("R", G.ALTS[1:], True), ("K", ["WK", "BK"], True)],
            "school": [("R", G.ALTS[1:], False), ("K", ["WK", "BK"], False), ("KG", ["WK", "BK"], True)]}


def loglike(df, alts, extra, km_modes, nested, dest, generic):
    V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}
    for a in alts:
        if a == "CD": continue
        for v in G.SOCIO + (G.DEST if dest else []) + extra:
            if df.loc[df[f"av_{a}"] > 0, v].std() > 0: V[a] = V[a] + Beta(f"{v}_{a}", 0, None, None, 0) * X(v)
        if a in km_modes: V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
    bg = Beta("gc", 0, None, None, 0)
    for a in G.GC_ALTS:
        if a in alts: V[a] = V[a] + (bg if generic else Beta(f"gc_{a}", 0, None, None, 0)) * X(f"gc_{a}")
    U = {G.NUM[a]: V[a] for a in alts}; AV = {G.NUM[a]: X(f"av_{a}") for a in alts}
    if nested:
        ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0), [G.NUM[a] for a in v if a in alts], name=k) for k, v in G.NESTS.items()]
        return models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    return models.loglogit(U, AV, X("y"))


def main():
    os.makedirs(f"{HERE}/bio", exist_ok=True); os.chdir(f"{HERE}/bio")
    fit, coef = [], []
    for seg, variants in VARIANTS.items():
        df = H.prep(G.load(seg)); ho = H.prep(pd.read_parquet(f"{G.WORK}/gc_hold_{seg}_s50.parquet"))
        alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        for code, km_modes, generic in variants:
            st = dict(STRUCT[seg], generic=generic)
            ll = loglike(df, alts, EXTRA[seg], km_modes, **st)
            num = lambda x: x.select_dtypes(include=[np.number, bool]).astype(float)
            m = bio.BIOGEME(db.Database(f"{seg}_{code}", num(df)), ll, save_iterations=False, generate_html=False, generate_yaml=False)
            m.model_name = f"m01_{seg}_{code}"; r = m.estimate()
            t = G.table(r); b = t.Value.to_dict()
            llh = loglike(ho, alts, EXTRA[seg], km_modes, **st)
            s = bio.BIOGEME(db.Database(f"{seg}_{code}_h", num(ho)), {"ll": llh}, save_iterations=False, generate_html=False, generate_yaml=False)
            HO = float(s.simulate(the_beta_values=b)["ll"].sum())
            LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
            fit.append(dict(segment=seg, variant=code, N=N, K=K, LL=LL, BIC=K * np.log(N) - 2 * LL, holdout_LL=HO, holdout_N=len(ho),
                            converged=bool(r.algorithm_has_converged)))
            for n, x in t.iterrows(): coef.append(dict(segment=seg, variant=code, param=n, coef=x.Value, se=x["Robust std err."], t=x["Robust t-stat."]))
            g = t.loc[[k for k in t.index if k.startswith("gc") or k.startswith("mu_")]]
            print(seg, code, f"K {K} LL {LL:.1f} BIC {fit[-1]['BIC']:.1f} hold-out {HO:.1f}", flush=True)
            print(g[["Value", "Robust t-stat."]].round(4).to_string(), flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/m01_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m01_coef.csv", index=False)


if __name__ == "__main__":
    main()
