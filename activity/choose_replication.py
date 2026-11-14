#!/usr/bin/env python3
"""Pick the SILO seed closest to the five-seed mean of the key 2024 outputs (smallest sum of squared relative deviations):
MD county populations (24), MD households, MD employed persons, students by school band, mean commute (silo_final_tables_seeds.csv).
Output: final_2024/seed_choice.csv, seed_choice_detail.csv."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; O = f"{V}/3_abit/final_2024"
zc = pd.read_csv(f"{ABIT_HOME}/input/maryland/zone_attributes.csv").set_index("id").countyfips.astype(int)
tab = pd.read_csv(f"{V}/data/silo_final_tables_seeds.csv")
rows = []
for k in range(1, 6):
    F = f"{S}/run/base/scenOutput/oos_s{k}/microData/futureYears"; R = f"{S}/schoolchoice/runs/oos_s{k}/2024"
    dd = pd.read_csv(f"{F}/dd_2024.csv", usecols=["id", "zone"], engine="pyarrow").set_index("id").zone
    hh = pd.read_csv(f"{F}/hh_2024.csv", usecols=["id", "dwelling"], engine="pyarrow")
    hh["cty"] = hh.dwelling.map(dd).map(zc); hc = hh.set_index("id").cty
    pp = pd.read_csv(f"{R}/pp_2024.csv", usecols=["hhid", "occupation", "schoolId"], engine="pyarrow"); pp["cty"] = pp.hhid.map(hc)
    md = pp[pp.cty // 1000 == 24]
    sc = pd.read_csv(f"{R}/schools_2024.csv", usecols=["id", "type"]).set_index("id").type
    r = {f"pop {c}": n for c, n in md.cty.value_counts().items()}
    r["MD households"] = int((hh.cty // 1000 == 24).sum()); r["MD employed"] = int((md.occupation == 1).sum())
    st = md[md.occupation == 3]
    for t, n in st.schoolId.map(sc).value_counts().items(): r[f"MD students school type {int(t)}"] = n
    r["mean commute"] = tab[(tab.seed == k) & (tab.year == 2024) & (tab.quantity == "mean car time to work (ACS: all modes)")].model.iloc[0]
    r["seed"] = k; rows.append(r); print(k, "read", flush=True)
d = pd.DataFrame(rows).set_index("seed").sort_index(axis=1)
rel = d / d.mean() - 1
out = pd.DataFrame({"ssq_rel_dev": (rel ** 2).sum(axis=1), "max_abs_rel_dev_pct": rel.abs().max(axis=1) * 100,
                    "MD_pop": d.filter(like="pop ").sum(axis=1), "MD_households": d["MD households"], "MD_employed": d["MD employed"], "mean_commute": d["mean commute"]})
out.to_csv(f"{O}/seed_choice.csv"); pd.concat({"value": d.T, "rel_dev_pct": rel.T * 100}, axis=1).to_csv(f"{O}/seed_choice_detail.csv")
print(out.to_string()); print("chosen seed:", out.ssq_rel_dev.idxmin())
