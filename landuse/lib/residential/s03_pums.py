#!/usr/bin/env python3
"""Mover households from ACS PUMS 5-year files (DC, DE, MD, PA, VA, WV).

Samples
  est   2014-2018 5-year file (2010 PUMA / MIGPUMA / POWPUMA geography throughout); random 80 / 20 split by household
        (hash of SERIALNO) into estimation and held-out validation
  oot   2017-2021 5-year file, records of survey years 2019-2021 only (2010 geography; no overlap with 2014-2018): out-of-time test
        (the 2019-2023 file recodes all years to 2020 PUMAs, so it is not used)
Mover household = householder (RELP 0 / RELSHIPP 20) who lived in a different house in the U.S. one year ago (MIG 3), in a
household (TYPE / TYPEHUGQ 1) that moved in within 12 months (MV 1).  Kept: origin MIGPUMA in the study states, origin and
destination touching the zone system.  Incomes: HINCP x ADJINC, deflated to 2016 $ (CPI-U); housing cost GRNTP or SMOCP x ADJHSG,
2016 $.
Outputs work/pums_movers_<tag>.parquet (one row per mover household) and work/pums_pool_<tag>.parquet (all dwellings occupied by
households that moved in within 12 months: the market of the year, used as the sampled alternatives of the dwelling model).
"""
import sys, hashlib
import numpy as np, pandas as pd
from rc import *

PCOLS = ["SERIALNO", "SPORDER", "ST", "STATE", "PUMA", "RELP", "RELSHIPP", "AGEP", "MIG", "MIGSP", "MIGPUMA", "POWSP", "POWPUMA", "ESR",
         "JWMNP", "RAC1P", "HISP", "SCHG"]
HCOLS = ["SERIALNO", "ST", "STATE", "PUMA", "ADJINC", "ADJHSG", "WGTP", "NP", "TYPE", "TYPEHUGQ", "BDSP", "BLD", "TEN", "GRNTP", "SMOCP",
         "VALP", "HINCP", "MV", "VEH", "R18", "HUPAC", "YBL", "YRBLT", "VACS"]


def bld_type(b):
    return np.select([b == 2, b == 3, b.isin([4, 5]), b.isin([6, 7, 8, 9]), b.isin([1, 10])], ["SFD", "SFA", "MF234", "MF5plus", "MH"], "NA")


def year_built(h, svy):
    if "YRBLT" in h.columns and h.YRBLT.notna().any():
        return h.YRBLT
    # YBL (2014-2018 files): 1 <=1939, 2 1940-49, 3 1950s, 4 1960s, 5 1970s, 6 1980s, 7 1990s, 8 2000-04, 9 2005, ..., 22 2018
    m = {1: 1935, 2: 1945, 3: 1955, 4: 1965, 5: 1975, 6: 1985, 7: 1995, 8: 2002}
    y = h.YBL.map(m)
    y = y.where(h.YBL < 9, 1996 + h.YBL)   # 9 -> 2005, ..., 22 -> 2018
    return y


def load(tag):
    year = 2018 if tag == "est" else 2021
    P, H = [], []
    for s in STATES:
        p = pums_read(year, "p", s, PCOLS); h = pums_read(year, "h", s, HCOLS)
        if "ST" not in h.columns: h = h.rename(columns={"STATE": "ST"})
        if "ST" not in p.columns: p = p.rename(columns={"STATE": "ST"})
        p["svy"] = p.SERIALNO.str[:4].astype(int); h["svy"] = h.SERIALNO.str[:4].astype(int)
        if tag == "oot":
            p = p[p.svy >= 2019]; h = h[h.svy >= 2019]
        P.append(p); H.append(h)
        print(s, len(p), len(h), flush=True)
    return pd.concat(P, ignore_index=True), pd.concat(H, ignore_index=True)


