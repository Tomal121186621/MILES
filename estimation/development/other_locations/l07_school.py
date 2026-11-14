#!/usr/bin/env python3
"""School location choice by school band (K-8, high school, college): model development in a fixed block order.

Data, estimator and choice set of 2_silo/schoolchoice (imported, nothing copied): students with a school record in the
estimation half of the RTS 2017/18 (school_data.py), location mixture over the possible home and school zones, FULL choice set
(all zones with enrolment of the student's band, sc_03_engine.Design 'full', the choice set of the article table), analytic
gradient, L-BFGS-B (sc_04_stepwise.Search.converge), robust sandwich covariance (Model.robust).  The validation half (full set)
is used once, for the final model and for the current specification re-estimated on the same estimation data.

Block order (fixed before estimation):
   1   size term mu ln S_j (K-12: public enrolment of the band, reference, + private enrolment; college: public 4-year, reference,
       + private 4-year + 2-year) and car peak time (the base S0 of school_stepwise.py)
   2   ln(1 + car time)
   3   same zone
   4   county line: 4a other county; 4b other county x public share of the zone's enrolment of the band (K-12 only;
       college: 4 = other county)
   5   state line: other state
   5s  attendance-boundary public enrolment (in-boundary weight of the public enrolment, SABS 2015-16; K-12 only)
   (County and state line are separate blocks, as in the location models l01-l06.  A first run bundled them in one block, as
   school_stepwise.py does; for K-8 the positive other-state term then rejected the county term with it.  The split was made
   for consistency with l01-l06 and the first run's results are in the log of that run, not used here.)
   6   car time x age (centred) and gender
   7   car time x household income (< $40k, >= $125k)
   8   car time x car availability (no car, fewer cars than drivers)
   9   K-12: private enrolment x household income (< $40k, $75-125k, >= $125k); college: private 4-year x income (< $40k, >= $125k)
  10   college only: 2-year enrolment x age 25+ and household income (< $40k, >= $125k)
  11   school-tour mode-choice logsum
Rule: a block is KEPT when the LR test against the current model is significant at 5 %, BIC falls and the signs are the expected
ones (sc_04_stepwise.K12 / COL: '+' / '-'; '?' = no prior, not checked; the logsum coefficient is expected in (0, 1]); otherwise
"not kept: LR" / "not kept: BIC" / "not kept: sign".  Lettered alternatives (4a / 4b) are evaluated against the same current model;
among those that pass, the lower BIC is "chosen".  Final check: a kept term whose sign reversed after later blocks and that is no
longer significant (|robust t| < 1.96) is dropped (one step each, LR of dropping it reported).  No other backward elimination.
    python3 estimation/development/other_locations/l07_school.py [k8 hs col]   ->  l07_school_<band>_fit.csv, _coef.csv, .log (band k8, hs, college)"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, json, time
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/locations"   # results of this step (data); CODE = this folder
SCD = f"{ORIOLE_HOME}/landuse/schools"   # school-choice code (data: school_common.W)
sys.path.insert(0, SCD)
import school_likelihood as G      # noqa: E402
if os.environ.get("SCHOOL_LOGSUM"):   # school-tour mode-choice logsums of another mode model (same layout)
    G.LSUM = np.load(os.environ["SCHOOL_LOGSUM"], mmap_mode="r")
import school_common as SC        # noqa: E402
import school_stepwise as S    # noqa: E402

BAND = {"k8": "k8", "hs": "hs", "col": "college"}
LAB = {"t": "car time", "lt": "log(1 + car time)", "ls": "school-tour mode-choice logsum", "intra": "same zone", "cc": "other county",
       "ccpub": "other county x public share", "cs": "other state", "size:in": "attendance-boundary public enrolment",
       "agec": "age", "female": "female", "g1": "income below $40k", "g3": "income $75-125k", "g4": "income $125k or more",
       "car0": "no car", "carlow": "fewer cars than drivers", "a25": "age 25 or older", "priv": "private enrolment",
       "priv4": "private 4-year enrolment", "cc_size": "2-year enrolment"}


def label(k):
    if k in LAB: return LAB[k]
    if "*" in k: b, v = k.split("*"); return f"{LAB[b]} x {LAB[v]}"
    c, v = k.split(":"); return f"{LAB['cc_size' if c == 'cc' else c]} x {LAB[v]}"


class Run:
    def __init__(self, seg):
        self.seg = seg; self.name = f"l07_school_{BAND[seg]}"; self.EXP = dict(S.COL if seg == "col" else S.K12)
        self.logf = open(f"{HERE}/{self.name}.log", "w"); self.rows, self.coefs = [], []
        self.D = G.Design(seg, "estimation", "full"); self.N = self.D.N
        self.log(f"{self.name}: estimation half, {self.N} students, {len(self.D.alts)} zones with enrolment (full choice set)")

    def log(self, s):
        print(s, flush=True); self.logf.write(s + "\n"); self.logf.flush()

    def fit(self, step, lab, spec, start=None, fixed=None, D=None):
        D = D or self.D; t, si, sabs = S.split(spec); M = G.Model(D, t, si, sabs, fixed)
        try:
            M = S.Search.converge(None, M, None if start is None else M.at(start)); M.robust()
        except Exception as e:
            self.log(f"  {step} {lab}: no converged fit ({e})"); return None
        tb = M.table(); K = len(M.th)
        r = dict(step=step, label=lab, spec=list(spec), fixed=fixed, K=K, LL=M.ll, BIC=K * np.log(self.N) - 2 * M.ll, M=M,
                 x=M.coef_dict(), t=dict(zip(tb.parameter, tb.robust_t)))
        for q in tb.itertuples(): self.coefs.append(dict(step=step, param=q.parameter, coef=q.estimate, se=q.robust_se, t=q.robust_t))
        self.log(f"  {step} {lab}: K {K} LL {M.ll:.2f} BIC {r['BIC']:.1f} max |score sum| {M.max_grad:.2g}")
        return r

    def row(self, r, cur=None, decision=""):
        d = dict(step=r["step"], label=r["label"], K=r["K"], LL=r["LL"], BIC=r["BIC"], LR=np.nan, df=np.nan, p=np.nan, decision=decision)
        if cur is not None:
            lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; d.update(LR=lr, df=df, p=float(chi2.sf(lr, df)) if df > 0 else np.nan)
        self.rows.append(d); return d

    def bad(self, r, terms):
        out = []
        for k in terms:
            e = self.EXP.get(k, "?"); v = r["x"][S.pname(k)]
            if (e == "+" and v <= 0) or (e == "-" and v >= 0) or (k == "ls" and v > 1): out.append(k)
        return out

    def go(self):
        t0 = time.time(); col = self.seg == "col"
        cur = self.fit("1", "Size term and car time", ["t"]); self.row(cur, None, "base")
        steps = [("2", [("2", "Log(1 + car time)", ["lt"])]), ("3", [("3", "Same zone", ["intra"])])]
        if col: steps.append(("4", [("4", "Other county", ["cc"])]))
        else: steps.append(("4", [("4a", "Other county", ["cc"]), ("4b", "Other county x public share of the enrolment", ["ccpub"])]))
        steps.append(("5", [("5", "Other state", ["cs"])]))
        if not col: steps.append(("5s", [("5s", "Attendance-boundary public enrolment", ["size:in"])]))
        steps += [("6", [("6", "Car time x age and gender", ["t*agec", "t*female"])]), ("7", [("7", "Car time x household income", ["t*g1", "t*g4"])]),
                  ("8", [("8", "Car time x car availability", ["t*car0", "t*carlow"])])]
        if col: steps += [("9", [("9", "Private 4-year enrolment x household income", ["priv4:g1", "priv4:g4"])]),
                          ("10", [("10", "2-year enrolment x age and household income", ["cc:a25", "cc:g1", "cc:g4"])])]
        else: steps.append(("9", [("9", "Private enrolment x household income", ["priv:g1", "priv:g3", "priv:g4"])]))
        steps.append(("11", [("11", "School-tour mode-choice logsum", ["ls"])]))
        sgn = {S.pname(k): np.sign(v) for k, v in zip(cur["spec"], [cur["x"][S.pname(k)] for k in cur["spec"]])}
        for code, alts in steps:
            res = []
            for sc, lab, add in alts:
                r = self.fit(sc, lab, cur["spec"] + add, cur["x"])
                if r is None: continue
                lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; p = float(chi2.sf(lr, df))
                b = self.bad(r, add)
                if b: self.log(f"    unexpected sign: {b}")
                res.append((r, "not kept: LR" if not p < 0.05 else "not kept: BIC" if r["BIC"] >= cur["BIC"] else "not kept: sign" if b else "pass"))
            passing = [r for r, d in res if d == "pass"]; best = min(passing, key=lambda r: r["BIC"]) if passing else None
            for r, d in res: self.row(r, cur, (("chosen" if r is best else "not chosen: BIC") if len(alts) > 1 else "kept") if d == "pass" else d)
            if best is not None:
                for k in best["spec"]:
                    if k not in cur["spec"]: sgn[S.pname(k)] = np.sign(best["x"][S.pname(k)])
                cur = best
        nf = 0
        while True:
            off = [(abs(cur["t"][S.pname(k)]), k) for k in cur["spec"] if np.sign(cur["x"][S.pname(k)]) != sgn[S.pname(k)] and abs(cur["t"][S.pname(k)]) < 1.96]
            if not off: break
            _, k = min(off); nf += 1
            r = self.fit(f"F{nf}", f"Final check: without {label(k)}", [x for x in cur["spec"] if x != k], cur["x"])
            d = self.row(r, cur, "dropped: sign reversed, not significant"); cur = r
            d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"])))   # LR of dropping the term
            self.log(f"    dropped {k} (LR of dropping {d['LR']:.2f}, {int(d['df'])} df, p {d['p']:.3f})")
        # ---- validation half, used once: final model and the current specification
        F = G.Design(self.seg, "validation", "full")
        def vll(r):
            t, si, sabs = S.split(r["spec"]); MF = G.Model(F, t, si, sabs, r["fixed"]); return float(MF.scores(r["M"].th)[0].sum())
        vf = vll(cur); f = self.row(cur, None, "final"); f.update(step="final", label="final model", validation_LL=vf)
        for c in [c for c in self.coefs if c["step"] == cur["step"]]: self.coefs.append(dict(c, step="final"))
        fj = json.load(open(f"{SC.W}/final_{self.seg}.json")); fx = fj.get("fixed") or None
        rr = self.fit("record", "current specification", fj["spec"], fj.get("coef_fullset", fj["coef"]), fx)
        vr = vll(rr); g = self.row(rr, None, ""); g.update(validation_LL=vr)
        self.log(f"final: {cur['spec']}, K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f}; validation LL {vf:.2f} ({vf / F.N:.4f} per student, N {F.N})")
        self.log(f"current specification: {fj['spec']} fixed {fx}, K {rr['K']} LL {rr['LL']:.2f} BIC {rr['BIC']:.1f}; validation LL {vr:.2f} ({vr / F.N:.4f} per student); {time.time() - t0:.0f} s")
        cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"]
        pd.DataFrame(self.rows).reindex(columns=cols).to_csv(f"{HERE}/{self.name}_fit.csv", index=False)
        pd.DataFrame(self.coefs).to_csv(f"{HERE}/{self.name}_coef.csv", index=False)


if __name__ == "__main__":
    for s in sys.argv[1:] or SC.SEG: Run(s).go()
