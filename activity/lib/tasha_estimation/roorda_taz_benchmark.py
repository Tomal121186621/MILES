#!/usr/bin/env python3
"""Roorda distances against a TAZ-placed benchmark (2026-10-29).  validate_survey.survey_activities places survey trip ends at
the zone of the tract internal point; here the observed skim distance of a trip is instead the expected skim over the TAZ
location mixtures of its two ends (prep_dc_taz.Locator: housing-unit weights for home ends, job weights otherwise; tract skim
kept where an end has no location).  Model side unchanged.  -> data/abit_roorda_tables_tazbench.csv, abit_roorda_bench_compare.csv"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import inspect, os, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
import roorda_taz as RT                       # noqa: E402  (settings of the TAZ sets)
import prep_dc_taz as PT                      # noqa: E402
import dc_common as C                         # noqa: E402
RV = RT.RV; ZID = C.zones().id.values; LOC = PT.Locator()
RAW = pd.read_csv(f"{RV.RTS}/rts_trips_clean.csv", low_memory=False, usecols=["tripid", "o_activity", "d_activity", "o_tpb_taz", "o_bmc_taz", "d_tpb_taz", "d_bmc_taz", "o_tract_fips", "d_tract_fips"]).set_index("tripid")


def taz_km(t, dm):
    r = RAW.reindex(t.tripid.values); out = t.km_skim.values.copy()
    for i, (tid, row) in enumerate(r.iterrows()):
        go, gd = t.o_geoid.values[i], t.d_geoid.values[i]
        a = LOC(row.o_bmc_taz, row.o_tpb_taz, go, "home" if row.o_activity == 1 else "work")[0]
        b = LOC(row.d_bmc_taz, row.d_tpb_taz, gd, "home" if row.d_activity == 1 else "work")[0]
        if a and b: out[i] = min(sum(wa * wb * dm[ZID[za], ZID[zb]] for za, wa in a.items() for zb, wb in b.items()), RV.DIST_CAP_KM)
    return out


src = inspect.getsource(RV.survey_activities)
src = src.replace('g = geoid(t.tripid.map(r[f"{e}_state_county_fips"]), t[f"{e}_tract_fips"]); t[f"{e}_zone"]', 'g = geoid(t.tripid.map(r[f"{e}_state_county_fips"]), t[f"{e}_tract_fips"]); t[f"{e}_geoid"] = g.values; t[f"{e}_zone"]')
anchor = 't.loc[ok, "km_skim"] = np.minimum(dm[t.o_zone[ok].values, t.d_zone[ok].values], DIST_CAP_KM)'
assert anchor in src and 't[f"{e}_geoid"]' in src
src = src.replace(anchor, anchor + "\n    t['km_skim'] = _taz_km(t, dm)")
ns = RV.__dict__; ns["_taz_km"] = taz_km; exec(src, ns)
TG = sys.argv[1].split(",") if len(sys.argv) > 1 else ["behavnow", "behavtaz2"]   # e.g. behavnow,rec1029
SETS = [f"{k}_{t}" for t in TG for k in ["verification", "validation"]]
T = pd.concat([RV.run_setting(s)[0] for s in SETS], ignore_index=True); T.to_csv(f"{RV.V}/data/abit_roorda_tables_tazbench{'' if len(sys.argv) < 2 else '_' + '_'.join(TG)}.csv", index=False)
O = pd.read_csv(f"{RV.V}/data/abit_roorda_tables_taz.csv"); rows = []
for bench, D in [("tract", O), ("TAZ", T)]:
    for s in SETS:
        g = D[(D.setting == s) & (D.variant == "base")].set_index("type")
        rows.append(dict(benchmark=bench, setting=s, **{f"km_{x}": g.diff_km_pct.get(x, np.nan) for x in ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME", "ALL"]}, obs_km_ALL=g.observed_km.get("ALL")))
R = pd.DataFrame(rows); R.to_csv(f"{RV.V}/data/abit_roorda_bench_compare{'' if len(sys.argv) < 2 else '_' + '_'.join(TG)}.csv", index=False); print(R.round(2).to_string(index=False))
