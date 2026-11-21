#!/usr/bin/env python3
"""2026-11-18m: copy of r18_export_silo.py for the r20 estimation (r20_final.py, r20_coef.csv, r20 crosswalk, M = stock x turnover);
only the Java check inputs (r20_verify/) and the comparison; the engine files *_1118m.csv come from r20_final.py.
r18 text: Two-level residential location model (r17_final.py) for SILO (2026-11-18): coefficient and geography files of the engine
(ReslocTwoLevel.java) and the inputs of the Java check.  Nothing of r14 / r17 is edited; their functions are imported.

Engine files (2_silo/input/, '#' lines = documentation, skipped by the reader):
  resloc_dwelling_coef_1118.csv   variable,value   the 18 dwelling-level coefficients of r17_coef.csv
  resloc_puma_coef_1118.csv       variable,value   the 10 PUMA-level coefficients + IVd = 1 (inclusive value held at 1)
  resloc_puma_zone_1118.csv       zone,puma7,f_member,w_attr
        w_attr  = the zone's share of its 2010 housing units in the PUMA (geo_puma_zone: hu / zone total): the PUMA attributes are
                  means over its zones with weights w_attr x dwellings of the zone (r14.geography Wn; dynamic: SILO's current dwellings)
        f_member = share of the zone's dwellings that belong to the PUMA in SILO (= w_attr; zones without a tract point (no row in
                  geo_puma_zone) belong to their zoneSystem PUMA_10 with f_member 1 and w_attr 0, as they had no weight in the
                  estimation; zones whose housing units are all 0 in the crosswalk get f_member 1 for PUMA_10 / equal shares and
                  w_attr 0 (in the estimation their weight was NaN, see the report))
  resloc_mig_zone_1118.csv        mig7,zone,w_attr,member
        w_attr 1 = the zone is part of the migration PUMA (MIGPUMA = POWPUMA geography) in geo_mig_zone: origin weights = dwellings,
                  workplace weights = jobs of the zone (r06 weights_matrices O, Pw; dynamic: SILO's current dwellings / jobs)
        member 1 = the MIGPUMA a home or job in the zone is located in (largest housing-unit share for split zones; zones without a
                  row through PUMA_10 -> geo_puma_mig)
  resloc_zone_attr_1118.csv       zone,crime,acres   county crime index of the zone (crimeIndex.csv; missing -> mean, as r14), ACRES
                                  of zoneSystem (ln dwelling density = ln(max(dwellings, 1) / acres), r11_zone_landuse.py)
  resloc_puma_adjacency_1118.csv  puma_a,puma_b      PUMAs sharing a boundary (r14.geography ADJ, both directions)
Java check (r18_verify/): 300 movers of the estimation half: dwelling level (their 30 sampled alternatives) and PUMA level (every PUMA,
the 200 market dwellings per PUMA of the inclusive value as drawn by r14.upper_data, the market size M of the estimation), with the
estimation's 2016 zone dwellings, jobs and household race counts; Python utilities X b (+ IVd).
    python3 r18_export_silo.py              -> engine files + r18_verify/*
    python3 r18_export_silo.py check DIR    -> compares DIR/java_dwelling.csv, DIR/java_puma.csv -> r20_java_check_{dwelling,puma}.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
ARGS = list(sys.argv)   # r14 replaces sys.argv on import
os.environ["RACE_TEST"] = "1"
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
import r20_final as F20              # noqa: E402  (sets GEO_PZ / GEO_MZ to the r20 crosswalk, imports r19 -> r14 with the race term)
F = F20.F; R = F.R; import r17_final as F17   # noqa: E402,E401
F.dw_final = F17.dw_final
from rc import WORK, MICRO, INP, ZONE_IDS, ZIDX   # noqa: E402
S2 = f"{WORKSPACE}/2_silo"; OUT = f"{S2}/input"; VD = f"{HERE}/r20_verify"
coef = pd.read_csv(f"{HERE}/r20_coef.csv")
BDW = coef[coef.level == "dwelling"].set_index("param").coef.reindex(F.DWF).values
BUP = coef[coef.level == "PUMA"].set_index("param").coef.reindex(F.UPF).values
RACES = ["white", "black", "hispanic", "other"]   # SILO Race enum order


def write(path, df, notes):
    with open(path, "w") as f:
        for n in notes: f.write("# " + n + "\n")
        df.to_csv(f, index=False)
    print(f"wrote {path} ({len(df)} rows)")


def export_engine(G):
    z, P, pumas, pidx, Wn, A, ADJ = G
    pd.DataFrame({"variable": F.DWF, "value": BDW}).to_csv(f"{OUT}/resloc_dwelling_coef_1118.csv", index=False)
    pd.DataFrame({"variable": F.UPF + ["IVd"], "value": list(BUP) + [1.0]}).to_csv(f"{OUT}/resloc_puma_coef_1118.csv", index=False)
    print("wrote coefficient files")
    zs = pd.read_csv(f"{INP}/zoneSystem.csv").set_index("ZoneId")
    pz = pd.read_csv(f"{WORK}/geo_puma_zone.csv"); pz = pz[pz.zone.isin(ZIDX.index)].copy()
    tot = pz.groupby("zone").hu.transform("sum"); pz["w_attr"] = np.where(tot > 0, pz.hu / tot.where(tot > 0, 1), 0.0)
    pz["f_member"] = pz.w_attr
    zero = pz[tot == 0].zone.unique()
    for zz in zero:   # crosswalk housing units all 0: membership = PUMA_10 if listed, else equal shares; no attribute weight
        m = pz.zone == zz; p10 = zs.PUMA_10[zz]
        pz.loc[m, "f_member"] = np.where(pz.loc[m, "puma7"] == p10, 1.0, 0.0) if (pz.loc[m, "puma7"] == p10).any() else 1.0 / m.sum()
    miss = [int(q) for q in ZONE_IDS if q not in set(pz.zone)]
    fb = pd.DataFrame({"zone": miss, "puma7": zs.PUMA_10.reindex(miss).values, "hu": 0, "w_attr": 0.0, "f_member": 1.0})
    assert fb.puma7.isin(pumas).all()
    out = pd.concat([pz, fb]).sort_values(["zone", "puma7"])[["zone", "puma7", "f_member", "w_attr"]]
    write(f"{OUT}/resloc_puma_zone_1118.csv", out, [
        "zone -> PUMA (2010, state*100000+PUMA) of the two-level residential location model (r17_final.py; r18_export_silo.py)",
        "w_attr: weight of the zone in the PUMA attributes = w_attr x the zone's current dwellings (estimation: hu share x 2016 dwellings)",
        "f_member: share of the zone's dwellings that belong to the PUMA in SILO (a dwelling of a split zone is assigned by a hash of its id)",
        f"zones without a tract point: zoneSystem PUMA_10, f_member 1, w_attr 0 ({len(miss)} zones); zones with crosswalk hu all 0: w_attr 0 ({list(map(int, zero))})"])
    mz = pd.read_csv(f"{WORK}/geo_mig_zone.csv"); pm = pd.read_csv(f"{WORK}/geo_puma_mig.csv").set_index("puma7").mig7
    mz = mz[mz.zone.isin(ZIDX.index)].copy(); mz["w_attr"] = 1; mz["member"] = 0
    mz.loc[mz.sort_values("hu").groupby("zone").tail(1).index, "member"] = 1
    missm = [int(q) for q in ZONE_IDS if q not in set(mz.zone)]
    fbm = pd.DataFrame({"mig7": pm.reindex(zs.PUMA_10.reindex(missm).values).values, "zone": missm, "w_attr": 0, "member": 1})
    assert fbm.mig7.notna().all()
    outm = pd.concat([mz[["mig7", "zone", "w_attr", "member"]], fbm]).astype(int).sort_values(["mig7", "zone"])
    write(f"{OUT}/resloc_mig_zone_1118.csv", outm, [
        "migration PUMA (MIGPUMA = POWPUMA geography, state*100000+MIGPUMA) <-> zone (r06 weights_matrices, geo_mig_zone.csv)",
        "w_attr 1: zone counted in the MIGPUMA's origin weights (x current dwellings) and workplace weights (x current jobs), as in the estimation",
        "member 1: MIGPUMA of a home or a job in the zone (largest housing-unit share for split zones; zones not in geo_mig_zone via PUMA_10)"])
    crime = z.crime.fillna(z.crime.mean())
    write(f"{OUT}/resloc_zone_attr_1118.csv", pd.DataFrame({"zone": ZONE_IDS, "crime": crime.values, "acres": zs.ACRES.reindex(ZONE_IDS).values}), [
        "fixed zone inputs of the two-level residential location model: crime = county crime index (input/crimeIndex.csv CrimeIndicator; missing -> mean, r14.geography)",
        "acres = zoneSystem ACRES (ln dwelling density = ln(max(dwellings, 1) / acres), r11_zone_landuse.py, recomputed every year)"])
    i, j = np.nonzero(ADJ > 0)
    write(f"{OUT}/resloc_puma_adjacency_1118.csv", pd.DataFrame({"puma_a": pumas[i], "puma_b": pumas[j]}), [
        "PUMAs sharing a boundary (dissolved zone polygons of each zone's main PUMA, 50 m buffer; r14.geography ADJ), both directions"])
    bad = P.index[~(P.dwellings > 0)].tolist()
    print(f"PUMAs with dwellings NaN/0 in the estimation geography (never available there): {bad}")
    return bad


class Rec:
    """RNG proxy: records the draws of upper_data (the 200 market dwellings per PUMA of the inclusive value)"""
    def __init__(self, rng): self.rng, self.draws = rng, []
    def choice(self, *a, **k):
        x = self.rng.choice(*a, **k); self.draws.append(np.array(x)); return x


def export_check(G, bad):
    z, P, pumas, pidx, Wn, A, ADJ = G
    os.makedirs(VD, exist_ok=True)
    mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True)
    migs = np.sort(pd.read_csv(f"{WORK}/geo_mig_zone.csv").mig7.unique())
    ok = est[est.mig7.isin(migs) & est.puma7.isin(pumas) & ~est.puma7.isin(bad)]   # movers into the PUMAs without weight were dropped in the estimation
    h = ok.sample(300, random_state=20261118).reset_index(drop=True); h["id"] = np.arange(len(h))
    # dwelling level: the estimation's sampling of 30 alternatives and design
    R.RNG = np.random.default_rng(20261118); alt, av = R.sample(h, pool); X = F.dw_final(h, alt); V = X @ BDW
    rows = []
    for i in range(len(h)):
        for k in range(R.J):
            if av[i, k]: rows.append((i, k, h.income.values[i], int(h.NP.values[i]), alt["cost"][i, k], int(alt["bed"][i, k]), alt["dtype"][i, k], int(bool(alt["new5"][i, k])), V[i, k]))
    pd.DataFrame(rows, columns=["id", "alt", "income", "size", "cost", "bedrooms", "type", "new5", "V_python"]).to_csv(f"{VD}/dwelling_in.csv", index=False)
    # PUMA level: r14.upper_data on these movers, with the recorded IV draws
    R.dw_X = F.dw_final
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]
    class B: pass
    mb = B(); mb.b = BDW
    R.RNG = Rec(np.random.default_rng(20261119)); X1, av1, C1, w1, n1 = R.upper_data(h, pool, mb, G)
    assert n1 == len(h), (n1, len(h))
    k = [R.UP.index(v) for v in F.UPF]; iv = R.UP.index("IVd")
    Xk = X1[:, :, k].copy(); Xk[:, :, F.UPF.index("lnM")] = np.log(np.maximum(F.MSIZES["stock_x_turnover"].reindex(pumas).values, 1.0))[None, :]
    U = Xk @ BUP + X1[:, :, iv]; U = np.where(av1, U, np.nan)
    pd.DataFrame({"id": np.repeat(h.id.values, len(pumas)), "puma7": np.tile(pumas, len(h)), "V_python": U.ravel()}).to_csv(f"{VD}/puma_python.csv", index=False)
    pd.DataFrame({"id": np.repeat(h.id.values, len(pumas)), "puma7": np.tile(pumas, len(h)), **{v: X1[:, :, R.UP.index(v)].ravel() for v in F.UPF + ["IVd"]}}).to_csv(f"{VD}/puma_design_python.csv", index=False)
    draws = R.RNG.draws; pr = []
    for j, p in enumerate(pumas):
        g = pool[pool.puma7 == p]
        if len(g) == 0: continue
        d = draws.pop(0); g = g.iloc[d]
        pr.append(pd.DataFrame({"puma7": p, "cost": g.cost.values, "bedrooms": g.BDSP.values.astype(int), "type": g.dtype.values, "new5": (g.age_dd.values <= 5).astype(int)}))
    assert not draws
    pd.concat(pr).to_csv(f"{VD}/puma_pool.csv", index=False)
    M = F.MSIZES["stock_x_turnover"].reindex(pumas).fillna(0)   # r19/r20: M of the estimation (PUMS movers x coverage), lnM column replaced as in upper_fit
    pd.DataFrame({"puma7": pumas, "M": M.values}).to_csv(f"{VD}/puma_M.csv", index=False)
    hh = pd.read_csv(f"{MICRO}/hh_2016.csv", usecols=["dwelling", "race"]); dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["id", "zone"])
    hh["zone"] = hh.dwelling.map(dd.set_index("id").zone); Sx = pd.crosstab(hh.zone, hh.race).reindex(index=ZONE_IDS, columns=RACES).fillna(0)
    zin = pd.DataFrame({"zone": ZONE_IDS, "dwellings": z.dwellings.values, "jobs": z.jobs.values, **{f"n_{r}": Sx[r].values for r in RACES}})
    zin.to_csv(f"{VD}/zone_inputs.csv", index=False)
    hv = pd.DataFrame({"id": h.id, "income": h.income, "size": h.NP.astype(int), "mig7": h.mig7.astype(int),
                       "pow": h.pow7s.fillna("").astype(str).str.replace(";", "|"), "nocar": (h.VEH.fillna(0) <= 0).astype(int),
                       "child": (h.n_child > 0).astype(int), "race": h.head_race})
    hv.to_csv(f"{VD}/puma_hh.csv", index=False)
    print(f"Java check inputs in {VD}: {len(h)} movers, dwelling alternatives {len(rows)}, PUMA pool {sum(len(x) for x in pr)} dwellings")


def check(d):
    p = pd.read_csv(f"{VD}/dwelling_in.csv"); j = pd.read_csv(f"{d}/java_dwelling.csv")
    m = p.merge(j, on=["id", "alt"]); assert len(m) == len(p)
    m["abs_diff"] = (m.V - m.V_python).abs(); m["rel_diff"] = m.abs_diff / np.maximum(1, m.V_python.abs())
    m.to_csv(f"{HERE}/r20_java_check_dwelling.csv", index=False)
    print(f"dwelling level: {len(m)} utilities, max abs diff {m.abs_diff.max():.3g}, max rel {m.rel_diff.max():.3g}")
    p = pd.read_csv(f"{VD}/puma_python.csv"); j = pd.read_csv(f"{d}/java_puma.csv")
    m = p.merge(j, on=["id", "puma7"], how="left"); both = m.V_python.notna() & m.V.notna()
    m["abs_diff"] = (m.V - m.V_python).abs(); m["rel_diff"] = m.abs_diff / np.maximum(1, m.V_python.abs())
    m.to_csv(f"{HERE}/r20_java_check_puma.csv", index=False)
    print(f"PUMA level: {both.sum()} utilities available in both, max abs diff {m.abs_diff[both].max():.3g}, max rel {m.rel_diff[both].max():.3g}; "
          f"available only in Python {(m.V_python.notna() & m.V.isna()).sum()}, only in Java {(m.V_python.isna() & m.V.notna()).sum()}")


if __name__ == "__main__":
    if len(ARGS) > 2 and ARGS[1] == "check": check(ARGS[2]); sys.exit()
    R.RNG = np.random.default_rng(20261117); G = R.geography()
    export_check(G, [])   # r20: the engine files *_1118m.csv are written by r20_final.py; no PUMA excluded
