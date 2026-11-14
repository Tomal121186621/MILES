#!/usr/bin/env python3
"""Return home between two consecutive out-of-home episodes: binary logit, y = 1 if the person went home between them.  Data and
split as in 3_abit/tasha_estimation/estimate_return_home.py (specification without the outcome-dependent gap; pairs inside an
outing from the workplace and pairs of two work episodes excluded; estimation half 28,349 pairs, validation half 28,327);
maximum likelihood, unweighted, robust sandwich (HC0) standard errors (statsmodels), as the existing script.

Rule (stepwise.py): from the constant only, blocks added in the order below; a block is kept when the LR test against the current
model is significant at 5 %, BIC falls and the newly added terms with a prior have the expected sign.  Lettered alternatives
(competing forms of one term) are compared by BIC among those that pass.  Final check: a kept term whose sign reversed after later
blocks and whose |robust t| < 1.96 is dropped; a member of a band set (person type, car and income bands, purposes of the
preceding / following episode, episode-count and time-of-day bands; BANDS) is never dropped alone: the whole set is dropped
if the joint LR test gives p >= 0.05, else kept.  Piecewise-linear segments are not band sets.  The validation half is used once (final model and current
specification).

Block order (decided before estimation):
  1   detour via home, distance  1a ln(1 + detour km) and distance from home   1b detour km (linear) and distance from home
                                  1c detour km and ln(1 + detour km) and distance from home
  2   person                     person type (worker, K-12 student, post-secondary student, retiree, child under 5; base
                                  non-worker), female, driving licence
  3   household                  household size, child under 16, no car, fewer cars than drivers, income < $50k, >= $100k
  4   episodes                   purpose of the preceding and of the following episode (work, school, accompany, shopping,
                                  joint; base other individual discretionary)
  5   joint episodes             both episodes joint; joint episode next to a work or school episode
  6   day pattern                6a three, four, five or more out-of-home episodes (base two)   6b number of out-of-home episodes
  7   time of day                end of the preceding episode before 9:00, 15-19, from 19:00 (base 9-15)
Expected signs (point estimate): detour via home (linear and ln) -, number of out-of-home episodes (dummies and linear) -.
Distance from home, person, household, purposes, joint terms and time of day are not sign-checked.
    python3 a03_return.py   -> a03_return_fit.csv, a03_return_coef.csv, a03_return.log
"""
import os, sys
import numpy as np
import pandas as pd
import statsmodels.api as sm
HERE = os.path.dirname(os.path.abspath(__file__))
TE = os.path.abspath(f"{HERE}/../../../../3_abit/tasha_estimation"); sys.path.insert(0, TE); sys.path.insert(0, HERE)
import estimate_return_home as ER   # noqa: E402
import stepwise as S                # noqa: E402

NAME = "a03_return"
PURP = ["a_work", "a_school", "a_acc", "a_shop", "a_joint", "e_work", "e_school", "e_acc", "e_shop", "e_joint"]
STEPS = [("1", [("a", "+ detour via home: ln(1 + km); distance from home", ["lndetour", "dhome_km"]),
                ("b", "+ detour via home: km; distance from home", ["detour_km", "dhome_km"]),
                ("c", "+ detour via home: km and ln(1 + km); distance from home", ["detour_km", "lndetour", "dhome_km"])]),
         ("2", [("", "+ person: person type, gender, licence", ["worker", "stud_k12", "stud_ps", "retiree", "toddler", "female", "lic"])]),
         ("3", [("", "+ household: size, children, cars, income", ["hhsize", "kids", "car0", "carshort", "inc_low", "inc_high"])]),
         ("4", [("", "+ episodes: purposes of the preceding and following episode", PURP)]),
         ("5", [("", "+ joint episodes: both joint, joint next to work or school", ["jj", "jmand"])]),
         ("6", [("a", "+ day pattern: out-of-home episodes (3, 4, 5+)", ["nep3", "nep4", "nep5"]),
                ("b", "+ day pattern: number of out-of-home episodes", ["nep"])]),
         ("7", [("", "+ time of day: end of the preceding episode", ["am", "pm", "ev"])])]
PRIOR = {"detour_km": -1, "lndetour": -1, "nep3": -1, "nep4": -1, "nep5": -1, "nep": -1}
NAMES = {"detour_km": "detour via home (km)", "lndetour": "ln(1 + detour via home)", "dhome_km": "distance from home", "worker": "worker",
         "stud_k12": "K-12 student", "stud_ps": "post-secondary student", "retiree": "retiree", "toddler": "child under 5", "female": "female",
         "lic": "licence", "hhsize": "household size", "kids": "child under 16", "car0": "no car", "carshort": "fewer cars than drivers",
         "inc_low": "income below $50k", "inc_high": "income $100k or more", "jj": "both episodes joint", "jmand": "joint next to work or school",
         "am": "end before 9:00", "pm": "end 15-19", "ev": "end from 19:00", "nep": "number of out-of-home episodes"}
RECORD = ["const", "detour_km", "lndetour", "dhome_km", "a_work", "a_shop", "a_joint", "e_work", "e_school", "e_acc", "e_shop", "e_joint",
          "stud_k12", "toddler", "nep3", "nep4", "nep5", "pm", "ev", "jj", "jmand"]
BANDS = [("worker", "stud_k12", "stud_ps", "retiree", "toddler"), ("car0", "carshort"), ("inc_low", "inc_high"),
         tuple(PURP[:5]), tuple(PURP[5:]), ("nep3", "nep4", "nep5"), ("am", "pm", "ev")]


def load(half):
    p = ER.pairs(half); p = p[~p.workwork].copy()
    X = ER.design(p).copy(); pa = S.person_attrs(half).reindex(p.person_id.values)
    assert pa.age.notna().all()
    X["nep"] = p.nep.values.astype(float); X["female"] = pa.female.values; X["lic"] = pa.lic.values; X["hhsize"] = pa.hhsize.values.astype(float)
    X["kids"] = pa.kids.values; X["car0"] = (pa.autos.values <= 0).astype(float)
    X["carshort"] = ((pa.autos.values > 0) & (pa.autos.values < pa.drivers.values)).astype(float)
    X["inc_low"] = (pa.inc.values < 50000).astype(float); X["inc_high"] = (pa.inc.values >= 100000).astype(float)
    return X, p.y.values.astype(float)


def fit(X, y, cols):
    cols = [c for c in cols if c == "const" or X[c].std() > 0]
    m = sm.Logit(y, X[cols]).fit(disp=0, maxiter=200, cov_type="HC0")   # = estimate_return_home.fit
    return dict(LL=float(m.llf), K=len(cols), N=len(y), b=m.params, se=m.bse, t=m.tvalues, conv=bool(m.mle_retvals["converged"]))


def main():
    (Xe, ye), (Xv, yv) = load("estimation"), load("validation")
    lines = []
    def log(s): print(s); lines.append(s)
    log(f"{NAME}: estimation {len(ye):,} pairs ({ye.mean():.3f} with a return home), validation {len(yv):,} ({yv.mean():.3f})")
    f, c, cols = S.run(lambda cl: fit(Xe, ye, cl), lambda cl, b: S.binary_ll(Xv, yv, cl, b), STEPS, PRIOR, RECORD, log, NAMES, BANDS)
    f.to_csv(f"{HERE}/{NAME}_fit.csv", index=False); c.to_csv(f"{HERE}/{NAME}_coef.csv", index=False)
    open(f"{HERE}/{NAME}.log", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__": main()
