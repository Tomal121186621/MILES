#!/usr/bin/env python3
"""Diagnostic of the re-specified mode models with the TASHA car allocation (coefficient set activity/parameters, 2026-11-10):
model consistency versus population composition.

    python3 activity/checks/survey_mode_shares.py run       ABIT on the hold-out (validation-half) survey population, seeds 1-5, as the
                                                  unit-check run (survey_population.run, skims base_transit2024)
                                                  -> run_survey/svy_val_respecval_s0N
    python3 activity/checks/survey_mode_shares.py compare   -> respec_survey_modeshares.csv (tour and trip shares by segment: survey-population
                                                  runs mean / min / max over the seeds, RTS hold-out tours; the 1 % SILO 2024 smoke run
                                                  final_2024/run_respec_smoke/smk_respec_s01) and respec_population_compare.csv (cars per
                                                  household, licence share 16+, workers per household: SILO 2024 vs the RTS survey population)
Observed: work/tours_validation.parquet (3_abit/mode_choice/prep_tours.py: tour mode = choice2, trips = tripids with the RTS travel
mode), unweighted, the same persons as the model runs.  Model tours: output/mc_tours.csv (alt after the household stage); model
trips: legs, assigned to the home-based chain that contains the tour's main activity.  Modes: car driver, car passenger, walk,
bike, transit (bus + train)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
A3 = f"{WORKSPACE}/3_abit"   # data
sys.path.insert(0, f"{TERP_HOME}/activity/survey"); sys.path.insert(0, f"{TERP_HOME}/activity/lib/mode_choice")
SK = f"{A3}/skims/base_transit2024"; SEEDS = range(1, 6); SMOKE = f"{A3}/final_2024/run_respec_smoke/smk_respec_s01"
GRP = {"CD": "car driver", "CP": "car passenger", "WK": "walk", "BK": "bike", "BUS": "transit", "TRAIN": "transit",
       "CAR_DRIVER": "car driver", "CAR_PASSENGER": "car passenger", "WALK": "walk", "BIKE": "bike"}
SEG = {"WORK": "work", "EDUCATION": "school", "SHOPPING": "shopping"}


def run():
    import survey_population as S
    for s in SEEDS: S.run("validation", s, coef=f"{TERP_HOME}/activity/parameters", tag="respecval", skims=SK, force=True)


def model_shares(out, name):
    t = pd.read_csv(f"{out}/mc_tours.csv", usecols=["person_id", "segment", "start", "end", "alt"])
    cols = ["person_id", "previous_purpose", "start_time_min", "next_purpose", "mode"]
    if os.path.exists(f"{out}/legs_{name}.csv"): l = pd.read_csv(f"{out}/legs_{name}.csv", usecols=cols)
    else:
        l = pd.read_parquet(f"{out}/legs_full.parquet", columns=cols)
        for c in ("person_id", "start_time_min"): l[c] = pd.to_numeric(l[c])
    l = l.sort_values(["person_id", "start_time_min"], kind="stable")
    l["chain"] = (l.previous_purpose.eq("HOME")).groupby(l.person_id).cumsum()
    ch = l.groupby(["person_id", "chain"]).agg(t0=("start_time_min", "min"), t1=("start_time_min", "max")).reset_index()
    m = t.merge(ch, on="person_id"); m = m[(m.t0 <= m.start) & (m.start <= m.t1)]
    m = m.sort_values("t0").drop_duplicates(["person_id", "start"], keep="last")[["person_id", "chain", "segment"]]
    l = l.merge(m, on=["person_id", "chain"], how="inner")
    tours = t.assign(g=t.alt.map(GRP)).groupby("segment").g.value_counts(normalize=True)
    trips = l.assign(g=l["mode"].map(GRP)).groupby("segment").g.value_counts(normalize=True)
    return tours, trips, len(t), len(l)


def observed():
    import mc_common as M
    from rts_common import RTS, MODE_MAP
    t = pd.read_parquet(f"{M.WORK}/tours_validation.parquet")
    tours = t.assign(g=t.choice2.map(GRP)).groupby("segment").g.value_counts(normalize=True)
    tm = pd.read_csv(f"{RTS}/rts_trips_clean.csv", usecols=["tripid", "travel_mode"]).drop_duplicates("tripid").set_index("tripid").travel_mode
    e = t[["segment", "tripids"]].explode("tripids"); e["mode"] = e.tripids.map(tm).map(lambda v: MODE_MAP.get(int(v)) if np.isfinite(v) else None)
    trips = e.assign(g=e["mode"].map(GRP)).groupby("segment").g.value_counts(normalize=True)
    return tours, trips


def compare():
    rows = []
    reps = [model_shares(f"{A3}/run_survey/svy_val_respecval_s{s:02d}/output", f"svy_val_respecval_s{s:02d}") for s in SEEDS]
    ot, otr = observed(); sm = model_shares(f"{SMOKE}/output", "smk_respec_s01")
    for kind, k in (("tour", 0), ("trip", 1)):
        obs = ot if k == 0 else otr
        for seg in ["work", "shopping", "other", "school"]:
            for g in ["car driver", "car passenger", "walk", "bike", "transit"]:
                v = np.array([r[k].get((seg, g), 0.0) for r in reps]) * 100
                rows.append(dict(level=kind, segment=seg, mode=g, survey_pop_mean=v.mean(), survey_pop_min=v.min(), survey_pop_max=v.max(),
                                 rts_holdout=100 * obs.get((seg, g), 0.0), silo2024_smoke=100 * sm[k].get((seg, g), 0.0)))
    r = pd.DataFrame(rows); r["survey_pop_minus_rts"] = r.survey_pop_mean - r.rts_holdout; r["silo_minus_rts"] = r.silo2024_smoke - r.rts_holdout
    r.to_csv(f"{A3}/respec_survey_modeshares.csv", index=False)
    pd.set_option("display.width", 220); print(r.round(2).to_string(index=False))
    # population composition
    sys.path.insert(0, f"{TERP_HOME}/activity/lib"); import replications as F
    hh = pd.read_csv(f"{F.SCEN_DIR}/microData/futureYears/hh_2024.csv", usecols=["id", "autos"], engine="pyarrow")
    per = pd.read_parquet(f"{SMOKE}/output/persons.parquet"); hs = per.household_id.unique()
    pp = pd.read_csv(f"{F.SCH}/pp_2024.csv", usecols=["id", "hhid", "age", "driversLicense", "occupation"], engine="pyarrow")
    pp = pp[pp.hhid.isin(hs)]; hh = hh[hh.id.isin(hs)]
    O = f"{A3}/survey_pop/validation"; oh = pd.read_csv(f"{O}/hh.csv"); op = pd.read_csv(f"{O}/pp.csv")
    def comp(h, p, lab):
        lic = p.driversLicense.astype(str).str.lower().eq("true"); a16 = p.age >= 16; d = {"population": lab, "households": len(h)}
        for c, s in (h.autos.clip(upper=3).value_counts(normalize=True).sort_index() * 100).items(): d[f"households with {c}{'+' if c == 3 else ''} cars (%)"] = s
        d["cars per household"] = h.autos.mean(); d["licence share, persons 16+ (%)"] = 100 * lic[a16].mean()
        d["workers per household"] = (p.occupation == 1).sum() / len(h); d["persons per household"] = len(p) / len(h)
        dr = lic.groupby(p.hhid.values).sum(); hc = h.set_index("id").autos.reindex(dr.index)
        d["households with fewer cars than licensed drivers (%)"] = 100 * ((hc > 0) & (hc < dr)).mean()
        return d
    P = pd.DataFrame([comp(hh, pp, "SILO 2024 (1 % smoke households)"), comp(oh, op.rename(columns={"hhID": "hhid"}), "RTS survey population, hold-out half (unweighted)")]).set_index("population").T
    P.to_csv(f"{A3}/respec_population_compare.csv"); print(P.round(3).to_string())


if __name__ == "__main__":
    {"run": run, "compare": compare}[sys.argv[1]]()
