#!/usr/bin/env python3
"""Unit check of the engine's re-specified residential location utilities (ReslocRespecUtility via ReslocRespecVerify) against the
estimation utilities X beta of the final models, on choice situations of the estimation data:
  zone      500 RTS households (estimation half), 30 sampled cells each (r03/r08 data, multimodal accessibility), V_B incl. commute
  dwelling  500 PUMS movers (estimation sample), 30 sampled dwellings (r06 data and draws), V_A
  county    500 PUMS movers, all available counties (county_data_est.pkl of r07, step Ja), U_r with the stored inclusive values
  ivb       200 movers: IV_B recomputed by the engine function from the 2016 stock, the respec accessibility file and the own-group
            shares, against the stored IV_B (r07)
  iva       200 movers: IV_A recomputed by the engine function from the r07 pool draws (seed 44), against the stored IV_A
Writes WORKSPACE/side_experiments/respec_2026-11/engine_check/c01_resloc_check.csv (max |difference| per part).   python3 check_residential_location.py <scratch dir>"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, pickle, json, subprocess
import numpy as np, pandas as pd
V = f"{WORKSPACE}"
HERE = f"{V}/side_experiments/respec_2026-11/engine_check"; SCR = sys.argv[1] if len(sys.argv) > 1 else HERE   # outputs (workspace)
R = f"{ESTIMATION_RESULTS}/residential"; INP = f"{V}/2_silo/input"   # R: estimation results (data)
JAVA = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip() + "/bin/java"
CP = f"{V}/2_silo/engine/useCases/maryland/target/classes"
COEF_Z = f"{INP}/residential_zone_dwelling_coefficients.csv"; COEF_R = f"{INP}/residential_county_coefficients.csv"
ACC = f"{V}/data/accessibility_multimodal_respec_2016.csv"
sys.path.insert(0, f"{MILES_HOME}/landuse/lib/residential"); sys.path.insert(0, f"{MILES_HOME}/estimation/development/residential_location"); sys.argv = [sys.argv[0]]
import r03_sequence as R3   # noqa: E402  (zone part with the r01/r02 extensions; sets cwd to 2_silo/resloc)
import r06_dwelling_income as R6   # noqa: E402
import r07_county_iv as R7   # noqa: E402
Z = R3.Z; DW = R6.DW; RG = R7.RG
from rc import ZONE_IDS, ZIDX, INC_GROUPS, WORK   # noqa: E402
RNG = np.random.default_rng(20261109)


def java(*a):
    r = subprocess.run([JAVA, "-cp", CP, "de.tum.bgu.msm.models.resloc.ReslocRespecVerify", *a], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr)


def compare(name, inp, py, key=("id", "alt")):
    out = f"{SCR}/c01_{name}_out.csv"; java(name, COEF_R if name == "county" else COEF_Z, inp, out)
    j = pd.read_csv(out); m = py.merge(j, on=list(key), suffixes=("_py", "_java")); assert len(m) == len(py) == len(j), (name, len(m), len(py), len(j))
    d = (m.V_py - m.V_java).abs(); print(f"{name}: {len(m):,} utilities, max |diff| {d.max():.3g}", flush=True)
    return dict(part=name, n=len(m), max_abs_diff=float(d.max()), mean_abs_V=float(m.V_py.abs().mean()))


def zone():
    zf = pd.read_csv(f"{R}/r08_fit.csv"); zm = zf[zf.chosen.fillna(False).astype(bool)].model.iloc[0]
    zc = pd.read_csv(f"{R}/r08_coef.csv"); b = zc[zc.model == zm].set_index("parameter").estimate
    spec = pd.read_csv(f"{R}/r03_fit.csv").query("step == 'final'").spec.iloc[0].split()
    Z.ACC_FILE = ACC; zd = Z.zone_data(); cells = Z.cells_of_region(zd[0], zd[1])
    h, _ = Z.load_rts(); h = h[h.age_max.notna() & (h.age_max >= 0) & (h.half == "estimation")]
    h = h.iloc[np.sort(RNG.choice(len(h), 500, replace=False))]
    drawn = Z.draw(h, zd, cells, 30); X, names, av, C, ok, meta = Z.build(h, zd, cells, spec, 30, drawn=drawn)
    Vp = X @ b.reindex(names).values
    _, Dm, lncost, A, car, pt = zd; rows, py = [], []
    for i, (hh, (zi, ti)) in enumerate(zip([x for x, o in zip(h.itertuples(), ok) if o], meta)):
        seg = f"{hh.inc_group}_{hh.car}"; T = car if hh.car != "nocar" else pt
        w = [ZIDX[x] for x in hh.wz if x in ZIDX.index]
        com = np.log1p(T[np.ix_(zi, w)]).sum(axis=1) if w else np.zeros(len(zi))
        for k in range(len(zi)):
            rows.append(dict(id=i, alt=k, income=hh.income, size=hh.hhsize, child=hh.children, age_max=int(hh.age_max), nocar=int(hh.car == "nocar"),
                             lnD=np.log(Dm[zi[k], ti[k]]), aw=A[(seg, "work")][zi[k]], an=A[(seg, "nonwork")][zi[k]], lncost=lncost[zi[k]],
                             sim=R3.R1.SH[zi[k], INC_GROUPS.index(hh.inc_group)], comlog=com[k], **{v: R3.LUA[v][zi[k]] for v in R3.LUA}))   # 2026-11-10 land use
            py.append(dict(id=i, alt=k, V=Vp[i, k]))
    f = f"{SCR}/c01_zone_in.csv"; pd.DataFrame(rows).to_csv(f, index=False)
    return compare("zone", f, pd.DataFrame(py))


def dwelling():
    df = pd.read_csv(f"{R}/r06_fit.csv"); fin = df[df.validation_LL.notna()].iloc[0]; spec = set(fin.spec.split(";"))
    dc = pd.read_csv(f"{R}/r06_coef.csv"); b = dc[dc.model == fin.model].set_index("parameter").estimate
    DW.build_X = R6.build_X
    mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); est = est.iloc[np.sort(RNG.choice(len(est), 500, replace=False))].reset_index(drop=True)
    alt, av = DW.sample_alts(est, pool, 30); X, names = DW.build_X(est, alt, spec); Vp = X @ b.reindex(names).values
    rows, py = [], []
    for i, hh in enumerate(est.itertuples()):
        for k in np.flatnonzero(av[i]):
            rows.append(dict(id=i, alt=k, income=hh.income, size=hh.NP, child=int(hh.n_child > 0), age_max=int(hh.age_max), cost=alt["cost"][i, k],
                             bedrooms=alt["bed"][i, k], type=alt["dtype"][i, k], new5=int(bool(alt["new5"][i, k]))))
            py.append(dict(id=i, alt=k, V=Vp[i, k]))
    f = f"{SCR}/c01_dwelling_in.csv"; pd.DataFrame(rows).to_csv(f, index=False)
    return compare("dwelling", f, pd.DataFrame(py))


def county_data():
    sys.argv = [sys.argv[0], "final"]   # s07_region_validation (imported by r05) reads its tag from argv[1]
    import r05_region_sequence as R5
    return R5.add_growth(pickle.load(open(f"{R}/county_data_est.pkl", "rb")))


def county(D):
    F = pd.read_csv(f"{R}/r05_fit.csv"); s = F[F.final].iloc[0]
    c = pd.read_csv(f"{R}/r05_coef.csv"); c = c[c.step == s.step].set_index("parameter").estimate.to_dict(); c.setdefault("IV_A", 1.0)   # fixed at 1 only when not estimated
    names = list(c); X, nm = RG.design(D, names); Vp = X @ np.array([c[n] for n in nm])
    idx = np.sort(RNG.choice(len(D["h"]), 500, replace=False)); F_ = D["F"]; h = D["h"]; rows, py = [], []
    t = F_["d1"] + F_["d2"] + F_["d3"]
    for i in idx:
        hh = h.iloc[i]
        for r in np.flatnonzero(D["av"][i]):
            rows.append(dict(id=i, alt=r, income=hh.income, size=hh.NP, child=int(hh.n_child > 0), age_max=int(hh.age_max), ivB=F_["IV_B"][i, r],
                             ivA=F_["IV_A"][i, r], t=t[i, r], same=F_["same_region"][i, r], adj=F_["adjacent"][i, r], same_state=F_["same_state"][i, r],
                             com=F_["commute_log"][i, r], growth=F_["growth"][i, r], crime=F_["crime"][i, r]))
            py.append(dict(id=i, alt=r, V=Vp[i, r]))
    f = f"{SCR}/c01_county_in.csv"; pd.DataFrame(rows).to_csv(f, index=False)
    return compare("county", f, pd.DataFrame(py))


def ivb(D):
    z, _ = RG.region_frame(); Dm, lncost, zi, ti = R7.cells()
    zs = pd.DataFrame({"zone": ZONE_IDS, "D_SFD": Dm[:, 0], "D_SFA": Dm[:, 1], "D_MF": Dm[:, 2], "D_MH": Dm[:, 3], "lncost": np.where(np.isfinite(lncost), lncost, np.log(100.0)),   # zones without dwellings: no cells
                       **{f"sh_{g}": R7.R1.SH[:, k] for k, g in enumerate(INC_GROUPS)}, "region": z.region.values,
                       **{v: R7.LU[v].values for v in ["lnddens", "lnjden", "lnretden", "mix", "park"]}})   # 2026-11-10 land use
    fz = f"{SCR}/c01_ivb_zones.csv"; zs.to_csv(fz, index=False)
    idx = np.sort(RNG.choice(len(D["h"]), 200, replace=False)); h = D["h"].iloc[idx]
    hh = pd.DataFrame({"id": idx, "income": h.income.values, "size": h.NP.values, "child": (h.n_child.values > 0).astype(int), "age_max": h.age_max.values.astype(int),
                       "nocar": (h.car.values == "nocar").astype(int), "segment": (h.inc_group + "_" + h.car).values, "group": [INC_GROUPS.index(g) for g in h.inc_group]})
    fh = f"{SCR}/c01_ivb_hh.csv"; hh.to_csv(fh, index=False); out = f"{SCR}/c01_ivb_out.csv"
    java("ivb", COEF_Z, fh, fz, ACC, out)
    j = pd.read_csv(out); regs = D["regs"]; ri = pd.Series(np.arange(len(regs)), index=regs)
    j["V_py"] = D["F"]["IV_B"][j.id.values, ri[j.region].values]; ok = np.isfinite(j.V_py) & np.isfinite(j.V)
    assert (np.isfinite(j.V_py) == np.isfinite(j.V)).all()
    d = (j.V_py - j.V)[ok].abs(); print(f"ivb: {ok.sum():,} values, max |diff| {d.max():.3g}", flush=True)
    return dict(part="ivb", n=int(ok.sum()), max_abs_diff=float(d.max()), mean_abs_V=float(j.V_py[ok].abs().mean()))


def iva(D):
    pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet"); pr = pd.read_csv(f"{WORK}/geo_puma_region.csv")
    rng = np.random.default_rng(44); rows = []
    for r in D["regs"]:   # the draws of s06_region.iv_A in r07 (RG.RNG reset to 44 before the estimation tag)
        g = pool[pool.puma7.isin(pr[pr.region == r].puma7.values)]; g = g.iloc[rng.choice(len(g), size=min(200, len(g)), replace=False)]
        rows.append(pd.DataFrame({"region": r, "cost": g.cost.values, "bedrooms": g.BDSP.values.astype(float), "type": g.dtype.values, "new5": (g.age_dd.values <= 5).astype(int)}))
    fp = f"{SCR}/c01_iva_pool.csv"; pd.concat(rows).to_csv(fp, index=False)
    idx = np.sort(RNG.choice(len(D["h"]), 200, replace=False)); h = D["h"].iloc[idx]
    hh = pd.DataFrame({"id": idx, "income": h.income.values, "size": h.NP.values, "child": (h.n_child.values > 0).astype(int), "age_max": h.age_max.values.astype(int)})
    fh = f"{SCR}/c01_iva_hh.csv"; hh.to_csv(fh, index=False); out = f"{SCR}/c01_iva_out.csv"
    java("iva", COEF_Z, fh, fp, out)
    j = pd.read_csv(out); ri = pd.Series(np.arange(len(D["regs"])), index=D["regs"]); j["V_py"] = D["F"]["IV_A"][j.id.values, ri[j.region].values]
    d = (j.V_py - j.V).abs(); print(f"iva: {len(j):,} values, max |diff| {d.max():.3g}", flush=True)
    return dict(part="iva", n=len(j), max_abs_diff=float(d.max()), mean_abs_V=float(j.V_py.abs().mean()))


def main():
    res = [zone(), dwelling()]
    D = county_data(); res += [county(D), ivb(D), iva(D)]
    pd.DataFrame(res).to_csv(f"{HERE}/c01_resloc_check.csv", index=False); print(pd.DataFrame(res).to_string(index=False))


if __name__ == "__main__":
    main()
