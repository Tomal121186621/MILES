#!/usr/bin/env python3
"""Harmonised primary-destination models of the discretionary tours (SHOPPING, RECREATION, ACCOMPANY, OTHER) with a pooled
market-segmentation test (Ben-Akiva & Lerman 1985, ch. 7: equality of coefficients across segments, segment-specific scale).
Family A.  Records, full choice set (1,588 zones), location mixture, chunked likelihood, variables: ../primary_destination/d_primary.py
(imported, which patches dc_model.features for ln distance x male / one-person household) and
activity/lib/tasha_estimation/estimate_fullset_taz.py.  Estimator: pool_core.py.  Estimation half for every step; the validation
half is used once, at the end (separate common-specification models and the final pooled model).

COMMON SPECIFICATION (union of the terms of the four final models of d_primary.py, one functional form each):
  distance       piecewise-linear car distance from home, knots 1, 2, 5, 10, 20, 50 km (7 pieces; the form of shopping,
                 recreation and other; accompanying had linear + log distance)
  zone anchor    intrazonal (destination = home zone)
  area           Baltimore City, Washington DC, central business district, Virginia, Delaware / Pennsylvania / West Virginia
  land use       ln(1 + retail jobs per km2), land-use mix
  boundaries     outside the home county, outside the home state
  ln distance x  no car, fewer cars than drivers, worker, person under 18, person 65+, household with children, male,
                 one-person household; AM, PM, evening; tour with at least one stop
  impedance      car generalised time (all four chose it; no purpose kept the mode-choice logsum)
  size term      mu_size ln(1 + S_j), S_j = retail jobs + sum_c exp(theta_c) x_jc, c = population, office jobs, other jobs,
                 school enrolment, base = retail jobs for every purpose.  A component whose weight runs to zero for a purpose
                 (theta < ln 1e-4, the rule of d_primary) is fixed out for that purpose only (re-estimated without it).
  All identification guards of d_primary (>= 20 records each way, >= 5 observed destinations) hold for every purpose.

STEP 2  SEPARATE: the common specification per purpose (python3 estimation/development/primary_destination_pooled/dp_pooled.py sep <PURPOSE>; start: the d_primary final
        estimates, theta re-based to retail jobs; missing terms from the mean of the other purposes' final estimates).
STEP 3  POOLED (python3 estimation/development/primary_destination_pooled/dp_pooled.py pool): U = mu_p V_p, mu_shopping = 1.  P0: everything purpose specific (scales not
        identified, fixed at 1): LL must equal the sum of the separate LLs.  Then equality across purposes imposed block by
        block in this FIXED ORDER, each tested against the current pooled model:
          B1  distance pieces (7)                         B2  boundaries: outside the home county, outside the home state
          B3  area dummies (Baltimore City, DC, CBD, Virginia, other states)
          B4  land use (retail density, land-use mix)
          B5  ln distance x household / person (no car, fewer cars than drivers, worker, under 18, 65+, children, male,
              one-person household)
          B6  ln distance x time of day (AM, PM, evening)  B7  ln distance x tour with stops
          B8  impedance: car generalised time             B9  size-term weights theta (over the purposes where free)
          B10 size coefficient mu_size                     B11 zone anchor: intrazonal
        Destination models have no alternative-specific constants, so no purpose-defining constant exists to protect.
        DECISION RULE (every block, every alternative): keep the restriction when BIC falls (BIC_restricted < BIC_current)
        AND every shared estimate of the block has its expected sign (d_primary.SIGN: distance, ln distance, boundaries,
        car generalised time negative, the income / car / age / children / stops interactions as there; plus every distance
        piece below 50 km negative; area, land use, gender, household size, time of day, intrazonal and size terms are not
        sign checked) AND no estimate sits at an optimiser bound.  The LR test of every restriction (restricted vs current,
        df = parameters removed) is reported.  The first block pooled frees the scales (df = parameters removed - 3).
        If block (a) (all four purposes) fails, the pre-stated lettered alternatives are tested against the same current
        model: (b) shopping + other (errand-type tours to retail / service places), (c) shopping + recreation + other
        (all but accompanying, whose destination is the passenger's); among those passing, the lowest BIC is kept.
STEP 4  final pooled model; validation LL per purpose, compared with the current separate final models (d_<p>_fit.csv,
        row final).
STEP 5  REVISION 2026-11-09 (python3 estimation/development/primary_destination_pooled/dp_pooled.py revise; collinearity/abit_notes.md), on the final pooled model of step 3
        (inputs dp_fit / dp_coef / dp_final _pre1109r.*), estimation half, in this order:
          B  size weights with theta < -10 removed (none left: the unidentified components of other, shopping and recreation
             were already fixed out in step 2).
          C  distance > 50 km (collinear with car generalised time in recreation and other): held at 0 (a) for every purpose
             (shared piece) or (b) for recreation and other only (shopping and accompanying share it); the lower BIC is kept if
             it is below the current BIC.  A positive first piece (0-1 km) would be held at 0 by BIC (the shared piece is negative).
          A  WHOLE-SET BAND RULE: no single band is ever dropped (area: Baltimore City, DC, Virginia, DE/PA/WV per purpose;
             cars: no car, fewer cars than drivers; age: under 18, 65+; time of day: AM, PM, evening).  The pooled model never
             dropped one and has no final sign check, so every set is complete and none is up for removal; each set's joint LR
             (every member held at 0) is reported for information.
          D  the effective size coefficient of shopping (scale x mu_size; shared by shopping, recreation and other, 1.25) is
             bounded at 1 (the bound binds: held at 1, K - 1): (a) the shared coefficient held at 1, (b) shopping's own held at 1
             and recreation + other sharing a free one; the lower BIC is adopted only if dBIC <= 2, otherwise mu stays free.
        Then the validation LL of the revised final model (validation half, used once more: disclosed reuse).  Rows R0 (re-
        estimation of the 2026-11-08 final), R1, ... and the new "final" are appended to dp_fit.csv / dp_coef.csv; the
        2026-11-08 final rows are kept as step final_pre1109r.
Outputs: dp_fit.csv, dp_coef.csv, dp.log (+ dp_sep_<P>.log, dp_sep_<P>.pkl per purpose); table: t_pooled.py dp.
    TAZ_THREADS=4 python3 estimation/development/primary_destination_pooled/dp_pooled.py sep SHOPPING      (x4, in parallel)
    TAZ_THREADS=16 python3 estimation/development/primary_destination_pooled/dp_pooled.py pool
    POOL_THREADS=3 python3 estimation/development/primary_destination_pooled/dp_pooled.py revise           (4 workers x 3 threads)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "4")
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/dest_pooled"; SBS = os.path.dirname(HERE)
sys.path.insert(0, CODE); sys.path.insert(0, f"{os.path.dirname(CODE)}/primary_destination")
import d_primary as D                   # noqa: E402  (patches dc_model.features; estimator modules)
import pool_core as PC                  # noqa: E402
FS, X, M, C = D.FS, D.X, D.M, D.C

PURP = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
SHORT = {"SHOPPING": "shop", "RECREATION": "rec", "ACCOMPANY": "acc", "OTHER": "oth"}
PIECES = C.pw_names("d", C.KNOTS)
LIN = PIECES + ["intra", "bc", "dcz", "cbd", "va", "othst", "lnretden", "mix", "xcounty", "xstate",
                "lnd_car0", "lnd_car1", "lnd_worker", "lnd_kid", "lnd_senior", "lnd_child", "lnd_male", "lnd_hh1",
                "lnd_am", "lnd_pm", "lnd_ev", "lnd_multi", "cgt"]
BASE, COMPS = "ret", ["pop", "off", "oth", "stu"]
BLOCKS = [("B1", "Distance pieces", PIECES),
          ("B2", "Boundaries: outside the home county and state", ["xcounty", "xstate"]),
          ("B3", "Area dummies", ["bc", "dcz", "cbd", "va", "othst"]),
          ("B4", "Land use", ["lnretden", "mix"]),
          ("B5", "Log distance x household and person", ["lnd_car0", "lnd_car1", "lnd_worker", "lnd_kid", "lnd_senior", "lnd_child", "lnd_male", "lnd_hh1"]),
          ("B6", "Log distance x time of day", ["lnd_am", "lnd_pm", "lnd_ev"]),
          ("B7", "Log distance x tour with stops", ["lnd_multi"]),
          ("B8", "Car generalised time", ["cgt"]),
          ("B9", "Size-term weights", [f"theta_{c}" for c in COMPS]),
          ("B10", "Size coefficient", ["mu_size"]),
          ("B11", "Intrazonal", ["intra"])]
SUBSETS = [("b", "shopping + other", ("SHOPPING", "OTHER")), ("c", "shopping + recreation + other", ("SHOPPING", "RECREATION", "OTHER"))]
DP = f"{SBS}/dest_primary"
_LOGF = None


def log(s):
    print(s, flush=True)
    if _LOGF: _LOGF.write(s + "\n"); _LOGF.flush()


def sign_of(q):
    if q in PIECES: return None if q == "d_50_inf" else -1
    return D.sign_of(q)


def SEG(p):
    return f"{p}_primary"


def build(p, spec, half="estimation", sk=None):
    rec, cand, cfg = FS.load(f"{p}_primary", half)
    ch = [FS.Chunk(rec.iloc[i:i + FS.CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + FS.CHUNK])], cfg, spec, p, sk)
          for i in range(0, len(rec), FS.CHUNK)]
    return ch, len(rec)


def old_final(p):
    c = pd.read_csv(f"{DP}/d_{SHORT[p]}_coef.csv"); c = c[c.step == "final"].set_index("param").coef.to_dict()
    lg = open(f"{DP}/d_{SHORT[p]}.log").read(); base = lg.split("final specification:")[1].split("size base ")[1].split(",")[0]
    th = {k[6:]: v for k, v in c.items() if k.startswith("theta_")}; th[base] = 0.0
    if BASE in th: c.update({f"theta_{k}": v - th[BASE] for k, v in th.items() if k != BASE})
    return {k: v for k, v in c.items() if not (k.startswith("theta_") and BASE not in th)}


def current_rows():
    out = {}
    for p in PURP:
        f = pd.read_csv(f"{DP}/d_{SHORT[p]}_fit.csv"); out[p] = f[f.step == "final"].iloc[0]
    return out


# ------------------------------------------------------------------------------------------------ step 2: separate
def separate(p):
    global _LOGF
    _LOGF = open(f"{HERE}/dp_sep_{p}.log", "w"); sk = C.skims(); t0 = time.time()
    starts = {q: old_final(q) for q in PURP}
    x0 = {}
    for q in LIN + [f"theta_{c}" for c in COMPS] + ["mu_size"]:
        if q in starts[p]: x0[q] = starts[p][q]
        else:
            v = [starts[o][q] for o in PURP if o != p and q in starts[o]]
            x0[q] = float(np.mean(v)) if v else (-5.0 if q.startswith("theta_") else 0.0)
    comps, fixed = list(COMPS), []
    log(f"{p}: common specification, estimation half; start values {x0}")
    while True:
        spec = M.Spec("sep", LIN, BASE, comps); ch, N = build(p, spec, sk=sk)
        eng = PC.Engine([p], {p: spec}, {p: ch}, {p: N}, log); S = PC.Structure([p], {p: spec})
        r = eng.fit(S, {f"{p}|{q}": x0[q] for q in spec.params()}, f"sep_{p}", "separate, common specification")
        x = {k.split("|")[1]: v for k, v in r["x"].items()}
        zero = [c for c in comps if x[f"theta_{c}"] < np.log(1e-4)]
        if not zero: break
        log(f"  size weight runs to zero (theta < ln 1e-4): {zero} -> fixed out for {p}"); fixed += zero
        comps = [c for c in comps if c not in zero]; x0 = {k: v for k, v in x.items()}; del ch, eng
    bad = [q for q in LIN if sign_of(q) is not None and np.sign(x[q]) != sign_of(q)]
    rv, cv, gv = FS.load(f"{p}_primary", "validation")
    v = float(X.heldout(rv, cv, gv, spec, np.array([x[q] for q in spec.params()]), p, sk, obs="mix")["LL"].sum())
    log(f"{p}: K {r['K']} LL {r['LL']:.2f} BIC {r['BIC']:.1f} N {N}; wrong sign: {bad}; size components fixed out: {fixed}; "
        f"validation LL {v:.2f} (N {len(rv)}); {time.time() - t0:.0f} s")
    keep = {k: r[k] for k in ["K", "LL", "BIC", "N", "x", "converged", "maxgrad", "at_bound"]}
    keep.update(table=r["table"], comps=comps, fixed=fixed, bad=bad, vLL=v, Nv=len(rv))
    pickle.dump(keep, open(f"{HERE}/dp_sep_{p}.pkl", "wb"))


# ------------------------------------------------------------------------------------------------ step 3-4: pooled
def x_start(S_new, cur):
    """start values of a restricted model: unchanged keys copied; a new shared key = mean of the members' current values"""
    x = {}
    for n in S_new.names():
        if n in cur["x"]: x[n] = cur["x"][n]; continue
        if n.startswith("scale|"): x[n] = 1.0; continue
        grp, q = n.split("|"); vals = []
        for p in S_new.P:
            if S_new.has(p, q) and S_new.key(p, q) == n: vals.append(cur["x"][cur["S"].key(p, q)])
        x[n] = float(np.mean(vals))
    return x


