#!/usr/bin/env python3
"""r19_final.py with the corrected crosswalk (r20_crosswalk.py, 2026-11-18m): the 252 zones without a tract point belong to the PUMA /
migration PUMA of their centroid with weight = SILO 2016 dwellings (jobs for workplaces); the 4 crosswalk-zero zones get the same weight.
Recomputed: geography and PUMA attributes, SILO 2016 dwellings of each PUMA (membership = hu share of r20_geo_puma_zone) and so the
turnover r_p = PUMS in-area movers / SILO 2016 dwellings; the estimation M (PUMS movers x coverage) is unchanged.  Same 28 terms,
seed, J = 30, robust s.e.  Writes r20_fit.csv, r20_coef.csv (+ change vs r19 in r19 s.e.), r20_vif.csv, r20_mover_filters.csv and the
export-ready engine files *_1118m.csv (this folder; not copied to 2_silo/input)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ["GEO_PZ"] = f"{HERE}/r20_geo_puma_zone.csv"; os.environ["GEO_MZ"] = f"{HERE}/r20_geo_mig_zone.csv"
import r19_final as F   # noqa: E402  (imports r14, which reads GEO_PZ / GEO_MZ)
R = F.R
from rc import MICRO, INP, ZONE_IDS, ZIDX   # noqa: E402
assert R.GEO_PZ.endswith("r20_geo_puma_zone.csv") and R.GEO_MZ.endswith("r20_geo_mig_zone.csv")


def silo_stock():
    pz = pd.read_csv(R.GEO_PZ); pz = pz[pz.zone.isin(ZIDX.index)].copy(); tot = pz.groupby("zone").hu.transform("sum")
    pz["f"] = np.where(tot > 0, pz.hu / tot.where(tot > 0, 1), 1.0 / pz.groupby("zone").hu.transform("size"))   # zones with 0 dwellings (99, 236, 340, 405, 1144): one row each, f 1
    assert set(pz.zone) == set(ZONE_IDS) and pz.f.notna().all()
    dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["zone", "hhID"])
    pz["dw"] = pz.f * pz.zone.map(dd.zone.value_counts()).fillna(0); pz["vac"] = pz.f * pz.zone.map(dd[dd.hhID <= 0].zone.value_counts()).fillna(0)
    return pz, pz.groupby("puma7").dw.sum(), pz.groupby("puma7").vac.sum()


def export(pz, G, mb, mub, MK):
    z, P, pumas, pidx, Wn, A, ADJ = G
    pd.DataFrame({"variable": F.DWF, "value": mb}).to_csv(f"{HERE}/resloc_dwelling_coef_1118m.csv", index=False)
    pd.DataFrame({"variable": F.UPF + ["IVd"], "value": list(mub) + [1.0]}).to_csv(f"{HERE}/resloc_puma_coef_1118m.csv", index=False)
    def write(name, df, notes):
        with open(f"{HERE}/{name}", "w") as f:
            for n in notes: f.write("# " + n + "\n")
            df.to_csv(f, index=False)
        print(f"wrote {name} ({len(df)} rows)")
    write("resloc_puma_zone_1118m.csv", pz.assign(f_member=pz.f, w_attr=pz.f).sort_values(["zone", "puma7"])[["zone", "puma7", "f_member", "w_attr"]], [
        "zone -> PUMA (2010, state*100000+PUMA) of the two-level residential location model (r20_final.py, crosswalk r20_crosswalk.py)",
        "w_attr: weight of the zone in the PUMA attributes = w_attr x the zone's current dwellings; f_member: share of the zone's dwellings in the PUMA",
        "every zone has a row: tract internal points (2010 HU10 shares); zones without a tract point -> PUMA of the zone centroid (2010 tract -> PUMA), weight 1"])
    mz = pd.read_csv(R.GEO_MZ); mz = mz[mz.zone.isin(ZIDX.index)].copy(); mz["w_attr"] = 1; mz["member"] = 0
    mz.loc[mz.sort_values("hu").groupby("zone").tail(1).index, "member"] = 1; assert mz.groupby("zone").member.sum().eq(1).all() and set(mz.zone) == set(ZONE_IDS)
    write("resloc_mig_zone_1118m.csv", mz[["mig7", "zone", "w_attr", "member"]].astype(int).sort_values(["mig7", "zone"]), [
        "migration PUMA (MIGPUMA = POWPUMA geography) <-> zone (r20_geo_mig_zone.csv): w_attr 1 = zone in the MIGPUMA's origin (x dwellings) and workplace (x jobs) weights",
        "member 1: MIGPUMA of a home or job in the zone (largest hu share); zones without a tract point: MIGPUMA of their centroid PUMA"])
    zs = pd.read_csv(f"{INP}/zoneSystem.csv").set_index("ZoneId"); crime = z.crime.fillna(z.crime.mean())
    write("resloc_zone_attr_1118m.csv", pd.DataFrame({"zone": ZONE_IDS, "crime": crime.values, "acres": zs.ACRES.reindex(ZONE_IDS).values}), [
        "fixed zone inputs: crime = county crime index (crimeIndex.csv; missing -> mean), acres = zoneSystem ACRES (unchanged from _1118)"])
    i, j = np.nonzero(ADJ > 0)
    write("resloc_puma_adjacency_1118m.csv", pd.DataFrame({"puma_a": pumas[i], "puma_b": pumas[j]}), [
        "PUMAs sharing a boundary (dissolved polygons of each zone's main PUMA, r20 crosswalk, 50 m buffer), both directions"])
    t = pd.DataFrame({"puma7": MK.index, "turnover": (MK.movers * F.COV / MK.silo_dw).values, "pums_movers": MK.movers.values, "coverage": F.COV.values,
                      "silo_dw_2016": MK.silo_dw.values, "M_2016": (MK.movers * F.COV).values}); assert np.isfinite(t.turnover).all() and (t.turnover > 0).all()
    write("resloc_puma_turnover_1118m.csv", t, [
        "fixed turnover rate r_p of the PUMA (r20_final.py): PUMS 2014-2018 movers' dwellings x coverage share / SILO 2016 dwellings of the PUMA",
        "(r20 crosswalk membership).  SILO: M_p,t = r_p x all dwellings (occupied + vacant) of the PUMA at the start of year t (= M_2016 in 2016)"])
    return t


def main():
    pz, dw, vac = silo_stock(); MK = F.MK.copy(); MK["silo_dw_r19"] = MK.silo_dw; MK["silo_dw"] = dw.reindex(MK.index); MK["silo_vac"] = vac.reindex(MK.index)
    assert MK.silo_dw.notna().all() and (MK.silo_dw > 0).all(); F.MK = MK; MK.to_csv(f"{HERE}/r20_puma_market.csv")
    ms = F.MSIZES["stock_x_turnover"]   # estimation M = PUMS movers x coverage (unchanged)
    est, val, pool, G = F.setup(); fit, coef, vif = [], [], []
    m, X, av, vll, ll0 = F.dwelling(est, val, pool)
    fit.append(dict(level="dwelling within PUMA", N=len(est), K=m.k, LL0=ll0, LL=m.ll, BIC=m.k * np.log(len(est)) - 2 * m.ll, validation_N=len(val), validation_LL=vll))
    coef += [dict(level="dwelling", param=a, coef=b, robust_se=s, t=b / s) for a, b, s in zip(F.DWF, m.b, m.rse)]
    F.vif_rows("dwelling", F.DWF, X, av, m.cov_robust, vif, "_r20tmp")
    D, Dv = F.upper_designs(est, val, pool, m.b, G); mu, X1, av1, vu, ll0u, n1, nv1 = F.upper_fit(D, Dv, ms)
    fit.append(dict(level="PUMA (inclusive value at 1)", N=n1, K=mu.k, LL0=ll0u, LL=mu.ll, BIC=mu.k * np.log(n1) - 2 * mu.ll, validation_N=nv1, validation_LL=vu))
    coef += [dict(level="PUMA", param=a, coef=b, robust_se=s, t=b / s) for a, b, s in zip(F.UPF, mu.b, mu.rse)]
    F.vif_rows("PUMA", F.UPF, X1, av1, mu.cov_robust, vif, "_r20tmp")
    for lv in ("dwelling", "PUMA"): os.replace(f"{HERE}/r19_est_corr_{lv}_r20tmp.csv", f"{HERE}/r20_est_corr_{lv}.csv")
    c = pd.DataFrame(coef); c["label"] = [F.LABEL.get(p, F.LABEL.get(p.replace("_x_lninc", ""), p) + (" x ln income" if p.endswith("_x_lninc") else "")) for p in c.param]
    r19 = pd.read_csv(f"{HERE}/r19_coef.csv").set_index(["level", "param"])
    c["r19_coef"] = [r19.coef[(a, b)] for a, b in zip(c.level, c.param)]; c["change_in_r19_se"] = (c.coef - c.r19_coef) / [r19.robust_se[(a, b)] for a, b in zip(c.level, c.param)]
    pd.DataFrame(fit).to_csv(f"{HERE}/r20_fit.csv", index=False); c.to_csv(f"{HERE}/r20_coef.csv", index=False); pd.DataFrame(vif).to_csv(f"{HERE}/r20_vif.csv", index=False)
    pd.DataFrame(R.FILTER_LOG, index=["estimation", "validation"]).to_csv(f"{HERE}/r20_mover_filters.csv")
    t = export(pz, G, m.b, mu.b, MK)
    r19t = pd.read_csv(f"{HERE}/resloc_puma_turnover_1118k.csv", comment="#").set_index("puma7").turnover
    d = np.log(t.set_index("puma7").turnover / r19t); print(f"ln(r_p r20 / r19): mean {d.mean():.3f}, max |.| {d.abs().max():.3f} ({d.abs().idxmax()}), PUMAs changed > 1 % {(d.abs() > .01).sum()}")
    a19 = pd.read_csv(f"{WORKSPACE}/2_silo/input/resloc_puma_adjacency_1118.csv", comment="#"); a20 = pd.read_csv(f"{HERE}/resloc_puma_adjacency_1118m.csv", comment="#")
    s19, s20 = set(map(tuple, a19.values)), set(map(tuple, a20.values)); print(f"adjacency pairs r19 {len(s19)}, r20 {len(s20)}, added {len(s20 - s19)}, removed {len(s19 - s20)}")
    print(pd.DataFrame(fit).round(2).to_string(index=False)); print(c[["level", "param", "r19_coef", "coef", "robust_se", "t", "change_in_r19_se"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
