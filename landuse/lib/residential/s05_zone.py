#!/usr/bin/env python3
"""Level 2 of the residential location model: choice of a zone x structure-type cell within the region of residence
(2017/18 Regional Travel Survey, estimation half of data/rts_split.csv; validation on the other half).

The RTS records the current residence, not a recent move (the codebook has no residence-duration variable), so the model is
a stock-sorting model: where households of a given type live within their region, given the zone attributes.  The alternative is
a cell (zone z, type t), t in {SFD, SFA, MF (2+ units), MH} (RTS home_type 1-4; dorms and missing dropped), so the location
coefficients are estimated conditional on the structure types offered in each zone; structure-type preferences themselves
are measured at level 3.  Choice set: the observed cell plus 29 cells drawn uniformly from the cells of the region with at least one
dwelling of that type in the 2016 synthetic stock (no McFadden correction needed under uniform sampling; sensitivity J = 10..60
and full choice set reported).  Weights: RTS household weight wthhfin (normalised to mean 1; WESML, as the RTS sample is
stratified by geography).

Variables of cell (z, t) for household n (segment s = income group x car availability: no car / cars < persons aged 16+ / cars >=
persons aged 16+):
  lnD_zt        ln dwellings of type t in zone z (2016 synthetic stock; engine: current stock)               size term, coef theta
  accW, accN    logsum accessibility to jobs (work) and to non-work destinations of the household's segment (utils)
  accN_x_child, accW_x_nocar   interactions
  commute       sum over the household's workers with a usual workplace in the zone system of the peak travel time (min) from z
                to the workplace zone: car time if the household has a car, else transit door-to-door time (180 if no path)
  commute_x_inc ... and its interaction with ln(income/50k)
  lncost_z      ln mean monthly cost of all dwellings of zone z (2016 synthetic stock)  (tested; price enters at level 3)
Outputs: tables/zone_*.csv, work/zone_beta.npy, work/zone_names.csv
"""
import sys, json
import numpy as np, pandas as pd
from rc import *
from mnl import MNL, lr_test

RNG = np.random.default_rng(1022)
INC_MID = {1: 10000, 2: 20000, 3: 30000, 4: 42500, 5: 62500, 6: 87500, 7: 125000, 8: 200000}
DEFL = CPI[2016] / ((CPI[2017] + CPI[2018]) / 2)
CT = ["SFD", "SFA", "MF", "MH"]
ACC_FILE = sys.argv[1] if len(sys.argv) > 1 else f"{WORK}/accessibility_provisional_2016.csv"
TAG = sys.argv[2] if len(sys.argv) > 2 else "prov"


