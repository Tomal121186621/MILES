#!/usr/bin/env python3
"""Primary destination of the discretionary tours (shopping, recreation, accompanying, other): model development in a fixed
block order.

Models (multinomial logit over all 1,588 zones, full choice set, no sampling; records, location mixture over the possible zones
of the destination and of home, chunked likelihood, optimiser bounds and robust sandwich covariance of
activity/lib/tasha_estimation/estimate_fullset_taz.py, imported):
  d_shop  SHOPPING_primary      d_rec  RECREATION_primary      d_acc  ACCOMPANY_primary      d_oth  OTHER_primary
Estimation half of the RTS for every selection step; the validation half is used once, at the end, for the final model and the
current (article) specification, the latter re-estimated with the same estimator on the same estimation records.

Block order (fixed before estimation; "distance" = car distance from home, km; ln distance = ln of it):
   1   size term mu ln(1 + S_j), S_j = sum_c exp(theta_c) x_jc over population, retail, office, other jobs, school enrolment,
       with linear distance.  Base component = the one with the largest weight in this model; components whose weight runs
       to zero (theta < ln 1e-4) are removed (not identified).
   2   distance form: 2a piecewise-linear distance (knots 1, 2, 5, 10, 20, 50 km) in place of the linear term,
       2b linear + log distance
   3   intrazonal (destination = home zone)
   4   Baltimore City, Washington DC, central business districts (>= 10,000 jobs per km2)
   5   Virginia; Delaware / Pennsylvania / West Virginia
   6   retail density ln(1 + retail jobs per km2), land-use mix (entropy)
   7   outside the home county
   8   outside the home state
   9   ln distance x household income (< $50k, >= $100k)
  10   ln distance x car availability (no car, fewer cars than drivers)
  11   ln distance x person under 18, person 65+, household with children
  12   ln distance x worker
  13   ln distance x male, ln distance x one-person household
  14   ln distance x time of day of the arrival (AM 6-9, PM 15-19, evening 19-6)
  15   ln distance x tour with at least one stop
  16   impedance: 16a car generalised time (time + cost / value of time), 16b mode-choice logsum (MAST mode model), 16c both
  17   bus within 120 min of home x household without a car (original S10)
Identification guards, fixed before estimation: a person / time-of-day / tour flag enters only if at least 20 records have it
and 20 do not; a zone dummy or boundary term only if at least 5 observed destinations (survey traffic zone) have it.

Rule: a block is KEPT when the LR test against the current model is significant at 5 %, BIC falls, every sign-checked term has
its expected sign (SIGN) and no estimate sits at an optimiser bound; otherwise "not kept: LR" / "not kept: BIC" /
"not kept: sign" / "not kept: estimate at bound".  Lettered alternatives of one step are evaluated against the same current
model; among those that pass, the lowest BIC is "chosen", the others "not chosen: BIC".
Final check: a kept linear term whose sign reversed after later blocks and that is no longer significant (|robust t| < 1.96)
is dropped (weakest first, one step each, LR of dropping it reported).  No other backward elimination.
    TAZ_THREADS=4 python3 estimation/development/primary_destination/d_primary.py d_shop [d_rec ...]
Outputs <name>_fit.csv, <name>_coef.csv, <name>.log in ESTIMATION_RESULTS/dest_primary."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, time
sys.dont_write_bytecode = True
os.environ.setdefault("TAZ_THREADS", "4")
import numpy as np, pandas as pd
from scipy.stats import chi2

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/dest_primary"   # results of this step (data); CODE = this folder
TE = f"{WORKSPACE}/3_abit/tasha_estimation"                     # data (work/, results/)
sys.path.insert(0, f"{MILES_HOME}/activity/lib/tasha_estimation")
import estimate_fullset_taz as FS       # noqa: E402  (chunked full-set mixture likelihood, records, current specification)
import dc_taz_engine as X               # noqa: E402
import dc_model as M                    # noqa: E402
import dc_common as C                   # noqa: E402
import torch                            # noqa: E402
from torch.func import jvp              # noqa: E402
from scipy.optimize import minimize     # noqa: E402

MODELS = {"d_shop": "SHOPPING", "d_rec": "RECREATION", "d_acc": "ACCOMPANY", "d_oth": "OTHER"}
COMPS = ["pop", "ret", "off", "oth", "stu"]
B0 = {"SHOPPING": "ret", "RECREATION": "pop", "ACCOMPANY": "pop", "OTHER": "pop"}   # starting base (estimate_dc.SIZE_BASE)
SIGN = {"d": -1, "lnd": -1, "xcounty": -1, "xstate": -1, "cgt": -1, "ls": 1, "intra": None,
        "inc0": -1, "inc2": 1, "car0": -1, "car1": -1, "kid": -1, "senior": -1, "child": -1, "multi": 1}
LAB = {"d": "linear distance", "lnd": "log distance", "intra": "intrazonal", "bc": "Baltimore City", "dcz": "Washington DC",
       "cbd": "central business district", "va": "Virginia", "othst": "Delaware, Pennsylvania, West Virginia", "lnretden": "retail density",
       "mix": "land-use mix", "xcounty": "outside the home county", "xstate": "outside the home state", "cgt": "car generalised time",
       "ls": "mode-choice logsum", "ptav_car0": "bus within 120 min x no car", "inc0": "income below $50k", "inc2": "income $100k or more",
       "car0": "no car", "car1": "fewer cars than drivers", "kid": "person under 18", "senior": "person 65 or older",
       "child": "household with children", "worker": "worker", "male": "male", "hh1": "one-person household", "am": "AM peak",
       "pm": "PM peak", "ev": "evening", "multi": "tour with stops"}
FLAGS = ["inc0", "inc2", "car0", "car1", "kid", "senior", "child", "worker", "male", "hh1", "am", "pm", "ev", "multi"]
BOUNDS = lambda p: (-30.0, 15.0) if p.startswith("theta_") else (0.0, 3.0) if p == "mu_size" else (None, None)

# ---- two person / household flags that dc_model.chooser does not have (male, one-person household): added here
_feat = M.features


def features_d(rec, alts, names, sk, purpose):
    new = [n for n in names if n in ("lnd_male", "lnd_hh1")]
    rest = [n for n in names if n not in new]
    out = dict(_feat(rec, alts, rest, sk, purpose)) if rest else {}
    if new:
        lnd = np.log(M.impedance(rec, alts, sk))
        fl = {"lnd_male": rec.male.values.astype(float), "lnd_hh1": (rec.hhsize.values == 1).astype(float)}
        for n in new: out[n] = lnd * fl[n][:, None]
    return {k: out[k] for k in names}


M.features = features_d


def flag_values(rec):
    ch = M.chooser(rec); ch["male"] = rec.male.values.astype(float); ch["hh1"] = (rec.hhsize.values == 1).astype(float)
    return ch


def label(p):
    if p.startswith("d_"):
        _, lo, hi = p.split("_"); return f"distance {lo}-{hi} km".replace("-inf km", " km and more")
    if p.startswith("lnd_"): return f"log distance x {LAB[p[4:]]}"
    return LAB.get(p, p)


def sign_of(p):
    return SIGN.get(p[4:]) if p.startswith("lnd_") else SIGN.get(p)


class Run:
    def __init__(self, name):
        self.name = name; self.pur = MODELS[name]; self.seg = f"{self.pur}_primary"; self.sk = C.skims(); self.rows, self.coefs = [], []
        self.logf = open(f"{HERE}/{name}.log", "w"); self._d = {}

    def log(self, s):
        print(s, flush=True); self.logf.write(s + "\n"); self.logf.flush()

    def data(self, half):
        if half not in self._d: self._d[half] = FS.load(self.seg, half)       # records with the tour-with-stops flag
        return self._d[half]

    # ---------------------------------------------------------------- one model (full set, mixture, robust covariance)
    def estimate(self, spec, x0):
        rec, cand, cfg = self.data("estimation"); names = spec.params()
        chunks = [FS.Chunk(rec.iloc[i:i + FS.CHUNK], cand[cand.rec.isin(rec.rec.values[i:i + FS.CHUNK])], cfg, spec, self.pur, self.sk)
                  for i in range(0, len(rec), FS.CHUNK)]
        bounds = [BOUNDS(p) for p in names]
        x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bounds)])
        def fg(v):
            t = torch.tensor(v, requires_grad=True); tot = 0.0
            for c in chunks:
                l = -c.ll(t, spec).sum(); l.backward(); tot += float(l)
            if not np.isfinite(tot): return 1e15, np.zeros_like(v)
            return tot, t.grad.numpy().copy()
        r = minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bounds, options=dict(maxiter=3000, maxfun=12000, ftol=1e-13, gtol=1e-6, maxcor=30))
        x = torch.tensor(r.x); K = len(x); H = torch.zeros((K, K)); G = []
        for c in chunks:
            H += torch.autograd.functional.hessian(lambda t: c.ll(t, spec).sum(), x)
            G.append(torch.stack([jvp(lambda t: c.ll(t, spec), (x,), (e,))[1] for e in torch.eye(K)], 1))
        G = torch.cat(G); g = G.sum(0)
        at_bound = [p for p, v, (lo, hi) in zip(names, r.x, bounds) if (lo is not None and v <= lo + 1e-6) or (hi is not None and v >= hi - 1e-6)]
        free = torch.tensor([p not in at_bound for p in names]); cov = torch.full((K, K), float("nan"))
        Hi = torch.linalg.inv(-H[free][:, free]); Gf = G[:, free]; fi = torch.where(free)[0]; cf = Hi @ (Gf.T @ Gf) @ Hi
        for a, ia in enumerate(fi): cov[ia, fi] = cf[a]
        se = torch.sqrt(torch.clamp(torch.diag(cov), min=0))
        tab = pd.DataFrame({"param": names, "value": x.numpy(), "rob_se": se.numpy(), "rob_t": (x / se).numpy()})
        return tab, -float(r.fun), bool(r.success), float(g.abs().max()), at_bound, len(rec)

    def fit(self, step, lab, spec, x0=None):
        names = spec.params(); sv = dict(zip(names, M.start_values(spec).numpy()))
        x0 = np.array([(x0 or {}).get(p, sv[p]) for p in names])
        try:
            t, LL, conv, mg, ab, N = self.estimate(spec, x0)
        except Exception as e:                                           # singular Hessian: not identified
            self.log(f"  {step}: estimation failed ({e})"); return None
        r = dict(step=step, label=lab, spec=spec, K=len(names), LL=LL, N=N, table=t, converged=conv, maxgrad=mg, at_bound=" ".join(ab))
        r["BIC"] = np.log(N) * r["K"] - 2 * LL; r["x"] = dict(zip(t.param, t.value))
        for q in t.itertuples(): self.coefs.append(dict(step=step, param=q.param, coef=q.value, se=q.rob_se, t=q.rob_t))
        self.log(f"  {step} {lab}: K {r['K']} LL {LL:.2f} BIC {r['BIC']:.1f} converged {conv} maxgrad {mg:.1e}"
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
    def base(self):
        b0 = B0[self.pur]; base, comps = b0, [c for c in COMPS if c != b0]; r = None
        for _ in range(4):
            spec = M.Spec("1", ["d"], base, comps); r = self.fit("1", "Size term and linear distance", spec, r["x"] if r else None)
            w = {base: 1.0, **{c: float(np.exp(r["x"][f"theta_{c}"])) for c in comps}}
            nb = max(w, key=w.get); keep = [c for c in w if c != nb and w[c] / w[nb] > 1e-4]
            if nb == base and keep == comps: break
            self.log(f"  size term: base {nb}, components {keep} (weights relative to {base}: { {k: round(v, 5) for k, v in w.items()} })")
            self.coefs = [c for c in self.coefs if c["step"] != "1"]
            x = {"d": r["x"]["d"], "mu_size": r["x"]["mu_size"]}
            x.update({f"theta_{c}": float(np.log(w[c] / w[nb])) for c in keep})
            base, comps = nb, keep; r = dict(x=x)
        return r

    # ---------------------------------------------------------------- data guards
    def guards(self):
        rec, _, _ = self.data("estimation"); ch = flag_values(rec); z = C.zones(); j = rec.dzone_taz.values.astype(int); a = rec.h_taz.values.astype(int)
        flags = [k for k in FLAGS if 20 <= ch[k].sum() <= len(rec) - 20]
        cnt = {k: int(z[k].values[j].sum()) for k in ["bc", "dcz", "cbd", "va", "othst"]}
        cty, st = z.countyfips.values, z.state.values
        cnt.update(xcounty=int((cty[j] != cty[a]).sum()), xstate=int((st[j] != st[a]).sum()), intra=int((j == a).sum()))
        zone_ok = {k for k, v in cnt.items() if v >= 5}
        self.log(f"  flags with >= 20 records each way: {flags}; observed destinations per zone term (survey zone): {cnt}")
        return flags, zone_ok

    # ---------------------------------------------------------------- sequence
    def go(self):
        t0 = time.time(); self.log(f"{self.name} ({self.seg}), estimation half, full choice set, location mixture")
        cur = self.base(); self.row(cur, None, "base")
        pieces = C.pw_names("d", C.KNOTS); flags, zone_ok = self.guards()
        steps = [("2", [("2a", "Piecewise-linear distance", pieces, ["d"]), ("2b", "Linear and log distance", ["lnd"], [])]),
                 ("3", [("3", "Intrazonal", ["intra"], [])]),
                 ("4", [("4", "Baltimore City, Washington DC, central business districts", ["bc", "dcz", "cbd"], [])]),
                 ("5", [("5", "Virginia; Delaware, Pennsylvania, West Virginia", ["va", "othst"], [])]),
                 ("6", [("6", "Retail density and land-use mix", ["lnretden", "mix"], [])]),
                 ("7", [("7", "Outside the home county", ["xcounty"], [])]),
                 ("8", [("8", "Outside the home state", ["xstate"], [])]),
                 ("9", [("9", "Log distance x household income", ["lnd_inc0", "lnd_inc2"], [])]),
                 ("10", [("10", "Log distance x car availability", ["lnd_car0", "lnd_car1"], [])]),
                 ("11", [("11", "Log distance x age and children", ["lnd_kid", "lnd_senior", "lnd_child"], [])]),
                 ("12", [("12", "Log distance x worker", ["lnd_worker"], [])]),
                 ("13", [("13", "Log distance x gender and household size", ["lnd_male", "lnd_hh1"], [])]),
                 ("14", [("14", "Log distance x time of day", ["lnd_am", "lnd_pm", "lnd_ev"], [])]),
                 ("15", [("15", "Log distance x tour with stops", ["lnd_multi"], [])]),
                 ("16", [("16a", "Car generalised time", ["cgt"], []), ("16b", "Mode-choice logsum", ["ls"], []),
                         ("16c", "Car generalised time and mode-choice logsum", ["cgt", "ls"], [])]),
                 ("17", [("17", "Bus within 120 min x no car", ["ptav_car0"], [])])]
        zone_terms = {"intra", "bc", "dcz", "cbd", "va", "othst", "xcounty", "xstate"}
        kept_sign = {p: np.sign(v) for p, v in cur["x"].items()}
        for code, alts in steps:
            res = []
            for sc, lab, add, rem in alts:
                add2 = [p for p in add if not (p in zone_terms and p not in zone_ok)
                        and not (p.startswith("lnd_") and p[4:] not in flags) and not (p == "ptav_car0" and "car0" not in flags)]
                if len(add2) < len(add): self.log(f"  {sc}: without {[p for p in add if p not in add2]} (identification guard)")
                if not add2: continue
                if len(add2) < len(add) and len(alts) == 1:
                    lab = ", ".join(label(p) for p in add2); lab = lab[0].upper() + lab[1:]
                lin = [p for p in cur["spec"].linear if p not in rem] + add2
                spec = M.Spec(sc, lin, cur["spec"].size_base, cur["spec"].size_comps)
                r = self.fit(sc, lab, spec, cur["x"])
                if r is None: continue
                lr = 2 * (r["LL"] - cur["LL"]); df = r["K"] - cur["K"]; p = float(chi2.sf(lr, df)) if df > 0 else np.nan
                bad = self.bad_signs(r, add2)
                dec = ("not kept: estimate at bound" if r["at_bound"] else "not kept: LR" if not (p < 0.05) else
                       "not kept: BIC" if r["BIC"] >= cur["BIC"] else "not kept: sign" if bad else "pass")
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
        # ---- final check: sign reversed since kept and no longer significant
        while True:
            t = cur["table"].set_index("param")
            off = [(abs(t.rob_t[p]), p) for p in cur["spec"].linear if p in kept_sign and np.sign(t.value[p]) != kept_sign[p] and abs(t.rob_t[p]) < 1.96]
            if not off: break
            _, p = min(off); sc = f"F{sum(1 for r in self.rows if r['step'].startswith('F')) + 1}"
            spec = M.Spec(sc, [q for q in cur["spec"].linear if q != p], cur["spec"].size_base, cur["spec"].size_comps)
            r = self.fit(sc, f"Final check: without {label(p)}", spec, cur["x"])
            d = self.row(r, cur, "dropped: sign reversed, not significant"); cur = r
            d.update(LR=-d["LR"], df=-d["df"], p=float(chi2.sf(-d["LR"], -d["df"])))   # LR of dropping the term
            self.log(f"    dropped {p} (LR of dropping {d['LR']:.2f}, {int(d['df'])} df, p {d['p']:.3f})")
        # ---- final model and current specification on the validation half (used once)
        rv, cv, gv = self.data("validation")
        def vll(r):
            xv = np.array([r["x"][q] for q in r["spec"].params()])
            return float(X.heldout(rv, cv, gv, r["spec"], xv, self.pur, self.sk, obs="mix")["LL"].sum())
        vfin = vll(cur)
        f = self.row(cur, None, "final"); f.update(step="final", label="final model", validation_LL=vfin)
        for c in [c for c in self.coefs if c["step"] == cur["step"]]: self.coefs.append(dict(c, step="final"))
        s0 = FS.spec_of(self.seg)
        E = pd.read_csv(f"{TE}/results/fullset_estimates_taz.csv"); x_art = E[E.segment == self.seg].set_index("param").value.to_dict()
        rr = self.fit("record", "current specification", M.Spec("record", s0.linear, s0.size_base, s0.size_comps), x_art)
        vrec = vll(rr); g = self.row(rr, None, ""); g.update(validation_LL=vrec)
        self.log(f"final: K {cur['K']} LL {cur['LL']:.2f} BIC {cur['BIC']:.1f} validation LL {vfin:.2f} ({vfin / len(rv):.4f} per record, N {len(rv)})")
        self.log(f"current specification: K {rr['K']} LL {rr['LL']:.2f} BIC {rr['BIC']:.1f} validation LL {vrec:.2f} ({vrec / len(rv):.4f} per record)")
        self.log(f"final specification: {cur['spec'].linear}, size base {cur['spec'].size_base}, components {cur['spec'].size_comps}; {time.time() - t0:.0f} s")
        cols = ["step", "label", "K", "LL", "BIC", "LR", "df", "p", "decision", "validation_LL"]
        pd.DataFrame(self.rows).reindex(columns=cols).to_csv(f"{HERE}/{self.name}_fit.csv", index=False)
        pd.DataFrame(self.coefs).to_csv(f"{HERE}/{self.name}_coef.csv", index=False)


if __name__ == "__main__":
    for n in sys.argv[1:] or list(MODELS): Run(n).go()
