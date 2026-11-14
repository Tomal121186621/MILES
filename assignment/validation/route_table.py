#!/usr/bin/env python3
"""Count validation by road class and route (detailed table of the MATSim stage): mainline count stations grouped by facility tier
and MDOT route, counted against modelled daily volume, model/count of all vehicles (mean of the seeds and min-max over the seeds)
and of passenger vehicles.  Reads the outputs of validate_counts.py; nothing is fitted to the counts.

Tiers: 1 interstates (every route), 2 other freeways and expressways and 3 principal arterials (the TOP routes by counted volume,
the rest pooled as "Other"), 4-6 minor arterials, major collectors, minor collectors and local roads (pooled).  A route is grouped
under the facility class of its stations, so a route can appear in two tiers (e.g. I-895 stations coded as other freeway).
Usage: python3 assignment/validation/route_table.py [data_dir] [tex_out]   (defaults: WORKSPACE/4_matsim/validation/data/, WORKSPACE/5_reports/article/sections/supp/tab_net_routes.tex)
Writes data_dir/route_table.csv and the LaTeX table."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, numpy as np, pandas as pd
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"   # H: validation data and outputs (workspace)
DATA = sys.argv[1] if len(sys.argv) > 1 else f"{H}/data"
TEX = sys.argv[2] if len(sys.argv) > 2 else f"{V}/5_reports/article/sections/supp/tab_net_routes.tex"
TOP = 8

TIERS = [("Tier 1", "Interstate", ["Interstate: I-695", "Interstate: other"], "routes"),
         ("Tier 2", "Other freeway and expressway", ["Other freeway / expressway"], "top"),
         ("Tier 3", "Principal arterial", ["Principal arterial"], "top"),
         ("Tier 4", "Minor arterial", ["Minor arterial"], "pool"),
         ("Tier 5", "Major collector", ["Major collector"], "pool"),
         ("Tier 6", "Minor collector, local", ["Minor collector / local"], "pool")]
# names of the main routes (MDOT road names are abbreviated and vary along a route)
NAMES = {"I-695": "Baltimore Beltway", "I-95": "JFK Memorial Highway", "I-83": "Jones Falls Expressway",
         "I-97": "Baltimore to Annapolis", "I-895": "Harbor Tunnel Thruway", "I-795": "Northwest Expressway", "I-70": "Baltimore National Pike",
         "I-195": "Metropolitan Boulevard", "I-395": "Cal Ripken Way", "I-595": "John Hanson Highway", "MD 295": "Balt.-Wash. Parkway", "MD 24": "Vietnam Veterans Mem. Hwy",
         "MD 100": "Pitcher Memorial Hwy", "US 29": "Columbia Pike", "MD 43": "White Marsh Boulevard", "MD 10": "Arundel Expressway",
         "MD 702": "Southeast Boulevard", "MD 25": "Falls Road", "US 50": "John Hanson Highway", "MD 32": "Patuxent Freeway"}
ABBR = [(r"\bBALTO\b", "Baltimore"), (r"\bHWY\b", "Hwy"), (r"\bEXPWY\b", "Expressway"), (r"\bBLVD\b", "Blvd"), (r"\bPKWY\b", "Pkwy"),
        (r"\bAVE\b", "Ave"), (r"\bRD\b", "Rd"), (r"\bST\b", "St"), (r"\bJ F K\b", "John F. Kennedy"), (r"\bMEM\b", "Mem.")]


def clean(n):
    n = str(n).strip().upper()
    for a, b in ABBR: n = re.sub(a, b.upper(), n)
    return " ".join(w if w in ("I", "II") else w.capitalize() for w in n.split()).replace("Mem.", "Mem.")


def road_name(route, names, tier):
    if route in NAMES and tier in ("Tier 1", "Tier 2"): return NAMES[route]
    v = [x for x in names if isinstance(x, str) and x.strip() and "NO NAME" not in x.upper() and not x.upper().startswith("RAMP")]
    if not v: return ""
    return clean(pd.Series(v).value_counts().index[0])


def main():
    S = pd.read_csv(f"{DATA}/stations_model_vs_count.csv", low_memory=False)
    S = S[S["use"] == "mainline"].copy()
    PS = pd.read_csv(f"{DATA}/stations_by_seed.csv.gz"); PS = PS[PS.LOCATION_ID.isin(S.LOCATION_ID)]
    seeds = sorted(PS.seed.unique())
    byseed = PS.pivot_table(index="LOCATION_ID", columns="seed", values="m_all", aggfunc="first")
    S = S.set_index("LOCATION_ID")

    def row(tier, label, route, road, idx, kind):
        d = S.loc[idx]; c, cp = d.count_all.sum(), d.count_pass.sum(); m, mc = d.model_all_mean.sum(), d.model_car_mean.sum()
        rs = byseed.loc[byseed.index.intersection(idx)].sum() / c
        return dict(tier=tier, tier_label=label, route=route, road=road, kind=kind, stations=len(d), counted=c, modelled=m,
                    ratio_all=m / c, ratio_min=rs.min(), ratio_max=rs.max(), ratio_pass=mc / cp, n_routes=d.route.nunique())

    R = []
    for tier, label, cls, mode in TIERS:
        T = S[S.cls.isin(cls)]
        if T.empty: continue
        g = T.groupby("route").count_all.sum().sort_values(ascending=False)
        if mode == "pool":
            R.append(row(tier, label, f"{T.route.nunique()} routes", "", T.index, "pool")); continue
        listed = g.index if mode == "routes" else g.index[:TOP]
        for r in listed: R.append(row(tier, label, r, road_name(r, T[T.route == r].ROADNAME, tier), T.index[T.route == r], "route"))
        rest = g.index.difference(listed)
        if len(rest): R.append(row(tier, label, "Other", f"{len(rest)} routes", T.index[T.route.isin(rest)], "other"))
        R.append(row(tier, label, "Subtotal", "", T.index, "subtotal"))
    R.append(row("", "All classes", "", "", S.index, "total"))
    R = pd.DataFrame(R); R.to_csv(f"{DATA}/route_table.csv", index=False, float_format="%.4f")
    write_tex(R, len(seeds)); print(R[["tier", "route", "road", "stations", "counted", "modelled", "ratio_all", "ratio_min", "ratio_max", "ratio_pass"]].to_string())


def write_tex(R, ns):
    f = lambda x: f"{x:,.0f}"; r2 = lambda x: f"{x:.2f}"
    rng = (lambda r: f"{r.ratio_min:.2f}--{r.ratio_max:.2f}") if ns > 1 else (lambda r: "--")
    L = [r"\begin{table}[p]", r"  \centering",
         r"  \caption{Daily traffic against the 2024 counts by road class and route.}%% UPDATE AFTER FINAL MATSIM RUN",
         r"  \label{tab:s_net_routes}", r"  \scriptsize\setlength{\tabcolsep}{3pt}",
         r"\begin{tabular}{@{}l>{\raggedright\arraybackslash}p{3.4cm}rrrrrr@{}}", r"    \toprule",
         r"    & & & & & \multicolumn{3}{c}{Model / count} \\", r"    \cmidrule(l){6-8}",
         r"    Route & Road & Stations & \shortstack[r]{Counted\\(veh/day)} & \shortstack[r]{Modelled\\(veh/day)} & \shortstack[r]{All\\vehicles} & \shortstack[r]{Seed\\range} & \shortstack[r]{Passenger\\vehicles} \\",
         r"    \midrule"]
    last = None
    for _, r in R.iterrows():
        if r.kind == "total":
            L.append(r"    \midrule"); L.append(f"    \\textbf{{All classes}} & & \\textbf{{{r.stations:,}}} & \\textbf{{{f(r.counted)}}} & \\textbf{{{f(r.modelled)}}} & \\textbf{{{r2(r.ratio_all)}}} & {rng(r)} & \\textbf{{{r2(r.ratio_pass)}}} \\\\"); continue
        if r.kind == "pool":
            if r.tier == "Tier 4": L.append(r"    \addlinespace")
            L.append(f"    \\textit{{{r.tier}}} & {r.tier_label} ({r.route.split()[0]}) & {r.stations:,} & {f(r.counted)} & {f(r.modelled)} & {r2(r.ratio_all)} & {rng(r)} & {r2(r.ratio_pass)} \\\\"); last = r.tier; continue
        if r.tier != last:
            if last is not None: L.append(r"    \addlinespace")
            L.append(f"    \\multicolumn{{8}}{{@{{}}l}}{{\\textit{{{r.tier}: {r.tier_label}}}}} \\\\")
            last = r.tier
        if r.kind == "subtotal":
            L.append(f"    \\quad Subtotal & & {r.stations:,} & {f(r.counted)} & {f(r.modelled)} & {r2(r.ratio_all)} & {rng(r)} & {r2(r.ratio_pass)} \\\\"); continue
        if r.kind == "pool":
            L.append(f"    \\quad {r.route} & & {r.stations:,} & {f(r.counted)} & {f(r.modelled)} & {r2(r.ratio_all)} & {rng(r)} & {r2(r.ratio_pass)} \\\\"); continue
        road = str(r.road).replace("&", r"\&") if isinstance(r.road, str) else ""
        L.append(f"    \\quad {r.route} & {road} & {r.stations:,} & {f(r.counted)} & {f(r.modelled)} & {r2(r.ratio_all)} & {rng(r)} & {r2(r.ratio_pass)} \\\\")
    L += [r"    \bottomrule", r"  \end{tabular}", "",
          r"  \vspace{4pt}\noindent\parbox{\linewidth}{\scriptsize \textit{Note:} Mainline stations of the six Baltimore-region counties matched by road identity (Section~\ref{sec:s_net_match}); a route is listed under the facility class of its stations and can appear in two tiers; tiers 2 and 3 list the " + str(TOP) + r" routes with the largest counted volume; tiers 4--6: number of routes in parentheses. Counts: MDOT SHA 2024 AAWDT, both directions; passenger vehicles: count less the station's (or its class's) truck and bus share. Model: residents' cars ($\times$10, mean of the last five iterations) plus transit buses; cars only for passenger vehicles. Residents only, so ratios below 1 are expected. Model: " + (f"mean of {ns} assignment seeds" if ns > 1 else "one assignment seed") + r"; seed range: minimum to maximum over the assignment seeds.\\",
          r"  \textit{Source:} \citet{MDOTAADT}; model: \matsim{} assignment.}", r"\end{table}"]
    open(TEX, "w").write("\n".join(L) + "\n"); print("wrote", TEX)


if __name__ == "__main__":
    main()
