#!/usr/bin/env python3
"""Tour mode choice: variables of the literature missing from the models, added one block at a time to the cost form chosen in
m03-m05 (work: generalised cost; shopping and other: time + cost; school: car time only).
  ovt    out-of-vehicle time of bus and train (min, round trip: walk access + walk egress + first wait of the walk-access path;
         train with drive access: wait + egress walk), in addition to the total time, so out-of-vehicle minutes weigh
         (time + ovt) / time as much as in-vehicle minutes (Koppelman and Bhat 2006: 2-3)
  park   paid-parking share of car-driver tours to the destination area (results/parking_paid_share.csv, estimation half),
         car driver only: the parking variable of the car-driver utility, prepared but not used in the models of record
  stops  tour with at least one stop besides the main activity, on every non-reference mode (complex tours favour the car)
A block is kept when the likelihood-ratio test is significant at 5 %, BIC falls and the sign is the expected one.
Estimation half; log-likelihood of the validation half (work: WESML-weighted).
    ~/.venvs/biogeme/bin/python m06_literature.py   ->  m06_fit.csv, m06_coef.csv"""
# COPY of Validation_2026/side_experiments/respec_2026-11/step_by_step/mode_choice/m06_literature.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "..", "00_shared_data"))
MDATA = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "data"))
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import m03_time_cost as T3   # noqa: E402
G, H, M = T3.G, T3.H, T3.M
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models
from biogeme.expressions import Beta, Variable as X
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit

NO_NONMOT = {k: v for k, v in G.NESTS.items() if k != "nonmot"}
BASE = {"work": dict(form="GC", extra=["short"], nested=True, dest=True, nests=G.NESTS, weight=True),
        "shopping": dict(form="TC", extra=["joint"], nested=False, dest=False, nests=None, weight=False),
        "other": dict(form="TC", extra=["joint", "acc", "rec"], nested=True, dest=True, nests=NO_NONMOT, weight=False),
        "school": dict(form="T", extra=[], nested=False, dest=False, nests=None, weight=False)}
BLOCKS = ["ovt", "park", "stops"]
SIGN = {"ovt": -1, "park": -1}   # expected signs (stops: positive for car is negative on the other modes; checked by eye)


def data(half, seg):
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet"); f = M.features2(t, 0.5)
    f["choice"] = t.choice2.values; f["y"] = t.choice2.map({a: i + 1 for i, a in enumerate(M.ALTS2)}).values
    for k in ["segment", "purpose", "drivers", "joint", "inc_year", "stops"]: f[k] = t[k].values
    f["t_CD"] = t.car_min.values; f["c_CD"] = t.km.values * M.OPC_KM; f["t_CP"] = t.car_min.values; f["c_CP"] = 0.0
    for a, m in [("BUS", "bus"), ("TRAIN", "train")]:
        f[f"t_{a}"] = np.where(t[f"{m}_ok"], t[f"{m}_t"], 0.0); f[f"c_{a}"] = np.where(t[f"{m}_ok"], t[f"{m}_c"], 0.0)
    ow = (t.tw_wait + t.tw_acc + t.tw_egr).fillna(0).values; od = (t.td_wait + t.td_egr).fillna(0).values
    f["ovt_BUS"] = np.minimum(ow, f.t_BUS); dr = t.train_drive.values
    f["ovt_TRAIN"] = np.minimum((1 - dr) * ow + dr * od, f.t_TRAIN)
    sh = pd.read_csv(f"{M.RES}/parking_paid_share.csv").set_index("park_area").share
    f["park"] = t.park_area.map(sh).values
    # 2026-11-09: car-driver availability consistent with the TASHA car allocation of the application (m10_car_availability.py):
    # not available when the other members' recorded car-driver tours overlapping the tour already use all household cars
    # (tours observed as car driver keep it: data conflicts)
    import m10_car_availability as CA
    blk = CA.blocked(half); assert len(blk) == len(f)
    f.loc[blk, "av_CD"] = 0
    ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(f.choice.values)])
    g = H.prep(f[f.segment.eq(seg) & ok].reset_index(drop=True))
    ref = pd.read_parquet(f"{M.WORK}/gc_{'bio' if half == 'estimation' else 'hold'}_{seg}_s50.parquet")
    assert len(g) == len(ref) and np.allclose(g.gc_CD.values, ref.gc_CD.values)
    if seg == "work":
        w = pd.read_parquet(f"{G.WORK}/wesml_{'est' if half == 'estimation' else 'hold'}.parquet"); assert (w.choice.values == g.choice.values).all()
        g["wesml"] = w.wesml.values
    return g


