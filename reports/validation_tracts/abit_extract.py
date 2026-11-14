#!/usr/bin/env python3
"""Zone-level destinations and home->work flows of the ABIT 2024 runs (fin24_tw_s01..s10, the current runs with the 2024 telework
input), weekday = day 1 of activities_full.parquet (days 2-7 hold only the overnight home stay).  Each run is a 10 % household
sample (sample.fraction = 0.1 in the properties) -> expansion factor 10.  Locations are unaffected by the latest component.

Output (out/cache/):
  abit_dest.parquet   rep, zone, purpose, activities, persons     (activities ending in the zone; persons = distinct persons
                      with at least one activity of the purpose in the zone; both expanded x10; all MSTM zones)
  abit_flows.parquet  rep, hzone, wzone, workers                  (distinct persons with a work activity: home zone -> zone of
                      their first work activity of the day; expanded x10)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, pyarrow.parquet as pq, pyarrow.compute as pc, os, re
V = f"{WORKSPACE}"
RUN = os.environ.get("ABIT_RUN_DIR", f"{V}/3_abit/final_2024/run"); OUT = os.environ.get("TRACT_CACHE", f"{V}/5_reports/validation_tracts/out/cache"); os.makedirs(OUT, exist_ok=True)
REPS = [f"{os.environ.get('ABIT_REP_PREFIX', 'fin24_tw_s')}{i:02d}" for i in range(1, 11)]   # env: ABIT_RUN_DIR, ABIT_REP_PREFIX (e.g. fin24_s), TRACT_CACHE

def sample_fraction(rep):
    for line in open(f"{RUN}/{rep}.properties"):
        m = re.match(r"\s*sample\.fraction\s*=\s*([0-9.]+)", line)
        if m: return float(m.group(1))
    raise ValueError(rep)

dest, flows = [], []
for k, rep in enumerate(REPS, 1):
    x = 1.0 / sample_fraction(rep)
    t = pq.read_table(f"{RUN}/{rep}/output/activities_full.parquet", columns=["person_id", "day", "start_time_min", "purpose", "zone"])
    t = t.filter(pc.and_(pc.equal(t["day"], "1"), pc.not_equal(t["purpose"], "HOME")))
    a = t.to_pandas(); a["zone"] = a.zone.astype(int); a["start"] = a.start_time_min.astype(int)
    d = a.groupby(["zone", "purpose"]).agg(activities=("person_id", "size"), persons=("person_id", "nunique")).reset_index()
    d[["activities", "persons"]] *= x; d["rep"] = k; dest.append(d)
    p = pd.read_parquet(f"{RUN}/{rep}/output/persons.parquet", columns=["person_id", "home_zone"]); p["person_id"] = p.person_id.astype(str)
    w = a[a.purpose == "WORK"].sort_values("start").drop_duplicates("person_id").merge(p, on="person_id", how="left")
    fl = w.groupby(["home_zone", "zone"]).size().rename("workers").reset_index().rename(columns={"home_zone": "hzone", "zone": "wzone"})
    fl["workers"] *= x; fl["rep"] = k; flows.append(fl)
    print(f"{rep}: x{x:g}, activities {len(a):,}, workers {len(w):,} (no home zone {w.home_zone.isna().sum()})", flush=True)
pd.concat(dest, ignore_index=True).to_parquet(f"{OUT}/abit_dest.parquet", index=False)
pd.concat(flows, ignore_index=True).to_parquet(f"{OUT}/abit_flows.parquet", index=False)
