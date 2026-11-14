#!/usr/bin/env python3
"""Small-area validation of land use (SILO, five seeds) and destinations / commuting (ABIT 2024, ten replications) in the six
Baltimore-region counties.  Validation only: nothing is fitted or adjusted.

Geography (see build_crosswalks.py):
  * The 1,588 MSTM zones (599 in the study area) neither nest in 2020 census tracts nor contain them: 79 % of the 699 tracts
    have >= 95 % of their occupied units in one zone, but only 66 % of the zones have >= 95 % in one tract.
  * Data published by BLOCK (Census 2020 PL 94-171, LODES 8 WAC / OD) are aggregated to the zones exactly (block internal point
    in the zone polygon), so these comparisons are made at the ZONE level, the model's own resolution (A1, A3b, A4, B1-B3).
  * Data published by TRACT (ACS 5-year) are compared on tract-zone CLUSTERS: the connected components of the bipartite graph
    tracts <-> zones whose edges are the block pieces holding >= 5 % of the occupied units of the tract or of the zone.  0.2 % of the
    occupied units lie in pieces that cross cluster boundaries.  Model zones and observed tracts are summed into clusters.
    2010 tracts (ACS 2012-16) are first split to zones by their 2010 blocks' occupied units, then summed into clusters.
  * District OD: the 21 PUMAs (2010 definitions) on which the zones nest (zoneSystem PUMA_10).
Inputs: out/blocks2020.parquet, out/blocks2010.parquet, out/lodes_block_zone.parquet (build_crosswalks.py);
        out/cache/silo_zone.parquet, silo_flows.parquet (silo_extract.py); out/cache/abit_dest.parquet, abit_flows.parquet
        (abit_extract.py); data/raw/acs_tract (ACS tract tables); data/raw/lodes_wac, lodes_od, bps.
Outputs: out/*.csv (unit-level comparisons + metrics_summary.csv); figures by tract_figures.py.
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, json, glob, os, networkx as nx
V = f"{WORKSPACE}"
D0 = f"{V}/5_reports/validation_tracts/out"; RAW = f"{V}/data/raw"
# env: TRACT_CACHE (extracts of the runs), TRACT_OUT (outputs), SILO_BASE (2016 microdata folder of the land-use runs)
C = os.environ.get("TRACT_CACHE", f"{D0}/cache"); D = os.environ.get("TRACT_OUT", D0); os.makedirs(D, exist_ok=True)
SILO_BASE = os.environ.get("SILO_BASE", "microData")
CTY = [24003, 24005, 24013, 24025, 24027, 24510]
ZS = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").set_index("ZoneId"); Z6 = ZS.index[ZS.COUNTYFIPS.isin(CTY)]
DIST = ZS.PUMA_10                                   # district of each zone (2010 PUMA)
INC_EDGES = [0, 25e3, 50e3, 75e3, 100e3, 150e3, 200e3, np.inf]; INC_LAB = ["<25k", "25-50k", "50-75k", "75-100k", "100-150k", "150-200k", "200k+"]
DW = ["SFD", "SFA", "MF234", "MF5plus", "MH"]
TL_EDGES = [0, 2, 5, 10, 15, 20, 30, 40, 60, np.inf]
M = []                                              # metrics rows

# ------------------------------------------------------------------ metrics
def r2(m, o): m, o = np.asarray(m, float), np.asarray(o, float); return float(np.corrcoef(m, o)[0, 1] ** 2)
def r2log(m, o):
    m, o = np.asarray(m, float), np.asarray(o, float); k = (m > 0) & (o > 0); return float(np.corrcoef(np.log(m[k]), np.log(o[k]))[0, 1] ** 2)
def wmape(m, o): m, o = np.asarray(m, float), np.asarray(o, float); return float(100 * np.abs(m - o).sum() / o.sum())
def medape(m, o): m, o = np.asarray(m, float), np.asarray(o, float); k = o > 0; return float(100 * np.median(np.abs(m[k] - o[k]) / o[k]))
def within(m, o, t): m, o = np.asarray(m, float), np.asarray(o, float); k = o > 0; return float(100 * np.mean(np.abs(m[k] / o[k] - 1) <= t))
def tvd(m, o): m, o = np.asarray(m, float), np.asarray(o, float); return float(50 * np.abs(m / m.sum() - o / o.sum()).sum())
def cr(m, o):
    m, o = np.asarray(m, float), np.asarray(o, float); p, q = m / m.sum(), o / o.sum(); return float(np.minimum(p, q).sum() / np.maximum(p, q).sum())

def add(check, var, geo, n, metric, f, Mdf, o, note=""):
    """Mdf: DataFrame units x runs (seeds / replications) aligned to o; metric on the run mean, range over runs."""
    mean = f(Mdf.mean(axis=1).values, o.values); per = [f(Mdf[c].values, o.values) for c in Mdf.columns]
    M.append(dict(check=check, variable=var, geography=geo, units=n, metric=metric, value=round(mean, 4), run_min=round(min(per), 4), run_max=round(max(per), 4), note=note))
def add1(check, var, geo, n, metric, value, note=""):
    M.append(dict(check=check, variable=var, geography=geo, units=n, metric=metric, value=round(float(value), 4), run_min=np.nan, run_max=np.nan, note=note))
def level_block(check, var, geo, Mdf, o, note=""):
    n = len(o)
    for nm, f in [("R2", r2), ("R2 (log)", r2log), ("weighted MAPE %", wmape), ("median APE %", medape),
                  ("within +-10 % (% of units)", lambda m, o: within(m, o, .10)), ("within +-20 % (% of units)", lambda m, o: within(m, o, .20)),
                  ("total ratio model/observed", lambda m, o: m.sum() / o.sum())]:
        add(check, var, geo, n, nm, f, Mdf, o, note)

# ------------------------------------------------------------------ geography
b20 = pd.read_parquet(f"{D0}/blocks2020.parquet"); b10 = pd.read_parquet(f"{D0}/blocks2010.parquet"); lbz = pd.read_parquet(f"{D0}/lodes_block_zone.parquet")
def clusters(th=0.05):
    tz = b20.groupby(["tract", "zone"]).hu_occ.sum().reset_index(); tz = tz[tz.hu_occ > 0]
    ts = tz.groupby("tract").hu_occ.transform("sum"); zs = tz.groupby("zone").hu_occ.transform("sum")
    e = tz[(tz.hu_occ / ts >= th) | (tz.hu_occ / zs >= th)]
    G = nx.Graph(); G.add_nodes_from("t" + b20.tract.unique()); G.add_nodes_from("z" + pd.Index(Z6).astype(str))
    G.add_edges_from(zip("t" + e.tract, "z" + e.zone.astype(str)))
    # zones without occupied units: attach to the tract holding most of their blocks (or leave alone if no block)
    nb = b20.groupby(["zone", "tract"]).size().reset_index(name="n").sort_values("n").drop_duplicates("zone", keep="last")
    for z, t in zip(nb.zone, nb.tract):
        if G.degree("z" + str(z)) == 0: G.add_edge("z" + str(z), "t" + t)
    comp = {n: i for i, c in enumerate(sorted(nx.connected_components(G), key=lambda c: min(c))) for n in c}
    tc = pd.Series({n[1:]: c for n, c in comp.items() if n[0] == "t"}, name="cluster"); zc = pd.Series({int(n[1:]): c for n, c in comp.items() if n[0] == "z"}, name="cluster")
    tz["ct"] = tz.tract.map(tc); tz["cz"] = tz.zone.map(zc); cross = tz.loc[tz.ct != tz.cz, "hu_occ"].sum() / tz.hu_occ.sum()
    return tc, zc, cross
TC, ZC, CROSS = clusters()
ZC_has_tract = ZC[ZC.isin(TC.values)]
NCL = TC.nunique()
print(f"clusters: {NCL} (with a tract); zones {len(ZC)}; occupied units crossing cluster borders {100 * CROSS:.2f} %")
nt = TC.value_counts(); nz = ZC.value_counts(); one = (nt == 1) & (nz.reindex(nt.index) == 1)
tp = b20.groupby(["tract", "zone"]).hu_occ.sum(); tp = (tp.groupby(level=0).max() / tp.groupby(level=0).sum()); zp = b20.groupby(["zone", "tract"]).hu_occ.sum(); zp = (zp.groupby(level=0).max() / zp.groupby(level=0).sum())
geo_meta = dict(tracts=len(TC), zones_study=len(Z6), zones_with_units=int((b20.groupby("zone").hu_occ.sum() > 0).sum()), clusters=NCL, clusters_1to1=int(one.sum()),
                max_tracts_per_cluster=int(nt.max()), max_zones_per_cluster=int(nz.max()), crossing_pct=100 * CROSS,
                tracts_95pct_in_one_zone=float(100 * (tp >= .95).mean()), zones_95pct_in_one_tract=float(100 * (zp.dropna() >= .95).mean()))
pd.Series(geo_meta).to_csv(f"{D}/geography_summary.csv", header=["value"])
pd.DataFrame({"tract": TC.index, "cluster": TC.values}).to_csv(f"{D}/crosswalk_tract2020_cluster.csv", index=False)
pd.DataFrame({"zone": ZC.index, "cluster": ZC.values}).to_csv(f"{D}/crosswalk_zone_cluster.csv", index=False)

# ------------------------------------------------------------------ model data
sz = pd.read_parquet(f"{C}/silo_zone.parquet")
def silo(var, year):
    x = sz[(sz["var"] == var) & (sz.year == year)]
    if year == 2016: return x.groupby("zone").value.sum().rename(0).to_frame()
    return x.pivot_table(index="zone", columns="seed", values="value", aggfunc="sum")
def to_units(Mz, unit):                       # zone frame -> zone (Z6) or cluster frame
    Mz = Mz.reindex(Z6).fillna(0)
    return Mz if unit == "zone" else Mz.groupby(ZC.reindex(Mz.index).values).sum()

# ------------------------------------------------------------------ ACS
def acs(ds, table):
    fr = []
    for f in sorted(glob.glob(f"{RAW}/acs_tract/{ds}_{table}_*.json")):
        d = json.load(open(f))["response"]["data"]; x = pd.DataFrame(d[1:], columns=d[0]); fr.append(x)
    x = pd.concat(fr); x.index = x.GEO_ID.str[-11:]
    cols = [c for c in x.columns if c.startswith(table) and (c.endswith("E") or c.endswith("M"))]
    x = x[cols].apply(pd.to_numeric, errors="coerce")
    x[x < -1e5] = np.nan                          # jam values (-666666666 etc.)
    return x
def E(x, *ids): return sum(x[f"{x.columns[0].split('_')[0]}_{i:03d}E"].fillna(0) for i in ids)
def MO(x, *ids): return np.sqrt(sum(x[f"{x.columns[0].split('_')[0]}_{i:03d}M"].fillna(0) ** 2 for i in ids))
def tcl(s, how="sum"):                        # tract series -> cluster
    s = s.reindex(TC.index).fillna(0)
    return s.groupby(TC.values).sum() if how == "sum" else np.sqrt((s ** 2).groupby(TC.values).sum())
def share_moe(X, MX, Y, MY):
    p = X / Y; rad = MX ** 2 - p ** 2 * MY ** 2; rad = np.where(rad < 0, MX ** 2 + p ** 2 * MY ** 2, rad); return p, np.sqrt(rad) / Y

# =================================================================== A1  2020 population and households vs Census 2020
for unit in ["zone", "cluster"]:
    ob = b20.groupby("zone")[["hu_occ", "hhpop", "pop"]].sum().reindex(Z6).fillna(0)
    if unit == "cluster": ob = b20.assign(c=b20.tract.map(TC)).groupby("c")[["hu_occ", "hhpop", "pop"]].sum()
    Mh = to_units(silo("households", 2020), unit); Mp = to_units(silo("persons", 2020), unit)
    k = ob.index[(ob.hu_occ > 0)]
    level_block("A1 2020 vs Census 2020", "households", unit, Mh.reindex(k), ob.hu_occ.reindex(k))
    level_block("A1 2020 vs Census 2020", "household population", unit, Mp.reindex(k), ob.hhpop.reindex(k))
    out = pd.DataFrame({"census_households": ob.hu_occ, "model_households_mean": Mh.mean(axis=1), "model_households_min": Mh.min(axis=1), "model_households_max": Mh.max(axis=1),
                        "census_household_pop": ob.hhpop, "census_total_pop": ob["pop"], "model_persons_mean": Mp.mean(axis=1), "model_persons_min": Mp.min(axis=1), "model_persons_max": Mp.max(axis=1)})
    out["ratio_households"] = out.model_households_mean / out.census_households; out["ratio_persons"] = out.model_persons_mean / out.census_household_pop
    out.index.name = unit; out.to_csv(f"{D}/a1_{unit}.csv")
# base 2016 for reference: how much of the 2020 zone pattern is already in the base (placed by Census 2010/2020-interpolated weights)
ob = b20.groupby("zone").hu_occ.sum().reindex(Z6).fillna(0); k = ob.index[ob > 0]
level_block("A1 reference: 2016 base vs Census 2020", "households", "zone", silo("households", 2016).reindex(Z6).fillna(0).reindex(k), ob.reindex(k), "base placed with Census 2010/2020 block-interpolated zone weights")

# =================================================================== A2  2024 composition vs ACS 2020-24 (clusters)
y = 2024
hh = acs("ACSDT5Y2024", "B11001"); hp = acs("ACSDT5Y2024", "B25008"); veh = acs("ACSDT5Y2024", "B25044"); inc = acs("ACSDT5Y2024", "B19001")
med = acs("ACSDT5Y2024", "B19013"); bld = acs("ACSDT5Y2024", "B25032")
OH, OHm = tcl(E(hh, 1)), tcl(MO(hh, 1), "moe"); OP, OPm = tcl(E(hp, 1)), tcl(MO(hp, 1), "moe")
MH = to_units(silo("households", y), "cluster"); MP = to_units(silo("persons", y), "cluster")
k = OH.index[OH > 0]
level_block("A2 2024 vs ACS 2020-24", "households", "cluster", MH.reindex(k), OH.reindex(k))
level_block("A2 2024 vs ACS 2020-24", "household population", "cluster", MP.reindex(k), OP.reindex(k))
add("A2 2024 vs ACS 2020-24", "households", "cluster", len(k), "within ACS 90% MOE (% of units)", lambda m, o: 100 * np.mean(np.abs(m - o) <= OHm.reindex(k).values), MH.reindex(k), OH.reindex(k))
add("A2 2024 vs ACS 2020-24", "household population", "cluster", len(k), "within ACS 90% MOE (% of units)", lambda m, o: 100 * np.mean(np.abs(m - o) <= OPm.reindex(k).values), MP.reindex(k), OP.reindex(k))
a2 = pd.DataFrame({"acs_households": OH, "acs_households_moe": OHm, "model_households": MH.mean(axis=1), "acs_hhpop": OP, "acs_hhpop_moe": OPm, "model_persons": MP.mean(axis=1)})
# cars: zero-car share and mean cars (3+ top-coded on both sides)
vz = tcl(E(veh, 3, 10)); vzm = tcl(MO(veh, 3, 10), "moe"); vt = tcl(E(veh, 1)); vtm = tcl(MO(veh, 1), "moe")
p0, p0m = share_moe(vz, vzm, vt, vtm)
cars_obs = (tcl(E(veh, 4, 11)) + 2 * tcl(E(veh, 5, 12)) + 3 * tcl(E(veh, 6, 7, 8, 13, 14, 15))) / vt
A = {a: to_units(silo(f"autos{a}", y), "cluster") for a in range(4)}; At = sum(A.values())
m0 = A[0] / At; mc = (A[1] + 2 * A[2] + 3 * A[3]) / At
k = vt.index[vt > 0]
add("A2 2024 vs ACS 2020-24", "zero-car share", "cluster", len(k), "R2", r2, m0.reindex(k), p0.reindex(k))
add("A2 2024 vs ACS 2020-24", "zero-car share", "cluster", len(k), "mean abs diff (pp)", lambda m, o: 100 * np.mean(np.abs(m - o)), m0.reindex(k), p0.reindex(k))
add("A2 2024 vs ACS 2020-24", "zero-car share", "cluster", len(k), "within ACS 90% MOE (% of units)", lambda m, o: 100 * np.mean(np.abs(m - o) <= p0m.reindex(k).values), m0.reindex(k), p0.reindex(k))
add("A2 2024 vs ACS 2020-24", "zero-car share", "cluster", len(k), "region share model/observed", lambda m, o: (m * At.mean(axis=1).reindex(k).values).sum() / At.mean(axis=1).reindex(k).sum() / ((o * vt.reindex(k).values).sum() / vt.reindex(k).sum()), m0.reindex(k), p0.reindex(k))
add("A2 2024 vs ACS 2020-24", "cars per household (3+ = 3)", "cluster", len(k), "R2", r2, mc.reindex(k), cars_obs.reindex(k))
add("A2 2024 vs ACS 2020-24", "cars per household (3+ = 3)", "cluster", len(k), "MAPE %", lambda m, o: 100 * np.mean(np.abs(m - o) / o), mc.reindex(k), cars_obs.reindex(k))
add("A2 2024 vs ACS 2020-24", "cars per household (3+ = 3)", "cluster", len(k), "within +-10 % (% of units)", lambda m, o: within(m, o, .10), mc.reindex(k), cars_obs.reindex(k))
a2["acs_zero_car_share"] = p0; a2["acs_zero_car_moe"] = p0m; a2["model_zero_car_share"] = m0.mean(axis=1); a2["acs_cars_per_hh"] = cars_obs; a2["model_cars_per_hh"] = mc.mean(axis=1)
# income bands (2024 $; model 2016 $ x CPI 1.307) and median
ib_obs_ids = [[2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12], [13], [14, 15], [16], [17]]   # <25k, 25-50k, 50-75k, 75-100k, 100-150k, 150-200k, 200k+
IO = pd.DataFrame({l: tcl(E(inc, *ids)) for l, ids in zip(INC_LAB, ib_obs_ids)}); IOm = pd.DataFrame({l: tcl(MO(inc, *ids), "moe") for l, ids in zip(INC_LAB, ib_obs_ids)})
IT, ITm = tcl(E(inc, 1)), tcl(MO(inc, 1), "moe")
ih = sz[(sz.year == y) & sz["var"].str.startswith("inc_b")].copy(); ih["b"] = ih["var"].str[5:].astype(int)
ih["band"] = pd.cut(ih.b * 2500 + 1, INC_EDGES, right=False, labels=INC_LAB); ih["cl"] = ih.zone.map(ZC)
IM = {s: ih[ih.seed == s].pivot_table(index="cl", columns="band", values="value", aggfunc="sum", observed=False).reindex(columns=INC_LAB).fillna(0) for s in sorted(ih.seed.unique())}
k = IT.index[IT > 0]
IMm = sum(IM.values()) / len(IM)
tv_mean = pd.Series([tvd(IMm.reindex(k).fillna(0).loc[c].values + 1e-12, IO.loc[c].values) for c in k], index=k)
w = IT.reindex(k)
add1("A2 2024 vs ACS 2020-24", "income bands (7, 2024 $)", "cluster", len(k), "household-weighted mean TVD per unit (pp)", (tv_mean * w).sum() / w.sum())
add1("A2 2024 vs ACS 2020-24", "income bands (7, 2024 $)", "cluster", len(k), "median TVD per unit (pp)", tv_mean.median())
add1("A2 2024 vs ACS 2020-24", "income bands (7, 2024 $)", "region", 1, "TVD of region distribution (pp)", tvd(IMm.reindex(k).sum().values, IO.loc[k].sum().values))
inwin = []
for l in INC_LAB:
    ps_m = IMm.reindex(k)[l] / IMm.reindex(k).sum(axis=1); po, pm = share_moe(IO.loc[k, l], IOm.loc[k, l], IT.reindex(k), ITm.reindex(k))
    add1("A2 2024 vs ACS 2020-24", f"income share {l}", "cluster", len(k), "R2", r2(ps_m.fillna(0), po)); inwin.append(np.abs(ps_m - po) <= pm)
    add1("A2 2024 vs ACS 2020-24", f"income share {l}", "cluster", len(k), "region share model - observed (pp)", 100 * (IMm.reindex(k)[l].sum() / IMm.reindex(k).values.sum() - IO.loc[k, l].sum() / IO.loc[k].values.sum()))
add1("A2 2024 vs ACS 2020-24", "income bands (7, 2024 $)", "cluster", len(k), "band shares within ACS 90% MOE (% of unit-bands)", 100 * np.mean(np.concatenate([x.values for x in inwin])))
EDG = [0, 10e3, 15e3, 20e3, 25e3, 30e3, 35e3, 40e3, 45e3, 50e3, 60e3, 75e3, 100e3, 125e3, 150e3, 200e3, 400e3]
def interp_median(counts, edges):
    c = np.cumsum(counts); h = c[-1] / 2; i = int(np.searchsorted(c, h)); lo = c[i - 1] if i else 0
    return edges[i] + (edges[i + 1] - edges[i]) * (h - lo) / max(counts[i], 1e-9)
OB = pd.DataFrame({j: tcl(E(inc, j)) for j in range(2, 18)})
obs_med = pd.Series([interp_median(OB.loc[c].values, EDG) for c in k], index=k)
mm = {}
for s in sorted(ih.seed.unique()):
    H = ih[ih.seed == s].pivot_table(index="cl", columns="b", values="value", aggfunc="sum").reindex(columns=range(200)).fillna(0)
    mm[s] = pd.Series([interp_median(H.loc[c].values, np.arange(201) * 2500.0) if c in H.index else np.nan for c in k], index=k)
MM = pd.DataFrame(mm)
add("A2 2024 vs ACS 2020-24", "median household income (2024 $)", "cluster", len(k), "R2", r2, MM, obs_med)
add("A2 2024 vs ACS 2020-24", "median household income (2024 $)", "cluster", len(k), "MAPE %", lambda m, o: 100 * np.mean(np.abs(m - o) / o), MM, obs_med)
add("A2 2024 vs ACS 2020-24", "median household income (2024 $)", "cluster", len(k), "median of model/observed", lambda m, o: np.median(m / o), MM, obs_med)
# single-tract clusters: published median and its MOE
one_cl = TC.value_counts(); one_cl = one_cl.index[one_cl == 1]; t1 = TC[TC.isin(one_cl)]
pm_ = pd.Series(med["B19013_001E"].reindex(t1.index).values, index=t1.values); pmm = pd.Series(med["B19013_001M"].reindex(t1.index).values, index=t1.values)
kk = pm_.dropna().index.intersection(MM.index)
add("A2 2024 vs ACS 2020-24", "median household income (2024 $), single-tract clusters vs published B19013", "cluster", len(kk), "within ACS 90% MOE (% of units)",
    lambda m, o: 100 * np.mean(np.abs(m - o) <= pmm.reindex(kk).values), MM.reindex(kk), pm_.reindex(kk))
a2["acs_median_income_interp"] = obs_med; a2["model_median_income"] = MM.mean(axis=1); a2["income_tvd_pp"] = tv_mean
# dwelling type of occupied units
dw_ids = {"SFD": [3, 14], "SFA": [4, 15], "MF234": [5, 6, 16, 17], "MF5plus": [7, 8, 9, 10, 18, 19, 20, 21], "MH": [11, 12, 22, 23]}
DO = pd.DataFrame({t: tcl(E(bld, *ids)) for t, ids in dw_ids.items()}); DOm = pd.DataFrame({t: tcl(MO(bld, *ids), "moe") for t, ids in dw_ids.items()})
DT, DTm = tcl(E(bld, 1)), tcl(MO(bld, 1), "moe")
DMs = {t: to_units(silo(f"dw_{t}", y), "cluster") for t in DW}
DMm = pd.DataFrame({t: DMs[t].mean(axis=1) for t in DW})
k = DT.index[DT > 0]
tvd_dw = pd.Series([tvd(DMm.reindex(k).fillna(0).loc[c].values + 1e-12, DO.loc[c].values) for c in k], index=k)
add1("A2 2024 vs ACS 2020-24", "dwelling type of occupied units (5)", "cluster", len(k), "household-weighted mean TVD per unit (pp)", (tvd_dw * DT.reindex(k)).sum() / DT.reindex(k).sum())
add1("A2 2024 vs ACS 2020-24", "dwelling type of occupied units (5)", "cluster", len(k), "median TVD per unit (pp)", tvd_dw.median())
add1("A2 2024 vs ACS 2020-24", "dwelling type of occupied units (5)", "region", 1, "TVD of region distribution (pp)", tvd(DMm.reindex(k).sum().values, DO.loc[k].sum().values))
inwin = []
for t in DW:
    sm = DMm.reindex(k)[t] / DMm.reindex(k).sum(axis=1); po, pm = share_moe(DO.loc[k, t], DOm.loc[k, t], DT.reindex(k), DTm.reindex(k))
    add1("A2 2024 vs ACS 2020-24", f"dwelling share {t}", "cluster", len(k), "R2", r2(sm.fillna(0), po)); inwin.append(np.abs(sm - po) <= pm)
    add1("A2 2024 vs ACS 2020-24", f"dwelling share {t}", "cluster", len(k), "region share model - observed (pp)", 100 * (DMm.reindex(k)[t].sum() / DMm.reindex(k).values.sum() - DO.loc[k, t].sum() / DO.loc[k].values.sum()))
    a2[f"acs_share_{t}"] = DO[t] / DT; a2[f"model_share_{t}"] = DMm[t] / DMm.sum(axis=1)
add1("A2 2024 vs ACS 2020-24", "dwelling type of occupied units (5)", "cluster", len(k), "type shares within ACS 90% MOE (% of unit-types)", 100 * np.mean(np.concatenate([x.values for x in inwin])))
a2["dwelling_tvd_pp"] = tvd_dw
for l in INC_LAB: a2[f"acs_share_inc_{l}"] = IO[l] / IT; a2[f"model_share_inc_{l}"] = IMm[l] / IMm.sum(axis=1)
a2.index.name = "cluster"; a2.to_csv(f"{D}/a2_cluster.csv")

# ---- A2 diagnostics: (i) the 2016 base against the same 2020-24 targets (what SILO inherited), (ii) a PUMA-uniform benchmark
# (every cluster given its PUMA's observed share: the spatial detail a population placed within PUMAs by counts only can carry)
CLP = b20.assign(cl=b20.tract.map(TC), p=b20.zone.map(DIST)).groupby(["cl", "p"]).hu_occ.sum().reset_index().sort_values("hu_occ").drop_duplicates("cl", keep="last").set_index("cl").p
def puma_bench(X, Y):
    k_ = Y.index[Y > 0]; pX = X.reindex(k_).groupby(CLP.reindex(k_).values).sum(); pY = Y.reindex(k_).groupby(CLP.reindex(k_).values).sum()
    return pd.Series((pX / pY).reindex(CLP.reindex(k_).values).values, index=k_)
A16 = {a: to_units(silo(f"autos{a}", 2016), "cluster")[0] for a in range(4)}; At16 = sum(A16.values())
D16 = pd.DataFrame({t: to_units(silo(f"dw_{t}", 2016), "cluster")[0] for t in DW})
_b = pd.read_csv(f"{V}/2_silo/run/base/{SILO_BASE}/hh_2016.csv", usecols=["dwelling", "income"]); _d = pd.read_csv(f"{V}/2_silo/run/base/{SILO_BASE}/dd_2016.csv", usecols=["id", "zone"])
_b = _b.merge(_d.rename(columns={"id": "dwelling"}), on="dwelling"); _b = _b[_b.zone.isin(Z6)]; _b["cl"] = _b.zone.map(ZC)
med16 = _b.groupby("cl").income.median() * 1.307
kv = vt.index[vt > 0]; kd = DT.index[DT > 0]; ki = IT.index[IT > 0]
diag = [("zero-car share", m0.mean(axis=1), A16[0] / At16, puma_bench(vz, vt), p0, kv),
        ("cars per household (3+ = 3)", mc.mean(axis=1), (A16[1] + 2 * A16[2] + 3 * A16[3]) / At16,
         puma_bench(tcl(E(veh, 4, 11)) + 2 * tcl(E(veh, 5, 12)) + 3 * tcl(E(veh, 6, 7, 8, 13, 14, 15)), vt), cars_obs, kv)]
for t in ["SFD", "SFA", "MF5plus"]: diag.append((f"dwelling share {t}", DMm[t] / DMm.sum(axis=1), D16[t] / D16.sum(axis=1), puma_bench(DO[t], DT), DO[t] / DT, kd))
for l in ["<25k", "200k+"]: diag.append((f"income share {l}", IMm[l] / IMm.sum(axis=1), None, puma_bench(IO[l], IT), IO[l] / IT, ki))
diag.append(("median household income (2024 $)", MM.mean(axis=1), med16, None, obs_med, ki))
for nm, m24, m16, pb, o, kk_ in diag:
    add1("A2 diagnostic", nm, "cluster", len(kk_), "R2, model 2024 (seed mean)", r2(m24.reindex(kk_).fillna(0), o.reindex(kk_)))
    if m16 is not None: add1("A2 diagnostic", nm, "cluster", len(kk_), "R2, 2016 base", r2(m16.reindex(kk_).fillna(0), o.reindex(kk_)))
    if pb is not None: add1("A2 diagnostic", nm, "cluster", len(kk_), "R2, PUMA-uniform benchmark (observed PUMA share)", r2(pb.reindex(kk_), o.reindex(kk_)))

# =================================================================== A3  change 2016 -> 2024
# (a) clusters: SILO 2016 base -> 2024 vs ACS 2012-16 -> 2020-24 households (B11001); 2010 tracts split to zones by 2010 blocks
h16 = acs("ACSDT5Y2016", "B11001"); e16, m16 = E(h16, 1), MO(h16, 1)
sh10 = b10.groupby(["tract10", "zone"]).hu_occ10.sum(); sh10 = sh10 / sh10.groupby(level=0).transform("sum")
sh10 = sh10.reset_index(); sh10["cl"] = sh10.zone.map(ZC); sh10 = sh10.groupby(["tract10", "cl"]).hu_occ10.sum().reset_index()
sh10.columns = ["tract10", "cl", "w"]
O16 = (sh10.w * sh10.tract10.map(e16).fillna(0)).groupby(sh10.cl).sum(); O16m = np.sqrt(((sh10.w * sh10.tract10.map(m16).fillna(0)) ** 2).groupby(sh10.cl).sum())
dO = (OH - O16).dropna(); dOm = np.sqrt(OHm ** 2 + O16m ** 2).reindex(dO.index)
M16 = to_units(silo("households", 2016), "cluster")[0]; dM = MH.sub(M16, axis=0).reindex(dO.index)
k = dO.index
add("A3 change 2016->2024", "households, change", "cluster", len(k), "R2", r2, dM, dO, "ACS 2012-16 -> 2020-24 (5-year windows centred 2014 / 2022)")
add("A3 change 2016->2024", "households, change", "cluster", len(k), "same sign (% of units)", lambda m, o: 100 * np.mean(np.sign(m) == np.sign(o)), dM, dO)
add("A3 change 2016->2024", "households, change", "cluster", len(k), "within MOE of the ACS change (% of units)", lambda m, o: 100 * np.mean(np.abs(m - o) <= dOm.values), dM, dO)
add("A3 change 2016->2024", "households, change", "cluster", len(k), "sum model / sum observed", lambda m, o: m.sum() / o.sum(), dM, dO)
add1("A3 change 2016->2024", "households, change", "cluster", len(k), "ACS change exceeds its own MOE (% of units)", 100 * np.mean(np.abs(dO) > dOm))
pd.DataFrame({"acs_2012_16": O16, "acs_2012_16_moe": O16m, "acs_2020_24": OH, "acs_change": dO, "acs_change_moe": dOm, "model_2016": M16, "model_2024_mean": MH.mean(axis=1),
              "model_change_mean": dM.mean(axis=1), "model_change_min": dM.min(axis=1), "model_change_max": dM.max(axis=1)}).rename_axis("cluster").to_csv(f"{D}/a3_cluster_change.csv")
# (b) zones, block-exact: SILO 2016 -> 2020 vs the Census 2010 -> 2020 change x 0.4 (the base is the 0.6 interpolation)
c10 = b10.groupby("zone").hu_occ10.sum().reindex(Z6).fillna(0); c20 = b20.groupby("zone").hu_occ.sum().reindex(Z6).fillna(0)
dC = 0.4 * (c20 - c10); dMz = silo("households", 2020).reindex(Z6).fillna(0).sub(silo("households", 2016).reindex(Z6).fillna(0)[0], axis=0)
add("A3 change 2016->2020", "households, change", "zone", len(Z6), "R2", r2, dMz, dC, "observed = 0.4 x Census 2010->2020 change (block-exact)")
add("A3 change 2016->2020", "households, change", "zone", len(Z6), "same sign (% of units)", lambda m, o: 100 * np.mean(np.sign(m) == np.sign(o)), dMz, dC)
add("A3 change 2016->2020", "households, change", "zone", len(Z6), "share of growth in the top-decile growth zones, model/observed", lambda m, o: m[o >= np.quantile(o, .9)].sum() / o[o >= np.quantile(o, .9)].sum(), dMz, dC)
pd.DataFrame({"census_2010_occ": c10, "census_2020_occ": c20, "census_change_x0.4": dC, "model_change_2016_2020_mean": dMz.mean(axis=1)}).rename_axis("zone").to_csv(f"{D}/a3_zone_change.csv")
# (c) counties: new dwellings (ids above the base maximum, built in 2016-2023) vs permits 2016-2023 (BPS, units of all structure types)
perm = {}
for yr in range(2016, 2024):
    b = pd.read_csv(f"{RAW}/bps/co{yr}a.txt", skiprows=3, header=None, dtype=str)
    b = b[(b[1] == "24")]; b["fips"] = (b[1] + b[2]).astype(int); b["units"] = b[[7, 10, 13, 16]].astype(int).sum(axis=1)
    perm[yr] = b.set_index("fips").units
perm = pd.DataFrame(perm).reindex(CTY); nd = silo("new_dwellings", 2024); nd = nd.groupby(ZS.COUNTYFIPS.reindex(nd.index).values).sum().reindex(CTY)
a3c = pd.DataFrame({"permits_2016_2023": perm.sum(axis=1), "model_new_dwellings_mean": nd.mean(axis=1), "model_min": nd.min(axis=1), "model_max": nd.max(axis=1)})
a3c["ratio"] = a3c.model_new_dwellings_mean / a3c.permits_2016_2023; a3c.rename_axis("county").to_csv(f"{D}/a3_county_permits.csv")
add("A3 new dwellings vs permits", "units 2016-2023", "county", 6, "MAPE %", lambda m, o: 100 * np.mean(np.abs(m - o) / o), nd, a3c.permits_2016_2023, "imposed: county construction calibrated to permits")
add("A3 new dwellings vs permits", "units 2016-2023", "county", 6, "total ratio model/observed", lambda m, o: m.sum() / o.sum(), nd, a3c.permits_2016_2023)

# =================================================================== LODES
def wac(yr, st="md"):
    w = pd.read_csv(f"{RAW}/lodes_wac/{st}_wac_S000_JT00_{yr}.csv.gz", dtype={"w_geocode": str}, usecols=lambda c: c == "w_geocode" or c == "C000" or c.startswith("CNS"))
    w["zone"] = w.w_geocode.map(lbz.set_index("block").zone); return w[w.zone.isin(Z6)].groupby("zone").sum(numeric_only=True).reindex(Z6).fillna(0)
W22, W16 = wac(2022), wac(2016)
# =================================================================== A4  jobs 2022 vs LODES WAC 2022 (zones, block-exact)
J22 = silo("jobs", 2022).reindex(Z6).fillna(0); F22 = silo("jobs_filled", 2022).reindex(Z6).fillna(0)
k = W22.index[W22.C000 > 0]
level_block("A4 jobs 2022 vs LODES 2022", "SILO jobs (filled + vacant)", "zone", J22.reindex(k), W22.C000.reindex(k), "imposed: zone x type job controls = 2016 base share x LODES change")
level_block("A4 jobs 2022 vs LODES 2022", "SILO filled jobs", "zone", F22.reindex(k), W22.C000.reindex(k))
add("A4 jobs 2022 vs LODES 2022", "SILO filled jobs", "zone", len(k), "TVD of zone shares (pp)", tvd, F22.reindex(k), W22.C000.reindex(k))
dJ = F22.sub(silo("jobs_filled", 2016).reindex(Z6).fillna(0)[0], axis=0); dW = W22.C000 - W16.C000
add("A4 jobs 2022 vs LODES 2022", "filled jobs, change 2016->2022", "zone", len(Z6), "R2", r2, dJ, dW)
pd.DataFrame({"lodes_2016": W16.C000, "lodes_2022": W22.C000, "silo_jobs_2022": J22.mean(axis=1), "silo_filled_2022": F22.mean(axis=1), "silo_filled_2016": silo("jobs_filled", 2016).reindex(Z6).fillna(0)[0]}).rename_axis("zone").to_csv(f"{D}/a4_zone_jobs.csv")

# =================================================================== B1/B2  ABIT destinations (zones in the study area), shares
ad = pd.read_parquet(f"{C}/abit_dest.parquet")
def abit(purpose, col="activities"):
    x = ad[ad.purpose == purpose].pivot_table(index="zone", columns="rep", values=col, aggfunc="sum"); return x.reindex(Z6).fillna(0)
Fsh = F22.copy()
F24 = silo("jobs_filled", 2024).reindex(Z6).fillna(0); R24 = silo("jobs_RET", 2024).reindex(Z6).fillna(0)
HH24 = silo("households", 2024).reindex(Z6).fillna(0)
b_out = pd.DataFrame(index=Z6)
def share_block(check, var, Mdf, o, note=""):
    n = len(o)
    add(check, var, "zone", n, "TVD of zone shares (pp)", tvd, Mdf, o, note)
    add(check, var, "zone", n, "R2 of shares", lambda m, o: r2(m / m.sum(), o / o.sum()), Mdf, o, note)
    add(check, var, "zone", n, "R2 of shares (log)", lambda m, o: r2log(m / m.sum(), o / o.sum()), Mdf, o, note)
    add(check, var, "zone", n, "coincidence ratio of shares", cr, Mdf, o, note)
    od = Mdf.groupby(DIST.reindex(Mdf.index).values).sum(); oo = o.groupby(DIST.reindex(o.index).values).sum()
    add(check, var, "district (21 PUMA)", len(oo), "TVD of district shares (pp)", tvd, od, oo, note)
    add(check, var, "district (21 PUMA)", len(oo), "R2 of shares", lambda m, o: r2(m / m.sum(), o / o.sum()), od, oo, note)
WK = abit("WORK", "persons")
share_block("B1 work attraction vs LODES WAC 2022 C000", "ABIT workers arriving at work (2024)", WK, W22.C000, "LODES counts jobs, ABIT daily attendance: shares compared")
share_block("B1 work attraction vs LODES WAC 2022 C000", "SILO filled jobs 2024 (ABIT workplace input)", F24, W22.C000)
share_block("B1 ABIT vs its own input", "ABIT workers arriving at work vs SILO filled jobs 2024 (seed 5)", WK, F24[5])
b_out["lodes_C000"] = W22.C000; b_out["abit_work_persons"] = WK.mean(axis=1); b_out["silo_filled_2024"] = F24.mean(axis=1)
SECT = {"SHOPPING": ("retail + accommodation/food jobs (CNS07+CNS18)", W22.CNS07 + W22.CNS18),
        "RECREATION": ("arts/recreation + accommodation/food jobs (CNS17+CNS18)", W22.CNS17 + W22.CNS18),
        "OTHER": ("health + other services + public administration + finance jobs (CNS16+CNS19+CNS20+CNS10)", W22.CNS16 + W22.CNS19 + W22.CNS20 + W22.CNS10)}
for p, (lab, o) in SECT.items():
    A_ = abit(p)
    share_block(f"B2 {p.lower()} attraction vs LODES WAC 2022", f"ABIT {p.lower()} activities vs {lab}", A_, o)
    share_block(f"B2 {p.lower()} attraction (reference predictors)", f"LODES all jobs C000 as predictor of {lab}", pd.DataFrame({0: W22.C000}), o)
    b_out[f"abit_{p.lower()}"] = A_.mean(axis=1); b_out[f"lodes_{p.lower()}_sectors"] = o
share_block("B2 shopping attraction (reference predictors)", "ABIT shopping activities vs SILO retail jobs 2024 (its size variable)", abit("SHOPPING"), R24[5])
share_block("B2 recreation attraction (reference predictors)", "ABIT recreation vs households 2024", abit("RECREATION"), HH24[5])
share_block("B2 other attraction (reference predictors)", "ABIT other vs households 2024", abit("OTHER"), HH24[5])
b_out.rename_axis("zone").to_csv(f"{D}/b12_zone_attraction.csv")

# =================================================================== B3  home -> work flows
SK = pd.read_csv(f"{V}/3_abit/skims/distance_auto.csv.gz"); SK = SK[SK.FROM.isin(Z6) & SK.TO.isin(Z6)].set_index(["FROM", "TO"]).VALUE / 1000
def od_lodes(jt):
    o = pd.read_csv(f"{RAW}/lodes_od/md_od_main_{jt}_2022.csv.gz", usecols=["w_geocode", "h_geocode", "S000"], dtype={"w_geocode": str, "h_geocode": str})
    bz = lbz.set_index("block").zone; o["hzone"] = o.h_geocode.map(bz); o["wzone"] = o.w_geocode.map(bz)
    o = o[o.hzone.isin(Z6) & o.wzone.isin(Z6)]; return o.groupby(["hzone", "wzone"]).S000.sum()
LO = {"JT00": od_lodes("JT00"), "JT01": od_lodes("JT01")}
sf = pd.read_parquet(f"{C}/silo_flows.parquet"); sf = sf[sf.hzone.isin(Z6) & sf.wzone.isin(Z6)].pivot_table(index=["hzone", "wzone"], columns="seed", values="workers", aggfunc="sum")
af = pd.read_parquet(f"{C}/abit_flows.parquet"); af = af[af.hzone.isin(Z6) & af.wzone.isin(Z6)].pivot_table(index=["hzone", "wzone"], columns="rep", values="workers", aggfunc="sum")
idx = sf.index.union(af.index).union(LO["JT00"].index).union(LO["JT01"].index)
sf, af = sf.reindex(idx).fillna(0), af.reindex(idx).fillna(0); LJ0, LJ1 = LO["JT00"].reindex(idx).fillna(0), LO["JT01"].reindex(idx).fillna(0)
dist = SK.reindex(idx); h_ = idx.get_level_values(0); w_ = idx.get_level_values(1)
dh, dw = DIST.reindex(h_).values, DIST.reindex(w_).values
tl_rows = []
for nm, Mdf in [("SILO home-work (2024)", sf), ("ABIT work trips (2024)", af)]:
    for jt, o in [("JT00", LJ0), ("JT01", LJ1)]:
        chk = f"B3 home-work flows vs LODES OD 2022 {jt}"
        add(chk, nm, "zone pair", len(o), "intrazonal share model - observed (pp)", lambda m, o: 100 * (m[h_ == w_].sum() / m.sum() - o[h_ == w_].sum() / o.sum()), Mdf, o)
        add(chk, nm, "zone pair", len(o), "TVD of OD shares (pp)", tvd, Mdf, o)
        add(chk, nm, "zone pair", len(o), "R2 of OD shares", lambda m, o: r2(m / m.sum(), o / o.sum()), Mdf, o)
        D_m = Mdf.groupby([dh, dw]).sum(); D_o = o.groupby([dh, dw]).sum()
        add(chk, nm, "district pair (21x21)", len(D_o), "R2 of OD shares", lambda m, o: r2(m / m.sum(), o / o.sum()), D_m, D_o)
        add(chk, nm, "district pair (21x21)", len(D_o), "R2 of OD shares (log)", lambda m, o: r2log(m / m.sum(), o / o.sum()), D_m, D_o)
        add(chk, nm, "district pair (21x21)", len(D_o), "TVD of OD shares (pp)", tvd, D_m, D_o)
        ii = D_o.index.get_level_values(0) == D_o.index.get_level_values(1)
        add(chk, nm, "district pair (21x21)", len(D_o), "intra-district share model - observed (pp)", lambda m, o: 100 * (m[ii].sum() / m.sum() - o[ii].sum() / o.sum()), D_m, D_o)
        hist = lambda x: np.histogram(dist.values, bins=TL_EDGES, weights=x)[0]
        add(chk, nm, "zone pair", len(o), "coincidence ratio of trip-length distribution", lambda m, o: cr(hist(m), hist(o)), Mdf, o, "car skim distance, bins 0-2-5-10-15-20-30-40-60+ km")
        add(chk, nm, "zone pair", len(o), "TVD of trip-length distribution (pp)", lambda m, o: tvd(hist(m), hist(o)), Mdf, o)
        add(chk, nm, "zone pair", len(o), "mean commute distance model/observed", lambda m, o: (m * dist.values).sum() / m.sum() / ((o * dist.values).sum() / o.sum()), Mdf, o)
for nm, x in [("LODES JT00", LJ0), ("LODES JT01", LJ1), ("SILO", sf.mean(axis=1)), ("ABIT", af.mean(axis=1))]:
    hh_ = np.histogram(dist.values, bins=TL_EDGES, weights=x.values)[0]
    tl_rows.append(dict(source=nm, mean_km=(x.values * dist.values).sum() / x.sum(), intrazonal_pct=100 * x[h_ == w_].sum() / x.sum(),
                        intradistrict_pct=100 * x[dh == dw].sum() / x.sum(), total=x.sum(), **{f"share_{TL_EDGES[i]}_{TL_EDGES[i + 1]}km": 100 * hh_[i] / hh_.sum() for i in range(len(hh_))}))
pd.DataFrame(tl_rows).to_csv(f"{D}/b3_tlfd_summary.csv", index=False)
dd_ = pd.DataFrame({"lodes_JT00": LJ0.groupby([dh, dw]).sum(), "lodes_JT01": LJ1.groupby([dh, dw]).sum(), "silo_mean": sf.mean(axis=1).groupby([dh, dw]).sum(),
                    "silo_min": sf.groupby([dh, dw]).sum().min(axis=1), "silo_max": sf.groupby([dh, dw]).sum().max(axis=1), "abit_mean": af.mean(axis=1).groupby([dh, dw]).sum()})
dd_.index.names = ["home_district", "work_district"]; dd_.to_csv(f"{D}/b3_district_od.csv")

ms = pd.DataFrame(M); ms.to_csv(f"{D}/metrics_summary.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_rows", 500)
print(pd.Series(geo_meta).to_string()); print(ms.drop(columns=["note"]).to_string())
