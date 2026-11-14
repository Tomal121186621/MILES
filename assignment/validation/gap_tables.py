#!/usr/bin/env python3
"""Main-text tables on the count shortfall (2026-11-04): (1) miles driven by the residents against the traffic in each county,
(2) road-class mix of the executed car routes by straight-line distance and of the short trips against the shortest and free-flow
fastest paths, (3) like-for-like car-driver trip length (straight line between tract internal points) against the RTS, by purpose,
(4) passenger traffic at the permanent counters by period.  Reads the outputs of regional_validation.py (c1e_vmt_per_capita.csv),
validate_counts.py (counters_summary.csv), gap_routes.py and gap_triplength.py; writes sections/tab_net_gap_*.tex.
Usage: python3 assignment/validation/gap_tables.py [regional_data_dir] [counts_data_dir] [gap_dir] [article_sections_dir]"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pandas as pd
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"   # H: validation data and outputs (workspace)
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
REG = ARGS[0] if len(ARGS) > 0 else f"{H}/previews/legmode_s12/regional/data"
CNT = ARGS[1] if len(ARGS) > 1 else f"{H}/previews/legmode_s12/data"
GAP = ARGS[2] if len(ARGS) > 2 else f"{H}/previews/gap"
OUT = ARGS[3] if len(ARGS) > 3 else f"{V}/5_reports/article/sections"
UPD = " %% UPDATE AFTER FINAL MATSIM RUN"
CO = {"24510": "Baltimore City", "24005": "Baltimore County", "24003": "Anne Arundel", "24027": "Howard", "24025": "Harford", "24013": "Carroll", "region": "Six counties"}


def table(label, caption, colspec, head, body, note, source):
    return "\n".join([r"\begin{table}[!tbp]", r"  \centering", rf"  \caption{{{caption.split('%%')[0]}}}" + ("%%" + caption.split("%%", 1)[1] if "%%" in caption else ""), rf"  \label{{{label}}}",
                      r"  \footnotesize\setlength{\tabcolsep}{4pt}", r"  \begin{adjustbox}{max width=\linewidth}", rf"  \begin{{tabular}}{{{colspec}}}", r"    \toprule", *head, r"    \midrule",
                      *body, r"    \bottomrule", r"  \end{tabular}", r"  \end{adjustbox}", "",
                      rf"  \vspace{{4pt}}\noindent\parbox{{\linewidth}}{{\footnotesize \textit{{Note:}} {note}\\", rf"  \textit{{Source:}} {source}}}",
                      r"\end{table}", ""])


def residents():
    P = pd.read_csv(f"{REG}/c1e_vmt_per_capita.csv", index_col=0); P.index = P.index.astype(str)
    rows = []
    for k in ["24510", "24005", "24003", "24027", "24025", "24013", "region"]:
        r = P.loc[k]; g, gr, l, lo = r.generated_model_pc, r.generated_rts_pc, r.located_model_pc, r.located_obs_pc
        if k == "region": rows.append(r"    \addlinespace")
        rows.append(f"    {CO[k]} & {g:.1f} & {gr:.1f} & {g / gr:.2f} & {l:.1f} & {lo:.1f} & {l / lo:.2f} \\\\{UPD}")
    head = [r"    & \multicolumn{3}{c}{By the residents} & \multicolumn{3}{c}{On the roads} \\",
            r"    \cmidrule(lr){2-4}\cmidrule(lr){5-7}",
            r"    Home county & Model & RTS & Ratio & Model & Observed & Ratio \\"]
    note = (r"Weekday passenger-vehicle miles per resident, 2024 population. By the residents: car-driver distance of the executed trips "
            r"of the county's residents wherever driven; RTS 2017/18 car-driver distance of the county's residents, weighted. On the roads: "
            r"all modelled car traffic on the network of the county, against the MDOT SHA vehicle miles converted to weekday passenger vehicles with the "
            r"region's count stations. Model: mean of the assignment seeds.")
    return table("tab:net_gap_residents", "Miles driven by the residents and on the roads of each county, per resident, 2024 weekday.%% UPDATE AFTER FINAL MATSIM RUN (seeds)",
                 "@{}lrrrrrr@{}", head, rows, note, r"RTS 2017/18; \citet{MDOTMileage2024}; model: \abit{} and \matsim{} assignment.")


CLS = ["Freeway", "Ramp", "Primary", "Secondary", "Tertiary", "Local/residential"]


HEAD_CLS = r"Motorway & Ramp & Primary & Secondary & Tertiary & Local"
NOTE_CLS = (r"Road type of each link from its OpenStreetMap highway tag: motorway includes trunk roads; ramp: the slip roads of motorways and trunk roads; "
            r"primary, secondary and tertiary include their slip roads; local: residential, unclassified and service roads. ")


def routes():
    B = pd.read_csv(f"{GAP}/route_mix_by_band.csv").set_index("band")
    lab = {"0-1": "Under 1", "1-2": "1 to 2", "2-5": "2 to 5", "5-10": "5 to 10", "10-20": "10 to 20", "20+": "20 and more", "all": "All trips"}
    body = []
    for k in ["0-1", "1-2", "2-5", "5-10", "10-20", "20+", "all"]:
        r = B.loc[k]
        if k == "all": body.append(r"    \addlinespace")
        body.append(f"    {lab[k]} & {int(r['car trips (10%)']):,} & "
                    + " & ".join(f"{r[c + ' %']:.1f}" for c in CLS) + f" \\\\{UPD}")
    head = [r"    Trip length, & Simulated & \multicolumn{6}{c}{Share of the route length by road type (\%)} \\",
            r"    \cmidrule(lr){3-8}",
            r"    straight line (km) & car trips & " + HEAD_CLS + r" \\"]
    note = (r"Car-driver trips of the residents of the six counties in the simulated 2024 weekday (\matsim{} plans executed in the last iteration, "
            r"one assignment seed; trips of the 10\% sample). Straight line: the distance between the start and the end of the trip as the crow flies, used to "
            r"group the trips by length. Shares: the length driven on each road type as a share of the total length of the roads driven by the trips of the row. " + NOTE_CLS)
    return table("tab:net_gap_routes", "Road types driven by the simulated car trips, by trip length, 2024 weekday.%% UPDATE AFTER FINAL MATSIM RUN (seeds)",
                 "@{}lrrrrrrrr@{}", head, body, note, r"Model: \matsim{} assignment; network: OpenStreetMap \citep{OSM}.")


def routes_short():
    S = pd.read_csv(f"{GAP}/route_mix_short_paths.csv").set_index("path")
    body = []
    for k, t in [("executed (MATSim)", "Simulated route"), ("free-flow fastest", "Fastest route"), ("shortest distance", "Shortest route")]:
        r = S.loc[k]
        body.append(f"    {t} & {r.mean_km:.2f} & {r.km_ratio_to_executed:.2f} & " + " & ".join(f"{r[c + ' %']:.1f}" for c in CLS) + f" \\\\{UPD}")
    n = int(S.loc["executed (MATSim)", "trips"]); st = S.loc["executed (MATSim)", "mean_straight_km"]
    head = [r"    & Mean & Relative & \multicolumn{6}{c}{Share of the route length by road type (\%)} \\", r"    \cmidrule(lr){4-9}",
            r"    Route & length (km) & length & " + HEAD_CLS + r" \\"]
    note = (rf"{n:,} car-driver trips drawn at random from the simulated trips of Table~\ref{{tab:net_gap_routes}} whose start and end lie 0.2 to 5\,km apart "
            rf"as the crow flies (mean {st:.2f}\,km). For each trip, three routes between the same start and end on the same road network: the simulated route, i.e. the route the "
            r"car drove in the simulation, the route of least travel time at the speed limit of every road (no congestion), and the route of least distance. Relative length: mean length $\div$ mean length of the simulated route. " + NOTE_CLS)
    return table("tab:net_gap_short", "Routes of short car trips: the simulated route against the fastest and the shortest route, 2024 weekday.%% UPDATE AFTER FINAL MATSIM RUN (seeds)",
                 "@{}lrrrrrrrr@{}", head, body, note, r"Model: \matsim{} assignment; network: OpenStreetMap \citep{OSM}.")


def triplength():
    T = pd.read_csv(f"{GAP}/tract_l4l.csv", header=0, index_col=[0, 1])
    bands = ["0-1", "1-2", "2-5", "5-10", "10-20", "20+"]
    lab = {"all": "All car-driver trips", "work": "To or from work", "school": "To or from school", "shopping": "To or from shopping", "other": "Other"}
    body = []
    for g in ["all", "work", "school", "shopping", "other"]:
        if g != "all": body.append(r"    \addlinespace")
        for w, t in [("survey", "RTS 2017/18"), ("current", "Model 2024")]:
            r = T.loc[(g, w)]
            first = lab[g] if w == "survey" else ""
            tvd = "--" if w == "survey" else f"{r.TVD:.1f}"
            body.append(f"    {first} & {t} & " + " & ".join(f"{r[b]:.1f}" for b in bands) + f" & {r['mean km']:.1f} & {r['same tract %']:.1f} & {tvd} \\\\")
    head = [r"    & & \multicolumn{6}{c}{Share of trips by distance (km), \%} & Mean & Same & TVD \\", r"    \cmidrule(lr){3-8}",
            r"    Trips & Source & 0--1 & 1--2 & 2--5 & 5--10 & 10--20 & 20+ & (km) & tract (\%) & (pp) \\"]
    note = (r"Car-driver trips of the residents of the six counties. Both trip ends of model and survey trips are placed at the internal point of their "
            r"2010 census tract and the distance is the straight line between the two points, so that model and survey are measured alike. "
            r"Model: activity locations of the 2024 \matsim{} population; survey: weighted. Purpose: either trip end; school: school activity only.")
    return table("tab:net_gap_length", "Car-driver trip length between census tracts, model against the travel survey, weekday.",
                 "@{}llrrrrrrrrr@{}", head, body, note, r"RTS 2017/18; model: \abit{} 2024 and its \matsim{} population.")


def counters():
    C = pd.read_csv(f"{CNT}/counters_summary.csv")
    per = ["Morning peak (6-10 h)", "Midday (10-15 h)", "Evening peak (15-19 h)", "Evening (19-24 h)", "Night (0-6 h)", "Whole day"]
    plab = {"Night (0-6 h)": "Night, 0:00--6:00", "Morning peak (6-10 h)": "Morning peak, 6:00--10:00", "Midday (10-15 h)": "Midday, 10:00--15:00",
            "Evening peak (15-19 h)": "Evening peak, 15:00--19:00", "Evening (19-24 h)": "Evening, 19:00--24:00", "Whole day": "Whole day"}
    G = ["Baltimore Beltway (I-695)", "Other freeways", "All counters"]
    X = C.set_index(["group", "period"])
    body = []
    for p in per:
        if p == "Whole day": body.append(r"    \addlinespace")
        body.append(f"    {plab[p]} & " + " & ".join(f"{X.loc[(g, p), 'ratio_mean']:.2f}" for g in G) + " & " +
                    " & ".join(f"{100 * X.loc[(g, p), 'geh5_mean']:.0f}" for g in G) + f" \\\\{UPD}")
    n = {g: int(X.loc[(g, 'Whole day'), 'stations']) for g in G}
    head = [r"    & \multicolumn{3}{c}{Model $\div$ count} & \multicolumn{3}{c}{GEH $<$ 5 (\%)} \\", r"    \cmidrule(lr){2-4}\cmidrule(lr){5-7}",
            r"    Period & I-695 & Other & All & I-695 & Other & All \\"]
    note = (rf"Counters on I-695 ({n[G[0]]} stations), on other freeways ({n[G[1]]}) and all ({n[G[2]]}). Passenger vehicles, both directions; ratio of the summed hourly volumes of the period; GEH $<$ 5: share of counter-hours of the period. Counts: FHWA continuous counters, 2023 scaled to 2024. "
            r"Model: residents' traffic, mean of the assignment seeds.")
    return table("tab:net_gap_counters", "Passenger traffic at the permanent counters by period, 2024 weekday.%% UPDATE AFTER FINAL MATSIM RUN (seeds)",
                 "@{}lrrrrrr@{}", head, body, note, r"FHWA continuous count stations; model: \matsim{} assignment.")


for name, f in [("residents", residents), ("routes", routes)]:
    if "--figure" in sys.argv: break
    open(f"{OUT}/tab_net_gap_{name}.tex", "w").write(f()); print(f"wrote {OUT}/tab_net_gap_{name}.tex")


def length_figure(path=None):
    """Figure replacing the trip-length table (2026-11-04): share of car-driver trips by straight-line distance between tracts,
    survey against model, all trips and four purposes, and the mean length by purpose."""
    import numpy as np
    sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps
    path = path or f"{V}/5_reports/article/figures/fig_net_gap_length"
    T = pd.read_csv(f"{GAP}/tract_l4l.csv", header=0, index_col=[0, 1])
    bands = ["0-1", "1-2", "2-5", "5-10", "10-20", "20+"]; blab = ["0–1", "1–2", "2–5", "5–10", "10–20", "20+"]
    grp = [("all", "All car-driver trips"), ("work", "To or from work"), ("school", "To or from school"), ("shopping", "To or from shopping"), ("other", "Other purposes")]
    fig, axs = ps.figure(height=5.2, nrows=2, ncols=3); axs = axs.ravel(); x = np.arange(len(bands)); w = 0.38
    for ax, (g, name) in zip(axs, grp):
        o = T.loc[(g, "survey"), bands].values.astype(float); m = T.loc[(g, "current"), bands].values.astype(float)
        ax.bar(x - w / 2, o, w, color=ps.OBSERVED, label="Survey 2017/18")
        ax.bar(x + w / 2, m, w, color=ps.MODEL, label="Model 2024")
        ax.set_xticks(x); ax.set_xticklabels(blab, rotation=45, ha="right", rotation_mode="anchor"); ax.set_ylim(0, 50); ax.grid(axis="x", visible=False)
        ax.set_title(name, loc="right", fontsize=ps.FONT, fontweight="normal", color=ps.INK)
        ax.text(0.03, 0.97, f"TVD {T.loc[(g, 'current'), 'TVD']:.1f} pp\nMean: model {T.loc[(g, 'current'), 'mean km']:.1f} km,\nsurvey {T.loc[(g, 'survey'), 'mean km']:.1f} km",
                transform=ax.transAxes, ha="left", va="top", fontsize=ps.TICK, color=ps.INK2)
    for ax in axs[[0, 3]]: ax.set_ylabel("Share of trips (%)")
    for ax in axs[3:5]: ax.set_xlabel("Distance (km)")
    ax = axs[5]; y = np.arange(len(grp))[::-1]
    o = [T.loc[(g, "survey"), "mean km"] for g, _ in grp]; m = [T.loc[(g, "current"), "mean km"] for g, _ in grp]
    ax.hlines(y, np.minimum(o, m), np.maximum(o, m), color=ps.GRID, lw=2, zorder=1)
    ax.scatter(o, y, color=ps.OBSERVED, s=22, zorder=3); ax.scatter(m, y, color=ps.MODEL, s=22, zorder=3)
    ax.set_yticks(y); ax.set_yticklabels(["All", "Work", "School", "Shopping", "Other"]); ax.set_xlim(0, 20); ax.set_xlabel("Mean distance (km)")
    ax.set_title("Mean trip length", loc="right", fontsize=ps.FONT, fontweight="normal", color=ps.INK); ax.grid(axis="y", visible=False)
    h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, loc="outside lower center", ncol=2)
    return ps.finish(fig, path, panel_labels="abcdef")


if "--figure" in sys.argv:
    length_figure()
