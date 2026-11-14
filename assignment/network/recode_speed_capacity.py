#!/usr/bin/env python3
"""Recode free speed and capacity of the surface-street classes of network_2024 from posted speeds and a published default table.

Scope: car links whose OSM class is primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, unclassified, residential or
living_street.  Freeways, expressways and their ramps (motorway, trunk, *_link of those, HCM capacities), the I-95 Express Toll Lanes merge link,
transit-only links, the Key Bridge closure, the topology and the link ids are not touched.  No traffic count enters this script.

Rules (sources and results in SPEED_CAPACITY.md):
 1. Posted speed of the link, first available of
    a. the OSM maxspeed tag of the link's way (Geofabrik Maryland extract 2026-06-11; PRICING_HOME/data/network_v8/osm_way_tags.csv);
    b. MDOT SHA posted-speed-limit signs attached to links of the same way (data/network_audit_links.parquet, column mdot_sign_mph; median);
    c. median posted speed (a or b) of links of the same road name and class in the same 5 km cell;
    d. median posted speed (a or b) of links of the same class in the same 5 km cell (at least 5 links): local area-type proxy;
    e. median posted speed (a or b) of the class in the whole network.
 2. Free speed = posted x urban factor, with the urban factor of the MATSim OSM network reader (matsim-libs contrib osm 2025.0,
    LinkProperties.calculateSpeedIfSpeedTag): 0.9 when the posted speed is below 51 km/h (i.e. 25 and 30 mph), 1.0 otherwise.
    The same rule applies to every class in scope.
 3. Capacity = capacity per lane of the class x max(lanes, 1), per-lane values of the same MATSim OSM reader (LinkProperties.create*):
    primary and primary_link 1,500; secondary and secondary_link 800; tertiary, tertiary_link, unclassified, residential 600; living_street 300.
    The class is the MDOT-reconciled class of the supply network (PRICING_HOME/data/network_v8/link_changes.csv, column 'profile':
    OSM class, or the MDOT functional class where MDOT rates the road higher).
Usage: python3 assignment/network/recode_speed_capacity.py <network in> <network out> [<pt network in> <pt network out>]
Writes link_speed_capacity_2024.csv.gz (old/new per link) and prints the summary by class.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, gzip
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netio

HERE = f"{WORKSPACE}/4_matsim/network"; MPH = 2.23694   # HERE: network files and outputs (workspace)
SCOPE = ["primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street"]
CPL = {"primary": 1500, "primary_link": 1500, "secondary": 800, "secondary_link": 800, "tertiary": 600, "tertiary_link": 600,
       "unclassified": 600, "residential": 600, "living_street": 300}
URBAN_KMH, URBAN_FACTOR = 51.0, 0.9

net_in, net_out = sys.argv[1], sys.argv[2]
pt_in, pt_out = (sys.argv[3], sys.argv[4]) if len(sys.argv) > 4 else (None, None)

nodes, L = netio.read_network(net_in)
E = L[L.car & L.hwy.isin(SCOPE) & ~L.index.str.startswith(("hot", "keybridge", "etl_", "pt_"))].copy()
print(f"network {len(L):,} links; in scope {len(E):,} car links")

# ---- 1. posted speed
O = netio.osm_way_tags()
E["posted"] = E.way.map(O.posted_mph); E["src"] = np.where(E.posted.notna(), "a OSM maxspeed", "")
A = pd.read_parquet(f"{netio.DATA}/network_audit_links.parquet", columns=["way", "mdot_sign_mph"])
sign_way = A.dropna(subset=["mdot_sign_mph"]).groupby("way").mdot_sign_mph.median()
k = E.posted.isna(); E.loc[k, "posted"] = E.way[k].map(sign_way); E.loc[k & E.posted.notna(), "src"] = "b MDOT sign"
E["cell"] = (E.xm // 5000).astype(int).astype(str) + "_" + (E.ym // 5000).astype(int).astype(str)
obs = E[E.posted.notna()]
by_name = obs[obs.name != ""].groupby(["name", "hwy", "cell"]).posted.median()
k = E.posted.isna() & (E.name != "")
E.loc[k, "posted"] = [by_name.get((n, h, c), np.nan) for n, h, c in zip(E.name[k], E.hwy[k], E.cell[k])]
E.loc[k & E.posted.notna(), "src"] = "c same road, 5 km cell"
g = obs.groupby(["hwy", "cell"]).posted.agg(["median", "size"]); by_cell = g["median"][g["size"] >= 5]
k = E.posted.isna()
E.loc[k, "posted"] = [by_cell.get((h, c), np.nan) for h, c in zip(E.hwy[k], E.cell[k])]
E.loc[k & E.posted.notna(), "src"] = "d class, 5 km cell"
by_cls = obs.groupby("hwy").posted.median()
k = E.posted.isna(); E.loc[k, "posted"] = E.hwy[k].map(by_cls); E.loc[k, "src"] = "e class, network"
assert E.posted.notna().all()

# ---- 2. free speed
pk = E.posted / MPH * 3.6
E["fs_new"] = (E.posted / MPH * np.where(pk < URBAN_KMH, URBAN_FACTOR, 1.0)).round(4)

# ---- 3. capacity
P = pd.read_csv(f"{PRICING_HOME}/data/network_v8/link_changes.csv", dtype={"link": str}, usecols=["link", "profile"]).set_index("link").profile
E["cls"] = pd.Series(E.index.map(P), index=E.index).fillna(E.hwy)
E.loc[~E.cls.isin(CPL.keys()), "cls"] = E.hwy
E["cap_new"] = (E.cls.map(CPL) * E.permlanes.clip(lower=1)).round(1)

NEW = E[["fs_new", "cap_new"]].to_dict("index")
def write(src, dst):
    n = 0
    with gzip.open(src, "rt") as fi, gzip.open(dst, "wt") as fo:
        for line in fi:
            if "<link " in line:
                m = re.search(r'<link id="([^"]+)"', line)
                v = NEW.get(m.group(1)) if m else None
                if v:
                    line = re.sub(r'freespeed="[^"]+"', f'freespeed="{v["fs_new"]:.4f}"', line, count=1)
                    line = re.sub(r'capacity="[^"]+"', f'capacity="{v["cap_new"]:.1f}"', line, count=1); n += 1
            fo.write(line)
    print(f"{os.path.basename(dst)}: {n:,} links rewritten"); return n
n1 = write(net_in, net_out)
if pt_in: n2 = write(pt_in, pt_out); assert n2 == n1, (n1, n2)

# ---- report
E["changed"] = (abs(E.fs_new - E.freespeed) > 1e-3) | (abs(E.cap_new - E.capacity) > 0.05)
E[["hwy", "cls", "name", "way", "permlanes", "posted", "src", "freespeed", "fs_new", "capacity", "cap_new", "changed"]].to_csv(f"{HERE}/link_speed_capacity_2024.csv.gz", float_format="%.4f")
car = L[L.car & ~L.is_pt]
S = E.groupby("hwy").agg(links=("hwy", "size"), posted_mph_med=("posted", "median"), tagged=("src", lambda s: s.str.startswith(("a", "b")).mean()),
                         fs_old_kmh=("freespeed", lambda s: s.median() * 3.6), fs_new_kmh=("fs_new", lambda s: s.median() * 3.6),
                         cap_old=("capacity", "median"), cap_new=("cap_new", "median"), changed=("changed", "mean")).reindex(SCOPE)
pd.set_option("display.width", 200); print(S.round(2).to_string())
print("posted-speed source:", E.src.value_counts(normalize=True).round(3).to_dict())
print(f"links changed: {E.changed.sum():,} of {len(E):,} in scope ({E.changed.mean():.1%}); {E.changed.sum() / len(car):.1%} of all {len(car):,} car links")
S.to_csv(f"{HERE}/speed_capacity_summary_2024.csv", float_format="%.3f")
