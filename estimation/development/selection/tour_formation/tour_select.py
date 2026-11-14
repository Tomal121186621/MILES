#!/usr/bin/env python3
"""Tour formation of ABIT under one base specification (re-specification 2026-11-06): outing generation (at least one outing
during a work episode at the usual workplace), outing mode (walk against the mode of the work tour) and return home between two
consecutive out-of-home episodes.  Binary logits, maximum likelihood (statsmodels), robust (HC0) standard errors; estimation half,
hold-out = validation half of the RTS.

    python3 estimation/development/selection/tour_formation/tour_select.py      -> selection_log.csv, final_<model>.csv, robustness.csv, holdout_checks.csv, work/final_<model>.pkl

Common blocks (RESPEC_PROTOCOL.md):  1 constant; 2 impedance (distance terms of the decision); 4 attributes of the episode / place;
7 person and household: the SAME eight terms in all three models (age < 30, age 55+, female, household income < $50k, >= $100k,
no car, fewer cars than licensed drivers, child under 16 in the household); return home adds the person types of the model of record.
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2
V = f"{WORKSPACE}"
TE = f"{V}/3_abit/tasha_estimation"; A3 = f"{V}/3_abit"; HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/abit/tour_formation"   # data
TE_CODE = f"{TERP_HOME}/activity/lib/tasha_estimation"
sys.path.insert(0, TE_CODE)
import te_common as T            # noqa: E402
import dc_common as C            # noqa: E402
os.makedirs(f"{HERE}/work", exist_ok=True)

PERSON = ["age_u30", "age_55p", "female", "inc_low", "inc_high", "car0", "carshort", "kids"]
TCRIT = 1.96
MODELS = {
    "gen": dict(base=["const", "lncomm", "sp_0_4", "sp_4_7", "sp_7_inf", "arr_early", "arr_late", "sw", "cbd_w"] + PERSON,
                cands=[(4, "lnacc2", "+"), (4, "lnretden_w", "+"), (4, "mix_w", "+"), (4, "rail_w", "+"), (4, "lnstopden_w", "+")],
                prior={"lncomm": "-", "sp_0_4": "+", "sp_4_7": "+", "cbd_w": "+"}),
    "mode": dict(base=["const", "lnkm", "tm_cd", "tm_cp", "cbd_w"] + PERSON,
                 cands=[(4, "lnretden_w", "+"), (4, "mix_w", "+"), (4, "rail_w", "+"), (4, "lnstopden_w", "+")],
                 prior={"lnkm": "-", "tm_cd": "-", "tm_cp": "-", "cbd_w": "+"}),
    "rh": dict(base=["const", "detour_km", "lndetour", "dhome_km", "a_work", "a_school", "a_acc", "a_shop", "a_joint", "e_work", "e_school", "e_acc", "e_shop",
                     "e_joint", "jj", "jmand", "nep3", "nep4", "nep5", "am", "pm", "ev", "worker", "stud_k12", "stud_ps", "retiree", "toddler"] + PERSON,
               cands=[(4, "core_h", "+"), (4, "rural_h", "-")],
               prior={"lndetour": "-"}),
}


def persons(half):
    pm = pd.read_csv(f"{A3}/survey_pop/{half}/persons_map.csv").drop_duplicates("person_id").set_index("person_id")
    pp = pd.read_csv(f"{A3}/survey_pop/{half}/pp.csv").set_index("id"); hh = pd.read_csv(f"{A3}/survey_pop/{half}/hh.csv").set_index("id")
    hp = pp.groupby("hhID").agg(drivers=("driversLicense", lambda x: x.astype(str).eq("True").sum()), minage=("age", "min"), inc=("income", "sum"))
    out = pd.DataFrame(index=pm.index); pid = pm.id; hid = pid.map(pp.hhID)
    age = pid.map(pp.age); inc = hid.map(hp.inc); cars = hid.map(hh.autos); drv = hid.map(hp.drivers)
    out["age_u30"] = (age < 30).astype(float); out["age_55p"] = (age >= 55).astype(float); out["female"] = pid.map(pp.gender).eq(2).astype(float)
    out["inc_low"] = (inc < 50000).astype(float); out["inc_high"] = (inc >= 100000).astype(float)
    out["car0"] = (cars <= 0).astype(float); out["carshort"] = ((cars > 0) & (cars < drv)).astype(float); out["kids"] = (hid.map(hp.minage) < 16).astype(float)
    out["household_id"] = pm.household_id
    return out


def zone_extra():
    z = C.zones(); e = pd.read_csv(f"{V}/side_experiments/respec_2026-11/abit/zone_extras.csv"); m = C.id2idx()
    return z, e, m


def data(model, half):
    P = persons(half); z, e, m = zone_extra()
    if model == "gen":
        X = pd.read_parquet(f"{TE}/work/wbs_{half}.parquet"); w = pd.read_parquet(f"{TE}/work/wbs_w_{half}.parquet")
        assert (X.person_id.values == w.person_id.values).all()
        wi = m[w.wz.values]
        X["lnretden_w"] = z.lnretden.values[wi]; X["mix_w"] = z.mix.values[wi]; X["rail_w"] = e.rail.values[wi]; X["lnstopden_w"] = e.lnstopden.values[wi]
    elif model == "mode":
        sys.path.insert(0, TE_CODE); import estimate_subtours as S
        o = pd.read_parquet(f"{TE}/work/wbs_out_{half}.parquet"); zz, d, acc = S.zone_tables()
        o = o[o.tour_mode.notna() & o["mode"].notna()].copy()
        z1 = o.zones.str.split(";").str[0].astype(int); ok = (z1 > 0) & (o.wz > 0); o = o[ok.values].copy(); z1 = z1[ok.values]; wi = m[o.wz.values]
        X = pd.DataFrame({"const": 1.0, "tm_cd": o.tour_mode.eq("CAR_DRIVER").astype(float).values, "tm_cp": o.tour_mode.eq("CAR_PASSENGER").astype(float).values,
                          "lnkm": np.log1p(d[wi, m[z1.values]]), "lnretden_w": z.lnretden.values[wi], "cbd_w": z.cbd.values[wi], "mix_w": z.mix.values[wi],
                          "rail_w": e.rail.values[wi], "lnstopden_w": e.lnstopden.values[wi],
                          "y": o["mode"].eq("WALK").astype(float).values, "w": o.w.values, "person_id": o.person_id.values})
    else:
        import estimate_return_home as R
        p = R.pairs(half); p = p[~p.workwork].copy()
        X = R.design(p); X["y"] = p.y.values; X["w"] = p.w.values; X["person_id"] = p.person_id.values
        hz = m[p.hz.values]; X["core_h"] = (z.bbsr.values[hz] == 10).astype(float); X["rural_h"] = (z.bbsr.values[hz] == 40).astype(float)
        X["seg"] = p.seg.values; X["nep"] = p.nep.values
    X = X.reset_index(drop=True)
    pj = P.reindex(X.person_id.values)
    for c in PERSON + ["household_id"]:
        if c in X and c != "household_id": X[c + "_orig"] = X[c]
        X[c] = pj[c].values
    X = X[X.household_id.notna()].reset_index(drop=True)
    return X


def fit(X, cols, w=None):
    if w is None: return sm.Logit(X.y.values, X[cols].values.astype(float)).fit(disp=0, maxiter=300, cov_type="HC0")
    return sm.GLM(X.y.values, X[cols].values.astype(float), family=sm.families.Binomial(), freq_weights=w).fit()


def ll(X, cols, b):
    v = X[cols].values @ b; p = 1 / (1 + np.exp(-v)); y = X.y.values
    return float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1)))), p


def sign_ok(v, s): return s == "0" or (s == "+" and v > 0) or (s == "-" and v < 0)


def bic(m, n): return np.log(n) * len(m.params) - 2 * m.llf


def run(model):
    spec = MODELS[model]; est = data(model, "estimation"); val = data(model, "validation"); log = []
    cols = [c for c in spec["base"] if c == "const" or est[c].std() > 0]
    m = fit(est, cols); n = len(est)
    while True:
        bad = [(c, m.tvalues[i]) for i, c in enumerate(cols) if c in spec["prior"] and not sign_ok(m.params[i], spec["prior"][c]) and abs(m.tvalues[i]) > 2]
        if not bad: break
        c, t = max(bad, key=lambda z: abs(z[1])); cols = [k for k in cols if k != c]; m = fit(est, cols)
        log.append(dict(model=model, round=0, candidate=c, rob_t=t, decision="base term dropped: wrong sign, |t| > 2"))
    ho = ll(val, cols, m.params)[0]
    log.append(dict(model=model, round=0, candidate="base", LL_after=m.llf, BIC_after=bic(m, n), holdout_LL_after=ho, decision="base"))
    for block, c, s in spec["cands"]:
        if est[c].std() == 0: continue
        m2 = fit(est, cols + [c]); h2 = ll(val, cols + [c], m2.params)[0]; v = m2.params[-1]; t = m2.tvalues[-1]
        kept = sign_ok(v, s) and abs(t) >= TCRIT and bic(m2, n) < bic(m, n) and h2 > ho
        why = "kept" if kept else "wrong sign" if not sign_ok(v, s) else f"|t| < {TCRIT}" if abs(t) < TCRIT else "BIC not lower" if bic(m2, n) >= bic(m, n) else "hold-out LL not higher"
        log.append(dict(model=model, round=1, block=block, candidate=c, expected=s, estimate=v, rob_t=t, LL_before=m.llf, LL_after=m2.llf, LR=2 * (m2.llf - m.llf),
                        BIC_before=bic(m, n), BIC_after=bic(m2, n), holdout_LL_before=ho, holdout_LL_after=h2, decision=why))
        print(f"  [{model}] {c}: {v:+.4f} (t {t:.2f}) dBIC {bic(m2, n) - bic(m, n):+.1f} dHO {h2 - ho:+.2f} -> {why}", flush=True)
        if kept: cols, m, ho = cols + [c], m2, h2
    # backward check of non-base terms
    while True:
        weak = [(c, m.tvalues[i]) for i, c in enumerate(cols) if c not in spec["base"] and abs(m.tvalues[i]) < TCRIT]
        if not weak: break
        c, t = min(weak, key=lambda z: abs(z[1])); cols = [k for k in cols if k != c]; m = fit(est, cols); ho = ll(val, cols, m.params)[0]
        log.append(dict(model=model, round=3, candidate=c, rob_t=t, decision="removed in the backward check"))
    return est, val, cols, m, ho, log


def robustness(model, est, val, cols, m, ho, B=100, seed=5):
    n = len(est); tab = pd.DataFrame({"variable": cols, "value": m.params, "rob_se": m.bse, "rob_t": m.tvalues, "p": m.pvalues})
    # household-cluster s.e. (sandwich) and bootstrap with re-estimation
    mc = sm.Logit(est.y.values, est[cols].values.astype(float)).fit(disp=0, maxiter=300, cov_type="cluster", cov_kwds=dict(groups=pd.factorize(est.household_id)[0]))
    tab["cluster_se"] = mc.bse
    u, inv = np.unique(est.household_id.values, return_inverse=True); rng = np.random.default_rng(seed); draws = []
    for b in range(B):
        k = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))[inv]
        idx = np.repeat(np.arange(n), k); Xb = est.iloc[idx]
        try: draws.append(sm.Logit(Xb.y.values, Xb[cols].values.astype(float)).fit(disp=0, maxiter=300, start_params=m.params).params)
        except Exception: pass
    tab["boot_se"] = np.std(np.array(draws), axis=0, ddof=1)
    # swap halves, pooled
    mv = fit(val, cols); mp = fit(pd.concat([est, val]), cols)
    tab["value_swap"] = mv.params; tab["se_swap"] = mv.bse; tab["z_diff"] = (m.params - mv.params) / np.sqrt(m.bse ** 2 + mv.bse ** 2)
    LR = 2 * (m.llf + mv.llf - mp.llf); df = len(cols)
    cov = m.cov_params(); sd = np.sqrt(np.diag(cov)); R = cov / np.outer(sd, sd)
    flags = [(cols[i], cols[j], float(R[i, j])) for i in range(len(cols)) for j in range(i + 1, len(cols)) if abs(R[i, j]) > 0.9]
    Hn = est[cols].values.T @ (est[cols].values * (m.predict() * (1 - m.predict()))[:, None])
    Lc = sm.Logit(est.y.values, np.ones((n, 1))).fit(disp=0).llf
    return dict(model=model, cols=cols, table=tab, LL=m.llf, LLc=Lc, LL0=n * np.log(0.5), K=len(cols), N=n, N_val=len(val), holdout=ho,
                holdout_const=ll(val, ["const"], np.array([np.log(est.y.mean() / (1 - est.y.mean()))]))[0],
                swap=dict(LL_est=m.llf, LL_val=mv.llf, LL_pooled=mp.llf, LR=LR, df=df, p=float(chi2.sf(LR, df)), n_z_gt_196=int((np.abs(tab.z_diff) > 1.96).sum())),
                corr_flags=flags, cond=float(np.linalg.cond(Hn)), nboot=len(draws), weighted_share_val=(float(np.average(val.y, weights=val.w)),
                float(np.average(ll(val, cols, m.params)[1], weights=val.w))))


def current_holdout(model, val):
    """the model of record on the same hold-out records"""
    if model == "rh":
        t = pd.read_csv(f"{TE}/results/rh_nogap_estimates.csv"); c = list(t.variable); b = t.value.values
    else:
        t = pd.read_csv(f"{TE}/results/wbs_{'gen' if model == 'gen' else 'mode'}_estimates.csv"); c = list(t.variable); b = t.value.values
    Xv = val.copy()
    for k in c:
        if k + "_orig" in Xv: Xv[k] = Xv[k + "_orig"]           # the model of record with its own person variables
    return ll(Xv, c, b)[0], len(c), dict(zip(c, b))


def main():
    rows, logs = [], []; checks = []
    for model in ["gen", "mode", "rh"]:
        est, val, cols, m, ho, log = run(model); logs += log
        r = robustness(model, est, val, cols, m, ho); r["log"] = log
        hc, kc, bcur = current_holdout(model, val); r["holdout_current"] = hc; r["K_current"] = kc
        r["est_current"] = current_holdout(model, est)[0]
        pickle.dump(r, open(f"{HERE}/work/final_{model}.pkl", "wb")); r["table"].to_csv(f"{HERE}/final_{model}.csv", index=False)
        rows.append(dict(model=model, N=r["N"], K=r["K"], LL=r["LL"], LLc=r["LLc"], BIC=np.log(r["N"]) * r["K"] - 2 * r["LL"], holdout_LL=ho, holdout_LL_current=hc, K_current=kc,
                         swap_LR=r["swap"]["LR"], swap_df=r["swap"]["df"], swap_p=r["swap"]["p"], n_z_gt_196=r["swap"]["n_z_gt_196"], corr_flags=len(r["corr_flags"]),
                         cond=r["cond"], nboot=r["nboot"], obs_share_val=r["weighted_share_val"][0], pred_share_val=r["weighted_share_val"][1]))
        # aggregate checks on the hold-out half
        p = ll(val, cols, m.params)[1]; Xv = val.assign(p=p)
        groups = {"gen": ["cbd_w", "female", "age_u30", "car0"], "mode": ["tm_cd", "cbd_w"], "rh": ["worker", "nep3", "nep5", "e_work", "car0"]}[model]
        for g in groups:
            for lev, x in Xv.groupby(g): checks.append(dict(model=model, group=g, level=lev, N=len(x), observed=np.average(x.y, weights=x.w), predicted=np.average(x.p, weights=x.w)))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{HERE}/robustness.csv", index=False); pd.DataFrame(logs).to_csv(f"{HERE}/selection_log.csv", index=False)
    pd.DataFrame(checks).to_csv(f"{HERE}/holdout_checks.csv", index=False)


if __name__ == "__main__":
    main()
