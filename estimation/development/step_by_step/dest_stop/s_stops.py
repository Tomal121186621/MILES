#!/usr/bin/env python3
"""Stop-location choice of the discretionary stops on tours (SHOPPING, RECREATION, ACCOMPANY, OTHER): model development in a
fixed block order.

Models (multinomial logit over all 1,588 zones, full choice set, no sampling correction; sequential anchors: a = the location the
person comes from, b = the next anchor of the tour; impedance = detour d(a,j) + d(j,b) - d(a,b) by car, km).  Records, location
mixture (TAZ records, destination and anchor configurations), chunked full-set likelihood, optimiser (L-BFGS-B, log size weights
bounded to [-30, 15], mu to [0, 3]) and robust sandwich covariance as 3_abit/tasha_estimation/estimate_fullset_taz.py (imported,
nothing changed):
  s_shop  SHOPPING_stop      s_rec  RECREATION_stop      s_acc  ACCOMPANY_stop      s_oth  OTHER_stop
Estimation half of the RTS for every selection step; the validation half is used once, at the end, for the final model and the
current (article) specification re-estimated on the same estimation data, full choice set (predictive LL of the location mixture).

Block order (fixed before estimation; ln detour = ln(1 + detour)):
   1   size term mu ln(1 + S_j), S_j = sum_c exp(theta_c) x_jc over population, retail, office, other jobs, school enrolment,
       with linear detour.  Start: base component of the original search (shopping: retail jobs, otherwise population); the
       base is moved to the component with the largest weight; components whose weight runs to zero (< 1e-4 of the base) are
       removed (not identified).
   2   detour form: 2a piecewise-linear detour (knots 1, 2, 5, 10, 20 km) in place of the linear term, 2b linear + ln detour
   3   stop in an anchor zone: the zone of the previous location, the zone of the next anchor
   4   area dummies: Baltimore City, Washington DC, central business districts (>= 10,000 jobs per km2), Virginia,
       Delaware / Pennsylvania / West Virginia
   5   land use: retail density ln(1 + retail jobs per km2), land-use mix (entropy)
   6   county and state boundaries: outside the counties of both anchors, outside the states of both anchors
   7   ln detour x household income (< $50k, >= $100k)
   8   ln detour x car availability (no car, fewer cars than drivers)
   9   ln detour x age (person 65+)
  10   ln detour x gender (male)
  11   ln detour x household size (persons)
  12   ln detour x tour mode (tour mode not car)
  13   ln detour x direction (inbound stop: on the way home)
  14   ln detour x time of day of the arrival (AM 6-9, PM 15-19, evening 19-6)
  15   impedance by mode: 15a car generalised detour time (time + cost / value of time), 15b mode-choice logsum of the detour
       (ABIT mode model), 15c both
  16   transit availability (bus door-to-door time from the previous location < 120 min) x household without a car
(Second run, 2026-11-08: a first run, logs *_firstrun_extra_blocks.log, also carried the original search's person under 18,
household with children, worker and work-tour interactions inside blocks 9, 11, 12 and 13; it was stopped before any decision
was final and the household / person / tour blocks restricted to the list of the brief.)
Identification guards, fixed before estimation: a person / tour / time-of-day flag enters only if at least 20 records have it
and 20 do not; a zone dummy or boundary term only if at least 5 observed destinations (zone of the tract point) have it.
All variables exist in the estimation records and are producible by the simulation chain (SILO persons and households, ABIT
tours, zone data, skims); race is not used.

Rule: a block is KEPT when the LR test against the current model is significant at 5 %, BIC falls and every sign-checked term
has its expected sign (SIGN: detour, ln detour, boundaries, car generalised time negative; logsum and transit availability
positive; income, cars, age 65+ and tour-mode interactions as in SIGN; detour pieces, anchor zones, areas, land
use, gender, household size, inbound and time of day have no clear prior and are not sign-checked); otherwise
"not kept: LR" / "not kept: BIC" / "not kept: sign"; a block whose estimates hit an estimator bound: "not kept: estimate at
bound".  Lettered alternatives of one step are evaluated against the same current model; among those that pass, the lowest
BIC is "chosen", the others "not chosen: BIC".
FINAL STAGE (revision 2026-11-09, collinearity/abit_notes.md; steps R1, R2, ...; estimation half; in this order):
  B  size components with theta < -10 (LL flat, not identified) are removed.
  C  detour: a positive first piece (0-1 km) is fixed at 0 (= dropped), linear detour is dropped where car generalised time
     and ln detour are also in; each change is kept only if BIC falls.
  A  final check with the WHOLE-SET BAND RULE.  Band sets: area (Baltimore City, DC, Virginia, DE/PA/WV), income (< $50k,
     >= $100k), cars (no car, fewer cars than drivers), age (65+), time of day (AM, PM, evening); members that fail an
     identification guard are not members; detour pieces are not band sets.  A kept linear term whose sign reversed after
     later blocks and that is no longer significant (|robust t| < 1.96) is dropped (weakest first, LR reported), EXCEPT a band
     member: its whole set is tested instead (a set present only in part is first completed); a band set present only in part
     (e.g. after block decisions) is likewise completed and kept whole, or dropped whole, by the joint LR (drop only if
     p >= 0.05).  A complete set with no flagged member is not re-tested for removal (it entered whole by its block's LR
     test); its joint LR p in the final model is reported for information only.  (The previous rule dropped
     single terms, e.g. no car in s_oth, merging that band into the reference.)  No other backward elimination.
  D  a size coefficient mu > 1 is re-estimated bounded at 1 (the bound binds: mu = 1, K - 1); adopted only if dBIC <= 2,
     otherwise mu stays free and the cost is reported.
  revise: `python3 s_stops_newls.py revise <name>` resumes from the model before block 15 of the previous run (*_pre1109r.*
  files; blocks 1-14 are not affected), re-runs blocks 15-16 with the current mode-choice logsum (tour mode models
  re-estimated 2026-11-09) and then the final stage; the current specification is re-estimated with the same logsum.
    TAZ_THREADS=4 python3 s_stops.py s_shop [s_rec ...]
Outputs <name>_fit.csv, <name>_coef.csv, <name>.log in this folder."""
import os, sys, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "4")
import numpy as np, pandas as pd
from scipy.stats import chi2
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
TE = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026/3_abit/tasha_estimation"
sys.path.insert(0, TE)
import estimate_fullset_taz as F_       # noqa: E402  (records, full-set chunks; wraps dc_model)
import dc_taz_engine as X               # noqa: E402
import dc_model as M                    # noqa: E402
import dc_common as C                   # noqa: E402
import torch                            # noqa: E402

