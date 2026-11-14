#!/usr/bin/env python3
"""Pooled models of the small location samples (2026-11-09, collaborator's request: daycare N 279, work at home base N 427 are
small): market-segmentation pooling of ../primary_destination_pooled/dp_pooled.py (Ben-Akiva & Lerman 1985, ch. 7; purpose-specific scale,
equality of coefficients imposed block by block) for two pairs of models that start at home:
  lp_edu   l02_nonstud (school episodes of persons without a school record) + l01_daycare (daycare / pre-school under 5)
  lp_work  l04_wbhome (work business from home) + l03_wahb (work trips of workers whose usual workplace is home)
The larger sample is listed first and is the scale reference (mu = 1).  Records, full choice set (1,588 zones), tract-to-zone
measurement model, chunked likelihood: l_locations.py / l_locations_newls.py (imported; new mode-choice logsum patch) and
activity/lib/tasha_estimation/estimate_fullset_loc.py.  Estimator: ../primary_destination_pooled/pool_core.py (Engine for the separate models,
ParEngine for the pooled ones).  Estimation half for every step; the validation half is used once, at the end.

STARTING POINT: the REVISED separate final models (l_locations.py final stage of 2026-11-09: rules B, C, A, D; <name>_coef.csv /
<name>.log rows "final").  Each purpose keeps its own size terms (base, components theta, mu; mu held at 1 where the separate
model adopted the bound) and its own scale.
COMMON SPECIFICATION: union of the two final linear specifications, one distance form (if the two finals differ in form, both
forms are estimated separately and the one with the lower sum of BIC is used).  A term enters a purpose's own specification
only if it passes that purpose's identification guards (l_locations: >= 20 records each way for a person / time-of-day flag,
>= 5 observed destinations for a zone term); a union term that fails them for one purpose but passes them in the POOLED sample
is carried for that purpose held at 0 and can only enter shared (per-purpose counts are logged).
STEP 2  SEPARATE: the common specification per purpose (Engine); size components with theta < -10 are removed (rule B).
STEP 3  POOLED: U = mu_p V_p.  P0: everything purpose specific (LL = sum of the separate LLs).  Equality imposed block by block in
        this FIXED ORDER, each against the current pooled model:  B1 distance (pieces or linear + log)   B2 boundaries (outside
        the home county / state)   B3 area dummies (Baltimore City, DC, CBD, Virginia, DE/PA/WV)   B4 land use (retail density,
        mix)   B5 ln distance x person / household / time of day (union terms)   B6 impedance (car generalised time, logsum)
        B7 same zone.  Size terms and scales are never shared.  DECISION RULE (dp_pooled): keep the restriction when BIC falls AND
        every shared estimate has its expected sign (l_locations.SIGN; distance pieces below 50 km negative) AND nothing sits at a
        bound; LR of every restriction reported.  With two purposes the first block shared frees the one scale: if it is a
        single coefficient the restricted model is the same model (df 0, same LL); it is then kept as a reparametrisation.
        RE-ENABLED INTERACTIONS (forward, after B7): the interaction blocks of l_locations (cars; age and children; worker; time
        of day) that the small model could not carry (a member failed its >= 20 records guard) enter SHARED by both purposes,
        guard applied to the pooled sample; kept when LR p < 0.05, BIC falls, signs as expected, nothing at a bound
        (l_locations block rule).  Members already in the union are not re-tested.
STEP 4  final pooled model; validation LL per purpose, compared with the revised separate finals (estimation BIC with the pooled
        N for both, validation LL).  Recommendation rule (fixed before estimation): adopt the pooled model only if its validation
        LL total is not worse than the separate total by more than 2.
Outputs: lp_<pair>_fit.csv, lp_<pair>_coef.csv, lp_<pair>.log, lp_<pair>_final.pkl.
    POOL_THREADS=3 TAZ_THREADS=3 python3 estimation/development/other_locations/lp_pooled.py lp_edu [lp_work]
    python3 estimation/development/other_locations/lp_pooled.py lp_work:0      (sensitivity: distance form 0 = the first model's form forced; outputs lp_work_form0_*)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "3")
import numpy as np, pandas as pd
from scipy.stats import chi2

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/locations"; SBS = os.path.dirname(HERE)
sys.path.insert(0, CODE); sys.path.insert(0, f"{os.path.dirname(CODE)}/primary_destination_pooled")
import l_locations_newls as LN          # noqa: E402  (new mode-choice logsum; imports l_locations)
import pool_core as PC                  # noqa: E402
LL = LN.LL; M, C, FL = LL.M, LL.C, LL.FL

PAIRS = {"lp_edu": ["l02_nonstud", "l01_daycare"], "lp_work": ["l04_wbhome", "l03_wahb"]}
PC.ABBR.update({"l01_daycare": "D", "l02_nonstud": "N", "l03_wahb": "H", "l04_wbhome": "B"})
PUR = {p: LL.MODELS[p][1] for p in LL.MODELS}
FLAGS = ["inc0", "inc2", "car0", "car1", "kid", "senior", "child", "worker", "am", "pm", "ev"]
ZT = ["bc", "dcz", "cbd", "va", "othst", "xcounty", "xstate", "intra"]
REEN = [("cars", ["car0", "car1"]), ("age and children", ["kid", "senior", "child"]), ("worker", ["worker"]), ("time of day", ["am", "pm", "ev"])]
BLOCKS = [("B1", "Distance", lambda q: q in ("d", "lnd") or (q.startswith("d_") and not q.startswith("dcz"))),
          ("B2", "Boundaries: outside the home county and state", lambda q: q in ("xcounty", "xstate")),
          ("B3", "Area dummies", lambda q: q in ("bc", "dcz", "cbd", "va", "othst")),
          ("B4", "Land use", lambda q: q in ("lnretden", "mix")),
          ("B5", "Log distance x person, household and time of day", lambda q: q.startswith("lnd_")),
          ("B6", "Impedance: car generalised time, mode-choice logsum", lambda q: q in ("cgt", "ls")),
          ("B7", "Same zone", lambda q: q == "intra")]
_LOGF = None; _runs = {}


def log(s):
    print(s, flush=True)
    if _LOGF: _LOGF.write(s + "\n"); _LOGF.flush()


def sign_of(q):
    if q.startswith("d_") and not q.startswith("dcz"): return None if q == "d_50_inf" else -1
    return LL.sign_of(q)


def run_of(p):
    if p not in _runs:
        r = LL.Run.__new__(LL.Run); r.name = p; r.seg, r.pur = LL.MODELS[p]; _runs[p] = r
    return _runs[p]


def SEG(p):
    return p


def build(p, spec, half="estimation", sk=None):
    """family interface of pool_core.worker: chunks of the full-set likelihood (one configuration per record)"""
    rec, cand = run_of(p).load(half, "primary"); cfg = FL.X.single_cfg(rec); n = FL.F_.CHUNK
    ch = [FL.F_.Chunk(rec.iloc[i:i + n], cand[cand.rec.isin(rec.rec.values[i:i + n])], cfg, spec, PUR[p], sk) for i in range(0, len(rec), n)]
    return ch, len(rec)


def val_ll(p, spec, x, sk):
    rv, cv = run_of(p).load("validation", "primary"); return FL.heldout_ll(spec, rv, cv, PUR[p], sk, np.asarray(x, float)), len(rv)


def counts(p):
    rec, _ = run_of(p).load("estimation", "primary"); ch = M.chooser(rec); z = C.zones(); dz = rec.dzone_pt.values; ok = dz >= 0
    a = rec.home_idx.values[ok]; j = dz[ok]
    cnt = {k: int(z[k].values[j].sum()) for k in ["bc", "dcz", "cbd", "va", "othst"]}
    cnt.update(xcounty=int((z.countyfips.values[j] != z.countyfips.values[a]).sum()), xstate=int((z.state.values[j] != z.state.values[a]).sum()),
               intra=int((j == a).sum()))
    return len(rec), {k: int(ch[k].sum()) for k in FLAGS}, cnt


def eligible(q, n, fl, cnt):
    if q.startswith("lnd_"): k = q[4:]; return 20 <= fl[k] <= n - 20
    if q in ZT: return cnt[q] >= 5
    return True


def final_of(p):
    c = pd.read_csv(f"{HERE}/{p}_coef.csv"); c = c[c.step == "final"]; x = dict(zip(c.param, c.coef))
    lg = open(f"{HERE}/{p}.log").read().split("final specification:")[-1]
    f = pd.read_csv(f"{HERE}/{p}_fit.csv"); f = f[f.step == "final"].iloc[0]
    return dict(lin=[q for q in x if not q.startswith("theta_") and q != "mu_size"], comps=[q[6:] for q in x if q.startswith("theta_")],
                base=lg.split("size base ")[1].split(",")[0].strip(), mu=1.0 if "mu fixed at 1" in lg else None, x=x, row=f)


def x_start(S_new, cur):
    """unchanged keys copied; a new shared key = mean of the members' current values that are not held at 0"""
    x = {}
    for n in S_new.names():
        if n in cur["x"]: x[n] = cur["x"][n]; continue
        if n.startswith("scale|"): x[n] = 1.0; continue
        grp, q = n.split("|"); vals = []
        for p in S_new.P:
            if S_new.has(p, q) and S_new.key(p, q) == n:
                k = cur["S"].key(p, q)
                if k not in cur["S"].fixed: vals.append(cur["x"][k])
        x[n] = float(np.mean(vals)) if vals else 0.0
    return x


