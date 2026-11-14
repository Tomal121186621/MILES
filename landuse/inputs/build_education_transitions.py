#!/usr/bin/env python3
"""Education and retirement transition probabilities by single year of age, from ACS PUMS Maryland (5-year file centred on
the calibration window): for EducationModelMd (file demographics.education.transitions.file).
  schoolExitProb[a]      = 1 - enrolled(a+1)/enrolled(a)   for ages 16-29 (shares smoothed by a 3-year moving average) (share of persons enrolled, SCH in {2,3}); forced exit after 29
  retireProbEmployed[a]  = 1 - employed(a+1)/employed(a)   for ages 55-85 (ESR in {1,2,4,5}), weighted; clipped to [0, 1]
  retireProbUnemployed[a]= 1 - inLabourForce(a+1)/inLabourForce(a) among non-employed ... approximated as 1.5 x employed hazard (stated)
Output: WORKSPACE/2_silo/input/education_transitions.csv; the observed shares by age are saved to data/ for validation."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import zipfile, io, pandas as pd, numpy as np, os, sys
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
VINTAGE = sys.argv[1] if len(sys.argv) > 1 else "2018"      # 5-year file 2014-2018, centred on 2016
with zipfile.ZipFile(f"{ROOT}/inputs/pums_{VINTAGE}_5yr/csv_pmd.zip") as zf:
    n = [x for x in zf.namelist() if x.endswith(".csv")][0]
    P = pd.read_csv(zf.open(n), usecols=["AGEP", "SCH", "ESR", "PWGTP"], low_memory=False)
P = P[P.AGEP.between(3, 90)]
P["enrolled"] = P.SCH.isin([2, 3]); P["employed"] = P.ESR.isin([1, 2, 4, 5]); P["inlf"] = P.ESR.isin([1, 2, 3, 4, 5])
g = P.groupby("AGEP").apply(lambda d: pd.Series(dict(w=d.PWGTP.sum(), enrolled=(d.PWGTP * d.enrolled).sum() / d.PWGTP.sum(), employed=(d.PWGTP * d.employed).sum() / d.PWGTP.sum(), inlf=(d.PWGTP * d.inlf).sum() / d.PWGTP.sum())))
g = g.reindex(range(3, 91)).interpolate()
for c in ["enrolled", "employed", "inlf"]: g[c] = g[c].rolling(3, center=True, min_periods=1).mean()   # 3-year moving average: single-year ACS ratios are noisy
rows = []
for a in range(0, 121):
    se = re_ = ru = 0.0
    if 16 <= a <= 28: se = float(np.clip(1 - g.enrolled.get(a + 1, 0) / max(g.enrolled.get(a, 1e-9), 1e-9), 0, 1))
    if a == 29: se = 1.0
    if 55 <= a <= 85:
        re_ = float(np.clip(1 - g.employed.get(a + 1, 0) / max(g.employed.get(a, 1e-9), 1e-9), 0, 1))
        ru = float(np.clip(1.5 * re_, 0, 1))
    if a > 85: re_ = ru = 0.30
    rows.append(dict(age=a, schoolExitProb=round(se, 4), retireProbEmployed=round(re_, 4), retireProbUnemployed=round(ru, 4)))
T = pd.DataFrame(rows); os.makedirs(f"{V}/2_silo/input", exist_ok=True); T.to_csv(f"{V}/2_silo/input/education_transitions.csv", index=False)
g.reset_index().rename(columns={"AGEP": "age"}).to_csv(f"{V}/data/silo_target_enrollment_employment_by_age_{VINTAGE}.csv", index=False)
print(f"PUMS {VINTAGE} MD: enrolled share age 18 {g.enrolled[18]:.2f}, 22 {g.enrolled[22]:.2f}, 25 {g.enrolled[25]:.2f}; employed share 60 {g.employed[60]:.2f}, 65 {g.employed[65]:.2f}, 70 {g.employed[70]:.2f}")
print(T[(T.age.between(17, 30)) | (T.age.between(60, 72))].to_string(index=False))
