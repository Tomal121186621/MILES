#!/usr/bin/env python3
"""Location choice of the anchored activities and of the outing destination: model development in a fixed block order.

Models (multinomial logit over all 1,588 zones, full choice set, no sampling; records, choice-set handling, tract-to-zone
measurement model, optimiser and robust sandwich covariance of activity/lib/tasha_estimation/estimate_fullset_loc.py, imported):
  l01_daycare      daycare / pre-school of children under 5 (from home)
  l02_nonstud      school episodes of persons without a school record (from home)
  l03_wahb         work trips of workers whose usual workplace is home (from home)
  l04_wbhome       work business from home
  l05_wbwork       work business of a worker with a usual workplace
  l06_outing_dest  first stop of an outing from the usual workplace (estimate_subtour_dest.py records; anchor = workplace)
Estimation half of the RTS for every selection step; the validation half is used once, at the end, for the final model and the
current specification (re-estimated on the same estimation data), full choice set.

Block order (fixed before estimation; "distance" = car distance from the anchor, for the detour form the detour via the zone
between home and the usual workplace, d(h,j) + d(j,w) - d(h,w); log distance in the detour form = ln(1 + detour)):
   1   size term mu ln(1 + S_j), S_j = sum_c exp(theta_c) x_jc over population, retail, office, other jobs, school enrolment,
       with linear distance.  Base component = the one with the largest weight in this model (as estimate_locations.search);
       components whose weight runs to zero (theta < ln 1e-4) are removed (not identified).  Work business of a worker with a
       usual workplace only: 1a distance from the usual workplace / 1b detour between home and the usual workplace, chosen by BIC.
   2   distance form: 2a piecewise-linear distance (knots 1, 2, 5, 10, 20, 50 km; detour 1, 2, 5, 10, 20 km) in place of the
       linear term, 2b linear + log distance
   3   same zone (detour form: the home zone, the workplace zone)
   4   Baltimore City, Washington DC, central business districts (>= 10,000 jobs per km2)
   5   Virginia; Delaware / Pennsylvania / West Virginia
   6   retail density ln(1 + retail jobs per km2), land-use mix (entropy)
   7   outside the county of the anchor (detour form: of both anchors)
   8   outside the state of the anchor (detour form: of both anchors)
   9   log distance x household income (< $50k, >= $100k)
  10   log distance x car availability (no car, fewer cars than drivers)
  11   log distance x person under 18, person 65+, household with children
  12   log distance x worker
  13   log distance x time of day of the arrival (AM 6-9, PM 15-19, evening 19-6)
  14   impedance by mode: 14a car generalised time (time + cost / value of time), 14b mode-choice logsum (MAST mode model)
Identification guards, fixed before estimation (small samples): a person / time-of-day flag enters only if at least 20 records
have it and 20 do not; a zone dummy or boundary term only if at least 5 observed destinations (zone of the tract point) have it.

Rule: a block is KEPT when the LR test against the current model is significant at 5 %, BIC falls and every sign-checked term
has its expected sign (SIGN; distance pieces, zone attributes, areas, same zone, worker and time-of-day terms have no clear
prior and are not sign-checked); otherwise "not kept: LR" / "not kept: BIC" / "not kept: sign".  Lettered alternatives of one
step are evaluated against the same current model; among those that pass, the lowest BIC is "chosen", the others "not chosen: BIC".
FINAL STAGE (revision 2026-11-09, collinearity/abit_notes.md; steps R1, R2, ...; estimation half; in this order):
  B  size components with theta < -10 (LL flat, not identified) are removed.
  C  distance: linear distance is dropped where car generalised time and log distance are also in; a positive first piece
     (0-1 km) is fixed at 0 (= dropped); the > 50 km piece is fixed at 0 where car generalised time is in; each change is kept
     only if BIC falls.
  A  final check with the WHOLE-SET BAND RULE.  Band sets: area (Baltimore City, DC, Virginia, DE/PA/WV), income (< $50k,
     >= $100k), cars (no car, fewer cars than drivers), age (under 18, 65+), time of day (AM, PM, evening); members that fail an
     identification guard are not members; distance / detour pieces are not band sets.  A kept linear term whose sign reversed
     after later blocks and that is no longer significant (|robust t| < 1.96) is dropped (weakest first, LR reported), EXCEPT a
     band member: its whole set is tested instead (a set present only in part is first completed); a band set present only in
     part (e.g. l04: Virginia and DE/PA/WV in, Baltimore City and DC out after blocks 4-5) is likewise completed and kept whole,
     or dropped whole, by the joint LR (drop only if p >= 0.05).  A complete set with no flagged member is not re-tested for
     removal (it entered whole by its block's LR test); its joint LR p in the final model is reported for information only.
     (The previous rule dropped single terms, merging one band into the reference.)  No other backward elimination.
  D  a size coefficient mu > 1 is re-estimated bounded at 1 (the bound binds: mu = 1, K - 1); adopted only if dBIC <= 2,
     otherwise mu stays free and the cost is reported.
  revise: `python3 l_locations_newls.py revise <name>` resumes from the model before block 14 of the previous run (*_pre1109r.*
  files; blocks 1-13 are not affected), re-runs block 14 with the current mode-choice logsum (tour mode models re-estimated
  2026-11-09) and then the final stage; the current specification is re-estimated with the same logsum.
    TAZ_THREADS=6 python3 estimation/development/other_locations/l_locations.py l01_daycare [l02_nonstud ...]
Outputs <name>_fit.csv, <name>_coef.csv, <name>.log in ESTIMATION_RESULTS/locations."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "6")
import numpy as np, pandas as pd
from scipy.stats import chi2

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/locations"   # results of this step (data); CODE = this folder
TE = f"{WORKSPACE}/3_abit/tasha_estimation"                     # data (work/, results/)
sys.path.insert(0, f"{MILES_HOME}/activity/lib/tasha_estimation")
import estimate_locations as L          # noqa: E402
_loc_load = L.load
import estimate_subtour_dest as W       # noqa: E402  (rebinds L.load; restored below)
L.load = _loc_load
import estimate_fullset_loc as FL       # noqa: E402  (full-set fit and validation LL)
import dc_model as M                    # noqa: E402
import dc_common as C                   # noqa: E402
import torch                            # noqa: E402

MODELS = {"l01_daycare": ("EDUCATION_daycare", "EDUCATION"), "l02_nonstud": ("EDUCATION_nonstud", "EDUCATION"),
          "l03_wahb": ("WORK_wahb", "WORK"), "l04_wbhome": ("WORK_wbhome", "WORK"), "l05_wbwork": ("WORK_wbwork", "WORK"),
          "l06_outing_dest": ("OTHER_wbs", "OTHER")}
COMPS = ["pop", "ret", "off", "oth", "stu"]
BANDS = [("area", ["bc", "dcz", "va", "othst"]), ("income", ["inc0", "inc2"]), ("car", ["car0", "car1"]), ("age", ["kid", "senior"]),
         ("time of day", ["am", "pm", "ev"])]       # dummy band sets (rule A); members that fail an identification guard are not members
SIGN ={"d": -1, "dt": -1, "lnd": -1, "lndt": -1, "xcounty": -1, "xstate": -1, "cgt": -1, "ls": 1,
        "inc0": -1, "inc2": 1, "car0": -1, "car1": -1, "kid": -1, "senior": -1, "child": -1}
LAB = {"d": "linear distance", "dt": "linear detour", "lnd": "log distance", "lndt": "log(1 + detour)", "intra": "same zone",
       "intra_a": "home zone", "intra_b": "workplace zone", "bc": "Baltimore City", "dcz": "Washington DC", "cbd": "central business district",
       "va": "Virginia", "othst": "Delaware, Pennsylvania, West Virginia", "lnretden": "retail density", "mix": "land-use mix",
       "xcounty": "outside the anchor county", "xstate": "outside the anchor state", "cgt": "car generalised time", "ls": "mode-choice logsum",
       "inc0": "income below $50k", "inc2": "income $100k or more", "car0": "no car", "car1": "fewer cars than drivers", "kid": "person under 18",
       "senior": "person 65 or older", "child": "household with children", "worker": "worker", "am": "AM peak", "pm": "PM peak", "ev": "evening"}


def label(p):
    if p.startswith(("d_", "dt_")):
        _, lo, hi = p.split("_"); return f"{'detour' if p.startswith('dt') else 'distance'} {lo}-{hi} km".replace("-inf km", " km and more")
    if p.startswith(("lnd_", "lndt_")): b, x = p.split("_", 1); return f"{LAB[b]} x {LAB[x]}"
    return LAB.get(p, p)


def sign_of(p):
    if p.startswith(("lnd_", "lndt_")): return SIGN.get(p.split("_", 1)[1])
    return SIGN.get(p)


class Run:
    def __init__(self, name):
        self.name = name; self.seg, self.pur = MODELS[name]; self.sk = C.skims(); self.rows, self.coefs = [], []
        self.logf = open(f"{HERE}/{name}.log", "w")

    def log(self, s):
        print(s, flush=True); self.logf.write(s + "\n"); self.logf.flush()

    def load(self, half, form):
        if self.seg == "OTHER_wbs": return W.load(half, self.seg)
        return L.load(half, self.seg, form)

    def data(self, form):
        if form not in getattr(self, "_d", {}):
            self._d = getattr(self, "_d", {}); self._d[form] = self.load("estimation", form)
        return self._d[form]

    # ---------------------------------------------------------------- one model
    def fit(self, step, lab, spec, form, x0=None):
        rec, cand = self.data(form); names = spec.params(); sv = dict(zip(names, M.start_values(spec).numpy()))
        x0 = np.array([(x0 or {}).get(p, sv[p]) for p in names])
        try:
            t = FL.fit(spec, rec, cand, self.pur, self.sk, x0)
        except Exception as e:                                           # singular Hessian: not identified
            self.log(f"  {step}: estimation failed ({e})"); return None
        r = dict(step=step, label=lab, spec=spec, form=form, K=int(t.K.iloc[0]), LL=float(t.LL.iloc[0]), N=len(rec), table=t,
                 converged=bool(t.converged.iloc[0]), at_bound=str(t.at_bound.iloc[0]) if isinstance(t.at_bound.iloc[0], str) else "")
        r["BIC"] = np.log(r["N"]) * r["K"] - 2 * r["LL"]; r["x"] = dict(zip(t.param, t.value))
        for q in t.itertuples(): self.coefs.append(dict(step=step, param=q.param, coef=q.value, se=q.rob_se, t=q.rob_t))
        self.log(f"  {step} {lab}: K {r['K']} LL {r['LL']:.2f} BIC {r['BIC']:.1f} converged {r['converged']}"
                 + (f" at bound: {r['at_bound']}" if r["at_bound"] else ""))
        return r

    def row(self, r, cur=None, decision=""):
        d = dict(step=r["step"], label=r["label"], K=r["K"], LL=r["LL"], BIC=r["BIC"], LR=np.nan, df=np.nan, p=np.nan, decision=decision)
        if cur is not None:
            lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; d.update(LR=lr, df=df, p=float(chi2.sf(lr, df)) if df > 0 else np.nan)
        self.rows.append(d); return d

    def bad_signs(self, r, terms):
        v = r["x"]; return [p for p in terms if sign_of(p) is not None and np.sign(v[p]) != sign_of(p)]

    # ---------------------------------------------------------------- step 1: size term
    def base(self, form, step, lab):
        b0 = "stu" if self.pur == "EDUCATION" else "off"; base, comps = b0, [c for c in COMPS if c != b0]
        lin = ["dt" if form == "stop" else "d"]; r = None
        for _ in range(4):
            spec = M.Spec(step, lin, base, comps); r = self.fit(step, lab, spec, form, r["x"] if r else None)
            w = {base: 1.0, **{c: float(np.exp(r["x"][f"theta_{c}"])) for c in comps}}
            nb = max(w, key=w.get); keep = [c for c in w if c != nb and w[c] / w[nb] > 1e-4]
            if nb == base and keep == comps: break
            self.log(f"  size term: base {nb}, components {keep} (weights relative to {base}: { {k: round(v, 5) for k, v in w.items()} })")
            self.coefs = [c for c in self.coefs if c["step"] != step]
            base, comps = nb, keep; r = None
        return r

    # ---------------------------------------------------------------- data guards
    def guards(self, form):
        rec, _ = self.data(form); ch = M.chooser(rec); z = C.zones(); dz = rec.dzone_pt.values; ok = dz >= 0
        flags = [k for k in ["inc0", "inc2", "car0", "car1", "kid", "senior", "child", "worker", "am", "pm", "ev"]
                 if 20 <= ch[k].sum() <= len(rec) - 20]
        a = rec.home_idx.values[ok]; b = rec.anchor_b.values[ok]; j = dz[ok]; stop = form == "stop"
        cnt = {k: int(z[k].values[j].sum()) for k in ["bc", "dcz", "cbd", "va", "othst"]}
        cty, st = z.countyfips.values, z.state.values
        xc = cty[j] != cty[a]; xs = st[j] != st[a]
        if stop: xc &= cty[j] != cty[b]; xs &= st[j] != st[b]
        cnt.update(xcounty=int(xc.sum()), xstate=int(xs.sum()), intra=int((j == a).sum()), intra_a=int((j == a).sum()),
                   intra_b=int((j == b).sum()) if stop else 0)
        zone_ok = {k for k, v in cnt.items() if v >= 5}
        self.log(f"  person / time-of-day flags with >= 20 records each way: {flags}; observed destinations per zone term: {cnt}")
        return flags, zone_ok

    # ---------------------------------------------------------------- sequence
    def go(self):
        t0 = time.time(); self.log(f"{self.name} ({self.seg}), estimation half, full choice set")
        if self.seg == "WORK_wbwork":
            ra = self.base("primary", "1a", "Size term and linear distance from the usual workplace")
            rb = self.base("stop", "1b", "Size term and linear detour between home and the usual workplace")
            cur = min([ra, rb], key=lambda r: r["BIC"])
            for r in (ra, rb): self.row(r, None, "chosen" if r is cur else "not chosen: BIC")
        else:
            cur = self.base("primary", "1", "Size term and linear distance"); self.row(cur, None, "base")
        form = cur["form"]; flags, zone_ok = self.guards(form); kept_sign = {p: np.sign(v) for p, v in cur["x"].items()}
        cur = self.sequence(cur, self.steps(form), kept_sign, form, flags, zone_ok)
        self.finish(cur, kept_sign, form, flags, zone_ok, t0)

    def steps(self, form):
        stop = form == "stop"; pre, ln = ("dt", "lndt") if stop else ("d", "lnd")
        pieces = C.pw_names(pre, C.DKNOTS if stop else C.KNOTS); imp = "detour" if stop else "distance"
        return [("2", [("2a", f"Piecewise-linear {imp}", pieces, [pre]), ("2b", f"Linear and log {imp}", [ln], [])]),
                 ("3", [("3", "Home zone and workplace zone" if stop else "Same zone", ["intra_a", "intra_b"] if stop else ["intra"], [])]),
                 ("4", [("4", "Baltimore City, Washington DC, central business districts", ["bc", "dcz", "cbd"], [])]),
                 ("5", [("5", "Virginia; Delaware, Pennsylvania, West Virginia", ["va", "othst"], [])]),
                 ("6", [("6", "Retail density and land-use mix", ["lnretden", "mix"], [])]),
                 ("7", [("7", "Outside the counties of both anchors" if stop else "Outside the anchor county", ["xcounty"], [])]),
                 ("8", [("8", "Outside the states of both anchors" if stop else "Outside the anchor state", ["xstate"], [])]),
                 ("9", [("9", f"Log {imp} x household income", [f"{ln}_inc0", f"{ln}_inc2"], [])]),
                 ("10", [("10", f"Log {imp} x car availability", [f"{ln}_car0", f"{ln}_car1"], [])]),
                 ("11", [("11", f"Log {imp} x age and children", [f"{ln}_kid", f"{ln}_senior", f"{ln}_child"], [])]),
                 ("12", [("12", f"Log {imp} x worker", [f"{ln}_worker"], [])]),
                 ("13", [("13", f"Log {imp} x time of day", [f"{ln}_am", f"{ln}_pm", f"{ln}_ev"], [])]),
                 ("14", [("14a", "Car generalised time", ["cgt"], []), ("14b", "Mode-choice logsum", ["ls"], [])])]

    def sequence(self, cur, steps, kept_sign, form, flags, zone_ok):
        zone_terms = {"intra", "intra_a", "intra_b", "bc", "dcz", "cbd", "va", "othst", "xcounty", "xstate"}
        for code, alts in steps:
            res = []
            for sc, lab, add, rem in alts:
                add2 = [p for p in add if not (p in zone_terms and p not in zone_ok)
                        and not (p.startswith(("lnd_", "lndt_")) and p.split("_", 1)[1] not in flags)]
                if len(add2) < len(add): self.log(f"  {sc}: without {[p for p in add if p not in add2]} (identification guard)")
                if not add2: continue
                if len(add2) < len(add):
                    if code in ("4", "5", "9", "10", "11", "13"): lab = ", ".join(label(p) for p in add2); lab = lab[0].upper() + lab[1:]
                lin = [p for p in cur["spec"].linear if p not in rem] + add2
                spec = M.Spec(sc, lin, cur["spec"].size_base, cur["spec"].size_comps)
                r = self.fit(sc, lab, spec, form, cur["x"])
                if r is None: continue
                lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; p = float(chi2.sf(lr, df)) if df > 0 else np.nan
                bad = self.bad_signs(r, add2)
                dec = ("not kept: LR" if not (p < 0.05) else "not kept: BIC" if r["BIC"] >= cur["BIC"] else "not kept: sign" if bad else "pass")
                if bad: self.log(f"    wrong sign: {bad}")
                res.append((r, dec))
            passing = [r for r, d in res if d == "pass"]; best = min(passing, key=lambda r: r["BIC"]) if passing else None
            lettered = len(alts) > 1
            for r, d in res:
                if d == "pass": d = ("chosen" if r is best else "not chosen: BIC") if lettered else "kept"
                self.row(r, cur, d)
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

    def finish(self, cur, kept_sign, form, flags, zone_ok, t0, record=None):
        stop = form == "stop"; pre, ln = ("dt", "lndt") if stop else ("d", "lnd"); imp = "detour" if stop else "distance"; n = [0]
        sets = [(nm, [m for m in mem if m in zone_ok] if nm == "area" else [f"{ln}_{m}" for m in mem if m in flags]) for nm, mem in BANDS]
        sets = [(nm, mem) for nm, mem in sets if mem]; done = set()

        def refit(lab, lin=None, comps=None, mu=None, base=None):
            n[0] += 1; b = base or cur; s = b["spec"]; sc = f"R{n[0]}"
            spec = M.Spec(sc, s.linear if lin is None else lin, s.size_base, s.size_comps if comps is None else comps,
                          mu_fixed=s.mu_fixed if mu is None else mu)
            return self.fit(sc, lab, spec, form, b["x"])
        # B  size components whose weight is not identified (theta < -10, LL flat): removed
        th = [c for c in cur["spec"].size_comps if cur["x"][f"theta_{c}"] < -10]
        if th:
            r = refit(f"Size components not identified (theta < -10) removed: {', '.join(th)}", comps=[c for c in cur["spec"].size_comps if c not in th])
            if r is not None:
                d = self.drop_row(r, cur, "dropped: theta < -10 (not identified)")
                self.log(f"    removed size components {th} (LR {d['LR']:.3f}, df {d['df']}, dBIC {r['BIC'] - cur['BIC']:+.1f})"); cur = r
        # C  distance: linear distance where car time is in; positive first piece; > 50 km piece where car time is in (fixed at 0
        #    = dropped); each change kept only if BIC falls
        tests = []
        if pre in cur["spec"].linear and ln in cur["spec"].linear and "cgt" in cur["spec"].linear: tests.append((pre, f"linear {imp} with car generalised time"))
        if f"{pre}_0_1" in cur["spec"].linear and cur["x"][f"{pre}_0_1"] > 0: tests.append((f"{pre}_0_1", f"positive {imp} 0-1 km slope"))
        if "d_50_inf" in cur["spec"].linear and "cgt" in cur["spec"].linear: tests.append(("d_50_inf", "distance > 50 km with car generalised time"))
        for q, why in tests:
            r = refit(f"{label(q)} fixed at 0 ({why})", lin=[p for p in cur["spec"].linear if p != q])
            if r is None: continue
            ok = r["BIC"] < cur["BIC"]; db = r["BIC"] - cur["BIC"]
            d = self.drop_row(r, cur, "fixed at 0: BIC falls" if ok else "not fixed: BIC")
            self.log(f"    {q} ({cur['x'][q]:+.4f}): {d['decision']} (dBIC {db:+.1f}, LR {d['LR']:.2f}, p {d['p']:.3g})")
            if ok: cur = r
        # A  final check with the whole-set band rule: a member of a band set is never dropped alone; the set is kept whole or
        #    dropped whole (joint LR, drop only if p >= 0.05); every band set in the model is tested jointly once
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
                r = self.fit(sc, f"Final check: without {label(p)}", spec, form, cur["x"])
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
        sk = self.sk
        rv, cv = self.load("validation", form)
        vfin = FL.heldout_ll(cur["spec"], rv, cv, self.pur, sk, np.array([cur["x"][q] for q in cur["spec"].params()]))
        f = self.row(cur, None, "final"); f.update(step="final", label="final model", validation_LL=vfin)
        for c in [c for c in self.coefs if c["step"] == cur["step"]]: self.coefs.append(dict(c, step="final"))
        if record is None:                     # current specification (article), same records, same estimator
            rform = "stop" if self.seg == "WORK_wbwork" else "primary"
            o = pickle.load(open(f"{TE}/work/locsearch_{self.seg}_{rform}.pkl", "rb")); s0 = o["models"]["F"]["spec"]
            cur_tab = pd.read_csv(f"{TE}/results/fullset_loc_estimates.csv"); cur_tab = cur_tab[cur_tab.segment == self.seg].set_index("param").value.to_dict()
            rr = self.fit("record", "current specification", M.Spec("record", s0.linear, s0.size_base, s0.size_comps), rform, cur_tab)
            rv0, cv0 = self.load("validation", rform)
            vrec = FL.heldout_ll(rr["spec"], rv0, cv0, self.pur, sk, np.array([rr["x"][q] for q in rr["spec"].params()]))
            g = self.row(rr, None, ""); g.update(validation_LL=vrec)
        else:                                  # revision: copied from the previous run (same records, same specification)
            self.rows += record[0]; self.coefs += record[1]; g = record[0][0]
        self.log(f"final: K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f} validation LL {vfin:.2f} ({vfin / len(rv):.4f} per record, N {len(rv)})")
        self.log(f"current specification: K {int(g['K'])} LL {g['LL']:.2f} BIC {g['BIC']:.1f} validation LL {g['validation_LL']:.2f}")
        self.log(f"final specification: {cur['spec'].linear}, size base {cur['spec'].size_base}, components {cur['spec'].size_comps}"
                 + ("; mu fixed at 1 (bound)" if cur["spec"].mu_fixed is not None else "") + f"; {time.time() - t0:.0f} s")
        cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"]
        pd.DataFrame(self.rows).reindex(columns=cols).to_csv(f"{HERE}/{self.name}_fit.csv", index=False)
        pd.DataFrame(self.coefs).to_csv(f"{HERE}/{self.name}_coef.csv", index=False)

    def revise(self):
        """revision 2026-11-09: resume from the model before block 14 of the previous run (<name>_fit/_coef_pre1109r.csv,
        <name>_pre1109r.log; blocks 1-13 do not involve the mode-choice logsum and are not affected by rules A-D), re-run block 14
        with the CURRENT mode-choice logsum (tour mode models re-estimated on 2026-11-09: ../mode_choice/m08_coef.csv,
        m09_coef.csv; md5 logged), then the new final stage; the current specification is re-estimated"""
        t0 = time.time(); B = f"{HERE}/{self.name}"
        f0 = pd.read_csv(f"{B}_fit_pre1109r.csv", dtype={"step": str}); c0 = pd.read_csv(f"{B}_coef_pre1109r.csv", dtype={"step": str})
        i = int(np.argmax(f0.step.str.match(r"^(14[a-z]?|F\d+|final|record)$").values)); head = f0.iloc[:i]
        kept = head[head.decision.isin(["base", "kept", "chosen"])]; kept_sign, x = {}, {}
        for st in kept.step:
            x = c0[c0.step == st].drop_duplicates("param", keep="last").set_index("param").coef.to_dict()
            for q, v in x.items(): kept_sign.setdefault(q, np.sign(v))
        lin = [q for q in x if not q.startswith("theta_") and q != "mu_size"]; comps = [q[6:] for q in x if q.startswith("theta_")]
        base = open(f"{B}_pre1109r.log").read().split("final specification:")[1].split("size base ")[1].split(",")[0].strip()
        form = "stop" if any(q.startswith(("dt", "lndt", "intra_a")) for q in lin) else "primary"
        self.rows = head.to_dict("records"); self.coefs = c0[c0.step.isin(head.step)].to_dict("records")
        import hashlib
        md = {f: hashlib.md5(open(os.path.join(os.path.dirname(HERE), "mode_choice", f), "rb").read()).hexdigest()[:10] for f in ("m08_coef.csv", "m09_coef.csv")}
        self.log(f"{self.name} ({self.seg}): REVISION 2026-11-09, resumed from step {kept.step.iloc[-1]} of the previous run (LL {kept.LL.iloc[-1]:.2f}); "
                 f"block 14 re-run with the current mode-choice logsum (md5 {md}), then the final stage (rules B, C, A, D); form {form}, size base {base}")
        flags, zone_ok = self.guards(form)
        r = self.fit("R0", f"Re-estimation of step {kept.step.iloc[-1]} (model before block 14)", M.Spec("R0", lin, base, comps), form, x)
        self.row(r, None, f"start of the revision (step {kept.step.iloc[-1]}, LL {kept.LL.iloc[-1]:.2f})")
        cur = self.sequence(r, [s for s in self.steps(form) if s[0] == "14"], kept_sign, form, flags, zone_ok)
        self.finish(cur, kept_sign, form, flags, zone_ok, t0)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["revise"]:
        for n in a[1:] or list(MODELS): Run(n).revise()
    else:
        for n in a or list(MODELS): Run(n).go()
