#!/usr/bin/env python3
# Copy of the project script of the two-level residential location model (estimation helpers).
# (manual-estimation package; only file paths changed, marked "# PATH (package)", and the household ids of upper_data kept)
"""Two-level residential location model: helpers of the estimation (ACS PUMS 2014-2018 movers).

  dw_X(h, alt)        design of the dwelling level (the final specification is a subset; see build_estimation_data.py)
  sample(h, pool)     the mover's dwelling plus 29 dwellings drawn uniformly from the dwellings of the same PUMA occupied by
                      households that moved in within 12 months (generator RNG; the mover's own record excluded)
  geography()         PUMA attributes: zones of each PUMA weighted by 2016 dwellings (a zone split by PUMAs: by housing units),
                      crime, ln dwelling density, bordering PUMAs; crosswalk files GEO_PZ / GEO_MZ, in which zones without a
                      tract internal point belong to the PUMA of their centroid (crosswalk.py)
  upper_data(...)     design of the PUMA level for every PUMA of the zone-system area: inclusive value of the dwelling level
                      (ln mean of exp(V_d) over 200 market dwellings of the PUMA drawn with RNG), ln market size (MSIZE), car time from
                      the origin migration area, previous-area share, bordering, same state, commute, crime x children,
                      ln dwelling density, own-race share; observation weights dest_cov x orig_cov / mean
main() is the specification search of the project (larger term set), kept for reference; the package uses the functions above."""
import os, sys, time
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); SH = os.path.abspath(f"{HERE}/../../../00_shared_data")   # PATH (package)
sys.path.insert(0, HERE)   # PATH (package): copies of the residential modules are in this folder
_argv = sys.argv; sys.argv = [sys.argv[0], f"{SH}/accessibility/accessibility_2016.csv", "final"]   # PATH (package); read by s06_region at import
import s06_region as RG                                                   # noqa: E402
from rc import WORK, MICRO, INP, RAW, ZONE_IDS, ZIDX, read_skim, SKIM_CAR, inc_group   # noqa: E402
from mnl import MNL                                                       # noqa: E402
sys.argv = _argv   # package: command line restored
SKIM_PT_D2D = RG.SKIM_PT_D2D
RNG = np.random.default_rng(20261117); J = 30
TYPES = ["SFA", "MF234", "MF5plus", "MH"]
DW = ["bur_lo", "bur_mid", "bur_hi", "lncost", "bed_short", "bed_extra", "new5"] + TYPES + [f"{t}_x_lninc" for t in TYPES] \
     + [f"{t}_x_age65" for t in TYPES] + ["MF234_x_size", "MF5plus_x_size"]
INC = ["bur_mid_x_lninc", "bur_hi_x_lninc", "lncost_x_lninc", "bed_short_x_lninc", "bed_extra_x_lninc", "new5_x_lninc"]
if os.environ.get("DW_INC", "1") == "1": DW = DW + INC   # 2026-11-17 v2: without them the dwelling LL fell 453 (the income interactions of the former model)
UP = ["IVd", "lnM", "d2", "d3", "d2_x_lninc", "d3_x_lninc", "same", "same_x_age", "adjacent", "same_state", "commute_log", "commute_log_x_inc",
      "crime_x_child", "lnddens"]   # v2: non-work accessibility (wrong sign, -0.19, t -4.5) and school growth x children (t 0.9) dropped
RACE = os.environ.get("RACE_TEST") == "1"   # sensitivity only (race is excluded from the model of record): own-race share of the PUMA
if RACE: UP = UP + ["own_race"]
RACE_INTER = [x for x in os.environ.get("RACE_INTER", "").split(",") if x]   # own_race_x_lninc, own_race_x_child
UP = UP + RACE_INTER
SUF = "_race" if RACE else ""
DROP = [x for x in os.environ.get("DROP_TERMS", "").split(",") if x]   # sensitivity: terms left out
if DROP: UP = [u for u in UP if u not in DROP]; SUF = SUF + "_no_" + "_".join(DROP)
if RACE_INTER: SUF = SUF + "_" + "_".join(RACE_INTER)
ACC = f"{SH}/accessibility/accessibility_2016_new_multimodal.csv"   # PATH (package)
MSIZE = None       # optional pd.Series puma7 -> market size M of ln M (build_estimation_data sets it); None = PUMS movers' dwellings (WGTP sum)
FILTER_LOG = []    # movers before / after every filter of upper_data
# crosswalk files: every zone has a row (zones without a tract internal point assigned by centroid; see crosswalk.py)
GEO_PZ = os.environ.get("GEO_PZ", f"{WORK}/geo_puma_zone_all.csv"); GEO_MZ = os.environ.get("GEO_MZ", f"{WORK}/geo_mig_zone_all.csv")   # PATH (package)


