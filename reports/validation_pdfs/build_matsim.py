#!/usr/bin/env python3
"""Validation of the traffic assignment (stage 4, MATSim) against counts, screenlines, mileage, commute and survey data.

    python3 reports/validation_pdfs/build_matsim.py [--runs DIR ...] [--pop-log FILE] [--reuse] [--out PDF] [--work DIR]

--runs    the MATSim run folders, one per seed (default: the final runs pipeline/runs_respec/matsim/2024_s1 ... 2024_s5, absolute paths).
          Each needs the final link statistics (ITERS/it.100) and its hourly link volumes (<run>/link_hours.csv.gz, or
          4_matsim/validation/data/link_hours[_respec]/link_hours_<name>.csv.gz, or the events file, from which they are extracted).
          The earlier runs stay reachable: --runs <V>/pipeline/runs/matsim/2024_s1 ... --work work/matsim
--pop-log the build log of the MATSim population (persons living inside and outside the region, activities on POIs)
--reuse   reuse the computed tables and figures of the work directory and only rebuild the document.
The comparison scripts of 4_matsim/validation are run on the given folders; all their output goes to the work directory.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, json, os, re, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import matsim_compute

ap = argparse.ArgumentParser()
ap.add_argument("--runs", nargs="+", default=[f"{V}/pipeline/runs_respec/matsim/2024_s{i}" for i in range(1, 6)])
ap.add_argument("--pop-log", default=f"{V}/pipeline/runs/matsim_pop/2024_respec/build.log")
ap.add_argument("--reuse", action="store_true")
ap.add_argument("--out", default=f"{OUTDIR}/matsim_validation.pdf")
ap.add_argument("--work", default=f"{OUTDIR}/work/matsim_respec")
a = ap.parse_args()
WORK = os.path.abspath(a.work)
O = matsim_compute.compute([os.path.abspath(r) for r in a.runs], WORK, reuse=a.reuse)
NS = len(O["seeds"]); CD = f"{O['counts']}/data"; RD = f"{O['regional']}/data"; RF = f"{O['regional']}/figures"
meta = json.load(open(f"{CD}/meta.json")); SUM = json.load(open(f"{RD}/summary.json"))
TS = pd.read_csv(f"{CD}/tables_over_seeds.csv"); CT = pd.read_csv(f"{CD}/counters_summary.csv"); SC = pd.read_csv(f"{CD}/scatter_stats.csv")
SL = pd.read_csv(f"{O['screen']}/data/screenline_table.csv"); TM = pd.read_csv(f"{O['tmas']}/data/tmas_summary.csv"); TH = pd.read_csv(f"{O['tmas']}/data/tmas_hourly.csv")
MS = pd.read_csv(f"{O['mode']}/data/mode_share.csv"); BO = pd.read_csv(f"{O['mode']}/data/mode_share_boardings.csv")
# diagnostics of the count comparison, coverage estimate and maps (matsim_compute.diagnostics)
DG = f"{O['diag']}/data"; DF = f"{O['diag']}/figures"
DJ = json.load(open(f"{DG}/diagnostics.json")); MA = pd.read_csv(f"{DG}/matching_audit.csv"); MRS = pd.read_csv(f"{DG}/matching_reasons.csv"); ZV = pd.read_csv(f"{DG}/stations_zero_volume.csv")
SG = pd.read_csv(f"{DG}/spatial_groups.csv"); MI = pd.read_csv(f"{DG}/morans_i.csv"); CQ = pd.read_csv(f"{DG}/count_quality.csv"); CQC = pd.read_csv(f"{DG}/count_quality_by_class.csv")
VG = pd.read_csv(f"{DG}/volume_groups_fdot.csv"); CE = pd.read_csv(f"{DG}/coverage_estimate.csv"); CSRC = json.load(open(f"{DG}/coverage_sources.json"))
CDD = pd.read_csv(f"{DG}/counters_direction_detail.csv", dtype={"station": str}); CPS = pd.read_csv(f"{DG}/counters_period_summary.csv"); TA = pd.read_csv(f"{DG}/transit_by_agency.csv")
CVS = pd.read_csv(f"{DG}/convergence_summary.csv"); LRG = pd.read_csv(f"{DG}/linkstats_iteration_range.csv"); SSP = pd.read_csv(f"{DG}/seed_spread_stations.csv")
CO = {24510: "Baltimore City", 24005: "Baltimore County", 24003: "Anne Arundel", 24027: "Howard", 24025: "Harford", 24013: "Carroll"}
doc = Doc("Validation of the traffic assignment", "Stage 4 of the Baltimore chain: MATSim", WORK)
words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}
nw = words.get(NS, str(NS))
F = TS[TS.table == "facility"]; allv = F[(F.group == "All classes") & (F.comparison == "all vehicles")].iloc[0]; allp = F[(F.group == "All classes") & (F.comparison == "passenger vehicles")].iloc[0]
nst = meta["use"]["mainline"]
def rng(lo, hi, d=3): return num(lo, d) + "--" + num(hi, d)

# ------------------------------------------------------------------ population and set-up
pop = dict(intra=np.nan, inflow=np.nan, outflow=np.nan, persons=np.nan, legs=np.nan, poi=np.nan)
if os.path.exists(a.pop_log):
    L = open(a.pop_log).read()
    m = re.search(r"person flow: \{'intra': (\d+), 'inflow': (\d+), 'outflow': (\d+)\}", L)
    if m: pop.update(intra=int(m.group(1)), inflow=int(m.group(2)), outflow=int(m.group(3)))
    m = re.search(r"MATSim population: ([\d,]+) persons, ([\d,]+) legs", L)
    if m: pop.update(persons=int(m.group(1).replace(",", "")), legs=int(m.group(2).replace(",", "")))
    m = re.search(r"POI placement: [\d,]+ of [\d,]+ non-home activities on a real POI \(([\d.]+)%\)", L)
    if m: pop["poi"] = float(m.group(1))
cfg = open(f"{os.path.abspath(a.runs[0])}/output_config.xml").read()
def par(name, after=None):
    t = cfg if after is None else cfg[cfg.index(after):]
    m = re.search(rf'name="{name}" value="([^"]+)"', t); return m.group(1) if m else "?"
def strat(name):
    m = re.search(rf'name="strategyName" value="{name}" />\s*<param name="subpopulation" value="[^"]*" />\s*<param name="weight" value="([^"]+)"', cfg); return m.group(1) if m else "?"
qsim = cfg[cfg.index('<module name="qsim"'):] if '<module name="qsim"' in cfg else cfg
flowcf, storcf = par("flowCapacityFactor", '<module name="qsim"'), par("storageCapacityFactor", '<module name="qsim"')
niter = par("lastIteration"); offinn = float(par("fractionOfIterationsToDisableInnovation")); mutr = float(par("mutationRange"))

doc.section("Data and targets")
doc.para(f"The assignment stage loads one weekday of activity chains onto the 2024 road network and the 2024 transit network. The persons are those of one replication of the activity model "
         f"whose day touches the six counties of the Baltimore region: {thousands(pop['persons'])} persons with {thousands(pop['legs'])} trips, a 10\\% sample whose volumes are scaled by ten. "
         f"{thousands(pop['intra'])} live in the region and travel only inside it, {thousands(pop['outflow'])} live in the region and also travel out, and {thousands(pop['inflow'])} "
         f"({100 * pop['inflow'] / pop['persons']:.0f}\\%) live elsewhere in the model area and travel into the region. Persons who only cross the region, visitors from outside the model area, "
         f"commercial vehicles and trucks are not in the model, so modelled volumes are expected to lie below the counts. Activities other than home are placed on points of interest of their type "
         f"({pop['poi']:.1f}\\% of them) inside the zone that the activity model chose.")
doc.para(f"Set-up. {niter} iterations; in each iteration 15\\% of the persons are rerouted, {100 * float(strat('TimeAllocationMutator')):.0f}\\% have their departure times shifted at random by up to "
         f"{mutr / 60:.0f} minutes (durations are kept), and the others choose among their plans. Shifting and rerouting stop after iteration {int(offinn * int(niter))}. "
         f"The departure times of the assignment are therefore those of the activity model after this shift. Flow capacity factor {flowcf}, storage capacity factor {storcf}, for the 10\\% sample. "
         f"Each of the {nw} runs uses a different random seed with the same population and inputs. Spread across runs is given as the range, smallest to largest run, in tables and figures.")
doc.para("Network. The road network is OpenStreetMap as coded for the assignment. Free speed is 0.9 times the posted speed below 51 km/h and the posted speed otherwise. "
         "Capacity is a value per lane by road class times the number of lanes (1,500 vehicles per hour for primary, 800 for secondary and 600 for tertiary and residential roads), "
         "and the bottleneck capacity of the Highway Capacity Manual on motorways and trunk roads. The 2024 network has the Key Bridge closed. Count stations near the bridge whose last count predates the closure in March 2024 carry estimates that do not show the diversion of its traffic, "
         "mainly to I-695 west of the harbour and the harbour tunnels, so the ratios of these stations are less reliable.")
doc.para(f"Targets. Daily traffic: annual average weekday traffic of the Maryland State Highway Administration at {thousands(nst)} mainline count stations matched to network links "
         f"({thousands(meta['use']['ramp'])} further ramp stations are reported separately). Passenger vehicles are the count less the truck and bus share of the station. "
         f"Of the mainline stations, {thousands(int(TS[(TS.table == 'facility_counted2024') & (TS.group == 'All classes')].n.iloc[0]))} were counted in 2024; the others carry the "
         "Administration's 2024 estimate from older counts grown with its own factors. Hourly traffic: the continuous count stations of the Federal Highway Administration (TMAS), "
         "all vehicles of 2023 scaled to 2024 at 11 counter sites, and passenger vehicles of 2024 at the continuous stations. Screenlines: seven lines across the region. "
         "Mileage: State Highway Administration vehicle miles by county and road class. Commute: American Community Survey (ACS) 2024 one-year distributions and 2020--2024 five-year means. "
         "Trip length and mode: 2017/18 Regional Travel Survey and the 2022 National Household Travel Survey (households in large South Atlantic metropolitan areas with heavy rail, as a stand-in for Baltimore; "
         "the public file has no metropolitan area). Transit: National Transit Database boardings 2024. Work flows: ACS county flows 2016--2020 and LODES 2022.")
doc.para("Standards. Percent root mean square error by volume group (Florida Department of Transportation) and volume to count ratio by facility class, with the bands of the Tennessee "
         "Department of Transportation guidelines: freeways within 7\\%, principal and minor arterials within 15\\%, collectors within 25\\%; deviation by volume as given by the Federal Highway Administration. "
         "Hourly flows: GEH statistic below 5 for more than 85\\% of flows.")

# ------------------------------------------------------------------ map
doc.section("Map of the network and the count stations")
mt = DJ["matching"]; lk = DJ["links"]
SGf = SG[SG.fac.notna()].set_index(["dimension", "group", "fac"]); SG0 = SG[SG.fac.isna()].set_index(["dimension", "group"])
doc.para(f"The network holds {thousands(lk['n'])} car links, {thousands(lk['with_traffic'])} of which carry modelled traffic; the rest are residential and service streets on which no sampled resident starts, ends or passes. "
         f"The map shows the pattern behind the tables: the freeways carry {min(SGf.loc[('Ring', '0-5 km', 'freeway')].ratio_pass, SGf.loc[('Ring', '10-20 km', 'freeway')].ratio_pass):.2f} to "
         f"{max(SGf.loc[('Ring', '0-5 km', 'freeway')].ratio_pass, SGf.loc[('Ring', '10-20 km', 'freeway')].ratio_pass):.2f} of their passenger counts within 20 km of downtown and {SGf.loc[('Ring', 'over 20 km', 'freeway')].ratio_pass:.2f} beyond, "
         f"where the through traffic is a larger share, the principal arterials are close to their counts everywhere, the blue stations below the count sit on the collectors and local "
         f"streets of every part of the region ({SGf.loc[('Ring', '0-5 km', 'collector')].ratio_pass:.2f} within 5 km of downtown, {SGf.loc[('Ring', 'over 20 km', 'collector')].ratio_pass:.2f} beyond 20 km), and the red stations above the count "
         f"are scattered arterials and collectors rather than a district. The stations with almost no modelled traffic are short residential streets at the edge of the built-up area (Section 4.1).")
doc.para("An interactive version of the map (validation\\_map.html, delivered with this report) draws every link with its volume and, on a click, its id, road type, lanes, capacity and the volume of each direction; "
         "every mainline and ramp station with its count, count year, passenger count, model mean and range over the runs, ratio, matched links and matching flags; the continuous counters with their hourly fit; "
         "the seven screenlines with their ratios; the county boundaries; and the area around the Key Bridge. The stations can be shown by ratio class or by deviation class (within the FHWA desirable deviation, within 25\\%, outside). "
         "Each layer can be switched on and off. The file opens in a web browser; only the base-map tiles are loaded from the web.")
# the map is a full page: a [p] float, so that the text of the next section fills the current page and the map takes the following one
import shutil
doc.nfig += 1; _mapname = f"f{doc.nfig:02d}.pdf"; shutil.copy(f"{DF}/validation_map.pdf", f"{WORK}/{_mapname}"); doc.figfiles.append(_mapname)
doc.raw("\\begin{figure}[p]\n\\centering\n\\includegraphics[width=\\textwidth]{" + _mapname + "}\n\\caption{"
        + f"(a) Modelled weekday traffic of the residents on the road network, mean of the {nw} runs, both directions of a road on one line; links carrying fewer than 500 vehicles per weekday are not drawn. "
        + f"Dots: the {thousands(nst)} mainline count stations, coloured by the passenger model/count ratio (grey within 10\\% of the count, blue below, red above); crosses: stations whose matched link carries fewer than "
        + f"{mt['zero_threshold']} modelled vehicles. Dashed circles: 5, 10 and 20 km from downtown Baltimore. (b) Passenger model/count by ring, with the number of stations."
        + "}\n\\end{figure}\n")

# ------------------------------------------------------------------ counts by facility
doc.section("Daily counts by facility class")
rows = []
for g in ["Interstate: I-695", "Interstate: other", "Other freeway / expressway", "Principal arterial", "Minor arterial", "Major collector", "Minor collector / local", "All classes"]:
    x = F[(F.group == g) & (F.comparison == "all vehicles")].iloc[0]; p = F[(F.group == g) & (F.comparison == "passenger vehicles")].iloc[0]
    rows.append([tx(g.replace(": ", ", ").replace(" / ", ", ")), thousands(x.n), num(x.ratio_mean, 3), rng(x.ratio_min, x.ratio_max), num(p.ratio_mean, 3), num(x.prmse_mean, 1), num(100 * x.within25_mean, 0), num(100 * x.within_fhwa_mean, 0)])
doc.table(["Facility class", "Stations", hd("Model/count,", "all vehicles"), hd("Range of", "runs"), hd("Model/count,", "passenger"), hd("RMSE", "(\\%)"), hd("Within", "25\\% (\\%)"), hd("Within FHWA", "deviation (\\%)")],
          rows, "lrrrrrrr", "Model against counts by facility class, weekday traffic at mainline stations.",
          note=f"Ratio of the summed model volume to the summed count; mean of the {nw} runs and range across runs (all vehicles). RMSE: root mean square error as a percentage of the mean count. "
               "Within 25\\%: share of stations with a ratio between 0.75 and 1.25. Within FHWA deviation: share of stations whose deviation is within the desirable deviation for their volume.", midrules=(7,))
doc.figure(f"{CD}/../figures/fig_counts_by_facility.pdf", "Model divided by count by facility class, all vehicles (solid) and passenger vehicles (hatched). Blue: within the band of the class; orange: outside. "
           "Grey band: the tolerance of the class (freeways 7\\%, arterials 15\\%, collectors 25\\%). Bars: range of the runs.")
doc.figure(f"{CD}/../figures/fig_net_scatter.pdf", "Modelled against counted daily traffic at the mainline stations, coloured by facility group: all vehicles (left) and passenger vehicles (right). Dashed: line through the origin.")
sc_all = SC[SC.panel == "All vehicles"].iloc[0]
G = TS[(TS.table == "volume_group") & (TS.comparison == "all vehicles")]
nfail = int((G.prmse_mean > G.acceptable).sum())
C24 = TS[(TS.table == "facility_counted2024") & (TS.group == "All classes")].iloc[0]
doc.para(f"Over all {thousands(nst)} stations the model carries {allv.ratio_mean * 100:.0f}\\% of the counted vehicles ({allp.ratio_mean * 100:.0f}\\% of the counted passenger vehicles). "
         f"The slope of the line through the origin is {sc_all.slope:.2f} and the squared correlation {sc_all.r2:.2f}. "
         f"The model does not meet the count standards. The percent RMSE is above the acceptable maximum in {nfail} of the {len(G)} volume groups; only the lowest group passes. "
         f"{100 * allv.within25_mean:.0f}\\% of the stations are within 25\\% of the count and {100 * allv.within_fhwa_mean:.0f}\\% within the FHWA deviation. "
         f"Most of the gap is traffic that the model does not hold: with passenger vehicles alone the ratio rises to {allp.ratio_mean:.2f} and the RMSE falls from {allv.prmse_mean:.0f}\\% to {allp.prmse_mean:.0f}\\%. "
         f"On the {thousands(int(C24.n))} stations counted in 2024 the ratio is {C24.ratio_mean:.3f} and the RMSE {C24.prmse_mean:.1f}\\%, so the older counts do not explain the gap. "
         "Collectors and minor arterials are lowest (about 0.6), where local commercial and delivery traffic, which the model does not have, is a large part of the count.")
Gp = TS[(TS.table == "volume_group") & (TS.comparison == "passenger vehicles")].set_index("group")
rows = [[tx(r.group.replace(" thousand", "")), thousands(r.n), num(r.ratio_mean, 2), num(r.prmse_mean, 1), num(Gp.prmse_mean.get(r.group, np.nan), 1), rng(r.prmse_min, r.prmse_max, 1), num(r.acceptable, 0), num(r.preferable, 0)] for r in G.itertuples()]
doc.table(["Counted volume (thousand)", "Stations", "Model/count", hd("RMSE, all", "vehicles (\\%)"), hd("RMSE, pass-", "enger (\\%)"), hd("Range of", "runs (pp)"), hd("Acceptable", "maximum (\\%)"), hd("Preferable", "maximum (\\%)")], rows, "lrrrrrrr",
          "Percent root mean square error by volume group.", note="Acceptable and preferable maxima: Florida Department of Transportation standards by volume group. Range of runs: smallest to largest RMSE of the runs, all vehicles, in percentage points.")
doc.figure(f"{CD}/../figures/fig_rmse_by_volume.pdf", "Percent root mean square error by volume group against the acceptable maximum (grey marks). Orange: above the standard. Bars: range of the runs.")
SH = TS[(TS.table.isin(["areawide", "split_half"])) & (TS.comparison == "all vehicles")]
rows = [[tx(r.group), thousands(r.n), num(r.ratio_mean, 3), num(r.prmse_mean, 1)] for r in SH.itertuples()]
RM = TS[(TS.table == "ramps") & (TS.group == "All ramp stations")].set_index("comparison")
rows += [["Ramp stations", thousands(RM.loc["all vehicles"].n), num(RM.loc["all vehicles"].ratio_mean, 3), num(RM.loc["all vehicles"].prmse_mean, 1)]]
doc.table(["Station set", "Stations", "Model/count", hd("RMSE", "(\\%)")], rows, "lrrr", "Model against counts for all mainline stations, the two halves of the station set, and ramps.",
          note="The halves are a fixed random split of the mainline stations into two sets of equal size.")
doc.para(f"Ramps carry {RM.loc['all vehicles'].ratio_mean:.2f} of their counts ({RM.loc['passenger vehicles'].ratio_mean:.2f} for passenger vehicles) while the mainline carries {allv.ratio_mean:.2f}. "
         "With trucks and non-residents missing, ramps at or above the counts suggest too many short trips that use the freeway between nearby interchanges. The RMSE of the ramps is high because many ramps carry little traffic.")

# ------------------------------------------------------------------ diagnostics of the daily-count comparison
doc.section("Diagnostics of the daily-count comparison")
doc.para("The checks of this section are descriptive. They ask whether the shortfall against the counts is spread evenly or concentrated, how much of it rests on uncertain station matches or on estimated counts, "
         "and how much of the counted traffic a model of the residents can hold at all. Nothing in the model, the counts or the station match is changed in response; the counts remain validation data only. "
         f"All figures of this section use the mean model volume of the {nw} runs (the runs differ by about 0.001 in any ratio).")
# ---- a. station matching
doc.sub("Station matching")
A0 = MA[MA.cls.isna()].set_index("set")
rows = [[tx(r.reason), tx(r.tier), thousands(r.stations)] for r in MRS.itertuples() if r.stations > 0]
doc.table(["Reason for doubt", "Tier", hd("Mainline", "stations")], rows, "L{0.66\\textwidth}lr", "Stations whose match to a network link is doubtful or weak, by reason.",
          note=f"Reasons overlap: {mt['doubtful']} stations are doubtful and {mt['weak']} further stations weak. Doubtful: the identity of the matched road could not be confirmed from route number or name; a parallel link of another road "
               "inside the matching tolerance carries more model traffic than the matched link (the model is used only to select these stations for review, the review itself is blind to it); the match lies beyond the tolerance; "
               "or the link is outside the connected core of the network. Weak: no word of the station's road name occurs in the link name, or the identity rests on one criterion only. The station-review page lists each of them with the surrounding links.")
sets = ["All mainline stations", "Without doubtful matches", "Without doubtful and weak matches", "Doubtful matches only", "Weak matches only", "Without near-zero model volume", "Without doubtful, weak and near-zero", "One station per link"]
rows = [[tx(s), thousands(A0.loc[s].n), num(A0.loc[s].ratio_all, 3), num(A0.loc[s].ratio_pass, 3), num(A0.loc[s].prmse_all, 1), num(A0.loc[s].prmse_pass, 1), num(100 * A0.loc[s].within25, 0), num(100 * A0.loc[s].within_fhwa, 0)] for s in sets]
doc.table(["Station set", "Stations", hd("Model/count,", "all vehicles"), hd("Model/count,", "passenger"), hd("RMSE, all", "vehicles (\\%)"), hd("RMSE, pass-", "enger (\\%)"), hd("Within", "25\\% (\\%)"), hd("Within FHWA", "deviation (\\%)")], rows, "lrrrrrrr",
          "Fit with and without the doubtful and weak matches and the stations without model traffic.",
          note=f"Near-zero: matched link with fewer than {mt['zero_threshold']} modelled vehicles per weekday. One station per link: where several stations share the same link or pair of links, the first is kept.", midrules=(3, 5))
a_all, a_nd, a_ndw, a_d = A0.loc["All mainline stations"], A0.loc["Without doubtful matches"], A0.loc["Without doubtful and weak matches"], A0.loc["Doubtful matches only"]
Mc = MA[(MA.set == "Without doubtful and weak matches") & MA.cls.notna()].set_index("cls")
doc.para(f"Removing the {mt['doubtful']} doubtful matches raises the all-vehicle ratio from {a_all.ratio_all:.3f} to {a_nd.ratio_all:.3f} and lowers the RMSE from {a_all.prmse_all:.1f} to {a_nd.prmse_all:.1f}\\%; removing the {mt['weak']} weak matches as well gives "
         f"{a_ndw.ratio_all:.3f} and {a_ndw.prmse_all:.1f}\\% ({a_ndw.ratio_pass:.3f} and {a_ndw.prmse_pass:.1f}\\% for passenger vehicles). The doubtful matches alone have a ratio of {a_d.ratio_all:.2f} and an RMSE of {a_d.prmse_all:.0f}\\%: "
         f"a wrong link usually carries less traffic than the counted road, so these stations pull the ratio down and the error up. They are {100 * mt['doubtful'] / mt['mainline']:.0f}\\% of the stations, and with the weak matches "
         f"{100 * (mt['doubtful'] + mt['weak']) / mt['mainline']:.0f}\\%; the clean set of {thousands(a_ndw.n)} stations raises the ratio by {a_ndw.ratio_all - a_all.ratio_all:.3f} and lowers the RMSE by {a_all.prmse_all - a_ndw.prmse_all:.0f} points, "
         "which is the size of the matching uncertainty in the headline figures. By class, without doubtful and weak matches, the passenger ratio is "
         f"{Mc.loc['Interstate: I-695'].ratio_pass:.2f} on I-695, {Mc.loc['Interstate: other'].ratio_pass:.2f} on the other interstates, {Mc.loc['Other freeway / expressway'].ratio_pass:.2f} on the other freeways, "
         f"{Mc.loc['Principal arterial'].ratio_pass:.2f} on principal arterials, {Mc.loc['Minor arterial'].ratio_pass:.2f} on minor arterials, {Mc.loc['Major collector'].ratio_pass:.2f} on major collectors and {Mc.loc['Minor collector / local'].ratio_pass:.2f} on minor collectors; "
         "the pattern by class is the same as with all stations.")
zc = ZV.cls.value_counts(); zcause = ZV.cause.value_counts(); zco = ZV.county.value_counts()
doc.para(f"{mt['near_zero']} mainline stations sit on a matched link that carries fewer than {mt['zero_threshold']} modelled vehicles per weekday; together they hold {100 * mt['near_zero_share_of_count']:.2f}\\% of the counted traffic "
         f"(mean count {ZV.count_all.mean():,.0f} vehicles). {zc.get('Minor collector / local', 0)} are minor collectors or local roads, {zc.get('Major collector', 0)} major collectors and {zc.get('Minor arterial', 0)} a minor arterial; "
         f"{zco.iloc[0]} lie in {zco.index[0]} and {zco.iloc[1]} in {zco.index[1]}. {'None' if mt['near_zero_outside_core'] == 0 else mt['near_zero_outside_core']} of their links {'lies' if mt['near_zero_outside_core'] == 0 else 'lie'} outside the connected core of the network, so this is not a connectivity fault; "
         f"{zcause.get('network ends at the state line', 0)} lie on local roads that cross the Pennsylvania line, where the network, built from the Maryland extract, ends at the state boundary and the road becomes a dead end; "
         f"{zcause.get('doubtful match', 0)} are doubtful matches, and the other {int(zcause.get('connected link, no route uses it', 0) + zcause.get('name differs', 0))} are connected residential streets that no modelled route uses: "
         "the 10\\% sample holds few residents of these streets, and their homes and destinations are placed on other links of the same neighbourhood. The list is in the data files of this report and the stations are marked on the map. "
         f"No two-way station has both of its directions matched to the same link. {mt['shared_link_stations']} stations ({mt['shared_links']} pairs of links) share their links with another station, the two one-way streets of the "
         "Fulton Avenue couplet in Baltimore City, where the matcher put both counts on the same links; keeping one station per link changes nothing in the totals.")
# ---- b. spatial pattern
doc.sub("Spatial pattern of the errors")
doc.figure(f"{DF}/fig_ratio_by_ring_county.pdf", "Model divided by count by distance from downtown Baltimore (a) and by county (b), all vehicles (solid) and passenger vehicles (hatched); number of stations in brackets.")
rows = []
for dim, order in [("Ring", ["0-5 km", "5-10 km", "10-20 km", "over 20 km"]), ("County", ["Baltimore City", "Baltimore County", "Anne Arundel", "Howard", "Harford", "Carroll"])]:
    for i, g in enumerate(order):
        r = SG0.loc[(dim, g)]; f = lambda fac: SGf.loc[(dim, g, fac)]
        rows.append([tx("Distance from downtown" if dim == "Ring" else "County") if i == 0 else "", tx(g.replace("-", "--")), thousands(r.n), num(r.ratio_all, 3), num(r.ratio_pass, 3), num(r.prmse_all, 1), num(r.prmse_pass, 1), num(r.median_ratio_pass, 2),
                     num(f("freeway").ratio_pass, 2) + f" ({int(f('freeway').n)})", num(f("arterial").ratio_pass, 2) + f" ({int(f('arterial').n)})", num(f("collector").ratio_pass, 2) + f" ({int(f('collector').n)})"])
doc.table(["", "Group", "Stations", hd("Model/count,", "all vehicles"), hd("Model/count,", "passenger"), hd("RMSE, all", "(\\%)"), hd("RMSE, pass-", "enger (\\%)"), hd("Median", "ratio"), hd("Freeways:", "ratio (n)"), hd("Arterials:", "ratio (n)"), hd("Collectors:", "ratio (n)")],
          rows, "llrrrrrrrrr", "Model against counts by distance from downtown Baltimore and by county.", note="Median ratio: median over the stations of the passenger model/count ratio. The last three columns give the passenger ratio and the number of stations of the freeways, the arterials and the collectors of the group.", small="\\scriptsize", midrules=(4,))
mi = MI.copy(); mi["variable"] = mi.variable.str.replace("log passenger ratio", "Log passenger ratio")
rows = [[tx(r.variable), str(int(r.k)), thousands(r.n), num(r.I, 3), num(r.expected, 4), num(r.z_perm, 1), num(r.p_perm, 3)] for r in mi.itertuples()]
doc.table(["Variable", hd("Neigh-", "bours"), "Stations", "Moran's I", hd("Expected", "value"), hd("z", "(permutation)"), hd("p", "(permutation)")], rows, "lrrrrrr", "Spatial autocorrelation of the log passenger ratio at the mainline stations.",
          note="Moran's I with row-standardised k-nearest-neighbour weights; z and p from 999 random permutations of the ratios over the stations. Class means removed: the log ratio minus the mean of its facility class, which takes out the road-class mix of the neighbourhoods.")
m8 = DJ["morans_i"]; r05 = SG0.loc[("Ring", "0-5 km")]; r20 = SG0.loc[("Ring", "over 20 km")]
doc.para(f"The ratio changes little with distance from downtown or by county: all-vehicle ratios of {SG0.loc[('Ring', '5-10 km')].ratio_all:.2f} to {r05.ratio_all:.2f} by ring and {SG0.loc[('County', 'Howard')].ratio_all:.2f} to {SG0.loc[('County', 'Carroll')].ratio_all:.2f} by county. "
         f"The innermost ring is highest because its arterials are at the count ({SGf.loc[('Ring', '0-5 km', 'arterial')].ratio_pass:.2f}) while its collectors are lowest of all ({SGf.loc[('Ring', '0-5 km', 'collector')].ratio_pass:.2f}): the model puts the residents' "
         f"trips of the city on the arterial grid and too few on the local streets. Carroll County is at {SG0.loc[('County', 'Carroll')].ratio_pass:.2f} for passenger vehicles with the smallest RMSE; it has the fewest through roads and the most self-contained travel. "
         f"The RMSE is largest in Harford ({SG0.loc[('County', 'Harford')].prmse_all:.0f}\\%) and Baltimore City ({SG0.loc[('County', 'Baltimore City')].prmse_all:.0f}\\%), where many low-volume stations sit.")
doc.para(f"Moran's I of the log passenger ratio with eight nearest neighbours is {m8['I']:.3f} (z = {m8['z']:.1f}, p = {m8['p']:.3f}); the expected value without autocorrelation is {MI.expected.iloc[0]:.4f}. The errors are therefore clustered beyond chance, "
         f"but weakly: neighbouring stations share about a tenth of their deviation. The statistic is the same after the class means are removed ({m8['I_class_removed']:.3f}), so the clustering is not the road-class mix of the neighbourhoods, "
         f"and it is similar with 4 and 12 neighbours and within freeways, arterials and collectors taken separately ({MI[MI.variable.str.contains('only')].I.min():.2f} to {MI[MI.variable.str.contains('only')].I.max():.2f}). "
         "Clustered errors point to causes in demand or network (a district with too few trips, a corridor with the wrong speed or capacity); scattered errors point to noise of the counts, the sample and the matching. "
         "The value found says that both are present and that the local part dominates: the deviation of one station is a poor predictor of its neighbour's. "
         "This is consistent with the picture of the map, where blue and red stations lie side by side on neighbouring roads, and with the class pattern, which is the same in every ring and county.")
# ---- c. count quality
doc.sub("Error by count quality, lanes and capacity")
rows = []; last = None
for r in CQ.itertuples():
    rows.append([tx(r.dimension) if r.dimension != last else "", tx(r.group), thousands(r.n), num(r.ratio_all, 3), num(r.ratio_pass, 3), num(r.prmse_all, 1), num(r.prmse_pass, 1), thousands(r.mean_count), num(100 * r.freeway_share, 0)]); last = r.dimension
mids = tuple(i for i, r in enumerate(rows) if r[0] and i)
doc.table(["", "Group", "Stations", hd("Model/count,", "all vehicles"), hd("Model/count,", "passenger"), hd("RMSE, all", "(\\%)"), hd("RMSE, pass-", "enger (\\%)"), hd("Mean count", "(vehicles)"), hd("Freeway", "stations (\\%)")], rows, "llrrrrrrr",
          "Model against counts by count year and age, basis of the count, lanes of the station and capacity class of the matched link.",
          note="Count age: years since the last count, from the published weekday value of the Administration (0 = counted in 2024; the others are estimates grown from the last count). Basis: every station of the set has a weekday value (AAWDT), "
               "so the annual average (AADT) is not used. Lanes: through lanes of the station in the count file. Capacity: capacity per lane of the matched link as coded in the network (600 vehicles per hour on tertiary and residential streets, "
               "800 on secondary roads, 1,500 on primary and trunk roads, the bottleneck capacity of the Highway Capacity Manual on motorways).", small="\\scriptsize", midrules=mids)
rows = [[tx(k.replace(": ", ", ").replace(" / ", ", ")), thousands(r.n), thousands(r.counted24), num(r.ratio_pass_counted, 3), num(r.ratio_pass_estimated, 3), num(r.prmse_pass_counted, 1), num(r.prmse_pass_estimated, 1)] for k, r in CQC.set_index("cls").iterrows()]
doc.table(["Facility class", "Stations", hd("Counted", "in 2024"), hd("Model/count,", "counted 2024"), hd("Model/count,", "estimated"), hd("RMSE,", "counted (\\%)"), hd("RMSE,", "estimated (\\%)")], rows, "lrrrrrr", "Stations counted in 2024 against stations with an estimate, by facility class, passenger vehicles.")
q = CQ.set_index(["dimension", "group"]); c24 = q.loc[("Count year", "Counted in 2024")]; est = q.loc[("Count year", "Estimate from an older count")]; cc = CQC.set_index("cls")
doc.para(f"The {thousands(c24.n)} stations counted in 2024 have a lower ratio ({c24.ratio_pass:.3f} passenger) than the {thousands(est.n)} with an estimate ({est.ratio_pass:.3f}); the difference comes from the minor arterials "
         f"({cc.loc['Minor arterial'].ratio_pass_counted:.2f} against {cc.loc['Minor arterial'].ratio_pass_estimated:.2f}), where most of the 2024 counts were made, while the collectors show the opposite ({cc.loc['Major collector'].ratio_pass_counted:.2f} against "
         f"{cc.loc['Major collector'].ratio_pass_estimated:.2f}). The fresh counts are therefore not kinder to the model than the estimates; the age of a count does not explain the shortfall. The ratio falls with the age of the estimate "
         f"({q.loc[('Count age', '5 years or older')].ratio_pass:.2f} at five years or more) because the old estimates sit on the smallest roads (mean count {q.loc[('Count age', '5 years or older')].mean_count:,.0f}), not because they are old. "
         "Every station of the set has a weekday value, so the basis of the count plays no part.")
cp = q.loc["Capacity of the matched link"]; ln = q.loc["Lanes of the station"]
doc.para(f"The clearest split is by the capacity class of the matched link: the model carries {cp.iloc[0].ratio_pass:.2f} of the passenger count on links coded with 600 vehicles per hour per lane (tertiary and residential streets, "
         f"{thousands(cp.iloc[0].n)} stations), {cp.iloc[1].ratio_pass:.2f} on secondary roads, {cp.iloc[2].ratio_pass:.2f} on primary and trunk roads and {cp.iloc[3].ratio_pass:.2f} on motorways. By lanes the picture is the same: "
         f"{ln.iloc[0].ratio_pass:.2f} on one- and two-lane roads against {ln.iloc[1].ratio_pass:.2f} on roads with three or four lanes and {ln.iloc[2].ratio_pass:.2f} with five or six. The residents' trips of the model reach the counts on the primary roads and fall short on the "
         "small streets. Two readings are possible and both are likely to hold in part: the local traffic that the model does not contain (deliveries, visitors, trips of non-residents) is a larger share of the count on small streets, "
         "and the assignment sends the residents' trips to the primary roads where in reality some use the parallel secondary and tertiary streets. The route-choice tables of the article (share of short trips on local roads) point the same way.")
# ---- d. volume groups
doc.sub("Volume groups")
rows = []
for r in VG.itertuples():
    rows.append([tx(r.group.replace(" thousand", "")), thousands(r.n), num(100 * r.share_stations, 0), num(100 * r.share_count, 0), num(r.ratio_all, 2), num(r.ratio_pass, 2), num(r.prmse_all, 1), num(r.prmse_pass, 1), num(r.acceptable, 0) if pd.notna(r.acceptable) else "--"])
doc.table(["Counted volume (thousand)", "Stations", hd("Share of", "stations (\\%)"), hd("Share of", "volume (\\%)"), hd("Model/count,", "all vehicles"), hd("Model/count,", "passenger"), hd("RMSE, all", "(\\%)"), hd("RMSE, pass-", "enger (\\%)"), hd("Acceptable", "maximum (\\%)")], rows, "lrrrrrrrr",
          "Volume groups with the share of the stations and of the counted traffic in each group, and the stations above 10,000, 25,000 and 50,000 vehicles.",
          note="Acceptable maximum: the Florida Department of Transportation standard for the group. Share of volume: share of the summed weekday count of all mainline stations.", midrules=(8, 11), small="\\scriptsize")
v = VG.set_index("group"); v5 = v.loc["0-5 thousand"]; v10 = v.loc["10 thousand and more"]; v25 = v.loc["25 thousand and more"]
doc.para(f"{100 * v5.share_stations:.0f}\\% of the stations count fewer than 5,000 vehicles and together hold {100 * v5.share_count:.0f}\\% of the counted traffic; {100 * (v5.share_stations + v.loc['5-10 thousand'].share_stations):.0f}\\% count fewer than 10,000 "
         f"and hold {100 * (v5.share_count + v.loc['5-10 thousand'].share_count):.0f}\\%. The all-station RMSE of {allv.prmse_mean:.0f}\\% is therefore dominated by small roads, whose percentage errors are large by nature. "
         f"On the {thousands(v10.n)} stations above 10,000 vehicles ({100 * v10.share_stations:.0f}\\% of the stations, {100 * v10.share_count:.0f}\\% of the traffic) the RMSE is {v10.prmse_all:.0f}\\% for all vehicles and {v10.prmse_pass:.0f}\\% for passenger vehicles "
         f"at a ratio of {v10.ratio_pass:.2f}; above 25,000 vehicles ({thousands(v25.n)} stations, {100 * v25.share_count:.0f}\\% of the traffic) {v25.prmse_all:.0f} and {v25.prmse_pass:.0f}\\% at {v25.ratio_pass:.2f}. "
         "These values still exceed the acceptable maxima of their groups, which are written for a model that carries all traffic; the shortfall itself, not scatter, makes up most of the error on the large roads.")
# ---- e. expected coverage
doc.sub("Expected coverage of the counts by a model of the residents")
th = CSRC["through"]; cd = CSRC["cordon"]; nh = CSRC["nhts"]
doc.para("The model carries the cars of the persons whose day touches the six counties. Trucks and buses are removed from the counts with the classification of the station. Three further groups of vehicles are in the counts and "
         "cannot be in the model: through trips of persons who cross the region without stopping, visitors from beyond the model area, and light commercial, delivery and fleet vehicles. The following estimate of their share "
         "of the counted passenger traffic is explanatory: it rests on sources already in the project and on one public survey, it is given with its range, and nothing is applied to the model or to the counts.")
doc.para(f"Through trips of the model area. The activity model covers Maryland, Delaware, the District of Columbia and the neighbouring counties of Pennsylvania, Virginia and West Virginia. Its output for the replication passed to the "
         f"assignment holds {thousands(th['persons_model_area'])} persons (10\\% sample), of whom {thousands(th['persons_touching_region'])} touch the six counties and are in the assignment. Of the others, "
         f"{thousands(th['through_car_trips_sample'])} car-driver trips, {thousands(th['through_car_trips_day'])} per weekday after expansion, run in a straight line through the region without an activity in it; "
         + ", ".join(f"{thousands(n)} of them start in {k.replace(' (outside the six counties)', ' outside the six counties')}" if i == 0 else f"{thousands(n)} in {k}" for i, (k, n) in enumerate(th["through_trips_by_home_state"].items())) +
         f". Their straight line inside the region is {th['mean_chord_inside_km']:.0f} km on average (median {th['median_chord_inside_km']:.0f} km) on trips of {th['mean_trip_distance_km']:.0f} km; with a detour factor of {th['detour_factor'][1]} "
         f"(range {th['detour_factor'][0]} to {th['detour_factor'][2]}) they amount to {th['through_vehicle_miles_day'] / 1e6:.2f} million vehicle miles per weekday, {100 * CE.set_index('group').loc['All mainline stations'].through_share:.1f}\\% of the "
         f"{CE.set_index('group').loc['All mainline stations'].observed_pass_vmt_mday:.1f} million weekday passenger-vehicle miles of the six counties. They are allocated to freeways and principal arterials in the proportion of the counts at the "
         f"{cd['crossings']} principal crossings of the regional boundary ({100 * cd['freeway_share']:.0f}\\% on freeways). Crossing the boundary twice, they are {100 * 2 * th['through_car_trips_day'] / cd['cordon_aadt_2023']:.0f}\\% of the "
         f"{thousands(cd['cordon_aadt_2023'])} vehicles counted at these crossings in 2023. Through traffic from beyond the model area, above all the I-95 corridor between the north-east and Washington, is not in this figure: "
         "the external trip tables of the statewide model, which would give it, are not in the project, and no public origin--destination count of this traffic is known to us; the freeway range below is therefore a lower bound.")
doc.para(f"Light commercial and fleet vehicles. No count separates commercial from private light vehicles. Two bounds are available. The lower bound is the share of household car-driver vehicle miles made to or from a work-related "
         f"meeting or trip in the 2022 National Household Travel Survey, {100 * nh['national_vmt_share']:.1f}\\% nationally on weekdays ({thousands(nh['n_trips_national'])} trips; the subsample of large South Atlantic metropolitan areas "
         f"with rail is too small, {nh['n_trips_south_atlantic']} trips, to be used); it leaves out the vehicles of businesses, which the survey does not cover. The upper bound is the share of two-axle, four-tyre light trucks "
         f"(pickups and vans, class 3 of the Federal Highway Administration) at the classification stations of the region, {100 * CE.set_index('group').loc['All mainline stations'].light_truck_share:.0f}\\% of the count, which "
         "includes the private pickups and vans. The midpoint of the two is used as the central value. Visitors from beyond the model area are not estimated.")
rows = []
for r in CE.itertuples():
    pr = lambda c, lo, hi: "--" if hi == 0 else f"{num(100 * c, 1)} ({num(100 * lo, 1)} to {num(100 * hi, 1)})"
    rows.append([tx(r.group), thousands(r.stations), num(100 * (r.truck_share + r.bus_share), 1), pr(r.through_share, r.through_low, r.through_high), pr(r.commercial_central, r.commercial_low, r.commercial_high),
                 pr(r.expected_central, r.expected_low, r.expected_high), num(100 * r.shortfall_all, 1), num(100 * r.shortfall_pass, 1), f"{num(100 * r.residual_central, 1)} ({num(100 * r.residual_low, 1)} to {num(100 * r.residual_high, 1)})"])
doc.table(["Facility group", "Stations", hd("Trucks and", "buses (\\%)"), hd("Through trips", "(\\%)"), hd("Commercial,", "fleet (\\%)"), hd("Expected", "shortfall (\\%)"), hd("Observed, all", "vehicles (\\%)"), hd("Observed, pass-", "enger (\\%)"), hd("Residual", "(\\%)")], rows, "lrrrrrrrr",
          "Share of the counted traffic that a model of the residents cannot carry, estimate against the observed shortfall, by facility group.",
          note="Trucks and buses: count-weighted share at the classification stations of the group, already removed from the passenger count. Through trips and commercial: share of the counted passenger traffic, central value with the range. "
               "Expected shortfall: sum of the two; through trips are allocated to freeways and principal arterials only. Observed: one minus the model/count ratio of the group, all vehicles and passenger vehicles. Residual: observed passenger shortfall minus the expected shortfall; positive values are traffic of the residents "
               "that the model lacks (or network and matching effects), negative values resident traffic above the count. Through traffic from beyond the model area is not included, so the expected shortfall of the freeways is a lower bound.",
          small="\\scriptsize", midrules=(4,))
ce = CE.set_index("group"); fw = ce.loc["Interstates and freeways"]; pa = ce.loc["Principal arterials"]; ma_ = ce.loc["Minor arterials"]; co = ce.loc["Collectors and local roads"]; al = ce.loc["All mainline stations"]
doc.para(f"On the freeways the expected shortfall of {100 * fw.expected_central:.0f}\\% ({100 * fw.expected_low:.0f} to {100 * fw.expected_high:.0f}) against an observed {100 * fw.shortfall_pass:.0f}\\% leaves a residual of "
         f"{100 * fw.residual_central:.0f} points, within the range of the estimate once the through traffic from beyond the model area is allowed for: the freeway shortfall is explained by what the model does not contain. "
         f"On the principal arterials the observed shortfall ({100 * pa.shortfall_pass:.0f}\\%) is smaller than the expected one ({100 * pa.expected_central:.0f}\\%): the residents' trips of the model are above the level the counts allow for them, "
         "which agrees with the finding of the previous subsection that the model loads the primary roads. On the minor arterials and the collectors the expected shortfall is "
         f"{100 * ma_.expected_central:.0f} and {100 * co.expected_central:.0f}\\% but the observed one {100 * ma_.shortfall_pass:.0f} and {100 * co.shortfall_pass:.0f}\\%, so residuals of {100 * ma_.residual_central:.0f} and {100 * co.residual_central:.0f} points "
         f"({100 * co.residual_low:.0f} to {100 * co.residual_high:.0f} on the collectors) remain that coverage does not explain. Over all stations the expected shortfall is {100 * al.expected_central:.0f}\\% ({100 * al.expected_low:.0f} to {100 * al.expected_high:.0f}) "
         f"against {100 * al.shortfall_pass:.0f}\\% observed. The part of the gap that belongs to the model is therefore on the small roads, and it is of the order of {100 * co.residual_low:.0f} to {100 * co.residual_high:.0f}\\% of their counts: "
         "too few short trips of the residents on the local network, or short trips routed onto the primary roads. The trip-length and route-choice checks of the article address this upstream; it is not resolved here.")

# ------------------------------------------------------------------ hourly
doc.section("Hourly counts")
pk = CT[CT.group == "All counters"].set_index("period")
doc.para(f"At the 11 counter sites the model carries {pk.loc['Whole day', 'ratio_mean']:.2f} of the daily count, but {pk.loc['Morning peak (6-10 h)', 'ratio_mean']:.2f} in the morning peak "
         f"and {pk.loc['Evening peak (15-19 h)', 'ratio_mean']:.2f} in the evening peak, against {pk.loc['Midday (10-15 h)', 'ratio_mean']:.2f} at midday and {pk.loc['Night (0-6 h)', 'ratio_mean']:.2f} at night. "
         "The traffic that the model does not hold (trucks, commercial vehicles, through traffic and visitors) runs mostly outside the peaks, and this explains much of the shortfall at midday and at night. "
         "In the peaks the volumes of the residents alone reach the counts, although part of the peak traffic is also non-resident. The trips of the residents are therefore somewhat too concentrated in the peaks. "
         "This agrees with the activity model, which has too many work activities on a weekday because it keeps the work attendance of the base year.")
gt = pk["geh5_mean"]
doc.para(f"The GEH statistic is below 5 in {100 * pk.loc['Whole day', 'geh5_mean']:.0f}\\% of the counter hours and in {100 * TM[(TM.group == 'All stations') & (TM.period == 'Whole day')].geh5.iloc[0]:.0f}\\% of the station hours of the "
         "continuous stations, far from the guideline of 85\\%. At night and at midday the failures are the missing traffic; in the peaks they are the excess of resident trips. "
         "The 10\\% sample scaled by ten also adds noise to the hourly volumes.")
rows = []
for g in CT.group.unique():
    for r in CT[CT.group == g].itertuples():
        rows.append([tx(g) if r.period.startswith("Night") else "", tx(r.period), num(r.ratio_mean, 3), rng(r.ratio_p5, r.ratio_p95), num(100 * r.geh5_mean, 0)])
doc.table(["Counters", "Period", "Model/count", hd("Range of", "runs"), hd("GEH < 5", "(\\%)")], rows, "llrrr", "Hourly traffic at the 11 counter sites by period, all vehicles.",
          note=f"Counter directions: {meta['n_counter_directions']}. Counts: all vehicles, TMAS 2023 weekday hourly means scaled to 2024 with the change of the annual traffic of the station. "
               "Model: cars of the residents plus buses. GEH: share of station-direction-hours with GEH below 5; the guideline is 85\\%.",
          midrules=tuple(i for i, r in enumerate(rows) if r[0] and i))
doc.figure(f"{CD}/../figures/fig_counters_hourly.pdf", "Hourly traffic at the 11 counter sites by direction, all vehicles: count, model and range of the runs. Orange: hours with GEH of 5 or more.")
mc = [c for c in TH.columns if re.fullmatch(r"model_s\d+", c)]
PER = [("Night (0-6 h)", range(0, 6)), ("Morning peak (6-10 h)", range(6, 10)), ("Midday (10-15 h)", range(10, 15)), ("Evening peak (15-19 h)", range(15, 19)), ("Evening (19-24 h)", range(19, 24)), ("Whole day", range(24))]
def seed_range(g, period):
    d = TH if g == "All stations" else TH[TH.grp == g]; d = d[d.hour.isin(list(dict(PER)[period]))]
    v = [d[c].sum() / d.obs_pass.sum() for c in mc]; return min(v), max(v)
rows = []
for g in TM.group.unique():
    for r in TM[TM.group == g].itertuples():
        lo, hi = seed_range(g, r.period)
        rows.append([tx(g) if r.period.startswith("Night") else "", tx(r.period), thousands(r.directions) if r.period.startswith("Night") else "", num(r.ratio, 3), rng(lo, hi), num(100 * r.geh5, 0)])
doc.table(["Road group", "Period", "Directions", "Model/count", hd("Range of", "runs"), hd("GEH < 5", "(\\%)")], rows, "llrrrr", "Hourly passenger traffic at the continuous count stations (TMAS) by period, 2024.",
          note="Average weekday of 2024 by station, direction and hour; passenger vehicles. Model: residents' cars on the link of the counted direction. Range of runs: the ratio of the period computed for each run, smallest to largest. "
               "The stations include ten of the 11 counter sites above; they are shown with passenger vehicles and the counts of 2024, which removes the trucks from the comparison.", midrules=tuple(i for i, r in enumerate(rows) if r[0] and i))
doc.figure(f"{O['tmas']}/figures/fig_net_tmas_hourly.pdf", "Hourly passenger traffic at the continuous count stations: count, model and range of the runs, by direction.")
# ---- f. detail by counter and direction
doc.sub("Profiles by counter and direction")
P6 = ["Night (0-6 h)", "Morning peak (6-10 h)", "Midday (10-15 h)", "Evening peak (15-19 h)", "Evening (19-24 h)", "Whole day"]
X = CPS.set_index(["group", "direction", "period"]); rows = []
for p in P6:
    r = [tx(p)]
    for g in ["Freeways", "Arterials and collectors"]:
        for dg in ["North- or eastbound", "South- or westbound"]:
            x = X.loc[(g, dg, p)]; r += [num(x.ratio, 2), num(100 * x.geh5, 0)]
    x = X.loc[("All stations", "Both", p)]; r += [num(x.ratio, 2), num(100 * x.geh5, 0), num(100 * x.geh10, 0)]; rows.append(r)
nfd = int(X.loc[("Freeways", "North- or eastbound", "Whole day")].directions); nad = int(X.loc[("Arterials and collectors", "North- or eastbound", "Whole day")].directions)
doc.table(["Period", hd("Freeways", "N/E"), hd("GEH<5", "(\\%)"), hd("Freeways", "S/W"), hd("GEH<5", "(\\%)"), hd("Arterials", "N/E"), hd("GEH<5", "(\\%)"), hd("Arterials", "S/W"), hd("GEH<5", "(\\%)"), hd("All", "directions"), hd("GEH<5", "(\\%)"), hd("GEH<10", "(\\%)")], rows, "lrrrrrrrrrrr",
          "Hourly passenger traffic at the continuous count stations by period and direction of travel: model/count and share of hours with GEH below 5.",
          note=f"North- or eastbound ({nfd} freeway and {nad} arterial directions) and south- or westbound ({nfd} and {nad}). Ratio: model divided by count of the hourly volumes summed over the stations and hours of the period. "
               "GEH < 5 and GEH < 10: share of the station-direction-hours of the period. The two directions of a road differ by the peak they carry: the morning peak is in the direction of the city and of the employment "
               "centres (south- or westbound on most radials), the evening peak in the other.", small="\\scriptsize")
CDD = CDD.assign(_o=CDD.grp.ne("Freeways").astype(int)).sort_values(["_o", "road", "station", "direction"], kind="stable").drop(columns="_o").reset_index(drop=True)
CL = {"Interstate: I-695": "I-695", "Interstate: other": "Interstate", "Other freeway / expressway": "Freeway", "Principal arterial": "Principal arterial", "Minor arterial": "Minor arterial", "Major collector": "Major collector", "Minor collector / local": "Minor collector"}
rows = []
for _, r in CDD.iterrows():
    rows.append([tx(r.road), str(r.station)[2:].lstrip("0"), tx(r.direction[0]), tx(CL.get(r.cls, r.cls)), thousands(r.count_day), thousands(r.model_day), num(r.ratio_day, 2), num(r.profile_corr, 2), num(100 * r.geh5_day, 0),
                 num(100 * r["geh5_Morning peak"], 0), num(100 * r["geh5_Midday"], 0), num(100 * r["geh5_Evening peak"], 0), num(100 * r["geh5_Night"], 0), tx(r.verdict)])
nfw = int((CDD.grp == "Freeways").sum())
doc.table(["Road", "Site", "Dir.", "Class", hd("Count", "per day"), hd("Model", "per day"), "Ratio", hd("Profile", "correlation"), hd("GEH<5", "day (\\%)"), hd("GEH<5", "AM (\\%)"), hd("GEH<5", "midday (\\%)"), hd("GEH<5", "PM (\\%)"), hd("GEH<5", "night (\\%)"), "Verdict"], rows, "lllllrrrrrrrrl",
          "Every continuous count station and direction: level, shape of the profile and share of hours with GEH below 5 by period, passenger vehicles.",
          note="Count and model: passenger vehicles per weekday in the direction. Profile correlation: Pearson correlation of the 24 hourly shares of count and model. Verdict: shape right when the correlation is at least 0.90, "
               "level low below a daily ratio of 0.85 and high above 1.15. Dir.: N, S, E, W. AM: 6--10 h; midday: 10--15 h; PM: 15--19 h; night: 0--6 h.", small="\\scriptsize", tabsep=2, midrules=(nfw,))
def names(v):
    d = CDD[CDD.verdict == v]; return ", ".join(f"{r.road} site {str(r.station)[2:].lstrip('0')} {r.direction.lower()}" for _, r in d.iterrows())
vc = CDD.verdict.value_counts(); i95 = CDD[CDD.road == "I-95"]
doc.para(f"Of the {len(CDD)} station directions, {vc.get('shape right, level right', 0)} have the right shape and level, {vc.get('shape right, level low', 0)} the right shape at a low level ({names('shape right, level low')}), "
         f"{vc.get('shape off, level low', 0)} a shape that is off at a low level ({names('shape off, level low')}), {vc.get('shape off, level high', 0)} a shape that is off at a high level ({names('shape off, level high')}), "
         f"and {vc.get('shape off, level right', 0)} a shape that is off at the right level ({names('shape off, level right')}).")
doc.para(f"The right-shape, low-level directions are freeway directions whose commute peaks the model reproduces while the traffic between the peaks is missing; the hourly ratio is close to one in the peak and 0.5 to 0.7 at midday. "
         f"I-95 is the clearest case of a shape that is off: at its three sites and in both directions the model carries {i95.ratio_day.min():.2f} to {i95.ratio_day.max():.2f} of the day, its morning peak holds "
         f"{100 * i95.am_share_model.min():.0f} to {100 * i95.am_share_model.max():.0f}\\% of the daily volume against {100 * i95.am_share_count.min():.0f} to {100 * i95.am_share_count.max():.0f}\\% in the count, and the night and midday volumes are a third to a half of the count: "
         "this is the corridor of the through traffic and of the freight that the model does not carry, and the resident commute alone makes a peakier day than the counts show. The arterials whose shape is off at a high level "
         "(MD 140 in Carroll County, MD 439 at I-83 in the north of Baltimore County, MD 129) are roads where the model puts commute peaks of residents that the count does not show at that size; MD 439 carries twice its count in both directions, "
         "which points to a routing of trips to and from I-83 through this road. Where the shape is off at the right level (MD 45, MD 129 northbound, I-695 site 74 northbound, MD 295), the peak hour of the model is shifted by one hour "
         "or the model has a sharper peak on a flat count. The departure-time shift of the assignment is limited to 30 minutes, so the peak shape is that of the activity model.")
doc.figure(f"{DF}/fig_counters_geh_heatmap.pdf", "Every continuous count station and direction by hour: GEH statistic (left) and model divided by count (right), passenger vehicles. Freeways above the line, arterials and collectors below.")

# ------------------------------------------------------------------ screenlines
doc.section("Screenlines")
doc.figure(f"{O['art']}/figures/fig_net_study_area.pdf", "The six counties of the study area, the major roads and the seven screenlines S1 to S7.")
S0 = SL[SL.section == "all"]
rows = [[f"S{int(r.sl)}", tx(r['name']), thousands(r.crossings), thousands(r.counted), num(100 * r.cap_share, 0), thousands(r.count_all), thousands(r.model_all), num(r.ratio_all, 2), rng(r.ratio_all_min, r.ratio_all_max), num(r.ratio_pass, 2)] for _, r in S0.iterrows()]
lowcov = [f"S{int(r.sl)} ({100 * r.cap_share:.0f}\\%)" for _, r in S0.iterrows() if r.cap_share < 0.5]
doc.table(["Line", "Screenline", "Crossings", "Counted", hd("Counted", "capacity (\\%)"), hd("Count", "(vehicles)"), hd("Model", "(vehicles)"), hd("Model/", "count"), hd("Range", "of runs"), hd("Passenger", "ratio")],
          rows, "lL{0.2\\textwidth}rrrrrrrr", "Screenline volumes: model against counts, all vehicles.",
          note="Crossings: car links of motorway to tertiary class that cross the line. Counted: crossings with a matched count station on the same road. Counted capacity: share of the capacity of all crossings "
               "that lies on counted crossings. Counted volume and model volume are summed over the counted crossings. Ratio: model divided by count."
               + (f" Lines with less than half of the capacity counted: {', '.join(lowcov)}; their ratios rest on part of the line only." if lowcov else ""), small="\\scriptsize")
doc.figure(f"{O['art']}/figures/fig_net_screenlines.pdf", "Screenlines with model divided by count, all vehicles and passenger vehicles.")

# ------------------------------------------------------------------ VMT
doc.section("Vehicle miles")
V0 = SUM["vmt"]
doc.para(f"Weekday vehicle miles of the residents on the network are {V0['model'] / 1e6:.1f} million in the six counties, against {V0['obs_pass'] / 1e6:.1f} million passenger-vehicle miles from the State Highway Administration mileage reports. "
         "The reports give annual vehicle miles of all public roads by county and functional class. They are divided by 365, multiplied by the ratio of weekday to annual average daily traffic of the class, "
         "and multiplied by the passenger share of the class, both from the 2024 count stations of the region. "
         f"The ratio is {V0['ratio']:.2f}. The mean absolute percentage error is {V0['mape_county']:.0f}\\% by county and {V0['mape_fc']:.0f}\\% by functional class.")
C1 = pd.read_csv(f"{RD}/c1_vmt_county.csv")
rows = [[tx(CO.get(int(r.county), r.county)), num(r.mean / 1e6, 2), rng(r.min / 1e6, r.max / 1e6, 2), num(r.wkday_pass / 1e6, 2), num(r.mean / r.wkday_pass, 2)] for r in C1.itertuples()]
rows.append(["Six counties", num(C1["mean"].sum() / 1e6, 2), "", num(C1.wkday_pass.sum() / 1e6, 2), num(C1["mean"].sum() / C1.wkday_pass.sum(), 2)])
doc.table(["County", hd("Model", "(million miles)"), hd("Range of runs", "(million miles)"), hd("Observed", "(million miles)"), "Ratio"], rows, "lrrrr", "Weekday passenger-vehicle miles by county, model against the mileage reports.", midrules=(len(rows) - 1,))
C2 = pd.read_csv(f"{RD}/c1_vmt_fc.csv")
FCO = ["Interstate", "Other freeway, expressway", "Other principal arterial", "Minor arterial", "Collector", "Local"]
FCL = {"Interstate": "Interstate", "Other freeway, expressway": "Other freeway", "Other principal arterial": "Principal arterial", "Minor arterial": "Minor arterial", "Collector": "Collector", "Local": "Local"}
C2 = C2.set_index("fc").reindex([f for f in FCO if f in set(C2.fc)]).reset_index()
rows = [[tx(FCL.get(r.fc, r.fc)), num(r.mean / 1e6, 2), num(r.wkday_pass / 1e6, 2), num(r.mean / r.wkday_pass, 2)] for r in C2.itertuples()]
doc.table(["Functional class", hd("Model", "(million miles)"), hd("Observed", "(million miles)"), "Ratio"], rows, "lrrr", "Weekday passenger-vehicle miles by functional class.")
doc.figure(f"{RF}/fig_reg_vmt_matrix.pdf", "Model divided by observed weekday passenger-vehicle miles by county and road class. Blank: no mileage reported.")

# ------------------------------------------------------------------ speeds and travel times
doc.section("Travel times, commute and trip length")
SK = pd.read_csv(f"{RD}/c3_skim.csv"); sa = SK[SK.band == "all"].set_index("period")
short = SK[SK.band == "<5"]["median"]
doc.para("Travel times. The upstream stages (synthetic population, land use and activity model) read one fixed car skim: the base-year AM-peak times of the Maryland Statewide Transportation Model. "
         "The congested car trip times of the assignment are compared with it. The median ratio of assigned to skim time is "
         + ", ".join(f"{r['median']:.2f} ({p.split(' (')[0].replace('AM peak', 'morning peak').replace('PM peak', 'evening peak').replace('Midday', 'midday')})" for p, r in sa.iterrows())
         + f", and {short.min():.2f} to {short.max():.2f} for trips under 5 km. The assigned times are 18 to 31\\% shorter than the skim. "
         "The skim comes from another model and network, with its own zone connectors, intrazonal times and congestion, so it is slower than the assignment on the network used here. "
         "Every time-based check upstream (the commute of the synthetic workers, the commute of the land-use model and of the activity model, and destination choice) rests on this slower skim; "
         "the times the travellers experience in the assignment are shorter.")
SK = SK.assign(_o=SK.band.map({"<5": 0, "5–10": 1, "10–20": 2, "20–40": 3, "40+": 4, "all": 5}))
rows = [[tx(r.period), tx(r.band), thousands(r.n), num(r.median, 2), num(r.q25, 2) + "--" + num(r.q75, 2), num(r.ratio_of_sums, 2), num(r.mean_model_min, 1), num(r.mean_skim_min, 1)] for r in SK.itertuples()]
doc.table(["Period", "Distance (km)", "Trips", hd("Median", "ratio"), hd("Quartile", "range"), hd("Ratio of", "sums"), hd("Model mean", "(min)"), hd("Skim mean", "(min)")], rows, "llrrrrrr",
          "Car trip time of the assignment divided by the skim time, by period and distance band.", small="\\scriptsize")
doc.figure(f"{RF}/fig_reg_skim.pdf", "Car trip time of the assignment against the skim time by distance band.")
CF = pd.read_csv(f"{RD}/c2_commute_fit.csv")
mean_all = CF[(CF.table == "mean_all")].set_index("county"); mean_alone = CF[(CF.table == "mean_alone")].set_index("county")
rows = []
for c in list(CO) + ["region"]:
    t = CF[CF.county.astype(str) == str(c)].set_index("table"); k = str(c) if str(c) in mean_all.index else c
    rows.append([tx(CO.get(c, "Six counties")), num(mean_all.loc[k, "model"], 1), num(mean_all.loc[k, "observed"], 1), num(mean_alone.loc[k, "model"], 1), num(mean_alone.loc[k, "observed"], 1),
                 num(t.loc["B08303", "tvd"], 1), num(t.loc["B08302", "tvd"], 1), num(t.loc["B08301_mode", "tvd"], 1)])
doc.table(["Home county", hd("All modes,", "model (min)"), hd("All modes,", "ACS (min)"), hd("Drivers alone,", "model (min)"), hd("Drivers alone,", "ACS (min)"), hd("Time", "distance (pp)"), hd("Departure", "distance (pp)"), hd("Mode", "distance (pp)")], rows, "lrrrrrrr",
          "Commute of resident workers against the ACS: mean travel time and distance of the distributions.",
          note="Model commute: from the last departure from home to the first arrival at work, summing the times of all trips in between, so it includes stops on the way and the access, waiting and "
               "transfer times of transit. ACS: direct travel time to work; means from the 2020--2024 five-year tables (B08134, B08136), distributions from the 2024 one-year tables (B08303, B08302, B08301). "
               "Distance: total variation distance between the model and ACS distributions, in percentage points.", midrules=(len(rows) - 1,), small="\\scriptsize")
reg = SUM["commute"]
doc.para(f"The mean commute of all modes is {reg['mean_all']['model']:.1f} min in the model against {reg['mean_all']['observed']:.1f} min in the ACS. The difference is mostly one of definition: the model time includes "
         f"the stops made on the way to work and all transit times, and the model has more transit commuters ({100 * reg['pt_share'][0]:.1f}\\% against {100 * reg['pt_share'][1]:.1f}\\% in the ACS). "
         f"For drivers alone, whose trip is direct, the model gives {reg['mean_alone']['model']:.1f} min against {reg['mean_alone']['observed']:.1f} min, shorter as the assigned car times are. "
         "The activity model reports a shorter commute (33.8 min for Maryland) because it measures the time from the skim, not from the assignment.")
for f_, cap in [("fig_reg_commute_time", "Distribution of the commute travel time of resident workers, model and ACS 2024."),
                ("fig_reg_commute_departure", "Departure time of the commute to work, model and ACS 2024, as share of workers per hour of each bin (the bins have unequal width)."),
                ("fig_reg_commute_mode", "Mode to work, model and ACS 2024.")]:
    doc.figure(f"{RF}/{f_}.pdf", cap)
tl = SUM["triplength"]
doc.figure(f"{RF}/fig_reg_triplength.pdf", "Car-driver trip distance and time of residents, model against the 2017/18 travel survey and the 2022 national survey (large South Atlantic metropolitan areas with heavy rail).")
doc.para(f"Trip length. The total variation distance of the car-driver trip distance distribution from the 2017/18 travel survey is {tl['tvd_dist_rts']:.1f} percentage points, and {tl['tvd_dist_nhts']:.1f} from the 2022 national survey, "
         f"which has only {thousands(tl['nhts']['n'])} car-driver trips in the comparison area.")

# ------------------------------------------------------------------ modes
doc.section("Mode shares and transit")
M0 = MS[MS.dim == "All"].iloc[0]
modes = ["Car driver", "Car passenger", "Transit", "Walk", "Bike"]
rows = [[m, num(M0[f"model_{m}"], 1), rng(M0[f"model_min_{m}"], M0[f"model_max_{m}"], 2), num(M0[f"observed_{m}"], 1), num(M0[f"model_{m}"] - M0[f"observed_{m}"], 1, sign=True)] for m in modes]
doc.table(["Mode", "Model (\\%)", "Range of runs (\\%)", "Survey (\\%)", "Difference (pp)"], rows, "lrrrr", "Mode shares of the executed trips of residents, model against the 2017/18 travel survey.",
          note=f"The assignment does not change modes; the modes are those of the activity model, executed on the network. Survey: {thousands(M0.observed_n)} trip records of residents of the six counties, weighted. "
               f"Total variation distance {M0.tvd_pp:.1f} pp. Commute to work by public transport: {100 * reg['pt_share'][0]:.1f}\\% in the model against {100 * reg['pt_share'][1]:.1f}\\% in the ACS 2024.")
DOR = {"0–2 km": 0, "2–5 km": 1, "5–10 km": 2, "10–20 km": 3, "20+ km": 4}
MSd = MS[MS.dim != "All"].copy(); MSd["_o"] = [DOR.get(s, 0) if d == "Distance" else 0 for d, s in zip(MSd.dim, MSd.segment)]
MSd["_d"] = MSd.dim.map({d: i for i, d in enumerate(dict.fromkeys(MSd.dim))}); MSd = MSd.sort_values(["_d", "_o"], kind="stable")
rows = [[tx(r.segment), tx(r.dim), num(r.model_trip_share, 1), num(r["model_Car driver"], 1), num(r["observed_Car driver"], 1), num(r["model_Transit"], 1), num(r["observed_Transit"], 1), num(r.tvd_pp, 1)] for _, r in MSd.iterrows()]
doc.table(["Segment", "Split by", hd("Trip share", "(\\%)"), hd("Car driver,", "model (\\%)"), hd("Car driver,", "survey (\\%)"), hd("Transit,", "model (\\%)"), hd("Transit,", "survey (\\%)"), hd("Distance", "(pp)")], rows, "llrrrrrr",
          "Mode shares by home county, trip purpose, household cars and distance.", small="\\scriptsize")
seg = MS.set_index(["dim", "segment"])
def sv(d, s, c): return seg.loc[(d, s), c]
doc.para(f"Households without a car use transit for {sv('Household cars', 'No car', 'model_Transit'):.0f}\\% of their trips in the model against {sv('Household cars', 'No car', 'observed_Transit'):.0f}\\% in the survey, "
         f"and never drive (the survey has {sv('Household cars', 'No car', 'observed_Car driver'):.1f}\\% driving, in borrowed cars). They walk and ride as passengers instead. "
         f"In Baltimore City the model has {sv('Home county', 'Baltimore City', 'model_Car driver'):.0f}\\% car-driver trips against {sv('Home county', 'Baltimore City', 'observed_Car driver'):.0f}\\%, "
         f"and on trips to or from work {sv('Purpose', 'To or from work', 'model_Car driver'):.0f}\\% against {sv('Purpose', 'To or from work', 'observed_Car driver'):.0f}\\%: the car allocation in the household "
         "sends members without the car to passenger and transit modes. Trips of 2 to 5 km have the largest mode distance.")
doc.figure(f"{O['mode']}/figures/fig_mode_share.pdf", "Mode shares of resident trips, model and survey, overall and by segment. Right: transit share, model with the range of the runs.")
TR = pd.read_csv(f"{RD}/c4_transit.csv")
rows = [[tx(r.group), thousands(r.mean), thousands(r.max - r.min), thousands(r.awd_2024) if pd.notna(r.awd_2024) else "--", num(r.mean / r.awd_2024, 2) if pd.notna(r.awd_2024) else "--",
         thousands(r.awd_1718) if "awd_1718" in TR and pd.notna(r.awd_1718) else "--"] for r in TR.itertuples() if r.group not in ("WMATA", "Other operators")]
T0 = SUM["transit"]
doc.table(["Transit mode", hd("Model weekday", "boardings"), hd("Range of", "runs"), hd("Observed 2024", "weekday boardings"), "Ratio", hd("2017/18", "equivalent")], rows, "lrrrrr",
          "Weekday transit boardings of the Maryland Transit Administration by mode, model against the National Transit Database.",
          note="Model: boardings of the modelled persons. Observed: average typical weekday boardings 2024, all riders. 2017/18 equivalent: the 2024 weekday boardings times the ratio of the annual boardings "
               f"of 2017--2018 to those of 2024, the ridership before the fall of transit use after 2020. All modes: model {thousands(T0['model_mta'])}, observed {thousands(T0['obs_mta_2024'])} "
               f"(ratio {T0['ratio_2024']:.2f}), 2017/18 equivalent {thousands(T0['obs_mta_1718'])} (ratio {T0['ratio_1718']:.2f}). Boardings on other operators (Washington Metro and local systems) "
               "are not compared: the Database gives them for whole systems that extend far beyond the region.")
doc.para(f"The model has {T0['ratio_2024']:.1f} times the observed weekday boardings of 2024, and {T0['ratio_1718']:.1f} times the 2017/18 equivalent, although only part of the riders are modelled. "
         "The main known cause is in the activity model: on a transit tour the tour mode is applied to every trip of the tour, while in the survey only about 59\\% of the trips of transit tours use transit. "
         f"Each transit trip also makes one boarding per line used, so transfers add boardings. The modelled transit share of trips ({M0['model_Transit']:.1f}\\%) is close to the survey ({M0['observed_Transit']:.1f}\\%), but the transit share of commutes "
         f"({100 * reg['pt_share'][0]:.1f}\\%) is twice the ACS.")
doc.figure(f"{RF}/fig_reg_transit.pdf", "Weekday transit boardings by mode, model and observed.")
# ---- g. boardings by operator
rows = [[tx(r.operator), thousands(r.lines), thousands(r["mean"]), thousands(r["min"]) + "--" + thousands(r["max"])] for _, r in TA.iterrows()]
doc.table(["Operator and mode", "Lines", hd("Model weekday", "boardings"), hd("Range of", "runs")], rows, "lrrr", "Weekday boardings of the modelled persons by operator and mode.",
          note="Boardings of the modelled persons on every transit line of the network, from the transit events of the runs, by the operator of the line. The comparison with the National Transit Database above covers the five modes of the "
               "Maryland Transit Administration, for which the Database reports the system that serves the region. The other operators report whole systems that extend beyond the region (Washington Metro, the county systems of "
               "Montgomery and Prince George's, Amtrak), so no observed figure is set against them; their boardings are listed for completeness.")
OD = pd.read_csv(f"{RD}/c7_od_fit.csv")
rows = [[tx(CO.get(int(r.county), r.county)), num(r.own_model, 1), num(r.own_acs, 1), num(r.own_lodes, 1), num(r.tvd_acs, 1), num(r.tvd_lodes, 1)] for r in OD.itertuples()]
doc.table(["Home county", hd("Own-county", "work share, model (\\%)"), hd("Own-county, ACS", "2016--2020 (\\%)"), hd("Own-county,", "LODES 2022 (\\%)"), hd("Distance to", "ACS (pp)"), hd("Distance to", "LODES (pp)")], rows, "lrrrrr",
          "Work location of resident workers by home county: share working in the home county and distance of the distribution of workplace counties.",
          note="ACS: county-to-county commuting flows of the 2016--2020 five-year file, by county. The activity-model validation uses the 2024 one-year PUMS by place-of-work area, so its values differ. "
               "LODES 2022: origin--destination jobs. Model: resident workers with a work trip, county of the first workplace of the day.")

# ------------------------------------------------------------------ seeds and convergence
doc.section("Convergence and spread across runs")
doc.para(f"The {nw} runs differ only in the random seed. Across runs the ratio of model to count of any facility class varies by at most "
         f"{(F.ratio_max - F.ratio_min).max():.3f} between the smallest and largest run, and the total vehicle miles range from {V0['model_min'] / 1e6:.2f} to {V0['model_max'] / 1e6:.2f} million.")
doc.figure(f"{CD}/../figures/fig_convergence.pdf", f"Average score of the executed plans and car travel time of the residents by iteration, mean of the runs with the range of the runs (shaded). "
           f"The step after iteration {int(offinn * int(niter))} (dashed) is the end of rerouting and time shifting: from then on every person executes the best of his or her plans.")
# ---- h. convergence detail: score and travel-time plateau, stability of the link volumes, spread across runs
rows = [[f"Run {int(r.seed)}", num(r.score_change_80_90_pct, 2), num(r.score_change_90_100_pct, 2), num(r.score_change_95_100_pct, 2), num(r.car_hours_change_80_90_pct, 2), num(r.car_hours_change_90_100_pct, 2),
         num(r.car_hours_max_abs_step_last10_pct, 2), num(r.final_vs_mean5_weighted_abs_pct, 2), num(100 * r.daily_rel_range_upper_median, 1)] for r in CVS.itertuples()]
doc.table(["Run", hd("Score,", "80 to 90 (\\%)"), hd("Score,", "90 to 100 (\\%)"), hd("Score,", "95 to 100 (\\%)"), hd("Car hours,", "80 to 90 (\\%)"), hd("Car hours,", "90 to 100 (\\%)"), hd("Largest step,", "91 to 100 (\\%)"), hd("Final iteration", "against mean of", "last five (\\%)"), hd("Spread of daily", "link volume, last", "five (\\%)")], rows, "lrrrrrrrr",
          "Convergence of each run: change of the average executed score and of the car travel time over the last iterations, and stability of the link volumes.",
          note="Score: average score of the executed plans; car hours: car travel time of all residents; changes between the iterations named. Largest step: largest change between consecutive iterations from 91 to 100. "
               "Final iteration against mean: volume-weighted mean absolute difference between the car volume of the final iteration and the average of iterations 96 to 100, links with at least 1,000 vehicles per weekday. "
               "Spread of daily link volume: median over the same links of the summed hourly ranges (largest minus smallest of the five iterations) divided by the daily volume, an upper bound of the day-to-day variation.", small="\\scriptsize")
lr = LRG.groupby("hourly_threshold_expanded").mean(numeric_only=True)
rows = [[thousands(k), thousands(r.link_hours), num(100 * r.median_rel_range, 1), num(100 * r.mean_rel_range, 1), num(100 * r.share_rel_range_gt_10pct, 1), num(100 * r.share_rel_range_gt_25pct, 2)] for k, r in lr.iterrows()]
doc.table([hd("Hourly volume of", "at least (vehicles)"), hd("Link-hours", "per run"), hd("Median range", "(\\% of mean)"), hd("Mean range", "(\\% of mean)"), hd("Range above", "10\\% (\\% of link-hours)"), hd("Range above", "25\\% (\\% of link-hours)")], rows, "rrrrrr",
          "Variation of the hourly link volumes over the last five iterations, mean of the runs.", note="Range: largest minus smallest hourly volume of a link over iterations 96 to 100, divided by its mean; link-hours above the given hourly volume.")
rows = [[tx(r.group.replace(" thousand", "")), thousands(r.n), num(100 * r.median_cv, 2), num(100 * r.median_range_rel, 1), num(100 * r.p90_range_rel, 1)] for r in SSP.itertuples()]
doc.table(["Counted volume (thousand)", "Stations", hd("Median coefficient", "of variation (\\%)"), hd("Median range", "(\\% of mean)"), hd("90th percentile", "of range (\\%)")], rows, "lrrrr", f"Spread of the station volumes across the {nw} runs by volume group.",
          note="Coefficient of variation: standard deviation over the runs divided by the mean, per station. Range: largest minus smallest run divided by the mean.", midrules=(len(rows) - 1,))
cv = CVS.mean(numeric_only=True); l1k = lr.loc[1000]; sa = SSP.set_index("group")
doc.para(f"The average executed score rises by {cv.score_change_80_90_pct:.1f}\\% between iterations 80 and 90 and by {cv.score_change_90_100_pct:.1f}\\% between 90 and 100, the step at which rerouting and time shifting stop and every person "
         f"executes the best of his or her plans; over the last five iterations it changes by {cv.score_change_95_100_pct:.1f}\\%, and the gap between the best and the executed plan is {cv.score_best_minus_executed:.2f} score units. "
         f"The car travel time of all residents changes by {cv.car_hours_change_90_100_pct:.2f}\\% between iterations 90 and 100, with no step larger than {CVS.car_hours_max_abs_step_last10_pct.max():.2f}\\% between consecutive iterations. "
         "The mode shares cannot change in the assignment, so they are constant over the iterations. The link statistics of the final iteration are the average of iterations 96 to 100; the hourly volume of a link with at least "
         f"1,000 vehicles per hour varies over these five iterations by {100 * l1k.median_rel_range:.1f}\\% of its mean (median), and {100 * l1k.share_rel_range_gt_10pct:.2f}\\% of these link-hours vary by more than 10\\%. "
         f"The car volume of the final iteration differs from the five-iteration average by {cv.final_vs_mean5_weighted_abs_pct:.1f}\\% (volume-weighted, links above 1,000 vehicles per weekday). The volumes are therefore stable at the end of the runs; "
         f"the remaining variation is the noise of the 10\\% sample, which is also what separates the {nw} runs: the station volumes differ between the runs by a median of {100 * sa.loc['All stations'].median_range_rel:.1f}\\% of their mean, "
         f"{100 * sa.loc['over 60 thousand'].median_range_rel:.1f}\\% above 60,000 vehicles and {100 * sa.loc['0-5 thousand'].median_range_rel:.1f}\\% below 5,000, and the ratio of any facility class by at most {(F.ratio_max - F.ratio_min).max():.3f}.")
# ------------------------------------------------------------------ appendix: station table, interstates
doc.clear(); doc.section("Appendix: station table, interstates")
SDg = pd.read_csv(f"{DG}/stations_diagnostics.csv", dtype={"LOCATION_ID": str}, low_memory=False)
MP = {f["properties"]["LOCATION_ID"]: f["properties"].get("ID_MP") for f in json.load(open(f"{PRICING_HOME}/data/mdot_aadt_statewide_2015-2024.geojson"))["features"]}
I = SDg[(SDg.use == "mainline") & SDg.cls.isin(["Interstate: I-695", "Interstate: other"])].copy()
I["mp"] = pd.to_numeric(I.LOCATION_ID.map(MP), errors="coerce"); I["sw_ne"] = I.x + I.y
LN = pd.read_csv(f"{V}/data/count_stations_matched.csv", dtype={"LOCATION_ID": str}, low_memory=False).drop_duplicates("LOCATION_ID").set_index("LOCATION_ID")
I["lanes_sha"] = I.LOCATION_ID.map(LN.NUM_LANES); I["lanes_net"] = I.LOCATION_ID.map(LN.lanes_network_total)
ldiff = I.lanes_net - I.lanes_sha; lane_exact = float((ldiff == 0).mean()); lane_within1 = float((ldiff.abs() <= 1).mean()); lane_more = float((ldiff > 0).mean())
rnum = lambda r: int(re.sub(r"\D", "", str(r)) or 0)
routes = sorted(I.route.unique(), key=lambda r: (r != "I-695", rnum(r)))
doc.para(f"One row per mainline count station on the interstates: the {int((I.cls == 'Interstate: I-695').sum())} stations of I-695 and the {int((I.cls != 'Interstate: I-695').sum())} stations of the other interstates "
         f"({', '.join(r for r in routes if r != 'I-695')}), grouped by route and ordered along the route by the milepost of the count file (stations without a milepost follow, from south-west to north-east). "
         "Columns: Id, station of the State Highway Administration; location, description in the count file (obs. observed, sim. simulated, pass. passenger vehicles); dir., counted direction (NE north- or eastbound, SW south- or westbound, both); year, 2024 when counted in 2024, "
         "else e and the year of the last count behind the Administration's estimate; observed all vehicles (weekday) and passenger vehicles (less trucks and buses); simulated, all vehicles on the matched link(s), mean of five runs; "
         "lanes, the through lanes of the station in the count file (SHA) and the lanes of the matched network link(s), both directions summed (net.); "
         "ratio, simulated passenger vehicles divided by observed passenger vehicles; dev., in or out of the FHWA desirable deviation for the station's volume (all vehicles); flag, matching tier of the audit (ok, weak, doubt. for doubtful) "
         "and KB for stations within 5 km of the Key Bridge, whose estimates from counts before the closure of March 2024 do not show the diverted traffic. Route totals: sums over the stations of the route and their ratios "
         f"(passenger, and all vehicles in the dev. column). The network lane count equals the count file's at {100 * lane_exact:.0f}\\% of the interstate stations and lies within one lane at {100 * lane_within1:.0f}\\%; "
         f"where they differ the network mostly has more lanes ({100 * lane_more:.0f}\\% of the stations), because the matched link carries auxiliary and weaving lanes between close interchanges that the count file does not count as through lanes.")
rows = []; route_totals = []
for rt in routes:
    d = I[I.route == rt].sort_values(["mp", "sw_ne"], na_position="last")
    rows.append([f"\\multicolumn{{12}}{{l}}{{\\textbf{{{tx(rt)}}}: {len(d)} stations}}"])
    for r in d.itertuples():
        dirn = "NE" if r.NE_SPLIT == 100 else "SW" if r.SW_SPLIT == 100 else "both"
        yr = "2024" if r.counted24 else (f"e{2024 - int(r.count_age)}" if np.isfinite(r.count_age) else "e")
        flag = ("doubt." if r.doubtful else "weak" if r.weak else "ok") + (", KB" if r.key_bridge_km <= 5 else "")
        loc = r.STATION_DESC if isinstance(r.STATION_DESC, str) and r.STATION_DESC.strip() else str(r.ROADNAME)
        loc = re.sub(r"\bIs ?(\d)", r"I-\1", loc[:60].title()); loc = re.sub(r"\bMd ?(\d)", r"MD \1", loc); loc = re.sub(r"\bUs ?(\d)", r"US \1", loc); loc = loc.replace(" Of ", " of ").replace(" Mi ", " mi ").replace(" N Of", " N of").replace(" S Of", " S of").replace("#", "# ").replace("/", "/ ")
        rows.append([tx(r.LOCATION_ID), tx(loc[:60]), dirn, yr, str(int(r.lanes_sha)) if np.isfinite(r.lanes_sha) else "--", str(int(r.lanes_net)) if np.isfinite(r.lanes_net) else "--",
                     thousands(r.count_all), thousands(r.count_pass), thousands(r.model_all_mean), num(r.ratio_pass, 2), "in" if r.within_fhwa else "out", tx(flag)])
    oa, op, sm, sp = d.count_all.sum(), d.count_pass.sum(), d.model_all_mean.sum(), d.model_car_mean.sum()
    route_totals.append(dict(route=rt, stations=len(d), observed_all=oa, observed_pass=op, simulated_all=sm, simulated_pass=sp, ratio_all=sm / oa, ratio_pass=sp / op))
    rows.append([f"\\multicolumn{{6}}{{l}}{{\\textit{{{tx(rt)} total}}}}", thousands(oa), thousands(op), thousands(sm), num(sp / op, 2), f"all {sm / oa:.2f}", ""])
doc.longtable(["Id", "Location", "Dir.", "Year", hd("SHA", "lanes"), hd("Net.", "lanes"), hd("Obs.", "all"), hd("Obs.", "pass."), hd("Sim.", "all"), "Ratio", "Dev.", "Flag"], rows, "lL{0.125\\textwidth}llrrrrrrll",
              "Station table of the interstates: observed and simulated weekday traffic at every mainline count station, by route.", small="\\footnotesize")
pd.DataFrame(route_totals).to_csv(f"{DG}/interstate_route_totals.csv", index=False, float_format="%.4g")
print(pd.DataFrame(route_totals).round(3).to_string())
pages, errs, over = doc.build(a.out)
