#!/usr/bin/env python3
"""Harmonised tour mode choice for work, shopping, other and school, with a pooled market-segmentation test
(Ben-Akiva & Lerman 1985, ch. 7: equality of coefficients across segments, segment-specific scale).

COMMON SPECIFICATION (union of the terms kept in any purpose's final model, m08 final / m09 final, one functional form each):
  level of service   travel time and travel cost on CD, CP, BUS, TRAIN (generic); round-trip km on WK and BK
  person             age, male, driving licence on every non-reference mode
  household          household size, cars, children under 16, fewer cars than drivers on every non-reference mode
  tour               joint household tour on every non-reference mode (only shopping and other have joint tours);
                     paid-parking share and tour with stops on CD; purpose accompany / recreation on every non-reference
                     mode in "other" only (purpose-only variables, never pooled)
  main-activity zone core city / rural on every non-reference mode (kept in work; rural not on walk, as in m08)
  constants          alternative-specific, per purpose
Reference alternative: car driver.  Multinomial logit.  A term enters a purpose only when it varies among the tours for which
the mode is available (m08 rule) and, for a 0/1 variable, when tours of both classes choose the mode (otherwise the
coefficient is not identified: perfect separation, e.g. no train tour to a rural main-activity zone).  Work tours carry WESML weights (column wesml); other purposes weight 1.

STEP 1  separate models: the common specification for each purpose, estimation half (validation LL reported, not used).
STEP 2  pooled model: the four estimation samples stacked, U = mu_p * V_p, mu_work = 1, mu_shopping, mu_other, mu_school > 0.
        P0: every coefficient purpose specific, scales fixed at 1 (not identified); LL must equal the sum of the separate LLs.
        A purpose's scale is free as soon as it shares a coefficient with work (in general: one scale per group of purposes
        connected by shared coefficients is normalised to 1, work's if work is in the group).
        Blocks pooled in this FIXED ORDER, each tested against the current pooled model:
          (a) travel cost  (b) travel time  (c) km on walk and bike  (d) person terms (age, male, licence)
          (e) household terms (size, cars, children, fewer cars than drivers)  (f) parking share, stops (CD), joint tour
          (f2) main-activity zone core city / rural          (g) alternative constants: NEVER pooled; acc / rec never pooled.
        DECISION RULE (applied to every block): keep the restriction when BIC does not rise (BIC_restricted <= BIC_current;
        for a block that removes parameters this means BIC falls; block (a) with free scales removes as many coefficients as
        it adds scales, df = 0) AND the shared estimates have the expected sign (PRIOR below).  The LR test (restricted vs
        current, df = parameters removed) is reported for information.
        If the full block is rejected, lettered alternatives (pre-stated, motivated by tour type): a1 shopping + other
        (discretionary tours), a2 work + school (mandatory tours), a3 both pairs; the alternative passing the rule with
        the lowest BIC is kept.
STEP 3  nesting of the other-purpose tours (auto {CD, CP}, transit {BUS, TRAIN}, as in m08 final) on the final pooled model:
        kept when the LR test rejects at 5 %, BIC falls and 1 < mu_nest < 10.
ENGINE  separate models: Biogeme 3.3.5 (as m08 / m09).  Pooled models: the same likelihood in JAX (see jmodel), because Biogeme
        needed > 20 min per pooled model; P0 must reproduce the Biogeme separate models (LL and robust t, checked in the log).
        Robust covariance of the pooled models: H^-1 (sum w^2 g g') H^-1 (WESML sandwich, Manski-Lerman); Biogeme's robust
        covariance with a weight uses sum w g g' instead, so the robust t of WORK coefficients differ from Biogeme's (median
        ratio of standard errors about 1.1); the other purposes (w = 1) agree to 4 digits.
STEP 4  final pooled model; validation half used once: LL per purpose (work WESML weighted), compared with m08 / m09 final.
    ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice_pooled/mp_pooled.py   ->  mp_fit.csv, mp_coef.csv, mp.log"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys
sys.dont_write_bytecode = True
import os, json
import numpy as np, pandas as pd
from scipy.stats import chi2

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/mode_pooled"   # results of this step (data); CODE = this folder
MCD = os.path.join(os.path.dirname(HERE), "mode_choice")   # tour mode-choice results (data)
sys.path.insert(0, os.path.join(os.path.dirname(CODE), "tour_mode_choice"))
import m07_children as K7   # noqa: E402
G = K7.L6.G
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models   # noqa: E402
from biogeme.expressions import Beta, Variable as X   # noqa: E402
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit   # noqa: E402

PURP = ["work", "shopping", "other", "school"]
ALTS = G.ALTS                      # CD WK BK CP BUS TRAIN
NONREF = [a for a in ALTS if a != "CD"]
MOT = ["CD", "CP", "BUS", "TRAIN"]
PERSON, HH, ZONE = ["age", "male", "lic"], ["hhsize", "autos", "kids", "short"], ["core_d", "rural_d"]
PURPOSE_ONLY = {"other": ["acc", "rec"]}
NEST_OTHER = {"auto": ["CD", "CP"], "transit": ["BUS", "TRAIN"]}
# expected signs (only terms with a clear prior)
PRIOR = {"time": -1, "cost": -1, "km_WK": -1, "km_BK": -1, "park_CD": -1, "stops_CD": 1,
         "lic_CP": -1, "lic_BUS": -1, "lic_TRAIN": -1, "autos_WK": -1, "autos_BK": -1, "autos_BUS": -1, "autos_TRAIN": -1,
         **{f"short_{a}": 1 for a in NONREF}, "joint_CP": 1, "male_CP": -1, "male_BK": 1}
BLOCKS = [("a", "travel cost", lambda k: k == "cost"),
          ("b", "travel time", lambda k: k == "time"),
          ("c", "round-trip km, walk and bike", lambda k: k in ("km_WK", "km_BK")),
          ("d", "person: age, male, driving licence", lambda k: k.split("_")[0] in PERSON),
          ("e", "household: size, cars, children, fewer cars than drivers", lambda k: k.split("_")[0] in HH),
          ("f", "parking share, stops (car driver), joint tour", lambda k: k in ("park_CD", "stops_CD") or k.startswith("joint_")),
          ("f2", "main-activity zone core city / rural", lambda k: k.startswith("core_d_") or k.startswith("rural_d_"))]
SUBSETS = [("1", "shopping + other", [["shopping", "other"]]), ("2", "work + school", [["work", "school"]]),
           ("3", "shopping + other, work + school", [["shopping", "other"], ["work", "school"]])]
LOG = open(f"{HERE}/mp.log", "a")


def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()


def load(half):
    out = []
    for p in PURP:
        d = K7.data(half, p).copy(); d["w"] = d["wesml"].astype(float) if p == "work" else 1.0
        for q in PURP: d[f"d_{q}"] = float(p == q)
        d["purp"] = p; out.append(d)
    return out


def terms_of(d, p):
    """common-specification terms present in purpose p (data d): {term: (variable, alternative list)}"""
    T = {"time": ("t", MOT), "cost": ("c", MOT), "km_WK": ("km", ["WK"]), "km_BK": ("km", ["BK"])}
    for a in NONREF:
        for v in PERSON + HH + ["joint"] + ZONE + PURPOSE_ONLY.get(p, []):
            if a == "WK" and v == "rural_d": continue
            x = d.loc[d[f"av_{a}"] > 0, v]
            if not x.std() > 0: continue
            if set(np.unique(x)) <= {0, 1} and min(((d[v] == 1) & (d.choice == a)).sum(), ((d[v] == 0) & (d.choice == a)).sum()) == 0:
                continue                              # perfect separation: no tour in one class chooses the mode
            T[f"{v}_{a}"] = (v, [a])
    for v in ("park", "stops"): T[f"{v}_CD"] = (v, ["CD"])
    for a in NONREF: T[f"ASC_{a}"] = (None, [a])
    return T


class Spec:
    """share: {term: [list of purpose groups sharing it]}"""
    def __init__(self, terms, share=None, nest=False):
        self.terms, self.share, self.nest = terms, share or {}, nest

    def name(self, k, p):
        for g in self.share.get(k, []):
            if p in g:
                have = [q for q in PURP if k in self.terms[q]]
                return k if sorted(g) == sorted(have) else f"{k}__{'+'.join(q for q in PURP if q in g)}"
        return f"{k}__{p}"

    def free_scales(self):
        par = {p: p for p in PURP}
        def f(x):
            while par[x] != x: x = par[x]
            return x
        for k, gs in self.share.items():
            for g in gs:
                g = [q for q in g if k in self.terms[q]]
                for q in g[1:]: par[f(q)] = f(g[0])
        comp = {}
        for p in PURP: comp.setdefault(f(p), []).append(p)
        free = []
        for c in comp.values():
            if len(c) > 1: free += [q for q in c if q != ("work" if "work" in c else c[0])]
        return free

    def copy(self, **kw):
        s = Spec(self.terms, json.loads(json.dumps(self.share)), self.nest); [setattr(s, a, b) for a, b in kw.items()]; return s


def loglike(spec, purps, start):
    free = spec.free_scales(); B = {}
    def beta(n, lo=None, hi=None, init=0.0):
        if n not in B: B[n] = Beta(n, start.get(n, init), lo, hi, 0)
        return B[n]
    V = {a: 0 for a in ALTS}
    for p in purps:
        Vp = {a: 0 for a in ALTS}
        for k, (v, alts) in spec.terms[p].items():
            b = beta(spec.name(k, p))
            for a in alts: Vp[a] = Vp[a] + b * (X(f"{v}_{a}") if v in ("t", "c") else (1 if v is None else X(v)))
        mu = beta(f"mu_{p}", 0.02, 50.0, 1.0) if p in free else 1.0
        for a in ALTS: V[a] = V[a] + X(f"d_{p}") * mu * Vp[a] if len(purps) > 1 else Vp[a]
    U = {G.NUM[a]: V[a] for a in ALTS}; AV = {G.NUM[a]: X(f"av_{a}") for a in ALTS}
    if spec.nest:
        ns = []
        for k, al in NEST_OTHER.items():
            m = beta(f"nest_{k}__other", 1.0, 10.0, 1.2)
            ns.append(OneNestForNestedLogit(1.0 + X("d_other") * (m - 1.0), [G.NUM[a] for a in al], name=k))
        return models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
    return models.loglogit(U, AV, X("y"))


def num(x): return x.select_dtypes(include=[np.number, bool]).astype(float)


def estimate(spec, data, purps, start, name):
    df = pd.concat([data[PURP.index(p)] for p in purps], ignore_index=True)
    m = bio.BIOGEME(db.Database(name, num(df)), {"loglike": loglike(spec, purps, start), "weight": X("w")},
                    save_iterations=False, generate_html=False, generate_yaml=False)
    m.model_name = f"mp_{name}"; r = m.estimate(); t = G.table(r)
    LL = float(r.final_loglikelihood); K = int(r.number_of_free_parameters); N = len(df)
    return t, dict(K=K, LL=LL, BIC=K * np.log(N) - 2 * LL, N=N, converged=bool(r.algorithm_has_converged))


def validation(spec, vdata, purps, b):
    out = {}
    for p in purps:
        d = vdata[PURP.index(p)]
        sim = bio.BIOGEME(db.Database("v", num(d)), {"ll": loglike(spec, purps if len(purps) > 1 else [p], b)},
                          save_iterations=False, generate_html=False, generate_yaml=False)
        lh = sim.simulate(the_beta_values=b)["ll"].values; out[p] = float((lh * d.w.values).sum())
    return out


# ---------------------------------------------------------------------------------------------------------------------------
# Pooled models: the same likelihood written directly in JAX (Biogeme's full analytic Hessian with ~240 parameters and the
# purpose-scale products took > 20 min per model).  P0 must reproduce the sum of the Biogeme separate models (check below).
# Estimation: L-BFGS-B (bounds: scales 0.02-50, nest parameters 1-10), Newton polish; robust (sandwich) covariance with the
# weighted per-tour scores, as Biogeme's robust standard errors.
import jax, jax.numpy as jnp   # noqa: E402
from scipy.optimize import minimize   # noqa: E402
jax.config.update("jax_enable_x64", True)
AI = {a: i for i, a in enumerate(ALTS)}


def design(d, T):
    """Z (N, 6, Q) for the ordered terms T of a purpose, availability (N, 6), chosen index, weight"""
    keys = list(T); Z = np.zeros((len(d), len(ALTS), len(keys)))
    for j, k in enumerate(keys):
        v, alts = T[k]
        for a in alts:
            Z[:, AI[a], j] = 1.0 if v is None else d[f"{v}_{a}" if v in ("t", "c") else v].values
    av = np.stack([d[f"av_{a}"].values > 0 for a in ALTS], 1)
    return dict(Z=np.nan_to_num(Z), av=av, y=d["y"].values.astype(int) - 1, w=d["w"].values.astype(float), keys=keys)


def jmodel(spec, D, purps):
    """parameter names, bounds and a function theta -> per-tour weighted log-likelihood (concatenated over purps)"""
    free = spec.free_scales() if len(purps) > 1 else []; names = []
    def idx(n):
        if n not in names: names.append(n)
        return names.index(n)
    parts = []
    for p in purps:
        dd = D[p]; m = np.array([idx(spec.name(k, p)) for k in dd["keys"]])
        mu = idx(f"mu_{p}") if p in free else None
        ne = [idx(f"nest_{k}__other") for k in NEST_OTHER] if (spec.nest and p == "other") else None
        parts.append((p, jnp.asarray(dd["Z"]), jnp.asarray(dd["av"]), jnp.asarray(dd["y"]), jnp.asarray(dd["w"]), jnp.asarray(m), mu, ne))
    lb = [0.02 if n.startswith("mu_") else 1.0 if n.startswith("nest_") else None for n in names]
    ub = [50.0 if n.startswith("mu_") else 10.0 if n.startswith("nest_") else None for n in names]

    def ll(theta):
        out = []
        for p, Z, av, y, w, m, mu, ne in parts:
            b = theta[m] * (theta[mu] if mu is not None else 1.0)
            V = jnp.einsum("naq,q->na", Z, b); V = jnp.where(av, V, -1e10)
            if ne is None:
                lp = V - jax.scipy.special.logsumexp(V, axis=1, keepdims=True)
            else:
                lam = jnp.ones(len(ALTS)); nid = np.arange(len(ALTS)); groups = []
                for g, (k, al) in enumerate(NEST_OTHER.items()):
                    for a in al: lam = lam.at[AI[a]].set(theta[ne[g]]); nid[AI[a]] = 100 + g
                # nest utilities: (1/lam) log sum_{j in nest} exp(lam V_j); singletons: V
                cols, logcond = [], jnp.zeros_like(V)
                for u in sorted(set(nid)):
                    mem = np.where(nid == u)[0]; l = lam[mem[0]]
                    s = jax.scipy.special.logsumexp(l * V[:, mem], axis=1)
                    cols.append(s / l); logcond = logcond.at[:, mem].set(l * V[:, mem] - s[:, None])
                Vn = jnp.stack(cols, 1); lpn = Vn - jax.scipy.special.logsumexp(Vn, axis=1, keepdims=True)
                pos = {u: i for i, u in enumerate(sorted(set(nid)))}
                lp = logcond + lpn[:, np.array([pos[u] for u in nid])]
            out.append(w * jnp.take_along_axis(lp, y[:, None], 1)[:, 0])
        return jnp.concatenate(out)
    return names, list(zip(lb, ub)), ll


def jestimate(spec, D, purps, start, name):
    names, bounds, ll = jmodel(spec, D, purps)
    f = jax.jit(lambda th: -jnp.sum(ll(th))); fg = jax.jit(jax.value_and_grad(lambda th: -jnp.sum(ll(th))))
    x0 = np.array([start.get(n, 1.2 if n.startswith("nest_") else 1.0 if n.startswith("mu_") else 0.0) for n in names], float)
    x0 = np.array([min(max(v, lo if lo is not None else -np.inf), hi if hi is not None else np.inf) for v, (lo, hi) in zip(x0, bounds)])
    r = minimize(lambda th: tuple(np.asarray(z, float) for z in fg(jnp.asarray(th))), x0, jac=True, method="L-BFGS-B",
                 bounds=bounds, options=dict(maxiter=3000, maxfun=6000, ftol=1e-14, gtol=1e-7, maxcor=30))
    th = r.x; H = jax.jit(jax.hessian(lambda t: -jnp.sum(ll(t))))
    lo = np.array([b[0] if b[0] is not None else -np.inf for b in bounds]); hi = np.array([b[1] if b[1] is not None else np.inf for b in bounds])
    lam = 1e-6
    for _ in range(80):                                   # damped (Levenberg-Marquardt) Newton polish, interior parameters
        val, g = fg(jnp.asarray(th)); g = np.asarray(g)
        act = ((th <= lo + 1e-9) & (g > 0)) | ((th >= hi - 1e-9) & (g < 0)); fr = ~act
        if np.max(np.abs(g[fr])) < 1e-6: break
        Hm = np.asarray(H(jnp.asarray(th)))[np.ix_(fr, fr)]; Dg = np.maximum(np.abs(np.diag(Hm)), 1e-8)
        while lam < 1e12:
            step = np.zeros_like(th)
            try: step[fr] = np.linalg.solve(Hm + lam * np.diag(Dg), g[fr])
            except np.linalg.LinAlgError: lam *= 10; continue
            tn = np.clip(th - step, lo, hi)
            if float(f(jnp.asarray(tn))) < float(val): th = tn; lam = max(lam / 10, 1e-12); break
            lam *= 10
        else: break
    val, g = fg(jnp.asarray(th)); g = np.asarray(g); Hm = np.asarray(H(jnp.asarray(th)))
    act = ((th <= lo + 1e-7) | (th >= hi - 1e-7)) & (np.abs(g) > 1e-4)
    S = np.asarray(jax.jit(jax.jacrev(ll))(jnp.asarray(th)))
    fr = ~act; Hi = np.linalg.pinv(Hm[np.ix_(fr, fr)]); C = Hi @ (S[:, fr].T @ S[:, fr]) @ Hi
    se = np.full(len(th), np.nan); se[fr] = np.sqrt(np.diag(C))
    gmax = float(np.max(np.abs(g[fr]))); conv = bool(gmax < 0.05) and bool(np.all(np.isfinite(se[fr])))
    t = pd.DataFrame({"Value": th, "Robust std err.": se, "Robust t-stat.": th / se}, index=pd.Index(names, name="Name"))
    LL = -float(val); K = len(names); N = sum(len(D[p]["y"]) for p in purps)
    return t, dict(K=K, LL=LL, BIC=K * np.log(N) - 2 * LL, N=N, converged=conv, max_gradient=gmax,
                   at_bound=",".join(n for n, a in zip(names, act) if a))


def jvalidation(spec, Dv, purps, b):
    names, _, ll = jmodel(spec, Dv, purps); v = np.asarray(ll(jnp.asarray([b[n] for n in names])))
    out, i = {}, 0
    for p in purps:
        n = len(Dv[p]["y"]); out[p] = float(v[i:i + n].sum()); i += n
    return out


def sign_problems(t, spec):
    bad = []
    for n in t.index:
        k = n.split("__")[0]
        if k in PRIOR and np.sign(t.Value[n]) != PRIOR[k]: bad.append(f"{n} {t.Value[n]:.3f} (t {t['Robust t-stat.'][n]:.1f})")
    return bad


FIT, COEF = [], []


def record(step, label, t, x, **kw):
    x = dict(step=step, label=label, **x, **kw); FIT.append(x)
    se_col = "Robust std err." if "Robust std err." in t.columns else None
    for n, y in t.iterrows():
        k, _, grp = n.partition("__")
        if k.startswith("mu_"): k, grp = "scale", k[3:]
        if k.startswith("nest_"): k = k
        COEF.append(dict(step=step, purpose=grp or "shared", param=k, coef=y.Value,
                         se=y[se_col] if se_col else abs(y.Value / y["Robust t-stat."]), t=y["Robust t-stat."]))
    say(f"[{step}] {label}: K {x['K']} LL {x['LL']:.2f} BIC {x['BIC']:.1f} LR {x.get('LR', np.nan):.2f} df {x.get('df', '')} "
        f"p {x.get('p', np.nan):.3g} {x.get('decision', '')} {'' if x['converged'] else 'NOT CONVERGED'}")
    pd.DataFrame(FIT).to_csv(f"{HERE}/mp_fit.csv", index=False); pd.DataFrame(COEF).to_csv(f"{HERE}/mp_coef.csv", index=False)


def main():
    os.chdir(f"{HERE}/bio"); say("==== mp_pooled run", pd.Timestamp.now())
    E, Vd = load("estimation"), load("validation")
    terms = {p: terms_of(E[i], p) for i, p in enumerate(PURP)}
    base = Spec(terms)
    D = {p: design(E[i], terms[p]) for i, p in enumerate(PURP)}; Dv = {p: design(Vd[i], terms[p]) for i, p in enumerate(PURP)}
    # ---- STEP 1: separate models
    start, sepLL, sepK = {}, 0.0, 0
    for p in PURP:
        t, x = estimate(base, E, [p], {}, f"sep_{p}")
        b = t.Value.to_dict(); vl = validation(base, Vd, [p], b)[p]
        bad = sign_problems(t, base)
        record(f"sep_{p}", f"separate model, common specification: {p}", t, x, purpose=p, validation_LL=vl,
               decision="separate", sign_problems="; ".join(bad))
        say("   sign problems:", bad or "none"); start.update(b); sepLL += x["LL"]; sepK += x["K"]
    # ---- STEP 2: pooled
    t, cur = jestimate(base, D, PURP, start, "P0")
    record("P0", "pooled, all coefficients purpose specific, scales 1", t, cur, decision=f"check: sum of separate LL {sepLL:.2f}, K {sepK}")
    bt = pd.DataFrame(COEF); bt = bt[bt.step.str.startswith("sep_")]
    bt = dict(zip(bt.param + "__" + bt.purpose, bt.t)); dt = pd.Series({n: abs(t["Robust t-stat."][n] - bt[n]) for n in t.index})
    say(f"   check: LL P0 (JAX) - sum of separate LL (Biogeme) = {cur['LL'] - sepLL:.3f}; |t difference| median {dt.median():.4f}, "
        f"largest {dt.max():.3f} ({dt.idxmax()})")
    assert -0.01 < cur["LL"] - sepLL < 0.5 and cur["K"] == sepK, "pooled P0 does not reproduce the separate models"
    spec, cb = base, t.Value.to_dict()
    for code, label, sel in BLOCKS:
        keys = sorted({k for p in PURP for k in terms[p] if sel(k)})
        def trial(groups, tag, lab):
            s = spec.copy()
            for k in keys:
                have = [q for q in PURP if k in terms[q]]
                gs = [[q for q in g if q in have] for g in groups]; gs = [g for g in gs if len(g) > 1]
                if gs: s.share[k] = gs
            st = dict(cb)
            for k in keys:
                for p in PURP:
                    if k in terms[p]:
                        n = s.name(k, p)
                        if n not in st: st[n] = cb.get(spec.name(k, p), 0.0)
            for p in s.free_scales(): st.setdefault(f"mu_{p}", 1.0)
            t, x = jestimate(s, D, PURP, st, f"{code}{tag}")
            lr = 2 * (cur["LL"] - x["LL"]); df = cur["K"] - x["K"]
            x.update(LR=lr, df=df, p=float(chi2.sf(max(lr, 0), df)) if df > 0 else np.nan)
            shared = [n for n in t.index if (n in keys) or ("+" in n and n.split("__")[0] in keys)]
            bad = [n for n in shared if n.split("__")[0] in PRIOR and np.sign(t.Value[n]) != PRIOR[n.split("__")[0]]]
            ok = x["BIC"] <= cur["BIC"] + 1e-6 and not bad and x["converged"]
            why = "kept" if ok else ("rejected: sign " + ", ".join(bad) if bad and x["converged"] else "rejected: BIC rises" if x["converged"]
                                     else "rejected: BIC rises (df 0, restricted LL cannot exceed the current LL; optimiser not fully converged)"
                                     if df == 0 and x["BIC"] > cur["BIC"] else "rejected: not converged")
            return s, t, x, ok, why, lab
        s, t, x, ok, why, lab = trial([PURP], "", f"({code}) pool {label}: all purposes")
        record(code, lab, t, x, decision=why, sign_problems="; ".join(sign_problems(t, s)))
        if ok:
            spec, cur, cb = s, x, t.Value.to_dict(); continue
        res = []
        for sc, sl, groups in SUBSETS:
            r = trial(groups, sc, f"({code}{sc}) pool {label}: {sl}")
            record(f"{code}{sc}", r[5], r[1], r[2], decision=r[4], sign_problems="; ".join(sign_problems(r[1], r[0]))); res.append(r)
        good = [r for r in res if r[3]]
        if good:
            best = min(good, key=lambda r: r[2]["BIC"]); s, t, x, ok, why, lab = best; spec, cur, cb = s, x, t.Value.to_dict()
            for f in FIT:
                if f["step"] == f"{code}{SUBSETS[res.index(best)][0]}": f["decision"] = "kept (lowest BIC of the alternatives)"
            say(f"   block {code}: kept alternative {lab}")
            pd.DataFrame(FIT).to_csv(f"{HERE}/mp_fit.csv", index=False)
    # ---- STEP 3: nesting of other tours
    s = spec.copy(nest=True); st = dict(cb); t, x = jestimate(s, D, PURP, st, "N")
    lr = 2 * (x["LL"] - cur["LL"]); df = x["K"] - cur["K"]; x.update(LR=lr, df=df, p=float(chi2.sf(max(lr, 0), df)))
    mus = [t.Value[n] for n in t.index if n.startswith("nest_")]
    ok = x["p"] < 0.05 and x["BIC"] < cur["BIC"] and all(1.0001 < m < 9.99 for m in mus)
    record("N", "other tours nested: car driver + passenger, bus + train", t, x, decision="kept" if ok else "not kept",
           sign_problems="; ".join(sign_problems(t, s)))
    if ok: spec, cur, cb = s, x, t.Value.to_dict()
    # ---- STEP 4: final + validation (once)
    t, x = jestimate(spec, D, PURP, cb, "final")
    vl = jvalidation(spec, Dv, PURP, t.Value.to_dict())
    ref = pd.read_csv(f"{MCD}/m08_fit.csv"); ref = ref[ref.step == "final"].set_index("segment")
    r9 = pd.read_csv(f"{MCD}/m09_fit.csv"); r9 = r9[r9.step == "final"].iloc[0]
    cur_v = {p: float(ref.loc[p, "holdout_LL"]) for p in ["work", "shopping", "other"]}; cur_v["school"] = float(r9.holdout_LL)
    cur_k = {p: int(ref.loc[p, "K"]) for p in ["work", "shopping", "other"]}; cur_k["school"] = int(r9.K)
    record("final", "final pooled model", t, x, decision="final", validation_LL=sum(vl.values()),
           **{f"validation_LL_{p}": vl[p] for p in PURP}, **{f"current_validation_LL_{p}": cur_v[p] for p in PURP},
           current_K_sum=sum(cur_k.values()), spec=json.dumps(spec.share), nest=spec.nest, free_scales=",".join(spec.free_scales()),
           sign_problems="; ".join(sign_problems(t, spec)))
    for p in PURP: say(f"   validation LL {p}: pooled {vl[p]:.1f}  current separate {cur_v[p]:.1f}")
    say(f"   K pooled {x['K']} vs current separate sum {sum(cur_k.values())}")


if __name__ == "__main__":
    main()