def weights_matrices(z):
    """s06_region.weights_matrices (origin O / workplace Pw weights of the migration PUMAs) reading GEO_MZ"""
    mz = pd.read_csv(GEO_MZ)
    migs = np.sort(mz.mig7.unique()); midx = pd.Series(np.arange(len(migs)), index=migs)
    O = np.zeros((len(migs), len(ZONE_IDS))); Pw = np.zeros((len(migs), len(ZONE_IDS)))
    O[midx[mz.mig7].values, ZIDX[mz.zone].values] = mz.w_dd.values; Pw[midx[mz.mig7].values, ZIDX[mz.zone].values] = mz.w_jobs.values
    O = O / np.maximum(O.sum(axis=1, keepdims=True), 1e-9); Pw = Pw / np.maximum(Pw.sum(axis=1, keepdims=True), 1e-9)
    return migs, midx, O, Pw


def dw_X(h, alt):
    inc = np.maximum(h.income.values, 5000.0)[:, None]; size = h.NP.values.astype(float)[:, None]
    need = np.minimum(size, 5.0); lninc = np.log(inc / 50000.0); a65 = (h.age_max.values >= 65)[:, None] * 1.0
    b = np.minimum(12 * alt["cost"] / inc, 3.0); c = {}
    c["bur_lo"] = np.minimum(b, .3); c["bur_mid"] = np.clip(b - .3, 0, .2); c["bur_hi"] = np.maximum(b - .5, 0); c["lncost"] = np.log(np.maximum(alt["cost"], 100.0))
    c["bed_short"] = np.maximum(0, need - alt["bed"]); c["bed_extra"] = np.maximum(0, alt["bed"] - need); c["new5"] = alt["new5"]
    for t in TYPES:
        d = (alt["dtype"] == t) * 1.0; c[t] = d; c[f"{t}_x_lninc"] = d * lninc; c[f"{t}_x_age65"] = d * a65
    c["MF234_x_size"] = (alt["dtype"] == "MF234") * (size - 1); c["MF5plus_x_size"] = (alt["dtype"] == "MF5plus") * (size - 1)
    for k in INC: c[k] = c[k.replace("_x_lninc", "")] * lninc
    return np.stack([c[k] for k in DW], 2)


def sample(h, pool):
    N = len(h); out = {k: np.zeros((N, J)) for k in ("cost", "bed", "new5")}; out["dtype"] = np.full((N, J), "NA", dtype=object); av = np.zeros((N, J), bool)
    byp = {p: g for p, g in pool.groupby("puma7")}
    for i, (sid, p) in enumerate(zip(h.SERIALNO.values, h.puma7.values)):
        g = byp[p]; g = g[g.SERIALNO.values != sid]; k = min(J - 1, len(g)); ix = RNG.choice(len(g), size=k, replace=False)
        out["cost"][i, 0] = h.cost.values[i]; out["bed"][i, 0] = h.BDSP.values[i]; out["dtype"][i, 0] = h.dtype.values[i]; out["new5"][i, 0] = h.age_dd.values[i] <= 5
        out["cost"][i, 1:k + 1] = g.cost.values[ix]; out["bed"][i, 1:k + 1] = g.BDSP.values[ix]; out["dtype"][i, 1:k + 1] = g.dtype.values[ix]
        out["new5"][i, 1:k + 1] = g.age_dd.values[ix] <= 5; av[i, :k + 1] = True
    return out, av


def lower(est, val, pool):
    alt, av = sample(est, pool); X = dw_X(est, alt); C = np.zeros_like(av); C[:, 0] = True
    m = MNL(X, DW, av, C).fit()
    altv, avv = sample(val, pool); Xv = dw_X(val, altv); Cv = np.zeros_like(avv); Cv[:, 0] = True
    return m, float(MNL(Xv, DW, avv, Cv).loglik_obs(m.b).sum()), float(np.log(1.0 / av.sum(1)).sum())


