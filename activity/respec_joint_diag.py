#!/usr/bin/env python3
"""Diagnostic of the joint-episode formation (2026-11-10, coef_respec): composition of the joint groups formed by ABIT
(MarylandTashaGenerator.household: household frequency, start, duration, number of participants P(k | type, household size),
participants drawn by segment propensity) against the observed survey joint groups (tasha_distributions.episodes: same household,
same purpose, same destination tract, arrival within the joint window).  Unit: a group of tours whose main activity is the same joint
episode (observed: household + jgid of the main episode in mode_choice/work/tours_validation.parquet; ABIT: household + joint_id of
mc_tours.csv), two or more tours.
    python3 respec_joint_diag.py   -> respec_joint_diag.csv (composition), respec_joint_rates.csv (groups per household by type)"""
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
A3 = os.path.dirname(os.path.abspath(__file__)); V = os.path.dirname(A3); SBS = f"{V}/side_experiments/respec_2026-11/step_by_step"
sys.path.insert(0, f"{SBS}/mode_choice"); sys.path.insert(0, f"{A3}/mode_choice"); sys.path.insert(0, f"{A3}/final_2024")
import m10_car_availability as CA   # noqa: E402
SEEDS = range(1, 6); SMOKE = f"{A3}/final_2024/run_respec_smoke/smk_respec_s01"


def hh_type(pp, hid_col):
    g = pp.groupby(hid_col).agg(n=("age", "size"), child=("age", lambda a: (a < 16).any()), wk=("occupation", lambda o: (o == 1).sum()))
    return np.where(g.n == 1, "single", np.where(g.child, "with child", np.where(g.n == 2, "two adults", "three+ adults"))) , g


def describe(T, P, H, src, wcol=None):
    """T: tours (hh, gid, person, purpose, start, w); P: persons (id -> age, lic); H: households (id -> autos)"""
    t = T.merge(P, left_on="person", right_index=True, how="left"); t["autos"] = t.hh.map(H.autos)
    t["lic16"] = (t.lic > 0) & (t.age >= 16); t["cdopt"] = t.lic16 & (t.autos > 0); t["kid"] = t.age < 16
    g = t.groupby(["hh", "gid"]).agg(size=("person", "size"), lic16=("lic16", "any"), cdopt=("cdopt", "any"), allkid=("kid", "all"), nokid=("kid", lambda k: not k.any()),
                                    purpose=("purpose", "first"), start=("start", "first"), w=("w", "first"))
    g = g[g["size"] >= 2]; w = g.w.fillna(0).values if wcol else np.ones(len(g)); W = w.sum()
    r = {"source": src, "weights": "RTS weights" if wcol else "unweighted", "groups": len(g)}
    for k in (2, 3, 4): r[f"size {k}{'+' if k == 4 else ''} (%)"] = 100 * w[(g["size"] >= 4) if k == 4 else (g["size"] == k)].sum() / W
    r["mean size"] = (g["size"] * w).sum() / W
    r[">= 1 licensed member 16+ (%)"] = 100 * w[g.lic16.values].sum() / W; r[">= 1 member with a car-driver option (%)"] = 100 * w[g.cdopt.values].sum() / W
    r["child-only (all < 16) (%)"] = 100 * w[g.allkid.values].sum() / W; r["adult-only (%)"] = 100 * w[g.nokid.values].sum() / W
    for p in ("SHOPPING", "RECREATION", "OTHER", "ACCOMPANY"): r[f"purpose {p.lower()} (%)"] = 100 * w[(g.purpose == p).values].sum() / W
    h = (g.start.values % 1440) // 60
    for lo, hi in ((0, 9), (9, 12), (12, 15), (15, 18), (18, 24)): r[f"start {lo:02d}-{hi:02d} h (%)"] = 100 * w[(h >= lo) & (h < hi)].sum() / W
    return r


