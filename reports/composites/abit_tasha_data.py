#!/usr/bin/env python3
"""Curves of the TASHA-form activity figures (Roorda, Miller & Habib 2008, Figs. 3/7 and 5/8) that data/abit_roorda_curves.parquet
does not hold: the replication spread of the mean duration by start hour, and the mean distance by start hour BY ACTIVITY TYPE
(the parquet has all types only), each with the standard deviation over the ten replications.

    python3 reports/composites/abit_tasha_data.py        -> data/abit_tasha_curves.parquet

Same activities, exclusions (variant 'base': persons 5+, internal trips), weights and distance measure (zone-skim distance on both
sides) as activity/validation/validate_survey.py, whose functions are used unchanged.  Settings: the behavioural model of record
(verification_behav, validation_behav, chain_behav).

Columns: setting, figure (duration | distance), type, hour (clock hour 0-23), model (pooled over the replications, as in
roorda_validation), model_sd (s.d. of the per-replication hourly means, ddof = 1), n_rep (replications with a value in the hour),
observed, n_obs (observed activities in the hour), D_hourly, P_hourly (Roorda's KS on the hourly values, constant per panel).
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
V = f"{WORKSPACE}"
sys.path.insert(0, f"{TERP_HOME}/activity/validation")
import validate_survey as RV   # noqa: E402

OUT = f"{V}/data/abit_tasha_curves.parquet"
SETS = os.environ.get("ABIT_SETTINGS", "verification_behav,validation_behav,chain_behav").split(",")   # e.g. ABIT_SETTINGS=verification_respec,validation_respec,chain_respec
MERGE = "ABIT_SETTINGS" in os.environ                    # with a setting list: keep the other settings already in the file
TYPES = RV.TYPES + ["ALL"]
MIN_OBS = {"duration": 10, "distance": 30}     # observed activities per hour (roorda_validation: duration 10, distance 30)
MIN_SHOW = 10                                  # observed activities per hour from which a value is drawn in the figures
MIN_REP = 10                                    # model activities per hour and replication for the replication spread


def curves(name):
    kind, half, runs, root = RV.SETTINGS[name]
    vpop = RV.survey_pop(half)
    pop = vpop if kind == "survey" else RV.synthetic_pop(root, runs[0], sorted(vpop.zc.unique()))
    o = RV.keep(RV.survey_activities(vpop), "base")
    mods = []
    for i, r in enumerate(runs):
        a = RV.model_activities(root, r, pop); a["rep"] = i + 1; mods.append(a)
    m = RV.keep(pd.concat(mods, ignore_index=True), "base")
    rows = []
    for ty in TYPES:
        om = o if ty == "ALL" else o[o.type == ty]; mm = m if ty == "ALL" else m[m.type == ty]
        for fig, ocol, mcol in [("duration", "dur", "dur"), ("distance", "km_skim", "km")]:
            if fig == "duration":
                om_ = om[om.dur.between(1, 1439)]; mm_ = mm[mm.dur.between(1, 1439)]
                obs = RV.hourly(om_, "dur", MIN_OBS[fig]); mod = RV.hourly(mm_, "dur", 10 * 10)
            else:
                om_ = om[om.km_skim.notna()]; mm_ = mm[mm.km.notna()]
                obs = RV.hourly(om_, "km_skim", MIN_OBS[fig]); mod = RV.hourly(mm_, "km", 300)
            obs_all = RV.hourly(om_, ocol, MIN_SHOW)     # drawn only (open markers below the KS threshold); KS uses obs
            n_obs = ((om_.start_min // 60) % 24).astype(int).value_counts().reindex(range(24), fill_value=0)
            per = pd.concat([RV.hourly(g, mcol, MIN_REP) for _, g in mm_.groupby("rep")], axis=1)
            both = obs.notna() & mod.notna()
            D, P, _ = RV.ks_values(mod[both], obs[both])
            for h in range(24):
                rows.append(dict(setting=name, figure=fig, type=ty, hour=h, model=mod[h], model_sd=per.loc[h].std(ddof=1), n_rep=int(per.loc[h].notna().sum()),
                                 observed=obs[h], observed_all=obs_all[h], n_obs=int(n_obs[h]), D_hourly=D, P_hourly=P))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    C = pd.concat([curves(s) for s in SETS], ignore_index=True)
    if MERGE and os.path.exists(OUT): old = pd.read_parquet(OUT); C = pd.concat([old[~old.setting.isin(SETS)], C], ignore_index=True)
    C.to_parquet(OUT, index=False)
    K = C.drop_duplicates(["setting", "figure", "type"])[["setting", "figure", "type", "D_hourly", "P_hourly"]]
    print(K.to_string(index=False)); print(OUT)
