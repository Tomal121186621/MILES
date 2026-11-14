#!/usr/bin/env python3
"""Level 1 of the residential location model: choice of the destination region (44 SILO regions) of moving households
(ACS PUMS 2014-2018 movers whose residence one year ago was in the zone-system area), with the inclusive values of the
lower levels (sequential nested-logit estimation).

  U_rn = lam_B IV_B(r, n) + lam_A IV_A(r, n) + b_d1 d1 + b_d2 d2 + b_d3 d3 + b_same same_region + b_state same_state
         + b_c commute_log + b_ci commute_log x lninc + b_s school x child + b_k crime + b_kc crime x child [+ ASC_r]
  IV_B(r, n) = ln sum_{cells (z,t) in r} exp(V_B(z,t; n))       zone x type model (s05) without its commute term
  IV_A(r, n) = ln mean_{d in market_r} exp(V_A(d; n))           dwelling model (s04); market = PUMS dwellings occupied by
               households that moved in within 12 months, 200 per region drawn once (engine: 200 vacant dwellings of the region)
  d1, d2, d3   piecewise car peak time t (min) from the origin to another region: min(t,20), min(max(t-20,0),40), max(t-60,0),
               times (1 - same_region) (0 for the own region); origin = the MIGPUMA's zones weighted by 2016 dwellings, region = its
               zones weighted by dwellings (engine: from the current zone; 0 when r is the current region)
  same_region  share of the origin MIGPUMA's dwellings in r (engine: 1 if r is the current region)
  same_state   origin state (MIGSP) = state of r
  commute_log  sum over workers with a place of work in the zone system of ln(1 + T(r, POW)), T = dwelling-weighted mean over the
               zones of r of the jobs-weighted mean car (no-car households: transit door-to-door, 180 if no path) time to the
               zones of the POWPUMA (engine: to the job zone)
  school       SEDA 4.1 mean achievement (grade-cohort standardised, pooled 2009-2018, EB) of the region's counties, weighted by
               assessments; x child (any person < 18)
  crime        county index offenses per 100,000 / Baltimore City rate (input/crimeIndex.csv), dwelling-weighted per region
Observed outcome: the destination PUMA; where a PUMA spans several regions, P(obs) = sum of their probabilities.  Weights: expected
in-area share of destination and origin (PUMA / MIGPUMA coverage of the zone system).
Race: not used (policy choice: the old MSTM region utility had a racial-share term with weights 0.1-0.55; we exclude race from the
estimated model; a test with the own-race share is reported in tables/region_race_test.csv for transparency only).
"""
import sys, json
import numpy as np, pandas as pd
from rc import *
from mnl import MNL, lr_test
import s04_dwelling as DW

RNG = np.random.default_rng(44)
ACC_FILE = sys.argv[1] if len(sys.argv) > 1 else f"{WORK}/accessibility_provisional_2016.csv"
TAG = sys.argv[2] if len(sys.argv) > 2 else "prov"
CT = ["SFD", "SFA", "MF", "MH"]
COMBINED = {51919: [51059, 51600, 51610], 51942: [51153, 51683, 51685], 51951: [51069, 51840]}


# ---------------------------------------------------------------- region attributes
def region_frame():
    z = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone").loc[ZONE_IDS]
    regs = np.sort(z.region.unique())
    R = pd.DataFrame(index=regs)
    R["state"] = z.groupby("region").STATEFP10.first()
    R["dwellings"] = z.groupby("region").dwellings.sum()
    crime = pd.read_csv(f"{INP}/crimeIndex.csv").set_index("FIPS").CrimeIndicator
    z["crime"] = z.COUNTYFIPS.map(crime)
    R["crime"] = z.groupby("region").apply(lambda g: np.average(g.crime, weights=g.dwellings + 1e-9))
    seda = pd.read_csv(f"{RAW}/seda_county_pool_cs_4.1.csv"); seda = seda[seda.subgroup == "all"].set_index("sedacounty")
    def sc(f):
        fl = COMBINED.get(f, [f]); s = seda.reindex(fl).dropna(subset=["cs_mn_avg_eb"])
        return np.average(s.cs_mn_avg_eb, weights=s.tot_asmts) if len(s) else np.nan
    z["school"] = z.COUNTYFIPS.map({f: sc(f) for f in z.COUNTYFIPS.unique()})
    R["school"] = z.groupby("region").apply(lambda g: np.average(g.school, weights=g.dwellings + 1e-9))
    return z, R


