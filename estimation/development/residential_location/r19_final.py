#!/usr/bin/env python3
"""FINAL two-level residential location model, re-estimated 2026-11-18 (r17_final.py + two changes):
  1. geography bug fix (r14_puma_two_level.py, 2026-11-18k): zones with zero crosswalk housing units get weight 0 instead of NaN, so
     PUMAs 2400506, 2400507, 2400804, 2401201 are available again and no mover is dropped (assertion in r14.upper_data).
  2. market size M of the PUMA term ln M (env MDEF, default the chosen definition; candidates in r19_market_test.py, data r19_puma_market.csv):
       movers       PUMS weighted dwellings of households that moved in within 12 months (r17)
       stock_x_turnover  (chosen) SILO dwelling stock of the PUMA (all dwellings, occupied + vacant, zones by f_member) x a fixed
                    turnover rate r_p = PUMS movers' dwellings of the in-area part of the PUMA / SILO 2016 dwellings of the PUMA.
                    In the estimation (base year 2016) M_p = PUMS movers x coverage share exactly (= movers_cov); in SILO
                    M_p,t = r_p x all dwellings of p at the start of year t (identical in 2016, then moves with the stock only).
       ... (see MSIZES)
Same 28 terms as r17 (18 dwelling, 10 PUMA; inclusive value held at 1); J = 30; seed 20261117; robust (sandwich) s.e.
Estimation half; validation half (hold-out, already used in model development) once.
Writes r19_fit.csv, r19_coef.csv, r19_vif.csv, r19_est_corr_<level>.csv and the export-ready engine coefficient files
resloc_dwelling_coef_1118k.csv, resloc_puma_coef_1118k.csv, resloc_puma_turnover_1118k.csv (this folder; not copied to 2_silo/input)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
os.environ["RACE_TEST"] = "1"
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r14_puma_two_level as R   # noqa: E402
import r16_collinearity as Q     # noqa: E402  (within(): within-choice-set correlation)
import r17_final as F17          # noqa: E402
from mnl import MNL              # noqa: E402
DWF, UPF, LABEL = F17.DWF, F17.UPF, dict(F17.LABEL)
_full = R.dw_X
MK = pd.read_csv(f"{HERE}/r19_puma_market.csv").set_index("puma7")
COV = pd.read_csv(f"{R.WORK}/geo_puma_region.csv").groupby("puma7").coverage.first().reindex(MK.index)
MSIZES = {   # puma7 -> M
    "movers": MK.movers,                                            # (b) r17: PUMS movers' dwellings, whole PUMA
    "movers_cov": MK.movers * COV,                                  # (b) in-area part of the PUMA (coverage share of its housing units)
    "stock_pums": MK.hu_all * COV,                                  # (a) PUMS housing units (occupied + vacant), in-area part
    "stock_pums_occ": MK.hu_occ * COV,                              # (a) PUMS occupied housing units, in-area part
    "stock_silo": MK.silo_dw,                                       # (a) SILO 2016 dwellings of the PUMA's zones (what SILO counts)
    "stock_turn": MK.silo_dw * MK.movers / MK.hu_all,               # (c) SILO stock x fixed PUMS turnover (movers / housing units)
    "stock_x_turnover": MK.movers * COV,                            # (c, chosen) = movers_cov in the estimation; SILO: r_p x stock_t
    "vac_silo": MK.silo_vac,                                        # diagnostic: SILO 2016 vacancies (the current Java default)
}
MDEF = os.environ.get("MDEF", "stock_x_turnover")
LABEL["lnM"] = {"movers": "ln market size (PUMS movers' dwellings)", "stock_x_turnover": "ln market size (dwelling stock x fixed PUMA turnover rate)"}.get(MDEF, f"ln market size ({MDEF})")


def dwelling(est, val, pool):
    R.dw_X = _full
    alt, av = R.sample(est, pool); X = F17.dw_final(est, alt); C = np.zeros_like(av); C[:, 0] = True; m = MNL(X, DWF, av, C).fit()
    altv, avv = R.sample(val, pool); Xv = F17.dw_final(val, altv); Cv = np.zeros_like(avv); Cv[:, 0] = True
    vll = float(MNL(Xv, DWF, avv, Cv).loglik_obs(m.b).sum()); ll0 = float(np.log(1.0 / av.sum(1)).sum())
    return m, X, av, vll, ll0


def upper_designs(est, val, pool, b, G):
    R.dw_X = F17.dw_final
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]
    class B: pass
    mb = B(); mb.b = b
    return R.upper_data(est, pool, mb, G), R.upper_data(val, pool, mb, G)


def upper_fit(D, Dv, msize):
    """PUMA level with ln M replaced by ln msize (the designs D, Dv hold the rest)"""
    (X1, av1, C1, w1, n1), (Xv1, avv1, Cv1, wv1, nv1) = D, Dv
    k = [R.UP.index(v) for v in UPF]; iv = R.UP.index("IVd"); jm = UPF.index("lnM")
    lm = np.log(np.maximum(msize.reindex(G_PUMAS).values, 1.0))
    X = X1[:, :, k].copy(); X[:, :, jm] = lm[None, :]; Xv = Xv1[:, :, k].copy(); Xv[:, :, jm] = lm[None, :]
    mu = MNL(X, UPF, av1, C1, weights=w1, offset=X1[:, :, iv]).fit()
    vu = float(MNL(Xv, UPF, avv1, Cv1, offset=Xv1[:, :, iv]).loglik_obs(mu.b).sum()); ll0 = float(np.log(1.0 / av1.sum(1)).sum())
    return mu, X, av1, vu, ll0, n1, nv1


def vif_rows(level, names, X, av, cov, rows, suf):
    C = Q.within(X, av); vif = np.diag(np.linalg.inv(C)); rows += [dict(level=level, variable=k, VIF=v) for k, v in zip(names, vif)]
    pd.DataFrame(cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov))), index=names, columns=names).round(3).to_csv(f"{HERE}/r19_est_corr_{level}{suf}.csv")


G_PUMAS = None


def setup():
    global G_PUMAS
    mv = pd.read_parquet(f"{R.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    print(f"movers: all {len(mv)}, estimation {len(est)}, validation {len(val)}", flush=True)
    R.RNG = np.random.default_rng(20261117); G = R.geography(); G_PUMAS = G[2]
    assert set(G_PUMAS) == set(MK.index), "PUMAs of the market file differ from the geography"
    return est, val, pool, G


def main():
    est, val, pool, G = setup(); fit, coef, vif = [], [], []; suf = os.environ.get("R19_SUF", "")
    m, X, av, vll, ll0 = dwelling(est, val, pool)
    fit.append(dict(level="dwelling within PUMA", N=len(est), K=m.k, LL0=ll0, LL=m.ll, BIC=m.k * np.log(len(est)) - 2 * m.ll, validation_N=len(val), validation_LL=vll))
    coef += [dict(level="dwelling", param=a, coef=b, robust_se=s, t=b / s) for a, b, s in zip(DWF, m.b, m.rse)]
    vif_rows("dwelling", DWF, X, av, m.cov_robust, vif, suf)
    D, Dv = upper_designs(est, val, pool, m.b, G)
    mu, X1, av1, vu, ll0u, n1, nv1 = upper_fit(D, Dv, MSIZES[MDEF])
    fit.append(dict(level="PUMA (inclusive value at 1)", N=n1, K=mu.k, LL0=ll0u, LL=mu.ll, BIC=mu.k * np.log(n1) - 2 * mu.ll, validation_N=nv1, validation_LL=vu))
    coef += [dict(level="PUMA", param=a, coef=b, robust_se=s, t=b / s) for a, b, s in zip(UPF, mu.b, mu.rse)]
    vif_rows("PUMA", UPF, X1, av1, mu.cov_robust, vif, suf)
    c = pd.DataFrame(coef); c["label"] = [LABEL.get(p, LABEL.get(p.replace("_x_lninc", ""), p) + (" x ln income" if p.endswith("_x_lninc") else "")) for p in c.param]
    pd.DataFrame(fit).to_csv(f"{HERE}/r19_fit{suf}.csv", index=False); c.to_csv(f"{HERE}/r19_coef{suf}.csv", index=False); pd.DataFrame(vif).to_csv(f"{HERE}/r19_vif{suf}.csv", index=False)
    pd.DataFrame(R.FILTER_LOG, index=["estimation", "validation"]).to_csv(f"{HERE}/r19_mover_filters{suf}.csv")
    if not suf:   # export-ready engine files (same layout as r18_export_silo.py; not copied to 2_silo/input)
        pd.DataFrame({"variable": DWF, "value": m.b}).to_csv(f"{HERE}/resloc_dwelling_coef_1118k.csv", index=False)
        pd.DataFrame({"variable": UPF + ["IVd"], "value": list(mu.b) + [1.0]}).to_csv(f"{HERE}/resloc_puma_coef_1118k.csv", index=False)
        t = pd.DataFrame({"puma7": MK.index, "turnover": (MK.movers * COV / MK.silo_dw).values, "pums_movers": MK.movers.values, "coverage": COV.values,
                          "silo_dw_2016": MK.silo_dw.values, "M_2016": (MK.movers * COV).values})
        assert np.isfinite(t.turnover).all() and (t.turnover > 0).all()
        with open(f"{HERE}/resloc_puma_turnover_1118k.csv", "w") as f:
            f.write("# fixed turnover rate of the PUMA (r19_final.py, market size stock_x_turnover): PUMS 2014-2018 weighted dwellings occupied by households\n"
                    "# that moved in within 12 months x coverage share of the PUMA in the zone system / SILO 2016 dwellings of the PUMA (dd_2016, occupied + vacant,\n"
                    "# zones by f_member of resloc_puma_zone).  SILO: M_p,t = turnover_p x all dwellings of the PUMA at the start of year t (= M_2016 in 2016).\n"
                    "# pums_movers, coverage, silo_dw_2016, M_2016 are documentation only.\n")
            t.to_csv(f, index=False)
        print("wrote resloc_dwelling_coef_1118k.csv, resloc_puma_coef_1118k.csv, resloc_puma_turnover_1118k.csv")
    print(pd.DataFrame(fit).round(2).to_string(index=False)); print(c[["level", "param", "coef", "robust_se", "t"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
