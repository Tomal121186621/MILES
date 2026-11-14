#!/usr/bin/env python3
"""Independent re-check of the joint-group comparison of mode_share_decomposition.py (2026-11-10).  Written separately: groups by their
labels (household, joint episode) from the tours file, probabilities from the utilities with its own logit / nested-logit formula,
the representative's group mode drawn from the group model's probabilities (inverse CDF, not random utilities), no car
allocation (C differs from B by < 0.7 pp).  Compares with respec_decompose.csv and respec_joint_coherence.csv.
    ~/.venvs/biogeme/bin/python activity/checks/joint_tours_recheck.py   -> respec_joint_recheck.csv"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
A3 = f"{WORKSPACE}/3_abit"; SBS = ESTIMATION_RESULTS   # data
sys.path.insert(0, f"{TERP_HOME}/estimation/development/tour_mode_choice"); sys.path.insert(0, f"{TERP_HOME}/estimation/development/accessibility"); sys.path.insert(0, f"{TERP_HOME}/activity/lib/mode_choice")
import m07_children as K7, m10_car_availability as CA, mode_logsum_new as LN, mc_common as M   # noqa: E402
ALTS = ["CD", "WK", "BK", "CP", "BUS", "TRAIN"]; HALF = "validation"


def probs(model, V, AV):
    """own formula: MNL, or nested logit with nests auto {CD, CP} and transit {BUS, TRAIN} (mu >= 1 inside, 1 at the root)"""
    b = LN.coef(model); n = len(V["CD"]); P = np.zeros((n, 6))
    nests = [["CD", "CP"], ["BUS", "TRAIN"]] if f"mu_auto" in b or "mu_transit" in b else []
    mu = {0: b.get("mu_auto", 1.0), 1: b.get("mu_transit", 1.0)}
    groups = [(mu[k], m) for k, m in enumerate(nests)] + [(1.0, [a]) for a in ALTS if not any(a in m for m in nests)]
    I = []
    for m_, mem in groups:
        e = np.stack([np.where(AV[a], np.exp(m_ * np.clip(V[a], -300, 300)), 0.0) for a in mem]); s = e.sum(0)
        I.append(np.where(s > 0, np.log(np.where(s > 0, s, 1)) / m_, -np.inf))
    I = np.stack(I); top = np.exp(I - np.nanmax(np.where(np.isfinite(I), I, -1e300), 0)); top = top / top.sum(0)
    for gi, (m_, mem) in enumerate(groups):
        e = np.stack([np.where(AV[a], np.exp(m_ * np.clip(V[a], -300, 300)), 0.0) for a in mem]); s = e.sum(0)
        for j, a in enumerate(mem): P[:, ALTS.index(a)] = top[gi] * np.where(s > 0, e[j] / np.where(s > 0, s, 1), 0)
    return P


def main():
    t = pd.read_parquet(f"{M.WORK}/tours_{HALF}.parquet").reset_index(drop=True); jg = CA.analyse(HALF)[0].jg.values
    f = M.features2(t, 0.5); f.loc[CA.blocked(HALF), "av_CD"] = 0
    ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(t.choice2.values)])
    parts = []
    for seg in ["work", "shopping", "other", "school"]:
        g = K7.data(HALF, seg); idx = np.where(t.segment.eq(seg).values & ok)[0]
        F = {k: g[k].values for k in g.columns}; V, AV = LN.utilities(seg, F); P = probs(seg, V, AV)
        AVp = dict(AV); AVp["CD"] = ((g.lic > 0) & (g.autos > 0) & (g.age >= 16)).values
        Vj = None
        if seg in ("shopping", "other"):
            c = pd.read_csv(f"{SBS}/mode_choice/m11_joint_coef.csv"); sj = f"{seg}_joint"; c = c[c.segment == sj]
            LN._coef[sj] = dict(zip(c.param, c.coef.astype(float))); LN.FORM[sj] = LN.FORM[seg]
            if seg in LN.NESTS: LN.NESTS[sj] = LN.NESTS[seg]
            Fj = dict(F); Fj["joint"] = np.ones(len(g)); Vj, _ = LN.utilities(sj, Fj)
        d = pd.DataFrame({"label": [f"{h}|{j}" for h, j in zip(t.household_id.values[idx], jg[idx])], "jg": jg[idx], "seg": seg, "choice": g.choice.values,
                          "age": g.age.values, "cdp": AVp["CD"]})
        for k, a in enumerate(ALTS):
            d[f"P_{a}"] = P[:, k]; d[f"av_{a}"] = AV[a]
            d[f"VJ_{a}"] = Vj[a] if Vj is not None else np.nan
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    rows = []
    # A: sample enumeration
    for seg, x in d.groupby("seg"):
        for a in ALTS: rows.append(dict(check="A sample enumeration", segment=seg, mode=a, recheck=100 * x[f"P_{a}"].mean(), observed=100 * (x.choice == a).mean()))
    # group rule with the group model, 5 seeds (no allocation): members of a joint group by label
    jt = d[d.jg >= 0]; lab = jt.groupby("label").size(); jt = jt[jt.label.map(lab) >= 2]
    sims = []; coh = []
    for seed in range(1, 6):
        rng = np.random.default_rng(100 + seed); u = rng.random(len(d))
        cum = np.cumsum(d[[f"P_{a}" for a in ALTS]].values, 1); alt = (u[:, None] > cum).sum(1).clip(max=5)   # inverse CDF, estimation availability
        for lb, x in jt.groupby("label"):
            ix = x.index.values; cand = x[x.cdp]
            rp = (cand if len(cand) else x).sort_values("age", kind="stable").index.values[-1]; seg = d.seg.values[rp]
            if seg in ("shopping", "other") and np.isfinite(d.VJ_CP.values[rp]):
                b = LN.coef(f"{seg}_joint")
                AVg = {a: np.array([bool(d[f"av_{a}"].values[rp]) and (a == "CD" or f"ASC_{a}" in b)]) for a in ALTS}; AVg["CD"] = np.array([bool(len(cand))])
                pj = probs(f"{seg}_joint", {a: np.array([d[f"VJ_{a}"].values[rp]]) for a in ALTS}, AVg)[0]
                a0 = int((rng.random() > np.cumsum(pj)).sum().clip(max=5))
            else: a0 = alt[rp]
            for r in ix:
                if r == rp: alt[r] = a0
                elif a0 == 0: alt[r] = 3
                elif d[f"av_{ALTS[a0]}"].values[r]: alt[r] = a0
        sims.append(alt.copy())
        z = jt.assign(a=alt[jt.index.values]).groupby("label").a.agg(lambda a: ((a == 0).sum() == 0 and (a == 3).sum() > 0, (a == 0).sum() >= 2, np.isin(a, [0, 3]).any() and not np.isin(a, [0, 3]).all()))
        coh.append(np.array(z.tolist()).mean(0) * 100)
    for seg, x in d.groupby("seg"):
        for k, a in enumerate(ALTS):
            rows.append(dict(check="D group model (no allocation)", segment=seg, mode=a, recheck=np.mean([100 * (s[x.index.values] == k).mean() for s in sims]), observed=100 * (x.choice == a).mean()))
    oc = jt.assign(a=jt.choice.map({a: k for k, a in enumerate(ALTS)})).groupby("label").a.agg(lambda a: ((a == 0).sum() == 0 and (a == 3).sum() > 0, (a == 0).sum() >= 2, np.isin(a, [0, 3]).any() and not np.isin(a, [0, 3]).all()))
    oc = np.array(oc.tolist()).mean(0) * 100; cm = np.mean(coh, 0)
    for k, nm in enumerate(["no_driver_with_passenger", "two_plus_drivers", "mixed_car_noncar"]):
        rows.append(dict(check="coherence observed", segment="all", mode=nm, recheck=oc[k])); rows.append(dict(check="coherence D group model", segment="all", mode=nm, recheck=cm[k]))
    # engine on the survey population (E): coherence from mc_tours
    ce = []
    for s in range(1, 6):
        m = pd.read_csv(f"{A3}/run_survey/svy_val_respecval_s{s:02d}/output/mc_tours.csv", usecols=["household_id", "joint_id", "alt"]); m = m[m.joint_id != 0]
        m["label"] = m.household_id.astype(str) + "|" + m.joint_id.astype(str); n = m.groupby("label").size(); m = m[m.label.map(n) >= 2]
        z = m.groupby("label").alt.agg(lambda a: ((a == "CD").sum() == 0 and (a == "CP").sum() > 0, (a == "CD").sum() >= 2, a.isin(["CD", "CP"]).any() and not a.isin(["CD", "CP"]).all()))
        ce.append(np.array(z.tolist()).mean(0) * 100)
    for k, nm in enumerate(["no_driver_with_passenger", "two_plus_drivers", "mixed_car_noncar"]): rows.append(dict(check="coherence E engine", segment="all", mode=nm, recheck=np.mean(ce, 0)[k]))
    R = pd.DataFrame(rows)
    # comparison with respec_decompose
    dec = pd.read_csv(f"{A3}/respec_decompose.csv"); dec = dec[dec.weights == "unweighted"].set_index(["segment", "mode"])
    coh0 = pd.read_csv(f"{A3}/respec_joint_coherence.csv").set_index("source")
    def ref(r):
        if r.check == "A sample enumeration": return dec.loc[(r.segment, r["mode"]), "A"]
        if r.check.startswith("D group"): return dec.loc[(r.segment, r["mode"]), "Dgrp"]
        src = {"coherence observed": "observed", "coherence D group model": "Dgrp", "coherence E engine": "E"}[r.check]
        return coh0.loc[src, r["mode"]]
    R["respec_decompose"] = R.apply(ref, axis=1); R["difference"] = R.recheck - R.respec_decompose
    R.to_csv(f"{A3}/respec_joint_recheck.csv", index=False)
    pd.set_option("display.width", 200); print(R[R["mode"].isin(["CD", "CP", "no_driver_with_passenger", "two_plus_drivers", "mixed_car_noncar"])].round(2).to_string(index=False))
    print("max |difference|: A", R[R.check.str.startswith("A")].difference.abs().max().round(3), "D", R[R.check.str.startswith("D")].difference.abs().max().round(3),
          "coherence", R[R.check.str.startswith("coherence")].difference.abs().max().round(3))


if __name__ == "__main__":
    main()
