#!/usr/bin/env python3
"""PUMA level of the two-level residential location model: writes the estimation and hold-out tables of
model/estimate_residential_puma.py with exactly the random draws of the original estimation.

Sequence of the original run (one generator, seed final_spec.SEED): the 30-dwelling sets of the estimation half, then of the
validation half (dwelling level; not written here, see ../../../02_residential_dwelling), then the 200 market dwellings per PUMA
for the inclusive values of the estimation half, then those of the validation half.  The inclusive value
IV_p = ln mean over the 200 dwellings of exp(V_d) uses the dwelling-level estimates: by default the original estimates
(../data/raw/original_estimates.csv); with DWELLING_ESTIMATES=<csv> your Biogeme estimates of the dwelling level
(02_residential_dwelling/output/residential_dwelling_estimates.csv: columns Name, Value).
Market size: M_p = r_p x dwellings of the PUMA, r_p fixed = PUMS dwellings of households that moved in within 12 months (WGTP) x the
PUMA's share of housing units in the zone system (geo_puma_region coverage) / the PUMA's 2016 dwellings; in estimation (2016)
M_p = PUMS movers' dwellings x coverage (lnM column); market.csv gives M_p, r_p and the 2016 dwellings of every PUMA.
Added PUMA terms (columns <name>_<j>): ln dwelling density x single-person household, x oldest member under 35, x ln income;
core-city share of the PUMA (dwellings in DC or Baltimore City).
Crosswalk: geo_puma_zone_all.csv / geo_mig_zone_all.csv (crosswalk.py).  No mover is dropped (asserted in two_level.upper_data).
Check (original estimates only): the log-likelihood at the original PUMA estimates, recomputed with the original estimator
(mnl.MNL) on the exported arrays, equals the original fit (estimation weighted, validation unweighted).
Needs geopandas (bordering PUMAs from the zone polygons):  /opt/homebrew/anaconda3/bin/python3 build_estimation_data.py
    ->  ../data/estimation/puma_estimation.parquet, puma_index.csv, market.csv, design_columns.csv; ../data/holdout/puma_holdout.parquet"""
import os, sys, time
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import final_spec as F   # noqa: E402  (sets the switches of two_level and imports it)
R = F.R
from mnl import MNL      # noqa: E402
OUT = os.path.abspath(f"{HERE}/../data"); RAWD = f"{OUT}/raw"


def dwelling_beta():
    p = os.environ.get("DWELLING_ESTIMATES")
    if p:
        e = pd.read_csv(p).set_index("Name")["Value"]
        return np.array([e[F.BIOGEME[n]] for n in F.DWF]), False
    c = pd.read_csv(f"{RAWD}/original_estimates.csv"); c = c[c.level == "dwelling"].set_index("param").coef
    return c.reindex(F.DWF).values, True


NEW = ["lnddens_x_single", "lnddens_x_young35", "lnddens_x_lninc", "core_share"]   # terms added to the PUMA level
CORE = [11001, 24510]   # core-city counties: District of Columbia, Baltimore City


def extras(h, X, Wn):
    """the four added PUMA terms: ln dwelling density x single-person household, x oldest member under 35, x ln income;
    core-city share of the PUMA = sum of Wn over the zones of DC and Baltimore City (Wn: the dwelling weights of the PUMA attributes)"""
    lnd = X[:, :, R.UP.index("lnddens")]; h = h.reset_index(drop=True)
    zs = pd.read_csv(f"{R.INP}/zoneSystem.csv").set_index("ZoneId").reindex(R.ZONE_IDS)
    core = Wn.T @ np.isin(zs.COUNTYFIPS.values, CORE).astype(float)
    return {"lnddens_x_single": lnd * (h.NP.values == 1)[:, None], "lnddens_x_young35": lnd * (h.age_max.values < 35)[:, None],
            "lnddens_x_lninc": lnd * np.log(np.maximum(h.income.values, 5000) / 50000)[:, None], "core_share": np.tile(core, (len(h), 1))}


def table(ids, X, av, C, w, EX):
    J = av.shape[1]; d = {"household": ids, "choice": C.argmax(1).astype(int), "weight": w}
    for j in range(J):
        d[f"av_{j}"] = av[:, j].astype(int)
        d[f"IV_{j}"] = X[:, j, R.UP.index("IVd")]
        for n in F.UPF:
            d[f"{n}_{j}"] = X[:, j, R.UP.index(n)]
        for n in NEW:
            d[f"{n}_{j}"] = EX[n][:, j]
    return pd.DataFrame(d)


