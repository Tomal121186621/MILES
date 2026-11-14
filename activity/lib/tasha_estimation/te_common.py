#!/usr/bin/env python3
"""Shared loaders of the TASHA-model estimation (stage 3 finalisation, 2026-10-23): the survey episodes of either half of the
2017/18 RTS with their TASHA activity types (the definitions of activity/distributions/build_distributions.py, applied to the half asked for),
the person segments, home / work / destination zones and the zone-skim distances.

Zones: the zone of the tract internal point (survey_population.tract_zone), the measurement convention of every stage-3
comparison; for the location MNLs the tract-to-zone measurement model of destination_choice/prep_dc_data.py is used instead
(candidate zones of the destination tract with weights b_zt).
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; A3 = os.path.dirname(HERE)
sys.path.insert(0, f"{ORIOLE_HOME}/activity/lib"); sys.path.insert(0, f"{ORIOLE_HOME}/activity/lib/destination_choice")
sys.path.insert(0, f"{ORIOLE_HOME}/activity/survey"); sys.path.insert(0, f"{ORIOLE_HOME}/activity/distributions")
import build_distributions as TD                       # noqa: E402
from rts_common import V, RTS, ACT_PURPOSE, load_split  # noqa: E402
from survey_population import tract_zone, geoid       # noqa: E402

WORK = f"{HERE}/work"; RES = f"{HERE}/results"
os.makedirs(WORK, exist_ok=True); os.makedirs(RES, exist_ok=True)


def load_half(half):
    """TD.load for either half: persons_map of the half, per-person RTS fields, trips sorted by person and trip number."""
    split = load_split(); hh = set(split[split == half].index)
    pm = pd.read_csv(f"{A3}/survey_pop/{half}/persons_map.csv"); pm = pm[pm.household_id.isin(hh)].copy()
    flat = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", low_memory=False,
                       usecols=["person_id", "tripid", "j1_workplace_loc", "work_state_county_fips", "work_tract_fips", "d_state_county_fips",
                                "d_tract_fips", "o_state_county_fips", "o_tract_fips", "school_type", "persno"])
    per = flat.drop_duplicates("person_id").set_index("person_id")
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", low_memory=False,
                    usecols=["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "dep_min", "arr_min", "wttrdfin", "travelers_hh", "age", "distance"])
    t = t[t.household_id.isin(hh)].merge(flat.drop_duplicates("tripid")[["tripid", "d_state_county_fips", "d_tract_fips", "o_state_county_fips", "o_tract_fips"]], on="tripid", how="left")
    t = t.sort_values(["person_id", "tripno"], kind="stable").reset_index(drop=True)
    return pm, per, t


def episodes(half):
    """Typed episodes of the half (TD.episodes) with segment, home / work / origin / destination zone (tract point; -1 unknown)."""
    f = f"{WORK}/episodes_{half}.parquet"
    if os.path.exists(f): return pd.read_parquet(f)
    pm, per, t = load_half(half)
    hh_child = pm.groupby("household_id").age.min().lt(16)
    pms, _ = TD.segments(pm, per, hh_child)
    e = TD.episodes(t, per)
    pseg = pms[~pms.imputed].drop_duplicates("person_id").set_index("person_id")
    e = e[e.person_id.isin(pseg.index)].copy()
    e["seg"] = e.person_id.map(pseg.seg); e["hhc"] = e.person_id.map(pseg.hhc)
    tz = tract_zone().set_index("geoid").zone
    e["oz"] = geoid(e.o_state_county_fips, e.o_tract_fips).map(tz).fillna(-1).astype(int).values
    e["dz"] = e.d_geoid.map(tz).fillna(-1).astype(int)
    e["wz"] = e.work_geoid.map(tz).fillna(-1).astype(int)
    hz = pm.drop_duplicates("person_id").set_index("person_id").home_zone
    e["hz"] = e.person_id.map(hz).fillna(-1).astype(int)
    e["w_person"] = e.person_id.map(pm.drop_duplicates("person_id").set_index("person_id").w)
    keep = ["tripid", "household_id", "person_id", "tripno", "o_activity", "d_activity", "purpose", "type", "is_home", "jgid", "jsize", "dep_min", "arr_min",
            "dur", "wttrdfin", "age", "seg", "hhc", "oz", "dz", "wz", "hz", "d_geoid", "work_geoid", "distance", "w_person"]
    e = e[keep].reset_index(drop=True); e.to_parquet(f, index=False)
    return e
