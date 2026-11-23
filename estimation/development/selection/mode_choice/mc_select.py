#!/usr/bin/env python3
"""Tour mode choice under one base specification for the four segments (re-specification 2026-11-06).

    python3 estimation/development/selection/mode_choice/mc_select.py select      -> selection_log.csv, work/sel_<seg>.pkl
    python3 estimation/development/selection/mode_choice/mc_select.py finalize    -> round 2, backward check, robustness: work/final_<seg>.pkl, final_<seg>.csv, robustness.csv

Base (identical in work, school, shopping, other; blocks of RESPEC_PROTOCOL.md):
  1 constants        ASC of walk, bicycle, car passenger, bus, train (reference car driver)
  2 impedance        generalised cost GC = T + 60 C / VOT (VOT = 0.5 x household income / 2,080 h), one coefficient for car driver,
                     car passenger, bus and train; round-trip km on the five non-reference modes
  5 areas            home zone core city, rural; main-activity zone core city, rural (five modes)
  7 person / hh      age, male, licence, household size, household cars, fewer cars than drivers (control, applied as 0 in DAYMAP);
                     joint household tour (control; shopping and other: the only segments with joint tours); accompanying and
                     recreation tour (other: the purposes inside the segment)
  8 nests            auto (CD, CP), transit (BUS, TRAIN), non-motorised (WK, BK), mu >= 1 (mu = 1: no nesting)
Work tours: WESML weights (as the model of record); the other segments unweighted.
Candidates (order): block 2 the level-of-service forms LOS1 (time + transit out-of-vehicle time + cost / income, replacing GC),
LOS2 (car time and transit in-vehicle time separately + out-of-vehicle time + cost / income), transit out-of-vehicle time added to GC;
block 4 paid-parking share at the destination (CD); block 5 home in the Washington region (TRAIN); block 7 stops of the tour on the
non-car modes, ln density of the main-activity zone on walk and bicycle, household income >= $100k on bus.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, time
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/abit/mode_choice"   # results of the selection (data); CODE = this folder
import mc_core as K     # noqa: E402
import mc_data as MD    # noqa: E402

SEGS = ["work", "school", "shopping", "other"]
NONREF = K.NONREF
LOS_FORMS = {"LOS1": ["time", "ovt", "cost_inc"], "LOS2": ["time_car", "time_pt", "ovt", "cost_inc"]}
CANDS = [(2, "LOS1", "form", "-"), (2, "LOS2", "form", "-"), (2, "ovt", "lin", "-"), (4, "park", "lin", "-"), (5, "wash_TRAIN", "lin", "+"),
         (7, "stops_nonauto", "lin", "-"), (7, "lnden_nonmot", "lin", "+"), (7, "inc_hi_BUS", "lin", "-")]
PRIOR = {"gc": "-", "km_WK": "-", "km_BK": "-", "autos_WK": "-", "autos_BK": "-", "autos_BUS": "-", "autos_TRAIN": "-", "lic_CP": "-",
         "time": "-", "time_car": "-", "time_pt": "-", "ovt": "-", "cost_inc": "-"}
TCRIT = 1.96


def data(seg, half): return MD.build(seg, half)


def weight(seg): return "wesml" if seg == "work" else None


def varies(f, var, a):
    m = f[f"av_{a}"].values > 0
    return f.loc[m, var].std() > 0 if var in f else True


def base_names(seg, f):
    n = [f"ASC_{a}" for a in NONREF] + ["gc"] + [f"km_{a}" for a in NONREF]
    n += [f"{v}_{a}" for v in ["core_o", "rural_o", "core_d", "rural_d"] for a in NONREF]
    pv = ["age", "male", "lic", "hhsize", "autos", "short"] + (["joint"] if seg in ("shopping", "other") else []) + (["acc", "rec"] if seg == "other" else [])
    n += [f"{v}_{a}" for v in pv for a in NONREF]
    n = [p for p in n if not ("_" in p and p.rsplit("_", 1)[1] in K.AI and not p.startswith("ASC_") and not varies(f, p.rsplit("_", 1)[0], p.rsplit("_", 1)[1]))]
    n = [p for p in n if p not in identical(f, n) and p not in separated(f, n) and p != "lic_WK"]
    return n + ["mu_auto", "mu_transit", "mu_nonmot"]


def separated(f, names):
    """0/1 terms of an alternative that is never chosen when the term is 1 (estimate at minus infinity, not identified)"""
    out = []
    for p in names:
        if p.startswith("ASC_") or "_" not in p or p.rsplit("_", 1)[1] not in K.AI: continue
        v, a = p.rsplit("_", 1)
        if v not in f or not set(np.unique(f[v].values)) <= {0.0, 1.0}: continue
        m = (f[f"av_{a}"].values > 0) & (f[v].values == 1)
        if m.sum() > 0 and (f.choice.values[m] == a).sum() == 0: out.append(p)
    return out


def identical(f, names):
    """terms of an alternative whose column equals that of an earlier term of the same alternative on the rows where it is
    available (only their sum is identified): the later one is dropped (e.g. home and main-activity zone rural for walk)"""
    out = []
    for a in K.NONREF:
        m = f[f"av_{a}"].values > 0; seen = []
        for p in names:
            if p.startswith("ASC_") or "_" not in p or p.rsplit("_", 1)[1] != a: continue
            v = p.rsplit("_", 1)[0]
            if v not in f: continue
            x = f.loc[m, v].values
            if any(np.array_equal(x, y) for y in seen): out.append(p)
            else: seen.append(x)
    return out


def bic(r): return np.log(r["N"]) * r["K"] - 2 * r["LL"]


def sign_ok(v, s): return s == "0" or (s == "+" and v > 0) or (s == "-" and v < 0)


def order(names):
    """block order of the table: constants, impedance, attributes, areas, person / household, nests"""
    blk = lambda p: (1 if p.startswith("ASC_") else 2 if p in ("gc", "time", "time_car", "time_pt", "ovt", "cost_inc") or p.startswith(("km_", "gc_")) else
                     4 if p == "park" else 5 if p.startswith(("core_", "rural_", "wash_")) else 8 if p.startswith("mu_") else 7)
    return sorted(names, key=lambda p: (blk(p), names.index(p)))


def fitm(seg, f, names, x0=None, cov=True):
    D = K.Data(f, names, weight(seg)); r = K.fit(D, x0=x0, cov=cov); r["D"] = D; return r


def holdout(seg, fv, r):
    D = K.Data(fv, r["names"], weight(seg)); return K.loglik(D, r["x"])[0]


def tv(r, p): i = r["names"].index(p); return r["x"][i] / r["se"][i] if r["se"][i] > 0 else np.nan


def select_seg(seg):
    f = data(seg, "estimation"); fv = data(seg, "validation"); log = []
    names = base_names(seg, f); r = fitm(seg, f, names)
    while True:
        bad = [(p, tv(r, p)) for p in r["names"] if p in PRIOR and not sign_ok(r["x"][r["names"].index(p)], PRIOR[p]) and abs(tv(r, p)) > 2]
        if not bad: break
        p, t = max(bad, key=lambda z: abs(z[1])); log.append(dict(segment=seg, round=0, candidate=p, estimate=r["x"][r["names"].index(p)], rob_t=t, decision="base term dropped: wrong sign, |t| > 2"))
        names = [q for q in names if q != p]; r = fitm(seg, f, names, x0=dict(zip(r["names"], r["x"])))
    ho = holdout(seg, fv, r)
    log.append(dict(segment=seg, round=0, candidate="base", LL_after=r["LL"], BIC_after=bic(r), holdout_LL_after=ho, decision="base"))
    print(f"[{seg}] base K {r['K']} LL {r['LL']:.2f} BIC {bic(r):.1f} hold-out {ho:.2f} cond {r['cond']:.3g} at bound {r['at_bound']}", flush=True)
    cur, curho = r, ho
    for block, c, kind, sgn in CANDS:
        if kind == "form":
            if "gc" in names:
                nn = [q for q in names if q != "gc"]; i = nn.index("km_WK") if "km_WK" in nn else len(nn); nn = nn[:i] + LOS_FORMS[c] + nn[i:]
            elif c == "LOS2" and "time" in names:
                nn = [q for q in names if q != "time"]; j = nn.index("ovt"); nn = nn[:j] + ["time_car", "time_pt"] + nn[j:]
            else: continue
            new = LOS_FORMS[c]
        else:
            if c in names: continue
            if c == "ovt" and "gc" not in names: continue
            if "_" in c and c.rsplit("_", 1)[1] in K.AI and not varies(f, c.rsplit("_", 1)[0], c.rsplit("_", 1)[1]):
                log.append(dict(segment=seg, round=1, block=block, candidate=c, decision="not applicable")); continue
            nn = order(names + [c]); new = [c]
        x0 = dict(zip(cur["names"], cur["x"]))
        if kind == "form" and "gc" in x0:   # start: time at the GC coefficient, cost_inc at the GC coefficient x 60 / VOT at the reference income
            g = x0["gc"]; x0.update(time=g, time_car=g, time_pt=g, ovt=g, cost_inc=g * 60 / (0.5 * 84216 / 2080))
        r = fitm(seg, f, nn, x0=x0); h = holdout(seg, fv, r)
        est = {p: r["x"][r["names"].index(p)] for p in new}; ts = {p: tv(r, p) for p in new}
        ok_sign = all(sign_ok(v, PRIOR.get(p, sgn)) for p, v in est.items()); ok_t = all(abs(t) >= TCRIT for t in ts.values())
        ok_bic = bic(r) < bic(cur); ok_ho = h > curho
        kept = ok_sign and ok_t and ok_bic and ok_ho
        why = "kept" if kept else "wrong sign" if not ok_sign else f"|t| < {TCRIT}" if not ok_t else "BIC not lower" if not ok_bic else "hold-out LL not higher"
        log.append(dict(segment=seg, round=1, block=block, candidate=c, estimate="; ".join(f"{p} {v:+.4g}" for p, v in est.items()),
                        rob_t="; ".join(f"{p} {t:.2f}" for p, t in ts.items()), LL_before=cur["LL"], LL_after=r["LL"], LR=2 * (r["LL"] - cur["LL"]),
                        BIC_before=bic(cur), BIC_after=bic(r), holdout_LL_before=curho, holdout_LL_after=h, decision=why))
        print(f"  [{seg}] B{block} {c}: {log[-1]['estimate']} (t {log[-1]['rob_t']}); dBIC {bic(r) - bic(cur):+.1f}; dHO {h - curho:+.2f} -> {why}", flush=True)
        if kept: names, cur, curho = nn, r, h
    return names, cur, curho, log


def select():
    logs = []
    for seg in SEGS:
        names, r, ho, log = select_seg(seg); logs += log
        pickle.dump(dict(names=names, x=r["x"], LL=r["LL"], holdout=ho, log=log, base=base_names(seg, data(seg, "estimation"))), open(f"{MD.OUT}/sel_{seg}.pkl", "wb"))
    pd.DataFrame(logs).to_csv(f"{HERE}/selection_log.csv", index=False)


# ------------------------------------------------------------------------------------------------ finalize
CUR = {"work": "gc_work_hh.csv", "school": "gc_school_mnl.csv", "shopping": "gc_shopping_hh.csv", "other": "gc_other_hh.csv"}


def current(seg):
    t = pd.read_csv(f"{MD.MCD}/results/{CUR[seg]}"); return list(t.Name), t.Value.values


def perturb(f, what, eps=0.01):
    g = f.copy(); vot = g.vot.values
    if what == "car time": g["car_min"] = g.car_min * (1 + eps)
    elif what == "car cost": g["cost_CD"] = g.cost_CD * (1 + eps)
    elif what == "transit in-vehicle time": g["bus_ivt"] = g.bus_ivt * (1 + eps); g["train_ivt"] = g.train_ivt * (1 + eps)
    elif what == "transit out-of-vehicle time": g["bus_ovt"] = g.bus_ovt * (1 + eps); g["train_ovt"] = g.train_ovt * (1 + eps)
    elif what == "transit fare": g["bus_c"] = g.bus_c * (1 + eps); g["train_c"] = g.train_c * (1 + eps)
    g["gc_CD"] = g.car_min + 60 * g.cost_CD / vot; g["gc_CP"] = g.car_min
    g["gc_BUS"] = np.where(g.bus_ok, g.bus_ivt + g.bus_ovt + 60 * g.bus_c / vot, 0.0); g["gc_TRAIN"] = np.where(g.train_ok, g.train_ivt + g.train_ovt + 60 * g.train_c / vot, 0.0)
    return g


def shares(seg, f, names, x):
    D = K.Data(f, names, weight(seg)); P = K.probs(D, x); w = f.wesml.values if seg == "work" else f.w.values
    return (P * w[:, None]).sum(0) / w.sum()


def elasticities(seg, f, names, x):
    base = shares(seg, f, names, x); f0 = perturb(f, "none"); b0 = shares(seg, f0, names, x); out = []
    for what in ["car time", "car cost", "transit in-vehicle time", "transit out-of-vehicle time", "transit fare"]:
        s = shares(seg, perturb(f, what), names, x)
        for a, i in K.AI.items(): out.append(dict(segment=seg, variable=what, mode=a, elasticity=(s[i] - b0[i]) / b0[i] / 0.01 if b0[i] > 0 else np.nan))
    return pd.DataFrame(out)


def finalize(nboot=100):
    rob = []; logs = []; elas = []; shr = []
    sel = {s: pickle.load(open(f"{MD.OUT}/sel_{s}.pkl", "rb")) for s in SEGS}
    kept_any = set()
    for s in SEGS: kept_any |= {r["candidate"] for r in sel[s]["log"] if r.get("decision") == "kept"}
    for seg in SEGS:
        f = data(seg, "estimation"); fv = data(seg, "validation"); names = sel[seg]["names"]; log = list(sel[seg]["log"])
        cur = fitm(seg, f, names, x0=dict(zip(names, sel[seg]["x"]))); curho = holdout(seg, fv, cur)
        # round 2: candidates kept in another segment
        for block, c, kind, sgn in CANDS:
            if c not in kept_any or c in names or (kind == "form" and "gc" not in names) or (kind == "form" and set(LOS_FORMS[c]) <= set(names)): continue
            if kind != "form" and "_" in c and c.rsplit("_", 1)[1] in K.AI and not varies(f, c.rsplit("_", 1)[0], c.rsplit("_", 1)[1]): continue
            if kind == "form":
                nn = [q for q in names if q != "gc"]; i = nn.index("km_WK"); nn = nn[:i] + LOS_FORMS[c] + nn[i:]; new = LOS_FORMS[c]
            else: nn = order(names + [c]); new = [c]
            x0 = dict(zip(cur["names"], cur["x"]))
            if "gc" in x0: g = x0["gc"]; x0.update(time=g, time_car=g, time_pt=g, ovt=g, cost_inc=g * 60 / (0.5 * 84216 / 2080))
            r = fitm(seg, f, nn, x0=x0); h = holdout(seg, fv, r)
            est = {p: r["x"][r["names"].index(p)] for p in new}; ts = {p: tv(r, p) for p in new}
            kept = all(sign_ok(v, PRIOR.get(p, sgn)) for p, v in est.items()) and all(abs(t) >= TCRIT for t in ts.values()) and bic(r) < bic(cur) and h > curho
            log.append(dict(segment=seg, round=2, block=block, candidate=c, estimate="; ".join(f"{p} {v:+.4g}" for p, v in est.items()),
                            rob_t="; ".join(f"{p} {t:.2f}" for p, t in ts.items()), LL_before=cur["LL"], LL_after=r["LL"], BIC_before=bic(cur), BIC_after=bic(r),
                            holdout_LL_before=curho, holdout_LL_after=h, decision="kept" if kept else "not kept"))
            print(f"  [{seg}] round 2 {c}: {'kept' if kept else 'not kept'}", flush=True)
            if kept: names, cur, curho = nn, r, h
        # backward check of non-base terms
        base = set(sel[seg]["base"]) | set(sum(LOS_FORMS.values(), []))
        while True:
            weak = [(p, tv(cur, p)) for p in names if p not in base and not p.startswith("mu_") and abs(tv(cur, p)) < TCRIT]
            if not weak: break
            p, t = min(weak, key=lambda z: abs(z[1])); names = [q for q in names if q != p]
            r = fitm(seg, f, names, x0=dict(zip(cur["names"], cur["x"]))); log.append(dict(segment=seg, round=3, candidate=p, rob_t=t, LL_before=cur["LL"], LL_after=r["LL"], decision="removed in the backward check"))
            cur = r; curho = holdout(seg, fv, cur)
        names = order(names); cur = fitm(seg, f, names, x0=dict(zip(cur["names"], cur["x"])))
        # nest parameters on the bound mu = 1 are fixed at 1 (no nesting for that nest), with the LR test of freeing them
        fixed = []
        for p in [q for q in cur["at_bound"] if q.startswith("mu_")]:
            LLf = cur["LL"]; names = [q for q in names if q != p]; cur = fitm(seg, f, names, x0=dict(zip(cur["names"], cur["x"])))
            fixed.append(dict(param=p, LL_free=LLf, LL_fixed=cur["LL"], LR=2 * (LLf - cur["LL"])))
            log.append(dict(segment=seg, round=4, candidate=p, LL_before=LLf, LL_after=cur["LL"], LR=2 * (LLf - cur["LL"]), decision="nest parameter on the bound 1: fixed at 1 (LR test of freeing it)"))
        curho = holdout(seg, fv, cur); D = cur.pop("D")
        tab = K.table(cur)
        se_b, draws = K.cluster_bootstrap(D, cur, B=nboot); tab["boot_se"] = se_b
        rv = fitm(seg, fv, names, x0=dict(zip(names, cur["x"]))); rv.pop("D")
        pool = pd.concat([f, fv], ignore_index=True); rp = fitm(seg, pool, names, x0=dict(zip(names, cur["x"])), cov=False); rp.pop("D")
        from scipy.stats import chi2
        LR = 2 * (cur["LL"] + rv["LL"] - rp["LL"]); df = cur["K"] - len(set(cur["at_bound"]) | set(rv["at_bound"]))
        tab["value_swap"] = rv["x"]; tab["se_swap"] = rv["se"]; tab["z_diff"] = (cur["x"] - rv["x"]) / np.sqrt(cur["se"] ** 2 + rv["se"] ** 2)
        sd = np.sqrt(np.diag(cur["cov"])); Rc = cur["cov"] / np.outer(sd, sd)
        flags = [(names[i], names[j], float(Rc[i, j])) for i in range(len(names)) for j in range(i + 1, len(names)) if np.isfinite(Rc[i, j]) and abs(Rc[i, j]) > 0.9]
        cn, cx = current(seg); Dc = K.Data(fv, cn, weight(seg)); xc = np.array([dict(zip(cn, cx))[n] for n in Dc.names])
        ho_cur = K.loglik(Dc, xc)[0]
        Dce = K.Data(f, cn, weight(seg)); est_cur = K.loglik(Dce, np.array([dict(zip(cn, cx))[n] for n in Dce.names]))[0]
        # shares on the hold-out half (weights: WESML for work, survey person weights otherwise)
        w = fv.wesml.values if seg == "work" else fv.w.values; y = np.array([K.AI[c] for c in fv.choice.values])
        obs = np.array([(w * (y == i)).sum() / w.sum() for i in range(6)])
        s_new = shares(seg, fv, names, cur["x"]); s_cur = shares(seg, fv, cn, xc)
        for a, i in K.AI.items(): shr.append(dict(segment=seg, mode=a, observed=obs[i], respecified=s_new[i], current=s_cur[i]))
        el = elasticities(seg, fv, names, cur["x"]).assign(model="re-specified"); elc = elasticities(seg, fv, cn, xc).assign(model="current")
        elas += [el, elc]
        LL0 = float(-(np.log(D.av.numpy().sum(1)) * D.w.numpy()).sum())
        Dc0 = K.Data(f, [f"ASC_{a}" for a in NONREF], weight(seg)); rc0 = K.fit(Dc0, cov=False)
        out = dict(seg=seg, names=names, x=cur["x"], cov=cur["cov"], se=cur["se"], LL=cur["LL"], LL0=LL0, LLc=rc0["LL"], K=cur["K"], N=cur["N"], N_val=len(fv),
                   holdout=curho, holdout_current=ho_cur, est_current=est_cur, K_current=len(cn), cond=cur["cond"], at_bound=cur["at_bound"], table=tab,
                   swap=dict(LL_est=cur["LL"], LL_val=rv["LL"], LL_pooled=rp["LL"], LR=LR, df=df, p=float(chi2.sf(LR, df)), n_z_gt_196=int((np.abs(tab.z_diff) > 1.96).sum())),
                   corr_flags=flags, nboot=nboot, log=log, weighted=seg == "work", fixed_nests=fixed,
                   nan_se=[n for n, v in zip(names, cur["se"]) if not np.isfinite(v) or v <= 0])
        pickle.dump(out, open(f"{MD.OUT}/final_{seg}.pkl", "wb")); tab.to_csv(f"{HERE}/final_{seg}.csv", index=False); logs += log
        rob.append(dict(segment=seg, K=cur["K"], N=cur["N"], LL=cur["LL"], BIC=bic(cur), holdout_LL=curho, holdout_LL_current=ho_cur, K_current=len(cn),
                        LL_current_est=est_cur, swap_LR=LR, swap_df=df, swap_p=out["swap"]["p"], n_z_gt_196=out["swap"]["n_z_gt_196"],
                        corr_flags=len(flags), cond=cur["cond"], max_boot_over_robust=float(np.nanmax(tab.boot_se / tab.rob_se)), min_boot_over_robust=float(np.nanmin(tab.boot_se / tab.rob_se))))
        print(rob[-1], flush=True)
    pd.DataFrame(rob).to_csv(f"{HERE}/robustness.csv", index=False); pd.DataFrame(logs).to_csv(f"{HERE}/selection_log.csv", index=False)
    pd.concat(elas).to_csv(f"{HERE}/elasticities.csv", index=False); pd.DataFrame(shr).to_csv(f"{HERE}/holdout_shares.csv", index=False)


if __name__ == "__main__":
    select() if sys.argv[1] == "select" else finalize()
