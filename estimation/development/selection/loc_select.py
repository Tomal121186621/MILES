#!/usr/bin/env python3
"""Selection and robustness of the ABIT location models under one base specification (re-specification 2026-11-06).

    TAZ_THREADS=5 python3 estimation/development/selection/loc_select.py select   SEG[,SEG..]   -> <folder>/work/sel_<SEG>.pkl, <folder>/selection_log_<SEG>.csv
    TAZ_THREADS=5 python3 estimation/development/selection/loc_select.py finalize SEG[,SEG..]   -> round 2 (candidates kept in another segment of the family),
                                                                  backward check, final estimates and robustness:
                                                                  <folder>/work/final_<SEG>.pkl, <folder>/final_<SEG>.csv
Families: destinations = the four discretionary purposes x (primary, stop); other_locations = WORK_wbwork (two anchors),
WORK_wbhome, WORK_wahb, EDUCATION_nonstud, EDUCATION_daycare, OTHER_wbs (first stop of an outing, anchor = workplace).

Base specification (decided before estimation, the same in every segment of the family; block numbers of RESPEC_PROTOCOL.md):
  1 constants          none (zones are unlabelled alternatives)
  2 impedance          piecewise-linear car distance (primary form: knots 1, 2, 5, 10, 20 km; two-anchor form: detour, same knots)
                       + car generalised time (form of the anchors as the distance)
  3 size               mu ln(1 + S), S = base component + exp(theta) x each of the other four components (residents, retail,
                       office, other jobs, school enrolment); base component a priori by activity: retail (shopping, recreation,
                       other, outing), school enrolment (accompany, education), office jobs (work business)
  4 zone attributes    land-use mix
  5 boundaries         same zone (primary: home / anchor zone; two-anchor form: zone of a, zone of b), outside the county, outside
                       the state
  6 person x impedance ln(distance) [ln(1+detour)] x income < $50k, x income >= $100k, x no car, x cars < drivers;
                       destinations only: primary x tour with stops; stop x tour mode not car, x inbound
  7 person x attribute none
Candidates (in this order within each block) and expected signs: CANDIDATES.md.
Rule (each candidate added to the current model of the segment): expected sign, robust |t| >= 1.96, BIC lower and hold-out
(validation-half) log-likelihood higher.  Base terms are kept unless their sign is wrong with |t| > 2.
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, time
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/abit"   # results of the selection (data); CODE = this folder
import loc_core as LC   # noqa: E402

DISC = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
DEST = [f"{p}_{k}" for k in ["primary", "stop"] for p in DISC]
OTHER = ["WORK_wbwork", "WORK_wbhome", "WORK_wahb", "EDUCATION_nonstud", "EDUCATION_daycare", "OTHER_wbs"]
SIZE_BASE = {"SHOPPING": "ret", "RECREATION": "ret", "OTHER": "ret", "ACCOMPANY": "stu", "WORK": "off", "EDUCATION": "stu"}
BASE_COMPS = ["pop", "ret", "off", "oth", "stu"]
TCRIT = 1.96


def folder(seg): return f"{HERE}/{'destinations' if seg in DEST else 'other_locations'}"


def form(seg): return "stop" if (seg.endswith("_stop") or seg == "WORK_wbwork") else "primary"


def base_spec(seg):
    st = form(seg) == "stop"; pre = "dt" if st else "d"; ln = "lndt" if st else "lnd"
    pieces = [f"{pre}_0_1", f"{pre}_1_2", f"{pre}_2_5", f"{pre}_5_10", f"{pre}_10_20", f"{pre}_20_inf"]
    lin = pieces + ["cgt"]                                                       # block 2
    lin += ["mix"]                                                               # block 4
    lin += (["intra_a", "intra_b"] if st else ["intra"]) + ["xcounty", "xstate"]  # block 5
    lin += [f"{ln}_{x}" for x in ["inc0", "inc2", "car0", "car1"]]               # block 6
    if seg in DEST: lin += [f"{ln}_multi"] if not st else [f"{ln}_nonauto", f"{ln}_inbound"]
    b = SIZE_BASE[seg.split("_")[0]]
    return LC.Spec(lin, b, [c for c in BASE_COMPS if c != b])


def candidates(seg):
    """[(block, name, kind 'lin'|'size', expected sign '+', '-', '0' (none))] in the pre-declared order"""
    st = form(seg) == "stop"; ln = "lndt" if st else "lnd"
    c = [(2, "ls", "lin", "+")]
    if not st: c.append((2, "d_50_inf", "lin", "+"))
    c += [(3, "leis", "size", "+"), (3, "hlth", "size", "+")]
    c += [(4, "lnretden", "lin", "-"), (4, "cbd", "lin", "-"), (4, "rail", "lin", "+"), (4, "lnstopden", "lin", "+")]
    c += [(5, x, "lin", "0") for x in ["bc", "dcz", "va", "othst"]]
    flags = ["worker", "child", "kid", "senior", "am", "pm", "ev"] + (["worktour"] if (st and seg in DEST) else [])
    c += [(6, f"{ln}_{x}", "lin", "-") for x in flags]
    c += [(7, "ptav_car0", "lin", "+")]
    return c


PRIOR = {"cgt": "-", "ls": "+", "mix": "+", "xcounty": "-", "xstate": "-", "lnd_inc0": "-", "lnd_inc2": "+", "lnd_car0": "-", "lnd_car1": "-",
         "lnd_multi": "+", "lndt_inc0": "-", "lndt_inc2": "+", "lndt_car0": "-", "lndt_car1": "-", "lndt_nonauto": "-", "lndt_inbound": "+"}


def prior(name):
    if name in PRIOR: return PRIOR[name]
    if (name.startswith("d_") or name.startswith("dt_")) and not name.endswith("_0_1"): return "-" if not name.endswith("50_inf") else "+"
    return "0"


def sign_ok(v, s): return s == "0" or (s == "+" and v > 0) or (s == "-" and v < 0)


def aux_cols(seg):
    """columns of the current model of record (for the comparison on the same data)"""
    cur = current(seg)
    return [p for p in cur["spec"].lin] if cur else []


def current(seg):
    """the model of record: specification, size base and full-set estimates"""
    R = f"{LC.TE}/results"
    if seg in DEST:
        E = pd.read_csv(f"{R}/fullset_estimates_taz.csv"); cf = pd.concat([pd.read_csv(f"{R}/dest_choice_primary_cx_fullset_taz.csv"), pd.read_csv(f"{R}/dest_choice_stop_seq_fullset_taz.csv")])
        key = seg if seg.endswith("primary") else seg.replace("_stop", "_seq_stop")
    else:
        E = pd.read_csv(f"{R}/fullset_loc_estimates.csv"); cf = pd.concat([pd.read_csv(f"{R}/dest_choice_loc.csv"), pd.read_csv(f"{R}/dest_choice_wbs.csv")])
        key = seg + ("_stop" if seg == "WORK_wbwork" else "")
    t = E[E.segment == seg]
    if not len(t): return None
    c = cf[(cf.segment == key) & cf.variable.str.startswith("size_") & (cf.value == 1.0)]
    base = c.variable.iloc[0][5:] if len(c) else SIZE_BASE[seg.split("_")[0]]
    lin = [p for p in t.param if not p.startswith("theta_") and p != "mu_size"]; comps = [p[6:] for p in t.param if p.startswith("theta_")]
    return dict(spec=LC.Spec(lin, base, comps), x=t.value.values, table=t)


def all_cols(seg):
    b = base_spec(seg); cols = list(b.lin)
    for _, n, k, _ in candidates(seg):
        if k == "lin" and n not in cols: cols.append(n)
    for n in aux_cols(seg):
        if n not in cols: cols.append(n)
    return cols


def informative(D, name):
    """False when the column is constant over the records (a chooser flag that does not vary in the segment)"""
    if "_" in name and name.split("_")[0] in ("lnd", "lndt"):
        import dc_model as M
        f = M.chooser(D.rec)[name.split("_", 1)[1]]
        return f.min() != f.max()
    return True


def bic(r): return np.log(r["N"]) * r["K"] - 2 * r["LL"]


def tval(r, name):
    i = r["names"].index(name); se = r["se"][i]
    return r["x"][i] / se if (se > 0 and np.isfinite(se)) else np.nan       # theta on the log-weight scale


def warm(r, extra=None):
    x = dict(zip(r["names"], r["x"])); x.update(extra or {}); return x


def test(D, Dv, cur, curho, spec2, name, kind, sgn, seg, block, log, rnd):
    """fit spec2 (= current + candidate), apply the rule, log it; returns (kept, fit, holdout) """
    pn = f"theta_{name}" if kind == "size" else name
    r = LC.fit(D, spec2, x0=warm(cur, {pn: -2.0 if kind == "size" else 0.0}), cov=False, tol=(1e-11, 1e-5))
    i = r["names"].index(pn); v = r["x"][i]
    h = LC.heldout(Dv, spec2, r["x"])
    ok_sign = sign_ok(v, sgn) if kind == "lin" else (pn not in r["at_bound"])
    ok_bic = bic(r) < bic(cur); ok_ho = h["LL_sum"] > curho["LL_sum"]
    t = np.nan
    if ok_sign and ok_bic and ok_ho:
        r = LC.fit(D, spec2, x0=warm(r))  # converge fully before the covariance
        h = LC.heldout(Dv, spec2, r["x"]); t = tval(r, pn)
    kept = bool(ok_sign and ok_bic and ok_ho and np.isfinite(t) and abs(t) >= TCRIT)
    why = "kept" if kept else ("wrong sign" if not ok_sign else "BIC not lower" if not ok_bic else "hold-out LL not higher" if not ok_ho else f"|t| < {TCRIT}")
    log.append(dict(segment=seg, round=rnd, block=block, candidate=name, expected=sgn, estimate=float(v if kind == "lin" else np.exp(v)),
                    rob_t=t, LL_before=cur["LL"], LL_after=r["LL"], LR=2 * (r["LL"] - cur["LL"]), BIC_before=bic(cur), BIC_after=bic(r),
                    holdout_LL_before=curho["LL_sum"], holdout_LL_after=h["LL_sum"], KS_after=h["KS"], decision=why))
    print(f"    [{seg}] B{block} {name}: est {log[-1]['estimate']:+.4f} t {t:.2f} dBIC {bic(r) - bic(cur):+.1f} dHO {h['LL_sum'] - curho['LL_sum']:+.2f} -> {why} ({r['time']:.0f} s)", flush=True)
    return kept, r, h


def swap_base(spec, c):
    """component c becomes the base of the size term; the old base gets a log weight"""
    return LC.Spec(spec.lin, c, [spec.base] + [k for k in spec.comps if k != c])


def swap_start(r, spec_new, c, old):
    v = dict(zip(r["names"], r["x"])); tc = v.get(f"theta_{c}", 0.0)
    x = {k: val for k, val in v.items() if not k.startswith("theta_")}; x[f"theta_{old}"] = max(-29.0, -tc)
    for k in spec_new.comps:
        if k != old: x[f"theta_{k}"] = max(-29.0, min(14.0, v.get(f"theta_{k}", -2.0) - tc))
    return x


HI, LO = 14.9, -10.0     # log weight below -10 (weight < 5e-5 of the base): the component is irrelevant


def test_size(D, Dv, cur, curho, spec, c, seg, log, rnd):
    """size component c: estimate with it added; t on the log-weight scale; a diverging weight (theta at the upper bound) means
    the component dominates the base: re-estimate with c as the base and apply the rule; theta at the lower bound = irrelevant"""
    spec2 = add(spec, c, "size"); pn = f"theta_{c}"
    r = LC.fit(D, spec2, x0=warm(cur, {pn: -2.0}), cov=False, tol=(1e-11, 1e-5)); v = r["x"][r["names"].index(pn)]
    rec = dict(segment=seg, round=rnd, block=3, candidate=c, expected="+", LL_before=cur["LL"], BIC_before=bic(cur), holdout_LL_before=curho["LL_sum"])
    if v <= LO:
        rec.update(estimate=v, LL_after=r["LL"], BIC_after=bic(r), decision="irrelevant: log weight -> -infinity (weight 0)"); log.append(rec)
        print(f"    [{seg}] B3 {c}: weight -> 0, irrelevant", flush=True); return False, None, None, spec
    if v >= HI or v > 10:
        old = spec2.base; spec3 = swap_base(spec2, c); r = LC.fit(D, spec3, x0=swap_start(r, spec3, c, old)); h = LC.heldout(Dv, spec3, r["x"])
        pn2 = f"theta_{old}"; t = tval(r, pn2); v2 = r["x"][r["names"].index(pn2)]
        ok = bic(r) < bic(cur) and h["LL_sum"] > curho["LL_sum"] and np.isfinite(t) and abs(t) >= TCRIT and pn2 not in r["at_bound"]
        why = ("kept as the base component" if ok else "diverged; as the base component: " + ("BIC not lower" if bic(r) >= bic(cur) else "hold-out LL not higher" if h["LL_sum"] <= curho["LL_sum"] else f"|t| < {TCRIT} or at a bound"))
        rec.update(estimate=v, note=f"theta of the former base {spec2.base} = {v2:.3f}", rob_t=t, LL_after=r["LL"], LR=2 * (r["LL"] - cur["LL"]), BIC_after=bic(r), holdout_LL_after=h["LL_sum"], KS_after=h["KS"], decision=why)
        log.append(rec); print(f"    [{seg}] B3 {c}: diverged -> base; t {t:.2f} dBIC {bic(r) - bic(cur):+.1f} dHO {h['LL_sum'] - curho['LL_sum']:+.2f} -> {why}", flush=True)
        return ok, r, h, (spec3 if ok else spec)
    h = LC.heldout(Dv, spec2, r["x"]); ok_b = bic(r) < bic(cur); ok_h = h["LL_sum"] > curho["LL_sum"]; t = np.nan
    if ok_b and ok_h:
        r = LC.fit(D, spec2, x0=warm(r)); h = LC.heldout(Dv, spec2, r["x"]); t = tval(r, pn)
    ok = ok_b and ok_h and np.isfinite(t) and abs(t) >= TCRIT and pn not in r["at_bound"]
    why = "kept" if ok else "BIC not lower" if not ok_b else "hold-out LL not higher" if not ok_h else f"|t| < {TCRIT}"
    rec.update(estimate=v, rob_t=t, LL_after=r["LL"], LR=2 * (r["LL"] - cur["LL"]), BIC_after=bic(r), holdout_LL_after=h["LL_sum"], KS_after=h["KS"], decision=why)
    log.append(rec); print(f"    [{seg}] B3 {c}: theta {v:+.3f} t {t:.2f} -> {why}", flush=True)
    return ok, r, h, (spec2 if ok else spec)


def clean_bounds(D, Dv, spec, cur, log, seg):
    """no final parameter at a bound: theta at the lower bound -> component removed (weight 0); at the upper bound -> base"""
    for _ in range(6):
        v = dict(zip(cur["names"], cur["x"]))
        lo = [p for p in cur["names"] if p.startswith("theta_") and v[p] <= LO + 0.5]; hi = [p for p in cur["names"] if p.startswith("theta_") and v[p] >= HI]
        if hi:
            c = hi[0][6:]; old = spec.base; spec = swap_base(spec, c); cur = LC.fit(D, spec, x0=swap_start(cur, spec, c, old))
            log.append(dict(segment=seg, round=4, candidate=c, decision=f"weight diverged: made the base component (former base {old})"))
        elif lo:
            c = lo[0][6:]; spec = spec.copy(comps=[k for k in spec.comps if k != c]); cur = LC.fit(D, spec, x0=warm(cur))
            log.append(dict(segment=seg, round=4, candidate=c, decision="size component with weight 0 (lower bound): removed"))
        else: break
    return spec, cur, LC.heldout(Dv, spec, cur["x"])


def add(spec, name, kind):
    return spec.copy(comps=spec.comps + [name]) if kind == "size" else spec.copy(lin=spec.lin + [name])


def base_fit(D, Dv, seg, log):
    spec = base_spec(seg); spec = spec.copy(lin=[c for c in spec.lin if informative(D, c)])
    cur = current(seg); x0 = {}
    if cur is not None:
        x0 = {k: v for k, v in zip(cur["spec"].params(), cur["x"]) if k in spec.params()}
    r = LC.fit(D, spec, x0=x0)
    # base terms with the wrong sign and |t| > 2 leave the base (reported)
    while True:
        bad = [(n, tval(r, n)) for n in spec.lin if not sign_ok(r["x"][r["names"].index(n)], prior(n)) and abs(tval(r, n)) > 2]
        if not bad: break
        n, t = max(bad, key=lambda z: abs(z[1]))
        log.append(dict(segment=seg, round=0, block=0, candidate=n, expected=prior(n), estimate=float(r["x"][r["names"].index(n)]), rob_t=t, decision="base term dropped: wrong sign, |t| > 2"))
        print(f"    [{seg}] base term {n} dropped: wrong sign, t {t:.2f}", flush=True)
        spec = spec.copy(lin=[c for c in spec.lin if c != n]); r = LC.fit(D, spec, x0=warm(r))
    # size components at the lower bound (weight 0) leave the size term
    for p in list(r["at_bound"]):
        if p.startswith("theta_"):
            c = p[6:]; spec = spec.copy(comps=[k for k in spec.comps if k != c])
            log.append(dict(segment=seg, round=0, block=3, candidate=c, expected="+", estimate=0.0, decision="base size component at weight 0 (bound): removed"))
    if any(p.startswith("theta_") for p in r["at_bound"]): r = LC.fit(D, spec, x0=warm(r))
    h = LC.heldout(Dv, spec, r["x"])
    log.append(dict(segment=seg, round=0, block=0, candidate="base", LL_after=r["LL"], BIC_after=bic(r), holdout_LL_after=h["LL_sum"], KS_after=h["KS"], decision="base"))
    print(f"  [{seg}] base: LL {r['LL']:.2f} K {r['K']} BIC {bic(r):.1f} hold-out {h['LL_sum']:.2f} KS {h['KS']:.4f}", flush=True)
    return spec, r, h


def select(seg):
    sk = LC.C.skims(); LC.zones_plus(); os.makedirs(f"{folder(seg)}/work", exist_ok=True)
    cols = all_cols(seg); D = LC.SegData(seg, "estimation", cols, sk); Dv = LC.SegData(seg, "validation", cols, sk)
    log = []; spec, cur, curho = base_fit(D, Dv, seg, log)
    base_after = spec
    for block, name, kind, sgn in candidates(seg):
        if kind == "lin" and not informative(D, name):
            log.append(dict(segment=seg, round=1, block=block, candidate=name, expected=sgn, decision="not applicable (constant in the segment)")); continue
        kept, r, h = test(D, Dv, cur, curho, add(spec, name, kind), name, kind, sgn, seg, block, log, 1)
        if kept: spec, cur, curho = add(spec, name, kind), r, h
    pd.DataFrame(log).to_csv(f"{folder(seg)}/selection_log_{seg}.csv", index=False)
    pickle.dump(dict(spec=spec, base=base_after, x=cur["x"], names=cur["names"], LL=cur["LL"], holdout=curho["LL_sum"], log=log), open(f"{folder(seg)}/work/sel_{seg}.pkl", "wb"))
    print(f"[{seg}] selected: LL {cur['LL']:.2f} K {cur['K']} hold-out {curho['LL_sum']:.2f}", flush=True)


def family(seg): return DEST if seg in DEST else OTHER


def finalize(seg, nboot=200):
    sk = LC.C.skims(); LC.zones_plus()
    s = pickle.load(open(f"{folder(seg)}/work/sel_{seg}.pkl", "rb")); spec = s["spec"]; log = list(s["log"])
    cols = all_cols(seg); D = LC.SegData(seg, "estimation", cols, sk); Dv = LC.SegData(seg, "validation", cols, sk)
    cur = LC.fit(D, spec, x0=dict(zip(s["names"], s["x"]))); curho = LC.heldout(Dv, spec, cur["x"])
    # round 2: candidates kept in another segment of the family
    kept_else = set()
    for o in family(seg):
        f = f"{folder(o)}/work/sel_{o}.pkl"
        if o != seg and os.path.exists(f):
            so = pickle.load(open(f, "rb"))["spec"]; bo = pickle.load(open(f, "rb"))["base"]
            kept_else |= set(so.lin) - set(bo.lin); kept_else |= {c for c in so.comps if c in LC.EXTRA_SIZE}
    for c in LC.EXTRA_SIZE:                       # size candidates re-tested in every segment on the log-weight scale
        if c in spec.comps or c == spec.base: continue
        kept, r, h, sp2 = test_size(D, Dv, cur, curho, spec, c, seg, log, 2)
        if kept: spec, cur, curho = sp2, r, h
    for block, name, kind, sgn in candidates(seg):
        if kind == "size" or name not in kept_else or name in spec.lin: continue
        if not informative(D, name): continue
        kept, r, h = test(D, Dv, cur, curho, add(spec, name, kind), name, kind, sgn, seg, block, log, 2)
        if kept: spec, cur, curho = add(spec, name, kind), r, h
    spec, cur, curho = clean_bounds(D, Dv, spec, cur, log, seg)
    # backward check of the non-base terms with |t| < 1.96
    base = base_spec(seg)
    while True:
        weak = [(n, tval(cur, n)) for n in spec.lin if n not in base.lin and abs(tval(cur, n)) < TCRIT]
        weak += [(f"theta_{c}", tval(cur, f"theta_{c}")) for c in spec.comps if c not in base.comps + [base.base] and abs(tval(cur, f"theta_{c}")) < TCRIT]
        if not weak: break
        n, t = min(weak, key=lambda z: abs(z[1]))
        spec = spec.copy(lin=[c for c in spec.lin if c != n], comps=[c for c in spec.comps if f"theta_{c}" != n])
        r = LC.fit(D, spec, x0=warm(cur)); log.append(dict(segment=seg, round=3, candidate=n, rob_t=t, LL_before=cur["LL"], LL_after=r["LL"], decision="removed in the backward check"))
        cur = r; curho = LC.heldout(Dv, spec, cur["x"])
    spec, cur, curho = clean_bounds(D, Dv, spec, cur, log, seg)
    if "se" not in cur: cur.update(LC.covariance(D, spec, cur["x"], cur["at_bound"]))
    out = robustness(seg, spec, cur, curho, D, Dv, nboot)
    out["log"] = log
    pd.DataFrame(log).to_csv(f"{folder(seg)}/selection_log_{seg}.csv", index=False)
    pickle.dump(out, open(f"{folder(seg)}/work/final_{seg}.pkl", "wb"))
    out["table"].to_csv(f"{folder(seg)}/final_{seg}.csv", index=False)
    print(f"[{seg}] final: LL {cur['LL']:.2f} K {cur['K']} hold-out LL/obs {curho['LL_obs']:.4f} KS {curho['KS']:.4f}; current hold-out LL/obs {out['current_holdout']['LL_obs'] if out['current_holdout'] else np.nan}", flush=True)


def robustness(seg, spec, cur, curho, D, Dv, nboot):
    names = cur["names"]; K = len(names)
    tab = pd.DataFrame({"param": names, "value": cur["x"], "rob_se": cur["se"], "rob_t": cur["x"] / cur["se"]})
    # household-cluster s.e.: sandwich and linearised bootstrap
    tab["cluster_se"] = LC.cluster_se(cur, D.hh); tab["boot_se"] = LC.onestep_bootstrap(cur, D.hh, B=nboot)
    # swap halves and pooled
    rv = LC.fit(Dv, spec, x0=warm(cur)); P = LC.Pooled(D, Dv); rp = LC.fit(P, spec, x0=warm(cur), cov=False)
    tab["value_swap"] = rv["x"]; tab["se_swap"] = rv["se"]; tab["z_diff"] = (cur["x"] - rv["x"]) / np.sqrt(cur["se"] ** 2 + rv["se"] ** 2)
    from scipy.stats import chi2
    LR = 2 * (cur["LL"] + rv["LL"] - rp["LL"]); df = K - len(set(cur["at_bound"]) | set(rv["at_bound"]))
    swap = dict(LL_est=cur["LL"], LL_val=rv["LL"], LL_pooled=rp["LL"], LR=LR, df=df, p=float(chi2.sf(LR, df)),
                n_z_gt_196=int((np.abs(tab.z_diff) > 1.96).sum()), swap_holdout_on_est=LC.heldout(D, spec, rv["x"])["LL_obs"])
    # collinearity: correlation of the estimates, Hessian condition number, within-set correlation of the impedance terms
    sd = np.sqrt(np.diag(cur["cov"])); Rc = cur["cov"] / np.outer(sd, sd)
    flags = [(names[i], names[j], float(Rc[i, j])) for i in range(K) for j in range(i + 1, K) if np.isfinite(Rc[i, j]) and abs(Rc[i, j]) > 0.9]
    imp = [c for c in spec.lin if c.startswith(("d_", "dt_")) or c in ("cgt", "ls")]
    Rw, vif = LC.within_corr(D, spec, cur["x"], imp)
    # current model of record on the same data
    cm = current(seg); cho = None; ce = None
    if cm is not None:
        cho = LC.heldout(Dv, cm["spec"], cm["x"]); ce = LC.heldout(D, cm["spec"], cm["x"])
        cho = {k: v for k, v in cho.items() if k != "LL"}; ce = {k: v for k, v in ce.items() if k != "LL"}
    eho = LC.heldout(D, spec, cur["x"])
    nan_se = [n for n, v in zip(names, cur["se"]) if not np.isfinite(v) or v <= 0]
    return dict(seg=seg, spec=spec, names=names, x=cur["x"], cov=cur["cov"], nan_se=nan_se, LL=cur["LL"], LL0=D.ll0(), K=K, N=D.N, cond=cur["cond"], at_bound=cur["at_bound"],
                table=tab, swap=swap, corr_flags=flags, corr=pd.DataFrame(Rc, index=names, columns=names), within_corr=Rw, within_vif=vif,
                holdout={k: v for k, v in curho.items() if k != "LL"}, est_fit={k: v for k, v in eho.items() if k != "LL"},
                current_holdout=cho, current_est=ce, current_spec=cm["spec"] if cm else None, N_val=Dv.N, nboot=nboot)


if __name__ == "__main__":
    cmd, segs = sys.argv[1], sys.argv[2].split(",")
    for sg in segs:
        t0 = time.time()
        select(sg) if cmd == "select" else finalize(sg)
        print(f"== {sg} {cmd} done in {time.time() - t0:.0f} s", flush=True)