def main():
    t0 = time.time()
    mv = pd.read_parquet(f"{R.WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{R.WORK}/pums_pool_est.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    cov = pd.read_csv(f"{R.WORK}/geo_puma_region.csv").groupby("puma7").coverage.first()
    movers = pool.groupby("puma7").WGTP.sum(); R.MSIZE = movers * cov.reindex(movers.index)   # M_p of the estimation (2016)
    R.RNG = np.random.default_rng(F.SEED); G = R.geography()
    R.sample(est, pool); R.sample(val, pool)                       # draws of the dwelling level (same generator)
    b, original = dwelling_beta()
    R.dw_X = F.dw_final
    if "crime" not in R.UP: R.UP = R.UP + ["crime"]

    class B: pass
    mb = B(); mb.b = b
    fit = pd.read_csv(f"{RAWD}/original_fit.csv").set_index("level").loc["PUMA (inclusive value at 1)"]
    coef = pd.read_csv(f"{RAWD}/original_estimates.csv"); bu = coef[coef.level == "PUMA"].set_index("param").coef.reindex(F.UPF + NEW).values
    pumas = G[2]; k = [R.UP.index(v) for v in F.UPF]; iv = R.UP.index("IVd")
    for nm, h, f, ref in (("estimation", est, "estimation/puma_estimation.parquet", fit.LL), ("validation", val, "holdout/puma_holdout.parquet", fit.validation_LL)):
        X, av, C, w, n = R.upper_data(h, pool, mb, G); ids = R.LAST_IDS; assert n == len(h)
        EX = extras(h, X, G[4]); Xf = np.concatenate([X[:, :, k]] + [EX[q][:, :, None] for q in NEW], 2)
        if nm == "validation":
            w = np.ones(n)                                          # the hold-out log-likelihood is unweighted
        ll = float((w * MNL(Xf, F.UPF + NEW, av, C, offset=X[:, :, iv]).loglik_obs(bu)).sum())
        print(f"{nm}: movers {len(h)}, records {n}, PUMAs {av.shape[1]} (available per record {av.sum(1).min()}-{av.sum(1).max()}), "
              f"LL at the original estimates {ll:.4f} (original {ref:.4f}), {time.time() - t0:.0f} s", flush=True)
        if original:
            assert abs(ll - ref) < 1e-6
        df = table(ids, X, av, C, w, EX)
        if nm == "validation":
            df["weight_coverage"] = df.household.map(dict(zip(h.SERIALNO, h.dest_cov * h.orig_cov)))
        df.to_parquet(f"{OUT}/{f}", index=False)
    pd.DataFrame({"j": np.arange(len(pumas)), "puma7": pumas, "state_fips": pumas // 100000, "puma": pumas % 100000,
                  "dwellings_2016": G[1].dwellings.values.round(1)}).to_csv(f"{OUT}/estimation/puma_index.csv", index=False)
    pz = pd.read_csv(R.GEO_PZ); pz = pz[pz.zone.isin(R.ZIDX.index)].copy(); tot = pz.groupby("zone").hu.transform("sum")
    pz["f"] = np.where(tot > 0, pz.hu / tot.where(tot > 0, 1), 1.0 / pz.groupby("zone").hu.transform("size"))   # SILO membership
    dd = pd.read_csv(f"{R.MICRO}/dd_2016.csv", usecols=["zone"]).zone.value_counts(); D = (pz.f * pz.zone.map(dd).fillna(0)).groupby(pz.puma7).sum().reindex(pumas)
    Mp = R.MSIZE.reindex(pumas)
    pd.DataFrame({"puma7": pumas, "pums_movers": movers.reindex(pumas).values, "coverage": cov.reindex(pumas).values, "M_2016": Mp.values,
                  "silo_dwellings_2016": D.values, "turnover_r": (Mp / D).values}).to_csv(f"{OUT}/estimation/market.csv", index=False)
    pd.Series(F.UPF + NEW, name="design_column").to_csv(f"{OUT}/estimation/design_columns.csv", index=False)


if __name__ == "__main__":
    main()