def load_rts():
    cols = ["household_id", "person_id", "home_state_county_fips", "home_tract_fips", "home_type", "home_ownership", "hhsize", "numworkers",
            "numvehicle", "numdrivers", "hh_income_detailed", "wthhfin", "age", "age_group", "employment_status", "j1_workplace_loc", "work_state_county_fips", "work_tract_fips"]
    r = pd.read_csv(f"{RTS}/RTS_raw_flat_data.csv", usecols=cols, low_memory=False)
    tz = pd.read_csv(TRACT_ZONE, dtype={"geoid": str}).set_index("geoid").zone

    def gid(c, t):
        c = pd.to_numeric(c, errors="coerce"); t = pd.to_numeric(t, errors="coerce")
        return np.where(c.notna() & t.notna() & (c > 0) & (t > 0), c.fillna(0).astype(np.int64).astype(str).str.zfill(5) + t.fillna(0).astype(np.int64).astype(str).str.zfill(6), "")
    h = r.drop_duplicates("household_id").set_index("household_id")
    p = r.drop_duplicates("person_id").copy()
    h["zone"] = pd.Series(gid(h.home_state_county_fips, h.home_tract_fips), index=h.index).map(tz).fillna(-1).astype(int)
    p["work_zone"] = pd.Series(gid(p.work_state_county_fips, p.work_tract_fips), index=p.index).map(tz).fillna(-1).astype(int)
    p["worker"] = p.employment_status.eq(0)
    p.loc[~(p.worker & p.j1_workplace_loc.isin([1, 2, 4])), "work_zone"] = -1
    h["wz"] = p[p.work_zone > 0].groupby("household_id").work_zone.apply(list).reindex(h.index)
    h["wz"] = h.wz.apply(lambda v: v if isinstance(v, list) else [])
    h["n_adults_listed"] = p[p.age >= 18].groupby("household_id").size().reindex(h.index).fillna(0)
    h["child_listed"] = p[(p.age >= 0) & (p.age < 18)].groupby("household_id").size().reindex(h.index).fillna(0)
    # members not in the person file (no travel-day record) are counted as children when the listed persons are all adults
    h["children"] = ((h.child_listed > 0) | (h.hhsize > h.n_adults_listed + h.child_listed)).astype(int)
    h["age_max"] = p.groupby("household_id").age.max().reindex(h.index)
    cls = h.hh_income_detailed.where(h.hh_income_detailed > 0)
    h["income"] = cls.map(INC_MID).fillna(np.nan) * DEFL
    h["inc_group"] = np.where(h.income.isna(), "NA", inc_group(h.income.fillna(1)))
    # car availability against drivers = persons aged 16+ (the definition of data/accessibility_<year>.csv, of the PUMS samples and
    # of the engine; the RTS licence variable is not used so that all three agree).  Age from `age`, else from age_group (>= 4 is
    # 16+).  About 20 % of households list fewer persons than hhsize; their unlisted members are counted as 16+ up to the number of
    # drivers (numdrivers) not accounted for by the listed persons aged 16+ (drivers are 16+; the rest are taken as under 16).
    p["p16"] = np.where(p.age >= 0, p.age >= 16, p.age_group >= 4)
    h["p16_listed"] = p.groupby("household_id").p16.sum().reindex(h.index).fillna(0)
    unlisted = (h.hhsize - p.groupby("household_id").size().reindex(h.index).fillna(0)).clip(lower=0)
    h["n_p16"] = h.p16_listed + np.clip(h.numdrivers.clip(lower=0) - h.p16_listed, 0, unlisted)
    h["car"] = np.select([h.numvehicle <= 0, h.numvehicle < h.n_p16], ["nocar", "carlt"], "carge")
    h["ctype"] = h.home_type.map({1: "SFD", 2: "SFA", 3: "MF", 4: "MH"})
    h["half"] = pd.read_csv(SPLIT).set_index("household_id").half.reindex(h.index)
    log = {"households_rts": len(h), "home_zone_in_system": int((h.zone > 0).sum()), "income_known": int(h.income.notna().sum()),
           "type_1_4": int(h.ctype.notna().sum())}
    h = h[(h.zone > 0) & h.income.notna() & h.ctype.notna()].copy()
    log["kept"] = len(h)
    return h, log


def zone_data():
    z = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone").loc[ZONE_IDS]
    dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["zone", "type", "monthlyCost"])
    dd["ct"] = dd.type.replace({"MF234": "MF", "MF5plus": "MF"})
    D = dd.groupby(["zone", "ct"]).size().unstack(fill_value=0).reindex(index=ZONE_IDS, columns=CT, fill_value=0)
    cost = dd.groupby("zone").monthlyCost.mean().reindex(ZONE_IDS)
    acc = pd.read_csv(ACC_FILE)
    A = {(s, p): g.set_index("zone").A.reindex(ZONE_IDS).values for (s, p), g in acc.groupby(["segment", "purpose"])}
    car = read_skim(SKIM_CAR); car = np.where(np.isnan(car), 300.0, car)
    pt = read_skim(SKIM_PT_D2D); pt = np.where(np.isnan(pt), 180.0, np.minimum(pt, 180.0))
    return z, D.values.astype(float), np.log(np.maximum(cost.values, 100.0)), A, car, pt


