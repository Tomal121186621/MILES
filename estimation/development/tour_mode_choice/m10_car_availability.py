#!/usr/bin/env python3
"""Car-driver availability of the estimation data consistent with the TASHA car allocation of the application (2026-11-09,
MarylandTourNestedModeChoice, mc.car.allocation = tasha): a tour's car driver is available only if the person has a licence,
is 16+ and the household has a car (mc_common.features2) AND at no instant inside the tour's window are `autos` or more household
cars simultaneously in use by car-driver units of the OTHER household members (the engine's simultaneous-use rule of the TASHA
allocation, MarylandTourNestedModeChoice.allocate).  Window = leaving home to returning home, half-open [leave, arrive)
(tours_<half>.parquet leave, arrive; the engine takes the same times from the tour's legs: departure of the first leg from home,
arrival home of the last).
Unit = one car-driver tour (choice2 CD) of another member; the car-driver tours of one recorded joint episode (household,
jgid of the main episode) count as one unit (window = their union); the tour's own joint group is excluded.  A tour observed as
car driver keeps car driver available (data conflict, e.g. a car from outside the household): counted and reported.
    blocked(half) -> boolean array over the rows of work/tours_<half>.parquet (True = car driver not available)
    python3 estimation/development/tour_mode_choice/m10_car_availability.py   -> m10_car_availability.csv (per half and segment)"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/mode_choice"   # results of this step (data); CODE = this folder
MC = f"{TERP_HOME}/activity/lib/mode_choice"
sys.path.insert(0, MC); sys.path.insert(0, f"{os.path.dirname(MC)}/tasha_estimation")
_cache = {}


def jgid_of_main(t, half):
    import te_common as TE
    e = TE.episodes(half)[["tripid", "arr_min", "jgid"]].drop_duplicates("tripid").set_index("tripid")
    out = np.full(len(t), -1.0)
    for i, (tids, st) in enumerate(zip(t.tripids.values, t.start.values)):
        for tid in tids:
            if tid in e.index and e.at[tid, "arr_min"] == st: out[i] = e.at[tid, "jgid"]; break
    return out


def analyse(half):
    if half in _cache: return _cache[half]
    import mc_common as M
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet").reset_index(drop=True)
    t["jg"] = jgid_of_main(t, half)
    base = (t.lic > 0) & (t.autos > 0) & (t.age >= 16)
    blk = np.zeros(len(t), bool); conflict = np.zeros(len(t), bool)
    for hid, g in t.groupby("household_id"):
        cd = g[g.choice2 == "CD"]
        if cd.empty: continue
        # car-driver units: joint episode -> one unit (union window), else the tour
        units = []
        for key, u in cd.groupby(np.where(cd.jg >= 0, "j" + cd.jg.astype(int).astype(str), "t" + cd.index.astype(str))):
            units.append((set(u.person_id), u.jg.iloc[0] if key.startswith("j") else -1, u.leave.min(), u.arrive.max()))
        autos = int(g.autos.iloc[0])
        for i, r in g.iterrows():
            if not base[i]: continue
            oth = [(a, b) for ps, jg, a, b in units if r.person_id not in ps and not (r.jg >= 0 and jg == r.jg) and a < r.arrive and r.leave < b]
            # cars in use at the instants where the count can change inside the window: its start and the other units' starts
            pts = [r.leave] + [a for a, b in oth if r.leave < a < r.arrive]
            n = max((sum(1 for a, b in oth if a <= t < b) for t in pts), default=0)
            if n >= autos:
                if r.choice2 == "CD": conflict[i] = True
                else: blk[i] = True
    _cache[half] = (t, blk, conflict); return _cache[half]


def blocked(half):
    return analyse(half)[1]


def main():
    rows = []
    for half in ["estimation", "validation"]:
        t, blk, cf = analyse(half)
        for seg in ["work", "shopping", "other", "school"]:
            s = t.segment.eq(seg).values; base = ((t.lic > 0) & (t.autos > 0) & (t.age >= 16)).values & s
            rows.append(dict(half=half, segment=seg, tours=int(s.sum()), cd_available_plain=int(base.sum()), cd_unavailable_now=int((blk & s).sum()),
                             observed_cd_kept_available=int((cf & s).sum())))
    r = pd.DataFrame(rows); r.to_csv(f"{HERE}/m10_car_availability.csv", index=False); print(r.to_string(index=False))


if __name__ == "__main__":
    main()