def main(arg):
    """arg: pair, or pair:N = sensitivity run with the N-th distance form forced (outputs <pair>_form<N>_*)"""
    global _LOGF
    pair, force = (arg.split(":")[0], int(arg.split(":")[1])) if ":" in arg else (arg, None); out = pair if force is None else f"{pair}_form{force}"
    _LOGF = open(f"{HERE}/{out}.log", "w"); t0 = time.time(); P = PAIRS[pair]; sk = C.skims()
    fin = {p: final_of(p) for p in P}; info = {p: counts(p) for p in P}
    npool = sum(info[p][0] for p in P); flp = {k: sum(info[p][1][k] for p in P) for k in FLAGS}; cntp = {k: sum(info[p][2][k] for p in P) for k in ZT}
    log(f"{pair}: {' + '.join(P)} (scale reference {P[0]}); estimation half, full choice set")
    for p in P:
        f = fin[p]; log(f"  {p}: N {info[p][0]}; revised final K {int(f['row'].K)} LL {f['row'].LL:.2f} BIC {f['row'].BIC:.1f} validation LL "
                        f"{f['row'].validation_LL:.2f}; linear {f['lin']}, size base {f['base']} {f['comps']}, mu {'1 (bound)' if f['mu'] else 'free'}")
        log(f"    flags (records with the flag, of {info[p][0]}): {info[p][1]}; observed destinations per zone term: {info[p][2]}")
    log(f"  pooled sample: N {npool}; flags {flp}; zone terms {cntp}")
    # ---- common specification: union, one distance form
    isd = BLOCKS[0][2]
    forms = []
    for p in P:
        fm = [q for q in fin[p]["lin"] if isd(q)]
        if fm not in forms: forms.append(fm)
    rest = []
    for p in P: rest += [q for q in fin[p]["lin"] if not isd(q) and q not in rest]
    reen = []
    for nm, mem in REEN:
        small = [k for k in mem if not eligible(f"lnd_{k}", *info[P[1]])]
        terms = [f"lnd_{k}" for k in mem if eligible(f"lnd_{k}", npool, flp, cntp) and f"lnd_{k}" not in rest]
        if small and terms: reen.append((nm, terms))
    log(f"  union (without distance): {rest}; distance forms: {forms}; re-enabled interaction blocks (shared only): {reen}")
    sep_all = {}
    for fm in forms:
        union = fm + rest; sep = {}
        for p in P:
            own = [q for q in union if eligible(q, *info[p])]
            comps = list(fin[p]["comps"])
            while True:
                spec = M.Spec("sep", own, fin[p]["base"], comps, mu_fixed=fin[p]["mu"]); ch, N = build(p, spec, sk=sk)
                eng = PC.Engine([p], {p: spec}, {p: ch}, {p: N}, log); S = PC.Structure([p], {p: spec})
                x0 = {f"{p}|{q}": fin[p]["x"].get(q, -0.1 if isd(q) else 0.0) for q in spec.params()}
                r = eng.fit(S, x0, f"sep_{p}", f"separate, common specification ({'/'.join(fm)})")
                zero = [c for c in comps if r["x"][f"{p}|theta_{c}"] < -10]
                if not zero: break
                log(f"    theta < -10 for {p}: {zero} -> removed"); comps = [c for c in comps if c not in zero]
            r.update(own=own, comps=comps, hold=[q for q in union if q not in own and eligible(q, npool, flp, cntp)],
                     out=[q for q in union if q not in own and not eligible(q, npool, flp, cntp)])
            bad = [q for q in own if sign_of(q) is not None and np.sign(r["x"][f"{p}|{q}"]) != sign_of(q)]
            log(f"    {p}: own terms {own}; held at 0 until shared {r['hold']}; not identified even pooled {r['out']}; wrong sign {bad}")
            sep[p] = r
        sep_all[tuple(fm)] = sep
        log(f"  form {fm}: sum of separate BIC {sum(sep[p]['BIC'] for p in P):.1f}, sum LL {sum(sep[p]['LL'] for p in P):.2f}")
    fm = list(min(sep_all, key=lambda k: sum(sep_all[k][p]["BIC"] for p in P)) if force is None else list(sep_all)[force]); sep = sep_all[tuple(fm)]
    log(f"  distance form used: {fm}" + ("" if force is None else " (FORCED: sensitivity run, not the rule)"))
    rows, coefs = [], []
    for k, sp in sep_all.items():
        for p in P:
            s = sp[p]; rows.append(dict(step=f"sep_{p}" + ("" if list(k) == fm else "_altform"), label=f"separate, common specification, {p}, distance {'/'.join(k)} (N {s['N']})",
                                        K=s["K"], LL=s["LL"], BIC=s["BIC"], decision="separate" + ("" if list(k) == fm else "; distance form not used (BIC)")))
            if list(k) == fm:
                for q in s["table"].itertuples(): coefs.append(dict(step=f"sep_{p}", purpose=p, param=q.param.split("|")[1], coef=q.value, se=q.rob_se, t=q.rob_t))
    for p in P:
        o = fin[p]["row"]; rows.append(dict(step=f"current_{p}", label=f"revised separate final model, {p}", K=o.K, LL=o.LL, BIC=o.BIC,
                                            decision="reference", validation_LL=o.validation_LL))
    # ---- pooled
    wl = {p: sep[p]["own"] + sep[p]["hold"] + [q for _, t in reen for q in t] for p in P}
    specs = {p: M.Spec("pool", wl[p], fin[p]["base"], sep[p]["comps"], mu_fixed=fin[p]["mu"]) for p in P}
    fixed = {f"{p}|{q}": 0.0 for p in P for q in sep[p]["hold"] + [q for _, t in reen for q in t]}
    eng = PC.ParEngine("lp_pooled", P, specs, threads=int(os.environ.get("POOL_THREADS", "3")), log=log); nrec = eng.nrec
    S0 = PC.Structure(P, specs, fixed=fixed)
    x0 = {n: (sep[n.split("|")[0]]["x"].get(n, 0.0)) for n in S0.names()}
    cur = eng.fit(S0, x0, "P0", "Pooled, everything purpose specific")
    ssum = sum(sep[p]["LL"] for p in P)
    log(f"  P0 check: LL {cur['LL']:.3f} vs sum of separate LLs {ssum:.3f} (difference {cur['LL'] - ssum:.4f})")
    rows.append(PC.lr_row(cur, None, "start: LL = sum of separate LLs" if abs(cur["LL"] - ssum) < 0.05 else f"start (sum of separate {ssum:.2f})"))
    coefs += PC.coef_rows(cur, "P0")
    for code, lab, sel in BLOCKS:
        terms = [q for q in fm + rest if sel(q) and all(S0.has(p, q) for p in P)]
        if not terms: continue
        Sn = cur["S"].copy({q: tuple(P) for q in terms}, unfix=[f"{p}|{q}" for p in P for q in terms])
        r = eng.fit(Sn, x_start(Sn, cur), code, f"{lab}: shared")
        if r is None: rows.append(dict(step=code, label=lab, decision="not kept: estimation failed")); continue
        shared = [n for n in Sn.names() if n.split("|")[0] not in P + ["scale"] and n not in cur["x"]]
        bad = [n for n in shared if sign_of(n.split("|")[1]) is not None and np.sign(r["x"][n]) != sign_of(n.split("|")[1])]
        rep_ = r["K"] == cur["K"] and abs(r["LL"] - cur["LL"]) < 0.01       # two purposes: sharing one coefficient frees the scale (same model)
        dec = ("not kept: estimate at bound" if r["at_bound"] else "not kept: sign" if bad else "kept: reparametrisation (df 0, frees the scale)"
               if rep_ else "not kept: BIC" if r["BIC"] >= cur["BIC"] else "kept")
        if bad: log(f"    wrong sign: {bad}")
        rows.append(PC.lr_row(r, cur, dec)); coefs += PC.coef_rows(r, code); d = rows[-1]
        log(f"    {code}: {dec} (LR {d['LR']:.2f}, df {d['df']}, p {d['p']:.3g})")
        if dec.startswith("kept"): cur = r
    for i, (nm, terms) in enumerate(reen):
        code = f"BR{i + 1}"
        log(f"  {code} re-enabled {nm}: " + "; ".join(f"{q}: " + ", ".join(f"{p} {info[p][1][q[4:]]}/{info[p][0]}" for p in P) + f", pooled {flp[q[4:]]}/{npool}" for q in terms))
        Sn = cur["S"].copy({q: tuple(P) for q in terms}, unfix=[f"{p}|{q}" for p in P for q in terms])
        r = eng.fit(Sn, x_start(Sn, cur), code, f"Re-enabled interactions, shared: log distance x {nm}")
        if r is None: rows.append(dict(step=code, label=nm, decision="not kept: estimation failed")); continue
        lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; pv = float(chi2.sf(max(lr, 0), df))
        sh = [n for n in Sn.names() if n.split("|")[1] in terms]
        bad = [n for n in sh if sign_of(n.split("|")[1]) is not None and np.sign(r["x"][n]) != sign_of(n.split("|")[1])]
        dec = ("not kept: estimate at bound" if r["at_bound"] else "not kept: LR" if not pv < 0.05 else "not kept: BIC" if r["BIC"] >= cur["BIC"]
               else "not kept: sign" if bad else "kept")
        if bad: log(f"    wrong sign: {bad}")
        rows.append(PC.lr_row(r, cur, dec, restriction=False)); coefs += PC.coef_rows(r, code)
        log(f"    {code}: {dec} (LR {lr:.2f}, df {df}, p {pv:.3g}, dBIC {r['BIC'] - cur['BIC']:+.1f})")
        if dec == "kept": cur = r
    # ---- final pooled model; validation half used once
    log(f"final pooled model: K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f}; shared: {cur['S'].describe()}; free scales {cur['S'].free_scales()}")
    f = PC.lr_row(cur, None, "final"); f.update(step="final", label="final pooled model")
    VV = eng.validation(cur["S"], cur["x"]); eng.close()
    for p in P:
        v, nv = VV[p]; f[f"validation_LL_{p}"] = v; f[f"N_{p}"] = nrec[p]; f[f"Nv_{p}"] = nv
        log(f"  validation LL {p}: pooled {v:.2f}, revised separate final {fin[p]['row'].validation_LL:.2f} (N {nv})")
    vp = sum(VV[p][0] for p in P); vs = sum(fin[p]["row"].validation_LL for p in P); f["validation_LL"] = vp
    Ks = int(sum(fin[p]["row"].K for p in P)); LLs = sum(fin[p]["row"].LL for p in P); BICs = np.log(npool) * Ks - 2 * LLs
    rec = "ADOPT POOLED" if vp >= vs - 2 else "KEEP SEPARATE"
    f["decision"] = f"final; validation LL pooled {vp:.2f} vs separate {vs:.2f} -> {rec}"
    rows.append(f); coefs += PC.coef_rows(cur, "final")
    rows.append(dict(step="separate_total", label="revised separate finals, together (BIC with the pooled N)", K=Ks, LL=LLs, BIC=BICs,
                     decision=f"sum of separate BICs {sum(fin[p]['row'].BIC for p in P):.1f}", validation_LL=vs))
    log(f"  estimation: pooled K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f}; separate finals K {Ks} LL {LLs:.2f} BIC (pooled N) {BICs:.1f}")
    log(f"  validation LL total: pooled {vp:.2f}, separate finals {vs:.2f} (difference {vp - vs:+.2f}) -> {rec}; {time.time() - t0:.0f} s")
    cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"]
    F = pd.DataFrame(rows); F.reindex(columns=cols + [c for c in F.columns if c not in cols]).to_csv(f"{HERE}/{out}_fit.csv", index=False)
    pd.DataFrame(coefs).to_csv(f"{HERE}/{out}_coef.csv", index=False)
    pickle.dump(dict(S=cur["S"].share, fixed=cur["S"].fixed, specs={p: (specs[p].linear, specs[p].size_base, specs[p].size_comps, specs[p].mu_fixed) for p in P},
                     x=cur["x"], cov=cur["cov"]), open(f"{HERE}/{out}_final.pkl", "wb"))


if __name__ == "__main__":
    for a in sys.argv[1:] or list(PAIRS): main(a)