def weights_matrices(z, R):
    regs = R.index.values; ridx = pd.Series(np.arange(len(regs)), index=regs)
    W = np.zeros((len(ZONE_IDS), len(regs)))          # zone -> region, dwelling weights normalised per region
    W[np.arange(len(ZONE_IDS)), ridx[z.region.values].values] = z.dwellings.values
    W = W / W.sum(axis=0, keepdims=True)
    mz = pd.read_csv(f"{WORK}/geo_mig_zone.csv")
    migs = np.sort(mz.mig7.unique()); midx = pd.Series(np.arange(len(migs)), index=migs)
    O = np.zeros((len(migs), len(ZONE_IDS))); Pw = np.zeros((len(migs), len(ZONE_IDS)))
    O[midx[mz.mig7].values, ZIDX[mz.zone].values] = mz.w_dd.values
    Pw[midx[mz.mig7].values, ZIDX[mz.zone].values] = mz.w_jobs.values
    O = O / np.maximum(O.sum(axis=1, keepdims=True), 1e-9); Pw = Pw / np.maximum(Pw.sum(axis=1, keepdims=True), 1e-9)
    return regs, ridx, W, migs, midx, O, Pw


# ---------------------------------------------------------------- inclusive values
def iv_B(h, z, beta, names, A):
    """ln sum over the region's cells of exp(V_B) without commute, per household x region."""
    b = dict(zip(names, beta))
    D = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["zone", "type", "monthlyCost"])
    D["ct"] = D.type.replace({"MF234": "MF", "MF5plus": "MF"})
    Dm = D.groupby(["zone", "ct"]).size().unstack(fill_value=0).reindex(index=ZONE_IDS, columns=CT, fill_value=0).values.astype(float)
    lncost = np.log(np.maximum(D.groupby("zone").monthlyCost.mean().reindex(ZONE_IDS).values, 100.0))
    zi, ti = np.nonzero(Dm > 0)
    reg = z.region.values[zi]
    regs = np.sort(z.region.unique()); rix = np.searchsorted(regs, reg)
    out = np.full((len(h), len(regs)), -np.inf)
    lninc = np.log(np.maximum(h.income.values, 5000) / 50000)
    seg = (h.inc_group + "_" + h.car).values
    child = (h.n_child.values > 0).astype(float); a65 = (h.age_max.values >= 65).astype(float); nocar = (h.car.values == "nocar").astype(float)
    for s in np.unique(seg):
        idx = np.where(seg == s)[0]
        aw = A[(s, "work")][zi]; an = A[(s, "nonwork")][zi]
        base = b["lnD"] * np.log(Dm[zi, ti]) + b.get("accW", 0) * aw + b.get("accN", 0) * an + b.get("lncost", 0) * lncost[zi]
        for k0 in range(0, len(idx), 2000):
            ii = idx[k0:k0 + 2000]
            V = (base[None, :] + b.get("accN_x_child", 0) * an[None, :] * child[ii, None] + b.get("accN_x_age65", 0) * an[None, :] * a65[ii, None]
                 + b.get("accW_x_nocar", 0) * aw[None, :] * nocar[ii, None] + b.get("lncost_x_inc", 0) * lncost[zi][None, :] * lninc[ii, None])
            m = V.max(axis=1, keepdims=True)
            E = np.exp(V - m)
            S = np.zeros((len(ii), len(regs)))
            np.add.at(S.T, rix, E.T)
            out[ii] = np.log(S) + m
    return out


