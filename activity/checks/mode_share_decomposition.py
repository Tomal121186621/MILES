#!/usr/bin/env python3
"""Decomposition of the predicted tour mode shares on the OBSERVED hold-out tours (validation half of the 2017/18 RTS; the tours of
the mode-choice estimation data, side_experiments/respec_2026-11/step_by_step/mode_choice m07/m08 data()), one change per step:
  A  sample enumeration: sum of the estimated probabilities (estimation availability: m10_car_availability, simultaneous use)
  B  simulation: random-utility draws of the estimated models (MNL Gumbel; nested logit exact GEV draw, as the engine's drawU), 5 seeds,
     estimation availability, no allocation
  C  B with the engine's availability (licence, 16+, a household car) and the TASHA car allocation on the observed windows (leave,
     arrive) and the observed household cars (MarylandTourNestedModeChoice.allocate: per household the feasible set of car-driver
     units with the largest utility gain, a tour without a car takes its best other alternative)
  D  C with the engine's joint-group procedure for the observed joint tours (household, jgid of the main episode, two or more tours):
     driver = the member with car driver available and the largest u_CD - u_CP, group utility = sum of the members' utilities (car
     driver: the driver's u_CD, the others' u_CP), group mode = best summed utility, the group is one car-driver unit (driver's window)
  Dfix  C with the joint tours as fixed in the engine (2026-11-10): every member keeps its own choice (joint term per person, as
     estimated), no group draw; the car-driver members of a joint group are one car unit (union of windows, summed gains)
  E  the engine on the hold-out survey population (run_survey/svy_val_respecval_s01-05, mc_tours.csv): ABIT's simulated tours
Shares per segment and mode (CD, CP, WK, BK, BUS, TRAIN), unweighted and with the RTS person weights (w); observed = choice2.
Utilities: accessibility_new/mode_logsum_new.utilities (the Python form that the unit check matched to the engine to <= 1e-7).
    ~/.venvs/biogeme/bin/python activity/checks/mode_share_decomposition.py   -> respec_decompose.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
V = WORKSPACE; A3 = f"{V}/3_abit"; SBS = f"{ESTIMATION_RESULTS}"   # data
sys.path.insert(0, f"{MILES_HOME}/estimation/development/tour_mode_choice"); sys.path.insert(0, f"{MILES_HOME}/estimation/development/accessibility"); sys.path.insert(0, f"{MILES_HOME}/activity/lib/mode_choice")
import m07_children as K7, m10_car_availability as CA, mode_logsum_new as LN, mc_common as M   # noqa: E402
ALTS = LN.ALTS; SEGS = ["work", "shopping", "other", "school"]; NEST = {"CD": 0, "CP": 0, "BUS": 1, "TRAIN": 1, "WK": 2, "BK": 3}
HALF = "validation"; SEEDS = range(1, 6)


def frame():
    """hold-out tours of all segments with utilities, availabilities and household data"""
    t = pd.read_parquet(f"{M.WORK}/tours_{HALF}.parquet").reset_index(drop=True); f = M.features2(t, 0.5); blk = CA.blocked(HALF)
    f.loc[blk, "av_CD"] = 0; ch = t.choice2.values
    ok = np.array([f[f"av_{c}"].iat[i] > 0 for i, c in enumerate(ch)]); jg = CA.analyse(HALF)[0].jg.values
    parts = []
    for seg in SEGS:
        g = K7.data(HALF, seg); idx = np.where(t.segment.eq(seg).values & ok)[0]; assert len(idx) == len(g)
        assert np.allclose(g.gc_CD.values, f.gc_CD.values[idx])
        Vd, AV = LN.utilities(seg, {k: g[k].values for k in g.columns}); _, lp = LN.logsum_and_logp(seg, Vd, AV)
        d = pd.DataFrame({"row": idx, "segment": seg, "choice": g.choice.values, "w": t.w.values[idx], "hh": t.household_id.values[idx],
                          "pid": t.person_id.values[idx], "leave": t.leave.values[idx], "arrive": t.arrive.values[idx], "autos": t.autos.values[idx],
                          "jg": jg[idx], "cd_plain": ((g.lic > 0) & (g.autos > 0) & (g.age >= 16)).values, "age": g.age.values})
        for a in ALTS: d[f"V_{a}"] = Vd[a]; d[f"av_{a}"] = AV[a]; d[f"p_{a}"] = np.where(AV[a], np.exp(lp[a]), 0.0)
        if seg in ("shopping", "other"):   # group-level model of the joint tours (m11_joint_group.py), utilities with joint = 1
            sj = f"{seg}_joint"; cj = pd.read_csv(f"{SBS}/mode_choice/m11_joint_coef.csv"); cj = cj[cj.segment == sj]
            LN._coef[sj] = dict(zip(cj.param, cj.coef.astype(float))); LN.FORM[sj] = LN.FORM[seg]
            if seg in LN.NESTS: LN.NESTS[sj] = LN.NESTS[seg]
            fj = {k: g[k].values for k in g.columns}; fj["joint"] = np.ones(len(g)); Vj, _ = LN.utilities(sj, fj)
            for a in ALTS: d[f"VJ_{a}"] = Vj[a]; d[f"hasJ_{a}"] = a == "CD" or f"ASC_{a}" in LN._coef[sj]
        AV2 = dict(AV); AV2["CD"] = d.cd_plain.values; _, lp2 = LN.logsum_and_logp(seg, Vd, AV2); d["pplain_CD"] = np.where(AV2["CD"], np.exp(lp2["CD"]), 0.0)
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


def coef_mu(seg):
    b = LN.coef(seg); return {k: b.get(f"mu_{k}", 1.0) for k in ("auto", "transit")}


def stable(a, n, rng):
    U = np.pi * rng.random(n); E = rng.exponential(size=n)
    return np.sin(a * U) / np.sin(U) ** (1 / a) * (np.sin((1 - a) * U) / E) ** ((1 - a) / a)


def draw_u(d, rng, cd_av):
    """random utilities (n x 6), unavailable -inf; nested segment (other): u = V + (nu + ln S_k) / mu_k"""
    n = len(d); U = np.empty((n, 6))
    nu = rng.gumbel(size=(n, 6))
    for s, idx in d.groupby("segment").indices.items():
        mu = coef_mu(s); nested = s in LN.NESTS
        eta = {k: (np.log(stable(1 / mu[k], len(idx), rng)) / mu[k] if nested and mu[k] > 1 else np.zeros(len(idx))) for k in ("auto", "transit")}
        for j, a in enumerate(ALTS):
            v = d[f"V_{a}"].values[idx]
            if nested and a in ("CD", "CP"): U[idx, j] = v + nu[idx, j] / mu["auto"] + eta["auto"]
            elif nested and a in ("BUS", "TRAIN"): U[idx, j] = v + nu[idx, j] / mu["transit"] + eta["transit"]
            else: U[idx, j] = v + nu[idx, j]
    av = np.stack([d[f"av_{a}"].values for a in ALTS], 1).astype(bool); av[:, 0] = cd_av
    U[~av] = -np.inf
    return U


def max_conc(w0, w1, sel):
    mx = 0
    for i in np.where(sel)[0]:
        mx = max(mx, int(((w0[sel] <= w0[i]) & (w0[i] < w1[sel])).sum()))
    return mx


def allocate(cars, w0, w1, gain):
    """MarylandTourNestedModeChoice.allocate: exhaustive per connected set (<= 12), greedy beyond"""
    n = len(w0); keep = np.ones(n, bool); order = np.argsort(w0, kind="stable"); i = 0
    while i < n:
        comp = [order[i]]; end = w1[order[i]]; k = i + 1
        while k < n and w0[order[k]] < end: comp.append(order[k]); end = max(end, w1[order[k]]); k += 1
        i = k; comp = np.array(comp); a0, a1, g = w0[comp], w1[comp], gain[comp]
        if max_conc(a0, a1, np.ones(len(comp), bool)) <= cars: continue
        m = len(comp); best = np.zeros(m, bool)
        if m <= 12:
            bv = -np.inf
            for mask in range(1 << m):
                s = np.array([(mask >> q) & 1 for q in range(m)], bool); v = g[s].sum()
                if v > bv + 1e-12 and max_conc(a0, a1, s) <= cars: bv, best = v, s
        else:
            for q in np.argsort(-g, kind="stable"):
                best[q] = True
                if max_conc(a0, a1, best) > cars: best[q] = False
        keep[comp] = best
    return keep


def draw_one(model, v, av, rng):
    """random utilities of one choice situation of a (possibly nested) model, as draw_u / the engine's drawU"""
    b = LN.coef(model); nested = model in LN.NESTS; nu = rng.gumbel(size=6); u = np.full(6, -np.inf)
    mu = {k: b.get(f"mu_{k}", 1.0) for k in ("auto", "transit")}
    eta = {k: (np.log(stable(1 / mu[k], 1, rng))[0] / mu[k] if nested and mu[k] > 1 else 0.0) for k in mu}
    for j, a in enumerate(ALTS):
        if not av[j]: continue
        if nested and a in ("CD", "CP"): u[j] = v[j] + nu[j] / mu["auto"] + eta["auto"]
        elif nested and a in ("BUS", "TRAIN"): u[j] = v[j] + nu[j] / mu["transit"] + eta["transit"]
        else: u[j] = v[j] + nu[j]
    return u


