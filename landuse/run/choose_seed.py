#!/usr/bin/env python3
"""After the five respec seeds (oos_respec_s1..5, validated by run_seeds.py into data/silo_validation_oos_respec_s<k>.parquet):
  1 seed mean + seed sd -> data/silo_validation_oos_respec_mean.parquet (same columns as aggregate_seeds.py writes for the record runs)
  2 out-of-sample per-bin scorecard, test years 2021-2024, respec mean vs record mean (data/silo_validation_oos_mean.parquet):
    share of cells within +-5 pp of the observed share, by section x table (composition by county and statewide) -> tables/p01_scorecard.csv;
    rates (C events, A totals, E commute, F flows) side by side -> tables/p01_rates.csv
  3 seed closest to the five-seed mean, rule of activity/choose_replication.py (smallest sum of squared relative deviations of the 2024
    MD county populations, MD households, MD employed, MD students by school type, mean commute) -> tables/p01_seed_choice.csv
    (tables/ = WORKSPACE/side_experiments/respec_2026-11/engine_check/tables)
    python3 landuse/run/choose_seed.py"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; T = f"{V}/side_experiments/respec_2026-11/engine_check/tables"   # outputs (workspace)
KEYS = ["section", "year", "geo", "table", "bin"]


def mean_of(tag):
    fs = [f"{V}/data/silo_validation_oos_respec_s{k}.parquet" for k in range(1, 6)]
    R = pd.concat([pd.read_parquet(f).assign(seed=i + 1) for i, f in enumerate(fs) if os.path.exists(f)]); g = R.groupby(KEYS, sort=False)
    M = g.agg(model=("model", "mean"), seed_sd=("model", "std"), observed=("observed", "first"), n_seeds=("model", "size")).reset_index()
    M["diff_pp"] = (M.model - M.observed) * 100; M["ratio"] = M.model / M.observed.replace(0, np.nan)
    M.to_parquet(f"{V}/data/silo_validation_{tag}.parquet", index=False); return M


def main():
    A = mean_of("oos_respec_mean"); B = pd.read_parquet(f"{V}/data/silo_validation_oos_mean.parquet")
    sc = {}
    for lab, X in (("respec", A), ("record", B)):
        x = X[X.year.between(2021, 2024) & X.section.isin(["B composition", "B2 statewide"]) & X.observed.notna() & X.model.notna()].copy()
        x["tbl"] = x.table.str.replace(r" \[PUMS \d+\]", "", regex=True); x["ok"] = x.diff_pp.abs() <= 5
        s_ = x.groupby(["section", "tbl"]).ok.agg(["mean", "size"]); s_.loc[("ALL", "all composition cells"), :] = [x.ok.mean(), len(x)]
        sc[lab] = s_.rename(columns={"mean": f"within5_{lab}", "size": f"cells_{lab}"})
    S_ = sc["respec"].join(sc["record"], how="outer").reset_index(); S_.to_csv(f"{T}/p01_scorecard.csv", index=False); print(S_.round(3).to_string(index=False))
    r = []
    for lab, X in (("respec", A), ("record", B)):
        x = X[X.year.between(2017, 2024) & X.section.isin(["C events", "E commute", "F flows"]) & X.geo.astype(str).isin(["Maryland", "24", "MD"])]
        r.append(x.set_index(["section", "table", "bin", "year"])[["model"]].rename(columns={"model": lab}))
    o = X[X.year.between(2017, 2024) & X.section.isin(["C events", "E commute", "F flows"]) & X.geo.astype(str).isin(["Maryland", "24", "MD"])].set_index(["section", "table", "bin", "year"]).observed
    Rt = pd.concat(r + [o], axis=1).reset_index(); Rt.to_csv(f"{T}/p01_rates.csv", index=False)
    # seed choice
    zc = pd.read_csv(f"{ABIT_HOME}/input/maryland/zone_attributes.csv").set_index("id").countyfips.astype(int)
    rows = []
    for k in range(1, 6):
        F = f"{S}/run/base/scenOutput/oos_respec_s{k}/microData/futureYears"; Rs = f"{S}/schoolchoice/runs/oos_respec_s{k}/2024"
        dd = pd.read_csv(f"{F}/dd_2024.csv", usecols=["id", "zone"], engine="pyarrow").set_index("id").zone
        hh = pd.read_csv(f"{F}/hh_2024.csv", usecols=["id", "dwelling"], engine="pyarrow"); hh["cty"] = hh.dwelling.map(dd).map(zc); hc = hh.set_index("id").cty
        pp = pd.read_csv(f"{Rs}/pp_2024.csv", usecols=["hhid", "occupation", "schoolId"], engine="pyarrow"); pp["cty"] = pp.hhid.map(hc); md = pp[pp.cty // 1000 == 24]
        sct = pd.read_csv(f"{Rs}/schools_2024.csv", usecols=["id", "type"]).set_index("id").type
        rr = {f"pop {c}": n for c, n in md.cty.value_counts().items()}
        rr["MD households"] = int((hh.cty // 1000 == 24).sum()); rr["MD employed"] = int((md.occupation == 1).sum())
        for t, n in md[md.occupation == 3].schoolId.map(sct).value_counts().items(): rr[f"MD students school type {int(t)}"] = n
        P = pd.read_parquet(f"{V}/data/silo_validation_oos_respec_s{k}.parquet")
        rr["mean commute"] = float(P[(P.year == 2024) & (P.section == "E commute") & P.table.str.startswith("travel time to work, mean")].model.iloc[0])
        rr["seed"] = k; rows.append(rr)
    d = pd.DataFrame(rows).set_index("seed").sort_index(axis=1); rel = d / d.mean() - 1
    out = pd.DataFrame({"ssq_rel_dev": (rel ** 2).sum(axis=1), "max_abs_rel_dev_pct": rel.abs().max(axis=1) * 100, "MD_pop": d.filter(like="pop ").sum(axis=1),
                        "MD_households": d["MD households"], "MD_employed": d["MD employed"], "mean_commute": d["mean commute"]})
    out.to_csv(f"{T}/p01_seed_choice.csv"); pd.concat({"value": d.T, "rel_dev_pct": rel.T * 100}, axis=1).to_csv(f"{T}/p01_seed_choice_detail.csv")
    print(out.to_string()); print("chosen seed:", out.ssq_rel_dev.idxmin())


if __name__ == "__main__":
    main()
