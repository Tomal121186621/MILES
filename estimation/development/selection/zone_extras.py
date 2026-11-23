#!/usr/bin/env python3
"""Candidate zone attributes that are not in the current DAYMAP models (re-specification 2026-11-06).

    python3 estimation/development/selection/zone_extras.py      -> side_experiments/respec_2026-11/abit/zone_extras.csv (one row per model zone, index order of dc_common.zones)

  leis_sh   share of the zone's jobs in arts, entertainment, recreation, accommodation and food services (LODES 8 WAC 2017,
            CNS17 + CNS18) / all jobs (C000); zones without WAC jobs: the job-weighted regional mean.  Fixed (2017) zone attribute.
  hlth_sh   share of the zone's jobs in health care and social assistance (CNS16 / C000), same rules.
  leis, hlth  the 2016 synthetic jobs of the zone (all types) x the share: size components that move with the land-use model.
  rail      the zone contains a rail stop (GTFS route types 0, 1, 2 of the merged regional timetable used for the transit skims).
  lnstopden ln(1 + transit stops per km2) of the same timetable (stops with at least one departure).
Blocks are placed in zones by their internal point (2_silo/jobchoice/work/blocks.parquet); GTFS stops by point in polygon.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np
import pandas as pd
V = f"{WORKSPACE}"
sys.path.insert(0, f"{MILES_HOME}/activity/lib/destination_choice"); sys.path.insert(0, f"{MILES_HOME}/activity/lib")
import dc_common as C  # noqa: E402

OUT = f"{V}/side_experiments/respec_2026-11/abit/zone_extras.csv"
RAW = f"{V}/data/raw"; GT = f"{V}/3_abit/mode_choice/work/gtfs_full"


def main():
    z = C.zones()
    blk = pd.read_parquet(f"{V}/2_silo/jobchoice/work/blocks.parquet").set_index("tabblk2020").zone
    cols = ["w_geocode", "C000", "CNS16", "CNS17", "CNS18"]
    w = [pd.read_csv(f"{RAW}/lodes_wac/md_wac_S000_JT00_2017.csv.gz", usecols=cols, dtype={"w_geocode": str})]
    for s in ("dc", "va", "pa", "de", "wv"):
        f = f"{RAW}/lodes_wac_2017_extra/{s}_wac_S000_JT00_2017.csv.gz"
        if os.path.exists(f): w.append(pd.read_csv(f, usecols=cols, dtype={"w_geocode": str}))
    w = pd.concat(w); w["zone"] = w.w_geocode.map(blk)
    g = w.dropna(subset=["zone"]).groupby("zone")[cols[1:]].sum()
    g = g.reindex(z.id.values).fillna(0)
    tot = g.C000.values
    leis = (g.CNS17 + g.CNS18).values; hl = g.CNS16.values
    m_leis = leis.sum() / tot.sum(); m_hl = hl.sum() / tot.sum()
    out = pd.DataFrame({"id": z.id.values})
    out["leis_sh"] = np.where(tot > 0, leis / np.maximum(tot, 1), m_leis)
    out["hlth_sh"] = np.where(tot > 0, hl / np.maximum(tot, 1), m_hl)
    out["leis"] = z.jobs.values * out.leis_sh.values; out["hlth"] = z.jobs.values * out.hlth_sh.values
    # GTFS stops
    import geopandas as gpd
    zz = gpd.read_file(C.ZONES_SHP)[["id", "geometry"]]
    st = pd.read_csv(f"{GT}/stops.txt", usecols=["stop_id", "stop_lat", "stop_lon"])
    tr = pd.read_csv(f"{GT}/trips.txt", usecols=["route_id", "trip_id"]); ro = pd.read_csv(f"{GT}/routes.txt", usecols=["route_id", "route_type"])
    rt = tr.merge(ro, on="route_id").set_index("trip_id").route_type
    used = {}
    for ch in pd.read_csv(f"{GT}/stop_times.txt", usecols=["trip_id", "stop_id"], chunksize=2_000_000):
        ch["rail"] = ch.trip_id.map(rt).isin([0, 1, 2])
        a = ch.groupby("stop_id").rail.max()
        for k, v in a.items(): used[k] = used.get(k, False) or bool(v)
    st = st[st.stop_id.isin(used)].copy(); st["rail"] = st.stop_id.map(used)
    p = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.stop_lon, st.stop_lat), crs="EPSG:4326").to_crs(zz.crs)
    j = gpd.sjoin(p, zz, how="inner", predicate="within")
    n = j.groupby("id").size().reindex(z.id.values).fillna(0).values; r = j.groupby("id").rail.max().reindex(z.id.values).fillna(False).values
    out["rail"] = r.astype(float); out["lnstopden"] = np.log1p(n / z.area_km2.clip(lower=0.05).values)
    out.to_csv(OUT, index=False)
    print(out.describe().round(3).T.to_string()); print("rail zones", int(out.rail.sum()), "WAC jobs placed", int(tot.sum()))


if __name__ == "__main__":
    main()
