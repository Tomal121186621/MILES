#!/usr/bin/env python3
"""Work-tour mode-choice logsums by zone pair from the RE-ESTIMATED work mode model (../accessibility/mode_logsum_new.py), in
the layout of 2_silo/jobchoice/work_rts/logsum.npy (car class 3 x income group 4 x zone x zone, zone index order) and with the
same representative workers (RTS estimation-half workers with a fixed workplace, weights wtperfin x pi_g: mean age, licence
share, household size, cars; logsum averaged over the sex dummy with the segment's male share) and the same time-of-day weights
(period pairs of the estimation-half work tours with a share of at least 1 %) as 2_silo/jobchoice/rts_02_logsum.py.  Added for
the re-estimated model: children (segment share with a child), fewer cars than drivers (car class), joint = 0, stops at the
estimation-sample mean of work tours.
    python3 estimation/development/workplace_choice/w05_logsum.py   ->  logsum_new.npy, logsum_new_segments.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/workplace"   # results of this step (data); CODE = this folder
sys.path.insert(0, f"{os.path.dirname(CODE)}/accessibility")
import mode_logsum_new as L   # noqa: E402

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; S = f"{V}/2_silo"
JC = f"{S}/jobchoice"; W = f"{JC}/work_rts"; MC = f"{V}/3_abit/mode_choice"; RTS = f"{ABIT_HOME}/input/rts/RTS_raw_flat_data.csv"


def segments():
    p = pd.read_parquet(f"{W}/workers.parquet"); p = p[p.half == "estimation"]
    lic = pd.read_csv(RTS, usecols=["person_id", "license"], low_memory=False).drop_duplicates("person_id").set_index("person_id").license
    p["lic"] = (p.person_id.map(lic) == 1).astype(float)
    pp = pd.read_csv(f"{S}/input/microData/pp_2016.csv", usecols=["hhID", "occupation"]); hh = pd.read_csv(f"{S}/input/microData/hh_2016.csv", usecols=["id", "income"])
    hw = hh[hh.id.isin(pp.hhID[pp.occupation == 1])]
    grp = np.digitize(hw.income.values, [40000, 75000, 125000]); med16 = [float(np.median(hw.income.values[grp == g])) for g in range(4)]
    rows = []
    for c in range(3):
        for g in range(4):
            w = p.wtperfin.values * p[f"pg{g + 1}"].values * (p.car_seg.values == c); sw = w.sum()
            avg = lambda x: float((np.asarray(x, float) * w).sum() / sw)
            rows.append(dict(car_seg=c, inc_group=g + 1, age=avg(p.age), female=avg(p.female), lic=avg(p.lic), hhsize=avg(p.hhsize),
                             autos=avg(p.cars), kids=avg(p.children > 0), inc17=med16[g] * 245.120 / 240.007))
    return pd.DataFrame(rows)


def main():
    SEG = segments(); n = len(L.C.zones())
    tw = pd.read_parquet(f"{MC}/work/tours_estimation.parquet"); tw = tw[tw.segment == "work"]
    pr = tw.groupby(["pout", "pret"]).size() / len(tw); pr = pr[pr >= 0.01]; pr /= pr.sum()
    stops = float((tw.stops > 0).mean()) if "stops" in tw else 0.0
    print("period pairs", pr.round(3).to_dict(), "stops share", round(stops, 3), flush=True)
    LS = np.zeros((3, 4, n, n), np.float32); dest = np.arange(n)
    for (po, pt), share in pr.items():
        for r in SEG.itertuples():
            autos = 0.0 if r.car_seg == 0 else r.autos
            for male, ws in ((1.0, 1 - r.female), (0.0, r.female)):
                for i0 in range(0, n, 200):
                    o = np.arange(i0, min(i0 + 200, n)); k = len(o)
                    person = dict(age=np.full(k, r.age), male=np.full(k, male), lic=np.full(k, r.lic), hhsize=np.full(k, r.hhsize),
                                  autos=np.full(k, autos), short=np.full(k, float(r.car_seg == 1)), kids=np.full(k, r.kids), inc_year=np.full(k, r.inc17),
                                  joint=np.zeros(k), stops=np.full(k, stops), pout=np.full(k, int(po)), pret=np.full(k, int(pt)))
                    ls = L.mode_logsum_new("work", o, np.broadcast_to(dest, (k, n)), person)
                    LS[r.car_seg, r.inc_group - 1, i0:i0 + k] += (share * ws * ls).astype(np.float32)
        print(f"period pair {po},{pt} done", flush=True)
    np.save(f"{HERE}/logsum_new.npy", LS)
    for r in SEG.itertuples():
        x = LS[r.car_seg, r.inc_group - 1]; SEG.loc[r.Index, "ls_mean"] = float(x.mean()); SEG.loc[r.Index, "ls_p05"] = float(np.percentile(x, 5))
    old = np.load(f"{W}/logsum.npy", mmap_mode="r")
    SEG["corr_old"] = [float(np.corrcoef(np.asarray(old[r.car_seg, r.inc_group - 1]).ravel()[::97], LS[r.car_seg, r.inc_group - 1].ravel()[::97])[0, 1]) for r in SEG.itertuples()]
    SEG.to_csv(f"{HERE}/logsum_new_segments.csv", index=False); print(SEG.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
