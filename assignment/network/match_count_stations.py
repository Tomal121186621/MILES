#!/usr/bin/env python3
"""Match the MDOT SHA AADT stations of the six study-area counties to links of the 2024 network, direction by direction, and split the
matched stations into two halves (seed 2026, stratified by MDOT functional system) before any assignment is run.

Matching rule: a station is a point on a road with a functional system F_SYSTEM (1-7), a lane count and directional shares (north/east and
south/west).  For each of the two directions the nearest car link within the tolerance whose class is compatible with the station's
(same MDOT class attached to the link in the audit, or the equivalent OSM class group; ramp stations only to ramp links) is taken.
Tolerance 60 m for F_SYSTEM 1-2 (divided freeways, station point between the carriageways), 40 m otherwise.
Flags: 'ambiguous' when another compatible link on a different road lies within 1.5 x the matched distance (or within 10 m of it);
'one_direction' when only one direction is found; 'name_differs' when no word of the MDOT road name occurs in the OSM name;
'outside_scc' when the link is not in the strongly connected component.

Road identity (added in the rematch): the nearest link is kept when it is the counted road (MDOT route = the link's MDOT route in the audit, or
the MDOT road name shares a word with the OSM name); if it is not, and a parallel link (same direction, bearing within 20 deg) inside the tolerance
is the counted road, that link is taken ('rematched_identity').  A two-way count (north/east and south/west shares both > 0) with one direction
matched takes the other carriageway: the nearest link within 150 m of the station, running opposite to the matched link (bearing within 30 deg of
reverse), same MDOT route or same OSM name, non-ramp, compatible class ('second_carriageway').  One-way counts (a share of 100) keep the one link of the
counted direction.  Column match_category: two_way_ok, oneway_ok (a), second_carriageway_added (b), other_carriageway_missing (c),
oneway_direction_conflict (d); match_review gives the reason.  Nothing here uses volumes.  Manual overrides: data/count_station_overrides.csv.
Inputs: I695_pricing/data/mdot_aadt_statewide_2015-2024.geojson (MDOT SHA AADT, 2015-2024), data/network_audit_links.parquet (audit_network.py).
Outputs: data/count_stations_matched.csv (every station in the area, matched or not, with distances and both classes),
         data/count_stations_split.csv (matched stations with 2024 AADT: calibration_check / held_out).
Nothing is fitted to the counts; the split exists so that the held-out half is never looked at before the final comparison.
"""
import os, sys, re, json, datetime
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely import points
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netio import *

SEED = 2026
A = pd.read_parquet(f"{DATA}/network_audit_links.parquet")
counties, area = study_area()
G = json.load(open(f"{ROOT}/I695_pricing/data/mdot_aadt_statewide_2015-2024.geojson"))
S = gpd.GeoDataFrame.from_features(G["features"], crs=CRS)
S = S[S.within(area)].reset_index(drop=True)
S["x"] = S.geometry.x; S["y"] = S.geometry.y
print(f"stations in the six counties: {len(S):,}; with AADT 2024: {S.AADT_2024.notna().sum():,}; mainline: {(S.MAIN_LINE == 1).sum():,}")

FS_TO_OSM = {1: {1, 2}, 2: {1, 2}, 3: {3}, 4: {4}, 5: {5}, 6: {5}, 7: {7}}
geoms = link_geoms(A); tree = shapely.STRtree(geoms)
def is_ne(b): return ((b % 360) < 135) | ((b % 360) >= 315)
A["dir_ne"] = is_ne(A.bearing.values)
STOP = {"RD", "ROAD", "ST", "AVE", "BLVD", "HWY", "PKWY", "DR", "LN", "WAY", "N", "S", "E", "W", "NB", "SB", "EB", "WB", "THE", "OF", "AT", "TO", "AND", "MD", "US", "IS", "I", "RAMP", "FR", "LOOP", "INNER", "OUTER"}
def name_ok(mdot, osm):
    if not isinstance(mdot, str) or not isinstance(osm, str) or osm == "": return np.nan
    a = {w for w in re.split(r"[^A-Z0-9]+", mdot.upper()) if w and w not in STOP and len(w) > 2}; b = set(re.split(r"[^A-Z0-9]+", osm.upper()))
    return bool(a & b) if a else np.nan