def repassign(rows, rp, a, U, alt, stats, d):
    for r in rows:
        if r == rp: alt[r] = a
        elif a == 0: alt[r] = 3
        elif d[f"av_{ALTS[a]}"].values[r]: alt[r] = a
        else: alt[r] = 1 + int(U[r, 1:].argmax()); stats["rep_unavailable"] = stats.get("rep_unavailable", 0) + 1
    stats["rep_members"] = stats.get("rep_members", 0) + len(rows)


def simulate(d, seed, alloc, joint):
    rng = np.random.default_rng(seed); cd_av = d.cd_plain.values if alloc else d.av_CD.values.astype(bool)
    U = draw_u(d, rng, cd_av); alt = U.argmax(1); stats = dict(units=0, reassigned=0)
    if not (alloc or joint): return alt, stats
    for hh, idx in d.groupby("hh").indices.items():
        units = []   # (rows, U row of the unit, window)
        done = set()
        if joint == "grp":   # representative applying the group-level model (mc.joint.model = group, engine 2026-11-10)
            sub = d.iloc[idx]; sj = sub[sub.jg >= 0]
            for jg, gi in sj.groupby("jg").indices.items():
                rows = sj.index.values[gi]
                if len(rows) < 2: continue
                done |= set(rows); cand = [r for r in rows if U[r, 0] > -np.inf]
                rp = max(cand, key=lambda r: d.age.values[r]) if cand else max(rows, key=lambda r: d.age.values[r])
                seg = d.segment.values[rp]
                if seg in ("shopping", "other") and np.isfinite(d[f"VJ_CP"].values[rp]):
                    v = np.array([d[f"VJ_{a}"].values[rp] for a in ALTS]); av = np.array([bool(d[f"av_{a}"].values[rp]) and bool(d[f"hasJ_{a}"].values[rp]) for a in ALTS])
                    av[0] = bool(cand); uj = draw_one(seg + "_joint", v, av, rng)
                else: uj = U[rp].copy()
                a0 = int(np.argmax(uj)); repassign(rows, rp, a0, U, alt, stats, d)
                if a0 == 0:
                    G = np.full(6, -np.inf); G[0] = uj[0] - np.max(uj[1:]); G[3] = 0.0
                    units.append(([rp], G, (d.leave.values[rp], d.arrive.values[rp]), rows, uj))
        elif joint == "rep":   # mc.joint.rule = representative (engine, 2026-11-10; TASHA JointTourRep)
            sub = d.iloc[idx]
            sj = sub[sub.jg >= 0]
            for jg, gi in sj.groupby("jg").indices.items():
                rows = sj.index.values[gi]   # positions in d (gi are positions in sj)
                if len(rows) < 2: continue
                done |= set(rows); cand = [r for r in rows if U[r, 0] > -np.inf]
                rp = max(cand, key=lambda r: d.age.values[r]) if cand else max(rows, key=lambda r: d.age.values[r])
                a0 = int(U[rp].argmax()); repassign(rows, rp, a0, U, alt, stats, d)
                if a0 == 0:
                    G = np.full(6, -np.inf); G[0] = U[rp, 0] - U[rp, 1:].max(); G[3] = 0.0
                    units.append(([rp], G, (d.leave.values[rp], d.arrive.values[rp]), rows))
        elif joint == "hh":   # mc.joint.driver = household (engine, 2026-11-10)
            sub = d.iloc[idx]
            sj = sub[sub.jg >= 0]
            for jg, gi in sj.groupby("jg").indices.items():
                rows = sj.index.values[gi]   # positions in d (gi are positions in sj)
                if len(rows) < 2: continue
                done |= set(rows); q = np.prod(1 - d.pplain_CD.values[rows]); drv, best = None, -np.inf
                for r in rows:
                    if U[r, 0] > -np.inf:
                        adv = U[r, 0] - U[r, 1:].max()
                        if adv > best: best, drv = adv, r
                car = drv is not None and rng.random() < 1 - q
                for r in rows:
                    cu = alt[r] in (0, 3)
                    if car: alt[r] = 0 if r == drv else (3 if cu else alt[r])
                    elif cu: alt[r] = [1, 2, 4, 5][int(np.argmax(U[r, [1, 2, 4, 5]]))] if np.isfinite(U[r, [1, 2, 4, 5]]).any() else 3
                if car:
                    G = np.full(6, -np.inf); G[0] = best; G[3] = 0.0
                    units.append(([drv], G, (d.leave.values[drv], d.arrive.values[drv])))
        elif joint == "own":
            sub = d.iloc[idx]
            sj = sub[sub.jg >= 0]
            for jg, gi in sj.groupby("jg").indices.items():
                rows = sj.index.values[gi]   # positions in d (gi are positions in sj)
                if len(rows) < 2: continue
                done |= set(rows); cdm = [r for r in rows if alt[r] == 0]
                if not cdm: continue
                gn = sum(U[r, 0] - U[r, 1:].max() for r in cdm); G = np.full(6, -np.inf); G[0] = gn; G[3] = 0.0
                units.append((cdm, G, (min(d.leave.values[r] for r in cdm), max(d.arrive.values[r] for r in cdm))))
        elif joint:
            sub = d.iloc[idx]
            sj = sub[sub.jg >= 0]
            for jg, gi in sj.groupby("jg").indices.items():
                rows = sj.index.values[gi]   # positions in d (gi are positions in sj)
                if len(rows) < 2: continue
                done |= set(rows); cand = [r for r in rows if U[r, 0] > -np.inf]
                drv = max(cand, key=lambda r: U[r, 0] - U[r, 3]) if cand else None
                G = np.zeros(6)
                for j in range(6):
                    if j == 0: G[0] = (U[drv, 0] + sum(U[r, 3] for r in rows if r != drv)) if drv is not None else -np.inf
                    else: G[j] = U[rows, j].sum()
                a = int(G.argmax()); alt[rows] = np.where(np.array(rows) == drv, 0, 3) if a == 0 else a
                if a == 0: units.append((rows, G, (d.leave.values[drv], d.arrive.values[drv])))
        if alloc:
            for r in idx:
                if r not in done and alt[r] == 0: units.append(([r], U[r], (d.leave.values[r], d.arrive.values[r])))
            if not units: continue
            w0 = np.array([u[2][0] for u in units]); w1 = np.array([u[2][1] for u in units])
            gain = np.array([u[1][0] - u[1][1:].max() for u in units]); keep = allocate(int(d.autos.values[idx[0]]), w0, w1, gain)
            stats["units"] += len(units); stats["reassigned"] += int((~keep).sum())
            for u, k in zip(units, keep):
                if not k:
                    if len(u) == 5: repassign(u[3], u[0][0], 1 + int(np.argmax(u[4][1:])), U, alt, stats, d); continue
                    if len(u) == 4: repassign(u[3], u[0][0], 1 + int(U[u[0][0], 1:].argmax()), U, alt, stats, d); continue
                    for r in u[0]: alt[r] = 1 + int(U[r, 1:].argmax())
    return alt, stats


