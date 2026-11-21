#!/usr/bin/env python3
"""Zone-level aggregates of the SILO land-use runs (five seeds, oos_s1..oos_s5) for the tract-level validation.  Read-only on the
runs; streams the large files with usecols / chunks.

Year convention (as landuse/validation/validate_landuse.py: the engine writes the state at the END of simulated year Y under label Y):
  state 2016 = run/base/microData/*_2016.csv (input base);  state Y (Y > 2016) = file labelled Y-1
  (microData/{dd,jj,pp}_<Y-1>.csv, microData/futureYears/hh_<Y-1>.csv).  State 2024 = files labelled 2023 (identical to
  futureYears/*_2024.csv, which MAST reads).
Study area: zones of the six Baltimore-region counties (zoneSystem COUNTYFIPS).

Output (out/cache/):
  silo_zone.parquet   seed, year, zone, var, value   (households, persons, autos0..3, dwelling types of occupied units,
                      income histogram 2024 (2024 $ bins of 2,500), jobs total / filled by type, new dwellings 2016->2024)
  silo_flows.parquet  seed, hzone, wzone, workers    (2024 state: employed residents of the study area, home zone -> job zone)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, os, sys, time
V = f"{WORKSPACE}"
RUN = f"{V}/2_silo/run/base"; OUT = os.environ.get("TRACT_CACHE", f"{V}/5_reports/validation_tracts/out/cache")   # env: TRACT_CACHE, SILO_SEEDS (e.g. oos_respec_s), SILO_BASE (e.g. microData_v5respec)
PFX = os.environ.get("SILO_SEEDS", "oos_s"); BASE = os.environ.get("SILO_BASE", "microData"); os.makedirs(OUT, exist_ok=True)
CTY = [24003, 24005, 24013, 24025, 24027, 24510]
ZS = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").set_index("ZoneId"); SZ = set(ZS.index[ZS.COUNTYFIPS.isin(CTY)])
CPI24 = 1.307                     # 2024 $ per 2016 $ (CPI-U, as validate_landuse.py); SILO incomes are 2016 $
INC_STEP = 2500.0; INC_NB = 200   # histogram 0 .. 500k (2024 $), last bin open

def f(seed, y, kind):
    if y == 2016: return f"{RUN}/{BASE}/{kind}_2016.csv"
    d = f"{RUN}/scenOutput/{PFX}{seed}/microData"
    return f"{d}/futureYears/hh_{y - 1}.csv" if kind == "hh" else f"{d}/{kind}_{y - 1}.csv"

def households(seed, y):
    dd = pd.read_csv(f(seed, y, "dd"), usecols=["id", "zone", "type", "hhID"])
    dd = dd[dd.zone.isin(SZ)]
    occ = dd[dd.hhID > 0]
    hh = pd.read_csv(f(seed, y, "hh"), usecols=["id", "dwelling", "hhSize", "autos"])
    hh = hh.merge(occ[["id", "zone", "type"]].rename(columns={"id": "dwelling"}), on="dwelling", how="inner")
    return dd, hh

def zone_rows(seed, y, hh, extra=None):
    g = hh.groupby("zone"); rows = [g.size().rename("households"), g.hhSize.sum().rename("persons")]
    for a in range(4): rows.append(g.autos.apply(lambda s, a=a: (s.clip(upper=3) == a).sum()).rename(f"autos{a}"))
    for t in ["SFD", "SFA", "MF234", "MF5plus", "MH"]: rows.append(g.type.apply(lambda s, t=t: (s == t).sum()).rename(f"dw_{t}"))
    df = pd.concat(rows, axis=1).fillna(0)
    if extra is not None: df = df.join(extra, how="outer").fillna(0)
    df = df.reset_index().melt(id_vars="zone", var_name="var", value_name="value"); df["seed"] = seed; df["year"] = y
    return df

def jobs(seed, y):
    jj = pd.read_csv(f(seed, y, "jj"), usecols=["id", "zone", "personId", "type"])
    return jj

def main(seeds):
    rows, flows = [], []
    t0 = time.time()
    # base 2016 (shared by all seeds)
    dd16, hh16 = households(1, 2016); maxid16 = pd.read_csv(f(1, 2016, "dd"), usecols=["id"]).id.max()
    base = zone_rows(0, 2016, hh16)
    jj16 = jobs(1, 2016); jj16 = jj16[jj16.zone.isin(SZ)]
    jb = pd.concat([jj16.groupby("zone").size().rename("jobs"), jj16[jj16.personId > 0].groupby("zone").size().rename("jobs_filled")], axis=1).fillna(0)
    base = pd.concat([base, jb.reset_index().melt(id_vars="zone", var_name="var", value_name="value").assign(seed=0, year=2016)])
    rows.append(base); print(f"base 2016 done {time.time() - t0:.0f}s", flush=True)
    for s in seeds:
        for y in (2020, 2022, 2024):
            dd, hh = households(s, y)
            extra = None
            if y == 2024:
                new = dd[dd.id > maxid16].groupby("zone").size().rename("new_dwellings")
                extra = pd.DataFrame(new)
            rows.append(zone_rows(s, y, hh, extra))
            jj = jobs(s, y); jz = jj[jj.zone.isin(SZ)]
            jt = [jz.groupby("zone").size().rename("jobs"), jz[jz.personId > 0].groupby("zone").size().rename("jobs_filled")]
            for t in ["RET", "OFF", "IND", "OTH"]: jt.append(jz[jz.type == t].groupby("zone").size().rename(f"jobs_{t}"))
            jt = pd.concat(jt, axis=1).fillna(0).reset_index().melt(id_vars="zone", var_name="var", value_name="value"); jt["seed"] = s; jt["year"] = y
            rows.append(jt)
            if y == 2024:
                # persons: household income (sum of persons) and workplaces, streamed
                hz = hh.set_index("id").zone; inc = []; wk = []
                for ch in pd.read_csv(f(s, y, "pp"), usecols=["hhid", "occupation", "workplace", "income"], chunksize=2_000_000):
                    ch = ch[ch.hhid.isin(hz.index)]
                    inc.append(ch.groupby("hhid").income.sum())
                    w = ch[(ch.occupation == 1) & (ch.workplace > 0)]; wk.append(w[["hhid", "workplace"]])
                inc = pd.concat(inc).groupby(level=0).sum()
                hi = pd.DataFrame({"zone": hz.reindex(inc.index).values, "b": np.minimum((inc.values * CPI24 // INC_STEP).astype(int).clip(0), INC_NB - 1)})
                ih = hi.groupby(["zone", "b"]).size().rename("value").reset_index(); ih["var"] = "inc_b" + ih.b.astype(str).str.zfill(3)
                rows.append(ih.drop(columns="b").assign(seed=s, year=y))
                wk = pd.concat(wk); wk["hzone"] = hz.reindex(wk.hhid).values
                jzone = jj.set_index("id").zone; wk["wzone"] = jzone.reindex(wk.workplace).values
                fl = wk.dropna(subset=["wzone"]).groupby(["hzone", "wzone"]).size().rename("workers").reset_index(); fl["seed"] = s
                flows.append(fl)
                print(f"  seed {s}: workers {len(wk):,} (no job zone {wk.wzone.isna().sum():,})", flush=True)
            print(f"seed {s} year {y} done {time.time() - t0:.0f}s; households {len(hh):,}", flush=True)
            del dd, hh, jj
    pd.concat(rows, ignore_index=True).to_parquet(f"{OUT}/silo_zone.parquet", index=False)
    pd.concat(flows, ignore_index=True).astype({"hzone": int, "wzone": int}).to_parquet(f"{OUT}/silo_flows.parquet", index=False)

if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5])
