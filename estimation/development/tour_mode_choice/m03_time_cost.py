#!/usr/bin/env python3
"""Tour mode choice, other and school tours: time and cost as separate terms instead of generalised cost (GC).
GC = time + 60 cost / VOT with VOT = 0.5 x income / 2,080 h and income floored at $5k: a $3.60 round-trip fare counts 180 min
for the lowest incomes, and low-income households ride transit most, so GC rises with the probability of choosing transit.
Variants (same data, structure and extra terms as the models of record):
  R    model of record (GC; km on every non-reference mode)
  TC   time (min) + cost ($), both generic over car driver, car passenger, bus and train; km on walk and bike only
  TCI  time + cost / (income / $50k): the cost term falls with income (Train and McFadden 1978 form); km on walk and bike only
Estimation half; log-likelihood of the validation half with the estimates.
    ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice/m03_time_cost.py   ->  m03_fit.csv, m03_coef.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
MC = f"{TERP_HOME}/activity/lib/mode_choice"
sys.path.insert(0, MC)
import estimate_gc as G, estimate_hh as H, mc_common as M   # noqa: E402
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
from biogeme.expressions import Beta, Variable as X
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit

EXTRA = {"other": ["joint", "acc", "rec"], "school": []}
STRUCT = {"other": dict(nested=True, dest=True), "school": dict(nested=False, dest=False)}
MOT = ["CD", "CP", "BUS", "TRAIN"]


def data(half, seg):
    """features of the model of record + time (min) and cost ($) per motorised mode; same rows as gc_<tag>_<seg>_s50.parquet"""
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet"); f = M.features2(t, 0.5)
    f["choice"] = t.choice2.values; f["y"] = t.choice2.map({a: i + 1 for i, a in enumerate(M.ALTS2)}).values
    for k in ["segment", "purpose", "drivers", "joint", "inc_year"]: f[k] = t[k].values
    f["t_CD"] = t.car_min.values; f["c_CD"] = t.km.values * M.OPC_KM; f["t_CP"] = t.car_min.values; f["c_CP"] = 0.0
    for a, m in [("BUS", "bus"), ("TRAIN", "train")]:
        f[f"t_{a}"] = np.where(t[f"{m}_ok"], t[f"{m}_t"], 0.0); f[f"c_{a}"] = np.where(t[f"{m}_ok"], t[f"{m}_c"], 0.0)
    inc = np.maximum(t.inc_year.values, M.INC_FLOOR) / 50000.0
    for a in MOT: f[f"ci_{a}"] = f[f"c_{a}"] / inc
    ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(f.choice.values)])
    g = H.prep(f[f.segment.eq(seg) & ok].reset_index(drop=True))
    ref = pd.read_parquet(f"{M.WORK}/gc_{'bio' if half == 'estimation' else 'hold'}_{seg}_s50.parquet")
    assert len(g) == len(ref) and np.allclose(g.gc_CD.values, ref.gc_CD.values), "rows differ from the model-of-record data"
    return g


def loglike(df, alts, extra, form, nested, dest, generic=None):
    generic = nested if generic is None else generic   # models of record: other generic (NL), school mode-specific (MNL)
    km_modes = G.ALTS[1:] if form == "R" else ["WK", "BK"]
    V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}
    for a in alts:
        if a == "CD": continue
        for v in G.SOCIO + (G.DEST if dest else []) + extra:
            if df.loc[df[f"av_{a}"] > 0, v].std() > 0: V[a] = V[a] + Beta(f"{v}_{a}", 0, None, None, 0) * X(v)
        if a in km_modes: V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
    bg, bt, bc = Beta("gc", 0, None, None, 0), Beta("time", 0, None, None, 0), Beta("cost", 0, None, None, 0)
    for a in MOT:
        if a not in alts: continue
        if form == "R": V[a] = V[a] + (bg if generic else Beta(f"gc_{a}", 0, None, None, 0)) * X(f"gc_{a}")
        else: V[a] = V[a] + bt * X(f"t_{a}") + bc * X(f"{'c' if form == 'TC' else 'ci'}_{a}")
    U = {G.NUM[a]: V[a] for a in alts}; AV = {G.NUM[a]: X(f"av_{a}") for a in alts}
    if nested:
        ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0), [G.NUM[a] for a in v if a in alts], name=k) for k, v in G.NESTS.items()]
        return models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    return models.loglogit(U, AV, X("y"))


def main():
    os.makedirs(f"{HERE}/bio", exist_ok=True); os.chdir(f"{HERE}/bio"); fit, coef = [], []
    num = lambda x: x.select_dtypes(include=[np.number, bool]).astype(float)
    for seg in ["other", "school"]:
        df, ho = data("estimation", seg), data("validation", seg)
        alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        for form in ["R", "TC", "TCI"]:
            m = bio.BIOGEME(db.Database(f"{seg}{form}", num(df)), loglike(df, alts, EXTRA[seg], form, **STRUCT[seg]), save_iterations=False, generate_html=False, generate_yaml=False)
            m.model_name = f"m03_{seg}_{form}"; r = m.estimate(); t = G.table(r); b = t.Value.to_dict()
            s = bio.BIOGEME(db.Database(f"{seg}{form}h", num(ho)), {"ll": loglike(ho, alts, EXTRA[seg], form, **STRUCT[seg])}, save_iterations=False, generate_html=False, generate_yaml=False)
            HO = float(s.simulate(the_beta_values=b)["ll"].sum())
            LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
            vot = 60 * b["time"] / b["cost"] if form != "R" else np.nan   # $/h (TCI: at $50k income)
            fit.append(dict(segment=seg, form=form, N=N, K=K, LL=LL, BIC=K * np.log(N) - 2 * LL, holdout_LL=HO, holdout_N=len(ho),
                            converged=bool(r.algorithm_has_converged), vot_per_h=vot))
            for n, x in t.iterrows(): coef.append(dict(segment=seg, form=form, param=n, coef=x.Value, se=x["Robust std err."], t=x["Robust t-stat."]))
            print(seg, form, f"K {K} LL {LL:.1f} BIC {fit[-1]['BIC']:.1f} hold-out {HO:.1f} conv {fit[-1]['converged']} VOT {vot:.1f}", flush=True)
            print(t.loc[[k for k in t.index if k.split('_')[0] in ('gc', 'time', 'cost', 'mu')], ["Value", "Robust t-stat."]].round(4).to_string(), flush=True)
    pd.DataFrame(fit).to_csv(f"{HERE}/m03_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m03_coef.csv", index=False)


if __name__ == "__main__":
    main()