def cells_of_region(z, D):
    reg = z.region.values
    out = {}
    for r in np.unique(reg):
        zi = np.where(reg == r)[0]
        zz, tt = np.nonzero(D[zi] > 0)
        out[r] = (zi[zz], tt)
    return out


def hh_cell_X(hh, zi, ti, zd, spec):
    """X (J, K) for one household over cells (zone index zi, type index ti)."""
    z, D, lncost, A, car, pt = zd
    seg = f"{hh.inc_group}_{hh.car}"
    cols = {"lnD": np.log(D[zi, ti])}
    aw = A[(seg, "work")][zi]; an = A[(seg, "nonwork")][zi]
    if "accW" in spec: cols["accW"] = aw
    if "accN" in spec: cols["accN"] = an
    if "accN_x_child" in spec: cols["accN_x_child"] = an * hh.children
    if "accN_x_age65" in spec: cols["accN_x_age65"] = an * (hh.age_max >= 65)
    if "accW_x_nocar" in spec: cols["accW_x_nocar"] = aw * (hh.car == "nocar")
    if "commute" in spec or "commute_max" in spec or "commute_log" in spec:
        T = car if hh.car != "nocar" else pt
        w = [ZIDX[x] for x in hh.wz if x in ZIDX.index]
        tt = T[np.ix_(zi, w)] if w else np.zeros((len(zi), 0))
        if "commute" in spec: cols["commute"] = tt.sum(axis=1)
        if "commute_max" in spec: cols["commute_max"] = tt.max(axis=1) if w else np.zeros(len(zi))
        if "commute_log" in spec: cols["commute_log"] = np.log1p(tt).sum(axis=1)
        if "commute_x_inc" in spec: cols["commute_x_inc"] = tt.sum(axis=1) * np.log(max(hh.income, 5000) / 50000)
        if "commute_log_x_inc" in spec: cols["commute_log_x_inc"] = np.log1p(tt).sum(axis=1) * np.log(max(hh.income, 5000) / 50000)
    if "lncost" in spec: cols["lncost"] = lncost[zi]
    if "lncost_x_inc" in spec: cols["lncost_x_inc"] = lncost[zi] * np.log(max(hh.income, 5000) / 50000)
    return np.stack(list(cols.values()), axis=1), list(cols)


def draw(h, zd, cells, J, full=False):
    """cells of the choice set per household: observed cell first, then J-1 uniform draws (or all cells)."""
    z = zd[0]; meta, ok = [], []
    for hh in h.itertuples():
        zi_all, ti_all = cells[z.region.values[ZIDX[hh.zone]]]
        k = np.where((zi_all == ZIDX[hh.zone]) & (ti_all == CT.index(hh.ctype)))[0]
        if len(k) == 0 or len(zi_all) < 2:
            ok.append(False); continue
        others = np.setdiff1d(np.arange(len(zi_all)), k)
        sel = np.r_[k, others] if full else np.r_[k, RNG.choice(others, size=min(J - 1, len(others)), replace=False)]
        meta.append((zi_all[sel], ti_all[sel])); ok.append(True)
    return meta, np.array(ok)


def build(h, zd, cells, spec, J, full=False, drawn=None):
    meta, ok = drawn if drawn is not None else draw(h, zd, cells, J, full)
    hs = [hh for hh, o in zip(h.itertuples(), ok) if o]
    Xs = []
    for hh, (zi, ti) in zip(hs, meta):
        X, names = hh_cell_X(hh, zi, ti, zd, spec); Xs.append(X)
    Jm = max(len(x) for x in Xs); K = Xs[0].shape[1]
    Xa = np.zeros((len(Xs), Jm, K)); av = np.zeros((len(Xs), Jm), bool)
    for i, x in enumerate(Xs):
        Xa[i, :len(x)] = x; av[i, :len(x)] = True
    C = np.zeros_like(av); C[:, 0] = True
    return Xa, names, av, C, ok, meta


