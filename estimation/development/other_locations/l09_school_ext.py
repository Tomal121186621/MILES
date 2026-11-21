#!/usr/bin/env python3
"""School location choice (K-8, high school, college): tests of new variables on top of the l07 final models (test only).

Engine, data, estimation half and full choice set of l07_school.py / 2_silo/schoolchoice (imported; nothing edited).  New zone
variables from l09_school_data.py (l09_zone_attr.parquet, l09_student_race.parquet).  Engine extensions are subclasses here:
  Design2  new utility bases: own (own-race share of the zone's enrolment of the student's band; unknown race -> 0),
           qual (enrolment-weighted mean % proficient of the band's Maryland public schools in the zone, per 10 points; 0 if none),
           qmiss (zone has no school with a quality value), charter / magnet / cm (charter, magnet, charter-or-magnet share of
           the zone's enrolment of the band);  variants: City homes without in-boundary enrolment (high school), college size
           from commuting enrolment (enrolment - dormitory capacity) or with a separate resident (dormitory) component 'res'.
  Model2   size weights fixed at 0 (gfix), size interaction with a home-zone variable (pub_in:city, home in Baltimore City).
Block order 0, 3, 4, 5, 2, 1 (race last).  Rule of l07: LR 5 %, BIC falls, expected sign (stated before estimation, EXP).
Lettered alternatives are evaluated against the same current model; among passing ones the lower BIC is chosen.  Alternatives
with the same K as the current model (non-nested: City in-boundary 0, commuting enrolment) are kept when BIC falls.
Validation half used once at the end: final model, cleanup model (step 0), final model without race (and, as asked, the
step-5 college size alternatives, reported only).
    python3 l09_school_ext.py k8|hs|col   ->  l09_school_<band>_fit.csv, _coef.csv, .log"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, time
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
from scipy.stats import chi2, norm
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/locations"   # HERE: results of this step (data); CODE: this folder
SCD = (f"{WORKSPACE}/2_silo/schoolchoice")
sys.path.insert(0, SCD)
import sc_03_engine as G      # noqa: E402
import sc_common as SC        # noqa: E402
import sc_04_stepwise as S    # noqa: E402

BAND = {"k8": "k8", "hs": "hs", "col": "college"}
CITY = 24510
ZA = pd.read_parquet(f"{HERE}/l09_zone_attr.parquet"); RACE = pd.read_parquet(f"{HERE}/l09_student_race.parquet").set_index("person_id").race
RC = ["white", "black", "hisp", "other"]
ZI = SC.zidx(); NZ = G.NZ


def zarr(band, col, fill=0.0):
    a = np.full(NZ, fill); g = ZA[ZA.band == band]; a[ZI[g.zone].values] = g[col].values; return a


ZV = {}
QV = os.environ.get("L09_Q", "both")   # "2b": sensitivity path, only the public-part quality variant offered in block 2
QMEAN = 3.83   # mean % proficient / 10 of the Maryland public school points (l09_data.log)
for b in ["elementary", "middle", "high", "postsec"]:
    n = zarr(b, "n"); nr = zarr(b, "n_race"); q = zarr(b, "qual", np.nan)
    ZV[b] = dict(own=np.stack([np.where(nr > 0, zarr(b, f"n_{c}") / np.maximum(nr, 1e-9), 0.0) for c in RC]),
                 qual=np.nan_to_num(q / 10.0), qmiss=np.isnan(q).astype(float),
                 charter=np.where(n > 0, zarr(b, "n_charter") / np.maximum(n, 1e-9), 0.0), magnet=np.where(n > 0, zarr(b, "n_magnet") / np.maximum(n, 1e-9), 0.0))
    ZV[b]["cm"] = np.minimum(ZV[b]["charter"] + ZV[b]["magnet"], 1.0)
    if b == "postsec":
        for c in ("pub4", "priv4", "cc"): ZV[b][f"commute_{c}"] = zarr(b, f"commute_{c}"); ZV[b][f"res_{c}"] = zarr(b, f"res_{c}")

_pvar = G.pvar
def pvar(name, P, rec):
    if name == "city": return np.zeros(len(rec))        # placeholder; Model2 replaces it by the row's home zone (home in Baltimore City)
    return _pvar(name, P, rec)
G.pvar = pvar


class Design2(G.Design):
    def __init__(self, seg, half="estimation", city_noin=False, dorm=None):
        super().__init__(seg, half, "full"); self.city_noin, self.dorm = city_noin, dorm
        self.P["race"] = self.P.person_id.map(RACE).fillna(-1).astype(int).values
        self.city_row = (G.CT[self.h] == CITY).astype(float)
        if city_noin:                                     # City homes: in-boundary enrolment counted as ordinary public enrolment
            m = self.city_row > 0; self.NK[0][m] += self.NK[1][m]; self.NK[1][m] = 0.0
        if dorm:
            A = self.A; V = ZV["postsec"]; com = [V[f"commute_{c}"][A].astype(np.float32) for c in ("pub4", "priv4", "cc")]
            if dorm == "commute": self.NK = np.stack(com)
            elif dorm == "split":
                self.NK = np.stack(com + [sum(V[f"res_{c}"][A] for c in ("pub4", "priv4", "cc")).astype(np.float32)]); self.comps = ["pub4", "priv4", "cc", "res"]
        self.cache = {}

    def base(self, name):
        if name in ("qualp", "qmissp"):                   # public part only: public share x (centred quality) / x no-value flag
            S_ = self.NK.sum(0); pubsh = np.where(S_ > 0, (self.NK[0] + self.NK[1]) / np.maximum(S_, 1e-9), 0).astype(np.float32)
            qm = self.base("qmiss"); q = self.base("qual")
            return pubsh * np.where(qm > 0, 0.0, q - QMEAN).astype(np.float32) if name == "qualp" else pubsh * qm
        if name in ("own", "qual", "qmiss", "charter", "magnet", "cm"):
            out = np.zeros(self.A.shape, np.float32); rb = self.band[self.rec]
            for b in G.BANDS[self.seg]:
                m = rb == b
                if not m.any(): continue
                if name == "own":
                    r = self.P.race.values[self.rec][m]; sh = ZV[b]["own"]; Am = self.A[m]; o = np.zeros(Am.shape, np.float32)
                    for k in range(4):
                        mk = r == k
                        if mk.any(): o[mk] = sh[k][Am[mk]]
                    out[m] = o
                else: out[m] = ZV[b][name][self.A[m]]
            return out
        return super().base(name)


class Model2(G.Model):
    def __init__(self, D, terms, size_inter=(), sabs=False, fixed=None, gfix=()):
        super().__init__(D, terms, size_inter, sabs, fixed)
        for j, s in enumerate(self.size_inter):
            if s.split(":")[1] == "city": self.SX[j] = D.city_row
        if gfix:
            keep = [i for i, c in enumerate(self.gfree) if c not in gfix]
            drop = {f"g_{c}" for c in self.gfree if c in gfix}
            self.gfree = [self.gfree[i] for i in keep]; self.gidx = [self.gidx[i] for i in keep]; self.ng = len(self.gfree)
            self.names = [n for n in self.names if n not in drop]


EXP_K12 = dict(S.K12, **{"own": "+", "qual": "+", "qmiss": "?", "qual*g4": "+", "qual*g1": "-", "charter": "+", "magnet": "+", "cm": "+", "pub_in:city": "-",
                                "qualp": "+", "qmissp": "?", "qualp*g4": "+", "qualp*g1": "-"})
EXP_COL = dict(S.COL, **{"own": "+"})
LAB = {"t": "car time", "lt": "log(1 + car time)", "intra": "same zone", "cc": "other county", "ccpub": "other county x public share", "cs": "other state",
       "size:in": "attendance-boundary public enrolment", "own": "own-race share of the zone's enrolment", "qual": "school quality (% proficient / 10)",
       "qmiss": "no quality value in the zone", "charter": "charter share", "magnet": "magnet share", "cm": "charter-or-magnet share"}


def pn(k):
    if k == "pub_in:city": return "h_pub_inXcity"
    return S.pname(k)


class Run:
    def __init__(self, seg):
        self.seg = seg; self.name = f"l09_school_{BAND[seg]}" + ("_q2b" if QV == "2b" else ""); self.EXP = EXP_COL if seg == "col" else EXP_K12
        self.logf = open(f"{HERE}/{self.name}.log", "w"); self.rows, self.coefs = [], []
        self.designs = {}; self.D = self.design(); self.N = self.D.N
        self.log(f"{self.name}: estimation half, {self.N} students, {len(self.D.alts)} zones with enrolment (full choice set)")

    def design(self, half="estimation", city_noin=False, dorm=None):
        k = (half, city_noin, dorm)
        if k not in self.designs: self.designs[k] = Design2(self.seg, half, city_noin, dorm)
        return self.designs[k]

    def log(self, s):
        print(s, flush=True); self.logf.write(s + "\n"); self.logf.flush()

    def fit(self, step, lab, spec, start=None, gfix=(), var=None):
        var = dict(var or {}); D = self.design("estimation", **var); t, si, sabs = S.split(spec); M = Model2(D, t, si, sabs, None, gfix)
        if D.N != self.N: raise RuntimeError("sample changed")
        try:
            M = S.Search.converge(None, M, None if start is None else M.at(start)); M.robust()
        except Exception as e:
            self.log(f"  {step} {lab}: no converged fit ({e})"); return None
        tb = M.table(); K = len(M.th)
        r = dict(step=step, label=lab, spec=list(spec), gfix=tuple(gfix), var=var, K=K, LL=M.ll, BIC=K * np.log(self.N) - 2 * M.ll, M=M,
                 x=M.coef_dict(), t=dict(zip(tb.parameter, tb.robust_t)), se=dict(zip(tb.parameter, tb.robust_se)))
        for q in tb.itertuples(): self.coefs.append(dict(step=step, param=q.parameter, coef=q.estimate, se=q.robust_se, t=q.robust_t, p=2 * norm.sf(abs(q.robust_t))))
        self.log(f"  {step} {lab}: K {K} LL {M.ll:.2f} BIC {r['BIC']:.1f} max |score sum| {M.max_grad:.2g}  [{', '.join(f'{n} {v:.3f} ({r['t'][n]:.1f})' for n, v in r['x'].items())}]")
        return r

    def row(self, r, cur=None, decision=""):
        d = dict(step=r["step"], label=r["label"], K=r["K"], LL=r["LL"], BIC=r["BIC"], LR=np.nan, df=np.nan, p=np.nan, decision=decision)
        if cur is not None:
            lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; d.update(LR=lr, df=df, p=float(chi2.sf(lr, df)) if df > 0 else np.nan)
        self.rows.append(d); return d

    def bad(self, r, terms):
        out = []
        for k in terms:
            e = self.EXP.get(k, "?"); v = r["x"][pn(k)]
            if (e == "+" and v <= 0) or (e == "-" and v >= 0): out.append(k)
        return out

    def block(self, code, alts, cur):
        """alts: (step, label, add_terms, var_change, extra_sign_checks {param: '+'/'-'}); returns the new current model"""
        res = []
        for sc, lab, add, var, xs in alts:
            v = dict(cur["var"]); v.update(var or {})
            self.log(f"  expected signs {sc}: " + ", ".join(f"{k} {self.EXP.get(k, '?')}" for k in add) + "".join(f", {k} {e}" for k, e in (xs or {}).items()))
            r = self.fit(sc, lab, cur["spec"] + add, cur["x"], cur["gfix"], v)
            if r is None: continue
            lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]
            b = self.bad(r, add) + [k for k, e in (xs or {}).items() if (e == "+" and r["x"][k] <= 0) or (e == "-" and r["x"][k] >= 0)]
            if b: self.log(f"    unexpected sign: {b}")
            if df > 0:
                p = float(chi2.sf(lr, df)); d = "not kept: LR" if not p < 0.05 else "not kept: BIC" if r["BIC"] >= cur["BIC"] else "not kept: sign" if b else "pass"
            else:
                d = "not kept: BIC" if r["BIC"] >= cur["BIC"] else "not kept: sign" if b else "pass"
            res.append((r, d))
        passing = [r for r, d in res if d == "pass"]; best = min(passing, key=lambda r: r["BIC"]) if passing else None
        for r, d in res: self.row(r, cur, (("chosen" if r is best else "not chosen: BIC") if len(alts) > 1 else "kept") if d == "pass" else d)
        if best is not None:
            for k in best["spec"]:
                if k not in cur["spec"]: self.sgn[pn(k)] = np.sign(best["x"][pn(k)])
            return best, res
        return cur, res

    def compare(self, a, b, title):
        ks = [k for k in a["x"] if k in b["x"]]
        self.log(f"  {title}: coefficient change ({a['step']} -> {b['step']}), in robust s.e. of the first")
        for k in ks: self.log(f"     {k:18s} {a['x'][k]:9.4f} -> {b['x'][k]:9.4f}  ({(b['x'][k] - a['x'][k]) / a['se'][k]:+.2f} s.e.)")

    def vll(self, r):
        D = self.design("validation", **r["var"]); t, si, sabs = S.split(r["spec"]); MF = Model2(D, t, si, sabs, None, r["gfix"])
        return float(MF.scores(r["M"].th)[0].sum()), D.N

    def go(self):
        t0 = time.time(); seg = self.seg; col = seg == "col"
        L7 = {"k8": ["t", "lt", "intra", "ccpub", "size:in", "t*car0", "t*carlow"], "hs": ["t", "ccpub", "size:in"], "col": ["t", "lt", "cc", "cs", "t*g1", "t*g4"]}[seg]
        ref = self.fit("R", "l07 final model (reference)", L7, None, (), {}); self.row(ref, None, "reference (l07 final)")
        self.sgn = {pn(k): np.sign(ref["x"][pn(k)]) for k in ref["spec"]}
        # ---- 0 cleanups
        if seg == "k8":
            cur = self.fit("0", "Cleanup: without car time x fewer cars than drivers (user rule)", [k for k in L7 if k != "t*carlow"], ref["x"])
            d = self.row(cur, ref, "cleanup (user rule)"); d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"])))
        elif seg == "hs":
            cur = self.fit("0", "Cleanup: private log weight fixed at 0", L7, ref["x"], ("priv",))
            d = self.row(cur, ref, "cleanup (fixed)"); d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"])))
        else:
            r = self.fit("0", "Cleanup test: without car time x income < $40k", [k for k in L7 if k != "t*g1"], ref["x"])
            keep_drop = r["BIC"] < ref["BIC"]; d = self.row(r, ref, "dropped (BIC falls)" if keep_drop else "not dropped (BIC rises)")
            d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"]))); cur = r if keep_drop else ref
        clean = cur
        # ---- 3 Baltimore City high-school choice
        if seg == "hs":
            cur, _ = self.block("3", [("3a", "In-boundary log weight x home in Baltimore City", ["pub_in:city"], None, None),
                                      ("3b", "In-boundary enrolment set to 0 for Baltimore City homes", [], {"city_noin": True}, None)], cur)
        # ---- 4 charter / magnet share (K-12)
        if not col:
            cur, _ = self.block("4", [("4a", "Charter share and magnet share of the zone's enrolment", ["charter", "magnet"], None, None),
                                      ("4b", "Charter-or-magnet share of the zone's enrolment", ["cm"], None, None)], cur)
        # ---- 5 dormitory students (college)
        if col:
            pre5 = cur
            cur, res5 = self.block("5", [("5a", "Size from commuting enrolment (enrolment - dormitory capacity)", [], {"dorm": "commute"}, None),
                                         ("5b", "Separate size component for the dormitory part (log weight estimated)", [], {"dorm": "split"}, {"g_res": "-"})], cur)
            self.v5 = [(pre5["step"], "total enrolment (current)", *self.vll(pre5))] + [(r["step"], r["label"], *self.vll(r)) for r, _ in res5]
            for s_, l_, v_, n_ in self.v5: self.log(f"    validation LL (step-5 comparison, reported only): {s_} {l_}: {v_:.2f}")
        # ---- 2 school quality (K-12)
        if not col:
            pre2 = cur
            cur, res2 = self.block("2", [("2a", "School quality (% proficient) of the zone + no-value indicator (zone level)", ["qual", "qmiss"], None, None)][QV == "2b":] + [
                                         ("2b", "Public part: public share x (quality - MD mean) + public share x no-value indicator", ["qualp", "qmissp"], None, None)], cur)
            for rr, _ in res2: self.compare(pre2, rr, f"quality main effect {rr['step']}")
            if cur is not pre2:
                qk = "qualp" if "qualp" in cur["spec"] else "qual"
                cur, _ = self.block("2i", [("2i-a", "Quality x income >= $125k", [f"{qk}*g4"], None, None), ("2i-b", "Quality x income < $40k", [f"{qk}*g1"], None, None)], cur)
            self.quality_diag(res2[0][0] if res2 else pre2)
        # ---- 1 race
        pre1 = cur
        cur, res1 = self.block("1", [("1", "Own-race share of the zone's enrolment of the band (unknown race -> 0)", ["own"], None, None)], cur)
        if res1: self.compare(pre1, res1[0][0], "own-race share")
        # ---- final check: sign reversed and not significant -> drop (l07 rule)
        nf = 0
        while True:
            off = [(abs(cur["t"][pn(k)]), k) for k in cur["spec"] if pn(k) in self.sgn and np.sign(cur["x"][pn(k)]) != self.sgn[pn(k)] and abs(cur["t"][pn(k)]) < 1.96]
            if not off: break
            _, k = min(off); nf += 1
            r = self.fit(f"F{nf}", f"Final check: without {k}", [x for x in cur["spec"] if x != k], cur["x"], cur["gfix"], cur["var"])
            d = self.row(r, cur, "dropped: sign reversed, not significant"); d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"]))); cur = r
        # ---- validation half, once
        out = [("final", "final model", cur), ("cleanup", "cleanup model (step 0, no new terms)", clean)]
        if "own" in cur["spec"]: out.append(("final_no_race", "final model without race (before block 1)", pre1))
        else: self.log("  race not kept: the final model is the no-race model")
        for code, lab, r in out:
            v, n = self.vll(r); d = self.row(r, None, code); d.update(step=code, label=lab, validation_LL=v, spec=" ".join(r["spec"]), gfix=",".join(r["gfix"]), var=str(r["var"]))
            for c in [c for c in self.coefs if c["step"] == r["step"]]: self.coefs.append(dict(c, step=code))
            self.log(f"{code}: {r['spec']} gfix {r['gfix']} var {r['var']}, K {r['K']} LL {r['LL']:.2f} BIC {r['BIC']:.1f}; validation LL {v:.2f} ({v / n:.4f} per student, N {n})")
        if col and hasattr(self, "v5"):
            for s_, l_, v_, n_ in self.v5: self.rows.append(dict(step=f"v5:{s_}", label=f"step-5 validation (reported only): {l_}", validation_LL=v_))
        self.log(f"{time.time() - t0:.0f} s")
        cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL", "spec", "gfix", "var"]
        pd.DataFrame(self.rows).reindex(columns=cols).to_csv(f"{HERE}/{self.name}_fit.csv", index=False)
        pd.DataFrame(self.coefs).to_csv(f"{HERE}/{self.name}_coef.csv", index=False)

    def quality_diag(self, r):
        """correlation of the zone quality with the in-boundary share of the alternative's public enrolment and with zone income,
        over (home row, available alternative) pairs of Maryland zones with a quality value (estimation half)"""
        D = self.design("estimation", **r["var"]); q = D.X("qual"); qm = D.X("qmiss"); av = D.av & (qm == 0) & (G.ST[D.A] == 24)
        tot = D.NK.sum(0); insh = np.where(tot > 0, D.NK[1] / np.maximum(tot, 1e-9), 0)
        hh = pd.read_csv(f"{SC.S}/input/microData/hh_2016.csv", usecols=["dwelling", "income"]); dd = pd.read_csv(f"{SC.S}/input/microData/dd_2016.csv", usecols=["id", "zone"])
        hh["zone"] = hh.dwelling.map(dd.set_index("id").zone); inc = hh.groupby("zone").income.mean().reindex(SC.zones().zone).fillna(0).values / 1000
        zq = q[av]; c1 = np.corrcoef(zq, insh[av])[0, 1]; c2 = np.corrcoef(zq, inc[D.A][av])[0, 1]
        ch = np.zeros(D.A.shape, bool); ch[np.arange(D.R)[:, None], D.cand] = np.isfinite(D.lwc)
        self.log(f"  quality diagnostics (MD alternatives with a value, {av.sum()} row x zone pairs): corr(quality, in-boundary share of the zone's enrolment "
                 f"from the home) {c1:.3f}; corr(quality, zone mean household income 2016) {c2:.3f}; corr at the zone level (MD zones of the band) "
                 + ", ".join(f"{b}: income {np.corrcoef(ZV[b]['qual'][ZV[b]['qmiss'] == 0], (inc)[ZV[b]['qmiss'] == 0])[0, 1]:.3f}" for b in G.BANDS[self.seg])
                 + f"; mean quality of chosen zones {np.average(q[ch & av]):.2f} vs all MD alternatives {zq.mean():.2f} (x10 % proficient)")


if __name__ == "__main__":
    for s in sys.argv[1:]: Run(s).go()