def iv_A(h, pool, regs, beta, names, spec, n_per_region=200):
    """ln mean over 200 market dwellings of the region of exp(V_A), per household x region."""
    pr = pd.read_csv(f"{WORK}/geo_puma_region.csv")
    out = np.zeros((len(h), len(regs)))
    for j, r in enumerate(regs):
        pumas = pr[pr.region == r].puma7.values
        g = pool[pool.puma7.isin(pumas)]
        g = g.iloc[RNG.choice(len(g), size=min(n_per_region, len(g)), replace=False)]
        for k0 in range(0, len(h), 3000):
            hh = h.iloc[k0:k0 + 3000]; n = len(hh)
            alt = {"cost": np.tile(g.cost.values, (n, 1)), "bed": np.tile(g.BDSP.values.astype(float), (n, 1)),
                   "dtype": np.tile(g.dtype.values, (n, 1)), "new5": np.tile((g.age_dd.values <= 5).astype(float), (n, 1))}
            X, nm = DW.build_X(hh, alt, spec)
            assert nm == list(names), (nm, names)
            V = X @ beta
            m = V.max(axis=1, keepdims=True)
            out[k0:k0 + n, j] = (np.log(np.exp(V - m).mean(axis=1)) + m[:, 0])
    return out


# ---------------------------------------------------------------- data assembly
def assemble(h, pool, tag):
    z, R = region_frame()
    regs, ridx, W, migs, midx, O, Pw = weights_matrices(z, R)
    car = read_skim(SKIM_CAR); car = np.where(np.isnan(car), 300.0, car)
    pt = read_skim(SKIM_PT_D2D); pt = np.where(np.isnan(pt), 180.0, np.minimum(pt, 180.0))
    h = h[h.mig7.isin(migs)].reset_index(drop=True)
    # car availability: VEH against persons aged 16+ (drivers; PUMS has no licence variable), as in data/accessibility_<year>.csv
    h["car"] = np.select([h.VEH.fillna(0) <= 0, h.VEH.fillna(0) < h.n_p16], ["nocar", "carlt"], "carge")
    # origin -> region time; same region share; same state
    om = O[midx[h.mig7].values]                          # (N, zones)
    T_or = (om @ car) @ W                                # (N, regions)
    same_region = om @ (W > 0).astype(float)             # share of origin dwellings in r
    same_state = (np.floor(h.mig7.values / 100000)[:, None] == R.state.values[None, :]).astype(float)
    # commute: workers' POWs (in-area only)
    Tcar_r = W.T @ car; Tpt_r = W.T @ pt                 # (regions, zones): from region (dwelling-weighted) to zone j
    com = np.zeros((len(h), len(regs))); nw_in = np.zeros(len(h))
    for i, (s, c) in enumerate(zip(h.pow7s.values, h.car.values)):
        if not isinstance(s, str) or not s:
            continue
        T = Tpt_r if c == "nocar" else Tcar_r
        for p in s.split(";"):
            p = int(p)
            if p in midx.index:
                com[i] += np.log1p(T @ Pw[midx[p]]); nw_in[i] += 1
    # chosen set and weights
    pr = pd.read_csv(f"{WORK}/geo_puma_region.csv")
    C = np.zeros((len(h), len(regs)), bool)
    for p, g in pr.groupby("puma7"):
        rows = np.where(h.puma7.values == p)[0]
        C[np.ix_(rows, ridx[g.region.values].values)] = True
    w = (h.dest_cov * h.orig_cov).values; w = w / w.mean()
    # inclusive values
    zb = np.load(f"{WORK}/zone_beta_{TAG}.npy"); zn = pd.read_csv(f"{WORK}/zone_names_{TAG}.csv").iloc[:, 0].tolist()
    acc = pd.read_csv(ACC_FILE)
    A = {(s, p): g.set_index("zone").A.reindex(ZONE_IDS).values for (s, p), g in acc.groupby(["segment", "purpose"])}
    IVB = iv_B(h, z, zb, zn, A)
    db = np.load(f"{WORK}/dwelling_beta.npy"); dn = pd.read_csv(f"{WORK}/dwelling_names.csv").iloc[:, 0].tolist()
    dspec = set(json.load(open(f"{WORK}/dwelling_final.json"))["spec"])
    IVA = iv_A(h, pool, regs, db, dn, dspec)
    lninc = np.log(np.maximum(h.income.values, 5000) / 50000)
    child = (h.n_child.values > 0).astype(float)
    Tx = T_or * (1 - same_region)                       # moving distance to other regions (0 for the own region)
    F = {"IV_B": IVB, "IV_A": IVA, "d1": np.minimum(Tx, 20), "d2": np.clip(Tx - 20, 0, 40), "d3": np.maximum(Tx - 60, 0),
         "same_region": same_region, "same_state": same_state, "commute_log": com, "commute_log_x_inc": com * lninc[:, None],
         "school_x_child": np.tile(R.school.values, (len(h), 1)) * child[:, None], "school": np.tile(R.school.values, (len(h), 1)),
         "crime": np.tile(R.crime.values, (len(h), 1)), "crime_x_child": np.tile(R.crime.values, (len(h), 1)) * child[:, None],
         "lnD_region": np.tile(np.log(R.dwellings.values), (len(h), 1))}
    av = np.isfinite(IVB) & (R.dwellings.values[None, :] > 0)
    C &= av
    keep = C.any(axis=1)
    h = h[keep].reset_index(drop=True)
    F = {k: v[keep] for k, v in F.items()}
    return dict(h=h, F=F, av=av[keep], C=C[keep], w=w[keep] / w[keep].mean(), regs=regs, R=R, T_or=T_or[keep], om=om[keep], nw_in=nw_in[keep])


