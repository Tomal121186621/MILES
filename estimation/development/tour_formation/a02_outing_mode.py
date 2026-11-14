#!/usr/bin/env python3
"""Outings from the usual workplace, mode: binary logit of walking on the outing (y = 1) against keeping the mode of the work
tour.  Data and split as in activity/lib/tasha_estimation/estimate_subtours.py (estimation half 1,177 outings with a known work-tour
mode and first-stop zone); Biogeme, unweighted, robust standard errors.

Rule (stepwise.py): from the constant only, blocks added in the order below; a block is kept when the LR test against the current
model is significant at 5 %, BIC falls and the newly added terms with a prior have the expected sign.  Lettered alternatives
(competing forms of one term) are compared by BIC among those that pass.  Final check: a kept term whose sign reversed after later
blocks and whose |robust t| < 1.96 is dropped; a member of a band set (age, car, income bands and the work-tour mode; BANDS) is never dropped
alone: the whole set is dropped if the joint LR test gives p >= 0.05, else kept.  Piecewise-linear segments are not band sets.
The validation half is used once (final model and current specification).

Block order (decided before estimation):
  1   distance workplace -> first stop (zone skim)   1a ln(1 + km)   1b km (linear)
  2   workplace zone        2a workplace zone >= 10,000 jobs/km2   2b ln retail-job density of the workplace zone
  3   person                age < 30, age 55+, female, driving licence
  4   household             no car, fewer cars than drivers, income < $50k, income >= $100k
  5   outing / tour         mode of the work tour (car driver, car passenger; base other modes), more than one stop
  6   time of day           departure from the workplace 11:00-14:00
Expected signs (point estimate): distance -, workplace density +, no car in the household +, work tour by car (driver,
passenger) -.  Age, gender, licence, cars < drivers, income, number of stops and departure time are not sign-checked.
    ~/.venvs/biogeme/bin/python estimation/development/tour_formation/a02_outing_mode.py   -> a02_outing_mode_fit.csv, a02_outing_mode_coef.csv, a02_outing_mode.log
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/activity"   # results of this step (data); CODE = this folder
TE = f"{ORIOLE_HOME}/activity/lib/tasha_estimation"; sys.path.insert(0, TE); sys.path.insert(0, CODE)   # estimation code
import estimate_subtours as ES   # noqa: E402
import stepwise as S             # noqa: E402
import a01_outing as A1          # noqa: E402

ES.BIO = f"{HERE}/bio"
NAME = "a02_outing_mode"
STEPS = [("1", [("a", "+ distance to the first stop: ln(1 + km)", ["lnkm"]), ("b", "+ distance to the first stop: km", ["km"])]),
         ("2", [("a", "+ workplace zone: high job density", ["cbd_w"]), ("b", "+ workplace zone: retail-job density", ["lnretden_w"])]),
         ("3", [("", "+ person: age, gender, licence", ["age_u30", "age_55p", "female", "lic"])]),
         ("4", [("", "+ household: cars, income", ["car0", "carshort", "inc_low", "inc_high"])]),
         ("5", [("", "+ outing: mode of the work tour, more than one stop", ["tm_cd", "tm_cp", "multi"])]),
         ("6", [("", "+ time of day: departure 11:00-14:00", ["midday"])])]
PRIOR = {"lnkm": -1, "km": -1, "cbd_w": 1, "lnretden_w": 1, "car0": 1, "tm_cd": -1, "tm_cp": -1}
NAMES = {"lnkm": "distance to the first stop", "km": "distance to the first stop", "cbd_w": "high job density at the workplace",
         "lnretden_w": "retail-job density at the workplace", "car0": "no car", "carshort": "fewer cars than drivers", "inc_low": "income below $50k",
         "inc_high": "income $100k or more", "tm_cd": "work tour as car driver", "tm_cp": "work tour as car passenger", "multi": "more than one stop",
         "midday": "departure 11:00-14:00", "age_u30": "age under 30", "age_55p": "age 55 or over", "female": "female", "lic": "licence"}
RECORD = ["const", "tm_cd", "tm_cp", "lnkm", "cbd_w"]
BANDS = [("age_u30", "age_55p"), ("car0", "carshort"), ("inc_low", "inc_high"), ("tm_cd", "tm_cp")]


def load(half):
    """Outings as in estimate_subtours.estimate (mdata), with person and household attributes and outing attributes added."""
    _, o = ES.data(half); z, d, _ = ES.zone_tables(); m = ES.C.id2idx()
    o = o[o.tour_mode.notna() & o["mode"].notna()].copy()
    z1 = o.zones.str.split(";").str[0].astype(int); ok = (z1 > 0) & (o.wz > 0); o = o[ok.values].copy(); z1 = z1[ok.values]
    km = d[m[o.wz.values], m[z1.values]]
    X = pd.DataFrame({"const": 1.0, "tm_cd": o.tour_mode.eq("CAR_DRIVER").astype(float).values, "tm_cp": o.tour_mode.eq("CAR_PASSENGER").astype(float).values,
                      "lnkm": np.log1p(km), "km": km, "lnretden_w": z.lnretden.values[m[o.wz.values]], "cbd_w": z.cbd.values[m[o.wz.values]],
                      "multi": (o.n_stops.values > 1).astype(float), "midday": ((o.leave.values % 1440 >= 660) & (o.leave.values % 1440 < 840)).astype(float),
                      "y": o["mode"].eq("WALK").astype(float).values, "w": o.w.values})
    pa = S.person_attrs(half).reindex(o.person_id.values)
    assert pa.age.notna().all()
    X["age_u30"] = (pa.age.values < 30).astype(float); X["age_55p"] = (pa.age.values >= 55).astype(float)
    X["female"] = pa.female.values; X["lic"] = pa.lic.values
    X["car0"] = (pa.autos.values <= 0).astype(float); X["carshort"] = ((pa.autos.values > 0) & (pa.autos.values < pa.drivers.values)).astype(float)
    X["inc_low"] = (pa.inc.values < 50000).astype(float); X["inc_high"] = (pa.inc.values >= 100000).astype(float)
    return X


def main():
    est, val = load("estimation"), load("validation")
    lines = []
    def log(s): print(s); lines.append(s)
    log(f"{NAME}: estimation {len(est):,} outings ({est.y.mean():.3f} on foot), validation {len(val):,} ({val.y.mean():.3f})")
    f, c, cols = S.run(lambda cl: A1.fit(est, cl), lambda cl, b: S.binary_ll(val, val.y.values, cl, b), STEPS, PRIOR, RECORD, log, NAMES, BANDS)
    f.to_csv(f"{HERE}/{NAME}_fit.csv", index=False); c.to_csv(f"{HERE}/{NAME}_coef.csv", index=False)
    open(f"{HERE}/{NAME}.log", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__": main()