OV = pd.read_csv(f"{DATA}/count_station_overrides.csv", dtype=str).fillna("").set_index("LOCATION_ID") if os.path.exists(f"{DATA}/count_station_overrides.csv") else pd.DataFrame()
def bdiff(a, b): return np.abs((a - b + 180) % 360 - 180)
def route_of(s): return f"{s.ID_PREFIX} {int(s.ID_RTE_NO)}" if pd.notna(s.ID_PREFIX) and pd.notna(s.ID_RTE_NO) else ""
def ident(sroute, sname, lk):
    """2 = MDOT route and name agree (or name unknown), 1 = route or name agrees, 0 = neither."""
    nm = None if (not isinstance(sname, str) or sname.upper().startswith("NO NAME")) else name_ok(sname, lk["name"])
    rt = bool(sroute) and lk.mdot_route == sroute
    return 2 if (rt and nm is not False) else 1 if (rt or nm is True) else 0
R_OPP, R_SEARCH = 30, 150
rows = []
for i, s in S.iterrows():
    fs = int(s.F_SYSTEM) if pd.notna(s.F_SYSTEM) else 7
    tol = 60 if fs <= 2 else 40
    ramp_station = (s.MAIN_LINE != 1)
    pt = points(s.x, s.y); cand = tree.query(pt, predicate="dwithin", distance=tol)
    C = A.iloc[cand].copy(); C["dist"] = shapely.distance(geoms[cand], pt)
    if ramp_station: C = C[C.is_ramp]
    else: C = C[~C.is_ramp & ((C.mdot_fc == fs) | C.osm_group.isin(FS_TO_OSM[fs]))]
    rec = dict(LOCATION_ID=s.LOCATION_ID, COUNTY=s.COUNTY_DESC, ROADNAME=s.ROADNAME, ROUTEID=s.ROUTEID_RH, STATION_DESC=s.STATION_DESC, F_SYSTEM=fs, F_SYSTEM_DESC=s.F_SYSTEM_DESC, MAIN_LINE=s.MAIN_LINE,
               NUM_LANES=s.NUM_LANES, PEAK_HOUR_DIRECTION=s.PEAK_HOUR_DIRECTION, NE_SPLIT=s.NORTH_EAST_SPLIT, SW_SPLIT=s.SOUTH_WEST_SPLIT, COUNTED_2024=None, AADT_2024=s.AADT_2024, AAWDT_2024=s.AAWDT_2024, AADT_2023=s.AADT_2023,
               CAR_AADT=s.CAR_AADT, LIGHT_TRUCK_AADT=s.LIGHT_TRUCK_AADT, SINGLE_UNIT_AADT=s.SINGLE_UNIT_AADT, COMBINATION_UNIT_AADT=s.COMBINATION_UNIT_AADT, x=s.x, y=s.y, tolerance_m=tol, n_candidates=len(C))
    flags = []
    for d, lab in ((True, "NE"), (False, "SW")):
        D = C[C.dir_ne == d].sort_values("dist")
        if len(D) == 0:
            rec.update({f"link_{lab}": "", f"dist_{lab}": np.nan, f"hwy_{lab}": "", f"mdot_fc_{lab}": np.nan, f"lanes_{lab}": np.nan, f"name_{lab}": "", f"in_scc_{lab}": np.nan}); continue
        best = D.iloc[0]; sroute = route_of(s)
        if not ramp_station:
            sc = D.apply(lambda lk: ident(sroute, s.ROADNAME, lk), axis=1)
            if sc.loc[best.name] == 0:
                alt = D[(sc > 0) & (bdiff(D.bearing, best.bearing) <= 20)]
                if len(alt): flags.append(f"rematched_identity_{lab}:{best.name}->{alt.index[0]}"); best = alt.iloc[0]
                else:   # the nearest link is not the counted road and no parallel link is: look up to 2 x tolerance for a link that is (route and name agree)
                    cw = tree.query(pt, predicate="dwithin", distance=2 * tol); W = A.iloc[cw].copy(); W["dist"] = shapely.distance(geoms[cw], pt)
                    W = W[~W.is_ramp & (W.dir_ne == d) & ((W.mdot_fc == fs) | W.osm_group.isin(FS_TO_OSM[fs]))]
                    if len(W):
                        W = W[W.apply(lambda lk: ident(sroute, s.ROADNAME, lk) == 2, axis=1)].sort_values("dist")
                        if len(W): flags.append(f"rematched_identity_wide_{lab}:{best.name}->{W.index[0]}@{W.dist.iloc[0]:.0f}m"); best = W.iloc[0]; best["dist"] = W.dist.iloc[0]
        rec.update({f"link_{lab}": best.name, f"dist_{lab}": round(best.dist, 1), f"hwy_{lab}": best.hwy, f"mdot_fc_{lab}": best.mdot_fc, f"lanes_{lab}": best.permlanes, f"name_{lab}": best["name"], f"in_scc_{lab}": bool(best.in_scc), f"freespeed_mph_{lab}": round(best.freespeed_mph, 1), f"capacity_{lab}": best.capacity})
        other = D[(D["name"] != best["name"]) & (D.index != best.name) & (D.dist <= max(1.5 * best.dist, best.dist + 10))]
        if not ramp_station and len(other):   # identity decides: a nearby link that is less the counted road than the matched one is not an ambiguity
            other = other[other.apply(lambda lk: ident(sroute, s.ROADNAME, lk), axis=1) >= ident(sroute, s.ROADNAME, best)]
        if len(other): flags.append(f"ambiguous_{lab}:{other.index[0]}@{other.dist.iloc[0]:.0f}m")
        if name_ok(s.ROADNAME, best["name"]) is False: flags.append(f"name_differs_{lab}")
        if not best.in_scc: flags.append(f"outside_scc_{lab}")
    n_dir = int(rec["link_NE"] != "") + int(rec["link_SW"] != "")
    rec.setdefault("match_review", ""); rec["match_category"] = ""
    two_way_count = (s.NORTH_EAST_SPLIT > 0 and s.SOUTH_WEST_SPLIT > 0 and pd.notna(s.NORTH_EAST_SPLIT) and pd.notna(s.SOUTH_WEST_SPLIT))
    if n_dir == 1 and not ramp_station:
        have, miss = ("NE", "SW") if rec["link_NE"] != "" else ("SW", "NE"); L0 = A.loc[rec[f"link_{have}"]]; sroute = route_of(s)
        if two_way_count:
            cand2 = tree.query(pt, predicate="dwithin", distance=R_SEARCH)
            K = A.iloc[cand2].copy(); K["dist"] = shapely.distance(geoms[cand2], pt)
            K = K[~K.is_ramp & (K.index != L0.name) & (bdiff(K.bearing, L0.bearing + 180) <= R_OPP) & ((K.mdot_fc == fs) | K.osm_group.isin(FS_TO_OSM[fs]) | (K.osm_group == L0.osm_group))]
            if len(K): K = K[K.apply(lambda lk: ident(sroute, s.ROADNAME, lk) > 0 or (L0["name"] != "" and lk["name"] == L0["name"]), axis=1)].sort_values("dist")
            if len(K):
                b = K.iloc[0]
                rec.update({f"link_{miss}": b.name, f"dist_{miss}": round(b.dist, 1), f"hwy_{miss}": b.hwy, f"mdot_fc_{miss}": b.mdot_fc, f"lanes_{miss}": b.permlanes, f"name_{miss}": b["name"], f"in_scc_{miss}": bool(b.in_scc), f"freespeed_mph_{miss}": round(b.freespeed_mph, 1), f"capacity_{miss}": b.capacity})
                flags.append(f"second_carriageway_{miss}:{b.name}@{b.dist:.0f}m"); n_dir = 2; rec["match_category"] = "second_carriageway_added"
                lsum = L0.permlanes + b.permlanes
                rec["match_review"] += f"other carriageway added: '{b['name']}' {b.mdot_route}, {b.dist:.0f} m, opposite to '{L0['name']}'; network lanes {L0.permlanes:.0f}+{b.permlanes:.0f} vs MDOT {s.NUM_LANES}" + ("; lanes differ by 2 or more" if pd.notna(s.NUM_LANES) and abs(lsum - s.NUM_LANES) >= 2 else "") + "; "
                if not b.in_scc: flags.append(f"outside_scc_{miss}")
            else:
                rec["match_category"] = "other_carriageway_missing"; rec["match_review"] += f"no opposite link of the same route/name within {R_SEARCH} m: network lacks the other carriageway; "
        else:
            counted = "NE" if s.NORTH_EAST_SPLIT == 100 else "SW" if s.SOUTH_WEST_SPLIT == 100 else None
            if counted == have: rec["match_category"] = "oneway_ok"; rec["match_review"] += "one-way count (share 100) and the link of the counted direction is matched" + ("" if not L0.two_way else "; network road has a reverse link"); 
            else: rec["match_category"] = "oneway_direction_conflict"; rec["match_review"] += f"one-way count in direction {counted} but the only link of this road is {have} (bearing {L0.bearing:.0f}); direction label contradicts the network; "
    elif n_dir == 2 and not ramp_station: rec["match_category"] = "two_way_ok"
    if s.LOCATION_ID in OV.index:
        o = OV.loc[s.LOCATION_ID]
        for lab in ("NE", "SW"):
            v = o.get(f"link_{lab}", "")
            if v != "":
                if v.upper() == "NONE": rec.update({f"link_{lab}": "", f"dist_{lab}": np.nan})
                else:
                    b = A.loc[v]; rec.update({f"link_{lab}": v, f"dist_{lab}": round(shapely.distance(geoms[A.index.get_loc(v)], pt), 1), f"hwy_{lab}": b.hwy, f"mdot_fc_{lab}": b.mdot_fc, f"lanes_{lab}": b.permlanes, f"name_{lab}": b["name"], f"in_scc_{lab}": bool(b.in_scc), f"freespeed_mph_{lab}": round(b.freespeed_mph, 1), f"capacity_{lab}": b.capacity})
        n_dir = int(rec["link_NE"] != "") + int(rec["link_SW"] != ""); flags.append("manual_override"); rec["match_category"] = o.get("category", "") or rec["match_category"]; rec["match_review"] += "MANUAL: " + o.get("reason", "") + "; "
    if n_dir == 1 and not ramp_station: flags.append("one_direction")
    if n_dir == 2 and ramp_station: flags.append("ramp_two_directions")
    if n_dir == 0: flags.append("unmatched")
    # parallel-link review (identity only): links inside the tolerance that run parallel (bearing within 20 deg, either direction) to a matched link
    chosen = [rec[f"link_{l}"] for l in ("NE", "SW") if rec[f"link_{l}"] != ""]; rec["matched_identity"] = np.nan; rec["parallel_review"] = ""; rec["n_parallel_other_road"] = 0
    if chosen and not ramp_station:
        sroute = route_of(s); idl = [ident(sroute, s.ROADNAME, A.loc[c]) for c in chosen]; rec["matched_identity"] = min(idl)
        P = A.iloc[cand].copy(); P = P[~P.is_ramp & ~P.index.isin(chosen) & ~P.hwy.isin(["service", "footway", "cycleway", "path", "track"])]
        P = P[[min(bdiff(b, A.loc[c].bearing), bdiff(b, A.loc[c].bearing + 180)) <= 20 for b, c in zip(P.bearing, [chosen[0]] * len(P))]] if len(P) else P
        if len(P):
            P["idn"] = P.apply(lambda lk: ident(sroute, s.ROADNAME, lk), axis=1); oth = P[P.idn == 0]; rec["n_parallel_other_road"] = len(oth)
            if len(oth):
                nm = "; ".join(sorted({f"{r['name'] or r.hwy} [{r.mdot_route or '-'}]" for _, r in oth.iterrows()})[:4])
                rec["parallel_review"] = ("matched link is the counted road (identity %d), parallel link(s) of other roads ignored: %s" % (min(idl), nm)) if min(idl) > 0 else ("matched link identity not confirmed (%s), parallel other road(s): %s; no parallel link is the counted road, kept" % (A.loc[chosen[0]]["name"] or "unnamed", nm))
            else: rec["parallel_review"] = "parallel links are the same road (other carriageway or adjacent segment)"
    rec["matched_directions"] = n_dir; rec["match_flags"] = ";".join(flags)
    rec["lanes_network_total"] = np.nansum([rec.get("lanes_NE", np.nan), rec.get("lanes_SW", np.nan)]) if n_dir else np.nan
    rec["lanes_delta"] = rec["lanes_network_total"] - s.NUM_LANES if n_dir and pd.notna(s.NUM_LANES) else np.nan
    rows.append(rec)
