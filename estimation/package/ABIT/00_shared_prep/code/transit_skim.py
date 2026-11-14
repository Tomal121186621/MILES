#!/usr/bin/env python3
"""Transit feedback of the integrated loop: AM-peak zone-to-zone transit travel times from the pt2matsim-mapped MTA schedule of a
network year, routed with MATSim's SwissRailRaptor (pipeline/java/TransitSkim.java on the chain's MATSim 2024.0 jar).
  1. zone centroids (zone shapefile, 1,588 MSTM zones, EPSG:26985) -> centroids.csv; zones more than 4 km from a network node are
     "off-network" (the same rule as matsim_to_skim.py: the MSTM zone system covers six states, the network the Baltimore region)
  2. TransitSkim: one raptor tree per origin and departure time (PEAK_FROM .. PEAK_TO every STEP minutes), walk access and egress
     within the search radius, in-vehicle, waiting and transfer times; a departure counts when it arrives within MAX_TT minutes, the
     pair is reachable when half of the departures count and its value is the mean over those; routed on the
     full schedule (ALL) and on the bus-only schedule (BUS); RAILSHARE = share of departures whose best path uses light rail,
     metro or MARC
  3. matrices in the conventions of the 2016 base skims: SILO transit_peak_time = ALL (1000 = no transit path, 5.0 intra-zonal);
     ABIT bus_tt = BUS (1000, 5.0); ABIT rail_tt00 = ALL where the best path uses rail in at least half of the departures, else 0
     (0 = no rail path, 0 intra-zonal).  Pairs with an off-network endpoint keep the prior (the base skims); on-network pairs
     without a path are unreachable (1000 / 0) - the MTA feeds are the transit supply of the modelled region.
  4. output: <out_dir>/{transit_peak_time,bus_tt,rail_tt00}.csv.gz (FROM,TO,VALUE minutes; door to door), transit_peak_time_ivtwait.csv.gz
     (the same path without the walk legs, for the comparison with the base skims' convention), <out_dir>/transit_skim_stats.json
     (counts, reachability, comparison with the base skims: correlation, mean, share unreachable on BMR-internal pairs) and the raw
     raptor table <out_dir>/raptor_pairs.csv.gz.
Usage: transit_skim.py <network_pt.xml.gz> <schedule.xml.gz> <vehicles.xml.gz> <out_dir> [--peak 7 9] [--step 15] [--radius 4000]
       [--extension 2000] [--threads 4] [--xmx 6g] [--prior-silo DIR] [--prior-abit DIR]"""
# COPY of Validation_2026/pipeline/transit_skim.py (manual-estimation package, 2026-11-13); only path constants changed (lines marked PATH).
import os as _os_pkg  # PACKAGE: paths of the manual-estimation package
_PKG_HERE = _os_pkg.path.dirname(_os_pkg.path.abspath(__file__))
SHARED = _os_pkg.path.abspath(_os_pkg.path.join(_PKG_HERE, "..", "..", "00_shared_data"))          # provided inputs
RAW = _os_pkg.environ.get("ABIT_RAW", _os_pkg.path.join(SHARED, "raw"))                                                              # your downloads
REBUILT = _os_pkg.environ.get("ABIT_REBUILT", _os_pkg.path.join(SHARED, "rebuilt"))                  # outputs of this chain
MDATA = REBUILT
import sys, os, re, gzip, json, time, argparse, subprocess, numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree
ROOT = SHARED; V = SHARED  # PATH
JAR = f"{RAW}/matsim_tools/baltimore-matsim-1.0.jar"; CLASSES = f"{RAW}/matsim_tools/classes"; JAVA_SRC = f"{_PKG_HERE}/TransitSkim.java"  # PATH
SHP = f"{RAW}/mstm_zone_system/SMZ_RMZ_02152011inMSTM_EPSG26918.shp"; ZONES_CSV = f"{RAW}/mstm_zone_system/zoneSystem.csv"  # PATH
UNREACH, INTRA = 1000.0, 5.0

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("network"); ap.add_argument("schedule"); ap.add_argument("vehicles"); ap.add_argument("out_dir")
ap.add_argument("--peak", nargs=2, type=float, default=[7, 9]); ap.add_argument("--step", type=float, default=15, help="departure draws every STEP minutes")
ap.add_argument("--radius", type=float, default=1600, help="walk access/egress radius around a centroid [m]: one mile; the assignment router searches 4,000 m (sensitivity in TRANSIT_BUILD.md)"); ap.add_argument("--extension", type=float, default=0)
ap.add_argument("--max-tt", type=float, default=180, help="minutes; a departure arriving later does not count, a pair needs half the departures within it"); ap.add_argument("--threads", type=int, default=4); ap.add_argument("--xmx", default="6g")
ap.add_argument("--prior-silo", default=f"{RAW}/mstm_skims_2016_csv"); ap.add_argument("--prior-abit", default=f"{SHARED}/skims/abit_base_2016")  # PATH
a = ap.parse_args(); os.makedirs(a.out_dir, exist_ok=True); t0 = time.time()
JAVA = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"

