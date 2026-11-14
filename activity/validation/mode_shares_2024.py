#!/usr/bin/env python3
"""Trip and tour mode shares of the re-specified ABIT 2024 replications (run_respec/fin24_s01-10) against the RTS 2017/18:
Maryland residents 5+, weekday.  Trips: every leg (report_2024 Table F6 form; RTS rts_acts with person weights).  Tours: home-based
chains of the legs; main activity = work, else school, else the discretionary activity with the longest stay; tour mode by the
hierarchy of the survey tours (activity/lib/mode_choice/prep_tours.py: transit, car driver, car passenger, bike, walk); RTS: tours of both halves
(mode_choice/work/tours_*.parquet), Maryland residents 5+, person weights.
    python3 activity/validation/mode_shares_2024.py   -> run_respec/mode_shares_vs_rts.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, glob
import numpy as np, pandas as pd
A3 = f"{WORKSPACE}/3_abit"; HERE = f"{A3}/final_2024"   # data
sys.path.insert(0, f"{TERP_HOME}/activity")
import run_replications as R
SEG = {"WORK": "work", "EDUCATION": "school", "SHOPPING": "shopping"}; GRP = {"CAR_DRIVER": "car driver", "CAR_PASSENGER": "car passenger", "WALK": "walk", "BIKE": "bike", "BUS": "transit", "TRAIN": "transit"}
HIER = ["transit", "car driver", "car passenger", "bike", "walk"]


def tours(run, P):
    l = pd.read_parquet(f"{R.RUN}/{run}/output/legs_full.parquet", columns=["person_id", "previous_purpose", "start_time_min", "next_purpose", "end_time", "mode"])
    for c in ("person_id", "start_time_min", "end_time"): l[c] = pd.to_numeric(l[c])
    l = l[l.person_id.isin(P.index)].sort_values(["person_id", "start_time_min"], kind="stable")
    l["chain"] = l.previous_purpose.eq("HOME").groupby(l.person_id).cumsum(); l["g"] = l["mode"].map(GRP)
    l["stay"] = l.groupby("person_id").start_time_min.shift(-1) - l.end_time
    trips = l.g.value_counts(normalize=True)
    # vectorised: main activity per chain (work > school > the longest discretionary stay), tour mode by the hierarchy
    l["key"] = l.person_id.astype(np.int64) * 1000 + l.chain.astype(np.int64)
    d = l[l.next_purpose != "HOME"].copy(); d["rank"] = np.select([d.next_purpose.eq("WORK"), d.next_purpose.eq("EDUCATION")], [2e6, 1e6], 0) + d.stay.fillna(0).clip(lower=0)
    mains = d.sort_values("rank").drop_duplicates("key", keep="last").set_index("key").next_purpose.map(lambda p: SEG.get(p, "other"))
    hr = {h: k for k, h in enumerate(HIER)}; l["h"] = l.g.map(hr)
    tm = l.groupby("key").h.min().map(dict(enumerate(HIER)))
    c = pd.DataFrame({"seg": mains, "mode": tm.reindex(mains.index)}).dropna()
    return trips, c.groupby("seg")["mode"].value_counts(normalize=True), c["mode"].value_counts(normalize=True)


def main():
    P = pd.read_parquet(f"{R.WORK}/measures/persons.parquet").set_index("pid"); P = P[(P.age >= 5) & (P.county // 1000 == 24)]
    runs = sorted(os.path.basename(d) for d in glob.glob(f"{R.RUN}/fin24_s??"))
    res = [tours(r, P) for r in runs]
    # RTS
    sys.path.insert(0, f"{TERP_HOME}/activity/lib/reporting_2024"); T24 = f"{A3}/temporal_2024"
    rk = pd.read_parquet(f"{T24}/data/rts_persons.parquet"); ra = pd.read_parquet(f"{T24}/data/rts_acts.parquet")
    rp = rk[(rk.age >= 5) & (rk.county // 1000 == 24)]; w = dict(zip(rp.person_id, rp.w)); rs = ra[ra.pid.isin(rp.person_id)].assign(w=lambda x: x.pid.map(w))
    MM = {"Car, driver": "car driver", "Car, passenger": "car passenger", "Walk": "walk", "Bicycle": "bike", "Bus": "transit", "Rail": "transit", "Other": "other"}
    rtrip = rs.assign(g=rs["mode"].map(MM)).groupby("g").w.sum() / rs.w.sum()
    t = pd.concat([pd.read_parquet(f"{A3}/mode_choice/work/tours_{h}.parquet") for h in ("estimation", "validation")])
    t = t[(t.age >= 5) & (t.county // 1000 == 24)]; t["g"] = t.choice2.map({"CD": "car driver", "CP": "car passenger", "WK": "walk", "BK": "bike", "BUS": "transit", "TRAIN": "transit"})
    rtour = t.groupby(["segment", "g"]).w.sum() / t.groupby("segment").w.sum().reindex(t.groupby(["segment", "g"]).w.sum().index.get_level_values(0)).values; rall = t.groupby("g").w.sum() / t.w.sum()
    rows = []
    for g in ["car driver", "car passenger", "walk", "bike", "transit"]:
        v = np.array([r[0].get(g, 0) for r in res]) * 100
        rows.append(dict(level="trip", segment="all", mode=g, model_mean=v.mean(), model_sd=v.std(ddof=1), rts=100 * rtrip.get(g, 0)))
        v = np.array([r[2].get(g, 0) for r in res]) * 100
        rows.append(dict(level="tour", segment="all", mode=g, model_mean=v.mean(), model_sd=v.std(ddof=1), rts=100 * rall.get(g, 0)))
        for s in ["work", "school", "shopping", "other"]:
            v = np.array([r[1].get((s, g), 0) for r in res]) * 100
            rows.append(dict(level="tour", segment=s, mode=g, model_mean=v.mean(), model_sd=v.std(ddof=1), rts=100 * rtour.get((s, g), 0)))
    out = pd.DataFrame(rows); out["model_minus_rts"] = out.model_mean - out.rts; out.to_csv(f"{R.RUN}/mode_shares_vs_rts.csv", index=False)
    pd.set_option("display.width", 200); print(out.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
