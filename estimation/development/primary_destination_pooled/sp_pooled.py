#!/usr/bin/env python3
"""Harmonised stop-location models of the discretionary stops (SHOPPING, RECREATION, ACCOMPANY, OTHER) with a pooled
market-segmentation test (Ben-Akiva & Lerman 1985, ch. 7: equality of coefficients across segments, segment-specific scale).
Family B.  Records, full choice set (1,588 zones), location mixture over the zones of the stop and of the anchors, chunked
likelihood and variables: ../stop_location/s_stops_newls.py (imported: the NEW mode-choice logsum of
../accessibility/mode_logsum_new.py for "ls", detour form LS(a,j) + LS(j,b) - LS(a,b); s_stops.py patches the chooser for
male / household size) and activity/lib/tasha_estimation/estimate_fullset_taz.py.  Estimator: pool_core.py.  Estimation half for
every step; the validation half is used once, at the end (separate common-specification models and the final pooled model).

COMMON SPECIFICATION (union of the terms of the four final models of s_stops_newls.py, one functional form each):
  detour         piecewise-linear car detour d(a,j) + d(j,b) - d(a,b), knots 1, 2, 5, 10, 20 km (6 pieces; all four)
  zone anchor    stop in the zone of the previous location, stop in the zone of the next anchor
  area           Baltimore City, Washington DC, central business district, Virginia, Delaware / Pennsylvania / West Virginia
  land use       ln(1 + retail jobs per km2), land-use mix
  boundaries     outside the counties of both anchors, outside the states of both anchors
  ln(1+detour) x no car, fewer cars than drivers, household size; tour mode not car, inbound stop
  impedance      car generalised detour time AND mode-choice logsum of the detour (shopping and other kept both)
  size term      mu_size ln(1 + S_j), S_j = retail jobs + sum_c exp(theta_c) x_jc, c = population, office jobs, other jobs,
                 school enrolment, base = retail jobs for every purpose.  A component whose weight runs to zero for a purpose
                 (theta < ln 1e-4, the rule of s_stops) is fixed out for that purpose only (re-estimated without it).
  All identification guards of s_stops (>= 20 records each way, >= 5 observed destinations) hold for every purpose.

STEP 2  SEPARATE: the common specification per purpose (python3 estimation/development/primary_destination_pooled/sp_pooled.py sep <PURPOSE>; start: the s_stops_newls final
        estimates, theta re-based to retail jobs; missing terms from the mean of the other purposes' final estimates).
STEP 3  POOLED (python3 estimation/development/primary_destination_pooled/sp_pooled.py pool): U = mu_p V_p, mu_shopping = 1.  P0: everything purpose specific (scales not
        identified, fixed at 1): LL must equal the sum of the separate LLs.  Then equality across purposes imposed block by
        block in this FIXED ORDER, each tested against the current pooled model:
          B1  detour pieces (6)                            B2  boundaries: outside the counties / states of both anchors
          B3  area dummies (Baltimore City, DC, CBD, Virginia, other states)
          B4  land use (retail density, land-use mix)
          B5  ln(1 + detour) x household / person (no car, fewer cars than drivers, household size)
          B6  ln(1 + detour) x tour (tour mode not car, inbound stop)   (no time-of-day term is in the common specification)
          B7  impedance: car generalised detour time        B8  impedance: mode-choice logsum of the detour
          B9  size-term weights theta (over the purposes where free)       B10 size coefficient mu_size
          B11 zone anchors: zone of the previous location, zone of the next anchor
        Destination models have no alternative-specific constants, so no purpose-defining constant exists to protect.
        DECISION RULE (every block, every alternative): keep the restriction when BIC falls (BIC_restricted < BIC_current)
        AND every shared estimate of the block has its expected sign (s_stops.SIGN: detour, boundaries, car generalised time
        negative, logsum positive, the income / car / age / tour-mode interactions as there; as in s_stops the detour
        pieces, area, land use, household size, inbound, anchor zones and size terms are not sign checked) AND no
        estimate sits at an optimiser bound.  The LR test of every restriction (restricted vs current, df = parameters
        removed) is reported.  The first block pooled frees the scales (df = parameters removed - 3).
        If block (a) (all four purposes) fails, the pre-stated lettered alternatives are tested against the same current
        model: (b) shopping + other (errand-type stops at retail / service places), (c) shopping + recreation + other
        (all but accompanying, whose stop location is the passenger's); among those passing, the lowest BIC is kept.
STEP 4  final pooled model; validation LL per purpose, compared with the current separate final models (s_<p>_fit.csv,
        row final).
Outputs: sp_fit.csv, sp_coef.csv, sp.log (+ sp_sep_<P>.log, sp_sep_<P>.pkl per purpose); table: t_pooled.py sp.
    TAZ_THREADS=4 python3 estimation/development/primary_destination_pooled/sp_pooled.py sep SHOPPING      (x4, in parallel)
    TAZ_THREADS=16 python3 estimation/development/primary_destination_pooled/sp_pooled.py pool
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "4")
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/dest_pooled"; SBS = os.path.dirname(HERE)
sys.path.insert(0, CODE); sys.path.insert(0, f"{os.path.dirname(CODE)}/stop_location")
import s_stops_newls as SN              # noqa: E402  (new mode-choice logsum; imports s_stops, which patches the chooser)
import pool_core as PC                  # noqa: E402
D = SN.S
FS, X, M, C = D.F_, D.X, D.M, D.C

PURP = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
SHORT = {"SHOPPING": "shop", "RECREATION": "rec", "ACCOMPANY": "acc", "OTHER": "oth"}
PIECES = C.pw_names("dt", C.DKNOTS)
LIN = PIECES + ["intra_a", "intra_b", "bc", "dcz", "cbd", "va", "othst", "lnretden", "mix", "xcounty", "xstate",
                "lndt_car0", "lndt_car1", "lndt_hhsize", "lndt_nonauto", "lndt_inbound", "cgt", "ls"]
BASE, COMPS = "ret", ["pop", "off", "oth", "stu"]
BLOCKS = [("B1", "Detour pieces", PIECES),
          ("B2", "Boundaries: outside the counties and states of both anchors", ["xcounty", "xstate"]),
          ("B3", "Area dummies", ["bc", "dcz", "cbd", "va", "othst"]),
          ("B4", "Land use", ["lnretden", "mix"]),
          ("B5", "Log detour x household and person", ["lndt_car0", "lndt_car1", "lndt_hhsize"]),
          ("B6", "Log detour x tour", ["lndt_nonauto", "lndt_inbound"]),
          ("B7", "Car generalised detour time", ["cgt"]),
          ("B8", "Mode-choice logsum", ["ls"]),
          ("B9", "Size-term weights", [f"theta_{c}" for c in COMPS]),
          ("B10", "Size coefficient", ["mu_size"]),
          ("B11", "Anchor zones", ["intra_a", "intra_b"])]
SUBSETS = [("b", "shopping + other", ("SHOPPING", "OTHER")), ("c", "shopping + recreation + other", ("SHOPPING", "RECREATION", "OTHER"))]
DP = f"{SBS}/dest_stop"
_LOGF = None


def log(s):
    print(s, flush=True)
    if _LOGF: _LOGF.write(s + "\n"); _LOGF.flush()


def sign_of(q):
    if q in PIECES: return None                      # s_stops: detour pieces not sign checked
    return D.sign_of(q)


def SEG(p):
    return f"{p}_stop"


def build(p, spec, half="estimation", sk=None):
    rec, cand, cfg = FS.load(f"{p}_stop", half)
    ch = [FS.Chunk(rec.iloc[i:i + FS.CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + FS.CHUNK])], cfg, spec, p, sk)
          for i in range(0, len(rec), FS.CHUNK)]
    return ch, len(rec)


def old_final(p):
    c = pd.read_csv(f"{DP}/s_{SHORT[p]}_coef.csv"); c = c[c.step == "final"].set_index("param").coef.to_dict()
    lg = open(f"{DP}/s_{SHORT[p]}.log").read(); base = lg.split("final specification:")[1].split("size base ")[1].split(",")[0]
    th = {k[6:]: v for k, v in c.items() if k.startswith("theta_")}; th[base] = 0.0
    if BASE in th: c.update({f"theta_{k}": v - th[BASE] for k, v in th.items() if k != BASE})
    return {k: v for k, v in c.items() if not (k.startswith("theta_") and BASE not in th)}


def current_rows():
    out = {}
    for p in PURP:
        f = pd.read_csv(f"{DP}/s_{SHORT[p]}_fit.csv"); out[p] = f[f.step == "final"].iloc[0]
    return out


# ------------------------------------------------------------------------------------------------ step 2: separate
def separate(p):
    global _LOGF
    _LOGF = open(f"{HERE}/sp_sep_{p}.log", "w"); sk = C.skims(); t0 = time.time()
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
    rv, cv, gv = FS.load(f"{p}_stop", "validation")
    v = float(X.heldout(rv, cv, gv, spec, np.array([x[q] for q in spec.params()]), p, sk, obs="mix")["LL"].sum())
    log(f"{p}: K {r['K']} LL {r['LL']:.2f} BIC {r['BIC']:.1f} N {N}; wrong sign: {bad}; size components fixed out: {fixed}; "
        f"validation LL {v:.2f} (N {len(rv)}); {time.time() - t0:.0f} s")
    keep = {k: r[k] for k in ["K", "LL", "BIC", "N", "x", "converged", "maxgrad", "at_bound"]}
    keep.update(table=r["table"], comps=comps, fixed=fixed, bad=bad, vLL=v, Nv=len(rv))
    pickle.dump(keep, open(f"{HERE}/sp_sep_{p}.pkl", "wb"))


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
    _LOGF = open(f"{HERE}/sp.log", "w"); sk = C.skims(); t0 = time.time()
    sep = {p: pickle.load(open(f"{HERE}/sp_sep_{p}.pkl", "rb")) for p in PURP}
    specs = {p: M.Spec("pool", LIN, BASE, sep[p]["comps"]) for p in PURP}
    rows, coefs = [], []
    cur_old = current_rows()
    for p in PURP:
        s = sep[p]; s["bad"] = [q for q in LIN if sign_of(q) is not None and np.sign(s["x"][f"{p}|{q}"]) != sign_of(q)]
        rows.append(dict(step=f"sep_{p}", label=f"separate, common specification, {p.lower()} (N {s['N']})", K=s["K"], LL=s["LL"],
                                     BIC=s["BIC"], decision="separate" + (f"; wrong sign: {' '.join(s['bad'])}" if s["bad"] else "; no wrong sign")
                                     + (f"; size fixed out: {' '.join(s['fixed'])}" if s["fixed"] else ""), validation_LL=s["vLL"]))
        for q in s["table"].itertuples(): coefs.append(dict(step=f"sep_{p}", purpose=p, param=q.param.split("|")[1], coef=q.value, se=q.rob_se, t=q.rob_t))
    for p in PURP:
        o = cur_old[p]; rows.append(dict(step=f"current_{p}", label=f"current separate final model, {p.lower()} (s_stops_newls)", K=o.K, LL=o.LL,
                                         BIC=o.BIC, decision="reference", validation_LL=o.validation_LL))
    log("starting one worker per purpose (estimation half, chunks built once)")
    eng = PC.ParEngine("sp_pooled", PURP, specs, threads=int(os.environ.get("POOL_THREADS", "4")), log=log,
                       split={"OTHER": 2, "RECREATION": 2}); nrec = eng.nrec
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
    F.reindex(columns=cols + extra).to_csv(f"{HERE}/sp_fit.csv", index=False)
    pd.DataFrame(coefs).to_csv(f"{HERE}/sp_coef.csv", index=False)
    pickle.dump(dict(S=cur["S"].share, specs={p: (specs[p].linear, specs[p].size_base, specs[p].size_comps) for p in PURP},
                     x=cur["x"], cov=cur["cov"]), open(f"{HERE}/sp_final.pkl", "wb"))


if __name__ == "__main__":
    if sys.argv[1] == "sep": separate(sys.argv[2])
    elif sys.argv[1] == "pool": pool()
