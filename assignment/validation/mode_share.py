#!/usr/bin/env python3
"""Mode share of the MATSim stage against the survey (2026-11-04): executed trips of residents of the six Baltimore-region counties,
by main mode, against the 2017/18 Regional Travel Survey (weighted, both halves, same residents), overall and by home county,
trip purpose (to or from work), household cars and trip distance; plus transit boardings per transit trip.
MATSim does not change modes (no mode-choice strategy; modes come from ABIT), so this tests the modes ABIT gives to the 2024
population as executed on the network.  Nothing is fitted.
Survey trips are linked across change-mode activities (activity 17), main mode transit > car driver > car passenger > bike > walk
(as in 3_abit/tasha_estimation); transit = bus + rail.  Boardings per linked survey transit trip counts only transfers recorded
as a change-mode stop, so it is a lower bound.
Usage: python3 assignment/validation/mode_share.py [runs_root] [out_dir]   -> out_dir/data/mode_share*.csv, out_dir/figures/fig_mode_share.pdf|png"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, glob, numpy as np, pandas as pd
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"; ROOT = f"{PROJECT_ROOT}"   # H: validation data and outputs (workspace)
sys.path.insert(0, f"{TERP_HOME}/reports"); import paperstyle as ps   # noqa: E402
RUNS = sys.argv[1] if len(sys.argv) > 1 else f"{V}/pipeline/runs/matsim"
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{H}/previews/mode_share"
os.makedirs(f"{OUT}/data", exist_ok=True); os.makedirs(f"{OUT}/figures", exist_ok=True)
CO = {24510: "Baltimore City", 24005: "Baltimore Co.", 24003: "Anne Arundel", 24027: "Howard", 24025: "Harford", 24013: "Carroll"}
MODES = ["Car driver", "Car passenger", "Transit", "Walk", "Bike"]
M_MAP = {"car": "Car driver", "ride": "Car passenger", "pt": "Transit", "walk": "Walk", "bike": "Bike"}
R_MAP = {1: "Walk", 2: "Bike", 3: "Car driver", 4: "Car driver", 5: "Car passenger", 6: "Car passenger", 7: "Transit", 8: "Transit",
         9: "Transit", 10: "Car passenger", 11: "Car passenger", 12: "Car passenger"}
RANK = {"Transit": 0, "Car driver": 1, "Car passenger": 2, "Bike": 3, "Walk": 4}
DBINS = [0, 2, 5, 10, 20, 1e9]; DLAB = ["0–2 km", "2–5 km", "5–10 km", "10–20 km", "20+ km"]
WORK_ACT = {2}   # RTS activity 2 = work (3 = volunteer; rts_common.ACT_PURPOSE)


def survey():
    RTS = f"{ABIT_HOME}/input/rts"
    h = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", usecols=["household_id", "home_state_county_fips"], low_memory=False).drop_duplicates("household_id")
    t = pd.read_csv(f"{RTS}/rts_trips_clean.csv", low_memory=False, usecols=["household_id", "person_id", "tripno", "o_activity", "d_activity",
                    "travel_mode", "distance", "wttrdfin", "numvehicle"]).merge(h, on="household_id")
    t = t[t.home_state_county_fips.isin(CO)].sort_values(["person_id", "tripno"]).copy()
    t["mode"] = t.travel_mode.map(R_MAP)
    # link: a new linked trip starts unless the previous trip of the person ended at a change-mode activity (17)
    prev17 = t.groupby("person_id").d_activity.shift().eq(17)
    t["link"] = (~prev17).cumsum()
    t["rank"] = t["mode"].map(RANK).fillna(9)
    g = t.groupby("link")
    L = pd.DataFrame({"county": g.home_state_county_fips.first(), "w": g.wttrdfin.first(), "cars": g.numvehicle.first(),
                      "o": g.o_activity.first(), "d": g.d_activity.last(), "km": g.distance.sum() * 1.609344,
                      "rank": g["rank"].min(), "boardings": g["mode"].apply(lambda m: (m == "Transit").sum())})
    L = L[L["rank"] < 9]; L["mode"] = L["rank"].map({v: k for k, v in RANK.items()})
    L["work"] = L.o.isin(WORK_ACT) | L.d.isin(WORK_ACT)
    return L[L.w > 0]


def matsim(run):
    P = pd.read_csv(f"{run}/output_persons.csv.gz", sep=";", usecols=["person", "homeCounty", "autos"])
    P = P[P.homeCounty.isin(CO)]
    T = pd.read_csv(f"{run}/output_trips.csv.gz", sep=";", usecols=["person", "main_mode", "modes", "traveled_distance", "start_activity_type", "end_activity_type"])
    T = T.merge(P, on="person")
    return pd.DataFrame({"county": T.homeCounty, "w": 1.0, "cars": T.autos, "km": T.traveled_distance / 1e3, "mode": T.main_mode.map(M_MAP),
                         "work": T.start_activity_type.eq("work") | T.end_activity_type.eq("work"),
                         "boardings": T.modes.str.count(r"(?:^|-)pt(?=-|$)")})


def shares(D):
    D = D.copy(); D["all"] = "All trips"; D["county_l"] = D.county.map(CO)
    D["purpose"] = np.where(D.work, "To or from work", "Other purposes")
    D["cars_l"] = pd.cut(D.cars.clip(lower=0), [-1, 0, 1, 2, 99], labels=["No car", "1 car", "2 cars", "3+ cars"]).astype(str)
    D["dist"] = pd.cut(D.km, DBINS, labels=DLAB, right=False).astype(str)
    rows = []
    for dim, col in [("All", "all"), ("Home county", "county_l"), ("Purpose", "purpose"), ("Household cars", "cars_l"), ("Distance", "dist")]:
        for seg, d in D[D[col] != "nan"].groupby(col):
            s = d.groupby("mode").w.sum().reindex(MODES, fill_value=0); tw = d.w.sum()
            rows.append(dict(dim=dim, segment=seg, trip_share=tw / D.w.sum() * 100, n=len(d), **{m: 100 * s[m] / tw for m in MODES}))
    return pd.DataFrame(rows)


def main():
    S = survey(); obs = shares(S)
    tr = S[S["mode"] == "Transit"]; obs_board = np.average(tr.boardings, weights=tr.w)
    runs = sorted((int(re.search(r"_s(\d+)$", d).group(1)), d) for d in glob.glob(f"{RUNS}/2024_s*") if re.search(r"_s\d+$", d) and os.path.exists(f"{d}/.done.json"))
    mods, boards = [], []
    for s, d in runs:
        M = matsim(d); x = shares(M); x["seed"] = s; mods.append(x)
        boards.append(M.loc[M["mode"] == "Transit", "boardings"].mean()); print(f"seed {s}: {len(M):,} trips of six-county residents (10 % sample)")
    A = pd.concat(mods); key = ["dim", "segment"]
    mean = A.groupby(key, sort=False)[MODES + ["trip_share"]].mean(); lo = A.groupby(key, sort=False)[MODES].min(); hi = A.groupby(key, sort=False)[MODES].max()
    O = obs.set_index(key)
    R = pd.concat({"model": mean, "model_min": lo, "model_max": hi, "observed": O[MODES + ["trip_share", "n"]]}, axis=1)
    R.columns = [f"{a}_{b}" for a, b in R.columns]
    for k in R.index:   # total variation distance of the mode distribution, pp
        R.loc[k, "tvd_pp"] = 0.5 * sum(abs(R.loc[k, f"model_{m}"] - R.loc[k, f"observed_{m}"]) for m in MODES)
    R.to_csv(f"{OUT}/data/mode_share.csv", float_format="%.3f")
    pd.DataFrame({"seed": [s for s, _ in runs], "boardings_per_transit_trip": boards}).assign(observed_lower_bound=obs_board).to_csv(f"{OUT}/data/mode_share_boardings.csv", index=False, float_format="%.3f")
    pd.set_option("display.width", 250)
    show = R[[f"{w}_{m}" for m in MODES for w in ("model", "observed")] + ["tvd_pp", "observed_n"]].round(1)
    show.columns = [c.replace("model_", "M ").replace("observed_", "O ").replace("Car driver", "CD").replace("Car passenger", "CP").replace("Transit", "TR").replace("Walk", "WK").replace("Bike", "BK") for c in show.columns]
    print(show.to_string()); print(f"boardings per transit trip: model {np.mean(boards):.2f} (seeds {', '.join(f'{b:.2f}' for b in boards)}); survey >= {obs_board:.2f}")
    figure(R, len(runs))


def figure(R, ns):
    import matplotlib.pyplot as plt   # noqa: F401
    dims = [("All", "All"), ("Home county", "Home county"), ("Purpose", "Purpose"), ("Household cars", "Household cars"), ("Distance", "Trip distance")]
    segs = [(d, s) for d, _ in dims for s in R.loc[d].index]
    order = {"Distance": DLAB, "Household cars": ["No car", "1 car", "2 cars", "3+ cars"], "Purpose": ["To or from work", "Other purposes"], "Home county": list(CO.values())}
    segs = [(d, s) for d, _ in dims for s in (order.get(d, list(R.loc[d].index))) if (d, s) in R.index]
    fig, axs = ps.figure(height=6.4, ncols=2, gridspec_kw=dict(width_ratios=[1.5, 1]))
    ax = axs[0]; y = np.arange(len(segs))[::-1].astype(float)
    # (a) stacked shares: observed (thin, upper) and model (lower) per segment
    for k, (row_y, who, hgt) in enumerate([(0.2, "observed", 0.34), (-0.2, "model", 0.34)]):
        left = np.zeros(len(segs))
        for i, m in enumerate(MODES):
            v = np.array([R.loc[(d, s), f"{who}_{m}"] for d, s in segs])
            ax.barh(y + row_y, v, left=left, height=hgt, color=ps.CAT[i], alpha=1.0 if who == "model" else 0.55, lw=0, label=m if who == "model" else None)
            left += v
    ax.set_yticks(y); ax.set_yticklabels([s for _, s in segs], fontsize=ps.TICK); ax.set_xlim(0, 100); ax.set_xlabel("Share of trips (%)\nupper bar: survey, lower bar: model")
    ax.tick_params(axis="y", length=0)
    # (b) transit share, model (seed range) vs observed
    ax = axs[1]
    o = np.array([R.loc[k, "observed_Transit"] for k in segs]); m = np.array([R.loc[k, "model_Transit"] for k in segs])
    lo = np.array([R.loc[k, "model_min_Transit"] for k in segs]); hi = np.array([R.loc[k, "model_max_Transit"] for k in segs])
    ax.scatter(o, y, s=14, color=ps.INK2, marker="|", lw=1.4, label="Survey 2017/18", zorder=3)
    ax.scatter(m, y, s=12, color=ps.CAT[2], label="Model 2024" + (f" (mean of {ns} runs)" if ns > 1 else ""), zorder=4)
    ax.hlines(y, lo, hi, color=ps.CAT[2], lw=2, alpha=0.4)
    ax.set_xscale("log"); ax.set_xlim(0.05, 70); ax.set_xticks([0.1, 0.3, 1, 3, 10, 30]); ax.set_xticklabels(["0.1", "0.3", "1", "3", "10", "30"]); ax.minorticks_off()
    ax.set_yticks(y); ax.set_yticklabels([]); ax.set_xlabel("Transit share of trips (%)"); ax.tick_params(axis="y", length=0)
    for a in axs:
        a.set_ylim(y.min() - 0.6, y.max() + 0.6)
        b = 0
        for d, _ in dims[:-1]:
            b += sum(1 for dd, _ in segs if dd == d); a.axhline(len(segs) - b - 0.5, color=ps.TOL_BAND, lw=0.8)
    h1, l1 = axs[0].get_legend_handles_labels(); h2, l2 = axs[1].get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="outside lower center", ncol=4, fontsize=ps.TICK)
    ps.finish(fig, f"{OUT}/figures/fig_mode_share", panel_labels="ab")


if __name__ == "__main__":
    main()
