#!/usr/bin/env python3
"""Export the tour mode choice (GC specification, estimate_gc.py) for ABIT (MarylandTourNestedModeChoice).

    python3 activity/lib/mode_choice/export_mc.py los      -> export/los/: zones.csv (idx, id, bbsr, wmata) and float32 matrices (little endian, row-major
                                     n x n, NaN = no path): dist, car_<P>, walk_<P>_{bus,all,rail}, drive_<P>_{all,rail,acc},
                                     prior_bus, prior_train
    python3 activity/lib/mode_choice/export_mc.py coef     -> <set>/tour_mode_choice.csv (the model of record of each segment, estimate_gc.CHOSEN) and the
                                     run_params.csv rows mode.choice.model, mc.coef.file, mc.los.dir, mc.vot.share, mc.tours.out
                                     (+ mc.asc.adjust in the calibrated set coef_tasha_cal)"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/mode_choice"   # data folder; CODE = this folder
import mc_common as M   # noqa: E402
EXP = f"{HERE}/export/los"; A3 = os.path.dirname(HERE)
# 2026-11-02: household-structure terms (estimate_hh.py): work + short, shopping + joint, other + joint and purpose; school unchanged
CHOSEN = {"work": "hh", "school": "mnl", "shopping": "hh", "other": "hh"}
CHOSEN_PRE_REEST = {"work": "nl_dest_gen", "school": "mnl", "shopping": "mnl_gen", "other": "nl_dest_gen"}


def los():
    os.makedirs(EXP, exist_ok=True); z = M.C.zones(); L = M.los()
    pd.DataFrame(dict(idx=z.idx, id=z.id, bbsr=z.bbsr.astype(int), wmata=M.wmata_zone().astype(int))).to_csv(f"{EXP}/zones.csv", index=False)
    w = lambda name, a: np.ascontiguousarray(a, dtype="<f4").tofile(f"{EXP}/{name}.f32")
    w("dist", L["d"]); w("prior_bus", L["prior_bus"]); w("prior_train", L["prior_train"])
    for k, p in enumerate(M.PERIODS):
        w(f"car_{p}", L["car_t"][k])
        for c in ["bus", "all", "rail"]: w(f"walk_{p}_{c}", L[("walk", p)][c])
        for c in ["all", "rail", "acc"]: w(f"drive_{p}_{c}", L[("drive", p)][c])
    for f in os.listdir(EXP):   # matrices of the earlier specification
        if f.endswith(".f32") and f[:-4] not in {"dist", "prior_bus", "prior_train"} | {f"car_{p}" for p in M.PERIODS} | {f"walk_{p}_{c}" for p in M.PERIODS for c in ["bus", "all", "rail"]} | {f"drive_{p}_{c}" for p in M.PERIODS for c in ["all", "rail", "acc"]}:
            os.remove(f"{EXP}/{f}")
    print("written", EXP, len(os.listdir(EXP)), "files")


def coef(sets=("coef_tasha", "coef_tasha_cal")):
    rows = []
    for seg, mod in CHOSEN.items():
        t = pd.read_csv(f"{M.RES}/gc_{seg}_{mod}.csv")
        rows += [dict(segment=seg, parameter=r.Name, value=r.Value) for r in t.itertuples()]
    c = pd.DataFrame(rows)
    for s in sets:
        d = f"{A3}/{s}"; c.to_csv(f"{d}/tour_mode_choice.csv", index=False)
        rp = pd.read_csv(f"{d}/run_params.csv"); rp = rp[~rp.key.str.startswith(("mode.choice.model", "mc."))]
        add = [("mode.choice.model", "tour_nl"), ("mc.coef.file", f"{d}/tour_mode_choice.csv"), ("mc.los.dir", EXP), ("mc.vot.share", "0.5"), ("mc.tours.out", "true"),
               ("mc.zero.terms", "joint;short")]
        if s.endswith("_cal"): add.append(("mc.asc.adjust", f"{d}/mc_asc_adjust.csv"))
        pd.concat([rp, pd.DataFrame(add, columns=["key", "value"])]).to_csv(f"{d}/run_params.csv", index=False)
        print("written", f"{d}/tour_mode_choice.csv", "and run_params.csv")


if __name__ == "__main__":
    los() if sys.argv[1] == "los" else coef(tuple(sys.argv[2:]) or ("coef_tasha", "coef_tasha_cal"))
