#!/usr/bin/env python3
"""Check of mode_logsum_new: log-likelihood of the estimation-half tours of each re-estimated mode model with the utility code of
mode_logsum_new.py and the final coefficients, against the final LL of m08_fit.csv / m09_fit.csv.
  (a) on the estimation data frames of the model scripts (m07_children.data: features as estimated)
  (b) on features rebuilt here from the raw tours (h, m, periods, person) with mode_logsum_new.los / features
    ~/.venvs/biogeme/bin/python validate_mode_ll.py   ->  validate_mode_ll.csv"""
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mode_logsum_new as L    # noqa: E402
sys.path.insert(0, L.MCD)
import m07_children as K7      # noqa: E402

FIT = {"work": "m08", "shopping": "m08", "other": "m08", "school": "m09"}


def ll(model, f, y, w):
    V, AV = L.utilities(model, f); ls, lp = L.logsum_and_logp(model, V, AV)
    l = np.array([lp[a][i] if a in lp else -np.inf for i, a in enumerate(y)])
    return float((l * w).sum()), ls


def main():
    t = pd.read_parquet(f"{L.M.WORK}/tours_estimation.parquet"); rows = []
    for seg in ["work", "shopping", "other", "school"]:
        df = K7.data("estimation", seg); w = df.wesml.values if seg == "work" else np.ones(len(df))
        F = pd.read_csv(f"{L.MCD}/{FIT[seg]}_fit.csv"); F = F[(F.segment == seg) & (F.step == "final")]; LLref = float(F.LL.iloc[-1])
        fa = {c: df[c].values.astype(float) for c in df.columns if df[c].dtype != object}
        lla, lsa = ll(seg, fa, df.choice.values, w)
        # (b) rebuilt from the raw tours
        v = L.los(t.h.values, t.m.values, t.pout.values, t.pret.values)
        pers = dict(age=t.age.values, male=t.male.values, lic=t.lic.values, hhsize=t.hhsize.values, autos=t.autos.values, drivers=t.drivers.values,
                    children=t.children.values, inc_year=t.inc_year.values, joint=t.joint.astype(float).values, stops=t.stops.values,
                    acc=t.purpose.eq("ACCOMPANY").astype(float).values, rec=t.purpose.eq("RECREATION").astype(float).values)
        fb = L.features(v, pers, seg)
        ok = np.array([fb[f"av_{c}"][i] > 0 for i, c in enumerate(t.choice2.values)]); sel = (t.segment.eq(seg).values & ok)
        fb = {k: x[sel] for k, x in fb.items()}; assert sel.sum() == len(df)
        dif = {k: float(np.nanmax(np.abs(fb[k] - fa[k]))) for k in fb if k in fa}
        llb, lsb = ll(seg, fb, t.choice2.values[sel], w)
        bad = {k: d for k, d in dif.items() if d > 1e-6}
        rows.append(dict(model=seg, N=len(df), LL_fit=LLref, LL_estimation_frame=lla, LL_rebuilt=llb, diff_a=lla - LLref, diff_b=llb - LLref,
                         max_feature_diff=max(dif.values()), features_differing=";".join(f"{k}:{d:.2g}" for k, d in bad.items()),
                         mean_logsum=float(np.mean(lsb))))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/validate_mode_ll.csv", index=False)


if __name__ == "__main__":
    main()
