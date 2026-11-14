#!/usr/bin/env python3
"""Collinearity of the final activity models (tour_formation/a01_outing.py, a02_outing_mode.py, a03_return.py; spec = 'final' step of
a0*_coef.csv), estimation half.  All three are binary logits with person / episode variables on one row per choice situation,
estimated unweighted: variable correlations over the estimation rows, unweighted (as c_silo_cars.py), VIF over the free
coefficients (constant excluded).  Estimate correlations from the robust (sandwich, HC0) covariance at the final estimates
(Biogeme robust for a01 / a02, statsmodels HC0 for a03: the same formula, checked against the reported s.e.).
Centring: all variables centred at their mean is an exact reparametrisation (constant' = constant + sum mean_k b_k); the
constant / variable estimate pairs are reported after it.
    ~/.venvs/biogeme/bin/python estimation/development/collinearity/c_abit_activity.py a01 a02;  python3 estimation/development/collinearity/c_abit_activity.py a03
      ->  a0x_<name>_var_corr.png / _est_corr.png / _var_corr.csv / _est_corr.csv / _pairs.csv / _facts.json"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; SB = os.path.dirname(HERE); ACT = os.path.join(SB, "activity")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, f"{DEV}/tour_formation"); sys.path.insert(0, CODE)
import c_abit_common as CA   # noqa: E402

TEX = {"a01": f"{SB}/tables_new/est_subtour_new.tex", "a02": f"{SB}/tables_new/est_subtour_new.tex", "a03": f"{SB}/tables_new/est_return_new.tex"}
CAP = {"a01": "binary logit of at least one outing", "a02": "binary logit of walking", "a03": "Return-home logit"}
TITLE = {"a01": "Outing from the workplace (generation), final model", "a02": "Outing mode (walk vs work-tour mode), final model",
         "a03": "Return home between episodes, final model"}
NAME = {"a01": "a01_outing", "a02": "a02_outing_mode", "a03": "a03_return"}
SETS = {"a01": [({"sp_0_4", "sp_4_7", "sp_7_inf"}, "adjacent piecewise segments of work duration"),
                ({"arr_early", "arr_late"}, "dummies of one categorical variable (arrival time)")],
        "a02": [({"tm_cd", "tm_cp"}, "dummies of one categorical variable (work-tour mode)"), ({"car0", "carshort"}, "dummies of one categorical variable (cars)")],
        "a03": [({"detour_km", "lndetour"}, "functional form of one variable (detour and ln(1 + detour))"),
                ({"am", "pm", "ev"}, "dummies of one categorical variable (time of day)"),
                ({"inc_low", "inc_high"}, "dummies of one categorical variable (income)"),
                ({"worker", "stud_k12", "stud_ps", "retiree", "toddler"}, "dummies of one categorical variable (person type)"),
                ({"a_work", "a_school", "a_acc", "a_shop", "a_joint"}, "dummies of one categorical variable (preceding purpose)"),
                ({"e_work", "e_school", "e_acc", "e_shop", "e_joint"}, "dummies of one categorical variable (following purpose)"),
                ({"car0", "carshort"}, "dummies of one categorical variable (cars)")]}   # 2026-11-09 re-run: band sets restored (school, car0)


def tex_rows(path, caption):
    """{rounded coefficient: plain label} of the table whose caption contains `caption`"""
    txt = open(path).read(); i = txt.index(caption); j = txt.find("\\end{longtable}", i); out = {}
    for line in txt[i:j].splitlines():
        if "&" not in line or "reference" in line or "Variable &" in line: continue
        cells = line.split("&"); m = re.search(r"(\$-\$)?([0-9.]+)", cells[1])
        if not m: continue
        v = float(m.group(2)) * (-1 if m.group(1) else 1); out[round(v, 4)] = CA.plain(cells[0].strip())
    return out


def sandwich(X, y, b):
    p = 1 / (1 + np.exp(-(X @ b))); H = (X * (p * (1 - p))[:, None]).T @ X; G = X * (y - p)[:, None]; Hi = np.linalg.inv(H)
    return Hi @ (G.T @ G) @ Hi


def loader(key):
    if key == "a03":   # statsmodels (python3)
        import a03_return as A3
        X, y = A3.load("estimation"); return X, y, lambda cols: A3.fit(X, y, cols)
    import a01_outing as A1, a02_outing_mode as A2   # Biogeme (~/.venvs/biogeme/bin/python)
    A1.ES.BIO = os.environ.get("C_ABIT_BIO", "/private/tmp/claude-501/c_abit_bio")   # Biogeme working files outside the project
    X = (A1 if key == "a01" else A2).load("estimation"); return X, X.y.values.astype(float), lambda cols: A1.fit(X, cols)


def one(key):
    model = NAME[key]; fr = pd.read_csv(f"{ACT}/{model}_fit.csv"); fin = fr[fr.step == "final"].iloc[0]
    co = pd.read_csv(f"{ACT}/{model}_coef.csv"); co = co[co.step == "final"]; cols = list(co.param)
    X, y, fitf = loader(key); N = len(y)

    def run(cs):
        r = fitf(list(cs)); b = r["b"].reindex(cs).values.astype(float); cov = sandwich(X[cs].values.astype(float), y, b)
        assert np.allclose(np.sqrt(np.diag(cov)), r["se"].reindex(cs).values, rtol=2e-3), "sandwich s.e. differ from the reported robust s.e."
        return dict(LL=r["LL"], K=r["K"], N=N, names=list(cs), b=b, se=np.sqrt(np.diag(cov)), cov=cov)

    base = run(cols); print(model, "LL", base["LL"], "reported", fin.LL, flush=True); assert abs(base["LL"] - fin.LL) < 0.1
    assert np.allclose(base["b"], co.coef.values, atol=1e-3)
    tl = tex_rows(TEX[key], CAP[key]); lab = {}
    for n, v in zip(cols, co.coef.values):
        lab[n] = tl.get(round(v, 4)) or tl.get(round(v, 4) + 1e-4) or tl.get(round(v, 4) - 1e-4); assert lab[n], (n, v)
    V = [c for c in cols if c != "const"]; Xv = X[V].values.astype(float); w = np.ones(N)
    R = CA.wcorr(Xv, w); vf = CA.vif(R)
    CA.heatmap(R, [lab[v] for v in V], f"{CA.OUT}/{model}_var_corr.png",
               f"{TITLE[key]}: correlations of the explanatory variables\nestimation half ({N:,} rows), unweighted as in estimation", "Correlation (estimation rows)")
    Re = CA.est_corr(base["cov"])
    CA.heatmap(Re, [lab[n] for n in cols], f"{CA.OUT}/{model}_est_corr.png",
               f"{TITLE[key]}: correlations of the estimates (robust covariance)\nestimation half, LL {base['LL']:,.1f}, {base['K']} parameters", "Correlation of the estimates")
    pd.DataFrame(R, index=V, columns=V).round(3).to_csv(f"{CA.OUT}/{model}_var_corr.csv")
    pd.DataFrame(Re, index=cols, columns=cols).round(3).to_csv(f"{CA.OUT}/{model}_est_corr.csv")
    # centred reparametrisation: const' = const + sum_k mean_k b_k
    T = np.eye(len(cols)); i0 = cols.index("const")
    for v in V: T[i0, cols.index(v)] += X[v].mean()
    Rc = CA.est_corr(T @ base["cov"] @ T.T)

    def kind(a, b):
        if "const" in (a, b): return "STRUCTURAL", "constant vs uncentred variable", True
        t, why, cen = CA.classify(a, b, {}, SETS[key]); return t, why, cen

    vi = {v: i for i, v in enumerate(V)}; rows = []
    for a, b, r in CA.pairs(R, V, CA.R_VAR):
        t, why, _ = kind(a, b)
        rows.append(dict(model=model, pair=f"{lab[a]} / {lab[b]}", p1=a, p2=b, source="variables", type=t, why=why, var_r=r, est_r=Re[cols.index(a), cols.index(b)]))
    for v, x in zip(V, vf):
        if x >= CA.VIF_MAX: rows.append(dict(model=model, pair=lab[v], p1=v, source="VIF", VIF=x))
    for a, b, r in CA.pairs(Re, cols, CA.R_EST):
        t, why, cen = kind(a, b); ia, ib = cols.index(a), cols.index(b)
        rows.append(dict(model=model, pair=f"{lab[a]} / {lab[b]}", p1=a, p2=b, source="estimates", type=t, why=why, est_r=r,
                         var_r=R[vi[a], vi[b]] if a in vi and b in vi else np.nan, est_r_centred=Rc[ia, ib] if "const" in (a, b) else np.nan,
                         centring_removes=(abs(Rc[ia, ib]) < CA.R_EST) if "const" in (a, b) else np.nan))
    P = pd.DataFrame(rows)
    for c in ["why", "est_r_centred", "centring_removes", "VIF"]:
        if c not in P: P[c] = np.nan
    if len(P):
        P["VIF_p1"] = [vf[vi[x]] if x in vi else np.nan for x in P.p1]
        P["VIF_p2"] = [vf[vi[x]] if isinstance(x, str) and x in vi else np.nan for x in P.p2]
    need = P[(P.source != "VIF") & ((P.type == "SUBSTANTIVE") | P.why.astype(str).str.startswith("functional form") |
                                   (P.centring_removes == False))] if len(P) else P   # noqa: E712
    ref, done, cache = [], set(), {}

    def refit_drop(d):
        k = tuple(sorted(d))
        if k not in cache: cache[k] = run([c for c in cols if c not in d])
        return cache[k]

    for _, q in need.iterrows():
        a, b = q.p1, q.p2
        if frozenset((a, b)) in done or "const" in (a, b): continue
        done.add(frozenset((a, b)))
        for lab_, d, follow in [(f"without {a}", a, b), (f"without {b}", b, a)]:
            rr = CA.refit_row(base, refit_drop([d]), follow, lab_); rr.update(model=model, pair=q.pair); ref.append(rr)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rr.items()}, flush=True)
    facts = dict(LL=base["LL"], LL_reported=float(fin.LL), K=base["K"], N=N, max_vif=float(vf.max()), vif=dict(zip(V, vf.round(2))),
                 weights="unweighted (as estimated)")
    CA.save_part(model, P.to_dict("records") + ref, facts)
    if key == "a03": a03_check(model, base, R, Re, vi, cols, lab, refit_drop, X)
    print(P.drop(columns=["pair"]).round(3).to_string() if len(P) else "no flags")


def a03_check(model, base, R, Re, vi, cols, lab, refit_drop, X):
    """distance from home (+) vs detour via home and ln(1 + detour): correlations and the refit without distance from home"""
    alt = refit_drop(["dhome_km"]); rows, checks = [], []
    bi = dict(zip(base["names"], zip(base["b"], base["se"]))); ai = dict(zip(alt["names"], zip(alt["b"], alt["se"])))
    for m in ["detour_km", "lndetour"]:
        r = CA.check_row(model, "distance from home vs detour via home", "without distance from home", base, alt, m,
                         var_r=R[vi["dhome_km"], vi[m]], est_r=Re[cols.index("dhome_km"), cols.index(m)], p1="dhome_km", p2=m)
        rows.append(r)
    sp = {f"spearman_{m}": float(pd.Series(X["dhome_km"]).corr(pd.Series(X[m]), method="spearman")) for m in ["detour_km", "lndetour"]}
    checks.append(dict(check="distance from home vs detour via home", var_r_detour_km=R[vi["dhome_km"], vi["detour_km"]],
                       var_r_lndetour=R[vi["dhome_km"], vi["lndetour"]], var_r_detour_lndetour=R[vi["detour_km"], vi["lndetour"]],
                       est_r_detour_km=Re[cols.index("dhome_km"), cols.index("detour_km")], est_r_lndetour=Re[cols.index("dhome_km"), cols.index("lndetour")],
                       b_dhome=bi["dhome_km"][0], t_dhome=bi["dhome_km"][0] / bi["dhome_km"][1], LL_without=alt["LL"], dLL=alt["LL"] - base["LL"],
                       dBIC=rows[0]["dBIC"], LR=rows[0]["LR"], p=rows[0]["p"], sign_changes=rows[0]["sign_changes"],
                       detour_km_before=bi["detour_km"], detour_km_after=ai["detour_km"], lndetour_before=bi["lndetour"], lndetour_after=ai["lndetour"],
                       mean_dhome=float(X.dhome_km.mean()), mean_detour=float(X.detour_km.mean()), **sp))
    print(checks[-1], flush=True); CA.append_checks(model, rows, checks)


if __name__ == "__main__":
    for k in sys.argv[1:] or ["a01", "a02", "a03"]: one(k)
