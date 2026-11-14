#!/usr/bin/env python3
"""Impedance of the vacant-job choice (engine property job.search.impedance.file, JobDataManagerImpl.findVacantJobByCommuteTime).
f(t) = share of base-year commutes (employed persons of input/microData, home zone -> job zone) with car peak travel time t
       / share of all home-job pairs (base-year workers by home zone x jobs by zone) with travel time t,
by whole minute 0-299, both shares smoothed over 5 minutes, scaled to max 1. A destination choice over vacant jobs with this
impedance reproduces the base-year commute-time distribution. Output: input/job_search_impedance.csv (minutes, weight, shares)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, pyarrow.csv as pc
S = f"{WORKSPACE}/2_silo"; M = f"{S}/input/microData"
rd = lambda p, c: pc.read_csv(p, convert_options=pc.ConvertOptions(include_columns=c)).to_pandas()
sk = pc.read_csv(f"{S}/input/skims/auto_peak_time.csv.gz").to_pandas()
hh = rd(f"{M}/hh_2016.csv", ["id", "dwelling"]); dd = rd(f"{M}/dd_2016.csv", ["id", "zone"]); jj = rd(f"{M}/jj_2016.csv", ["id", "zone"])
pp = rd(f"{M}/pp_2016.csv", ["id", "hhID", "occupation", "workplace"]); pp = pp[(pp.occupation == 1) & (pp.workplace > 0)]
pp["hz"] = pp.hhID.map(hh.set_index("id").dwelling.map(dd.set_index("id").zone)); pp["jz"] = pp.workplace.map(jj.set_index("id").zone); pp = pp.dropna(subset=["hz", "jz"])
T = sk.set_index(["FROM", "TO"]).VALUE; t_obs = T.reindex(pd.MultiIndex.from_arrays([pp.hz.astype(int).values, pp.jz.astype(int).values])).dropna().values
sk["w"] = sk.FROM.map(pp.groupby("hz").size()).fillna(0) * sk.TO.map(jj.groupby("zone").size()).fillna(0)
bins = np.arange(0, 301); sm = lambda x: pd.Series(x).rolling(5, center=True, min_periods=1).mean().values
Po = np.histogram(np.clip(t_obs, 0, 299.9), bins)[0].astype(float); Po /= Po.sum()
Pp = np.histogram(np.clip(sk.VALUE, 0, 299.9), bins, weights=sk.w)[0]; Pp /= Pp.sum()
f = np.where(sm(Pp) > 0, sm(Po) / np.maximum(sm(Pp), 1e-12), 0); f /= f.max()
pd.DataFrame(dict(minutes=bins[:-1], weight=np.round(f, 6), observed_share=np.round(Po, 6), opportunity_share=np.round(Pp, 6))).to_csv(f"{S}/input/job_search_impedance.csv", index=False)
print(f"base-year commutes: median {np.median(t_obs):.1f} min; all home-job pairs: weighted median {np.interp(0.5, np.cumsum(Pp), bins[1:]):.0f} min -> input/job_search_impedance.csv")
