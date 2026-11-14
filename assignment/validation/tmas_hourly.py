#!/usr/bin/env python3
"""Hourly validation against the FHWA TMAS 2024 continuous counts (2026-11-04), replacing the 11-counter check of validate_counts.py.

Observed: the twelve monthly Maryland TMAS 2024 volume files (data/raw/tmas_2024/md_vol/MD_*_2024 (TMAS).VOL, extracted from the FHWA
monthly continuous-count files https://www.fhwa.dot.gov/policyinformation/tables/tmasdata/2024/), every continuous
station of the six counties that is matched to the network in the audited MDOT station file (TMAS station 0Pnnnn = MDOT station Pnnnn,
data/count_stations_matched.csv, links by direction: north- and eastbound = link_NE, south- and westbound = link_SW).  Per station,
direction and weekday (Monday-Friday, federal holidays excluded): sum over lanes for each hour; a day is kept when every lane of the
direction reported all 24 hours and the daily total is at least half the direction's median day.  Average weekday = mean of the kept days.
Same year as the model (2024, Key Bridge closed from 26 March): no year scaling.  Passenger vehicles: x (1 - truck share - bus share) of the station (MDOT
classification counts, else its class; validate_counts.stations()).
Model: residents' cars by link and hour, it.100 linkstats x 10 minus transit vehicles (validate_counts.model_seed), every finished seed.
Fit: model / count of the summed volumes by period and road group; GEH of each station-direction-hour (UK TAG: GEH < 5 for 85 %).
Usage: python3 assignment/validation/tmas_hourly.py [out_dir]  -> out_dir/data/tmas_*.csv, figures/fig_net_tmas_hourly; article table and figure."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, glob, re, numpy as np, pandas as pd
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"; ROOT = f"{PROJECT_ROOT}"   # H: validation data and outputs (workspace)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, f"{MILES_HOME}/reports")
import validate_counts as vc   # noqa: E402  (model_seed, stations, PERIODS, geh)
import paperstyle as ps        # noqa: E402
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{H}/previews/tmas"
ART = f"{V}/5_reports/article"
os.makedirs(f"{OUT}/data", exist_ok=True); os.makedirs(f"{OUT}/figures", exist_ok=True)
VOL = f"{V}/data/raw/tmas_2024/md_vol"
STA = f"{V}/data/raw/tmas_2024/MD_2024 (TMAS).STA"
SIX = {"003", "005", "013", "025", "027", "510"}
HOL = {(1, 1), (1, 15), (2, 19), (5, 27), (6, 19), (7, 4), (9, 2), (10, 14), (11, 11), (11, 28), (11, 29), (12, 25)}   # 2024 federal holidays (+ day after Thanksgiving)
DIRN = {1: "Northbound", 3: "Eastbound", 5: "Southbound", 7: "Westbound"}
HR = [f"hour_{h:02d}" for h in range(24)]
UPD = " %% UPDATE AFTER FINAL MATSIM RUN"


def observed():
    S = pd.read_csv(STA, sep="|", dtype=str); S["county_code"] = S.county_code.str.strip()
    sta = S[S.county_code.isin(SIX)].drop_duplicates("station_id").set_index("station_id")
    rows = []
    for f in sorted(glob.glob(f"{VOL}/MD_*_2024 (TMAS).VOL")):
        d = pd.read_csv(f, sep="|", dtype={"station_id": str}, usecols=["station_id", "travel_dir", "travel_lane", "month_record", "day_record", "day_of_week"] + HR)
        rows.append(d[d.station_id.isin(sta.index) & d.day_of_week.between(2, 6)])
    D = pd.concat(rows)
    D = D[~np.array([(m, dd) in HOL for m, dd in zip(D.month_record, D.day_record)])]
    D = D[(D[HR] >= 0).all(axis=1)]
    key = ["station_id", "travel_dir", "month_record", "day_record"]
    G = D.groupby(key).agg(lanes=("travel_lane", "nunique"), **{h: (h, "sum") for h in HR}).reset_index()
    full = G.groupby(["station_id", "travel_dir"]).lanes.transform("max"); G = G[G.lanes == full]
    G["tot"] = G[HR].sum(axis=1); med = G.groupby(["station_id", "travel_dir"]).tot.transform("median"); G = G[G.tot >= 0.5 * med]
    A = G.groupby(["station_id", "travel_dir"]).agg(n_days=("tot", "size"), **{h: (h, "mean") for h in HR}).reset_index()
    A = A.merge(sta[["station_location", "f_system"]], left_on="station_id", right_index=True)
    return A


def main():
    O = observed()
    St = vc.stations().set_index("LOCATION_ID")
    rows = []
    for r in O.itertuples():
        mid = "P" + r.station_id[2:]
        if mid not in St.index: continue
        m = St.loc[mid]; link = m.link_NE if r.travel_dir in (1, 3) else m.link_SW
        if not isinstance(link, str) or not link: continue
        sc = 1.0   # TMAS 2024 against the 2024 model
        pas = 1 - m.trk_sh - m.bus_sh
        for h in range(24):
            v = getattr(r, f"hour_{h:02d}")
            rows.append(dict(station=r.station_id, mdot=mid, dir=DIRN.get(r.travel_dir, str(r.travel_dir)), link=link, road=m.route.strip(), cls=m.cls, n_days=r.n_days,
                             hour=h, obs_all=v, scale=sc, pass_share=pas, obs_pass=v * sc * pas))
    C = pd.DataFrame(rows)
    seeds = sorted(int(re.search(r"_s(\d+)$", d).group(1)) for d in glob.glob(f"{vc.RUN_ROOT}/2024_s*") if re.search(r"_s\d+$", d)
                   and os.path.exists(f"{d}/.done.json") and os.path.exists(f"{vc.LH}/link_hours_s{re.search(r'_s(\d+)$', d).group(1)}.csv.gz"))
    for s in seeds:
        car, _ = vc.model_seed(s); C[f"model_s{s}"] = [car.loc[l, h] if l in car.index else 0.0 for l, h in zip(C.link, C.hour)]
    mc = [f"model_s{s}" for s in seeds]; C["model"] = C[mc].mean(axis=1); C["model_min"] = C[mc].min(axis=1); C["model_max"] = C[mc].max(axis=1)
    C["geh"] = vc.geh(C.model, C.obs_pass)
    C["grp"] = np.where(C.cls.str.startswith("Interstate") | C.cls.eq("Other freeway / expressway"), "Freeways", "Arterials and collectors")
    C.to_csv(f"{OUT}/data/tmas_hourly.csv", index=False, float_format="%.4g")
    # summary by period and road group
    T = []
    for gname, d0 in [("Freeways", C[C.grp == "Freeways"]), ("Arterials and collectors", C[C.grp != "Freeways"]), ("All stations", C)]:
        for p, hrs in vc.PERIODS:
            d = d0[d0.hour.isin(list(hrs))]
            T.append(dict(group=gname, period=p, stations=d.station.nunique(), directions=d.groupby(["station", "dir"]).ngroups,
                          ratio=d.model.sum() / d.obs_pass.sum(), ratio_min=d.model_min.sum() / d.obs_pass.sum(), ratio_max=d.model_max.sum() / d.obs_pass.sum(),
                          geh5=(d.geh < 5).mean()))
    T = pd.DataFrame(T); T.to_csv(f"{OUT}/data/tmas_summary.csv", index=False, float_format="%.4f")
    print(f"seeds {seeds}; {C.station.nunique()} stations, {C.groupby(['station', 'dir']).ngroups} directions")
    print(T.round(3).to_string())
    table(T, C, seeds); figure(C, seeds)


def table(T, C, seeds):
    per = ["Morning peak (6-10 h)", "Midday (10-15 h)", "Evening peak (15-19 h)", "Evening (19-24 h)", "Night (0-6 h)", "Whole day"]
    plab = {"Night (0-6 h)": "Night, 0:00--6:00", "Morning peak (6-10 h)": "Morning peak, 6:00--10:00", "Midday (10-15 h)": "Midday, 10:00--15:00",
            "Evening peak (15-19 h)": "Evening peak, 15:00--19:00", "Evening (19-24 h)": "Evening, 19:00--24:00", "Whole day": "Whole day"}
    G = ["Freeways", "Arterials and collectors", "All stations"]; X = T.set_index(["group", "period"])
    body = []
    for p in per:
        if p == "Whole day": body.append(r"    \addlinespace")
        body.append(f"    {plab[p]} & " + " & ".join(f"{X.loc[(g, p), 'ratio']:.2f}" for g in G) + " & " + " & ".join(f"{100 * X.loc[(g, p), 'geh5']:.0f}" for g in G) + f" \\\\{UPD}")
    n = {g: (int(X.loc[(g, 'Whole day'), 'stations']), int(X.loc[(g, 'Whole day'), 'directions'])) for g in G}
    nd = C.drop_duplicates(["station", "dir"]).n_days
    tex = "\n".join([r"\begin{table}[!tbp]", r"  \centering", r"  \caption{Hourly passenger traffic at the TMAS continuous count stations by period, 2024 weekday.}" + UPD + " (seeds)",
                     r"  \label{tab:net_tmas}", r"  \footnotesize\setlength{\tabcolsep}{4pt}", r"  \begin{tabular}{@{}lrrrrrr@{}}", r"    \toprule",
                     r"    & \multicolumn{3}{c}{Model $\div$ count} & \multicolumn{3}{c}{GEH $<$ 5 (\%)} \\", r"    \cmidrule(lr){2-4}\cmidrule(lr){5-7}",
                     r"    Period & Freeways & Other & All & Freeways & Other & All \\", r"    \midrule", *body, r"    \bottomrule", r"  \end{tabular}", "",
                     rf"  \vspace{{4pt}}\noindent\parbox{{\linewidth}}{{\footnotesize \textit{{Note:}} The {n['All stations'][0]} of the 25 FHWA TMAS continuous count stations of the six counties with complete 2024 weekdays "
                     rf"({n['All stations'][1]} station directions): freeways {n['Freeways'][0]} stations ({n['Freeways'][1]} directions), other roads (arterials and collectors) "
                     rf"{n['Arterials and collectors'][0]} ({n['Arterials and collectors'][1]}). Observed: average weekday of 2024 by station, direction and hour, Monday to Friday "
                     rf"without federal holidays, days with every lane reporting all 24 hours ({nd.min()}--{nd.max()} days per direction), converted to passenger vehicles with the station's truck and bus shares. Model: residents' cars on the link of the "
                     rf"station's direction, mean of {len(seeds)} assignment seeds. Ratio: model $\div$ count of the volumes summed over the stations and hours of the period. "
                     r"GEH $<$ 5: share of the station-direction-hours of the period (guideline: 85\%).\\",
                     r"  \textit{Source:} FHWA Travel Monitoring Analysis System (TMAS) 2024; \citet{MDOTAADT}; model: \matsim{} assignment.}", r"\end{table}", ""])
    open(f"{ART}/sections/tab_net_tmas.tex", "w").write(tex); print("wrote tab_net_tmas.tex")


def figure(C, seeds):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    out_col = ps.CAT[1]
    order = C.drop_duplicates("station").assign(o=lambda d: d.grp.ne("Freeways").astype(int)).sort_values(["o", "road", "station"]).station.tolist()
    n = len(order); nc = 5; nr = int(np.ceil(n / nc))
    fig, axs = ps.figure(ps.MAX_HEIGHT, nrows=nr, ncols=nc, sharex=True); axs = np.atleast_1d(axs).ravel()
    for ax, s in zip(axs, order):
        d = C[C.station == s]; ymax = 0
        for (dr, g), ls in zip(d.groupby("dir"), ["-", (0, (3, 1.5))]):
            g = g.sort_values("hour")
            ax.fill_between(g.hour, g.model_min / 1e3, g.model_max / 1e3, color=ps.SEED_BAND, lw=0)
            ax.plot(g.hour, g.obs_pass / 1e3, color=ps.OBSERVED, lw=0.9, ls=ls); ax.plot(g.hour, g.model / 1e3, color=ps.MODEL, lw=0.9, ls=ls)
            b = g[g.geh >= 5]; ax.scatter(b.hour, b.model / 1e3, s=3, color=out_col, zorder=3, lw=0); ymax = max(ymax, g.obs_pass.max(), g.model_max.max())
        dirs = "/".join(x[0] for x in sorted(d.dir.unique()))
        ax.set_title(f"{d.road.iloc[0]}, {s[2:].lstrip('0')} ({dirs})", fontsize=ps.TICK, fontweight="normal", loc="left")
        ax.set_xticks([0, 6, 12, 18, 24]); ax.set_xlim(0, 23); ax.set_ylim(0, ymax / 1e3 * 1.08)
    for ax in axs[n:]: ax.set_visible(False)
    for i, ax in enumerate(axs[:n]):
        if i + nc >= n: ax.tick_params(labelbottom=True)   # last panel of its column shows the hours
    fig.supxlabel("Hour of the day", fontsize=ps.FONT); fig.supylabel("Passenger vehicles per hour (thousand)", fontsize=ps.FONT)
    fig.legend(handles=[Line2D([], [], color=ps.OBSERVED, label="Count (TMAS)"), Line2D([], [], color=ps.MODEL, label=ps.LEG["model"]),
                        Line2D([], [], color=ps.INK2, label="N or E bound"), Line2D([], [], color=ps.INK2, ls=(0, (3, 1.5)), label="S or W bound"),
                        Patch(color=ps.SEED_BAND, label="Range of the runs"), Line2D([], [], marker="o", ls="", color=out_col, ms=3, label="GEH ≥ 5")],
               ncol=6, loc="outside upper center", fontsize=ps.TICK)
    ps.finish(fig, f"{OUT}/figures/fig_net_tmas_hourly")
    import shutil
    for e in ("pdf", "png"): shutil.copy(f"{OUT}/figures/fig_net_tmas_hourly.{e}", f"{ART}/figures/fig_net_tmas_hourly.{e}")


if __name__ == "__main__":
    main()