# ---- zones, centroids, off-network flag (as matsim_to_skim.py)
Z = gpd.read_file(SHP).to_crs(26985); Z["zone"] = Z.SMZRMZ.astype(int); Z = Z.sort_values("zone").reset_index(drop=True); c = Z.geometry.representative_point()
zones = Z.zone.values; n = len(zones); zidx = {z: i for i, z in enumerate(zones)}
nodes = []
with gzip.open(a.network, "rt") as f:
    for line in f:
        if "<node " in line:
            m = re.search(r'x="([^"]+)" y="([^"]+)"', line); nodes.append((float(m.group(1)), float(m.group(2))))
d, _ = cKDTree(np.array(nodes)).query(np.c_[c.x.values, c.y.values]); off = d > 4000
cty = pd.read_csv(ZONES_CSV, usecols=["ZoneId", "COUNTYFIPS"]).set_index("ZoneId").COUNTYFIPS
bmr = np.isin(cty.reindex(zones).values, [24003, 24005, 24510, 24013, 24025, 24027])
print(f"zones {n}, off-network (> 4 km from a node) {off.sum()}, BMR zones {bmr.sum()}")
cent = f"{a.out_dir}/centroids.csv"; pd.DataFrame({"zone": zones, "x": c.x.values, "y": c.y.values}).to_csv(cent, index=False)

# ---- raptor
if not os.path.exists(f"{CLASSES}/de/umd/skim/TransitSkim.class") or os.path.getmtime(JAVA_SRC) > os.path.getmtime(f"{CLASSES}/de/umd/skim/TransitSkim.class"):
    os.makedirs(CLASSES, exist_ok=True); subprocess.run([JAVA.replace("/bin/java", "/bin/javac"), "-nowarn", "-d", CLASSES, "-cp", JAR, JAVA_SRC], check=True)
raw = f"{a.out_dir}/raptor_pairs.csv.gz"; log = f"{a.out_dir}/raptor.log"
cmd = [JAVA, f"-Xmx{a.xmx}", "-cp", f"{CLASSES}:{JAR}", "de.umd.skim.TransitSkim", a.network, a.schedule, a.vehicles, cent, raw, str(a.peak[0]), str(a.peak[1]), str(a.step), str(a.radius), str(a.extension), str(a.threads), str(a.max_tt)]
print("raptor:", " ".join(cmd[4:]), flush=True)
with open(log, "w") as lf: rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode
tail = [l.strip() for l in open(log) if not re.match(r"^\d{4}-\d\d-\d\dT", l)]
print("\n".join("  " + l for l in tail[-6:]))
if rc != 0: raise SystemExit(f"TransitSkim failed (rc {rc}); see {log}")

# ---- matrices
R = pd.read_csv(raw); i, j = R.FROM.map(zidx).values, R.TO.map(zidx).values
ALL = np.full((n, n), np.nan); BUS = np.full((n, n), np.nan); RS = np.zeros((n, n)); ACC = np.full((n, n), np.nan); EGR = np.full((n, n), np.nan)
ALL[i, j] = R.ALL.values; BUS[i, j] = R.BUS.values; RS[i, j] = R.RAILSHARE.values; ACC[i, j] = R.ACCESS.values; EGR[i, j] = R.EGRESS.values
def prior(path):
    pr = pd.read_csv(path); P = np.full((n, n), np.nan); sel = pr.FROM.isin(zidx) & pr.TO.isin(zidx)
    P[pr.FROM[sel].map(zidx).values, pr.TO[sel].map(zidx).values] = pr.VALUE[sel].values; return P
