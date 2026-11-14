#!/usr/bin/env python3
"""Share of vacant housing units that are on the market (for rent, rented but not yet occupied, for sale, sold but not yet
occupied) by 2010 PUMA, from the ACS PUMS 2013-17 Maryland housing file (VACS vacancy status, housing-unit weights).  Seasonal
and recreational units, migrant-worker units and "other vacant" units (largely long-term vacant or abandoned stock) are not
available to movers and are excluded from the vacant dwelling stock that SILO's moves, construction and pricing models see.
Output: 1_vae/output/market_vacancy_by_puma_2016.csv (puma, vacant_w, market_w, market_share) and the Maryland total."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import zipfile, pandas as pd
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
zf = zipfile.ZipFile(f"{ROOT}/inputs/pums_2017_5yr/csv_hmd.zip"); n = [x for x in zf.namelist() if x.endswith(".csv")][0]
H = pd.read_csv(zf.open(n), usecols=["PUMA", "WGTP", "TYPE", "VACS"], low_memory=False); v = H[(H.TYPE == 1) & H.VACS.notna()].copy()
v["market"] = v.VACS.isin([1, 2, 3, 4]); g = v.groupby("PUMA").apply(lambda d: pd.Series(dict(vacant_w=d.WGTP.sum(), market_w=d.WGTP[d.market].sum()))).reset_index()
g["market_share"] = (g.market_w / g.vacant_w).round(4); g.to_csv(f"{V}/1_vae/output/market_vacancy_by_puma_2016.csv", index=False)
print(f"Maryland vacant units (PUMS 2013-17, weighted) {g.vacant_w.sum():,.0f}; on the market {g.market_w.sum():,.0f} ({g.market_w.sum() / g.vacant_w.sum():.3f}); by PUMA min {g.market_share.min():.3f} (PUMA {g.loc[g.market_share.idxmin(), 'PUMA']}) max {g.market_share.max():.3f}")