def shares(seg, alt_or_p, w, kind):
    if kind == "p": s = (alt_or_p * w[:, None]).sum(0) / w.sum()
    else: s = np.array([w[alt_or_p == j].sum() for j in range(6)]) / w.sum()
    return dict(zip(ALTS, 100 * s))


def engine_runs():
    pm = pd.read_csv(f"{A3}/survey_pop/{HALF}/persons_map.csv").drop_duplicates("id").set_index("id").person_id
    t = pd.read_parquet(f"{M.WORK}/tours_{HALF}.parquet"); pw = t.groupby("person_id").w.first()
    out = []
    for s in SEEDS:
        m = pd.read_csv(f"{A3}/run_survey/svy_val_respecval_s{s:02d}/output/mc_tours.csv", usecols=["person_id", "segment", "alt"])
        m["w"] = m.person_id.map(pm).map(pw); out.append(m)
    return out


def main():
    d = frame(); rows = []
    P = np.stack([d[f"p_{a}"].values for a in ALTS], 1); obs = d.choice.map({a: j for j, a in enumerate(ALTS)}).values
    sims = {k: [simulate(d, s, *f) for s in SEEDS] for k, f in {"B": (False, False), "C": (True, False), "D": (True, True), "Dfix": (True, "own"), "Dhh": (True, "hh"), "Drep": (True, "rep"), "Dgrp": (True, "grp")}.items()}
    E = engine_runs()
    for wk in ("unweighted", "RTS weights"):
        for seg in SEGS:
            m = d.segment.values == seg; w = d.w.values[m] if wk == "RTS weights" else np.ones(m.sum())
            row = {"weights": wk, "segment": seg, "tours": int(m.sum())}
            o = shares(seg, obs[m], w, "a"); a = shares(seg, P[m], w, "p")
            vals = {"obs": o, "A": a}
            for k, L in sims.items():
                v = [shares(seg, alt[m], w, "a") for alt, _ in L]
                vals[k] = {x: np.mean([q[x] for q in v]) for x in ALTS}; vals[k + "_sd"] = {x: np.std([q[x] for q in v], ddof=1) for x in ALTS}
            ev = []
            for e in E:
                g = e[e.segment == seg]; ww = g.w.fillna(0).values if wk == "RTS weights" else np.ones(len(g))
                ev.append({x: 100 * ww[g.alt.values == x].sum() / ww.sum() for x in ALTS})
            vals["E"] = {x: np.mean([q[x] for q in ev]) for x in ALTS}
            for x in ALTS:
                rows.append(dict(row, mode=x, **{k: v[x] for k, v in vals.items()}))
    r = pd.DataFrame(rows)
    st = {k: (sum(s["units"] for _, s in L) / len(L), sum(s["reassigned"] for _, s in L) / len(L)) for k, L in sims.items()}
    r.to_csv(f"{A3}/respec_decompose.csv", index=False)
    # coherence of the joint groups (observed joint episodes with >= 2 tours in the sample; engine: household + joint id)
    sub = d[d.jg >= 0]; grp = [sub.index.values[v] for v in sub.groupby(["hh", "jg"]).indices.values() if len(v) >= 2]   # positions in d
    def coh(alts):
        z = np.array([[(a == 0).sum(), (a == 3).sum(), np.isin(a, [0, 3]).sum(), len(a)] for a in alts])
        return dict(groups=len(z), no_driver_with_passenger=100 * np.mean((z[:, 0] == 0) & (z[:, 1] > 0)), two_plus_drivers=100 * np.mean(z[:, 0] >= 2),
                    mixed_car_noncar=100 * np.mean((z[:, 2] > 0) & (z[:, 2] < z[:, 3])))
    C = [dict(source="observed", **coh([obs[g] for g in grp]))]
    for k in ("C", "D", "Dfix", "Dhh", "Drep", "Dgrp"):
        v = [coh([alt[g] for g in grp]) for alt, _ in sims[k]]; C.append(dict(source=k, **{q: np.mean([x[q] for x in v]) for q in v[0]}))
    code = {a: j for j, a in enumerate(ALTS)}; v = []
    for s in SEEDS:
        m = pd.read_csv(f"{A3}/run_survey/svy_val_respecval_s{s:02d}/output/mc_tours.csv", usecols=["household_id", "joint_id", "alt"])
        m = m[m.joint_id != 0]; gs = [g.alt.map(code).values for _, g in m.groupby(["household_id", "joint_id"]) if len(g) >= 2]; v.append(coh(gs))
    C.append(dict(source="E", **{q: np.mean([x[q] for x in v]) for q in v[0]}))
    C = pd.DataFrame(C); C.to_csv(f"{A3}/respec_joint_coherence.csv", index=False); print(C.round(2).to_string(index=False))
    pd.set_option("display.width", 220)
    print(r[r["mode"].isin(["CD", "CP", "WK", "BUS", "TRAIN"])].round(2).to_string(index=False))
    print("car-driver units / reassigned per run:", {k: tuple(round(x, 1) for x in v) for k, v in st.items()})
    rs = [s for _, s in sims["Drep"]]; print("representative rule: members", np.mean([s.get("rep_members", 0) for s in rs]), "group mode unavailable", np.mean([s.get("rep_unavailable", 0) for s in rs]))
    print("joint groups (observed, >= 2 tours):", int(d[d.jg >= 0].groupby(["hh", "jg"]).size().ge(2).sum()), "tours in them:",
          int(d[d.jg >= 0].groupby(["hh", "jg"]).size().pipe(lambda s: s[s >= 2].sum())))


if __name__ == "__main__":
    main()
