#!/usr/bin/env python3
"""Collinearity of the final car-ownership model (car_ownership/s07_sequence.py 'final', est_cars_new.tex), estimation sample.
Variables are household attributes entering alternative-specific utilities: correlations over the household rows, unweighted as
in the estimation (mnl.fit is unweighted).  Estimate correlations from the robust (sandwich) covariance at the final estimates.
    python3 estimation/development/collinearity/c_silo_cars.py   ->  cars_var_corr.png, cars_est_corr.png, cars_pairs.csv, cars_facts.json"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/collinearity"; CO = os.path.join(os.path.dirname(HERE), "car_ownership")
DEV = os.path.dirname(CODE)   # estimation/development (code of the estimation steps)
sys.path.insert(0, os.path.join(DEV, "car_ownership")); sys.path.insert(0, CODE)
from mnl import fit, probs, design   # noqa: E402
from s04_form import pieces   # noqa: E402
from s06_age import oldest_age, prep   # noqa: E402  (2026-11-10: age of the oldest member, s08_oldest_age.py)
import t_final_table as TT   # noqa: E402
import c_silo_common as CC   # noqa: E402

PIECES = ["inc_lt25", "inc_25_50", "inc_50_100", "inc_gt100"]


def robust_cov(r, d, vs):
    """sandwich covariance of mnl.fit (same formulas as mnl.fit, which returns only the s.e.)"""
    X = design(d, vs); Y = np.eye(4)[d.cars.values]; K = X.shape[1]; P = probs(r["b"], X); H = np.zeros((3 * K, 3 * K))
    for a in range(3):
        for c in range(3):
            s = P[:, a + 1] * ((a == c) - P[:, c + 1]); H[a * K:(a + 1) * K, c * K:(c + 1) * K] = (X * s[:, None]).T @ X
    G = np.concatenate([X * (Y[:, a + 1] - P[:, a + 1])[:, None] for a in range(3)], axis=1); Hi = np.linalg.inv(H)
    return Hi @ (G.T @ G) @ Hi


def res(r, d, vs):
    return dict(LL=r["LL"], K=r["K"], N=r["N"], names=r["names"], b=r["b"], se=r["se"])


def main():
    d = pd.read_parquet(f"{CO}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    md = d.ln_density.mean(); d = prep(d, md, oldest_age()); pieces(d)
    sf = pd.read_csv(f"{CO}/s07_fit.csv"); fin = sf[sf.step == "final"].iloc[0]; V = fin.spec.split()
    V = [v for v in TT.ORDER if v in V]                     # table order
    r = fit(d, V); print("LL", r["LL"], "reported", fin.LL, "diff", r["LL"] - fin.LL, flush=True)
    assert abs(r["LL"] - fin.LL) < 0.1
    cov = robust_cov(r, d, V); assert np.allclose(np.sqrt(np.diag(cov)), r["se"], rtol=1e-6)
    lab = {v: CC.plain(TT.LAB[v]) for v in ["constant"] + V}
    # (a) variable correlations over the household rows, unweighted, and VIF
    X = d[V].values.astype(float); w = np.ones(len(d)); R = CC.wcorr(X, w); vf = CC.vif(R)
    CC.heatmap(R, [lab[v] for v in V], f"{HERE}/cars_var_corr.png",
               f"Car ownership, final model: correlations of the explanatory variables\nACS PUMS 2014–2018 Maryland households, estimation sample ({len(d):,}), unweighted as in estimation",
               "Correlation (household rows)")
    # (b) estimate correlations, robust covariance
    Re = CC.est_corr(cov); alt = {"1": "1 car", "2": "2 cars", "3+": "3+ cars"}
    elab = [f"{alt[n.split('|')[1]]}: {lab[n.split('|')[0]]}" for n in r["names"]]
    CC.heatmap(Re, elab, f"{HERE}/cars_est_corr.png",
               f"Car ownership, final model: correlations of the estimates (robust covariance)\nestimation sample, LL {r['LL']:,.1f}, {r['K']} parameters",
               "Correlation of the estimates")
    pd.DataFrame(R, index=V, columns=V).round(3).to_csv(f"{HERE}/cars_var_corr.csv"); pd.DataFrame(Re, index=r["names"], columns=r["names"]).round(3).to_csv(f"{HERE}/cars_est_corr.csv")

    # centring checks: interacting variables centred at their sample mean (unweighted)
    inc_c = d.ln_income - d.ln_income.mean(); age_m = d.age10.mean()
    def var_corr_centred(a, b):
        """correlation of a and b after centring the interacting variable of the structural pair"""
        x = {v: d[v].values.astype(float) for v in V}
        if "inc_x_dens" in (a, b):
            x["inc_x_dens"] = (inc_c * (d.ln_density - md)).values
            if a in PIECES or b in PIECES:   # interaction of income with density: density is the interacting variable, already centred
                x["inc_x_dens"] = (d.ln_income * (d.ln_density - md)).values
        if {a, b} == {"age10", "age10_sq"}:
            x["age10_sq"] = (d.age10 - age_m).values ** 2; x["age10"] = (d.age10 - age_m).values
        return float(np.corrcoef(x[a], x[b])[0, 1])

    def kind(a, b):
        s = {a, b}
        if s <= set(PIECES):
            i, j = sorted(PIECES.index(v) for v in s); return "STRUCTURAL", "adjacent piecewise segments" if j - i == 1 else "piecewise segments (non-adjacent)"
        if "inc_x_dens" in s and (s & ({"ln_density"} | set(PIECES))): return "STRUCTURAL", "main effect vs its own interaction"
        if s == {"age10", "age10_sq"}: return "STRUCTURAL", "age and its square (main effect vs its own interaction)"
        return "SUBSTANTIVE", ""

    rows = []; base = res(r, d, V)
    for a, b, rv in CC.pairs(R, V, CC.R_VAR):
        t, why = kind(a, b); rows.append(dict(model="cars", pair=f"{lab[a]} / {lab[b]}", p1=a, p2=b, source="variables", type=t, why=why, var_r=rv,
                                              var_r_centred=var_corr_centred(a, b) if "interaction" in why or "square" in why else np.nan))
    for v, x in zip(V, vf):
        if x >= CC.VIF_MAX: rows.append(dict(model="cars", pair=lab[v], p1=v, source="VIF", VIF=x))
    for a, b, re_ in CC.pairs(Re, r["names"], CC.R_EST):
        va, aa = a.split("|"); vb, ab = b.split("|")
        if va == vb: t, why = "STRUCTURAL", "same variable in two alternatives (common reference: no car)"
        elif "constant" in (va, vb): t, why = "STRUCTURAL", "constant vs uncentred variable (same alternative)" if aa == ab else "constant vs variable, different alternatives"
        else: t, why = kind(va, vb); why = why + ("" if aa == ab else ", different alternatives")
        rows.append(dict(model="cars", pair=f"{elab[r['names'].index(a)]} / {elab[r['names'].index(b)]}", p1=a, p2=b, source="estimates", type=t, why=why, est_r=re_))
    P = pd.DataFrame(rows); P["est_r"] = P.get("est_r", np.nan).astype(object)
    # estimate correlations after centring (exact linear reparametrisation, LL unchanged): every variable centred at its mean ->
    # constant_a' = constant_a + sum_k mean_k b_k,a ; and ln income centred in the interaction -> ln_density_a' = ln_density_a + mean(ln inc) b_x,a
    names = r["names"]; T = np.eye(len(names)); mu = {v: d[v].mean() for v in V}
    for a in ["1", "2", "3+"]:
        i0 = names.index(f"constant|{a}")
        for v in V: T[i0, names.index(f"{v}|{a}")] += mu[v]
        T[names.index(f"ln_density|{a}"), names.index(f"inc_x_dens|{a}")] += d.ln_income.mean()
        T[names.index(f"age10|{a}"), names.index(f"age10_sq|{a}")] += 2 * age_m     # age10 centred at its mean in the square too
    Rc = CC.est_corr(T @ cov @ T.T)
    for i, q in P[P.source == "estimates"].iterrows():
        P.loc[i, "est_r_centred"] = Rc[names.index(q.p1), names.index(q.p2)]
    # var-flag pairs: estimate correlations (all three alternatives) for the summary
    for i, q in P[P.source == "variables"].iterrows():
        P.loc[i, "est_r"] = "; ".join(f"{Re[names.index(q.p1 + '|' + a), names.index(q.p2 + '|' + a)]:+.2f}" for a in ["1", "2", "3+"])
    # (e) refits for substantive pairs and structural pairs whose correlation centring does not remove
    need = P[(P.source != "VIF") & ((P.type == "SUBSTANTIVE") | (P.why.str.contains("interaction|square", na=False) &
             (P.var_r_centred.abs().fillna(0).ge(CC.R_VAR) | P.est_r_centred.abs().fillna(0).ge(CC.R_EST))))]
    ref = []; done = set()
    for _, q in need.iterrows():
        a, b = q.p1.split("|")[0], q.p2.split("|")[0]
        if (a, b) in done or a == b or "constant" in (a, b): continue
        done.add((a, b))
        for lab_, drop, keep in [(f"without {a}", a, b), (f"without {b}", b, a)]:
            vs = [v for v in V if v != drop]; m = fit(d, vs)
            for alt_ in ["1", "2", "3+"]:
                ref.append(dict(model="cars", pair=f"{lab[a]} / {lab[b]}", **CC.refit_row(base, res(m, d, vs), f"{keep}|{alt_}", lab_ + f" (followed: {alt_})")))
            print(lab_, m["LL"], flush=True)
    CC.save_part("cars", P.to_dict("records") + ref, dict(LL=r["LL"], LL_reported=float(fin.LL), K=r["K"], N=r["N"], max_vif=float(vf.max()),
                                                           vif=dict(zip(V, vf.round(2)))))
    print(P.to_string()); print(pd.DataFrame(ref).to_string())


if __name__ == "__main__":
    main()