def geography():
    z = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone").loc[ZONE_IDS]
    pz = pd.read_csv(GEO_PZ); pz = pz[pz.zone.isin(ZIDX.index)]
    # zones whose crosswalk housing units are all 0 get weight 0 (0/0 would make the whole PUMA column of Wn NaN)
    tot = pz.groupby("zone").hu.transform("sum"); pz["f"] = np.where(tot > 0, pz.hu / tot.where(tot > 0, 1), 0.0)
    pumas = np.sort(pz.puma7.unique()); pidx = pd.Series(np.arange(len(pumas)), index=pumas)
    W = np.zeros((len(ZONE_IDS), len(pumas))); W[ZIDX[pz.zone].values, pidx[pz.puma7].values] = pz.f.values * z.dwellings.reindex(pz.zone).fillna(0).values
    dw = W.sum(0); Wn = W / np.maximum(dw, 1e-9)
    assert np.isfinite(W).all() and (dw > 0).all(), "PUMA weights not finite / PUMA without dwellings"
    crime = pd.read_csv(f"{INP}/crimeIndex.csv").set_index("FIPS").CrimeIndicator; z["crime"] = z.COUNTYFIPS.map(crime)
    seda = pd.read_csv(f"{RAW}/seda_county_pool_cs_4.1.csv"); seda = seda[seda.subgroup == "all"].set_index("sedacounty")
    def gr(f):
        s = seda.reindex(RG.COMBINED.get(f, [f])).dropna(subset=["cs_mn_grd_eb"]); return np.average(s.cs_mn_grd_eb, weights=s.tot_asmts) if len(s) else np.nan
    z["growth"] = z.COUNTYFIPS.map({f: gr(f) for f in z.COUNTYFIPS.unique()})
    P = pd.DataFrame(index=pumas); P["state"] = pumas // 100000; P["dwellings"] = dw
    for v in ["crime", "growth"]: P[v] = Wn.T @ z[v].fillna(z[v].mean()).values
    lu = pd.read_csv(f"{SH}/resloc_work/zone_landuse_2016.csv")   # PATH (package)
    lu = lu.set_index("zone").reindex(ZONE_IDS); P["lnddens"] = Wn.T @ lu.lnddens.fillna(0).values
    acc = pd.read_csv(ACC); A = {s: g.set_index("zone").A.reindex(ZONE_IDS).fillna(0).values for (s, pp), g in acc.groupby(["segment", "purpose"]) if pp == "nonwork"}
    import geopandas as gpd
    g = gpd.read_file(f"{SH}/zone_system/zones.shp")   # PATH (package)
    g = g[["id", "geometry"]]; main = pz.sort_values("f").groupby("zone").puma7.last()
    g["puma"] = g.id.map(main); c = g.dropna(subset=["puma"]).dissolve("puma").buffer(50).reindex(pumas)
    ADJ = np.array([[float(i != j and c.iloc[i] is not None and c.iloc[j] is not None and c.iloc[i].intersects(c.iloc[j])) for j in range(len(pumas))] for i in range(len(pumas))])
    return z, P, pumas, pidx, Wn, A, ADJ


