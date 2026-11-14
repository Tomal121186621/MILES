#!/usr/bin/env python3
"""Employment rate by single year of age and sex for the employment model's labour-participation targets: share of persons who are
employed (ACS PUMS ESR 1, 2, 4, 5; civilian and armed forces, at work or with a job), Maryland, PUMS 2013-17 five-year file, person
weights, smoothed over a 3-year age window. Output: 2_silo/input/laborParticipationRates.csv (age, male, female)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import zipfile, pandas as pd, numpy as np
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
zf = zipfile.ZipFile(f"{ROOT}/inputs/pums_2017_5yr/csv_pmd.zip"); n = [x for x in zf.namelist() if x.endswith(".csv")][0]
P = pd.read_csv(zf.open(n), usecols=["PWGTP", "AGEP", "SEX", "ESR", "RELP"], low_memory=False); P = P[~P.RELP.isin([16, 17])]   # households only
P["emp"] = P.ESR.isin([1, 2, 4, 5]).astype(int); rows = []
for sex, col in [(1, "male"), (2, "female")]:
    d = P[P.SEX == sex]; e = d.groupby("AGEP").apply(lambda g: pd.Series(dict(w=g.PWGTP.sum(), ew=(g.PWGTP * g.emp).sum())))
    e = e.reindex(range(0, 100), fill_value=0); sm = e.rolling(3, center=True, min_periods=1).sum(); rows.append((col, (sm.ew / sm.w.replace(0, np.nan)).fillna(0).round(4)))
T = pd.DataFrame({"age": range(0, 100), rows[0][0]: rows[0][1].values, rows[1][0]: rows[1][1].values}); T.to_csv(f"{V}/2_silo/input/laborParticipationRates.csv", index=False)
a = P[P.AGEP >= 16]; print(f"employed share 16+: {(a.PWGTP * a.emp).sum() / a.PWGTP.sum():.4f}; ages 25-54 male {T.loc[25:54].male.mean():.3f} female {T.loc[25:54].female.mean():.3f}; 65-69 {T.loc[65:69][['male', 'female']].mean().round(3).to_dict()}")
