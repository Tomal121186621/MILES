#!/usr/bin/env python3
"""Application of the estimated tour mode choice (GC specification, the models of record estimate_gc.CHOSEN) in Python, the
utility of MarylandTourNestedModeChoice:

    python3 activity/lib/mode_choice/mc_apply.py calibrate         ASC adjustments of the calibrated variant -> 3_abit/coef_tasha_cal/mc_asc_adjust.csv
    python3 activity/lib/mode_choice/mc_apply.py elasticities      aggregate elasticities by sample enumeration -> results/elasticities.csv
    python3 activity/lib/mode_choice/mc_apply.py observed          verification / validation on the observed tours, 10 replications -> results/obs_validation.csv
    python3 activity/lib/mode_choice/mc_apply.py javacheck RUNDIR  Java probabilities (output/mc_tours.csv of a survey-population run) against Python

Observed-tour tests (mode choice isolated): each survey tour is taken as given (home, main destination, start and end of the main
activity, stops, the person and household) and its mode is drawn from the model (seeds 1-10); shares weighted by the person
weights on both sides; band = 5th-95th percentile of the 10 replications (90 %).  The household stage of the application (joint
tours, car allocation) is not applied to the observed tours: their joint travel and car use are observed outcomes.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/mode_choice"   # data folder; CODE = this folder
import mc_common as M   # noqa: E402
A3 = os.path.dirname(HERE)
# 2026-11-02: household-structure terms (estimate_hh.py): work + short, shopping + joint, other + joint and purpose; school unchanged
CHOSEN = {"work": "hh", "school": "mnl", "shopping": "hh", "other": "hh"}
CHOSEN_PRE_REEST = {"work": "nl_dest_gen", "school": "mnl", "shopping": "mnl_gen", "other": "nl_dest_gen"}
ALTS = M.ALTS2; NEST_OF = np.array([0, 2, 2, 0, 1, 1]); NEST = ["auto", "transit", "nonmot"]
SOCIO = ["age", "male", "lic", "hhsize", "autos", "core_o", "rural_o", "core_d", "rural_d", "joint", "short", "acc", "rec"]
OUTMODE = ["CAR_DRIVER", "CAR_PASSENGER", "BUS", "TRAIN", "WALK", "BIKE"]; ALT2OUT = {"CD": 0, "CP": 1, "BUS": 2, "TRAIN": 3, "WK": 4, "BK": 5}


def coef(chosen=CHOSEN):
    return {s: pd.read_csv(f"{M.RES}/gc_{s}_{m}.csv").set_index("Name").Value.to_dict() for s, m in chosen.items()}


def utilities(f, b, adj=None):
    V = np.zeros((len(f), 6))
    for a, alt in enumerate(ALTS):
        v = np.full(len(f), b.get(f"ASC_{alt}", 0.0) + (adj.get(alt, 0.0) if adj else 0.0)) + b.get(f"km_{alt}", 0.0) * f.km.values
        if alt in ("CD", "CP", "BUS", "TRAIN"): v = v + b.get(f"gc_{alt}", b.get("gc", 0.0)) * f[f"gc_{alt}"].values
        for s in SOCIO:
            if f"{s}_{alt}" in b: v = v + b[f"{s}_{alt}"] * f[s].values
        V[:, a] = v
    av = np.stack([f[f"av_{a}"].values > 0 for a in ALTS], 1)
    return V, av


def probs(V, av, b):
    V = np.where(av, V, -np.inf); mx = V.max(1, keepdims=True); E = np.where(av, np.exp(V - mx), 0.0)
    if not any(f"mu_{k}" in b for k in NEST): return E / E.sum(1, keepdims=True)
    mu = np.array([b.get(f"mu_{k}", 1.0) for k in NEST])
    Em = np.where(av, np.exp(mu[NEST_OF] * np.where(av, V - mx, 0)), 0.0); S = np.stack([Em[:, NEST_OF == k].sum(1) for k in range(3)], 1)
    I = np.where(S > 0, np.log(np.where(S > 0, S, 1)) / mu, -np.inf); D = np.exp(I).sum(1); P = np.zeros_like(E)
    for a in range(6): k = NEST_OF[a]; P[:, a] = np.where(S[:, k] > 0, np.exp(I[:, k]) / D * Em[:, a] / np.where(S[:, k] > 0, S[:, k], 1), 0.0)
    return P


def tours(half, vot_share=0.5, t=None):
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet") if t is None else t
    f = M.features2(t, vot_share)
    for k in ["choice2", "segment", "purpose", "w", "county", "km", "pout", "autos", "drivers", "inc_year", "h", "m"]:
        if k in t: f[k if k != "choice2" else "choice"] = t[k].values
    hh_terms(f, t.joint.astype(bool).values if "joint" in t else None)
    return f, t


def hh_terms(f, joint=None):
    """household-structure terms (estimate_hh.py): joint (observed flag, or 0 as in MAST's person-level choice), short (fewer
    cars than licensed drivers, at least one car), acc / rec (purpose within the 'other' segment)"""
    f["joint"] = 0.0 if joint is None else np.asarray(joint, float)
    f["short"] = ((f.autos > 0) & (f.autos < f.drivers)).astype(float) if "drivers" in f else 0.0
    p = f.purpose if "purpose" in f else pd.Series("", index=f.index)
    f["acc"] = p.eq("ACCOMPANY").astype(float).values; f["rec"] = p.eq("RECREATION").astype(float).values


def predict(f, cf, adj=None):
    P = np.zeros((len(f), 6))
    for s in M.SEGMENTS:
        i = np.where(f.segment.values == s)[0]
        if len(i): V, av = utilities(f.iloc[i], cf[s], adj.get(s) if adj else None); P[i] = probs(V, av, cf[s])
    return P


def wshare(P, w, m=None):
    m = np.ones(len(w), bool) if m is None else m
    return (P[m] * w[m, None]).sum(0) / w[m].sum()


def calibrate():
    """calibrated variant only: ASC adjustments delta += ln(observed / predicted weighted share) per segment and mode on the
    observed tours of the estimation half (survey weights), until every share is within 0.1 pp"""
    f, _ = tours("estimation"); cf = coef(); w = f.w.values; adj = {s: {a: 0.0 for a in ALTS} for s in M.SEGMENTS}
    seg = f.segment.values; ch = f.choice.values
    obs = {s: np.array([w[(seg == s) & (ch == a)].sum() for a in ALTS]) / w[seg == s].sum() for s in M.SEGMENTS}
    for it in range(200):
        P = predict(f, cf, adj); dmax = 0
        for s in M.SEGMENTS:
            pr = wshare(P, w, seg == s)
            for k, a in enumerate(ALTS):
                if a == "CD" or obs[s][k] <= 0: continue
                adj[s][a] += np.log(obs[s][k] / max(pr[k], 1e-6)); dmax = max(dmax, abs(obs[s][k] - pr[k]))
        if dmax < 1e-3: break
    rows = [dict(segment=s, alt=a, delta=adj[s][a]) for s in M.SEGMENTS for a in ALTS]
    pd.DataFrame(rows).to_csv(f"{A3}/coef_tasha_cal/mc_asc_adjust.csv", index=False); pd.DataFrame(rows).to_csv(f"{M.RES}/asc_adjust.csv", index=False)
    print(f"calibration: {it + 1} iterations, max share error {dmax:.4f}")


def elasticities():
    """aggregate point elasticities of the weighted mode shares (+1 % arc, sample enumeration, estimation half): car time, car
    operating cost, transit time (bus and train door-to-door minutes), transit fare"""
    t0 = pd.read_parquet(f"{M.WORK}/tours_estimation.parquet"); cf = coef()
    f0, _ = tours("estimation", t=t0); w = f0.w.values; base = predict(f0, cf); rows = []
    cases = {"car time": dict(car_min=1.01), "car operating cost": "opc", "transit time": dict(bus_t=1.01, train_t=1.01), "transit fare": "fare"}
    for name, ch in cases.items():
        t = t0.copy()
        if ch == "opc": t["toll"] = 0.01 * t.km * M.OPC_KM
        elif ch == "fare": t["bus_c"] = t.bus_c * 1.01; t["train_c"] = t.train_c * 1.01   # train_c includes the drive-access cost (small)
        else:
            for k, x in ch.items(): t[k] = t[k] * x
        f1, _ = tours("estimation", t=t); P = predict(f1, cf)
        for seg in ["all"] + M.SEGMENTS:
            m = np.ones(len(f0), bool) if seg == "all" else f0.segment.values == seg
            s0, s1 = wshare(base, w, m), wshare(P, w, m)
            for k, a in enumerate(ALTS): rows.append(dict(variable=name, segment=seg, alt=a, share=s0[k], elasticity=(s1[k] / s0[k] - 1) / 0.01 if s0[k] > 0 else np.nan))
    e = pd.DataFrame(rows); e.to_csv(f"{M.RES}/elasticities.csv", index=False)
    print(e[e.segment.eq("all")].pivot(index="variable", columns="alt", values="elasticity").round(3).to_string())


DBANDS = [0, 2, 5, 10, 20, 40, 80, 1e9]; DLAB = ["0-2", "2-5", "5-10", "10-20", "20-40", "40-80", "80+"]


def groups(f):
    return {"purpose": f.purpose.values, "distance": pd.cut(f.km.values / 2, DBANDS, labels=DLAB, right=False).astype(str),
            "period": np.array(M.PERIODS)[f.pout.values],
            "cars": np.select([f.autos.values <= 0, f.autos.values < f.drivers.values], ["0 cars", "cars < drivers"], "cars >= drivers"),
            "income": np.select([f.inc_year.values < 50000, f.inc_year.values < 100000], ["< $50k", "$50-100k"], "$100k+"),
            "county": f.county.astype(int).astype(str).values, "all": np.full(len(f), "all")}


def observed():
    cf = coef(); rows = []; adjf = pd.read_csv(f"{M.RES}/asc_adjust.csv"); adj_cal = {s: dict(zip(g.alt, g.delta)) for s, g in adjf.groupby("segment")}
    for half, setting in [("estimation", "verification"), ("validation", "validation")]:
        f, _ = tours(half); w = f.w.values; G = groups(f); oo = np.array([ALT2OUT[a] for a in f.choice.values])
        for vname, adj in [("behavioural", None), ("calibrated", adj_cal)]:
            P = predict(f, cf, adj); cP = P.cumsum(1); draws = []
            for rep in range(10):
                u = np.random.default_rng(rep + 1).random(len(f)) * cP[:, -1]; c = (u[:, None] > cP).sum(1).clip(0, 5)
                draws.append(np.array([ALT2OUT[ALTS[x]] for x in c]))
            for dim, lab in G.items():
                for gv in np.unique(lab):
                    m = lab == gv
                    if m.sum() < 30: continue
                    for k, mo in enumerate(OUTMODE):
                        reps = np.array([w[m & (d == k)].sum() / w[m].sum() for d in draws])
                        rows.append(dict(setting=setting, variant=vname, dim=dim, group=gv, mode=mo, n_tours=int(m.sum()), observed=w[m & (oo == k)].sum() / w[m].sum(),
                                         model=reps.mean(), model_sd=reps.std(ddof=1), p05=np.percentile(reps, 5), p95=np.percentile(reps, 95)))
    r = pd.DataFrame(rows); r.to_csv(f"{M.RES}/obs_validation.csv", index=False)
    s = r[r.dim.isin(["all"])]; print(s.pivot_table(index=["setting", "variant"], columns="mode", values=["observed", "model"]).round(3).to_string())


def javacheck(run_dir):
    """recompute the person-level probabilities of the tours the Java class wrote (output/mc_tours.csv) for the same persons"""
    name = os.path.basename(run_dir.rstrip("/")); half = "estimation" if "_est_" in name else "validation"
    j = pd.read_csv(f"{run_dir}/output/mc_tours.csv")
    sp = f"{A3}/survey_pop/{half}"; pp = pd.read_csv(f"{sp}/pp.csv"); hh = pd.read_csv(f"{sp}/hh.csv").set_index("id")
    pp["lic"] = pp.driversLicense.astype(str).eq("True"); pp["inc_m"] = np.floor(pp.income / 12.0)
    g = pp.groupby("hhID").agg(drivers=("lic", "sum"), hhsize=("age", "size"), inc_month=("inc_m", "sum"))
    q = pp.set_index("id").join(g, on="hhID").join(hh[["autos"]], on="hhID").reindex(j.person_id.values)
    idx = M.C.id2idx()
    t = pd.DataFrame(dict(h=idx[j.home_zone.values], m=idx[j.main_zone.values], age=q.age.values, male=(q.gender.values == 1).astype(float), lic=q.lic.values.astype(float),
                          hhsize=q.hhsize.values, autos=q.autos.values, inc_year=12 * q.inc_month.values, segment=j.segment.values))
    t["pout"] = M.period(j.start.values); t["pret"] = M.period(j.end.values)
    for k, x in M.tour_los2(t.h.values, t.m.values, t.pout.values, t.pret.values).items(): t[k] = x
    f = M.features2(t); f["segment"] = t.segment.values; f["purpose"] = j.purpose.values; hh_terms(f)   # joint, short applied as 0 (mc.zero.terms)
    P = predict(f, coef()); J = j[[f"p_{a}" for a in ALTS]].values; d = np.abs(P - J).max(1)
    print(f"{name}: {len(j)} tours; max |dP| {d.max():.2e}, 99th percentile {np.percentile(d, 99):.2e}, share > 1e-3 {np.mean(d > 1e-3):.4f}")
    pd.DataFrame(dict(run=[name], tours=[len(j)], max_abs_dp=[d.max()], p99=[np.percentile(d, 99)], share_gt_1e3=[np.mean(d > 1e-3)])).to_csv(f"{M.RES}/java_check.csv", index=False)


if __name__ == "__main__":
    c = sys.argv[1]
    {"calibrate": calibrate, "elasticities": elasticities, "observed": observed}.get(c, lambda: javacheck(sys.argv[2]))()
