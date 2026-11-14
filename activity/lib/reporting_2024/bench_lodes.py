#!/usr/bin/env python3
"""LODES 8 origin-destination 2022 (all jobs, JT00): home-to-work flows of Maryland residents by county and place-of-work
PUMA unit, and the jobs by MSTM zone used to place workers inside their place-of-work PUMA.

    python3 -I activity/lib/reporting_2024/bench_lodes.py   -> temporal_2024/data/lodes2022_flows.csv (home unit, work unit, jobs),
                                   temporal_2024/data/lodes2022_zone_jobs.csv (zone, jobs; workplace-area characteristics 2022)

Maryland residents working in Maryland: md_od_main; working in DC, DE, PA, VA, WV: the 'aux' file of that state (jobs in the
state held by residents of other states, filtered to Maryland home blocks).  Units: county, or the group of counties of one
place-of-work PUMA (t24common.county_group), so that LODES, ACS and the model are compared on the same geography.
Zone jobs: WAC 2022 (C000) of the six states; block -> zone by the block's internal point (LODES geography crosswalk
blklatdd, blklondd) in the MSTM zone polygons.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import t24common as C

L = C.RAW
STATES = {"md": 24, "dc": 11, "de": 10, "pa": 42, "va": 51, "wv": 54}


def flows():
    cg = C.county_group(); parts = []
    for s in STATES:
        f = f"{L}/lodes_od/md_od_main_JT00_2022.csv.gz" if s == "md" else f"{L}/lodes_od/{s}_od_aux_JT00_2022.csv.gz"
        d = pd.read_csv(f, usecols=["w_geocode", "h_geocode", "S000"], dtype={"w_geocode": str, "h_geocode": str})
        d = d[d.h_geocode.str[:2] == "24"]
        d["hc"] = d.h_geocode.str[:5].astype(int); d["wc"] = d.w_geocode.str[:5].astype(int)
        parts.append(d.groupby(["hc", "wc"]).S000.sum().reset_index())
    f = pd.concat(parts).groupby(["hc", "wc"]).S000.sum().reset_index()
    f["home_unit"] = f.hc.map(cg.unit); f["work_unit"] = f.wc.map(cg.unit).fillna(-1).astype(int)
    out = f.groupby(["home_unit", "work_unit"]).S000.sum().rename("jobs").reset_index()
    cty = f.rename(columns={"hc": "home_county", "wc": "work_county", "S000": "jobs"})[["home_county", "work_county", "jobs"]]
    return out, cty


def zone_jobs():
    import geopandas as gpd
    z = gpd.read_file(C.ZONES_SHP)[["id", "geometry"]]; parts = []
    for s in STATES:
        w = pd.read_csv(f"{L}/lodes_wac/{s}_wac_S000_JT00_2022.csv.gz", usecols=["w_geocode", "C000"], dtype={"w_geocode": str})
        x = pd.read_csv(f"{L}/lodes_wac/{s}_xwalk.csv.gz", usecols=["tabblk2020", "blklatdd", "blklondd"], dtype={"tabblk2020": str})
        w = w.merge(x, left_on="w_geocode", right_on="tabblk2020")
        pt = gpd.GeoDataFrame(w[["C000"]], geometry=gpd.points_from_xy(w.blklondd, w.blklatdd), crs="EPSG:4326").to_crs(z.crs)
        j = gpd.sjoin(pt, z, how="inner", predicate="within")
        j["county"] = w.loc[j.index, "w_geocode"].str[:5].astype(int).values
        parts.append(j.groupby(["id", "county"]).C000.sum().reset_index())
    out = pd.concat(parts).rename(columns={"id": "zone", "C000": "jobs"})
    return out.groupby(["zone", "county"]).jobs.sum().reset_index()


if __name__ == "__main__":
    f, cty = flows(); f.to_csv(f"{C.OUT}/lodes2022_flows.csv", index=False); cty.to_csv(f"{C.OUT}/lodes2022_county_flows.csv", index=False)
    print("Maryland residents' jobs (LODES 2022, all jobs):", int(f.jobs.sum()))
    zj = zone_jobs(); zj.to_csv(f"{C.OUT}/lodes2022_zone_jobs.csv", index=False)
    print("jobs placed in zones:", int(zj.jobs.sum()), "zones:", zj.zone.nunique())
