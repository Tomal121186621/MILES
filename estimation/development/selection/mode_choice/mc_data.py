#!/usr/bin/env python3
"""Tour mode-choice data of the re-specification (2026-11-06): the tours and variables of 3_abit/mode_choice (prep_tours.py,
mc_common.features2; the rows of work/gc_bio_<segment>_s50.parquet and gc_hold_<segment>_s50.parquet, rebuilt in the same order),
plus the components needed by the candidate level-of-service forms:

  car_min        car minutes of the round trip (period skims)                        car driver, car passenger
  cost_CD        km x 0.1112 $/km (2017 $)                                            car driver
  bus_ivt / bus_ovt     in-vehicle / out-of-vehicle minutes of the bus path; out-of-vehicle = walk access + egress + first wait
                 of the walk-access path of the period (raptor components), at most the door-to-door bus time; a half on the
                 regional (MSTM) skim counts as in-vehicle time
  train_ivt / train_ovt walk-access rail path: in-vehicle (incl. transfers) and access + egress + first wait; drive-access path:
                 in-vehicle + car access minutes, and egress + first wait
  bus_c, train_c fares (+ the car operating cost of drive access), as in the model of record
  inc_r          household income / $84,216 (income at least $5,000)
  park           share of car-driver tours that paid for parking, by the destination area (estimation half; mc_common)
  wash           home zone in the Washington region (WMATA counties)
  lnden_m        ln(1 + jobs and residents per km2 / 1000) of the main-activity zone
  stops          stops of the tour
  inc_hi         household income >= $100,000
WESML weights of the work tours: work/wesml_<est|hold>.parquet (same rows).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
V = f"{WORKSPACE}"
MCD = f"{V}/3_abit/mode_choice"   # mode-choice data (work/, results/)
sys.path.insert(0, f"{TERP_HOME}/activity/lib/mode_choice")
import mc_common as M   # noqa: E402

ALTS = ["CD", "WK", "BK", "CP", "BUS", "TRAIN"]
OUT = f"{V}/side_experiments/respec_2026-11/abit/mode_choice/work"
os.makedirs(OUT, exist_ok=True)


def los_components(t):
    L = M.los(); h, m = t.h.values, t.m.values; po, pr = t.pout.values, t.pret.values; n = len(t)
    res = {}
    for mode in ["bus", "train"]:
        ivt = np.zeros(n); ovt = np.zeros(n); tot = np.zeros(n)
        for a, b, pp, out in [(h, m, po, True), (m, h, pr, False)]:
            for pi in range(4):
                s = pp == pi
                if not s.any(): continue
                W = L[("walk", M.PERIODS[pi])]; D = L[("drive", M.PERIODS[pi])]; aa, bb = a[s], b[s]
                if mode == "bus":
                    tt = W["bus"][aa, bb]; o = np.nan_to_num(W["acc"][aa, bb] + W["egr"][aa, bb] + W["wait"][aa, bb], nan=np.inf)
                    pr_ = L["prior_bus"][aa, bb]; use_p = ~np.isfinite(tt) & np.isfinite(pr_)
                    o = np.where(np.isfinite(tt), np.minimum(o, tt), 0.0); tt = np.where(use_p, pr_, tt)
                    oo = np.where(use_p, 0.0, o); ii = tt - oo
                else:
                    tw = np.where(W["rail"][aa, bb] >= 0.5, W["all"][aa, bb], np.nan)
                    hh_, mm_ = (aa, bb) if out else (bb, aa)
                    td = np.where(D["rail"][hh_, mm_] >= 0.5, D["all"][hh_, mm_], np.nan)
                    use_d = ~np.isfinite(tw) & np.isfinite(td)
                    ow = W["acc"][aa, bb] + W["egr"][aa, bb] + W["wait"][aa, bb]
                    od = D["egr"][hh_, mm_] + D["wait"][hh_, mm_]
                    tt = np.where(use_d, td, tw); oo = np.where(use_d, od, ow)
                    pr_ = L["prior_train"][aa, bb]; use_p = ~np.isfinite(tt) & np.isfinite(pr_)
                    tt = np.where(use_p, pr_, tt); oo = np.where(use_p, 0.0, oo); ii = tt - oo
                tot[s] += np.nan_to_num(tt); ivt[s] += np.nan_to_num(ii); ovt[s] += np.nan_to_num(oo)
        res[f"{mode}_ivt"] = ivt; res[f"{mode}_ovt"] = ovt; res[f"{mode}_tot"] = tot
    return res


def build(seg, half):
    """rows of gc_<bio|hold>_<seg>_s50 with the extra variables"""
    f0 = f"{OUT}/mc_{seg}_{half}.parquet"
    if os.path.exists(f0): return pd.read_parquet(f0)
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet")
    f = M.features2(t, 0.5)
    f["choice"] = t.choice2.values; f["y"] = t.choice2.map({a: i + 1 for i, a in enumerate(M.ALTS2)}).values
    for k in ["segment", "purpose", "w", "person_id", "household_id", "county", "inc_year", "drivers", "pout", "pret", "h", "m", "stops", "joint",
              "car_min", "km", "bus_ok", "bus_t", "bus_c", "train_ok", "train_t", "train_c", "lnden_m"]:
        f[k] = t[k].values
    ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(f.choice.values)])
    sel = (f.segment.values == seg) & ok
    f = f[sel].reset_index(drop=True); tt = t[sel].reset_index(drop=True)
    comp = los_components(tt)
    for k, v in comp.items(): f[k] = v
    # check: the components add up to the times of the model of record
    for mode in ["bus", "train"]:
        okm = f[f"{mode}_ok"].values.astype(bool)
        err = np.abs(f[f"{mode}_tot"].values - f[f"{mode}_t"].values)[okm]
        assert (err.max() if len(err) else 0) < 1e-3, (mode, err.max())
    f["cost_CD"] = f.km * M.OPC_KM
    f["inc_r"] = np.maximum(f.inc_year.values, M.INC_FLOOR) / M.INC_REF
    f["park"] = M.park_share()[tt.park_area.values.astype(int)]
    f["wash"] = M.wmata_zone()[tt.h.values].astype(float)
    f["inc_hi"] = (f.inc_year >= 100000).astype(float)
    f["short"] = ((f.autos > 0) & (f.autos < f.drivers)).astype(float)
    f["joint"] = f.joint.astype(bool).astype(float)
    f["acc"] = f.purpose.eq("ACCOMPANY").astype(float); f["rec"] = f.purpose.eq("RECREATION").astype(float)
    if seg == "work":
        w = pd.read_parquet(f"{MCD}/work/wesml_{'est' if half == 'estimation' else 'hold'}.parquet")
        assert len(w) == len(f) and (w.person_id.values == f.person_id.values).all() and (w.choice.values == f.choice.values).all()
        f["wesml"] = w.wesml.values
    # same rows as the files of the model of record
    g = pd.read_parquet(f"{MCD}/work/{'gc_bio' if half == 'estimation' else 'gc_hold'}_{seg}_s50.parquet")
    assert len(g) == len(f) and np.allclose(g.gc_CD.values, f.gc_CD.values) and (g.choice.values == f.choice.values).all()
    f.to_parquet(f0, index=False)
    return f


if __name__ == "__main__":
    for s in M.SEGMENTS:
        for h in ["estimation", "validation"]:
            d = build(s, h); print(s, h, len(d), d[["bus_ivt", "bus_ovt", "train_ivt", "train_ovt"]].describe().loc[["mean", "max"]].round(1).to_dict())
