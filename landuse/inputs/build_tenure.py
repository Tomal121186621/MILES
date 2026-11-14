#!/usr/bin/env python3
"""Years in the current dwelling for the base-year households and the duration term of the move-or-not decision (Baltimore 2026,
resloc.model = mnl). ACS PUMS 2014-18 (Maryland, households, WGTP), MV = when the householder moved into the unit:
1 = 12 months or less (0 years), 2 = 13-23 months (1), 3 = 2-4 years, 4 = 5-9, 5 = 10-19, 6 = 20-29, 7 = 30 years or more (30-39),
by age band of the householder (the engine uses the oldest member).
Output 1: 2_silo/input/tenure_by_age.csv (age_from, age_to, dur_from, dur_to, share): the engine draws a band, then a year
uniformly within it, for every base-year household.
Output 2 (printed, data/silo_tenure_hazard.csv): the hazard of moving by years in the dwelling implied by the stock distribution
under stationarity (density per year of duration within each band ~ survival; hazard between band midpoints), and the slope
gamma of logit(hazard) on ln(1 + years), the duration coefficient resloc.move.duration of the move-or-not decision."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import zipfile, numpy as np, pandas as pd
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
def rd(f, cols):
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/{f}") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]; return pd.read_csv(zf.open(n), usecols=cols, low_memory=False)
H = rd("csv_hmd.zip", ["SERIALNO", "WGTP", "MV", "TYPE", "NP"]); P = rd("csv_pmd.zip", ["SERIALNO", "AGEP", "RELP"])
H = H[(H.TYPE == 1) & (H.NP > 0)].merge(P[P.RELP == 0][["SERIALNO", "AGEP"]], on="SERIALNO")
DUR = {1: (0, 0), 2: (1, 1), 3: (2, 4), 4: (5, 9), 5: (10, 19), 6: (20, 29), 7: (30, 39)}
AGES = [(15, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 74), (75, 120)]
rows = []
for a0, a1 in AGES:
    g = H[H.AGEP.between(a0, a1)]; s = g.groupby("MV").WGTP.sum(); s = s / s.sum()
    for mv, (d0, d1) in DUR.items(): rows.append(dict(age_from=a0, age_to=a1, dur_from=d0, dur_to=d1, share=round(float(s.get(mv, 0)), 5)))
pd.DataFrame(rows).to_csv(f"{V}/2_silo/input/tenure_by_age.csv", index=False)
s = H.groupby("MV").WGTP.sum(); s = s / s.sum(); w = np.array([1, 1, 3, 5, 10, 10]); f = s.loc[1:6].values / w
mid = np.array([.5, 1.5, 3.5, 7.5, 15, 25]); h = 1 - (f[1:] / f[:-1]) ** (1 / np.diff(mid)); dm = (mid[1:] + mid[:-1]) / 2
b = np.polyfit(np.log1p(dm), np.log(h / (1 - h)), 1)
pd.DataFrame(dict(years=dm, hazard=h)).to_csv(f"{V}/data/silo_tenure_hazard.csv", index=False)
print("hazard by years in dwelling:", dict(zip(dm.round(1), h.round(3)))); print(f"gamma (logit hazard on ln(1+years)) = {b[0]:.3f}, intercept {b[1]:.3f}")