def pool():
    global _LOGF
    _LOGF = open(f"{HERE}/dp.log", "w"); sk = C.skims(); t0 = time.time()
    sep = {p: pickle.load(open(f"{HERE}/dp_sep_{p}.pkl", "rb")) for p in PURP}
    specs = {p: M.Spec("pool", LIN, BASE, sep[p]["comps"]) for p in PURP}
    rows, coefs = [], []
    cur_old = current_rows()
    for p in PURP:
        s = sep[p]; rows.append(dict(step=f"sep_{p}", label=f"separate, common specification, {p.lower()} (N {s['N']})", K=s["K"], LL=s["LL"],
                                     BIC=s["BIC"], decision="separate" + (f"; wrong sign: {' '.join(s['bad'])}" if s["bad"] else "; no wrong sign")
                                     + (f"; size fixed out: {' '.join(s['fixed'])}" if s["fixed"] else ""), validation_LL=s["vLL"]))
        for q in s["table"].itertuples(): coefs.append(dict(step=f"sep_{p}", purpose=p, param=q.param.split("|")[1], coef=q.value, se=q.rob_se, t=q.rob_t))
    for p in PURP:
        o = cur_old[p]; rows.append(dict(step=f"current_{p}", label=f"current separate final model, {p.lower()} (d_primary)", K=o.K, LL=o.LL,
                                         BIC=o.BIC, decision="reference", validation_LL=o.validation_LL))
    log("starting one worker per purpose (estimation half, chunks built once)")
    eng = PC.ParEngine("dp_pooled", PURP, specs, threads=int(os.environ.get("POOL_THREADS", "4")), log=log); nrec = eng.nrec
    S0 = PC.Structure(PURP, specs)
    x0 = {f"{p}|{q}": sep[p]["x"][f"{p}|{q}"] for p in PURP for q in specs[p].params()}
    cur = eng.fit(S0, x0, "P0", "Pooled, everything purpose specific")
    ssum = sum(sep[p]["LL"] for p in PURP)
    log(f"  P0 check: LL {cur['LL']:.3f} vs sum of separate LLs {ssum:.3f} (difference {cur['LL'] - ssum:.4f}); "
        f"per purpose {{ {', '.join(f'{p}: {cur['LLp'][p] - sep[p]['LL']:.4f}' for p in PURP)} }}")
    d = PC.lr_row(cur, None, "start: LL = sum of separate LLs" if abs(cur["LL"] - ssum) < 0.05 else f"start (sum of separate {ssum:.2f})")
    rows.append(d); coefs += PC.coef_rows(cur, "P0")
    for code, lab, terms in BLOCKS:
        def attempt(sc, group, lab2):
            add = {q: group for q in terms if sum(S0.has(p, q) for p in group) >= 2}
            if not add: return None
            Sn = cur["S"].copy(add)
            r = eng.fit(Sn, x_start(Sn, cur), sc, lab2)
            if r is None: return None
            shared = [n for n in Sn.names() if not n.split("|")[0] in PURP + ["scale"] and n not in cur["x"]]
            bad = [n for n in shared if sign_of(n.split("|")[1]) is not None and np.sign(r["x"][n]) != sign_of(n.split("|")[1])]
            dec = ("not kept: estimate at bound" if r["at_bound"] else "not kept: BIC" if r["BIC"] >= cur["BIC"] else
                   "not kept: sign" if bad else "pass")
            if bad: log(f"    wrong sign: {bad}")
            return r, dec
        res = []; a = attempt(f"{code}a", tuple(PURP), f"{lab}: all four purposes")
        if a: res.append(a)
        if not a or a[1] != "pass":
            for letter, word, grp in SUBSETS:
                b = attempt(f"{code}{letter}", grp, f"{lab}: {word}")
                if b: res.append(b)
        passing = [r for r, dd in res if dd == "pass"]; best = min(passing, key=lambda r: r["BIC"]) if passing else None
        for r, dd in res:
            if dd == "pass": dd = "kept" if r is best else "not chosen: BIC"
            rows.append(PC.lr_row(r, cur, dd)); coefs += PC.coef_rows(r, r["step"])
            log(f"    {r['step']}: {dd} (LR {rows[-1]['LR']:.2f}, df {rows[-1]['df']}, p {rows[-1]['p']:.3g})")
        if best is not None: cur = best
    # ---- final pooled model; validation half used once
    log(f"final pooled model: K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f}; shared: {cur['S'].describe()}; free scales {cur['S'].free_scales()}")
    fin = PC.lr_row(cur, None, "final"); fin.update(step="final", label="final pooled model")
    V = {}; VV = eng.validation(cur["S"], cur["x"]); eng.close()
    for p in PURP:
        V[p], nv = VV[p]
        fin[f"validation_LL_{p}"] = V[p]; fin[f"N_{p}"] = nrec[p]; fin[f"Nv_{p}"] = nv
        log(f"  validation LL {p}: pooled {V[p]:.2f}, separate common spec {sep[p]['vLL']:.2f}, current separate final {cur_old[p].validation_LL:.2f} (N {nv})")
    fin["validation_LL"] = sum(V.values()); rows.append(fin); coefs += PC.coef_rows(cur, "final")
    log(f"  validation LL total: pooled {sum(V.values()):.2f}, current separate finals {sum(cur_old[p].validation_LL for p in PURP):.2f}; "
        f"K pooled {cur['K']} vs sum of current K {int(sum(cur_old[p].K for p in PURP))}; {time.time() - t0:.0f} s")
    cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"]
    F = pd.DataFrame(rows); extra = [c for c in F.columns if c not in cols]
    F.reindex(columns=cols + extra).to_csv(f"{HERE}/dp_fit.csv", index=False)
    pd.DataFrame(coefs).to_csv(f"{HERE}/dp_coef.csv", index=False)
    pickle.dump(dict(S=cur["S"].share, specs={p: (specs[p].linear, specs[p].size_base, specs[p].size_comps) for p in PURP},
                     x=cur["x"], cov=cur["cov"]), open(f"{HERE}/dp_final.pkl", "wb"))