def main():
    rows, rates = [], []
    # ---- observed (hold-out half)
    t, _, _ = CA.analyse("validation"); t = t[t.jg >= 0]
    O = f"{A3}/survey_pop/validation"; pm = pd.read_csv(f"{O}/persons_map.csv").drop_duplicates("person_id").set_index("person_id")
    pp = pd.read_csv(f"{O}/pp.csv"); hh = pd.read_csv(f"{O}/hh.csv").set_index("id")
    pa = pp.set_index("id"); pa["lic"] = pa.driversLicense.astype(str).str.lower().eq("true").astype(float)
    T = pd.DataFrame({"hh": t.household_id.values, "gid": t.jg.values, "person": t.person_id.map(pm.id).values, "purpose": t.purpose.values, "start": t.start.values, "w": t.w.values})
    # households of the survey population: ABIT ids; observed groups keyed by the survey household -> map to the ABIT household of its persons
    T["hh"] = T.person.map(pa.hhID)
    for wc in (None, "w"): rows.append(describe(T, pa[["age", "lic"]], hh, "observed RTS hold-out", wc))
    types, hg = hh_type(pp, "hhID"); ht = pd.Series(types, index=hg.index)
    def rate(Tx, ht, src, n_runs=1):
        g = Tx.groupby(["hh", "gid"]).size(); g = g[g >= 2].reset_index()
        cnt = g.groupby(g.hh.map(ht)).size() / n_runs; tot = ht.value_counts()
        for k in tot.index: rates.append(dict(source=src, household_type=k, households=int(tot[k]), joint_groups_per_household=float(cnt.get(k, 0) / tot[k])))
    rate(T, ht, "observed RTS hold-out")
    # ---- ABIT on the survey population (hold-out), 5 seeds
    ab = []
    tours_w = CA.analyse("validation")[0].groupby("person_id").w.first(); rev = pm.reset_index().drop_duplicates("id").set_index("id").person_id
    for s in SEEDS:
        m = pd.read_csv(f"{A3}/run_survey/svy_val_respecval_s{s:02d}/output/mc_tours.csv", usecols=["person_id", "household_id", "purpose", "start", "joint_id"])
        m = m[m.joint_id != 0]
        ab.append(pd.DataFrame({"hh": m.household_id.values, "gid": m.joint_id.values + 1000 * s, "person": m.person_id.values, "purpose": m.purpose.values, "start": m.start.values,
                                "w": m.person_id.map(rev).map(tours_w).values}))
    AB = pd.concat(ab)
    for wc in (None, "w"): rows.append(describe(AB, pa[["age", "lic"]], hh, "ABIT, survey population hold-out (5 seeds)", wc))
    rate(AB, ht, "ABIT, survey population hold-out (5 seeds)", n_runs=len(SEEDS))
    # ---- ABIT on the SILO 2024 population, 1 % smoke
    import runs_fin24 as F
    m = pd.read_csv(f"{SMOKE}/output/mc_tours.csv", usecols=["person_id", "household_id", "purpose", "start", "joint_id"])
    per = pd.read_parquet(f"{SMOKE}/output/persons.parquet"); hs = set(per.household_id)
    sp = pd.read_csv(f"{F.SCH}/pp_2024.csv", usecols=["id", "hhid", "age", "driversLicense", "occupation"], engine="pyarrow"); sp = sp[sp.hhid.isin(hs)]
    sh = pd.read_csv(f"{F.SCEN_DIR}/microData/futureYears/hh_2024.csv", usecols=["id", "autos"], engine="pyarrow"); sh = sh[sh.id.isin(hs)].set_index("id")
    spa = sp.set_index("id"); spa["lic"] = spa.driversLicense.astype(str).str.lower().eq("true").astype(float)
    m = m[m.joint_id != 0]
    S = pd.DataFrame({"hh": m.household_id.values, "gid": m.joint_id.values, "person": m.person_id.values, "purpose": m.purpose.values, "start": m.start.values, "w": 1.0})
    rows.append(describe(S, spa[["age", "lic"]], sh, "ABIT, SILO 2024 1 % smoke"))
    types2, hg2 = hh_type(sp, "hhid"); rate(S, pd.Series(types2, index=hg2.index), "ABIT, SILO 2024 1 % smoke")
    R = pd.DataFrame(rows).set_index(["source", "weights"]).T; R.to_csv(f"{A3}/respec_joint_diag.csv")
    Q = pd.DataFrame(rates).pivot(index="household_type", columns="source", values="joint_groups_per_household"); Q.to_csv(f"{A3}/respec_joint_rates.csv")
    pd.set_option("display.width", 250); print(R.round(2).to_string()); print(Q.round(3).to_string())
    # ---- driver's joint flag in the estimation data
    tt = CA.analyse("validation")[0]; g = tt[tt.jg >= 0].groupby(["household_id", "jg"])
    one = g.filter(lambda x: len(x) >= 2)
    print("observed joint tours (groups >= 2): car-driver members", int((one.choice2 == "CD").sum()), "of which joint flag = 1:", int(((one.choice2 == "CD") & one.joint).sum()),
          "| all members joint = 1:", bool(one.joint.all()))


if __name__ == "__main__":
    main()