def upper_data(h, pool, m, G):
    z, P, pumas, pidx, Wn, A, ADJ = G
    migs, midx, O, Pw = weights_matrices(z)   # as s06_region.weights_matrices, reading GEO_MZ
    car = read_skim(SKIM_CAR); car = np.where(np.isnan(car), 300.0, car)
    pt = read_skim(SKIM_PT_D2D); pt = np.where(np.isnan(pt), 180.0, np.minimum(pt, 180.0))
    n0 = len(h); h = h[h.mig7.isin(migs)]; n1 = len(h); h = h[h.puma7.isin(pumas)].reset_index(drop=True); n2 = len(h)
    h["car"] = np.select([h.VEH.fillna(0) <= 0, h.VEH.fillna(0) < h.n_p16], ["nocar", "carlt"], "carge"); h["grp"] = inc_group(h.income.clip(lower=1).values)
    om = O[midx[h.mig7].values]; T = (om @ car) @ Wn; same = om @ (Wn > 0).astype(float); Tx = T * (1 - same)
    zp = (Wn > 0).argmax(1)                                              # main PUMA of each zone (for bordering)
    adjacent = (om @ ADJ[zp]) * (1 - same)
    same_state = ((h.mig7.values // 100000)[:, None] == P.state.values[None, :]) * 1.0
    Tc = Wn.T @ car; Tp = Wn.T @ pt; com = np.zeros((len(h), len(pumas)))
    for i, (s, cc) in enumerate(zip(h.pow7s.values, h.car.values)):
        if isinstance(s, str) and s:
            TT = Tp if cc == "nocar" else Tc
            for w in s.split(";"):
                if int(w) in midx.index: com[i] += np.log1p(TT @ Pw[midx[int(w)]])
    # inclusive value: ln M_p + ln mean over 200 market dwellings of exp(V_d)
    M = (pool.groupby("puma7").WGTP.sum() if MSIZE is None else MSIZE).reindex(pumas).fillna(0).values; IV = np.full((len(h), len(pumas)), -np.inf)
    for j, p in enumerate(pumas):
        g = pool[pool.puma7 == p]
        if len(g) == 0: continue
        g = g.iloc[RNG.choice(len(g), size=min(200, len(g)), replace=False)]
        for k0 in range(0, len(h), 3000):
            hh = h.iloc[k0:k0 + 3000]; n = len(hh)
            alt = {"cost": np.tile(g.cost.values, (n, 1)), "bed": np.tile(g.BDSP.values.astype(float), (n, 1)), "dtype": np.tile(g.dtype.values, (n, 1)),
                   "new5": np.tile((g.age_dd.values <= 5) * 1.0, (n, 1))}
            v = dw_X(hh, alt) @ m.b; mx = v.max(1, keepdims=True); IV[k0:k0 + n, j] = np.log(np.exp(v - mx).mean(1)) + mx[:, 0]
    lninc = np.log(np.maximum(h.income.values, 5000) / 50000)[:, None]; child = (h.n_child.values > 0)[:, None] * 1.0; age = ((h.age_max.values - 50) / 10)[:, None]
    accN = np.stack([Wn.T @ A[f"{gg}_{cc}"] for gg, cc in zip(h.grp, h.car)])
    F = dict(IVd=IV, lnM=np.tile(np.log(np.maximum(M, 1.0)), (len(h), 1)), d2=np.clip(Tx - 20, 0, 40), d3=np.maximum(Tx - 60, 0), same=same, adjacent=adjacent, same_state=same_state, commute_log=com,
             growth_x_child=np.tile(P.growth.values, (len(h), 1)) * child, crime_x_child=np.tile(P.crime.values, (len(h), 1)) * child, crime=np.tile(P.crime.values, (len(h), 1)),
             accN=accN, lnddens=np.tile(P.lnddens.values, (len(h), 1)))
    if RACE:   # share of the PUMA's 2016 households whose race (synthetic population, householder categories) is the mover's
        hh = pd.read_csv(f"{MICRO}/hh_2016.csv", usecols=["dwelling", "race"]); dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["id", "zone"])
        hh["zone"] = hh.dwelling.map(dd.set_index("id").zone); S = pd.crosstab(hh.zone, hh.race).reindex(ZONE_IDS).fillna(0)
        Sp = (Wn.T @ S.values) / np.maximum((Wn.T @ S.values).sum(1, keepdims=True), 1e-9); cols = list(S.columns)
        F["own_race"] = Sp.T[[cols.index(r) for r in h.head_race.values]]
        F["own_race_x_lninc"] = F["own_race"] * np.log(np.maximum(h.income.values, 5000) / 50000)[:, None]
        F["own_race_x_child"] = F["own_race"] * (h.n_child.values > 0)[:, None]
    F["d2_x_lninc"] = F["d2"] * lninc; F["d3_x_lninc"] = F["d3"] * lninc; F["same_x_age"] = same * age; F["commute_log_x_inc"] = com * lninc
    av = np.isfinite(IV) & (P.dwellings.values > 0)[None, :] & (M > 0)[None, :]
    for k in F: F[k] = np.where(np.isfinite(F[k]), F[k], 0.0)
    F["IVd"] = np.where(av, IV, 0.0)
    C = (h.puma7.values[:, None] == pumas[None, :]) & av; keep = C.any(1)
    FILTER_LOG.append(dict(movers_in=n0, after_origin_in_migpumas=n1, after_destination_in_pumas=n2, after_chosen_puma_available=int(keep.sum())))
    print(f"  upper_data movers: {n0} -> origin MIGPUMA in area {n1} -> destination PUMA in area {n2} -> chosen PUMA available {int(keep.sum())}", flush=True)
    assert keep.all(), f"{(~keep).sum()} movers dropped: chosen PUMA unavailable (NaN / zero weights)"
    w = (h.dest_cov * h.orig_cov).values[keep]
    global LAST_IDS; LAST_IDS = h.SERIALNO.values[keep]   # package: household ids of the returned rows
    return np.stack([F[k][keep] for k in UP], 2), av[keep], C[keep], w / w.mean(), int(keep.sum())


def main():
    t0 = time.time(); fit, coef = [], []
    mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    m, vll, ll0 = lower(est, val, pool)
    print(f"dwelling level: N {len(est)} K {m.k} LL {m.ll:.2f} LL0 {ll0:.2f} validation LL {vll:.2f} ({time.time() - t0:.0f} s)", flush=True)
    fit.append(dict(level="dwelling within PUMA", N=len(est), K=m.k, LL0=ll0, LL=m.ll, BIC=m.k * np.log(len(est)) - 2 * m.ll, validation_LL=vll))
    for nm, b, s in zip(DW, m.b, m.rse): coef.append(dict(level="dwelling", param=nm, coef=b, se=s, t=b / s))
    G = geography(); print(f"geography {time.time() - t0:.0f} s", flush=True)
    X, av, C, w, n = upper_data(est, pool, m, G); mu = MNL(X, UP, av, C, weights=w).fit()
    Xv, avv, Cv, wv, nv = upper_data(val, pool, m, G); vllu = float(MNL(Xv, UP, avv, Cv).loglik_obs(mu.b).sum())
    ll0u = float(np.log(1.0 / av.sum(1)).sum())
    print(f"PUMA level: N {n} K {mu.k} LL {mu.ll:.2f} LL0 {ll0u:.2f} validation LL {vllu:.2f} ({time.time() - t0:.0f} s)", flush=True)
    fit.append(dict(level="PUMA", N=n, K=mu.k, LL0=ll0u, LL=mu.ll, BIC=mu.k * np.log(n) - 2 * mu.ll, validation_LL=vllu, validation_N=nv))
    for nm, b, s in zip(UP, mu.b, mu.rse): coef.append(dict(level="PUMA", param=nm, coef=b, se=s, t=b / s))
    # inclusive-value coefficient held at 1 (the bound of the nested logit; free estimate above 1): IVd as a fixed offset
    k = UP.index("IVd"); keepk = [i for i in range(len(UP)) if i != k]
    m1 = MNL(X[:, :, keepk], [UP[i] for i in keepk], av, C, weights=w, offset=X[:, :, k]).fit()
    v1 = float(MNL(Xv[:, :, keepk], [UP[i] for i in keepk], avv, Cv, offset=Xv[:, :, k]).loglik_obs(m1.b).sum())
    print(f"PUMA level, lambda = 1: K {m1.k} LL {m1.ll:.2f} (free {mu.ll:.2f}) validation LL {v1:.2f} (free {vllu:.2f})", flush=True)
    fit.append(dict(level="PUMA, inclusive value at 1", N=n, K=m1.k, LL0=ll0u, LL=m1.ll, BIC=m1.k * np.log(n) - 2 * m1.ll, validation_LL=v1, validation_N=nv))
    for i, b, s in zip(keepk, m1.b, m1.rse): coef.append(dict(level="PUMA lambda=1", param=UP[i], coef=b, se=s, t=b / s))
    for r in coef: print(f"  {r['level']:8s} {r['param']:18s} {r['coef']: .4f} ({r['se']:.4f}) t {r['t']: .2f}")
    pd.DataFrame(fit).to_csv(f"{HERE}/two_level{SUF}_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/two_level{SUF}_coef.csv", index=False); print(f"done {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