# ------------------------------------------------------------------------------------------------ step 5: revision 2026-11-09
BANDS_P = [("area", ["bc", "dcz", "va", "othst"]), ("cars", ["lnd_car0", "lnd_car1"]), ("age", ["lnd_kid", "lnd_senior"]),
           ("time of day", ["lnd_am", "lnd_pm", "lnd_ev"])]


def revise():
    """final stage of 2026-11-09 on the final pooled model of step 3 (dp_*_pre1109r.*): B, C, A, D (see the docstring)"""
    global _LOGF
    _LOGF = open(f"{HERE}/dp.log", "w"); _LOGF.write(open(f"{HERE}/dp_pre1109r.log").read()); t0 = time.time()
    f0 = pd.read_csv(f"{HERE}/dp_fit_pre1109r.csv"); c0 = pd.read_csv(f"{HERE}/dp_coef_pre1109r.csv")
    old = f0[f0.step == "final"].iloc[0]
    f0.loc[f0.step == "final", ["step", "label"]] = ["final_pre1109r", "final pooled model of 2026-11-08 (before the revision)"]
    c0.loc[c0.step == "final", "step"] = "final_pre1109r"
    fin0 = pickle.load(open(f"{HERE}/dp_final_pre1109r.pkl", "rb"))
    specs = {p: M.Spec("pool", *fin0["specs"][p]) for p in PURP}
    log("REVISION 2026-11-09 (rules B, C, A, D) of the final pooled model; estimation half; validation half once, at the end")
    eng = PC.ParEngine("dp_pooled", PURP, specs, threads=int(os.environ.get("POOL_THREADS", "3")), log=log)
    cur = eng.fit(PC.Structure(PURP, specs, fin0["S"]), fin0["x"], "R0", "Re-estimation of the final pooled model of 2026-11-08")
    rows = [PC.lr_row(cur, None, f"start of the revision (final of 2026-11-08: LL {old.LL:.2f})")]; coefs = PC.coef_rows(cur, "R0")
    n = [0]

    def fit(S, lab):
        n[0] += 1; r = eng.fit(S, x_start(S, cur), f"R{n[0]}", lab); return r

    def add(r, dec):
        rows.append(PC.lr_row(r, cur, dec)); coefs.extend(PC.coef_rows(r, r["step"])); d = rows[-1]
        log(f"    {r['step']}: {dec} (LR {d['LR']:.2f}, df {d['df']}, p {d['p']:.3g}, dBIC {r['BIC'] - cur['BIC']:+.1f})")
    # B  size components with theta < -10
    th = {k: v for k, v in cur["x"].items() if "|theta_" in k and v < -10}
    log(f"  B size weights with theta < -10: {th or 'none'} (population and school enrolment of other, other jobs and school enrolment of "
        f"shopping and other jobs of recreation were fixed out in step 2: theta < ln 1e-4)")
    # C  distance: > 50 km piece (collinear with car generalised time); first piece if positive
    k50 = {p: cur["S"].key(p, "d_50_inf") for p in PURP}; k01 = cur["S"].key("SHOPPING", "d_0_1")
    log(f"  C d_50_inf: {', '.join(f'{p} {k50[p]} {cur['x'][k50[p]]:+.4f}' for p in PURP)}; first piece {k01} {cur['x'][k01]:+.4f}"
        f"{' (positive: tested)' if cur['x'][k01] > 0 else ' (negative: no test)'}")
    sh = {q: list(gs) for q, gs in cur["S"].share.items()}; sh["d_50_inf"] = [("SHOPPING", "ACCOMPANY")]
    alts = [(cur["S"].copy(fix={k50[p]: 0.0 for p in PURP}), "Distance > 50 km fixed at 0 for every purpose (shared piece)"),
            (PC.Structure(PURP, specs, sh, {**cur["S"].fixed, "RECREATION|d_50_inf": 0.0, "OTHER|d_50_inf": 0.0}),
             "Distance > 50 km fixed at 0 for recreation and other (shared by shopping and accompanying)")]
    res = [r for r in (fit(S, lab) for S, lab in alts) if r is not None]
    best = min(res, key=lambda r: r["BIC"])
    for r in res: add(r, ("chosen: BIC falls" if r is best else "not chosen: BIC") if best["BIC"] < cur["BIC"] else "not kept: BIC")
    if best["BIC"] < cur["BIC"]: cur = best
    # A  band sets: no single band is ever dropped; the pooled model has no final sign check and every set is complete, so no set
    #    is up for removal; each set's joint LR (whole set held at 0) is reported for information (a set would be dropped whole only
    #    if a member were flagged or the set were present in part, and then only if p >= 0.05)
    for nm, mem in BANDS_P:
        units = []
        for p in PURP:
            u = tuple(sorted({cur["S"].key(p, q) for q in mem if cur["S"].has(p, q)} - set(k for k, v in cur["S"].fixed.items() if v == 0.0)))
            if u and u not in [x[0] for x in units]: units.append((u, p))
        for u, p in units:
            who = "shared" if all(k.split("|")[0] not in PURP for k in u) else p.lower()
            r = fit(cur["S"].copy(fix={k: 0.0 for k in u}), f"Band set {nm} ({who}): without the whole set")
            if r is None: continue
            pv = float(PC.chi2.sf(max(2 * (cur["LL"] - r["LL"]), 0), cur["K"] - r["K"]))
            add(r, f"information only: complete set, kept (joint LR p {pv:.3g})")
    # D  size coefficient above 1 (effective mu_p x mu_size, the coefficient of ln S in the purpose's own logit): bounded at 1
    #    (the bound binds: mu = 1, K - 1).  (a) the shared coefficient held at 1; (b) shopping's own coefficient held at 1 (shopping
    #    is the scale reference), recreation + other keep a shared free one.  The lower BIC is adopted if dBIC <= 2.
    sc = lambda p: cur["x"].get(f"scale|{p}", 1.0)
    eff = {p: sc(p) * cur["x"][cur["S"].key(p, "mu_size")] for p in PURP}
    log(f"  D effective size coefficients (scale x mu_size): { {p: round(v, 3) for p, v in eff.items()} }")
    km = cur["S"].key("SHOPPING", "mu_size")
    if eff["SHOPPING"] > 1 and km.split("|")[0] not in PURP:
        sh = {q: list(gs) for q, gs in cur["S"].share.items()}; grp = cur["S"].group_of("SHOPPING", "mu_size")
        sh["mu_size"] = [g for g in sh["mu_size"] if g != grp] + ([tuple(p for p in grp if p != "SHOPPING")] if len(grp) > 2 else [])
        alts = [(cur["S"].copy(fix={km: 1.0}), f"Size coefficient {km} held at 1 (bound)"),
                (PC.Structure(PURP, specs, sh, {**cur["S"].fixed, "SHOPPING|mu_size": 1.0}),
                 "Size coefficient of shopping held at 1 (bound), the others' shared coefficient free")]
        res = [r for r in (fit(S, lab) for S, lab in alts) if r is not None]; best = min(res, key=lambda r: r["BIC"])
        ok = best["BIC"] - cur["BIC"] <= 2
        for r in res:
            db = r["BIC"] - cur["BIC"]
            add(r, f"mu <= 1 {'adopted' if (ok and r is best) else 'not adopted'}: dLL {r['LL'] - cur['LL']:.2f}, dBIC {db:+.1f} (adopt if dBIC <= 2)")
        if ok: cur = best
    # final revised model; validation half used once
    log(f"final pooled model (revised): K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f}; shared: {cur['S'].describe()}; "
        f"held fixed: {cur['S'].fixed}; free scales {cur['S'].free_scales()}")
    fin = PC.lr_row(cur, None, "final"); fin.update(step="final", label="final pooled model (revised 2026-11-09)")
    VV = eng.validation(cur["S"], cur["x"]); eng.close()
    for p in PURP:
        v, nv = VV[p]; fin[f"validation_LL_{p}"] = v; fin[f"N_{p}"] = eng.nrec[p]; fin[f"Nv_{p}"] = nv
        log(f"  validation LL {p}: revised {v:.2f}, final of 2026-11-08 {old[f'validation_LL_{p}']:.2f} (N {nv})")
    fin["validation_LL"] = sum(VV[p][0] for p in PURP); rows.append(fin); coefs += PC.coef_rows(cur, "final")
    log(f"  validation LL total: revised {fin['validation_LL']:.2f}, final of 2026-11-08 {old.validation_LL:.2f}; K {cur['K']} vs {int(old.K)}; "
        f"{time.time() - t0:.0f} s")
    F = pd.concat([f0, pd.DataFrame(rows)], ignore_index=True); cols = list(f0.columns)
    F.reindex(columns=cols + [c for c in F.columns if c not in cols]).to_csv(f"{HERE}/dp_fit.csv", index=False)
    pd.concat([c0, pd.DataFrame(coefs)], ignore_index=True).to_csv(f"{HERE}/dp_coef.csv", index=False)
    pickle.dump(dict(S=cur["S"].share, fixed=cur["S"].fixed, specs={p: (specs[p].linear, specs[p].size_base, specs[p].size_comps) for p in PURP},
                     x=cur["x"], cov=cur["cov"]), open(f"{HERE}/dp_final.pkl", "wb"))


if __name__ == "__main__":
    if sys.argv[1] == "sep": separate(sys.argv[2])
    elif sys.argv[1] == "pool": pool()
    elif sys.argv[1] == "revise": revise()