def loglike(df, alts, form, extra, nested, dest, nests, blocks, **_):
    km_modes = G.ALTS[1:] if form == "GC" else ["WK", "BK"]
    socio = G.SOCIO + (G.DEST if dest else []) + extra + (["stops"] if "stops" in blocks else [])
    V = {a: (Beta(f"ASC_{a}", 0, None, None, 0) if a != "CD" else 0) for a in alts}
    for a in alts:
        if a == "CD": continue
        for v in socio:
            if a == "WK" and v == "rural_d": continue          # same variable as rural_o for walk in the sample
            if df.loc[df[f"av_{a}"] > 0, v].std() > 0: V[a] = V[a] + Beta(f"{v}_{a}", 0, None, None, 0) * X(v)
        if a in km_modes: V[a] = V[a] + Beta(f"km_{a}", 0, None, None, 0) * X("km")
    bg, bt, bc, bo = Beta("gc", 0, None, None, 0), Beta("time", 0, None, None, 0), Beta("cost", 0, None, None, 0), Beta("ovt", 0, None, None, 0)
    for a in T3.MOT:
        if a not in alts: continue
        V[a] = V[a] + (bg * X(f"gc_{a}") if form == "GC" else bt * X(f"t_{a}") + (bc * X(f"c_{a}") if form == "TC" else 0))
        if "ovt" in blocks and a in ("BUS", "TRAIN"): V[a] = V[a] + bo * X(f"ovt_{a}")
    if "park" in blocks and "CD" in alts: V["CD"] = V["CD"] + Beta("park_CD", 0, None, None, 0) * X("park")
    U = {G.NUM[a]: V[a] for a in alts}; AV = {G.NUM[a]: X(f"av_{a}") for a in alts}
    if nested:
        ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0), [G.NUM[a] for a in v if a in alts], name=k) for k, v in nests.items()]
        return models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    return models.loglogit(U, AV, X("y"))


def estimate(seg, df, ho, alts, blocks, name):
    B = BASE[seg]; num = lambda x: x.select_dtypes(include=[np.number, bool]).astype(float)
    ll = loglike(df, alts, blocks=blocks, **B)
    m = bio.BIOGEME(db.Database(name, num(df)), ll if not B["weight"] else {"loglike": ll, "weight": X("wesml")}, save_iterations=False, generate_html=False, generate_yaml=False)
    m.model_name = f"m06_{name}"; r = m.estimate(); t = G.table(r); b = t.Value.to_dict()
    s = bio.BIOGEME(db.Database(name + "h", num(ho)), {"ll": loglike(ho, alts, blocks=blocks, **B)}, save_iterations=False, generate_html=False, generate_yaml=False)
    lh = s.simulate(the_beta_values=b)["ll"].values
    LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
    return t, dict(segment=seg, model=name, blocks=",".join(blocks), N=N, K=K, LL=LL, BIC=K * np.log(N) - 2 * LL,
                   holdout_LL=float((lh * ho.wesml.values).sum() if B["weight"] else lh.sum()), converged=bool(r.algorithm_has_converged))


def main():
    os.makedirs(f"{HERE}/bio", exist_ok=True); os.chdir(f"{HERE}/bio"); fit, coef = [], []
    for seg in ["work", "shopping", "other", "school"]:
        df, ho = data("estimation", seg), data("validation", seg)
        alts = [a for a in G.ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        t, cur = estimate(seg, df, ho, alts, [], f"{seg}_base"); cur.update(added="", LR=np.nan, p=np.nan, kept=True); fit.append(cur)
        for n, x in t.iterrows(): coef.append(dict(segment=seg, model=cur["model"], param=n, coef=x.Value, t=x["Robust t-stat."]))
        print(f"{seg} base: LL {cur['LL']:.1f} BIC {cur['BIC']:.1f} hold-out {cur['holdout_LL']:.1f}", flush=True)
        kept = []
        for blk in BLOCKS:
            t, x = estimate(seg, df, ho, alts, kept + [blk], f"{seg}_{'_'.join(kept + [blk])}")
            lr = 2 * (x["LL"] - cur["LL"]); k = x["K"] - cur["K"]; p = float(chi2.sf(lr, k)) if k > 0 else np.nan
            new = [i for i in t.index if i.startswith(blk) or i.endswith(f"_{blk}") or i.startswith(f"{blk}_")]
            sign_ok = all(np.sign(t.Value[i]) == SIGN[blk] for i in new) if blk in SIGN else True
            ok = (p < 0.05) and (x["BIC"] < cur["BIC"]) and sign_ok
            x.update(added=blk, LR=lr, p=p, kept=ok); fit.append(x)
            for n, y in t.iterrows(): coef.append(dict(segment=seg, model=x["model"], param=n, coef=y.Value, t=y["Robust t-stat."]))
            print(f"{seg} + {blk}: LL {cur['LL']:.1f} -> {x['LL']:.1f}, LR {lr:.1f} ({k}), p {p:.2g}, BIC {cur['BIC']:.1f} -> {x['BIC']:.1f}, "
                  f"hold-out {cur['holdout_LL']:.1f} -> {x['holdout_LL']:.1f}; {'kept' if ok else 'not kept'}", flush=True)
            print("   ", {i: (round(t.Value[i], 4), round(t['Robust t-stat.'][i], 2)) for i in new + [i for i in t.index if i in ('gc', 'time', 'cost')]}, flush=True)
            if ok: kept, cur = kept + [blk], x
    pd.DataFrame(fit).to_csv(f"{HERE}/m06_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/m06_coef.csv", index=False)


if __name__ == "__main__":
    main()