def design(D, vars_, asc=False, inter=None):
    """X from feature dict; inter = {var: groups array} -> var interacted with group dummies (replacing var)."""
    cols, names = [], []
    for v in vars_:
        x = D["F"][v]
        if inter and v in inter:
            g = inter[v]
            for lev in np.unique(g):
                cols.append(x * (g == lev)[:, None]); names.append(f"{v}_{lev}")
        else:
            cols.append(x); names.append(v)
    if asc:
        for j, r in enumerate(D["regs"]):
            if r == 24510:   # Baltimore City = reference
                continue
            e = np.zeros_like(D["F"]["d1"]); e[:, j] = 1; cols.append(e); names.append(f"asc_{r}")
    return np.stack(cols, axis=2), names


def balt_migs():
    """MIGPUMAs whose in-area dwellings lie mostly (> 50 %) in the six Baltimore-region counties."""
    mz = pd.read_csv(f"{WORK}/geo_mig_zone.csv"); z = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone")
    mz["balt"] = mz.zone.map(z.region).isin([24003, 24005, 24013, 24025, 24027, 24510])
    sh = mz.groupby("mig7").apply(lambda g: np.average(g.balt, weights=g.w_dd + 1e-9))
    return sh[sh > .5].index.values


SPECS = {
    "R0 distance only": ["d1", "d2", "d3"],
    "R1 + same region, same state": ["d1", "d2", "d3", "same_region", "same_state"],
    "R2 + region size ln dwellings": ["d1", "d2", "d3", "same_region", "same_state", "lnD_region"],
    "R3 IV_B replaces size": ["d1", "d2", "d3", "same_region", "same_state", "IV_B"],
    "R4 + IV_A": ["d1", "d2", "d3", "same_region", "same_state", "IV_B", "IV_A"],
    "R5 + commute": ["d1", "d2", "d3", "same_region", "same_state", "IV_B", "IV_A", "commute_log", "commute_log_x_inc"],
    "R6 + school x children, crime": ["d1", "d2", "d3", "same_region", "same_state", "IV_B", "IV_A", "commute_log", "commute_log_x_inc",
                                      "school_x_child", "crime", "crime_x_child"],
    "R7 + school main effect": ["d1", "d2", "d3", "same_region", "same_state", "IV_B", "IV_A", "commute_log", "commute_log_x_inc",
                                "school", "school_x_child", "crime", "crime_x_child"],
}
FINAL = "R7 + school main effect"


