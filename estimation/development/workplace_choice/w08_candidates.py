#!/usr/bin/env python3
"""Workplace choice, candidate terms on the simplified model S3 of w07_simplify.py (24 terms; size term ln total jobs) (2026-11-17):
  T  commute time by the worker's means: transit door-to-door time (2024 transit skim, capped at 180 min) for workers in households
     without a car, car time otherwise; replaces car time in every time term (t, ln(1 + t) and the time interactions)
  P  + paid-parking share of the workplace zone (survey estimation half, as in the tour mode model) x household with a car
  R  + own-race share of the workplace zone's workers (sensitivity; race of the worker from the survey: Hispanic, Black, white,
     other; workers by race and zone from the 2016 synthetic population, persons' job zones)
Each candidate is added to the current model and kept if BIC falls and the hold-out LL rises.
    WDC_LOGSUM=logsum_new.npy python3 w08_candidates.py   ->  w08_fit.csv, w08_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import norm
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import wdc          # noqa: E402
import w07_simplify as W7   # noqa: E402
V = f"{WORKSPACE}"; ROOT = PROJECT_ROOT
zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").sort_values("ZoneId").reset_index(drop=True); ZI = pd.Series(np.arange(len(zs)), index=zs.ZoneId.values)
# transit door-to-door time
sk = pd.read_csv(f"{V}/pipeline/test/skims/transit_2024/transit_peak_time.csv.gz"); c = sk.columns
PT = np.full((len(zs), len(zs)), 180.0); o, d = ZI.reindex(sk[c[0]]).values, ZI.reindex(sk[c[1]]).values; ok = ~(np.isnan(o) | np.isnan(d))
PT[o[ok].astype(int), d[ok].astype(int)] = np.minimum(sk[c[2]].values[ok], 180.0)
# paid-parking share of the zone
lu = pd.read_csv(f"{V}/side_experiments/respec_2026-11/step_by_step/residential/zone_landuse_2016.csv").set_index("zone").reindex(zs.ZoneId.values)
wdc.D["z_park"] = lu.park.fillna(0).values.astype(float)
# race of the survey workers (order of data.npz = workers_v2.parquet) and workers by race x job zone (2016 synthetic population)
P = pd.read_parquet(f"{V}/2_silo/jobchoice/work_rts/workers_v2.parquet")
r = pd.read_csv(f"{ABIT_HOME}/input/rts/RTS_raw_flat_data.csv", usecols=["person_id", "race_ethnicity"], low_memory=False).drop_duplicates("person_id").set_index("person_id").race_ethnicity
RC = ["white", "black", "hispanic", "other"]
wdc.D["p_race"] = P.person_id.map(r).map({4: 0, 2: 1, 1: 2}).fillna(3).astype(int).values
pp = pd.read_csv(f"{V}/2_silo/input/microData/pp_2016.csv", usecols=["race", "workplace"]); pp = pp[pp.workplace > 0]
jj = pd.read_csv(f"{V}/2_silo/input/microData/jj_2016.csv", usecols=["id", "zone"]).set_index("id").zone
pp["zone"] = pp.workplace.map(jj); S = pd.crosstab(pp.zone, pp.race).reindex(index=zs.ZoneId.values, columns=RC).fillna(0)
SHR = (S.values / np.maximum(S.values.sum(1, keepdims=True), 1)).T        # race x zone
_base, _pvar = wdc.base, wdc.pvar


def base(key, h, A, Pp):
    if key in ("tm", "ltm"):
        T = np.where((Pp["car_seg"] == 0)[:, None], PT[h[:, None], A], wdc.TT[h[:, None], A]); return T if key == "tm" else np.log1p(T)
    if key == "ownrace": return SHR[Pp["race"][:, None], A]
    return _base(key, h, A, Pp)


def pvar(name, Pp):
    if name == "car": return (Pp["car_seg"] > 0).astype(float)
    return _pvar(name, Pp)


wdc.base, wdc.pvar = base, pvar


def main():
    f7 = pd.read_csv(f"{HERE}/w07_fit.csv"); s3 = f7[f7.step == "S3"].terms.iloc[0].split()
    c7 = pd.read_csv(f"{HERE}/w07_coef.csv"); c7 = c7[c7.step == "S3"].set_index("param").coef
    tm = [("tm" + t[1:] if t.startswith("t*") else {"t": "tm", "lt": "ltm"}.get(t, t)) for t in s3]
    rows, coefs = [], []

    def run(code, lab, terms, start):
        m = W7.Equal(terms); th0 = np.array([start.get(n, 0.0) if n != "mu" else start.get("mu", 0.86) for n in m.names]); m.fit(th0); m.robust(); ho = m.holdout_ll()
        rows.append(dict(step=code, label=lab, K=m.K, N=m.N, LL=m.LL, BIC=m.BIC, validation_LL=ho, terms=" ".join(terms)))
        for n, b, s, t in m.table():
            if not n.startswith("g_"): coefs.append(dict(step=code, param=n, coef=b, se=s, t=t, p=2 * norm.sf(abs(t))))
        print(f"{code} {lab}: K {m.K} LL {m.LL:.2f} BIC {m.BIC:.1f} hold-out {ho:.2f}", flush=True)
        pd.DataFrame(rows).to_csv(f"{HERE}/w08_fit.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/w08_coef.csv", index=False)
        return m, rows[-1]
    st = {("tm" + k[1:] if k.startswith("t*") else {"t": "tm", "lt": "ltm"}.get(k, k)): v for k, v in c7.items()}
    _, r0 = run("S3", "simplified model (car time for all)", s3, c7.to_dict())
    _, rT = run("T", "transit time for workers without a car", tm, st)
    cur, rc = (tm, rT) if (rT["BIC"] < r0["BIC"] and rT["validation_LL"] > r0["validation_LL"]) else (s3, r0)
    _, rP = run("P", "+ paid-parking share x car", cur + ["z_park*car"], st if cur is tm else c7.to_dict())
    if rP["BIC"] < rc["BIC"] and rP["validation_LL"] > rc["validation_LL"]: cur, rc = cur + ["z_park*car"], rP
    run("R", "+ own-race share of the workplace zone's workers (sensitivity)", cur + ["ownrace"], st if "tm" in cur else c7.to_dict())


if __name__ == "__main__":
    main()
