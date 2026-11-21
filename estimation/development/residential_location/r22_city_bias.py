#!/usr/bin/env python3
"""City-vs-suburb bias of the residential PUMA level (2026-11-19): in-sample check and candidate terms, decided on the ESTIMATION half.

Base: the r20 model (bug-fixed crosswalk, M = stock x turnover, 10 PUMA terms, inclusive value at 1, dwelling level of r20).
Step 1: observed vs model shares by PUMA and county on the estimation half (weighted, as the estimator) and on the hold-out half.
Step 2: candidate blocks, each added alone to the base (all PUMA x household terms, computable in SILO every year unless noted):
  dens_hh   ln dwelling density x single-person household, x household with children, x youngest band (oldest member < 35),
            x oldest member 65+  (4 terms); dens3 without 65+, dens2 single and young only (simplifications)
  dens_inc  ln dwelling density x ln income
  core      core-city share of the PUMA (dwellings in DC or Baltimore City), estimated coefficient
  core2     core (DC, Baltimore City) and inner core (Arlington, Alexandria) shares, two coefficients
  tcbd      ln(1 + car time to the nearest central business district: highest job-density zone of DC / of Baltimore City)
  transit   transit accessibility of the PUMA: ln sum_j jobs_j exp(-0.05 t_pt) (door-to-door transit time, 2024 network), PUMA mean
  mfshare   multifamily share of the PUMA's 2016 dwellings (MF 2-4 and 5+)
  mf_hh     multifamily share x single-person, x children
For each: K, LL, delta LL, LR p, BIC, coefficients (robust s.e.), VIF of the PUMA design, in-sample county residuals.  The hold-out
LL and county residuals are reported after and never used to choose.
    python3 r22_city_bias.py   ->  r22_blocks.csv, r22_block_coef.csv, r22_county_resid.csv, r22_puma_resid.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ["GEO_PZ"] = f"{HERE}/r20_geo_puma_zone.csv"; os.environ["GEO_MZ"] = f"{HERE}/r20_geo_mig_zone.csv"
import r19_final as F   # noqa: E402
import r16_collinearity as Q   # noqa: E402
R = F.R
from mnl import MNL      # noqa: E402
CORE, INNER = [11001, 24510], [51013, 51510]


def designs():
    co = pd.read_csv(f"{HERE}/r20_coef.csv"); b_dw = co[co.level == "dwelling"].set_index("param").coef.reindex(F.DWF).values
    est, val, pool, G = F.setup()
    R.dw_X = F._full; R.sample(est, pool); R.sample(val, pool)
    D, Dv = F.upper_designs(est, val, pool, b_dw, G)
    k = [R.UP.index(v) for v in F.UPF]; iv = R.UP.index("IVd"); jm = F.UPF.index("lnM")
    lm = np.log(np.maximum(F.MSIZES["stock_x_turnover"].reindex(F.G_PUMAS).values, 1.0))
    out = []
    for (X, av, C, w, n), h in ((D, est), (Dv, val)):
        Z = X[:, :, k].copy(); Z[:, :, jm] = lm[None, :]
        out.append(dict(X=Z, IV=X[:, :, iv], av=av, C=C, w=w, h=h.reset_index(drop=True), lnddens=X[:, :, R.UP.index("lnddens")]))
    return out, G


def puma_attrs(G):
    z, P, pumas, pidx, Wn, A, ADJ = G
    zs = pd.read_csv(f"{R.INP}/zoneSystem.csv").set_index("ZoneId").reindex(R.ZONE_IDS)
    cty = zs.COUNTYFIPS.values; acres = zs.ACRES.values
    a = {}
    a["core"] = Wn.T @ np.isin(cty, CORE).astype(float); a["inner"] = Wn.T @ np.isin(cty, INNER).astype(float)
    car = R.read_skim(R.SKIM_CAR); car = np.where(np.isnan(car), 300.0, car)
    jd = z.jobs.values / np.maximum(acres, 1)
    cbd = [int(np.argmax(np.where(cty == c, jd, -1))) for c in CORE]
    a["tcbd"] = Wn.T @ np.log1p(np.minimum(car[:, cbd[0]], car[:, cbd[1]]))
    pt = R.read_skim(R.SKIM_PT_D2D); pt = np.where(np.isnan(pt), 180.0, np.minimum(pt, 180.0))
    a["transit"] = Wn.T @ np.log(np.maximum((z.jobs.values[None, :] * np.exp(-0.05 * pt)).sum(1), 1.0))
    dd = pd.read_csv(f"{R.MICRO}/dd_2016.csv", usecols=["zone", "type"]); mf = dd[dd.type.isin(["MF234", "MF5plus"])].zone.value_counts().reindex(R.ZONE_IDS).fillna(0).values
    a["mfshare"] = Wn.T @ (mf / np.maximum(z.dwellings.values, 1))
    print("CBD zones:", [R.ZONE_IDS[i] for i in cbd], {k_: (round(float(v.min()), 3), round(float(v.max()), 3)) for k_, v in a.items()})
    return a


def extras(name, d, A):
    h = d["h"]; N, J = d["av"].shape
    lnd = d["lnddens"]; single = (h.NP.values == 1)[:, None] * 1.0; child = (h.n_child.values > 0)[:, None] * 1.0
    young = (h.age_max.values < 35)[:, None] * 1.0; old = (h.age_max.values >= 65)[:, None] * 1.0
    lninc = np.log(np.maximum(h.income.values, 5000) / 50000)[:, None]
    T = lambda v: np.tile(v, (N, 1))
    if name == "dens_hh": return {"lnddens_x_single": lnd * single, "lnddens_x_child": lnd * child, "lnddens_x_young": lnd * young, "lnddens_x_old65": lnd * old}
    if name == "dens3": return {"lnddens_x_single": lnd * single, "lnddens_x_child": lnd * child, "lnddens_x_young": lnd * young}
    if name == "dens2": return {"lnddens_x_single": lnd * single, "lnddens_x_young": lnd * young}
    if name == "dens_inc": return {"lnddens_x_lninc": lnd * lninc}
    if name == "core": return {"core": T(A["core"])}
    if name == "core2": return {"core": T(A["core"]), "inner_core": T(A["inner"])}
    if name == "tcbd": return {"ln1p_time_cbd": T(A["tcbd"])}
    if name == "transit": return {"transit_access": T(A["transit"])}
    if name == "mfshare": return {"mf_share": T(A["mfshare"])}
    if name == "mf_hh": return {"mf_share_x_single": T(A["mfshare"]) * single, "mf_share_x_child": T(A["mfshare"]) * child}
    if name == "base": return {}
    raise KeyError(name)


def combine(names, d, A):
    e = {}
    for n in names: e.update(extras(n, d, A))
    return e


def split_county(G):
    pz = pd.read_csv(R.GEO_PZ); pz = pz[pz.zone.isin(R.ZIDX.index)].copy(); tot = pz.groupby("zone").hu.transform("sum")
    pz["f"] = np.where(tot > 0, pz.hu / tot.where(tot > 0, 1), 1.0 / pz.groupby("zone").hu.transform("size"))
    zs = pd.read_csv(f"{R.INP}/zoneSystem.csv").set_index("ZoneId"); dd = pd.read_csv(f"{R.MICRO}/dd_2016.csv", usecols=["zone"]).zone.value_counts()
    pz["county"] = pz.zone.map(zs.COUNTYFIPS); pz["dw"] = pz.f * pz.zone.map(dd).fillna(0)
    s = pz.groupby(["puma7", "county"]).dw.sum().reset_index(); s["share"] = s.dw / s.groupby("puma7").dw.transform("sum")
    pumas = G[2]; S = s.pivot_table(index="puma7", columns="county", values="share", fill_value=0).reindex(pumas).fillna(0)
    return S


def shares(d, P, weighted):
    w = d["w"] if weighted else np.ones(len(d["w"]))
    return 100 * (w[:, None] * d["C"]).sum(0) / w.sum(), 100 * (w[:, None] * P).sum(0) / w.sum()


def fit(label, names, D, A, S, base_b=None):
    de, dv = D; names_x = list(F.UPF)
    ee, ev = combine(names, de, A), combine(names, dv, A)
    names_x += list(ee)
    Xe = np.concatenate([de["X"]] + [ee[k][:, :, None] for k in ee], 2); Xv = np.concatenate([dv["X"]] + [ev[k][:, :, None] for k in ev], 2)
    m = MNL(Xe, names_x, de["av"], de["C"], weights=de["w"], offset=de["IV"]).fit()
    mv = MNL(Xv, names_x, dv["av"], dv["C"], offset=dv["IV"]); vll = float(mv.loglik_obs(m.b).sum())
    Pe = MNL(Xe, names_x, de["av"], de["C"], weights=de["w"], offset=de["IV"])._probs(m.b); Pv = mv._probs(m.b)
    C = Q.within(Xe, de["av"]); vif = np.diag(np.linalg.inv(C))
    res = {}
    for half, d, P, wt in (("estimation", de, Pe, True), ("holdout", dv, Pv, False)):
        o, p = shares(d, P, wt); res[half] = (pd.Series(o, index=S.index), pd.Series(p, index=S.index))
    return dict(label=label, names=names_x, m=m, vll=vll, vif=dict(zip(names_x, vif)), res=res)


def county(o, p, S):
    return pd.DataFrame({"observed_pct": S.T @ o.values, "model_pct": S.T @ p.values}, index=S.columns).assign(diff_pp=lambda t: t.model_pct - t.observed_pct)


def main():
    D, G = designs(); A = puma_attrs(G); S = split_county(G); N = len(D[0]["w"])
    blocks = [("base", "r20 model", ["base"])] if os.environ.get("R22_ONLY_COMBOS") else [("base", "r20 model", ["base"]), ("dens_hh", "ln density x household type (4)", ["dens_hh"]), ("dens_inc", "ln density x ln income", ["dens_inc"]),
              ("core", "core-city share (DC, Baltimore City)", ["core"]), ("core2", "core + inner core (Arlington, Alexandria)", ["core2"]),
              ("tcbd", "ln(1 + car time to the nearest CBD)", ["tcbd"]), ("transit", "transit accessibility of the PUMA", ["transit"]),
              ("mfshare", "multifamily share of the stock", ["mfshare"]), ("mf_hh", "multifamily share x single, x children", ["mf_hh"])]
    if os.environ.get("R22_COMBOS"):
        for c in os.environ["R22_COMBOS"].split(";"):
            blocks.append(("+".join(c.split(",")), "combination " + c, c.split(",")))
    rows, coefs, cres, pres = [], [], [], []
    base = None
    for code, lab, names in blocks:
        r = fit(code, names, D, A, S); m = r["m"]
        if base is None: base = r
        dLL = m.ll - base["m"].ll; df = m.k - base["m"].k; p = float(chi2.sf(2 * dLL, df)) if df > 0 else np.nan
        ce = county(*r["res"]["estimation"], S); ch = county(*r["res"]["holdout"], S)
        pe = pd.DataFrame({"o": r["res"]["estimation"][0], "p": r["res"]["estimation"][1]})
        key = [11001, 24510, 51919, 24003, 51013, 24031, 24033, 24005]
        rows.append(dict(block=code, label=lab, K=m.k, LL=m.ll, dLL=dLL, LR_p=p, BIC=m.k * np.log(N) - 2 * m.ll, max_VIF=max(r["vif"].values()),
                         est_county_MAD=ce.diff_pp.abs().mean(), est_county_maxabs=ce.diff_pp.abs().max(), est_puma_MAD=(pe.p - pe.o).abs().mean(),
                         holdout_LL=r["vll"], holdout_county_MAD=ch.diff_pp.abs().mean(),
                         **{f"est_{c}": ce.diff_pp.get(c, np.nan) for c in key}, **{f"hold_{c}": ch.diff_pp.get(c, np.nan) for c in key}))
        for n_, b, s in zip(r["names"], m.b, m.rse): coefs.append(dict(block=code, param=n_, coef=b, robust_se=s, t=b / s, VIF=r["vif"][n_]))
        cres.append(ce.assign(block=code, half="estimation").reset_index()); cres.append(ch.assign(block=code, half="holdout").reset_index())
        pres.append(pe.assign(block=code).reset_index())
        print(f"{code:12s} K {m.k} LL {m.ll:.1f} dLL {dLL:+.1f} BIC {rows[-1]['BIC']:.1f} | est county MAD {ce.diff_pp.abs().mean():.3f} "
              f"DC {ce.diff_pp.get(11001):+.2f} BC {ce.diff_pp.get(24510):+.2f} Fx {ce.diff_pp.get(51919):+.2f} AA {ce.diff_pp.get(24003):+.2f} Arl {ce.diff_pp.get(51013):+.2f} "
              f"| hold-out LL {r['vll']:.1f} MAD {ch.diff_pp.abs().mean():.3f}", flush=True)
        for n_ in r["names"][len(F.UPF):]: print(f"     {n_:20s} {m.b[r['names'].index(n_)]: .4f} ({m.rse[r['names'].index(n_)]:.4f}) VIF {r['vif'][n_]:.2f}")
    suf = os.environ.get("R22_SUF", "")
    pd.DataFrame(rows).to_csv(f"{HERE}/r22_blocks{suf}.csv", index=False); pd.DataFrame(coefs).to_csv(f"{HERE}/r22_block_coef{suf}.csv", index=False)
    pd.concat(cres).to_csv(f"{HERE}/r22_county_resid{suf}.csv", index=False); pd.concat(pres).to_csv(f"{HERE}/r22_puma_resid{suf}.csv", index=False)


if __name__ == "__main__":
    main()