bad = off[:, None] | off[None, :]   # an endpoint beyond the network: the prior
mats = {}
IVW = ALL - ACC - EGR   # in-vehicle + waiting + transfer time of the full-schedule path (no access/egress walk): written as transit_peak_time_ivtwait for the convention question (TRANSIT_BUILD.md)
for name, M, pr_path, unreach, intra in [("transit_peak_time", ALL, f"{a.prior_silo}/transit_peak_time.csv.gz", UNREACH, INTRA), ("bus_tt", BUS, f"{a.prior_abit}/bus_tt.csv.gz", UNREACH, INTRA),
                                        ("rail_tt00", np.where(RS >= 0.5, ALL, 0.0), f"{a.prior_abit}/rail_tt00.csv.gz", 0.0, 0.0),
                                        ("transit_peak_time_ivtwait", IVW, f"{a.prior_silo}/transit_peak_time.csv.gz", UNREACH, INTRA)]:
    X = M.copy(); X[np.isnan(X)] = unreach; np.fill_diagonal(X, intra)
    P = prior(pr_path); use = bad & ~np.isnan(P); X[use] = P[use]; mats[name] = X
    F, T = np.meshgrid(zones, zones, indexing="ij")
    with gzip.open(f"{a.out_dir}/{name}.csv.gz", "wt") as fo:
        fo.write("FROM,TO,VALUE\n"); np.savetxt(fo, np.c_[F.ravel(), T.ravel(), X.ravel()], fmt="%d,%d,%.3f")

# ---- statistics and comparison with the base
offd = ~np.eye(n, dtype=bool); onnet = ~bad & offd; bmrp = bmr[:, None] & bmr[None, :] & offd
reach_all = ~np.isnan(ALL) & onnet; reach_bus = ~np.isnan(BUS) & onnet
stats = {"network": a.network, "schedule": a.schedule, "vehicles": a.vehicles, "peak_h": a.peak, "step_min": a.step, "search_radius_m": a.radius, "extension_radius_m": a.extension, "max_tt_min": a.max_tt,
         "zones": int(n), "off_network_zones": int(off.sum()), "pairs_from_prior": float(bad[offd].mean()), "raptor_log_tail": tail[-4:],
         "on_network_pairs": int(onnet.sum()), "reachable_share_on_network": {"all": float(reach_all.sum() / onnet.sum()), "bus": float(reach_bus.sum() / onnet.sum()), "rail_used": float(((RS >= 0.5) & onnet).sum() / onnet.sum())},
         "mean_min_reachable": {"all": float(np.nanmean(ALL[reach_all])), "bus": float(np.nanmean(BUS[reach_bus])), "access_walk": float(np.nanmean(ACC[reach_all])), "egress_walk": float(np.nanmean(EGR[reach_all]))},
         "compare_base_bmr_internal": {}}
for name, pr_path in [("transit_peak_time", f"{a.prior_silo}/transit_peak_time.csv.gz"), ("bus_tt", f"{a.prior_abit}/bus_tt.csv.gz"), ("rail_tt00", f"{a.prior_abit}/rail_tt00.csv.gz")]:
    P = prior(pr_path); X = mats[name]; unreach = UNREACH if name != "rail_tt00" else 0.0
    both = bmrp & (X != unreach) & (P != unreach) & ~np.isnan(P)
    rec = {"share_unreachable_new": float((X[bmrp] == unreach).mean()), "share_unreachable_base": float((P[bmrp] == unreach).mean()),
           "mean_new": float(X[bmrp & (X != unreach)].mean()) if (bmrp & (X != unreach)).any() else None, "mean_base": float(P[bmrp & (P != unreach)].mean()),
           "pairs_reachable_both": int(both.sum()), "corr_both": float(np.corrcoef(X[both], P[both])[0, 1]) if both.sum() > 2 else None,
           "mean_new_both": float(X[both].mean()) if both.any() else None, "mean_base_both": float(P[both].mean()) if both.any() else None,
           "median_ratio_both": float(np.median(X[both] / np.maximum(P[both], 0.1))) if both.any() else None}
    stats["compare_base_bmr_internal"][name] = rec
    print(f"{name}: BMR-internal pairs unreachable new {rec['share_unreachable_new']:.1%} vs base {rec['share_unreachable_base']:.1%}; reachable in both {rec['pairs_reachable_both']:,}: mean new {rec['mean_new_both']:.1f} vs base {rec['mean_base_both']:.1f} min, corr {rec['corr_both']:.3f}, median ratio {rec['median_ratio_both']:.2f}" if both.any() else f"{name}: no common reachable pairs")
stats["duration_s"] = round(time.time() - t0, 1); json.dump(stats, open(f"{a.out_dir}/transit_skim_stats.json", "w"), indent=1)
print(f"reachable on-network pairs: all {stats['reachable_share_on_network']['all']:.1%}, bus {stats['reachable_share_on_network']['bus']:.1%}, rail used {stats['reachable_share_on_network']['rail_used']:.1%}; mean {stats['mean_min_reachable']['all']:.1f} min (access walk {stats['mean_min_reachable']['access_walk']:.1f}, egress {stats['mean_min_reachable']['egress_walk']:.1f}); pairs from the prior {stats['pairs_from_prior']:.1%}")
print(f"written {a.out_dir}/{{transit_peak_time,bus_tt,rail_tt00}}.csv.gz in {stats['duration_s']} s")
