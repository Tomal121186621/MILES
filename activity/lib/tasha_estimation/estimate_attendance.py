#!/usr/bin/env python3
"""Work attendance of the TASHA generator with a year-specific telework input (stage 3 finalisation, 2026-10-23).

    python3 activity/lib/tasha_estimation/estimate_attendance.py      -> results/attendance_estimates.csv, attendance_fit.csv, tasha_attendance.csv

Model: a worker with a usual workplace (segment worker_usual) is at the usual workplace on a weekday (at least one PW or SW
episode) with probability
    P(attend) = (1 - min(0.6, k p_c)) (1 - q0)
p_c = ACS work-at-home share of workers in the home county c in the year simulated (temporal_2024/build_telework.py: workers
at work in the reference week, means of transportation 'worked from home'), k = the day factor (work-at-home days per usual
work-at-home worker share, including hybrid workers), q0 = the absence for other reasons (leave, sickness, no work that day).
Estimation (ESTIMATION half; the validation half only for the check):
  k   the ratio of the mean usual telework-day share of the survey's usual-workplace workers (j1_telecommute_days / 5, 0 for
      workers not eligible or choosing not to telecommute; person weights) to the mean ACS 2017-19 work-at-home share of their
      home counties (telework/wfh_attendance_2017_19.csv, the survey's interview years): the county share does not identify k in
      the cross-section (attendance has no gradient over the narrow 3-8 % range; ML gives k = 0.03, s.e. 0.51), the person-level
      telework days do (travel-day attendance 0.79 with no telework day, 0.58 with two, 0.36 with three);
  q0  maximum likelihood (person weights) of the attendance of all usual-workplace workers of the model input (travellers and
      imputed non-travellers) given k;
  standard errors: household-cluster bootstrap (200 replications).
In ABIT (MarylandTashaGenerator, tasha_params attendance.*): a worker who does not attend makes no
PW / SW episode that day; a worker who attends draws PW and SW from their frequency distributions conditional on at least one
of them.  Persons in the model input: travellers and the imputed non-travelling workers (TASHA segments of
build_distributions.py; an imputed worker is split over the workplace types by the age-band shares, and does not attend).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import te_common as T            # noqa: E402

TW = f"{T.A3}/temporal_2024/telework"
CAP = 0.6


def sample(half):
    pm, per, t = T.load_half(half)
    hh_child = pm.groupby("household_id").age.min().lt(16)
    pms, _ = T.TD.segments(pm, per, hh_child)
    w = pms[pms.seg.eq("worker_usual")].copy()
    e = T.episodes(half); att = e[e.type.isin(["PW", "SW"])].person_id.unique()
    w["y"] = np.where(w.imputed, 0, w.person_id.isin(att)).astype(float)
    p = pd.read_csv(f"{TW}/wfh_attendance_2017_19.csv").set_index("countyfips").p
    w["p"] = w.county.map(p)
    w = w[w.p.notna() & (w.w > 0)]
    return w[["id", "person_id", "household_id", "county", "imputed", "w", "y", "p"]]


def prob(theta, p):
    k, q0 = theta
    return (1 - np.minimum(CAP, k * p)) * (1 - q0)


def nll(theta, d):
    pr = np.clip(prob(theta, d.p.values), 1e-9, 1 - 1e-9); y = d.y.values
    return -float((d.w.values * (y * np.log(pr) + (1 - y) * np.log(1 - pr))).sum())


def telework_days(d):
    r = pd.read_csv(f"{T.RTS}/RTS_raw_flat_data.csv", usecols=["person_id", "j1_telecommute", "j1_telecommute_days"], low_memory=False).drop_duplicates("person_id").set_index("person_id")
    tc = d.person_id.map(r.j1_telecommute); dd = pd.to_numeric(d.person_id.map(r.j1_telecommute_days).astype(str).replace({"5+": "5"}), errors="coerce")
    days = np.where(tc.isin([2, 3]), 0.0, dd); days = np.where((tc == 1) & (days < 0), np.nan, days)
    return pd.Series(np.minimum(days, 5), index=d.index)


def fit(d):
    t = d[~d.imputed].assign(days=lambda x: telework_days(x)); t = t[t.days.notna() & (t.days >= 0)]
    k = np.average(t.days / 5, weights=t.w) / np.average(t.p, weights=t.w)
    r = minimize(lambda q: nll([k, q[0]], d), x0=[0.2], method="L-BFGS-B", bounds=[(0.0, 0.9)])
    return np.array([k, r.x[0]]), len(t)


def estimate():
    est, val = sample("estimation"), sample("validation")
    th, nt = fit(est); rng = np.random.default_rng(2026); hh = est.household_id.unique(); B = []
    g = {h: i for h, i in est.groupby("household_id").groups.items()}
    for b in range(200):
        idx = np.concatenate([g[h] for h in rng.choice(hh, len(hh))]); B.append(fit(est.loc[idx])[0])
    se = np.std(B, axis=0, ddof=1)
    tab = pd.DataFrame(dict(parameter=["k (day factor)", "q0 (other absence)"], value=th, boot_se=se, t=th / se, n=[nt, len(est)]))
    tab.to_csv(f"{T.RES}/attendance_estimates.csv", index=False)
    pd.DataFrame([dict(key="attendance.k", value=round(th[0], 6)), dict(key="attendance.q0", value=round(th[1], 6)), dict(key="attendance.cap", value=CAP)]).to_csv(
        f"{T.RES}/tasha_attendance.csv", index=False)
    rows = []
    p24 = pd.read_csv(f"{TW}/wfh_attendance_2024.csv").set_index("countyfips").p
    for half, d in [("estimation", est), ("validation", val)]:
        pr = prob(th, d.p.values)
        rows.append(dict(half=half, group="all", persons=len(d), observed=np.average(d.y, weights=d.w), predicted=np.average(pr, weights=d.w),
                         predicted_2024_shares=np.average(prob(th, d.county.map(p24).fillna(d.p).values), weights=d.w)))
        t = d[~d.imputed].assign(days=lambda x: telework_days(x), pr=lambda x: prob(th, x.p.values)); t = t[t.days.notna() & (t.days >= 0)]
        rows.append(dict(half=half, group="travellers: telework-day share / k p", persons=len(t), observed=np.average(t.days / 5, weights=t.w), predicted=np.average(np.minimum(CAP, th[0] * t.p), weights=t.w)))
        d = d.assign(pr=pr, g=pd.qcut(d.p, 4, duplicates="drop").astype(str))
        for gg, x in d.groupby("g"): rows.append(dict(half=half, group=f"p {gg}", persons=len(x), observed=np.average(x.y, weights=x.w), predicted=np.average(x.pr, weights=x.w)))
    fit_ = pd.DataFrame(rows); fit_.to_csv(f"{T.RES}/attendance_fit.csv", index=False)
    print(tab.round(4).to_string()); print(fit_.round(4).to_string())


if __name__ == "__main__":
    estimate()