M = pd.DataFrame(rows)
M["COUNTED_2024"] = M.AADT_2024.notna()
M.to_csv(f"{DATA}/count_stations_matched.csv", index=False)
ok = M[(M.matched_directions > 0)]
amb = M.match_flags.str.contains("ambiguous"); one = M.match_flags.str.contains("one_direction"); un = M.matched_directions == 0
print(f"matched: {len(ok):,} of {len(M):,} stations ({(M.matched_directions == 2).sum():,} both directions, {((M.matched_directions == 1) & (M.MAIN_LINE != 1)).sum():,} ramp stations one direction, {one.sum():,} mainline stations one direction only); unmatched {un.sum():,}; ambiguous flag {amb.sum():,}; name differs {M.match_flags.str.contains('name_differs').sum():,}")
print("by F_SYSTEM (stations / matched / both directions):")
print(M.groupby("F_SYSTEM").agg(stations=("LOCATION_ID", "size"), mainline=("MAIN_LINE", lambda s: (s == 1).sum()), matched=("matched_directions", lambda s: (s > 0).sum()), both=("matched_directions", lambda s: (s == 2).sum()), with_2024=("COUNTED_2024", "sum")).to_string())
lanes_cmp = M[M.matched_directions == 2].dropna(subset=["lanes_delta"])
print(f"lanes at stations matched both ways: equal {(lanes_cmp.lanes_delta == 0).mean():.1%}, network fewer {(lanes_cmp.lanes_delta < 0).mean():.1%}, network more {(lanes_cmp.lanes_delta > 0).mean():.1%} (n={len(lanes_cmp)})")

