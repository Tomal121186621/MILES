#!/usr/bin/env python3
"""Outings from the usual workplace, generation: binary logit of at least one outing during a (merged) work episode at the usual
workplace of a worker with a usual workplace.  Data and split as in activity/lib/tasha_estimation/estimate_subtours.py (estimation half
8,613 episodes; validation half 8,561); Biogeme, unweighted, robust standard errors.

Rule (stepwise.py): from the constant only, blocks added in the order below; a block is kept when the LR test against the current
model is significant at 5 %, BIC falls and the newly added terms with a prior have the expected sign.  Lettered alternatives
(competing forms of one term) are compared by BIC among those that pass.  Final check: a kept term whose sign reversed after later
blocks and whose |robust t| < 1.96 is dropped; a member of a band set (age, income, car and arrival-time bands; BANDS) is never dropped
alone: the whole set is dropped if the joint LR test gives p >= 0.05, else kept.  Piecewise-linear segments are not band sets.
The validation half is used once (final model and current specification).

Block order (decided before estimation):
  1   commute distance          1a ln(1 + home-workplace km)          1b home-workplace km (linear)
  2   workplace zone            2a workplace zone >= 10,000 jobs/km2  2b ln(1 + retail and other jobs within 2 km of the workplace)
  3   person                    3a age < 30, age 55+ (bands), female, driving licence   3b age (years, linear), female, licence
  4   household                 income < $50k, income >= $100k, no car, fewer cars than drivers, child under 16
  5   work episode              5a duration piecewise linear (knots 4, 7 h)  5b duration linear (h)  5c ln duration;
                                each with the secondary-work-episode indicator (arrival from 15:00)
  6   time of day               arrival at work before 7:00, from 10:00 (base 7-10)
Expected signs (point estimate): commute distance -, workplace density / accessibility +, high income +, low income -,
child under 16 -, work duration (0-4 h, 4-7 h, linear, ln) +.  Age, gender, licence, cars, duration above 7 h, secondary
episode and arrival time have no clear prior and are not sign-checked.
    ~/.venvs/biogeme/bin/python estimation/development/tour_formation/a01_outing.py   -> a01_outing_fit.csv, a01_outing_coef.csv, a01_outing.log
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/activity"   # results of this step (data); CODE = this folder
TE = f"{TERP_HOME}/activity/lib/tasha_estimation"; sys.path.insert(0, TE); sys.path.insert(0, CODE)   # estimation code
import estimate_subtours as ES   # noqa: E402
import stepwise as S             # noqa: E402

ES.BIO = f"{HERE}/bio"           # Biogeme working files stay in the results folder
NAME = "a01_outing"
STEPS = [("1", [("a", "+ commute distance: ln(1 + km)", ["lncomm"]), ("b", "+ commute distance: km", ["km_comm"])]),
         ("2", [("a", "+ workplace zone: high job density", ["cbd_w"]), ("b", "+ workplace zone: retail jobs within 2 km", ["lnacc2"])]),
         ("3", [("a", "+ person: age bands, gender, licence", ["age_u30", "age_55p", "female", "lic"]),
                ("b", "+ person: age (linear), gender, licence", ["age10", "female", "lic"])]),
         ("4", [("", "+ household: income, cars, children", ["inc_low", "inc_high", "car0", "carshort", "kids"])]),
         ("5", [("a", "+ work episode: duration (piecewise), secondary episode", ["sp_0_4", "sp_4_7", "sp_7_inf", "sw"]),
                ("b", "+ work episode: duration (linear), secondary episode", ["dur_h", "sw"]),
                ("c", "+ work episode: ln duration, secondary episode", ["lndur", "sw"])]),
         ("6", [("", "+ time of day: arrival before 7:00, from 10:00", ["arr_early", "arr_late"])])]
PRIOR = {"lncomm": -1, "km_comm": -1, "cbd_w": 1, "lnacc2": 1, "inc_high": 1, "inc_low": -1, "kids": -1,
         "sp_0_4": 1, "sp_4_7": 1, "dur_h": 1, "lndur": 1}
NAMES = {"sp_7_inf": "work duration above 7 h", "sp_0_4": "work duration 0-4 h", "sp_4_7": "work duration 4-7 h", "sw": "secondary work episode",
         "arr_early": "arrival before 7:00", "arr_late": "arrival from 10:00", "lncomm": "commute distance", "cbd_w": "high job density at the workplace"}
RECORD = ["const", "sp_0_4", "sp_4_7", "sp_7_inf", "arr_early", "sw", "age_u30", "age_55p", "car0", "kids", "cbd_w", "lncomm"]
BANDS = [("age_u30", "age_55p"), ("inc_low", "inc_high"), ("car0", "carshort"), ("arr_early", "arr_late")]


def load(half):
    X, _ = ES.data(half); X = X.copy(); pa = S.person_attrs(half)
    X["km_comm"] = np.expm1(X.lncomm); X["age10"] = X.person_id.map(pa.age).values / 10.0; X["lic"] = X.person_id.map(pa.lic).values
    h = X.span.values / 60.0; X["dur_h"] = h; X["lndur"] = np.log(h)
    assert X[["age10", "lic"]].notna().all().all()
    assert ((X.age10 * 10 < 30).astype(float) == X.age_u30).all()
    return X


def fit(X, cols):
    cols = [c for c in cols if c == "const" or X[c].std() > 0]
    r = ES.biogeme_logit(X, cols, f"{NAME}_{len(cols)}_{abs(hash(tuple(cols))) % 10**8}"); t = r["table"]
    return dict(LL=r["LL"], K=r["K"], N=r["N"], b=t["Value"], se=t["Robust std err."], t=t["Robust t-stat."], conv=r["conv"])


def main():
    est, val = load("estimation"), load("validation")
    lines = []
    def log(s): print(s); lines.append(s)
    log(f"{NAME}: estimation {len(est):,} episodes ({est.y.mean():.3f} with an outing), validation {len(val):,} ({val.y.mean():.3f})")
    f, c, cols = S.run(lambda cl: fit(est, cl), lambda cl, b: S.binary_ll(val, val.y.values, cl, b), STEPS, PRIOR, RECORD, log, NAMES, BANDS)
    f.to_csv(f"{HERE}/{NAME}_fit.csv", index=False); c.to_csv(f"{HERE}/{NAME}_coef.csv", index=False)
    open(f"{HERE}/{NAME}.log", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__": main()