SPECS = {
    "Z0 size only": ["lnD"],
    "Z1 + accessibility work": ["lnD", "accW"],
    "Z2 + accessibility non-work": ["lnD", "accW", "accN"],
    "Z3 + commute (sum, linear)": ["lnD", "accW", "accN", "commute"],
    "Z4 + interactions (children, 65+, no car)": ["lnD", "accW", "accN", "commute", "accN_x_child", "accN_x_age65", "accW_x_nocar"],
    "Z5 + commute x income": ["lnD", "accW", "accN", "commute", "commute_x_inc", "accN_x_child", "accN_x_age65", "accW_x_nocar"],
    "Z6 + zone price level": ["lnD", "accW", "accN", "commute", "commute_x_inc", "accN_x_child", "accN_x_age65", "accW_x_nocar", "lncost", "lncost_x_inc"],
}
ALT_COMMUTE = {"Z5b commute max instead of sum": ["lnD", "accW", "accN", "commute_max", "accN_x_child", "accN_x_age65", "accW_x_nocar"],
               "Z5c commute sum of ln(1+t)": ["lnD", "accW", "accN", "commute_log", "accN_x_child", "accN_x_age65", "accW_x_nocar"]}
SPECS["Z7 commute ln(1+t) with income, zone price level"] = ["lnD", "accW", "accN", "commute_log", "commute_log_x_inc", "accN_x_child", "accN_x_age65",
                                                             "accW_x_nocar", "lncost", "lncost_x_inc"]
FINAL = "Z7 commute ln(1+t) with income, zone price level"


