#!/usr/bin/env python3
"""Household-structure terms in the tour mode choice (2026-11-02), estimation half only (work/gc_bio_<segment>_s50.parquet).

    ~/.venvs/biogeme/bin/python activity/lib/mode_choice/estimate_hh.py            -> results/hh_<segment>_<block>.csv / _cov.csv, results/hh_summary.csv
    ~/.venvs/biogeme/bin/python activity/lib/mode_choice/estimate_hh.py export     -> results/gc_<segment>_hh.csv (the selected models)

Why.  Applied in ABIT, the models of record give 5-6 pp too few car-driver tours on the survey's own households, although they
reproduce the shares on the observed tours.  Two causes are specification gaps that the household stage of the application then
counts twice:
  joint   a tour whose main activity is a joint household episode.  The survey's joint tours are 18 % of the tours with 36 % car
          driver against 63 % for the other tours.  Without the term the constants mix both, so every individual tour gets the
          passenger propensity of the joint tours, and the household stage then makes the joint tours' passengers once more.
  short   fewer cars than licensed drivers in the household (and at least one car).  Without the term the model over-predicts
          car driver in these households (55 % against 47 % on the observed tours) and the vehicle allocation of the household
          stage reduces it once more.
  acc, rec  accompanying and recreation tours within the 'other' segment (base: other errands).  The pooled constants put
          accompanying 8 pp too low in car driver on the observed tours and recreation 5 pp too high.
Blocks are added in this order to the model of record of each segment (estimate_gc.CHOSEN), each on the five non-reference
modes (car passenger, walk, bike, bus, train), and kept when the likelihood-ratio test is significant at 5 % and BIC falls.
Hold-out: log-likelihood of the validation half (gc_hold_<segment>_s50.parquet).
Application (MarylandTourNestedModeChoice): joint and short are estimation controls; ABIT applies them as 0, because the
household stage generates the joint tours' passengers and the car shortages of the household explicitly.  acc and rec apply.
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/mode_choice"   # data folder; CODE = this folder
import estimate_gc as G   # noqa: E402

RES = G.RES
BLOCKS = {"work": [("short", ["short"])], "school": [("short", ["short"])],
          "shopping": [("joint", ["joint"]), ("short", ["short"])],
          "other": [("joint", ["joint"]), ("purpose", ["acc", "rec"]), ("short", ["short"])]}
NONREF = ["WK", "BK", "CP", "BUS", "TRAIN"]


def prep(df):
    df = df.copy()
    df["joint"] = df.joint.astype(bool).astype(float)
    df["short"] = ((df.autos > 0) & (df.autos < df.drivers)).astype(float)
    df["acc"] = df.purpose.eq("ACCOMPANY").astype(float); df["rec"] = df.purpose.eq("RECREATION").astype(float)
    return df


def model(tag, df, base, extra, name):
    """estimate_gc.model with extra person / tour variables on the non-reference modes"""
    old = list(G.SOCIO)
    try:
        G.SOCIO[:] = old + extra
        return G.model(tag, df, nested=base.startswith("nl"), dest="_dest" in base, generic=base.endswith("_gen"), name=name)
    finally:
        G.SOCIO[:] = old


def holdout_ll(seg, b, extra):
    """log-likelihood of the validation half with the estimates b (utility of MarylandTourNestedModeChoice / mc_apply)"""
    import mc_apply as A
    f = prep(pd.read_parquet(f"{G.WORK}/gc_hold_{seg}_s50.parquet"))
    old = list(A.SOCIO)
    try:
        A.SOCIO[:] = old + extra; V, av = A.utilities(f, b)
    finally:
        A.SOCIO[:] = old
    P = A.probs(V, av, b); y = np.array([A.ALTS.index(c) for c in f.choice.values])
    return float(np.log(np.clip(P[np.arange(len(f)), y], 1e-300, None)).sum()), len(f)


def run():
    rows, keep = [], {}
    for seg, blocks in BLOCKS.items():
        base = G.CHOSEN[seg]; df = prep(G.load(seg))
        rc, alts = G.model(seg, df, asc_only=True, name="constants_hh"); llc = float(rc.final_loglikelihood)
        r, alts = model(seg, df, base, [], f"{base}_ref"); st = G.save(seg, f"{base}_ref", r, df, alts, llc)
        b = G.table(r).Value.to_dict(); st["holdout_LL"], st["holdout_N"] = holdout_ll(seg, b, [])
        st.update(block="model of record", added="", LR=np.nan, df=np.nan, p=np.nan, kept=True); rows.append(st)
        extra, cur = [], st
        for bname, vars_ in blocks:
            name = f"hh_{'_'.join(extra + vars_)}"
            r, alts = model(seg, df, base, extra + vars_, name); x = G.save(seg, name, r, df, alts, llc)
            b = G.table(r).Value.to_dict(); x["holdout_LL"], x["holdout_N"] = holdout_ll(seg, b, extra + vars_)
            t = G.lr(cur, x); ok = t["p"] < 0.05 and x["BIC"] < cur["BIC"]
            x.update(block=bname, added=",".join(vars_), kept=ok, **t); rows.append(x)
            print(f"{seg} + {bname}: LL {cur['LL']:.1f} -> {x['LL']:.1f}, LR {t['LR']:.1f} ({t['df']}), p {t['p']:.2g}, BIC {cur['BIC']:.1f} -> {x['BIC']:.1f}, "
                  f"hold-out LL {cur['holdout_LL']:.1f} -> {x['holdout_LL']:.1f}: {'kept' if ok else 'not kept'}", flush=True)
            if ok: extra, cur = extra + vars_, x
        keep[seg] = (base, extra, f"hh_{'_'.join(extra)}" if extra else f"{base}_ref")
    S = pd.DataFrame(rows); S.to_csv(f"{RES}/hh_summary.csv", index=False)
    pd.DataFrame([dict(segment=s, base=v[0], extra=",".join(v[1]), model=v[2]) for s, v in keep.items()]).to_csv(f"{RES}/hh_selected.csv", index=False)
    print(S[["segment", "model", "block", "K", "LL", "BIC", "holdout_LL", "LR", "df", "p", "kept"]].round(2).to_string())


def export():
    """results/gc_<seg>_hh.csv = the selected model (read by export_mc.py)"""
    sel = pd.read_csv(f"{RES}/hh_selected.csv")
    for r in sel.itertuples():
        t = pd.read_csv(f"{RES}/gc_{r.segment}_{r.model}.csv"); t.to_csv(f"{RES}/gc_{r.segment}_hh.csv", index=False)
        c = pd.read_csv(f"{RES}/gc_{r.segment}_{r.model}_cov.csv", index_col=0); c.to_csv(f"{RES}/gc_{r.segment}_hh_cov.csv")
        sd = np.sqrt(np.diag(c.values)); R = c.values / np.outer(sd, sd); np.fill_diagonal(R, 0)
        i, j = np.unravel_index(np.abs(R).argmax(), R.shape)
        print(f"{r.segment}: {r.model} ({len(t)} parameters); largest |r| of two estimates {abs(R[i, j]):.2f} ({c.index[i]}, {c.index[j]}); "
              f"pairs above 0.8: {int((np.abs(R) > 0.8).sum() / 2)}")


if __name__ == "__main__":
    export() if sys.argv[-1] == "export" else run()