MODELS = {"s_shop": "SHOPPING_stop", "s_rec": "RECREATION_stop", "s_acc": "ACCOMPANY_stop", "s_oth": "OTHER_stop"}
COMPS = ["pop", "ret", "off", "oth", "stu"]
BASE0 = {"SHOPPING": "ret", "RECREATION": "pop", "ACCOMPANY": "pop", "OTHER": "pop"}
BANDS = [("area", ["bc", "dcz", "va", "othst"]), ("income", ["inc0", "inc2"]), ("car", ["car0", "car1"]), ("age", ["kid", "senior"]),
         ("time of day", ["am", "pm", "ev"])]       # dummy band sets (rule A); members that fail an identification guard are not members
FLAGS = ["inc0", "inc2", "car0", "car1", "senior", "male", "nonauto", "inbound", "am", "pm", "ev"]
SIGN = {"dt": -1, "lndt": -1, "xcounty": -1, "xstate": -1, "cgt": -1, "ls": 1, "ptav_car0": 1,
        "inc0": -1, "inc2": 1, "car0": -1, "car1": -1, "kid": -1, "senior": -1, "child": -1, "nonauto": -1, "worktour": -1}
LAB = {"dt": "linear detour", "lndt": "ln(1 + detour)", "intra_a": "zone of the previous location", "intra_b": "zone of the next anchor",
       "bc": "Baltimore City", "dcz": "Washington DC", "cbd": "central business district", "va": "Virginia",
       "othst": "Delaware, Pennsylvania, West Virginia", "lnretden": "retail density", "mix": "land-use mix",
       "xcounty": "outside the counties of both anchors", "xstate": "outside the states of both anchors", "cgt": "car generalised detour time",
       "ls": "mode-choice logsum", "ptav_car0": "transit available x no car", "inc0": "income below $50k", "inc2": "income $100k or more",
       "car0": "no car", "car1": "fewer cars than drivers", "kid": "person under 18", "senior": "person 65 or older", "male": "male",
       "hhsize": "household size", "child": "household with children", "worker": "worker", "nonauto": "tour mode not car",
       "worktour": "work or school tour", "inbound": "inbound stop", "am": "AM peak", "pm": "PM peak", "ev": "evening"}

