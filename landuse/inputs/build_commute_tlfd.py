#!/usr/bin/env python3
"""Commuting-time frequency distribution for SILO's job search (CommutingTimeProbabilityImpl: file input/hts_work_tripLengthFrequencyDistribution.csv,
columns TravelTime (1..200 minutes, 1-minute steps), frequency, Utility = relative frequency scaled to a maximum of 1), from the
2023 household travel survey: reported travel time of home-work car-driver trips, trip weights, smoothed with a Gaussian
kernel (sd 3 min) because single-minute reports cluster on multiples of 5.  Replaces the legacy MSTM curve."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"
r = pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv", low_memory=False, usecols=["o_activity", "d_activity", "travel_mode", "reported_travel_time", "wttrdfin"])
r = r[(r.travel_mode == 4) & (((r.o_activity == 1) & (r.d_activity == 2)) | ((r.o_activity == 2) & (r.d_activity == 1))) & r.reported_travel_time.between(1, 200)]
raw = r.groupby(r.reported_travel_time.round().astype(int)).wttrdfin.sum().reindex(range(1, 201), fill_value=0.0)
t = np.arange(1, 201); k = np.exp(-0.5 * ((t[:, None] - t[None, :]) / 3.0) ** 2); sm = (k * raw.values[None, :]).sum(1) / k.sum(1)
freq = sm / sm.sum(); util = freq / freq.max()
pd.DataFrame({"TravelTime": t, "frequency": np.round(freq, 7), "Utility": np.round(util, 6)}).to_csv(f"{V}/2_silo/input/hts_work_tripLengthFrequencyDistribution.csv", index=False)
print(f"survey trips {len(r):,} (weighted {r.wttrdfin.sum():,.0f}); mean {np.average(t, weights=freq):.1f} min; mode {t[util.argmax()]} min; share within 30 min {freq[:30].sum():.2f}")
