#!/usr/bin/env python3
"""Residential location with TWO levels, ACS PUMS 2014-2018 movers only (2026-11-17; user: fewer model levels, upper level the PUMA,
one data source).  Sequential nested-logit estimation on the estimation half; the validation half once.

  level 2  dwelling d within the destination PUMA p: the mover's dwelling plus 29 dwellings drawn uniformly from the PUMA's market
           (dwellings of the PUMS file occupied by households that moved in within 12 months), as the former dwelling level
           V_d = burden (piecewise, knots 30 % and 50 % of income) + ln cost + bedroom shortfall / excess (bedrooms needed = household
                 size, up to 5: chosen by fit, 2026-11-17, over size - 1 / one per couple and size / 2) + built in the last 5 years
                 + structure type (SFA, MF 2-4, MF 5+, mobile home; SFD reference) x 1, x ln income, x oldest member 65+;
                 MF x (household size - 1)
           Dropped against the former dwelling level: the income interactions of cost, bedrooms and new dwellings, the age bands
           under 35 / 50-64 and the children interactions of the types.
  level 1  PUMA p (the 97 PUMAs of the zone-system area); observed: the destination PUMA (exact in the PUMS)
           U_p = lambda IV_p + car time from the origin (pieces 20-60 and > 60 min, x ln income) + same migration PUMA (x (age-50)/10)
                 + bordering + same state + commute sum ln(1 + t) (x ln income) + school learning growth x children
                 + crime x children + non-work accessibility of the household's segment (PUMA mean) + ln dwelling density (PUMA mean)
           IV_p = ln M_p + ln mean_{200 market dwellings of p} exp(V_d), M_p = the PUMA's market (weighted movers' dwellings)
           Geography of a PUMA: its zones weighted by 2016 dwellings (zones split by PUMAs: housing units in the PUMA).  The origin is
           the migration PUMA (MIGPUMA, groups of PUMAs): same migration PUMA = share of the PUMA's dwellings inside the origin area.
           The location attributes enter here only (no zone level): within a PUMA the dwelling choice has no location term.
    python3 r14_puma_two_level.py   ->  r14_fit.csv, r14_coef.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, time
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; V = WORKSPACE   # HERE: results of this step (data); CODE: this folder; PROJECT_ROOT: folder holding Validation_2026 (data)
sys.path.insert(0, f"{MILES_HOME}/landuse/lib/residential"); os.chdir(f"{MILES_HOME}/landuse/lib/residential")
sys.argv = [sys.argv[0], f"{V}/data/accessibility_2016.csv", "final"]
import s06_region as RG                                                   # noqa: E402
from rc import WORK, MICRO, INP, RAW, ZONE_IDS, ZIDX, read_skim, SKIM_CAR, inc_group   # noqa: E402
from mnl import MNL                                                       # noqa: E402
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
ACC = os.environ.get("RESLOC_ACC", f"{V}/side_experiments/respec_2026-11/step_by_step/accessibility_new/accessibility_2016_new_multimodal.csv")   # written by code/estimation/step_by_step/accessibility_new/accessibility_new.py
MSIZE = None       # 2026-11-18k: optional pd.Series puma7 -> market size M of ln M (r19); None = PUMS movers' dwellings (WGTP sum of the pool)
FILTER_LOG = []    # 2026-11-18k: movers before / after every filter of upper_data
# 2026-11-18m: crosswalk files (r20 sets the corrected r20_geo_*_zone.csv: zones without a tract point added by centroid)
GEO_PZ = os.environ.get("GEO_PZ", f"{WORK}/geo_puma_zone.csv"); GEO_MZ = os.environ.get("GEO_MZ", f"{WORK}/geo_mig_zone.csv")


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
    # 2026-11-18k fix: zones whose crosswalk housing units are all 0 (80, 139, 369, 405) gave f = 0/0 = NaN, which made the whole
    # PUMA column of Wn NaN (PUMAs 2400506, 2400507, 2400804, 2401201 never available; 885 movers dropped).  They now get weight 0.
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
    lu = pd.read_csv(f"{HERE}/zone_landuse_2016.csv").set_index("zone").reindex(ZONE_IDS); P["lnddens"] = Wn.T @ lu.lnddens.fillna(0).values
    acc = pd.read_csv(ACC); A = {s: g.set_index("zone").A.reindex(ZONE_IDS).fillna(0).values for (s, pp), g in acc.groupby(["segment", "purpose"]) if pp == "nonwork"}
    import geopandas as gpd
    g = gpd.read_file(f"{V}/2_silo/input/zones.shp")[["id", "geometry"]]; main = pz.sort_values("f").groupby("zone").puma7.last()
    g["puma"] = g.id.map(main); c = g.dropna(subset=["puma"]).dissolve("puma").buffer(50).reindex(pumas)
    ADJ = np.array([[float(i != j and c.iloc[i] is not None and c.iloc[j] is not None and c.iloc[i].intersects(c.iloc[j])) for j in range(len(pumas))] for i in range(len(pumas))])
    return z, P, pumas, pidx, Wn, A, ADJ


def upper_data(h, pool, m, G):
    z, P, pumas, pidx, Wn, A, ADJ = G
    migs, midx, O, Pw = weights_matrices(z)   # 2026-11-18m: was RG.weights_matrices (same O, Pw, fixed file)
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
    pd.DataFrame(fit).to_csv(f"{HERE}/r14{SUF}_fit.csv", index=False); pd.DataFrame(coef).to_csv(f"{HERE}/r14{SUF}_coef.csv", index=False); print(f"done {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