# ------------------------------------------------------------------ seeded split, stratified by functional system, only stations with a 2024 count and a match
E = M[(M.matched_directions > 0) & M.COUNTED_2024 & ~amb].copy()
rng = np.random.default_rng(SEED)
E["split"] = ""
for fs, g in E.groupby("F_SYSTEM"):
    idx = g.index.to_numpy().copy(); rng.shuffle(idx); half = len(idx) // 2 + (rng.integers(0, 2) if len(idx) % 2 else 0)
    E.loc[idx[:half], "split"] = "calibration_check"; E.loc[idx[half:], "split"] = "held_out"
# stations already assigned in the first matching keep their half (the rematch only adds or swaps links); new ones are drawn with the same seed
PRE = f"{DATA}/count_stations_split_pre_rematch.csv"
if os.path.exists(PRE):
    prev = pd.read_csv(PRE).set_index("LOCATION_ID").split; kept = E.LOCATION_ID.map(prev)
    for fs, g in E[kept.isna()].groupby("F_SYSTEM"):
        idx = g.index.to_numpy().copy(); np.random.default_rng(SEED + int(fs)).shuffle(idx); h = len(idx) // 2
        E.loc[idx[:h], "split"] = "calibration_check"; E.loc[idx[h:], "split"] = "held_out"
    E.loc[kept.notna(), "split"] = kept[kept.notna()]
E[["LOCATION_ID", "COUNTY", "ROADNAME", "F_SYSTEM", "F_SYSTEM_DESC", "MAIN_LINE", "link_NE", "link_SW", "matched_directions", "AADT_2024", "split"]].to_csv(f"{DATA}/count_stations_split.csv", index=False)
print(f"split (seed {SEED}, stations with a 2024 count, matched and unambiguous): {len(E):,} -> calibration_check {(E.split == 'calibration_check').sum():,}, held_out {(E.split == 'held_out').sum():,}")
print(E.groupby(["F_SYSTEM", "split"]).size().unstack(fill_value=0).to_string())