# person attributes not in dc_model.chooser (gender, household size): added here, nothing else changes
_chooser = M.chooser


def chooser(rec):
    a = _chooser(rec); a["male"] = np.asarray(rec.male, float); a["hhsize"] = np.asarray(rec.hhsize, float); return a


M.chooser = chooser


def label(p):
    if p.startswith("dt_"):
        _, lo, hi = p.split("_"); return f"detour {lo}-{hi} km".replace("-inf km", " km and more")
    if p.startswith("lndt_"): return f"ln(1 + detour) x {LAB[p.split('_', 1)[1]]}"
    return LAB.get(p, p)


def sign_of(p):
    if p.startswith("lndt_"): return SIGN.get(p.split("_", 1)[1])
    return SIGN.get(p)


def bounds_of(names):
    return [(-30.0, 15.0) if p.startswith("theta_") else (0.0, 3.0) if p == "mu_size" else (None, None) for p in names]


def fit_mix(spec, rec, cand, cfg, pur, sk, x0):
    """full-set ML of the location mixture (chunks of estimate_fullset_taz), robust sandwich covariance"""
    names = spec.params(); t0 = time.time()
    chunks = [F_.Chunk(rec.iloc[i:i + F_.CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + F_.CHUNK])], cfg, spec, pur, sk)
              for i in range(0, len(rec), F_.CHUNK)]
    bounds = bounds_of(names)
    x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bounds)])
    def fg(v):
        t = torch.tensor(v, requires_grad=True); tot = 0.0
        for c in chunks:
            l = -c.ll(t, spec).sum(); l.backward(); tot += float(l.detach())
        return (tot, t.grad.numpy().copy()) if np.isfinite(tot) else (1e15, np.zeros_like(v))
    r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bounds, options=dict(maxiter=3000, maxfun=12000, ftol=1e-13, gtol=1e-6, maxcor=30))
    x = torch.tensor(r.x); K = len(x)
    from torch.func import jvp
    H = torch.zeros((K, K)); G = []
    for c in chunks:
        H += torch.autograd.functional.hessian(lambda t: c.ll(t, spec).sum(), x)
        G.append(torch.stack([jvp(lambda t: c.ll(t, spec), (x,), (e,))[1] for e in torch.eye(K)], 1))
    G = torch.cat(G)
    at_bound = [p for p, v, (lo, hi) in zip(names, r.x, bounds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
    free = torch.tensor([p not in at_bound for p in names]); cov = torch.full((K, K), float("nan"))
    Hi = torch.linalg.inv(-H[free][:, free]); Gf = G[:, free]; fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
    for a, ia in enumerate(fi): cov[ia, fi] = cf[a]
    se = torch.sqrt(torch.clamp(torch.diag(cov), min=0))
    tab = pd.DataFrame({"param": names, "value": x.numpy(), "rob_se": se.numpy(), "rob_t": (x / se).numpy()})
    LL = -float(r.fun); LL0 = sum(c.ll0() for c in chunks)
    return tab.assign(N=len(rec), LL=LL, LL0=LL0, K=K, converged=bool(r.success), maxgrad=float(G.sum(0).abs().max()),
                      nit=int(r.nit), secs=time.time() - t0, at_bound=" ".join(at_bound))


class Run:
    def __init__(self, name):
        self.name = name; self.seg = MODELS[name]; self.pur = self.seg.split("_")[0]; self.sk = C.skims(); self.rows, self.coefs = [], []
        self.logf = open(f"{HERE}/{name}.log", "w")
        self.rec, self.cand, self.cfg = F_.load(self.seg, "estimation")

    def log(self, s):
        print(s, flush=True); self.logf.write(s + "\n"); self.logf.flush()

    # ---------------------------------------------------------------- one model
    def fit(self, step, lab, spec, x0=None):
        names = spec.params(); sv = dict(zip(names, M.start_values(spec).numpy()))
        x0 = np.array([(x0 or {}).get(p, sv[p]) for p in names])
        try:
            t = fit_mix(spec, self.rec, self.cand, self.cfg, self.pur, self.sk, x0)
        except Exception as e:                                           # singular Hessian: not identified
            self.log(f"  {step}: estimation failed ({e})"); return None
        r = dict(step=step, label=lab, spec=spec, K=int(t.K.iloc[0]), LL=float(t.LL.iloc[0]), N=len(self.rec), table=t,
                 converged=bool(t.converged.iloc[0]), at_bound=str(t.at_bound.iloc[0]) if isinstance(t.at_bound.iloc[0], str) else "")
        r["BIC"] = np.log(r["N"]) * r["K"] - 2 * r["LL"]; r["x"] = dict(zip(t.param, t.value))
        for q in t.itertuples(): self.coefs.append(dict(step=step, param=q.param, coef=q.value, se=q.rob_se, t=q.rob_t))
        self.log(f"  {step} {lab}: K {r['K']} LL {r['LL']:.2f} BIC {r['BIC']:.1f} converged {r['converged']} maxgrad {t.maxgrad.iloc[0]:.1e} "
                 f"({int(t.nit.iloc[0])} it, {t.secs.iloc[0]:.0f} s)" + (f" at bound: {r['at_bound']}" if r["at_bound"] else ""))
        return r

    def row(self, r, cur=None, decision=""):
        d = dict(step=r["step"], label=r["label"], K=r["K"], LL=r["LL"], BIC=r["BIC"], LR=np.nan, df=np.nan, p=np.nan, decision=decision)
        if cur is not None:
            lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; d.update(LR=lr, df=df, p=float(chi2.sf(lr, df)) if df > 0 else np.nan)
        self.rows.append(d); return d

    # ---------------------------------------------------------------- step 1: size term
    def base(self):
        b0 = BASE0[self.pur]; base, comps = b0, [c for c in COMPS if c != b0]; r = None
        for _ in range(5):
            spec = M.Spec("1", ["dt"], base, comps); r = self.fit("1", "Size term and linear detour", spec, r["x"] if r else None)
            w = {base: 1.0, **{c: float(np.exp(r["x"][f"theta_{c}"])) for c in comps}}
            nb = max(w, key=w.get); keep = [c for c in w if c != nb and w[c] / w[nb] > 1e-4]
            if nb == base and keep == comps: break
            self.log(f"  size term: base {nb}, components {keep} (weights relative to {base}: { {k: round(v, 5) for k, v in w.items()} })")
            self.coefs = [c for c in self.coefs if c["step"] != "1"]
            base, comps = nb, keep; r = None
        return r

    # ---------------------------------------------------------------- data guards
    def guards(self):
        rec = self.rec; ch = M.chooser(rec); z = C.zones(); dz = rec.dzone_pt.values; ok = dz >= 0
        flags = [k for k in FLAGS if 20 <= ch[k].sum() <= len(rec) - 20]
        a = rec.home_idx.values[ok]; b = rec.anchor_b.values[ok]; j = dz[ok]
        cnt = {k: int(z[k].values[j].sum()) for k in ["bc", "dcz", "cbd", "va", "othst"]}
        cty, st = z.countyfips.values, z.state.values
        xc = (cty[j] != cty[a]) & (cty[j] != cty[b]); xs = (st[j] != st[a]) & (st[j] != st[b])
        cnt.update(xcounty=int(xc.sum()), xstate=int(xs.sum()), intra_a=int((j == a).sum()), intra_b=int((j == b).sum()))
        zone_ok = {k for k, v in cnt.items() if v >= 5}
        self.log(f"  N {len(rec)}; flags with >= 20 records each way: {flags}; observed destinations per zone term: {cnt}")
        return flags, zone_ok

    # ---------------------------------------------------------------- sequence
    def go(self):
        t0 = time.time(); self.log(f"{self.name} ({self.seg}), estimation half, full choice set, location mixture")
        cur = self.base(); self.row(cur, None, "base")
        flags, zone_ok = self.guards(); kept_sign = {p: np.sign(v) for p, v in cur["x"].items()}
        cur = self.sequence(cur, self.steps(), kept_sign, flags, zone_ok)
        self.finish(cur, kept_sign, flags, zone_ok, t0)

    def steps(self):
        pieces = C.pw_names("dt", C.DKNOTS); ix = lambda *v: [f"lndt_{k}" for k in v]
        return [("2", [("2a", "Piecewise-linear detour", pieces, ["dt"]), ("2b", "Linear and log detour", ["lndt"], [])]),
                 ("3", [("3", "Stop in the zone of the previous location or of the next anchor", ["intra_a", "intra_b"], [])]),
                 ("4", [("4", "Area: Baltimore City, Washington DC, central business districts, Virginia, other states", ["bc", "dcz", "cbd", "va", "othst"], [])]),
                 ("5", [("5", "Land use: retail density and land-use mix", ["lnretden", "mix"], [])]),
                 ("6", [("6", "Outside the counties and the states of both anchors", ["xcounty", "xstate"], [])]),
                 ("7", [("7", "Log detour x household income", ix("inc0", "inc2"), [])]),
                 ("8", [("8", "Log detour x car availability", ix("car0", "car1"), [])]),
                 ("9", [("9", "Log detour x person 65+", ix("senior"), [])]),
                 ("10", [("10", "Log detour x gender", ix("male"), [])]),
                 ("11", [("11", "Log detour x household size", ix("hhsize"), [])]),
                 ("12", [("12", "Log detour x tour mode not car", ix("nonauto"), [])]),
                 ("13", [("13", "Log detour x inbound stop", ix("inbound"), [])]),
                 ("14", [("14", "Log detour x time of day", ix("am", "pm", "ev"), [])]),
                 ("15", [("15a", "Car generalised detour time", ["cgt"], []), ("15b", "Mode-choice logsum of the detour", ["ls"], []),
                         ("15c", "Car generalised detour time and mode-choice logsum", ["cgt", "ls"], [])]),
                 ("16", [("16", "Transit availability x household without a car", ["ptav_car0"], [])])]

    def sequence(self, cur, steps, kept_sign, flags, zone_ok):
        zone_terms = {"intra_a", "intra_b", "bc", "dcz", "cbd", "va", "othst", "xcounty", "xstate"}
        gflags = set(flags) | {"hhsize"}
        for code, alts in steps:
            res = []
            for sc, lab, add, rem in alts:
                add2 = [p for p in add if not (p in zone_terms and p not in zone_ok)
                        and not (p.startswith("lndt_") and p.split("_", 1)[1] not in gflags)
                        and not (p == "ptav_car0" and "car0" not in gflags)]
                if len(add2) < len(add):
                    self.log(f"  {sc}: without {[p for p in add if p not in add2]} (identification guard)")
                    if add2 and code not in ("2", "15"): lab = lab.split(":")[0] + ": " + ", ".join(label(p) for p in add2) if ":" in lab else lab + " (" + ", ".join(label(p) for p in add2) + ")"
                if not add2: continue
                lin = [p for p in cur["spec"].linear if p not in rem] + add2
                spec = M.Spec(sc, lin, cur["spec"].size_base, cur["spec"].size_comps)
                r = self.fit(sc, lab, spec, cur["x"])
                if r is None:
                    self.rows.append(dict(step=sc, label=lab, decision="not kept: estimation failed")); continue
                lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; p = float(chi2.sf(lr, df)) if df > 0 else np.nan
                bad = [q for q in add2 if sign_of(q) is not None and np.sign(r["x"][q]) != sign_of(q)]
                dec = ("not kept: estimate at bound" if r["at_bound"] else "not kept: LR" if not (p < 0.05) else
                       "not kept: BIC" if r["BIC"] >= cur["BIC"] else "not kept: sign" if bad else "pass")
                if bad: self.log(f"    wrong sign: {bad}")
                res.append((r, dec))
            passing = [r for r, d in res if d == "pass"]; best = min(passing, key=lambda r: r["BIC"]) if passing else None
            lettered = len(alts) > 1
            for r, d in res:
                if d == "pass": d = ("chosen" if r is best else "not chosen: BIC") if lettered else "kept"
                self.row(r, cur, d); self.log(f"    {r['step']}: {d}")
            if best is not None:
                for q, v in best["x"].items():
                    if q not in cur["x"]: kept_sign[q] = np.sign(v)
                cur = best
        return cur

    # ---------------------------------------------------------------- final stage (revision 2026-11-09, rules B, C, A, D)
    def drop_row(self, r, cur, decision):
        """row of the restriction r of cur: LR = 2 (LL_cur - LL_r), df = parameters removed"""
        d = self.row(r, cur, decision); lr, df = -d["LR"], -d["df"]
        d.update(LR=lr, df=df, p=float(chi2.sf(max(lr, 0), df)) if df > 0 else np.nan); return d

    def finish(self, cur, kept_sign, flags, zone_ok, t0, record=None):
        n = [0]; gflags = set(flags)
        sets = [(nm, [m for m in mem if m in zone_ok] if nm == "area" else [f"lndt_{m}" for m in mem if m in gflags]) for nm, mem in BANDS]
        sets = [(nm, mem) for nm, mem in sets if mem]; done = set()

        def refit(lab, lin=None, comps=None, mu=None, base=None):
            n[0] += 1; b = base or cur; s = b["spec"]; sc = f"R{n[0]}"
            spec = M.Spec(sc, s.linear if lin is None else lin, s.size_base, s.size_comps if comps is None else comps,
                          mu_fixed=s.mu_fixed if mu is None else mu)
            return self.fit(sc, lab, spec, b["x"])
        # B  size components whose weight is not identified (theta < -10, LL flat): removed
        th = [c for c in cur["spec"].size_comps if cur["x"][f"theta_{c}"] < -10]
        if th:
            r = refit(f"Size components not identified (theta < -10) removed: {', '.join(th)}", comps=[c for c in cur["spec"].size_comps if c not in th])
            if r is not None:
                d = self.drop_row(r, cur, "dropped: theta < -10 (not identified)")
                self.log(f"    removed size components {th} (LR {d['LR']:.3f}, df {d['df']}, dBIC {r['BIC'] - cur['BIC']:+.1f})"); cur = r
        # C  detour: linear detour where car time is in; positive first piece (0-1 km) fixed at 0 (= dropped); kept only if BIC falls
        tests = []
        if "dt" in cur["spec"].linear and "lndt" in cur["spec"].linear and "cgt" in cur["spec"].linear: tests.append(("dt", "linear detour with car generalised time"))
        if "dt_0_1" in cur["spec"].linear and cur["x"]["dt_0_1"] > 0: tests.append(("dt_0_1", "positive detour 0-1 km slope"))
        for q, why in tests:
            r = refit(f"{label(q)} fixed at 0 ({why})", lin=[p for p in cur["spec"].linear if p != q])
            if r is None: continue
            ok = r["BIC"] < cur["BIC"]; db = r["BIC"] - cur["BIC"]
            d = self.drop_row(r, cur, "fixed at 0: BIC falls" if ok else "not fixed: BIC")
            self.log(f"    {q} ({cur['x'][q]:+.4f}): {d['decision']} (dBIC {db:+.1f}, LR {d['LR']:.2f}, p {d['p']:.3g})")
            if ok: cur = r
        # A  final check with the whole-set band rule (see the docstring)
        set_of = lambda p: next((s for s in sets if p in s[1]), None)

        def band(nm, mem, why, act=True):
            nonlocal cur
            have = [q for q in mem if q in cur["spec"].linear]; miss = [q for q in mem if q not in have]; rw = cur
            if miss:
                rw = refit(f"Band set {nm}: whole set ({', '.join(label(q) for q in mem)})", lin=cur["spec"].linear + miss)
            rn = refit(f"Band set {nm}: without the whole set", lin=[q for q in rw["spec"].linear if q not in mem], base=rw)
            lr = 2 * (rw["LL"] - rn["LL"]); df = rw["K"] - rn["K"]; p = float(chi2.sf(max(lr, 0), df)); keep = p < 0.05 or not act
            if not act:                        # complete set, no member flagged: joint LR reported only (no backward elimination)
                self.drop_row(rn, rw, f"information only: set entered whole at its block, kept (joint LR p {p:.3g})")
                self.log(f"    band set {nm} {mem}: joint LR {lr:.2f}, df {df}, p {p:.3g} (information only; kept)"); done.add(nm); return
            if miss: self.row(rw, cur, f"whole band set {'kept' if keep else 'not kept'} (joint LR p {p:.3g}); {why}")
            self.drop_row(rn, rw, ("not dropped: joint LR p < 0.05" if keep else "dropped: whole band set, joint LR p >= 0.05") + f"; {why}")
            self.log(f"    band set {nm} {mem} (in the model before: {have}): joint LR {lr:.2f}, df {df}, p {p:.3g} -> "
                     f"{'kept whole' if keep else 'dropped whole'}")
            cur = rw if keep else rn; done.add(nm)

        def sign_loop():
            nonlocal cur
            while True:
                t = cur["table"].set_index("param")
                off = [(abs(t.rob_t[p]), p) for p in cur["spec"].linear if p in kept_sign and np.sign(t.value[p]) != kept_sign[p]
                       and abs(t.rob_t[p]) < 1.96 and not (set_of(p) and set_of(p)[0] in done)]
                if not off: return
                _, p = min(off); s = set_of(p)
                if s: band(s[0], s[1], f"sign of {label(p)} reversed, not significant"); continue
                sc = f"F{sum(1 for r in self.rows if str(r['step']).startswith('F')) + 1}"
                spec = M.Spec(sc, [q for q in cur["spec"].linear if q != p], cur["spec"].size_base, cur["spec"].size_comps, mu_fixed=cur["spec"].mu_fixed)
                r = self.fit(sc, f"Final check: without {label(p)}", spec, cur["x"])
                d = self.drop_row(r, cur, "dropped: sign reversed, not significant"); cur = r
                self.log(f"    dropped {p} (LR of dropping {d['LR']:.2f}, {int(d['df'])} df, p {d['p']:.3f})")
        sign_loop()
        for nm, mem in sets:                   # a set present only in part is completed or dropped whole; a complete set: p reported
            have = [q for q in mem if q in cur["spec"].linear]
            if nm not in done and have: band(nm, mem, "band set present only in part", act=len(have) < len(mem))
        sign_loop()
        # D  size coefficient above 1: re-estimated with mu bounded at 1 (the bound binds, so mu = 1, K - 1); adopted if dBIC <= 2
        if cur["spec"].mu_fixed is None and cur["x"]["mu_size"] > 1:
            r = refit("Size coefficient bounded at 1 (estimate on the bound: mu = 1)", mu=1.0)
            if r is not None:
                dll, db = r["LL"] - cur["LL"], r["BIC"] - cur["BIC"]; ok = db <= 2
                self.drop_row(r, cur, f"mu <= 1 {'adopted' if ok else 'not adopted'}: dLL {dll:.2f}, dBIC {db:+.1f} (adopt if dBIC <= 2)")
                self.log(f"    mu {cur['x']['mu_size']:.3f} -> 1: dLL {dll:.2f}, dBIC {db:+.1f}: {'adopted' if ok else 'not adopted'}")
                if ok: cur = r
        # ---- final model and current specification on the validation half (used once)
        rv, cv, gv = F_.load(self.seg, "validation"); sk = self.sk
        hf = X.heldout(rv, cv, gv, cur["spec"], np.array([cur["x"][q] for q in cur["spec"].params()]), self.pur, sk, obs="mix")
        vfin = float(hf["LL"].sum())
        f = self.row(cur, None, "final"); f.update(step="final", label="final model", validation_LL=vfin)
        for c in [c for c in self.coefs if c["step"] == cur["step"]]: self.coefs.append(dict(c, step="final"))
        if record is None:
            s0 = F_.spec_of(self.seg)
            cur_tab = pd.read_csv(f"{TE}/results/fullset_estimates_taz.csv"); cur_tab = cur_tab[cur_tab.segment == self.seg].set_index("param").value.to_dict()
            rr = self.fit("record", "current specification", M.Spec("record", s0.linear, s0.size_base, s0.size_comps), cur_tab)
            hr = X.heldout(rv, cv, gv, rr["spec"], np.array([rr["x"][q] for q in rr["spec"].params()]), self.pur, sk, obs="mix")
            vrec = float(hr["LL"].sum())
            g = self.row(rr, None, ""); g.update(validation_LL=vrec)
            kmr = f"; mean leg km pred {np.average(hr['km_pred'], weights=rv.w):.2f}"
        else:                                  # revision: copied from the previous run (same records, same specification)
            self.rows += record[0]; self.coefs += record[1]; g = record[0][0]; kmr = " (copied from the previous run)"
        self.log(f"final: K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f} validation LL {vfin:.2f} ({vfin / len(rv):.4f} per record, N {len(rv)}); "
                 f"mean leg km obs {np.average(hf['km_obs'], weights=rv.w):.2f} pred {np.average(hf['km_pred'], weights=rv.w):.2f}")
        self.log(f"current specification: K {int(g['K'])} LL {g['LL']:.2f} BIC {g['BIC']:.1f} validation LL {g['validation_LL']:.2f} "
                 f"({g['validation_LL'] / len(rv):.4f} per record){kmr}")
        self.log(f"final specification: {cur['spec'].linear}, size base {cur['spec'].size_base}, components {cur['spec'].size_comps}"
                 + ("; mu fixed at 1 (bound)" if cur["spec"].mu_fixed is not None else "") + f"; {time.time() - t0:.0f} s")
        cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"]
        pd.DataFrame(self.rows).reindex(columns=cols).to_csv(f"{HERE}/{self.name}_fit.csv", index=False)
        pd.DataFrame(self.coefs).to_csv(f"{HERE}/{self.name}_coef.csv", index=False)
        pd.DataFrame([dict(N_estimation=len(self.rec), N_validation=len(rv))]).to_csv(f"{HERE}/{self.name}_n.csv", index=False)

    def revise(self):
        """revision 2026-11-09: resume from the model before block 15 of the previous run (<name>_fit/_coef_pre1109r.csv,
        <name>_pre1109r.log; blocks 1-14 do not involve the mode-choice logsum and are not affected by rules A-D), re-run blocks
        15 and 16 with the CURRENT mode-choice logsum (the tour mode models were re-estimated on 2026-11-09: ../mode_choice/
        m08_coef.csv; the md5 is logged), then the new final stage; the current specification (which also carries the
        logsum) is re-estimated"""
        t0 = time.time(); B = f"{HERE}/{self.name}"
        f0 = pd.read_csv(f"{B}_fit_pre1109r.csv", dtype={"step": str}); c0 = pd.read_csv(f"{B}_coef_pre1109r.csv", dtype={"step": str})
        i = int(np.argmax(f0.step.str.match(r"^(15[a-z]?|16|F\d+|final|record)$").values)); head = f0.iloc[:i]
        kept = head[head.decision.isin(["base", "kept", "chosen"])]; kept_sign, x = {}, {}
        for st in kept.step:
            x = c0[c0.step == st].drop_duplicates("param", keep="last").set_index("param").coef.to_dict()
            for q, v in x.items(): kept_sign.setdefault(q, np.sign(v))
        lin = [q for q in x if not q.startswith("theta_") and q != "mu_size"]; comps = [q[6:] for q in x if q.startswith("theta_")]
        base = open(f"{B}_pre1109r.log").read().split("final specification:")[1].split("size base ")[1].split(",")[0].strip()
        self.rows = head.to_dict("records"); self.coefs = c0[c0.step.isin(head.step)].to_dict("records")
        import hashlib
        mc = os.path.join(os.path.dirname(HERE), "mode_choice", "m08_coef.csv")
        self.log(f"{self.name} ({self.seg}): REVISION 2026-11-09, resumed from step {kept.step.iloc[-1]} of the previous run (LL {kept.LL.iloc[-1]:.2f}); "
                 f"blocks 15-16 re-run with the current mode-choice logsum (m08_coef.csv md5 {hashlib.md5(open(mc, 'rb').read()).hexdigest()[:10]}, "
                 f"modified {time.ctime(os.path.getmtime(mc))}), then the final stage (rules B, C, A, D); size base {base}")
        flags, zone_ok = self.guards()
        r = self.fit("R0", f"Re-estimation of step {kept.step.iloc[-1]} (model before block 15)", M.Spec("R0", lin, base, comps), x)
        self.row(r, None, f"start of the revision (step {kept.step.iloc[-1]}, LL {kept.LL.iloc[-1]:.2f})")
        cur = self.sequence(r, [s for s in self.steps() if s[0] in ("15", "16")], kept_sign, flags, zone_ok)
        self.finish(cur, kept_sign, flags, zone_ok, t0)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["revise"]:
        for n in a[1:] or list(MODELS): Run(n).revise()
    else:
        for n in a or list(MODELS): Run(n).go()
