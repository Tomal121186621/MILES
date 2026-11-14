#!/usr/bin/env python3
"""School-tour mode-choice logsums by zone pair from the RE-ESTIMATED school mode model (../accessibility/mode_logsum_new.py:
round-trip distance on every mode, bus and train sharing the person and household terms), in the layout of
2_silo/schoolchoice/work/logsum.npy (school level 3 x car class 3 x income group 4 x zone x zone) and with the representative
students, sex and licence averaging and time-of-day weights of 2_silo/schoolchoice/school_logsums.py.  Added for the re-estimated
model: children under 16 in the household = share of students of the cell younger than 16 (the student counts), fewer cars than
drivers = car class 1.
    python3 estimation/development/other_locations/l08_school_logsum.py   ->  school_logsum_new.npy, school_logsum_new_segments.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/locations"   # results of this step (data); CODE = this folder
sys.path.insert(0, f"{os.path.dirname(CODE)}/accessibility")
import mode_logsum_new as L   # noqa: E402
SC = f"{TERP_HOME}/landuse/schools"   # school-choice code
sys.path.insert(0, SC)
import school_common as C   # noqa: E402
MC = f"{C.V}/3_abit/mode_choice"


def main():
    n = len(L.C.zones())
    p = pd.read_parquet(f"{C.W}/students.parquet"); p = p[p.half == "estimation"]
    p["car_seg"] = np.select([p.car0 == 1, p.carlow == 1], [0, 1], 2)
    hh = pd.read_csv(f"{C.S}/input/microData/hh_2016.csv", usecols=["income"]); grp = np.digitize(hh.income.values, [40000, 75000, 125000])
    med16 = [float(np.median(hh.income.values[grp == g])) for g in range(4)]
    rows = []
    for si, sg in enumerate(C.SEG):
        for c in range(3):
            q = p[(p.seg == sg) & (p.car_seg == c)]; q = q if len(q) >= 10 else p[p.seg == sg]
            w = q.wtperfin.values; avg = lambda x: float((np.asarray(x, float) * w).sum() / w.sum())
            for g in range(4):
                rows.append(dict(seg=sg, si=si, car_seg=c, inc_group=g + 1, age=avg(q.age), female=avg(q.female), lic=avg(q.lic * (q.age >= 16)),
                                 hhsize=avg(q.hhsize), autos=0.0 if c == 0 else avg(q.cars), kids=avg(q.age < 16), inc17=med16[g] * 245.120 / 240.007))
    SEG = pd.DataFrame(rows)
    tw = pd.read_parquet(f"{MC}/work/tours_estimation.parquet", columns=["segment", "pout", "pret"]); tw = tw[tw.segment == "school"]
    pr = tw.groupby(["pout", "pret"]).size() / len(tw); pr = pr[pr >= 0.05]; pr /= pr.sum(); print("period pairs", pr.round(3).to_dict(), flush=True)
    LS = np.zeros((3, 3, 4, n, n), np.float32); dest = np.arange(n)
    for (po, pt), share in pr.items():
        for r in SEG.itertuples():
            for male, ws in ((1.0, 1 - r.female), (0.0, r.female)):
                for lic, wl in ((1.0, r.lic), (0.0, 1 - r.lic)):
                    if wl <= 0: continue
                    for i0 in range(0, n, 200):
                        o = np.arange(i0, min(i0 + 200, n)); k = len(o)
                        person = dict(age=np.full(k, r.age), male=np.full(k, male), lic=np.full(k, lic), hhsize=np.full(k, r.hhsize),
                                      autos=np.full(k, r.autos), short=np.full(k, float(r.car_seg == 1)), kids=np.full(k, r.kids),
                                      inc_year=np.full(k, r.inc17), joint=np.zeros(k), stops=np.zeros(k), pout=np.full(k, int(po)), pret=np.full(k, int(pt)))
                        ls = L.mode_logsum_new("school", o, np.broadcast_to(dest, (k, n)), person)
                        LS[r.si, r.car_seg, r.inc_group - 1, i0:i0 + k] += (share * ws * wl * ls).astype(np.float32)
        print(f"period pair {po},{pt} done", flush=True)
    np.save(f"{HERE}/school_logsum_new.npy", LS)
    old = np.load(f"{C.W}/logsum.npy", mmap_mode="r")
    for r in SEG.itertuples():
        x = LS[r.si, r.car_seg, r.inc_group - 1]; SEG.loc[r.Index, "ls_mean"] = float(x.mean())
        SEG.loc[r.Index, "corr_old"] = float(np.corrcoef(np.asarray(old[r.si, r.car_seg, r.inc_group - 1]).ravel()[::97], x.ravel()[::97])[0, 1])
    SEG.to_csv(f"{HERE}/school_logsum_new_segments.csv", index=False); print(SEG.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
