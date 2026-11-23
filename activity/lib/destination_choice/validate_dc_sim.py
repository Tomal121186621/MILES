#!/usr/bin/env python3
"""Simulated validation of the destination choice: discretionary trips of DAYMAP runs against the survey, before (calibrated
gravity form) and after (estimated MNL), ten seeds each.

    python3 validate_dc.py sim

Settings (run directories as in activity/validation/validate_survey.py):
  validation   survey population of the VALIDATION half: before 3_abit/run_survey/svy_val_s01..10, after svy_val_mnl_s01..10
  chain        synthetic 2016 base population (5 % sample): before 3_abit/run/val_s01..10, after val_mnl_s01..10;
               observed = the validation half
Trips: model legs of the representative weekday (Monday) whose next activity is SHOPPING, RECREATION, ACCOMPANY or OTHER
(primary destinations and stops together, as the trip tables of the survey), persons 5+; survey trips of the half with a
discretionary destination activity, persons 5+, both ends in the zone system, weight wttrdfin (model: the weight of the survey
person, chain: 1).  Distance = car-distance skim between the zones (intrazonal 0.5 sqrt(area)) on both sides, so that the two
distributions use one measure.  Measures per purpose: mean, binned distribution (rts_common.DIST_BINS), weighted KS on the
trip distances (two-sample, Kish sizes), coincidence ratio, intrazonal share, destination area shares, own-county share, and
the county-to-county flow matrix (home county x destination county) with its dissimilarity index.
Output: results/sim_summary.csv (mean and s.d. over the seeds), results/sim_tld.csv, results/sim_flows.csv.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f"{MILES_HOME}/activity/lib"); sys.path.insert(0, f"{MILES_HOME}/activity/survey")
import dc_common as C
from rts_common import RTS, ACT_PURPOSE, DIST_BINS, DIST_LABELS, ks_stat, kish_n, coincidence_ratio, load_split
from activity_metrics import dist_matrix, zone_county
from survey_population import tract_zone, geoid, OUTD, RUNROOT
from validate_dc import area_of_county, AREAS

RES = f"{C.DCD}/results"
SETS = {"validation": ("survey", {"before": [f"{RUNROOT}/svy_val_s{s:02d}" for s in range(1, 11)], "after": [f"{RUNROOT}/svy_val_mnl_s{s:02d}" for s in range(1, 11)]}),
        "chain": ("synthetic", {"before": [f"{C.A3}/run/val_s{s:02d}" for s in range(1, 11)], "after": [f"{C.A3}/run/val_mnl_s{s:02d}" for s in range(1, 11)]})}


def survey_trips(half="validation"):
    pm = pd.read_csv(f"{OUTD}/{half}/persons_map.csv"); zc = zone_county()
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", low_memory=False, usecols=["tripid", "household_id", "person_id", "d_activity", "o_tract_fips", "d_tract_fips", "wttrdfin", "age"])
    t = t[t.household_id.isin(pm.household_id.unique()) & (t.age >= 5)].copy()
    t["purpose"] = t.d_activity.map(ACT_PURPOSE); t = t[t.purpose.isin(C.DISC)]
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", usecols=["tripid", "o_state_county_fips", "d_state_county_fips"], low_memory=False).drop_duplicates("tripid").set_index("tripid")
    tz = tract_zone().set_index("geoid").zone
    for e in ["o", "d"]: t[f"{e}_zone"] = geoid(t.tripid.map(r[f"{e}_state_county_fips"]), t[f"{e}_tract_fips"]).map(tz).fillna(-1).astype(int)
    t = t[(t.o_zone > 0) & (t.d_zone > 0)]
    hz = pm.drop_duplicates("household_id").set_index("household_id").home_zone
    t["home_zone"] = t.household_id.map(hz).astype(int)
    return pd.DataFrame({"purpose": t.purpose.values, "o": t.o_zone.values, "d": t.d_zone.values, "home": t.home_zone.values, "w": t.wttrdfin.values.astype(float)})


def model_trips(run, pop_w, pop_home):
    name = os.path.basename(run)
    legs = pd.read_csv(f"{run}/output/legs_{name}.csv", usecols=["person_id", "start_time_min", "start_zone", "next_purpose", "end_zone"], engine="pyarrow")
    legs = legs[(legs.start_time_min >= 0) & (legs.start_time_min < 1440) & legs.next_purpose.astype(str).isin(C.DISC)]
    legs = legs[legs.person_id.isin(pop_w.index)]
    return pd.DataFrame({"purpose": legs.next_purpose.astype(str).values, "o": legs.start_zone.values, "d": legs.end_zone.values,
                         "home": pop_home.reindex(legs.person_id.values).values, "w": pop_w.reindex(legs.person_id.values).values})


def measures(df, dm, zc):
    km = np.minimum(dm[df.o.values, df.d.values], 300.0); cd = zc.reindex(df.d.values).values; ch = zc.reindex(df.home.values).values
    out = {}
    for pur in C.DISC + ["ALL"]:
        m = np.ones(len(df), bool) if pur == "ALL" else (df.purpose.values == pur)
        w = df.w.values[m]; k = km[m]
        h, _ = np.histogram(k, bins=DIST_BINS, weights=w); h = h / h.sum()
        ar = area_of_county(cd[m])
        fl = pd.Series(w).groupby([ch[m], cd[m]]).sum(); fl = fl / fl.sum()
        out[pur] = dict(km=k, w=w, tld=h, mean=float(np.average(k, weights=w)), intra=float(w[df.o.values[m] == df.d.values[m]].sum() / w.sum()),
                        area={a: float(w[ar == i].sum() / w.sum()) for i, a in enumerate(AREAS)}, own=float(w[ch[m] == cd[m]].sum() / w.sum()), flows=fl)
    return out


def main(argv=()):
    dm = dist_matrix(); zc = zone_county()
    only = [a for a in argv if a in SETS]
    obs = measures(survey_trips(), dm, zc)
    S, T, Fl = [], [], []
    for setting, (kind, runs) in SETS.items():
        if only and setting not in only: continue
        if kind == "survey":
            pm = pd.read_csv(f"{OUTD}/validation/persons_map.csv"); pm = pm[pm.age >= 5]
            pw, ph = pm.set_index("id").w, pm.set_index("id").home_zone
        else:
            pp = pd.read_parquet(f"{C.A3}/run_survey/chain_population.parquet"); pp = pp[pp.age >= 5]
            pw, ph = pp.set_index("id").w, pp.set_index("id").home_zone
        for variant, rr in runs.items():
            rr = [r for r in rr if os.path.exists(f"{r}/output/legs_{os.path.basename(r)}.csv")]
            if not rr: print(f"{setting} {variant}: no runs"); continue
            per = [measures(model_trips(r, pw, ph), dm, zc) for r in rr]
            for pur in C.DISC + ["ALL"]:
                o = obs[pur]; vals = []
                for p in per:
                    x = p[pur]; idx = o["flows"].index.union(x["flows"].index)
                    di = 0.5 * float(np.abs(o["flows"].reindex(idx, fill_value=0) - x["flows"].reindex(idx, fill_value=0)).sum())
                    D = ks_stat(o["km"], o["w"], x["km"], x["w"])
                    vals.append(dict(mean_km=x["mean"], KS=D, CR=coincidence_ratio(x["tld"], o["tld"]), intrazonal=x["intra"], own_county=x["own"], flow_dissimilarity=di,
                                     **{f"share_{a}": x["area"][a] for a in AREAS}))
                v = pd.DataFrame(vals)
                row = dict(setting=setting, variant=variant, purpose=pur, seeds=len(rr), mean_km_obs=o["mean"], intrazonal_obs=o["intra"], own_county_obs=o["own"],
                           **{f"share_{a}_obs": o["area"][a] for a in AREAS}, n_obs=len(o["km"]), n_obs_kish=kish_n(o["w"]))
                for c in v.columns: row[c] = v[c].mean(); row[f"{c}_sd"] = v[c].std(ddof=1) if len(v) > 1 else np.nan
                ne = kish_n(o["w"]) * kish_n(per[0][pur]["w"]) / (kish_n(o["w"]) + kish_n(per[0][pur]["w"]))
                row["KS_crit_5pct"] = 1.36 / np.sqrt(ne)
                S.append(row)
                tm = np.mean([p[pur]["tld"] for p in per], 0)
                for k, lab in enumerate(DIST_LABELS):
                    T.append(dict(setting=setting, variant=variant, purpose=pur, bin=lab, model=tm[k], observed=o["tld"][k]))
                fm = pd.concat([p[pur]["flows"] for p in per], axis=1).fillna(0).mean(1)
                for (hc, dc_), v_ in fm.items(): Fl.append(dict(setting=setting, variant=variant, purpose=pur, home_county=hc, dest_county=dc_, model=v_, observed=float(o["flows"].get((hc, dc_), 0.0))))
            print(f"{setting} {variant}: {len(rr)} runs", flush=True)
    S = pd.DataFrame(S); S.to_csv(f"{RES}/sim_summary.csv", index=False); pd.DataFrame(T).to_csv(f"{RES}/sim_tld.csv", index=False); pd.DataFrame(Fl).to_csv(f"{RES}/sim_flows.csv", index=False)
    print(S[["setting", "variant", "purpose", "mean_km", "mean_km_obs", "KS", "CR", "intrazonal", "intrazonal_obs", "flow_dissimilarity", "share_Baltimore City", "share_Baltimore City_obs", "share_Washington DC", "share_Washington DC_obs"]].round(3).to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
