#!/usr/bin/env python3
"""Discretionary (shopping + other) tour frequency and participation by person type and licence (2026-11-10): RTS hold-out tours
(mode_choice/work/tours_validation.parquet; persons of survey_pop/validation), ABIT on the hold-out survey population (seed 1) and the
1 % SILO 2024 smoke (mc_tours.csv).  Types: child < 16; 16-64 worker; 16-64 non-worker; 65+; persons 16+ by licence.  Unweighted.
    python3 activity/checks/person_frequencies.py -> respec_person_freq.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
A3 = f"{WORKSPACE}/3_abit"   # data
sys.path.insert(0, f"{TERP_HOME}/activity/lib")
import replications as F


def ptype(pp):
    lic = pp.driversLicense.astype(str).str.lower().eq("true")
    t = np.where(pp.age < 16, "child <16", np.where(pp.age >= 65, "65+", np.where(pp.occupation == 1, "16-64 worker", "16-64 non-worker")))
    return pd.Series(np.where(pp.age >= 16, t + np.where(lic, ", licence", ", no licence"), t), index=pp.id.values)


def table(pt, tours, src):
    n = tours.groupby("pid").size().reindex(pt.index).fillna(0)
    d = pd.DataFrame({"type": pt.values, "n": n.values})
    g = d.groupby("type").agg(persons=("n", "size"), tours_per_person=("n", "mean"), participation=("n", lambda x: 100 * (x > 0).mean()))
    g.columns = pd.MultiIndex.from_product([[src], g.columns]); return g


def main():
    O = f"{A3}/survey_pop/validation"; pp = pd.read_csv(f"{O}/pp.csv"); pm = pd.read_csv(f"{O}/persons_map.csv").drop_duplicates("person_id").set_index("person_id").id
    t = pd.read_parquet(f"{A3}/mode_choice/work/tours_validation.parquet"); t = t[t.segment.isin(["shopping", "other"])]
    obs = pd.DataFrame({"pid": t.person_id.map(pm).values})
    m = pd.read_csv(f"{A3}/run_survey/svy_val_respecval_s01/output/mc_tours.csv"); m = m[m.segment.isin(["shopping", "other"])].rename(columns={"person_id": "pid"})
    S = f"{A3}/final_2024/run_respec_smoke/smk_respec_s01/output"; per = pd.read_parquet(f"{S}/persons.parquet")
    sp = pd.read_csv(f"{F.SCH}/pp_2024.csv", usecols=["id", "age", "driversLicense", "occupation"], engine="pyarrow"); sp = sp[sp.id.isin(per.person_id)]
    s = pd.read_csv(f"{S}/mc_tours.csv"); s = s[s.segment.isin(["shopping", "other"])].rename(columns={"person_id": "pid"})
    pt = ptype(pp)
    R = pd.concat([table(pt, obs, "RTS hold-out"), table(pt, m, "ABIT survey population"), table(ptype(sp), s, "ABIT SILO 2024 1 %")], axis=1)
    R.to_csv(f"{A3}/respec_person_freq.csv"); pd.set_option("display.width", 250); print(R.round(3).to_string())


if __name__ == "__main__":
    main()