def main():
    mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    oot = pd.read_parquet(f"{WORK}/pums_movers_oot.parquet"); pool_oot = pd.read_parquet(f"{WORK}/pums_pool_oot.parquet")
    De = assemble(mv[mv.half == "estimation"], pool, "est")
    print("assembled estimation", len(De["h"]), flush=True)
    rows, models, prev = [], {}, None
    for lab, vs in SPECS.items():
        X, names = design(De, vs)
        m = MNL(X, names, De["av"], De["C"], weights=De["w"]).fit(); models[lab] = m
        s = m.stats(lab)
        if prev is not None and m.k > prev.k and set(prev.names) <= set(names):
            lr = lr_test(prev.ll, m.ll, m.k - prev.k); s.update(LR=lr[0], df=lr[1], p=lr[2])
        rows.append(s); prev = m
        print(lab, f"LL {m.ll:.1f} K {m.k}", dict(zip(names, np.round(m.b, 3))), flush=True)
    vs = SPECS[FINAL]
    # income-group interactions of the key terms (SILO structure), and the calibrated variant with region constants
    g = De["h"].inc_group.values
    inter = {v: g for v in ["IV_B", "IV_A", "d1", "d2", "d3", "same_region", "commute_log"]}
    X, names = design(De, vs, inter=inter)
    mi = MNL(X, names, De["av"], De["C"], weights=De["w"]).fit(); models["R8 R7 with income-group IV, distance, inertia, commute"] = mi
    s = mi.stats("R8 R7 with income-group IV, distance, inertia, commute"); lr = lr_test(models[FINAL].ll, mi.ll, mi.k - models[FINAL].k)
    s.update(LR=lr[0], df=lr[1], p=lr[2]); rows.append(s)
    X, names = design(De, [v for v in vs if v not in ("school", "crime")], asc=True, inter=inter)
    ma = MNL(X, names, De["av"], De["C"], weights=De["w"]).fit(); models["R9 R8 + 43 region constants"] = ma
    s = ma.stats("R9 R8 + 43 region constants"); lr = lr_test(mi.ll, ma.ll, ma.k - mi.k); s.update(LR=lr[0], df=lr[1], p=lr[2]); rows.append(s)
    print("R8", mi.ll, "R9", ma.ll, flush=True)
    pd.DataFrame(rows).to_csv(f"{TAB}/region_specification_search_{TAG}.csv", index=False)
    for lab, fn in ((FINAL, "R7"), ("R8 R7 with income-group IV, distance, inertia, commute", "R8"), ("R9 R8 + 43 region constants", "R9")):
        models[lab].table().to_csv(f"{TAB}/region_{fn}_{TAG}.csv", index=False)
    # segmentation tests on R7: fully separate models per segment
    h = De["h"]
    segs = {"income group (4)": g, "tenure (own / rent)": np.where(h.owner.values == 1, "own", "rent"),
            "household size (1 / 2 / 3+)": np.where(h.NP.values >= 3, "3+", h.NP.values.astype(str)),
            "children (yes / no)": (h.n_child.values > 0).astype(str),
            "age of oldest member (<35 / 35-64 / 65+)": pd.cut(h.age_max.values, [0, 34, 64, 200], labels=["<35", "35-64", "65+"]).astype(str),
            "origin in the Baltimore region (6 counties) / elsewhere": np.where(np.isin(h.mig7.values, balt_migs()), "baltimore", "other")}
    X, names = design(De, vs)
    seg_rows = []
    for sn, lab in segs.items():
        llu, ku = 0, 0
        for lev in np.unique(lab):
            s_ = lab == lev
            mg = MNL(X[s_], names, De["av"][s_], De["C"][s_], weights=De["w"][s_]).fit(); llu += mg.ll; ku += mg.k
        lr = lr_test(models[FINAL].ll, llu, ku - models[FINAL].k)
        seg_rows.append(dict(segmentation=sn, LL_pooled=models[FINAL].ll, K_pooled=models[FINAL].k, LL_segmented=llu, K_segmented=ku, LR=lr[0], df=lr[1], p=lr[2]))
        print(sn, lr, flush=True)
    pd.DataFrame(seg_rows).to_csv(f"{TAB}/region_segmentation_tests_{TAG}.csv", index=False)
    # save
    import pickle
    pickle.dump({"models": {k: (m.names, m.b, m.cov_robust) for k, m in models.items()}, "final": FINAL}, open(f"{WORK}/region_models_{TAG}.pkl", "wb"))
    pickle.dump(De, open(f"{WORK}/region_data_est_{TAG}.pkl", "wb"))
    Dv = assemble(mv[mv.half == "validation"], pool, "val"); pickle.dump(Dv, open(f"{WORK}/region_data_val_{TAG}.pkl", "wb"))
    Do = assemble(oot, pool_oot, "oot"); pickle.dump(Do, open(f"{WORK}/region_data_oot_{TAG}.pkl", "wb"))
    print(models[FINAL].table().to_string()); print(mi.table().to_string())


if __name__ == "__main__":
    main()
