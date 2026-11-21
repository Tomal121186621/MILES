#!/usr/bin/env python3
"""School location choice: rerun with the decisions of 2026-11-18 on the l09 tests (test; nothing adopted, l09 files untouched).

Imports the l09 engine extensions (l09_school_ext.Design2 / Model2 / zone data; sc_03/sc_04 engine) and adds:
  qpub   quality on the public part only: (share of the zone's band enrolment in Maryland public schools with a score) x
         (enrolment-weighted mean % proficient of those schools - MD mean) / 10
  qnone  share of the zone's band enrolment in public schools without a score (outside Maryland or no value)
  The private part keeps its own log weight g_priv (K-8 free; high school: free vs fixed at 0 re-tested in the quality block).
Blocks: 0 cleanups (K-8 without t x fewer cars than drivers; high school g_priv fixed 0; college without t x income < $40k if
BIC falls), 4 charter-or-magnet share (K-12), 2 quality (K-12; high school with g_priv fixed / free), 2i quality x income
< $40k or >= $125k (one at a time, at most one kept), 1 own-race share (last).  No Baltimore City term; college size = total
enrolment (the dormitory test is in l09).  Rule of l07/l09 (LR 5 %, BIC falls, expected sign).  Validation half once at the
end: final, final without race, cleanup.  Collinearity: correlations and VIF of the utility attributes (and ln of each size
component) over available (home row, zone) pairs of the estimation half.
    python3 l10_school.py k8|hs|col  ->  l10_school_<band>_fit.csv, _coef.csv, _final_coef.csv (parameter,value), _collin.csv, .log"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/locations"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import l09_school_ext as X9   # noqa: E402  (engine extensions; its module-level code only loads the l09 zone data)
G, S, SC = X9.G, X9.S, X9.SC

PUBZ = {b: SC.size()[b].get("pub", np.zeros(X9.NZ)) for b in ("elementary", "middle", "high")}
QZ = {}
for b in PUBZ:
    n = X9.zarr(b, "n"); w = X9.zarr(b, "w_prof"); q = X9.zarr(b, "qual", np.nan)
    QZ[b] = dict(qpub=np.where(n > 0, w / np.maximum(n, 1e-9), 0) * np.nan_to_num(q / 10.0 - X9.QMEAN) * (w > 0),
                 qnone=np.where(n > 0, np.maximum(PUBZ[b] - w, 0) / np.maximum(n, 1e-9), 0))


class Design3(X9.Design2):
    def base(self, name):
        if name in ("qpub", "qnone"):
            out = np.zeros(self.A.shape, np.float32); rb = self.band[self.rec]
            for b in G.BANDS[self.seg]:
                m = rb == b
                if m.any(): out[m] = QZ[b][name][self.A[m]]
            return out
        return super().base(name)


X9.Design2 = Design3   # Run.design of l09 builds X9.Design2 -> the extended class
X9.EXP_K12.update({"qpub": "+", "qnone": "?", "qpub*g1": "-", "qpub*g4": "+"})


class Run(X9.Run):
    def __init__(self, seg):
        # not super().__init__: that would open (overwrite) the l09 log
        self.seg = seg; self.name = f"l10_school_{X9.BAND[seg]}"; self.EXP = X9.EXP_COL if seg == "col" else X9.EXP_K12
        self.logf = open(f"{HERE}/{self.name}.log", "w"); self.rows, self.coefs = [], []
        self.designs = {}; self.D = self.design(); self.N = self.D.N
        self.log(f"{self.name}: estimation half, {self.N} students, {len(self.D.alts)} zones with enrolment (full choice set)")

    def block(self, code, alts, cur):
        """alts: (step, label, add, var, xs[, gfix]); a 6th element overrides the size weights fixed at 0"""
        res = []
        for a in alts:
            sc, lab, add, var, xs = a[:5]; gf = a[5] if len(a) > 5 else cur["gfix"]
            v = dict(cur["var"]); v.update(var or {})
            self.log(f"  expected signs {sc}: " + ", ".join(f"{k} {self.EXP.get(k, '?')}" for k in add) + f"; fixed size weights {gf}")
            r = self.fit(sc, lab, cur["spec"] + add, cur["x"], gf, v)
            if r is None: continue
            lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; b = self.bad(r, add)
            if b: self.log(f"    unexpected sign: {b}")
            p = float(chi2.sf(lr, df)) if df > 0 else np.nan
            d = "not kept: LR" if not p < 0.05 else "not kept: BIC" if r["BIC"] >= cur["BIC"] else "not kept: sign" if b else "pass"
            res.append((r, d))
        passing = [r for r, d in res if d == "pass"]; best = min(passing, key=lambda r: r["BIC"]) if passing else None
        for r, d in res: self.row(r, cur, (("chosen" if r is best else "not chosen: BIC") if len(alts) > 1 else "kept") if d == "pass" else d)
        if best is None: return cur, res
        for k in best["spec"]:
            if k not in cur["spec"]: self.sgn[X9.pn(k)] = np.sign(best["x"][X9.pn(k)])
        return best, res

    def collin(self, r, new):
        D = self.design("estimation", **r["var"]); t, si, sabs = S.split(r["spec"]); M = r["M"]
        av = D.av; cols, data = [], []
        for k in t: cols.append(k); data.append(D.X(k)[av])
        for i, c in enumerate(D.comps):
            if c in ("pub_in",) and not sabs: continue
            if c in r["gfix"]: continue
            cols.append(f"ln N_{c}"); data.append(np.log1p(D.NK[i][av]))
        Z = np.stack(data, 1).astype(float); keep = Z.std(0) > 0; Z, cols = Z[:, keep], [c for c, k in zip(cols, keep) if k]
        Cm = np.corrcoef(Z, rowvar=False); vif = np.diag(np.linalg.inv(Cm))
        out = pd.DataFrame(Cm, index=cols, columns=cols); out["VIF"] = vif; out.to_csv(f"{HERE}/{self.name}_collin.csv")
        self.log(f"  collinearity of the final model's attributes ({av.sum()} available row x zone pairs): max VIF {vif.max():.2f} ({cols[int(np.argmax(vif))]})")
        for k in [c for c in cols if c in new]:
            o = out[k].drop(k).abs(); j = o.idxmax()
            self.log(f"     {k:10s} VIF {out.loc[k, 'VIF']:.2f}; largest |corr| {o[j]:.3f} with {j}")

    def go(self):
        seg = self.seg; col = seg == "col"
        L7 = {"k8": ["t", "lt", "intra", "ccpub", "size:in", "t*car0", "t*carlow"], "hs": ["t", "ccpub", "size:in"], "col": ["t", "lt", "cc", "cs", "t*g1", "t*g4"]}[seg]
        ref = self.fit("R", "l07 final model (reference)", L7, None, (), {}); self.row(ref, None, "reference (l07 final)")
        self.sgn = {X9.pn(k): np.sign(ref["x"][X9.pn(k)]) for k in ref["spec"]}
        if seg == "k8":
            cur = self.fit("0", "Cleanup: without car time x fewer cars than drivers (user rule)", [k for k in L7 if k != "t*carlow"], ref["x"])
            d = self.row(cur, ref, "cleanup (user rule)")
        elif seg == "hs":
            cur = self.fit("0", "Cleanup: private log weight fixed at 0", L7, ref["x"], ("priv",)); d = self.row(cur, ref, "cleanup (fixed)")
        else:
            r = self.fit("0", "Cleanup test: without car time x income < $40k", [k for k in L7 if k != "t*g1"], ref["x"])
            kd = r["BIC"] < ref["BIC"]; d = self.row(r, ref, "dropped (BIC falls)" if kd else "not dropped (BIC rises)"); cur = r if kd else ref
        d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"])))
        clean = cur; new = []
        if not col:
            cur, _ = self.block("4", [("4", "Charter-or-magnet share of the zone's enrolment", ["cm"], None, None)], cur)
            pre2 = cur
            alts = [("2", "Quality on the public part (centred) + share of public enrolment without a score", ["qpub", "qnone"], None, None)]
            if seg == "hs": alts = [(a[0] + "-fix", a[1] + "; g_priv fixed at 0", *a[2:], ("priv",)) for a in alts] + [(a[0] + "-free", a[1] + "; g_priv free", *a[2:], ()) for a in alts]
            cur, res2 = self.block("2", alts, cur)
            for rr, _ in res2:
                self.compare(pre2, rr, f"quality {rr['step']}")
                self.log(f"    g_priv in {rr['step']}: " + (f"{rr['x']['g_priv']:.3f} (s.e. {rr['se']['g_priv']:.3f})" if "g_priv" in rr["x"] else "fixed at 0"))
            if cur is not pre2:
                cur, _ = self.block("2i", [("2i-a", "Quality x income < $40k", ["qpub*g1"], None, None), ("2i-b", "Quality x income >= $125k", ["qpub*g4"], None, None)], cur)
        pre1 = cur
        cur, res1 = self.block("1", [("1", "Own-race share of the zone's enrolment of the band (unknown race -> 0)", ["own"], None, None)], cur)
        if res1: self.compare(pre1, res1[0][0], "own-race share")
        nf = 0
        while True:
            off = [(abs(cur["t"][X9.pn(k)]), k) for k in cur["spec"] if X9.pn(k) in self.sgn and np.sign(cur["x"][X9.pn(k)]) != self.sgn[X9.pn(k)] and abs(cur["t"][X9.pn(k)]) < 1.96]
            if not off: break
            _, k = min(off); nf += 1
            r = self.fit(f"F{nf}", f"Final check: without {k}", [x for x in cur["spec"] if x != k], cur["x"], cur["gfix"], cur["var"])
            d = self.row(r, cur, "dropped: sign reversed, not significant"); d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"]))); cur = r
        new = [k for k in cur["spec"] if k not in L7]
        self.collin(cur, new + ["ln N_priv"] if seg == "k8" else new)
        out = [("final", "final model", cur), ("cleanup", "cleanup model (step 0, no new terms)", clean)]
        if "own" in cur["spec"]: out.insert(1, ("final_no_race", "final model without race (before block 1)", pre1))
        for code, lab, r in out:
            v, n = self.vll(r); d = self.row(r, None, code); d.update(step=code, label=lab, validation_LL=v, spec=" ".join(r["spec"]), gfix=",".join(r["gfix"]), var=str(r["var"]))
            for c in [c for c in self.coefs if c["step"] == r["step"]]: self.coefs.append(dict(c, step=code))
            self.log(f"{code}: {r['spec']} gfix {r['gfix']}, K {r['K']} LL {r['LL']:.2f} BIC {r['BIC']:.1f}; validation LL {v:.2f} ({v / n:.4f} per student, N {n})")
        fc = pd.DataFrame({"parameter": list(cur["x"]), "value": list(cur["x"].values())})
        for g in cur["gfix"]: fc = pd.concat([fc, pd.DataFrame({"parameter": [f"g_{g}"], "value": [0.0]})])
        fc.to_csv(f"{HERE}/{self.name}_final_coef.csv", index=False)
        cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL", "spec", "gfix", "var"]
        pd.DataFrame(self.rows).reindex(columns=cols).to_csv(f"{HERE}/{self.name}_fit.csv", index=False)
        pd.DataFrame(self.coefs).to_csv(f"{HERE}/{self.name}_coef.csv", index=False)


if __name__ == "__main__":
    for s in sys.argv[1:]: Run(s).go()