def main(tag):
    P, H = load(tag)
    tcol = "TYPE" if "TYPE" in H.columns and H.TYPE.notna().any() else "TYPEHUGQ"
    H = H[(H[tcol] == 1) & (H.NP > 0)].copy()
    adj = H.ADJINC / (1e6 if H.ADJINC.max() > 100 else 1.0)
    adjh = H.ADJHSG / (1e6 if H.ADJHSG.max() > 100 else 1.0)
    ref = 2018 if tag == "est" else 2021
    defl = CPI[2016] / CPI[ref]
    H["income"] = H.HINCP.fillna(0) * adj * defl
    H["cost"] = (H.GRNTP.fillna(0) + H.SMOCP.fillna(0)) * adjh * defl
    H["dtype"] = bld_type(H.BLD)
    H["yearBuilt"] = year_built(H, H.svy)
    H["age_dd"] = (H.svy - H.yearBuilt).clip(lower=0)
    H["owner"] = H.TEN.isin([1, 2]).astype(int)
    H["puma7"] = H.ST * 100000 + H.PUMA
    # persons: workers and their places of work; householder
    rel = P.RELP if "RELP" in P.columns and P.RELP.notna().any() else P.RELSHIPP
    head_code = 0 if "RELP" in P.columns and P.RELP.notna().any() else 20
    P["worker"] = P.ESR.isin([1, 2, 4, 5]) & P.POWPUMA.notna()
    P["pow7"] = (P.POWSP.fillna(0) * 100000 + P.POWPUMA.fillna(0)).astype(int)
    P["child"] = P.AGEP < 18
    P["p16"] = P.AGEP >= 16          # potential drivers (PUMS has no licence variable): car availability = VEH vs persons 16+
    agg = P.groupby("SERIALNO").agg(n_child=("child", "sum"), n_workers=("worker", "sum"), n_p16=("p16", "sum"), age_max=("AGEP", "max"))
    wk = P[P.worker].sort_values(["SERIALNO", "SPORDER"]).groupby("SERIALNO").pow7.apply(lambda s: ";".join(map(str, s)))
    hd = P[rel == head_code].drop_duplicates("SERIALNO").set_index("SERIALNO")
    H = H.set_index("SERIALNO").join(agg).join(wk.rename("pow7s"))
    H["head_age"] = hd.AGEP.reindex(H.index)
    H["head_race"] = np.select([hd.HISP.reindex(H.index) > 1, hd.RAC1P.reindex(H.index) == 1, hd.RAC1P.reindex(H.index) == 2], ["hispanic", "white", "black"], "other")
    H["mig"] = hd.MIG.reindex(H.index)
    H["migsp"] = hd.MIGSP.reindex(H.index)
    H["mig7"] = (hd.MIGSP.reindex(H.index).fillna(0) * 100000 + hd.MIGPUMA.reindex(H.index).fillna(0)).astype(int)
    H["inc_group"] = inc_group(H.income)
    H["size4"] = H.NP.clip(upper=4)
    H["n_child"] = H.n_child.fillna(0); H["n_workers"] = H.n_workers.fillna(0); H["n_p16"] = H.n_p16.fillna(0)
    pr = pd.read_csv(f"{WORK}/geo_puma_region.csv")
    cov = pr.groupby("puma7").coverage.first()
    mz = pd.read_csv(f"{WORK}/geo_mig_zone.csv"); mcov = mz.groupby("mig7").coverage.first()
    H["dest_cov"] = H.puma7.map(cov).fillna(0)
    H["orig_cov"] = H.mig7.map(mcov).fillna(0)
    keep = ["ST", "puma7", "svy", "WGTP", "NP", "size4", "n_child", "n_workers", "n_p16", "pow7s", "income", "inc_group", "cost", "dtype", "BDSP",
            "yearBuilt", "age_dd", "owner", "TEN", "VEH", "head_age", "age_max", "head_race", "mig", "migsp", "mig7", "dest_cov", "orig_cov", "VALP", "GRNTP", "SMOCP"]
    pool = H[(H.MV == 1) & (H.dest_cov > 0) & (H.dtype != "NA")][keep].copy()
    pool.reset_index().to_parquet(f"{WORK}/pums_pool_{tag}.parquet")
    mv = H[(H.MV == 1) & (H.mig == 3) & (H.dest_cov > 0) & (H.orig_cov > 0) & (H.dtype != "NA")][keep].copy().reset_index()
    if tag == "est":
        h = mv.SERIALNO.map(lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 5)
        mv["half"] = np.where(h == 0, "validation", "estimation")
    else:
        mv["half"] = "oot"
    mv.to_parquet(f"{WORK}/pums_movers_{tag}.parquet")
    allh = len(H); m3 = int((H.MV.eq(1) & H.mig.eq(3)).sum())
    print(f"[{tag}] households {allh:,}; moved in <=12 months from a U.S. house {m3:,}; kept (origin and destination in the zone system) {len(mv):,}; "
          f"pool of mover-occupied dwellings {len(pool):,}")
    print(mv.half.value_counts().to_string())
    print(mv.inc_group.value_counts().to_string())


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["est", "oot"]):
        main(t)