def main():
    h, log = load_rts()
    zd = zone_data(); cells = cells_of_region(zd[0], zd[1])
    est = h[h.half == "estimation"].copy(); val = h[h.half == "validation"].copy()
    J = 30
    rows = []; models = {}; prev = None
    drawn = draw(est, zd, cells, J)       # one set of draws for the whole specification search and the segmentation tests
    for lab, sp in {**SPECS, **ALT_COMMUTE}.items():
        X, names, av, C, ok, _ = build(est, zd, cells, set(sp), J, drawn=drawn)
        w = est.wthhfin.values[ok]; w = w / w.mean()
        m = MNL(X, names, av, C, weights=w).fit(); models[lab] = (m, sp)
        s = m.stats(lab)
        ref = models["Z4 + interactions (children, 65+, no car)"][0] if lab.startswith("Z5b") or lab.startswith("Z5c") else prev
        if ref is not None:
            if m.k > ref.k:
                lr = lr_test(ref.ll, m.ll, m.k - ref.k); s.update(LR=lr[0], df=lr[1], p=lr[2])
        rows.append(s)
        if lab in SPECS: prev = m
        print(lab, f"LL {m.ll:.1f} K {m.k} conv {m.converged}", flush=True)
    log["estimation_households_used"] = int(ok.sum()); log["dropped_cell_not_in_stock"] = int((~ok).sum())
    pd.DataFrame(rows).to_csv(f"{TAB}/zone_specification_search_{TAG}.csv", index=False)
    m, sp = models[FINAL]
    m.table().to_csv(f"{TAB}/zone_final_{TAG}.csv", index=False)
    np.save(f"{WORK}/zone_beta_{TAG}.npy", m.b); pd.Series(m.names).to_csv(f"{WORK}/zone_names_{TAG}.csv", index=False)
    # segmentation tests (same draws for pooled and segmented)
    X, names, av, C, ok, _ = build(est, zd, cells, set(sp), J, drawn=drawn)
    e2 = est[ok]; w = e2.wthhfin.values / e2.wthhfin.values.mean()
    pooled = MNL(X, names, av, C, weights=w).fit()
    segs = {"income group (4)": e2.inc_group.values, "tenure (own / rent)": np.where(e2.home_ownership.values == 1, "own", "rent"),
            "household size (1 / 2 / 3+)": np.where(e2.hhsize.values >= 3, "3+", e2.hhsize.values.astype(str)),
            "children (yes / no)": e2.children.values.astype(str),
            "age of oldest member (<35 / 35-64 / 65+)": pd.cut(e2.age_max.values, [-10, 34, 64, 200], labels=["<35", "35-64", "65+"]).astype(str)}
    seg_rows = []
    for sn, lab in segs.items():
        llu = 0; ku = 0
        for g in np.unique(lab):
            s_ = lab == g
            mg = MNL(X[s_], names, av[s_], C[s_], weights=w[s_]).fit(); llu += mg.ll; ku += mg.k
        lr = lr_test(pooled.ll, llu, ku - pooled.k)
        seg_rows.append(dict(segmentation=sn, LL_pooled=pooled.ll, K_pooled=pooled.k, LL_segmented=llu, K_segmented=ku, LR=lr[0], df=lr[1], p=lr[2]))
        print(sn, lr, flush=True)
    pd.DataFrame(seg_rows).to_csv(f"{TAB}/zone_segmentation_tests_{TAG}.csv", index=False)
    # sensitivity to J
    sens = []
    for Js in (10, 20, 30, 60):
        Xj, names, avj, Cj, okj, _ = build(est, zd, cells, set(sp), Js)
        wj = est.wthhfin.values[okj]; wj = wj / wj.mean()
        mj = MNL(Xj, names, avj, Cj, weights=wj).fit()
        sens.append(pd.concat([pd.Series({"J": Js, "LL": mj.ll}), mj.table().set_index("parameter").estimate, mj.table().set_index("parameter").robust_se.add_suffix("_rse")]))
    pd.DataFrame(sens).to_csv(f"{TAB}/zone_sensitivity_J_{TAG}.csv", index=False)
    # validation: predictive LL over the full choice set, estimation and validation halves; predicted vs observed shares
    vrows, shares = [], []; full_draws = {}
    for nm, hs in (("estimation", est), ("validation", val)):
        full_draws[nm] = draw(hs, zd, cells, J, full=True)
        X, names, av, C, ok, meta = build(hs, zd, cells, set(sp), J, full=True, drawn=full_draws[nm])
        mm = MNL(X, names, av, C); P = mm._probs(m.b)
        ll = mm.loglik_obs(m.b); ll0 = np.log(1 / av.sum(axis=1))
        w = hs.wthhfin.values[ok]
        vrows.append(dict(sample=nm, N=int(ok.sum()), LL=ll.sum(), LL0=ll0.sum(), rho2=1 - ll.sum() / ll0.sum(), LL_per_obs=ll.mean(),
                          LL_size_only=np.nan))
        hs2 = hs[ok]
        z = zd[0]
        for i, (zi, ti) in enumerate(meta):
            shares.append(pd.DataFrame({"sample": nm, "household": hs2.index[i], "inc_group": hs2.inc_group.values[i], "children": hs2.children.values[i],
                                        "zone": ZONE_IDS[zi], "ctype": np.array(CT)[ti], "p": P[i, :len(zi)], "obs": np.r_[1.0, np.zeros(len(zi) - 1)], "w": w[i]}))
    sh = pd.concat(shares)
    sh.to_parquet(f"{WORK}/zone_predictions_{TAG}.parquet")
    # size-only benchmark LL on the same full choice sets
    for k, (nm, hs) in enumerate((("estimation", est), ("validation", val))):
        X, names, av, C, ok, meta = build(hs, zd, cells, {"lnD"}, J, full=True, drawn=full_draws[nm])
        mm = MNL(X, names, av, C); b0 = models["Z0 size only"][0].b
        vrows[k]["LL_size_only"] = mm.loglik_obs(b0).sum()
    pd.DataFrame(vrows).to_csv(f"{TAB}/zone_validation_{TAG}.csv", index=False)
    json.dump(log, open(f"{TAB}/zone_data_counts_{TAG}.json", "w"), indent=1)
    print(m.table().to_string()); print(pd.DataFrame(vrows).to_string()); print(log)


if __name__ == "__main__":
    main()
