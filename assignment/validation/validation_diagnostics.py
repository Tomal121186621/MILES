#!/usr/bin/env python3
"""Diagnostics of the count validation of the assignment (2026-11-12): descriptive checks on top of validate_counts.py.
Nothing here changes the model, the counts or the station match; counts are validation data only.

Reads the outputs of validate_counts.py (station table with the seed-mean model volumes, link volumes, hourly counters), tmas_hourly.py,
regional_validation.py and the run folders (link statistics, score and mode statistics), the station match table and the station review.
Writes to <OUT>/data and <OUT>/figures:
  a. matching_audit.csv, matching_reasons.csv, stations_doubtful.csv, stations_zero_volume.csv, stations_shared_link.csv
       station matching audit: doubtful matches (results with and without them), stations whose matched link carries (almost) no model
       traffic, two-way stations whose both directions sit on the same link, several stations on one link
  b. spatial_groups.csv (county, ring distance from downtown Baltimore), morans_i.csv (log passenger ratio, k nearest neighbours),
       fig_ratio_by_ring_county
  c. count_quality.csv: counted in 2024 against estimated, count age, weekday against annual basis, lanes, capacity class of the link
  d. volume_groups_fdot.csv: FDOT groups with the share of stations and of the counted volume; stations above 10,000 and 25,000
  f. counters_direction_detail.csv, counters_period_direction.csv, fig_counters_geh_heatmap: hourly profiles by counter and direction
  g. transit_by_agency.csv: boardings by operator (the comparison by mode is in regional_validation.py)
  h. convergence_summary.csv, linkstats_iteration_range.csv: score, mode-share and travel-time plateau; spread of the link volumes over
       the last five iterations; five-seed spread of the station volumes
  links_map.parquet: car links with geometry (EPSG:26985) and the seed-mean daily volumes, for validation_map.py
  diagnostics.json: headline numbers
Usage: python3 assignment/validation/validation_diagnostics.py   (env COUNTS_DATA, TMAS_DATA, REGIONAL_DATA, RUN_ROOT, OUT)"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, json, gzip, glob, warnings, numpy as np, pandas as pd; warnings.filterwarnings("ignore")
V = f"{WORKSPACE}"; H = f"{V}/4_matsim/validation"; ROOT = f"{PROJECT_ROOT}"   # H: validation data and outputs (workspace)
sys.path.insert(0, f"{ORIOLE_HOME}/reports"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paperstyle as ps
WORK = f"{V}/5_reports/validation_pdfs/work/matsim_respec"
CD = os.environ.get("COUNTS_DATA", f"{WORK}/counts/data"); TD = os.environ.get("TMAS_DATA", f"{WORK}/tmas/data"); RD = os.environ.get("REGIONAL_DATA", f"{WORK}/regional/data")
RUN_ROOT = os.environ.get("RUN_ROOT", f"{V}/pipeline/runs_respec/matsim"); IT = int(os.environ.get("IT", "100"))
OUT = os.environ.get("OUT", H); DATA = f"{OUT}/data"; FIG = f"{OUT}/figures"; os.makedirs(DATA, exist_ok=True); os.makedirs(FIG, exist_ok=True)
CRS = 26985; EXP = 10
CLASSES = ["Interstate: I-695", "Interstate: other", "Other freeway / expressway", "Principal arterial", "Minor arterial", "Major collector", "Minor collector / local"]
SHORT = {"Interstate: I-695": "I-695", "Interstate: other": "Other interstate", "Other freeway / expressway": "Other freeway", "Principal arterial": "Principal arterial",
         "Minor arterial": "Minor arterial", "Major collector": "Major collector", "Minor collector / local": "Minor collector, local"}
VGROUPS = [(0, 5e3, 100, 45), (5e3, 1e4, 45, 35), (1e4, 1.5e4, 35, 27), (1.5e4, 2e4, 30, 25), (2e4, 3e4, 27, 15), (3e4, 5e4, 25, 15), (5e4, 6e4, 20, 10), (6e4, 1e12, 19, 10)]
PERIODS = [("Night (0-6 h)", range(0, 6)), ("Morning peak (6-10 h)", range(6, 10)), ("Midday (10-15 h)", range(10, 15)), ("Evening peak (15-19 h)", range(15, 19)), ("Evening (19-24 h)", range(19, 24)), ("Whole day", range(24))]
DOWNTOWN = (-76.6122, 39.2904)          # Inner Harbor, Pratt and Light Streets
KEY_BRIDGE = (-76.5285, 39.2176)
RINGS = [(0, 5, "0-5 km"), (5, 10, "5-10 km"), (10, 20, "10-20 km"), (20, 1e9, "over 20 km")]
COUNTY = {"BALTIMORE CITY": "Baltimore City", "BALTIMORE": "Baltimore County", "ANNE ARUNDEL": "Anne Arundel", "HOWARD": "Howard", "HARFORD": "Harford", "CARROLL": "Carroll"}
geh = lambda m, c: np.sqrt(2 * (m - c) ** 2 / np.maximum(m + c, 1e-9))
ZERO = 100          # vehicles per weekday: a matched link with less model traffic than this is 'near zero'


def summary(d, m="model_all_mean", c="count_all"):
    """Fit statistics of a station set on the seed-mean model volume (the runs differ by about 0.001 in the ratio)."""
    if not len(d): return dict(n=0)
    r = d[m] / d[c]
    return dict(n=int(len(d)), count=float(d[c].sum()), model=float(d[m].sum()), ratio=float(d[m].sum() / d[c].sum()), median_ratio=float(r.median()),
                within25=float(r.between(0.75, 1.25).mean()), prmse=float(100 * np.sqrt(((d[m] - d[c]) ** 2).mean()) / d[c].mean()),
                within_fhwa=float(((100 * (d[m] - d[c]).abs() / d[c]) <= d.fhwa_dev).mean()))


def both(d):
    a = summary(d); p = summary(d, "model_car_mean", "count_pass")
    return dict(n=a.get("n", 0), count=a.get("count"), ratio_all=a.get("ratio"), ratio_pass=p.get("ratio"), prmse_all=a.get("prmse"), prmse_pass=p.get("prmse"),
                median_ratio_pass=p.get("median_ratio"), within25=a.get("within25"), within_fhwa=a.get("within_fhwa"))


def stations():
    from pyproj import Transformer
    S = pd.read_csv(f"{CD}/stations_model_vs_count.csv", low_memory=False, dtype={"link_NE": str, "link_SW": str, "LOCATION_ID": str})
    # the station table of validate_counts.py is written with four significant digits: take the exact coordinates, counts and lanes from the match table
    X = pd.read_csv(f"{V}/data/count_stations_matched.csv", dtype={"LOCATION_ID": str}, low_memory=False).drop_duplicates("LOCATION_ID").set_index("LOCATION_ID")
    for c in ["x", "y", "AAWDT_2024", "AADT_2024", "AADT_2023", "NUM_LANES", "CAR_AADT", "LIGHT_TRUCK_AADT", "SINGLE_UNIT_AADT", "COMBINATION_UNIT_AADT"]:
        S[c] = S.LOCATION_ID.map(X[c])
    exact = S.AAWDT_2024.where(S.AAWDT_2024 > 0, S.AADT_2024); S["count_pass"] = S.count_pass * exact / S.count_all; S["count_all"] = exact
    S["ratio_all"] = S.model_all_mean / S.count_all; S["ratio_pass"] = S.model_car_mean / S.count_pass
    S["link_NE"] = S.link_NE.where(S.link_NE.notna() & (S.link_NE != "nan"), None); S["link_SW"] = S.link_SW.where(S.link_SW.notna() & (S.link_SW != "nan"), None)
    S["link_NE"] = S.link_NE.str.replace(r"\.0$", "", regex=True); S["link_SW"] = S.link_SW.str.replace(r"\.0$", "", regex=True)
    tf = Transformer.from_crs(CRS, 4326, always_xy=True); S["lon"], S["lat"] = tf.transform(S.x.values, S.y.values)
    dx, dy = Transformer.from_crs(4326, CRS, always_xy=True).transform(*DOWNTOWN); S["dist_km"] = np.hypot(S.x - dx, S.y - dy) / 1e3
    kx, ky = Transformer.from_crs(4326, CRS, always_xy=True).transform(*KEY_BRIDGE); S["key_bridge_km"] = np.hypot(S.x - kx, S.y - ky) / 1e3
    S["ring"] = [next(l for lo, hi, l in RINGS if lo <= d < hi) for d in S.dist_km]
    S["county"] = S.COUNTY.map(COUNTY).fillna(S.COUNTY.str.title())
    S["count_age"] = (S.AAWDT_2024 % 10).where(S.AAWDT_2024 > 0, np.nan)      # MDOT: last digit of the published weekday value = years since the count
    S["basis"] = np.where(S.AAWDT_2024 > 0, "Weekday (AAWDT)", "Annual average (AADT)")
    # matching flags (count_stations_matched.csv columns carried by validate_counts) and the parallel-link review of station_review/
    par = set(pd.read_csv(f"{H}/station_review/match_parallel_flagged.csv", dtype={"LOCATION_ID": str}).LOCATION_ID)
    fl = S.match_flags.fillna("").astype(str); cat = S.match_category.fillna("").astype(str)
    S["r_identity"] = S.matched_identity.eq(0); S["r_identity_weak"] = S.matched_identity.eq(1)
    S["r_direction"] = cat.eq("oneway_direction_conflict"); S["r_carriageway"] = cat.eq("other_carriageway_missing")
    S["r_ambiguous"] = fl.str.contains("ambiguous"); S["r_name"] = fl.str.contains("name_differs"); S["r_scc"] = fl.str.contains("outside_scc")
    S["r_parallel"] = S.LOCATION_ID.isin(par); S["r_onedir"] = fl.str.contains("one_direction") & S.use.eq("mainline") & S.match_category.ne("oneway_ok")
    S["r_wide"] = fl.str.contains("rematched_identity_wide")
    S["doubtful"] = S.r_identity | S.r_direction | S.r_carriageway | S.r_ambiguous | S.r_parallel | S.r_scc | S.r_wide
    S["weak"] = (S.r_name | S.r_identity_weak) & ~S.doubtful
    S["same_link"] = S.link_NE.notna() & (S.link_NE == S.link_SW) & S.use.eq("mainline") & (S.NE_SPLIT.between(1, 99))
    S["near_zero"] = S.use.eq("mainline") & (S.model_all_mean < ZERO)
    S["laneclass"] = pd.cut(S.NUM_LANES, [0, 2, 4, 6, 99], labels=["1-2 lanes", "3-4 lanes", "5-6 lanes", "7 or more lanes"])
    S["agegroup"] = pd.cut(S.count_age, [-1, 0, 1, 2, 3, 4, 99], labels=["Counted 2024", "1 year old", "2 years", "3 years", "4 years", "5 years or older"])
    S["light_truck_sh"] = np.where(S.has_cls, S.LIGHT_TRUCK_AADT.fillna(0) / S.AADT_CLS, np.nan)
    return S


def links_map(S):
    """Car links of the network with geometry and the seed-mean daily volumes (for the map); cached as parquet."""
    out = f"{DATA}/links_map.parquet"
    if os.path.exists(out): return pd.read_parquet(out)
    L = pd.read_csv(f"{RUN_ROOT}/2024_s1/output_links.csv.gz", sep=";", dtype={"link": str, "from_node": str, "to_node": str}, usecols=["link", "from_node", "to_node", "length", "freespeed", "capacity", "lanes", "modes", "osm:way:highway", "osm:way:name", "geometry", "vol_car"])
    L = L[L.modes.str.contains("car", na=False)].rename(columns={"osm:way:highway": "hw", "osm:way:name": "name", "from_node": "f", "to_node": "t"}).drop(columns="modes")
    Vm = pd.read_csv(f"{CD}/link_daily_volume_mean.csv.gz", dtype={"link": str}).set_index("link")
    L = L.join(Vm, on="link"); L["car"] = L.car.fillna(0); L["bus"] = L.bus.fillna(0); L["vol"] = L.car + L.bus
    try:
        A = pd.read_parquet(f"{V}/data/network_audit_links.parquet", columns=["link", "mdot_fc", "in_scc"]); A["link"] = A.link.astype(str); L = L.join(A.set_index("link"), on="link")
    except Exception: L["mdot_fc"] = np.nan; L["in_scc"] = np.nan
    st = pd.concat([S[["LOCATION_ID", "link_NE"]].rename(columns={"link_NE": "link"}), S[["LOCATION_ID", "link_SW"]].rename(columns={"link_SW": "link"})]).dropna()
    L["stations"] = L.link.map(st.groupby("link").LOCATION_ID.apply(lambda s: ";".join(s)))
    L["geometry"] = L.geometry.str.replace(r"\s+", " ", regex=True).str.strip()
    L.to_parquet(out, index=False); return L


def link_seed_stats(S):
    """Per link: daily volume (car x 10 + bus) of every run, its mean, smallest and largest, and the mean hourly profile's morning (6-10 h)
    and evening (15-19 h) peak-hour volumes; per station and direction: the daily volume of the matched link in every run.
    Model volume as in validate_counts.model_seed: final link statistics minus the transit vehicles of the final iteration, times ten; buses once."""
    out = f"{DATA}/links_seed_stats.parquet"; out2 = f"{DATA}/stations_direction_volumes.csv"
    if os.path.exists(out) and os.path.exists(out2): return pd.read_parquet(out), pd.read_csv(out2, dtype={"LOCATION_ID": str, "link": str})
    LH = os.environ.get("LINK_HOURS", f"{WORK}/link_hours")
    seeds = sorted(int(re.search(r"_s(\d+)$", d).group(1)) for d in glob.glob(f"{RUN_ROOT}/2024_s*") if re.search(r"_s\d+$", d) and os.path.exists(f"{d}/ITERS/it.{IT}/{IT}.linkstats.txt.gz") and os.path.exists(f"{LH}/link_hours_s{re.search(r'_s(\d+)$', d).group(1)}.csv.gz"))
    HRS = [f"HRS{h}-{h+1}avg" for h in range(24)]; daily = {}; hourly_sum = None; index = None
    for s in seeds:
        LS = pd.read_csv(f"{RUN_ROOT}/2024_s{s}/ITERS/it.{IT}/{IT}.linkstats.txt.gz", sep="\t", dtype={"LINK": str}, usecols=["LINK"] + HRS).set_index("LINK"); LS.columns = range(24)
        E = pd.read_csv(f"{LH}/link_hours_s{s}.csv.gz", dtype={"link": str}); E = E[E.hour < 24]
        pt = E.assign(pt=E.bus + E.pt_other).pivot_table(index="link", columns="hour", values="pt", aggfunc="sum").reindex(index=LS.index, columns=range(24)).fillna(0)
        bus = E.pivot_table(index="link", columns="hour", values="bus", aggfunc="sum").reindex(index=LS.index, columns=range(24)).fillna(0)
        allv = (LS - pt).clip(lower=0) * EXP + bus
        if index is None: index = LS.index; hourly_sum = allv.values.copy()
        else: allv = allv.reindex(index).fillna(0); hourly_sum += allv.values
        daily[s] = allv.sum(axis=1)
        print(f"  link statistics of run {s} read", flush=True)
    D = pd.DataFrame(daily).reindex(index).fillna(0); Hm = hourly_sum / len(seeds)
    am = Hm[:, 6:10]; pm = Hm[:, 15:19]
    R = pd.DataFrame({"link": index.values, "vol_mean": D.mean(axis=1).values, "vol_min": D.min(axis=1).values, "vol_max": D.max(axis=1).values,
                      "am_peak_vol": am.max(axis=1), "am_peak_hour": 6 + am.argmax(axis=1), "pm_peak_vol": pm.max(axis=1), "pm_peak_hour": 15 + pm.argmax(axis=1)})
    R.to_parquet(out, index=False)
    rows = []
    for r in S.itertuples():
        for dirn, lk in (("NE", r.link_NE), ("SW", r.link_SW)):
            if isinstance(lk, str) and lk in D.index:
                v = D.loc[lk]; rows.append(dict(LOCATION_ID=r.LOCATION_ID, dir=dirn, link=lk, mean=float(v.mean()), min=float(v.min()), max=float(v.max()), **{f"run{s}": float(v[s]) for s in seeds}))
    SD = pd.DataFrame(rows); SD.to_csv(out2, index=False, float_format="%.1f")
    return R, SD


def add_capacity(S, L):
    """Capacity class of the matched links as coded in the run network (capacity per lane): 600 tertiary and residential, 800 secondary,
    1,500 primary and trunk, the bottleneck capacities of the Highway Capacity Manual on motorways."""
    Li = L.set_index("link")
    cap = S.link_NE.map(Li.capacity).fillna(0) + S.link_SW.map(Li.capacity).fillna(0); lanes = S.link_NE.map(Li.lanes).fillna(0) + S.link_SW.map(Li.lanes).fillna(0)
    S["cap_total"] = cap.where(cap > 0); S["lanes_net"] = lanes.where(lanes > 0); S["cap_per_lane"] = S.cap_total / S.lanes_net
    S["capclass"] = pd.cut(S.cap_per_lane, [0, 700, 1000, 1700, 1e9], labels=["600 per lane (tertiary, residential)", "800 per lane (secondary)", "1,500 per lane (primary, trunk)", "Freeway (bottleneck capacity)"])
    S["hw_net"] = S.link_NE.map(Li.hw).fillna(S.link_SW.map(Li.hw))
    return S


# ------------------------------------------------------------------------------------------------ a. matching audit
def matching_audit(S):
    M = S[S.use == "mainline"]
    reasons = [("r_identity", "Road identity of the matched link not confirmed"), ("r_direction", "One-way count whose direction contradicts the network"),
               ("r_carriageway", "Other carriageway missing in the network"), ("r_ambiguous", "Another compatible link of a different road as near"),
               ("r_parallel", "Parallel link of another road carries more model traffic than the matched link"), ("r_scc", "Matched link outside the connected core of the network"),
               ("r_wide", "Identity rematched to a link beyond the tolerance"), ("r_onedir", "Two-way count with one direction matched"),
               ("r_name", "Road name of the station not found in the link name"), ("r_identity_weak", "Road identity confirmed by one criterion only")]
    R = pd.DataFrame([dict(reason=lab, stations=int(M[c].sum()), ramp_stations=int(S[(S.use == "ramp")][c].sum()), tier="doubtful" if c in ("r_identity", "r_direction", "r_carriageway", "r_ambiguous", "r_parallel", "r_scc", "r_wide") else "weak") for c, lab in reasons])
    R.to_csv(f"{DATA}/matching_reasons.csv", index=False)
    rows = []
    for lab, d in [("All mainline stations", M), ("Without doubtful matches", M[~M.doubtful]), ("Without doubtful and weak matches", M[~M.doubtful & ~M.weak]),
                   ("Doubtful matches only", M[M.doubtful]), ("Weak matches only", M[M.weak]), ("Without near-zero model volume", M[~M.near_zero]),
                   ("Without doubtful, weak and near-zero", M[~M.doubtful & ~M.weak & ~M.near_zero]), ("One station per link", M.drop_duplicates(subset=["link_NE", "link_SW"], keep="first"))]:
        rows.append(dict(set=lab, **both(d)))
        for k in CLASSES: rows.append(dict(set=lab, cls=k, **both(d[d.cls == k])))
    A = pd.DataFrame(rows); A.to_csv(f"{DATA}/matching_audit.csv", index=False, float_format="%.5g")
    cols = ["LOCATION_ID", "ROADNAME", "county", "cls", "use", "count_all", "count_pass", "model_all_mean", "model_car_mean", "ratio_pass", "link_NE", "link_SW", "in_scc_NE", "in_scc_SW", "match_flags", "match_category", "matched_identity", "parallel_review", "lon", "lat"]
    M[M.doubtful | M.weak].assign(tier=np.where(M[M.doubtful | M.weak].doubtful, "doubtful", "weak"))[cols + ["tier"]].to_csv(f"{DATA}/stations_doubtful.csv", index=False, float_format="%.5g")
    Z = M[M.near_zero].copy()
    Z["cause"] = np.where(Z.in_scc_NE.eq(False) | Z.in_scc_SW.eq(False), "link outside the connected core", np.where(Z.lat > 39.70, "network ends at the state line",
                 np.where(Z.doubtful, "doubtful match", np.where(Z.match_flags.fillna("").str.contains("name_differs"), "name differs", "connected link, no route uses it"))))   # 39.72 N: Pennsylvania line
    Z[cols + ["cause"]].to_csv(f"{DATA}/stations_zero_volume.csv", index=False, float_format="%.5g")
    # several stations on one link (two-way stations: same pair of links; one-way: same link)
    key = M.link_NE.fillna("") + "|" + M.link_SW.fillna("")
    dup = M[key.duplicated(keep=False)].assign(linkkey=key[key.duplicated(keep=False)]).sort_values("linkkey")
    dup[["linkkey"] + cols].to_csv(f"{DATA}/stations_shared_link.csv", index=False, float_format="%.5g")
    same = M[M.same_link]
    same[cols].to_csv(f"{DATA}/stations_same_link_both_directions.csv", index=False, float_format="%.5g")
    meta = dict(mainline=int(len(M)), doubtful=int(M.doubtful.sum()), weak=int(M.weak.sum()), near_zero=int(M.near_zero.sum()), near_zero_outside_core=int((Z.cause == "link outside the connected core").sum()),
                near_zero_doubtful=int((Z.cause == "doubtful match").sum()), near_zero_state_line=int((Z.cause == "network ends at the state line").sum()), same_link=int(len(same)), shared_link_stations=int(len(dup)), shared_links=int(dup.linkkey.nunique()),
                ramp_doubtful=int(S[(S.use == "ramp")].doubtful.sum()), zero_threshold=ZERO,
                near_zero_count_sum=float(Z.count_all.sum()), near_zero_share_of_count=float(Z.count_all.sum() / M.count_all.sum()))
    return A, meta


# ------------------------------------------------------------------------------------------------ b. spatial pattern
def morans_i(x, xy, k=8, nperm=999, seed=2026):
    from scipy.spatial import cKDTree
    x = np.asarray(x, float); n = len(x); z = x - x.mean()
    _, idx = cKDTree(xy).query(xy, k=k + 1); idx = idx[:, 1:]
    lag = z[idx].mean(axis=1)                                     # row-standardised k-nearest-neighbour weights
    I = (z * lag).sum() / (z ** 2).sum()
    rng = np.random.default_rng(seed); sims = np.empty(nperm)
    for i in range(nperm):
        zp = rng.permutation(z); sims[i] = (zp * zp[idx].mean(axis=1)).sum() / (zp ** 2).sum()
    p = (1 + (sims >= I).sum()) / (nperm + 1); zsc = (I - sims.mean()) / sims.std(ddof=1)
    return dict(I=float(I), expected=float(-1 / (n - 1)), p_perm=float(p), z_perm=float(zsc), k=k, n=int(n))


def spatial(S):
    M = S[S.use == "mainline"].copy(); rows = []
    for dim, col, order in [("Ring", "ring", [l for _, _, l in RINGS]), ("County", "county", ["Baltimore City", "Baltimore County", "Anne Arundel", "Howard", "Harford", "Carroll"])]:
        for g in order:
            d = M[M[col] == g]; rows.append(dict(dimension=dim, group=g, **both(d), freeway_share=float((d.fac == "freeway").mean()) if len(d) else np.nan, counted24=int(d.counted24.sum()) if len(d) else 0))
            for fac in ["freeway", "arterial", "collector"]: rows.append(dict(dimension=dim, group=g, fac=fac, **both(d[d.fac == fac])))
    G = pd.DataFrame(rows); G.to_csv(f"{DATA}/spatial_groups.csv", index=False, float_format="%.5g")
    # Moran's I of the log passenger ratio (stations with a model volume), k nearest neighbours; also after removing the class means
    D = M[(M.model_car_mean > 0) & (M.count_pass > 0)].copy(); D["lr"] = np.log(D.model_car_mean / D.count_pass)
    D["lr_cls"] = D.lr - D.groupby("cls").lr.transform("mean")
    xy = D[["x", "y"]].values; mi = []
    for k in (4, 8, 12):
        mi.append(dict(variable="log passenger ratio", **morans_i(D.lr.values, xy, k)))
        mi.append(dict(variable="log passenger ratio, class means removed", **morans_i(D.lr_cls.values, xy, k)))
    for fac in ["freeway", "arterial", "collector"]:
        d = D[D.fac == fac]; mi.append(dict(variable=f"log passenger ratio, {fac}s only", **morans_i(d.lr.values, d[["x", "y"]].values, 8)))
    MI = pd.DataFrame(mi); MI.to_csv(f"{DATA}/morans_i.csv", index=False, float_format="%.4g")
    # distance to the nearest neighbour of the same class (how local the comparison is)
    spatial_fig(G)
    return G, MI


def spatial_fig(G):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    fig, axs = ps.figure(2.9, ncols=2, gridspec_kw=dict(width_ratios=[4, 6]))
    short = {"0-5 km": "0–5", "5-10 km": "5–10", "10-20 km": "10–20", "over 20 km": "> 20", "Baltimore City": "Baltimore\nCity", "Baltimore County": "Baltimore\nCounty", "Anne Arundel": "Anne\nArundel"}
    for ax, dim in zip(axs, ["Ring", "County"]):
        d = G[(G.dimension == dim) & G.fac.isna()].reset_index(drop=True); xx = np.arange(len(d)); w = 0.38
        ax.bar(xx - w / 2, d.ratio_all, w * 0.9, color=ps.MODEL)
        ax.bar(xx + w / 2, d.ratio_pass, w * 0.9, color="white", edgecolor=ps.MODEL, hatch="////", lw=0.8)
        ax.axhline(1, color=ps.OBSERVED, lw=0.8); ax.set_xticks(xx); ax.set_xticklabels([f"{short.get(g, g)}\n({int(n)})" for g, n in zip(d.group, d.n)], fontsize=ps.TICK)
        ax.set_ylim(0, 1.25); ax.set_ylabel(ps.RATIO_LABEL if dim == "Ring" else ""); ax.set_xlabel("Distance from downtown Baltimore (km)\nand number of stations" if dim == "Ring" else "County and number of stations")
    fig.legend(handles=[Patch(color=ps.MODEL, label="All vehicles"), Patch(facecolor="white", edgecolor=ps.MODEL, hatch="////", label="Passenger vehicles"), Line2D([], [], color=ps.OBSERVED, lw=0.8, label="Model = count")],
               loc="outside lower center", fontsize=ps.TICK, ncol=3)
    ps.finish(fig, f"{FIG}/fig_ratio_by_ring_county", panel_labels="ab")


# ------------------------------------------------------------------------------------------------ c. count quality
def count_quality(S):
    M = S[S.use == "mainline"]; rows = []
    dims = [("Count year", "counted24", {True: "Counted in 2024", False: "Estimate from an older count"}), ("Count age", "agegroup", None), ("Basis of the count", "basis", None),
            ("Lanes of the station", "laneclass", None), ("Capacity of the matched link", "capclass", None)]
    for dim, col, lab in dims:
        vals = list(lab.keys()) if lab else [v for v in (M[col].cat.categories if hasattr(M[col], "cat") else sorted(M[col].dropna().unique()))]
        for v in vals:
            d = M[M[col] == v]
            if not len(d): continue
            rows.append(dict(dimension=dim, group=lab[v] if lab else str(v), **both(d), freeway_share=float((d.fac == "freeway").mean()), mean_count=float(d.count_all.mean())))
    Q = pd.DataFrame(rows); Q.to_csv(f"{DATA}/count_quality.csv", index=False, float_format="%.5g")
    # count year by class (the share counted in 2024 differs by class)
    rows = []
    for k in CLASSES:
        d = M[M.cls == k]; a = d[d.counted24]; b = d[~d.counted24]
        rows.append(dict(cls=k, n=len(d), counted24=int(len(a)), ratio_pass_counted=a.model_car_mean.sum() / a.count_pass.sum() if len(a) else np.nan, ratio_pass_estimated=b.model_car_mean.sum() / b.count_pass.sum() if len(b) else np.nan,
                         prmse_pass_counted=summary(a, "model_car_mean", "count_pass").get("prmse"), prmse_pass_estimated=summary(b, "model_car_mean", "count_pass").get("prmse")))
    pd.DataFrame(rows).to_csv(f"{DATA}/count_quality_by_class.csv", index=False, float_format="%.5g")
    return Q


# ------------------------------------------------------------------------------------------------ d. volume groups
def volume_groups(S):
    M = S[S.use == "mainline"]; rows = []
    for i, (lo, hi, acc, pref) in enumerate(VGROUPS):
        d = M[M.vgroup == i]; lab = f"{lo/1e3:.0f}-{hi/1e3:.0f} thousand" if hi < 1e11 else f"over {lo/1e3:.0f} thousand"
        rows.append(dict(group=lab, lo=lo, hi=hi, acceptable=acc, preferable=pref, **both(d), share_stations=len(d) / len(M), share_count=d.count_all.sum() / M.count_all.sum(), meets_acceptable=bool(both(d)["prmse_all"] <= acc) if len(d) else None))
    for lo, lab in [(1e4, "10 thousand and more"), (2.5e4, "25 thousand and more"), (5e4, "50 thousand and more")]:
        d = M[M.count_all >= lo]; rows.append(dict(group=lab, lo=lo, hi=1e12, **both(d), share_stations=len(d) / len(M), share_count=d.count_all.sum() / M.count_all.sum()))
    rows.append(dict(group="All stations", lo=0, hi=1e12, acceptable=45, preferable=35, **both(M), share_stations=1.0, share_count=1.0))
    # volume-weighted RMSE (each station weighted by its count), which the FDOT areawide figure effectively compares with the sum
    G = pd.DataFrame(rows); G.to_csv(f"{DATA}/volume_groups_fdot.csv", index=False, float_format="%.5g")
    return G


# ------------------------------------------------------------------------------------------------ f. hourly detail by counter
def counters_detail():
    C = pd.read_csv(f"{TD}/tmas_hourly.csv", dtype={"station": str, "mdot": str, "link": str})
    C["grp2"] = np.where(C.grp == "Freeways", "Freeways", "Arterials and collectors")
    rows = []; prow = []
    for (st, dr), d in C.groupby(["station", "dir"]):
        d = d.sort_values("hour"); o = d.obs_pass.values; m = d.model.values
        po = o / o.sum(); pm = m / max(m.sum(), 1e-9); corr = float(np.corrcoef(po, pm)[0, 1]) if m.sum() > 0 else np.nan
        tvd = float(0.5 * np.abs(po - pm).sum()) if m.sum() > 0 else np.nan
        ratio = m.sum() / o.sum(); pk_o = int(np.argmax(o)); pk_m = int(np.argmax(m)) if m.sum() > 0 else -1
        am_o = o[6:10].sum() / o.sum(); am_m = m[6:10].sum() / max(m.sum(), 1e-9); md_o = o[10:15].sum() / o.sum(); md_m = m[10:15].sum() / max(m.sum(), 1e-9)
        rec = dict(station=st, mdot=d.mdot.iloc[0], road=d.road.iloc[0], direction=dr, cls=d.cls.iloc[0], grp=d.grp2.iloc[0], link=d.link.iloc[0], n_days=int(d.n_days.iloc[0]), count_day=float(o.sum()), model_day=float(m.sum()),
                   ratio_day=float(ratio), profile_corr=corr, profile_tvd=tvd, peak_hour_count=pk_o, peak_hour_model=pk_m, am_share_count=am_o, am_share_model=am_m, midday_share_count=md_o, midday_share_model=md_m,
                   geh5_day=float((d.geh < 5).mean()), geh_mean=float(d.geh.mean()))
        for p, hs in PERIODS:
            x = d[d.hour.isin(list(hs))]; rec[f"ratio_{p.split(' (')[0]}"] = x.model.sum() / x.obs_pass.sum(); rec[f"geh5_{p.split(' (')[0]}"] = float((x.geh < 5).mean())
            prow.append(dict(station=st, direction=dr, road=rec["road"], grp=rec["grp"], period=p, ratio=x.model.sum() / x.obs_pass.sum(), geh5=float((x.geh < 5).mean()), hours=len(x)))
        shape = "shape off" if not (corr >= 0.90) else "shape right"
        level = "level low" if ratio < 0.85 else "level high" if ratio > 1.15 else "level right"
        rec["verdict"] = f"{shape}, {level}"; rows.append(rec)
    D = pd.DataFrame(rows).sort_values(["grp", "road", "station", "direction"]); D.to_csv(f"{DATA}/counters_direction_detail.csv", index=False, float_format="%.4g")
    P = pd.DataFrame(prow); P.to_csv(f"{DATA}/counters_period_direction.csv", index=False, float_format="%.4g")
    # by period and direction group (north/east against south/west) and road group
    P["dirgrp"] = np.where(P.direction.isin(["Northbound", "Eastbound"]), "North- or eastbound", "South- or westbound")
    rows = []
    for g in ["Freeways", "Arterials and collectors", "All stations"]:
        for dg in ["North- or eastbound", "South- or westbound", "Both"]:
            for p, _ in PERIODS:
                x = C[(C.grp2 == g) if g != "All stations" else C.index == C.index]; x = x[x.hour.isin(list(dict(PERIODS)[p]))]
                if dg != "Both": x = x[x.dir.isin(["Northbound", "Eastbound"]) == (dg == "North- or eastbound")]
                rows.append(dict(group=g, direction=dg, period=p, directions=x.groupby(["station", "dir"]).ngroups, ratio=x.model.sum() / x.obs_pass.sum(), geh5=float((x.geh < 5).mean()), geh10=float((x.geh < 10).mean()), hours=len(x)))
    pd.DataFrame(rows).to_csv(f"{DATA}/counters_period_summary.csv", index=False, float_format="%.4g")
    counters_fig(C, D)
    return D, P


def counters_fig(C, D):
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    order = D.sort_values(["grp", "road", "station", "direction"], key=lambda s: s.map({"Freeways": 0, "Arterials and collectors": 1}) if s.name == "grp" else s)
    keys = list(zip(order.station, order.direction)); n = len(keys)
    Mx = np.full((n, 24), np.nan); Rx = np.full((n, 24), np.nan)
    for i, (st, dr) in enumerate(keys):
        d = C[(C.station == st) & (C.dir == dr)].sort_values("hour"); Mx[i, d.hour.values] = d.geh.values; Rx[i, d.hour.values] = np.log2(np.maximum(d.model.values, 1) / np.maximum(d.obs_pass.values, 1))
    h = min(ps.MAX_HEIGHT, 0.108 * n + 1.1)
    fig, axs = ps.figure(h, ncols=2, sharey=True, gridspec_kw=dict(width_ratios=[1, 1]))
    bounds = [0, 5, 10, 20, 40]; cmap = ListedColormap([ps.MODEL, "#86b6ef", ps.VARIANT, "#9c1d1c"])
    im0 = axs[0].imshow(np.minimum(Mx, 39.9), aspect="auto", cmap=cmap, norm=BoundaryNorm(bounds, cmap.N), interpolation="nearest")
    im1 = axs[1].imshow(Rx, aspect="auto", cmap=ps.DIV, vmin=-1.5, vmax=1.5, interpolation="nearest")
    labs = [f"{r.road}, {str(r.station)[2:].lstrip('0')} {r.direction[0]}" for r in order.itertuples()]
    axs[0].set_yticks(range(n)); axs[0].set_yticklabels(labs, fontsize=ps.TICK)
    for ax in axs:
        ax.set_xticks([0, 6, 12, 18, 23]); ax.set_xticklabels(["0", "6", "12", "18", "23"]); ax.set_xlabel("Hour of the day"); ax.grid(False)
        nf = int((order.grp == "Freeways").sum()); ax.axhline(nf - 0.5, color=ps.INK, lw=0.8)
    axs[0].set_title("GEH statistic", loc="left", fontsize=ps.FONT, fontweight="normal"); axs[1].set_title("Model ÷ count (log scale)", loc="left", fontsize=ps.FONT, fontweight="normal")
    cb0 = fig.colorbar(im0, ax=axs[0], orientation="horizontal", fraction=0.025, pad=0.06, ticks=[2.5, 7.5, 15, 30]); cb0.ax.set_xticklabels(["below 5", "5 to 10", "10 to 20", "over 20"], fontsize=ps.TICK); cb0.ax.tick_params(length=0)
    cb1 = fig.colorbar(im1, ax=axs[1], orientation="horizontal", fraction=0.025, pad=0.06, ticks=[-1.5, -1, 0, 1, 1.5]); cb1.ax.set_xticklabels(["0.35", "0.5", "1", "2", "2.8"], fontsize=ps.TICK)
    ps.finish(fig, f"{FIG}/fig_counters_geh_heatmap")


# ------------------------------------------------------------------------------------------------ g. transit by operator
def transit_by_agency():
    try: T = pd.read_csv(f"{RD}/c4_transit_lines.csv")
    except FileNotFoundError: return None
    T["agency"] = T.transit_line.astype(str).str.split(":").str[0]
    AG = {"bus": "Maryland Transit Administration, local bus", "lr": "Maryland Transit Administration, light rail", "mt": "Maryland Transit Administration, metro subway", "cb": "Maryland Transit Administration, commuter bus",
          "marc": "MARC train (Maryland Transit Administration)", "wmb": "Washington Metropolitan Area Transit Authority, bus", "wmr": "Washington Metropolitan Area Transit Authority, rail", "aact": "Anne Arundel County Transit",
          "rta": "Regional Transportation Agency of Central Maryland", "ccc": "Charm City Circulator", "hfd": "Harford Transit LINK", "cts": "Carroll Transit", "at": "Annapolis Transit", "ro": "Montgomery County Ride On",
          "pg": "Prince George's County TheBus", "amt": "Amtrak", "hc": "Harbor Connector", "tl": "Towson Loop"}
    g = T.groupby(["agency", "group"]).agg(lines=("transit_line", "nunique"), mean=("mean", "sum"), min=("min", "sum"), max=("max", "sum")).reset_index()
    g["operator"] = g.agency.map(lambda a: AG.get(a.lower(), a))
    g = g.sort_values("mean", ascending=False); g.to_csv(f"{DATA}/transit_by_agency.csv", index=False, float_format="%.1f")
    return g


# ------------------------------------------------------------------------------------------------ h. convergence
def convergence(S):
    seeds = sorted(int(re.search(r"_s(\d+)$", d).group(1)) for d in glob.glob(f"{RUN_ROOT}/2024_s*") if re.search(r"_s\d+$", d) and os.path.exists(f"{d}/scorestats.csv"))
    rows = []; lrows = []
    for s in seeds:
        d = f"{RUN_ROOT}/2024_s{s}"
        sc = pd.read_csv(f"{d}/scorestats.csv", sep=";").set_index("iteration"); ms = pd.read_csv(f"{d}/modestats.csv", sep=";").set_index("iteration")
        ph = pd.read_csv(f"{d}/ph_modestats.csv", sep=";"); ph.columns = [c.strip().lower() for c in ph.columns]; ph = ph.set_index("iteration")
        td = pd.read_csv(f"{d}/traveldistancestats.csv", sep=";"); td.columns = [c.strip().lower() for c in td.columns]; td = td.set_index("iteration")
        last = sc.index.max(); i90 = int(round(0.9 * last)); i80 = int(round(0.8 * last)); i95 = last - 5
        rec = dict(seed=s, last=last, score_last=sc.avg_executed[last], score_90=sc.avg_executed[i90], score_80=sc.avg_executed[i80],
                   score_change_90_100_pct=100 * (sc.avg_executed[last] - sc.avg_executed[i90]) / abs(sc.avg_executed[i90]), score_change_95_100_pct=100 * (sc.avg_executed[last] - sc.avg_executed[i95]) / abs(sc.avg_executed[i95]),
                   score_change_80_90_pct=100 * (sc.avg_executed[i90] - sc.avg_executed[i80]) / abs(sc.avg_executed[i80]), score_best_minus_executed=sc.avg_best[last] - sc.avg_executed[last],
                   car_share_last=100 * ms.car[last], car_share_90=100 * ms.car[i90], car_share_change_pp=100 * (ms.car[last] - ms.car[i90]), pt_share_change_pp=100 * (ms.pt[last] - ms.pt[i90]),
                   car_hours_last=ph.car_travel[last] * EXP, car_hours_change_90_100_pct=100 * (ph.car_travel[last] - ph.car_travel[i90]) / ph.car_travel[i90], car_hours_change_80_90_pct=100 * (ph.car_travel[i90] - ph.car_travel[i80]) / ph.car_travel[i80],
                   car_hours_max_abs_step_last10_pct=100 * (ph.car_travel.loc[i90:last].diff().abs() / ph.car_travel.loc[i90:last].shift()).max())
        # link statistics of the final iteration file: min, average and maximum over the iterations averaged (five), per link and hour
        f = f"{RUN_ROOT}/2024_s{s}/ITERS/it.{IT}/{IT}.linkstats.txt.gz"
        if os.path.exists(f):
            LS = pd.read_csv(f, sep="\t", dtype={"LINK": str}, usecols=lambda c: c == "LINK" or (c.startswith("HRS") and not c.startswith("HRS24")))
            av = LS[[f"HRS{h}-{h+1}avg" for h in range(24)]].values; mn = LS[[f"HRS{h}-{h+1}min" for h in range(24)]].values; mx = LS[[f"HRS{h}-{h+1}max" for h in range(24)]].values
            day = av.sum(1); rng_h = (mx - mn)
            for thr in (20, 50, 100):          # sample-scale hourly volume (x 10 expanded)
                m = av >= thr; rel = rng_h[m] / av[m]
                lrows.append(dict(seed=s, hourly_threshold_expanded=thr * EXP, link_hours=int(m.sum()), median_rel_range=float(np.median(rel)), mean_rel_range=float(rel.mean()), share_rel_range_gt_10pct=float((rel > 0.10).mean()), share_rel_range_gt_25pct=float((rel > 0.25).mean())))
            m = day >= 100
            rec.update(links_ge_1000=int(m.sum()), daily_rel_range_upper_median=float(np.median(rng_h[m].sum(1) / day[m])), daily_rel_range_upper_mean=float((rng_h[m].sum(1) / day[m]).mean()))
            # final iteration against the mean of the last five: vol_car of output_links.csv is the car volume of the final iteration
            try:
                OL = pd.read_csv(f"{d}/output_links.csv.gz", sep=";", dtype={"link": str}, usecols=["link", "vol_car"]).set_index("link")
                x = pd.DataFrame({"avg": day}, index=LS.LINK.values).join(OL, how="inner"); x = x[x.avg >= 100]
                dev = (x.vol_car - x.avg).abs() / x.avg
                rec.update(final_vs_mean5_links=int(len(x)), final_vs_mean5_median_abs_pct=float(100 * dev.median()), final_vs_mean5_mean_abs_pct=float(100 * dev.mean()), final_vs_mean5_weighted_abs_pct=float(100 * (x.vol_car - x.avg).abs().sum() / x.avg.sum()),
                           final_vs_mean5_total_ratio=float(x.vol_car.sum() / x.avg.sum()))
            except Exception as e: print("output_links:", e)
        rows.append(rec)
    CV = pd.DataFrame(rows); CV.to_csv(f"{DATA}/convergence_summary.csv", index=False, float_format="%.5g")
    LR = pd.DataFrame(lrows); LR.to_csv(f"{DATA}/linkstats_iteration_range.csv", index=False, float_format="%.4g")
    # five-seed spread of the station volumes
    M = S[(S.use == "mainline") & (S.model_all_mean > 0)].copy(); M["cv"] = M.model_all_sd / M.model_all_mean; M["range_rel"] = (M.model_all_p95 - M.model_all_p5) / M.model_all_mean
    rows = []
    for i, (lo, hi, _, _) in enumerate(VGROUPS):
        d = M[M.vgroup == i]; lab = f"{lo/1e3:.0f}-{hi/1e3:.0f} thousand" if hi < 1e11 else f"over {lo/1e3:.0f} thousand"
        rows.append(dict(group=lab, n=len(d), median_cv=float(d.cv.median()), median_range_rel=float(d.range_rel.median()), p90_range_rel=float(d.range_rel.quantile(0.9)) if len(d) else np.nan))
    rows.append(dict(group="All stations", n=len(M), median_cv=float(M.cv.median()), median_range_rel=float(M.range_rel.median()), p90_range_rel=float(M.range_rel.quantile(0.9))))
    SS = pd.DataFrame(rows); SS.to_csv(f"{DATA}/seed_spread_stations.csv", index=False, float_format="%.4g")
    return CV, LR, SS


def main():
    S = stations(); print(f"stations {len(S)}: mainline {(S.use == 'mainline').sum()}, ramps {(S.use == 'ramp').sum()}")
    L = links_map(S); print(f"car links {len(L):,}, with model traffic {(L.vol > 0).sum():,}"); S = add_capacity(S, L)
    link_seed_stats(S)
    print(S[S.use == "mainline"].cap_per_lane.round(-1).value_counts().sort_index().to_string())
    A, meta = matching_audit(S); print("matching audit:", meta)
    G, MI = spatial(S); print(MI.to_string())
    Q = count_quality(S); VG = volume_groups(S)
    D, P = counters_detail(); print(D.verdict.value_counts().to_string())
    T = transit_by_agency()
    CV, LR, SS = convergence(S); print(CV.T.to_string())
    S.drop(columns=[c for c in S.columns if c.startswith("r_")]).to_csv(f"{DATA}/stations_diagnostics.csv", index=False, float_format="%.5g")
    a = A[A.cls.isna()].set_index("set")
    mi8 = MI[(MI.variable == "log passenger ratio") & (MI.k == 8)].iloc[0]; mi8c = MI[(MI.variable == "log passenger ratio, class means removed") & (MI.k == 8)].iloc[0]
    J = dict(matching=meta, audit=dict(all=a.loc["All mainline stations"].to_dict(), no_doubtful=a.loc["Without doubtful matches"].to_dict(), no_doubtful_weak=a.loc["Without doubtful and weak matches"].to_dict(),
                                       no_zero=a.loc["Without near-zero model volume"].to_dict(), clean=a.loc["Without doubtful, weak and near-zero"].to_dict(), one_per_link=a.loc["One station per link"].to_dict()),
             morans_i=dict(I=mi8.I, p=mi8.p_perm, z=mi8.z_perm, k=int(mi8.k), n=int(mi8.n), I_class_removed=mi8c.I, p_class_removed=mi8c.p_perm),
             counters=dict(directions=int(len(D)), verdicts=D.verdict.value_counts().to_dict(), shape_right_level_low=D[D.verdict == "shape right, level low"].apply(lambda r: f"{r.road} {str(r.station)[2:].lstrip('0')} {r.direction}", axis=1).tolist(),
                           shape_off=D[D.verdict.str.startswith("shape off")].apply(lambda r: f"{r.road} {str(r.station)[2:].lstrip('0')} {r.direction}", axis=1).tolist()),
             convergence=CV.drop(columns=["seed"]).mean(numeric_only=True).to_dict(), links=dict(n=int(len(L)), with_traffic=int((L.vol > 0).sum())),
             volume_groups=VG.set_index("group")[["n", "share_stations", "share_count", "ratio_all", "ratio_pass", "prmse_all", "prmse_pass"]].to_dict("index"))
    json.dump(J, open(f"{DATA}/diagnostics.json", "w"), indent=1, default=float)


if __name__ == "__main__": main()
