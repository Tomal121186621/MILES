#!/usr/bin/env python3
"""Collinearity of the final tour mode-choice models: work, shopping, other (nested logit) of tour_mode_choice/m08_sequence.py and
school of tour_mode_choice/m09_school.py (final rows of m08_coef.csv / m09_coef.csv, the models mode_logsum_new.py reproduces).
Estimation half (m07_children.data), work with its WESML weights as in the estimation, the others unweighted.

(a) Variables: one column per free coefficient (alternative constants and nest parameters excluded), its utility contribution per
    mode (N tours x 6 modes; a person / household variable z of mode a enters as z 1[j = a]), demeaned within each tour over its
    available modes, with the alternative constants partialled out (c_abit_common.within_corr_partial; for two person variables
    of one mode this is their centred correlation over the tours where the mode is available).  Tour weights as in estimation.
    Person-row correlations of the household variables (cars check) are added to the facts.
(b) Estimates: robust covariance of the Biogeme re-fit of the final specification (LL checked against m08 / m09 to 0.1).
(d) Pairs: same variable in two modes, constant vs variable of one mode, nest parameter vs the terms of its modes: STRUCTURAL;
    others SUBSTANTIVE.  Centring: the person variables and the mode-specific distance centred at their weighted mean over the
    tours where the mode is available (exact reparametrisation, constants absorb the means).
(e) Refits without each member of a substantive pair; explicit check of the positive car-passenger "Cars" coefficient: person-row
    correlations with household size, fewer cars than drivers, licence and children; refit with cars per driver
    (cars / max(1, drivers)) in place of cars on every mode, and refits without "fewer cars than drivers" and household size.
    Identification of licence vs constants (car driver needs a licence): LL after shifting every constant +1 and every licence
    term -1, and the refit with the licence term of walk normalised to 0; VIF with that normalisation.
    ~/.venvs/biogeme/bin/python estimation/development/collinearity/c_abit_mode.py [work shopping other school]  ->  mc_<seg>_var_corr.png, mc_<seg>_est_corr.png, ..."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, ast
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; SB = os.path.dirname(HERE); MC = os.path.join(SB, "mode_choice")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, os.path.join(DEV, "tour_mode_choice")); sys.path.insert(0, CODE)
import c_abit_common as CA   # noqa: E402
CC = CA.CC
import m08_sequence as M8   # noqa: E402
import t_mc_tables as TT   # noqa: E402
K7, G = M8.K7, M8.G
import biogeme.database as db, biogeme.biogeme as bio, biogeme.models as models   # noqa: E402
from biogeme.expressions import Beta, Variable as X   # noqa: E402
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit   # noqa: E402
from biogeme.results_processing import EstimateVarianceCovariance as EVC   # noqa: E402

ALTS = G.ALTS; MOT = ["CD", "CP", "BUS", "TRAIN"]
MODE = dict(TT.MODES); MODE["PT"] = "Bus and train"; MODE["CD"] = "Car driver"
VLAB = {k: CC.plain(v) for g in TT.GROUPS for k, v in g[1]} | {k: CC.plain(v) for k, v in TT.GENERIC}
VLAB.update(ovt="Out-of-vehicle time (min)", cars_per_driver="Cars per driver")
TEX = {"work": "work", "shopping": "shopping", "other": "other", "school": "school"}
TITLE = {"work": "Tour mode choice, work", "shopping": "Tour mode choice, shopping", "other": "Tour mode choice, other (nested logit)",
         "school": "Tour mode choice, school"}
HH = ["hhsize", "autos", "short", "lic", "kids", "age", "male", "cars_per_driver"]


def final_spec(seg):
    """coefficient names and nests of the final model"""
    if seg == "school":
        F = pd.read_csv(f"{MC}/m09_fit.csv"); fin = F[F.step == "final"].iloc[-1]; C = pd.read_csv(f"{MC}/m09_coef.csv")
    else:
        F = pd.read_csv(f"{MC}/m08_fit.csv"); F = F[F.segment == seg]; fin = F[F.step == "final"].iloc[-1]; C = pd.read_csv(f"{MC}/m08_coef.csv")
    C = C[(C.segment == seg) & (C.step == "final")]
    nests = None if pd.isna(fin.nests) or fin.nests == "None" else ast.literal_eval(fin.nests)
    return list(C.param), dict(zip(C.param, C.coef)), nests, float(fin.LL)


def columns(p, alts):
    """{alt: data column} of the utility term of parameter p ('one' for a constant)"""
    if p.startswith("mu_"): return {}
    if p.startswith("ASC_"): return {p[4:]: "one"}
    if p in ("gc", "time", "cost"): return {a: f"{ {'gc': 'gc', 'time': 't', 'cost': 'c'}[p]}_{a}" for a in MOT if a in alts}
    if p == "ovt": return {a: f"ovt_{a}" for a in ("BUS", "TRAIN") if a in alts}
    if p == "park_CD": return {"CD": "park"}
    if p == "stops_CD": return {"CD": "stops"}
    v, a = p.rsplit("_", 1)
    return {m: v for m in (("BUS", "TRAIN") if a == "PT" else (a,)) if m in alts}


class Model:
    def __init__(self, seg):
        self.seg = seg; df = K7.data("estimation", seg).reset_index(drop=True); df["one"] = 1.0
        df["cars_per_driver"] = df.autos / np.maximum(1.0, df.drivers)
        self.df = df; self.alts = [a for a in ALTS if df[f"av_{a}"].sum() > 0 and (df.choice == a).sum() > 0]
        self.params, self.b0, self.nests, self.LLrep = final_spec(seg)
        self.w = df.wesml.values if seg == "work" else np.ones(len(df)); self.N = len(df)
        self.av = np.stack([df[f"av_{a}"].values > 0 for a in self.alts], 1)

    def fit(self, drop=(), replace=None, start=True, tag="fit"):
        """re-fit with parameters `drop` removed; replace {param: new data column name} (the column then enters in its place)"""
        df = self.df; replace = replace or {}; V = {a: 0 for a in self.alts}; ps = [p for p in self.params if p not in drop]
        for p in ps:
            if p.startswith("mu_"): continue
            for a, c in columns(p, self.alts).items():
                c = replace.get(p, c)
                V[a] = V[a] + Beta(p, 0, None, None, 0) * X(c)
        U = {G.NUM[a]: V[a] for a in self.alts}; AV = {G.NUM[a]: X(f"av_{a}") for a in self.alts}
        if self.nests:
            ns = [OneNestForNestedLogit(Beta(f"mu_{k}", 1.2, 1.0, 10.0, 0), [G.NUM[a] for a in v if a in self.alts], name=k) for k, v in self.nests.items()]
            ll = models.lognested(U, AV, NestsForNestedLogit(choice_set=list(U), tuple_of_nests=tuple(ns)), X("y"))
        else: ll = models.loglogit(U, AV, X("y"))
        num = df.select_dtypes(include=[np.number, bool]).astype(float)
        m = bio.BIOGEME(db.Database(f"c_{self.seg}_{tag}", num), {"loglike": ll, "weight": X("wesml")} if self.seg == "work" else ll,
                        save_iterations=False, generate_html=False, generate_yaml=False)
        m.model_name = f"c_abit_{self.seg}_{tag}"
        if start: m.change_init_values({p: v for p, v in self.b0.items() if p in ps and p not in replace})
        r = m.estimate(); b = r.get_beta_values(); names = list(b)
        cov = np.asarray(r.get_variance_covariance_matrix(EVC.ROBUST)); se = np.sqrt(np.diag(cov))
        t = G.table(r); assert np.allclose(se, t.loc[names, "Robust std err."].values, rtol=1e-6)
        return dict(LL=float(r.final_loglikelihood), K=len(names), N=self.N, names=names, b=np.array([b[n] for n in names]), se=se, cov=cov,
                    conv=bool(r.algorithm_has_converged))

    def design(self, names, col_of=None):
        """(N, J, K) utility columns of the parameters `names`"""
        out = np.zeros((self.N, len(self.alts), len(names)))
        for k, p in enumerate(names):
            for a, c in columns(p, self.alts).items(): out[:, self.alts.index(a), k] = self.df[c].values
        return out


def lab(p):
    if p.startswith("mu_"): return {"mu_auto": "Nest parameter, car driver and passenger", "mu_transit": "Nest parameter, bus and train"}[p]
    if p in ("gc", "time", "cost", "park_CD", "stops_CD", "ovt"): return VLAB[p]
    v, a = p.rsplit("_", 1); return f"{VLAB['ASC' if v == 'ASC' else v]}: {MODE[a]}"


def split(p):
    if p.startswith("ASC_"): return "ASC", p[4:]
    if p.startswith("mu_") or p in ("gc", "time", "cost", "ovt", "park_CD", "stops_CD"): return p, None
    return tuple(p.rsplit("_", 1))


def classify(a, b, nests):
    (va, ma), (vb, mb) = split(a), split(b)
    if a.startswith("mu_") or b.startswith("mu_"):
        mu = a if a.startswith("mu_") else b; o = b if mu == a else a; mem = nests[mu[3:]] if nests else []
        om = split(o)[1]; inn = om is None or om in mem or om == "PT" and ("BUS" in mem)
        return ("STRUCTURAL", "nest parameter vs a term of its nest (scale of the within-nest differences)", False) if inn else ("SUBSTANTIVE", "", False)
    if ma and mb and va == vb: return "STRUCTURAL", "same variable in two modes (common reference: car driver)", False
    if "ASC" in (va, vb) and ma == mb: return "STRUCTURAL", "constant vs uncentred variable (same mode)", True
    if "ASC" in (va, vb): return "STRUCTURAL", "constant vs variable, different modes", True
    if {va, vb} == {"core_d", "rural_d"} and ma == mb: return "STRUCTURAL", "categories of one variable (area type)", False
    return "SUBSTANTIVE", "", False


def wcorr_rows(df, cols, w):
    return pd.DataFrame(CC.wcorr(df[cols].values.astype(float), w), index=cols, columns=cols)


def one(seg):
    model = f"mc_{seg}"; M = Model(seg); df, w, av = M.df, M.w, M.av
    base = M.fit(tag="final"); print(seg, "LL", base["LL"], "reported", M.LLrep, flush=True); assert abs(base["LL"] - M.LLrep) < 0.1
    assert sorted(base["names"]) == sorted(M.params)
    order = [p for p in M.params]                                            # coefficient-file order (generic, then by mode)
    ix = [base["names"].index(p) for p in order]
    base.update(names=order, b=base["b"][ix], se=base["se"][ix], cov=base["cov"][np.ix_(ix, ix)])
    vn = [p for p in order if not p.startswith(("ASC_", "mu_"))]; asc = [p for p in order if p.startswith("ASC_")]
    Xv = M.design(vn); P = M.design(asc)
    R, _ = CA.within_corr_partial(Xv, av, w, P); vf = CC.vif(R)
    vf = np.where((vf < 0) | (vf > 1e8), np.inf, vf)        # numerically singular matrix (exact linear dependence): VIF infinite
    labels = {p: lab(p) for p in order}
    CC.heatmap(R, [labels[v] for v in vn], f"{HERE}/{model}_var_corr.png",
               f"{TITLE[seg]}, final model: correlations of the explanatory variables\nwithin tour (demeaned over the available modes, constants partialled out), estimation half"
               + (", WESML weights" if seg == "work" else ""), "Correlation (within tour, net of the constants)")
    Re = CC.est_corr(base["cov"])
    CC.heatmap(Re, [labels[n] for n in order], f"{HERE}/{model}_est_corr.png",
               f"{TITLE[seg]}, final model: correlations of the estimates (robust covariance)\nestimation half, LL {base['LL']:,.1f}, {base['K']} parameters",
               "Correlation of the estimates")
    pd.DataFrame(R, index=vn, columns=vn).round(3).to_csv(f"{HERE}/{model}_var_corr.csv")
    pd.DataFrame(Re, index=order, columns=order).round(3).to_csv(f"{HERE}/{model}_est_corr.csv")
    # centring: every mode-specific variable centred at its weighted mean over the tours where the mode is available
    T = np.eye(len(order)); bi = {n: i for i, n in enumerate(order)}
    for p in order:
        v, a = split(p)
        if a is None or v == "ASC": continue
        for m_ in (("BUS", "TRAIN") if a == "PT" else (a,)):
            c = columns(p, M.alts)[m_]; ok = df[f"av_{m_}"].values > 0; mu = float(np.sum(w[ok] * df[c].values[ok]) / np.sum(w[ok]))
            k = f"ASC_{m_}"
            if k in bi: T[bi[k], bi[p]] += mu
    Rc = CC.est_corr(T @ base["cov"] @ T.T)
    vi = {n: i for i, n in enumerate(vn)}; rows = []
    for a, b, r in CC.pairs(R, vn, CC.R_VAR):
        t, why, _ = classify(a, b, M.nests)
        rows.append(dict(model=model, pair=f"{labels[a]} / {labels[b]}", p1=a, p2=b, source="variables", type=t, why=why, var_r=r, est_r=Re[bi[a], bi[b]],
                         est_r_centred=Rc[bi[a], bi[b]]))
    for v, x in zip(vn, vf):
        if x >= CC.VIF_MAX: rows.append(dict(model=model, pair=labels[v], p1=v, source="VIF", VIF=x))
    for a, b, r in CC.pairs(Re, order, CC.R_EST):
        t, why, cen = classify(a, b, M.nests)
        rows.append(dict(model=model, pair=f"{labels[a]} / {labels[b]}", p1=a, p2=b, source="estimates", type=t, why=why, est_r=r,
                         var_r=R[vi[a], vi[b]] if a in vi and b in vi else np.nan, est_r_centred=Rc[bi[a], bi[b]] if cen else np.nan))
    Pp = pd.DataFrame(rows)
    for c in ["est_r_centred", "why", "type", "var_r", "p2"]:
        if c not in Pp: Pp[c] = np.nan
    Pp["centring_removes"] = np.where(Pp.why.astype(str).str.startswith("constant"), Pp.est_r_centred.abs() < CC.R_EST, np.nan)
    Pp["VIF_p1"] = [vf[vi[x]] if x in vi else np.nan for x in Pp.p1]; Pp["VIF_p2"] = [vf[vi[x]] if isinstance(x, str) and x in vi else np.nan for x in Pp.p2]
    print(Pp.drop(columns=["pair"]).round(3).to_string(), flush=True)
    # (e) refits of the substantive pairs
    ref, cache = [], {}
    def get(drop=(), replace=None, tag=""):
        key = (tuple(sorted(drop)), str(replace))
        if key not in cache: cache[key] = M.fit(drop=drop, replace=replace, tag=tag or "r%d" % len(cache))
        return cache[key]
    done = set()
    for _, q in Pp[(Pp.source != "VIF") & (Pp.type == "SUBSTANTIVE")].iterrows():
        if frozenset((q.p1, q.p2)) in done: continue
        done.add(frozenset((q.p1, q.p2)))
        for d, f in ((q.p1, q.p2), (q.p2, q.p1)):
            if d.startswith("mu_"): continue
            m = get([d]); rr = CC.refit_row(base, m, f, f"without {d}"); rr.update(model=model, pair=q.pair); ref.append(rr)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rr.items()}, flush=True)
    # explicit check: cars on car passenger
    checks, crow = [], []
    Rp = {}
    for a in ["CP"] + [m_ for m_ in M.alts if m_ not in ("CD", "CP")]:
        ok = df[f"av_{a}"].values > 0
        Rp[a] = wcorr_rows(df[ok], HH, w[ok])
    rc = Rp["CP"].loc["autos"]
    ac = [p for p in order if p.startswith("autos_")]
    est_cp = {p: float(Re[bi["autos_CP"], bi[p]]) for p in order if p.endswith("_CP") and p != "autos_CP"}
    chk = dict(check="cars on car passenger", b_autos_CP=float(base["b"][bi["autos_CP"]]), se_autos_CP=float(base["se"][bi["autos_CP"]]),
               r_rows_autos=dict(rc.drop("autos").round(3)), est_r_autos_CP=dict(pd.Series(est_cp).round(3)),
               mean_drivers=float(np.average(df.drivers, weights=w)), share_zero_drivers=float(np.average(df.drivers == 0, weights=w)))
    cpd = {p: "cars_per_driver" for p in ac}
    m = get([], cpd, "cpd"); nb = dict(zip(m["names"], m["b"])); ns = dict(zip(m["names"], m["se"]))
    rr = CA.check_row(model, "cars on car passenger", "cars per driver in place of cars (all modes)", base, m, "autos_CP"); crow.append(rr)
    chk["cars_per_driver"] = dict(LL=m["LL"], dLL=m["LL"] - base["LL"], dBIC=rr["dBIC"], b_CP=nb["autos_CP"], se_CP=ns["autos_CP"],
                                  b=dict((p, round(nb[p], 4)) for p in ac), t=dict((p, round(nb[p] / ns[p], 2)) for p in ac),
                                  short_CP=nb.get("short_CP"), r_rows_cpd=dict(Rp["CP"].loc["cars_per_driver"].drop("cars_per_driver").round(3)))
    for nm, drop in [("without fewer cars than drivers", [p for p in order if p.startswith("short_")]),
                     ("without household size", [p for p in order if p.startswith("hhsize_")]),
                     ("without children", [p for p in order if p.startswith("kids_")])]:
        if not drop: continue
        m = get(drop, None); nb = dict(zip(m["names"], m["b"])); ns = dict(zip(m["names"], m["se"]))
        rr = CA.check_row(model, "cars on car passenger", nm, base, m, "autos_CP"); crow.append(rr)
        chk[nm] = dict(LL=m["LL"], dBIC=rr["dBIC"], p=rr["p"], b_CP=nb["autos_CP"], t_CP=nb["autos_CP"] / ns["autos_CP"])
    if "short_CP" in bi:
        m = get([p for p in order if p.startswith("short_")], cpd, "cpd_noshort"); nb = dict(zip(m["names"], m["b"])); ns = dict(zip(m["names"], m["se"]))
        rr = CA.check_row(model, "cars on car passenger", "cars per driver, without fewer cars than drivers", base, m, "autos_CP"); crow.append(rr)
        chk["cars per driver, without fewer cars than drivers"] = dict(LL=m["LL"], dBIC=rr["dBIC"], b_CP=nb["autos_CP"], t_CP=nb["autos_CP"] / ns["autos_CP"])
    checks.append(chk); print(chk, flush=True)
    # identification: car driver is available only with a licence, so the licence terms of all non-reference modes and their
    # constants move together (V_a + d (1 - lic) leaves every probability unchanged); LL after the shift, and the refit with the
    # licence term of walk normalised to 0 (same LL); VIF of the other variables with that normalisation
    lic = [p for p in order if p.startswith("lic_")]
    if len(lic) == len([a for a in M.alts if a != "CD"]) - (1 if seg == "school" else 0):
        import importlib; sys.path.insert(0, f"{DEV}/accessibility"); L = importlib.import_module("mode_logsum_new")
        f = {c: df[c].values.astype(float) for c in df.columns if df[c].dtype != object}; bL = L.coef(seg); keep = dict(bL)
        def llL():
            V, AV = L.utilities(seg, f); _, lp = L.logsum_and_logp(seg, V, AV); return float(sum(lp[a][i] * w[i] for i, a in enumerate(df.choice.values)))
        l0 = llL()
        for k in list(bL):
            if k.startswith("lic_"): bL[k] -= 1.0
            if k.startswith("ASC_"): bL[k] += 1.0
        l1 = llL(); bL.clear(); bL.update(keep)
        m = get(["lic_WK"], None, "nolicWK"); nb = dict(zip(m["names"], m["b"])); ns = dict(zip(m["names"], m["se"]))
        rr = CA.check_row(model, "licence vs constants (identification)", "licence on walk normalised to 0", base, m, "lic_CP"); crow.append(rr)
        vn2 = [v for v in vn if v != "lic_WK"]; R2, _ = CA.within_corr_partial(M.design(vn2), av, w, P); vf2 = CC.vif(R2)
        for v, x in zip(vn2, vf2):
            if x >= CC.VIF_MAX: crow.append(dict(model=model, pair=f"CHECK: VIF with licence on walk normalised: {labels[v]}", p1=v, source="VIF", VIF=x))
        checks.append(dict(check="licence vs constants (identification)", LL_final=l0, LL_after_shift_constants_plus1_licence_minus1=l1, dLL=l1 - l0,
                           LL_licence_walk_normalised=m["LL"], dLL_refit=m["LL"] - base["LL"],
                           lic_after=dict((p, (round(nb[p], 4), round(nb[p] / ns[p], 2))) for p in lic if p in nb),
                           lic_contrast_final=dict((p, round(float(base["b"][bi[p]] - base["b"][bi["lic_WK"]]), 4)) for p in lic if p != "lic_WK"),
                           max_vif_normalised=float(np.nanmax(vf2)), vif_normalised=dict(zip(vn2, np.round(vf2, 2)))))
        print(checks[-1], flush=True)
    elif lic:   # 2026-11-09 re-run: licence already normalised to 0 on walk in the final model; confirm the licence VIF is finite
        vl = {p: float(vf[vi[p]]) for p in lic}; erl = {f"{p}/{q}": round(float(Re[bi[p], bi[q]]), 3) for p in lic for q in order if q.startswith("ASC_")}
        checks.append(dict(check="licence normalised on walk (identification)", lic_terms=lic, vif_lic=vl, all_finite=bool(np.all(np.isfinite(list(vl.values())))),
                           max_abs_est_r_lic_ASC=float(max(abs(x) for x in erl.values())), est_r_lic_ASC=erl))
        crow.append(dict(model=model, pair="CHECK: licence normalised on walk: max VIF of licence terms", source="VIF", VIF=max(vl.values())))
        print(checks[-1], flush=True)
    CA.save_part(model, Pp.to_dict("records") + ref + crow,
                 dict(LL=base["LL"], LL_reported=M.LLrep, K=base["K"], N=M.N, max_vif=float(np.nanmax(vf)), vif=dict(zip(vn, np.round(vf, 2))), checks=checks,
                      person_row_corr_CP=Rp["CP"].round(3).to_dict()))


if __name__ == "__main__":
    WD = os.environ.get("BIO_WD", "/private/tmp/claude-501/c_abit_mode_bio"); os.makedirs(WD, exist_ok=True)
    import shutil; shutil.copy(f"{MC}/bio/biogeme.toml", WD); os.chdir(WD)        # Biogeme settings of the estimation; scratch files outside the project
    for s in sys.argv[1:] or ["work", "shopping", "other", "school"]: one(s)
