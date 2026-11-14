#!/usr/bin/env python3
# Copy of 2_silo/resloc/s04_dwelling.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Level 3 of the residential location model: choice of a dwelling within the destination PUMA (ACS PUMS movers 2014-2018).

Choice set: the mover's own dwelling plus J-1 dwellings drawn at random (uniform, without replacement) from the dwellings of the
same PUMA occupied by households that moved in within 12 months (the year's market: same PUMS file).  Uniform sampling: the
McFadden correction ln(J_sampled / J_market) is the same for every alternative and drops out.
Location is held fixed by the PUMA, so the model measures only dwelling attributes; location attributes enter levels 2 and 1.

Variables (alternative d, household n), definitions identical to the engine implementation (HousingStrategyMstmMnl):
  burden      = 12 * monthly cost_d / max(income_n, 5000)  (share of annual income; capped at 3), piecewise linear with knots
                0.3 and 0.5: bur_lo = min(b, .3), bur_mid = min(max(b-.3, 0), .2), bur_hi = max(b-.5, 0)
  lncost      = ln(max(cost_d, 100))      housing consumption (unobserved quality) at a given burden
  bed_short   = max(0, need_n - bedrooms_d),  bed_extra = max(0, bedrooms_d - need_n),  need_n = 1 if size 1 else min(size-1, 4)
  SFA, MF234, MF5plus, MH   structure type dummies (SFD = 0), each also x (size-1), x children (any person < 18), x age65 (oldest
                member >= 65), x lninc (ln(max(income, 5000) / 50000))
  new5        = dwelling built within the last 5 years
Monthly cost = GRNTP (renters) or SMOCP (owners) x ADJHSG, 2016 $ (the definition of monthlyCost of the synthetic stock).
Outputs: tables/dwelling_*.csv, work/dwelling_coef_<model>.csv
"""
import sys, json
import numpy as np, pandas as pd
from rc import *
from mnl import MNL, lr_test

RNG = np.random.default_rng(20261022)
TYPES = ["SFA", "MF234", "MF5plus", "MH"]


def hh_terms(h):
    inc = np.maximum(h.income.values, 5000.0)
    size = h.NP.values.astype(float)
    return dict(inc=inc, size=size, need=np.where(size <= 1, 1.0, np.minimum(size - 1, 4.0)), child=(h.n_child.values > 0).astype(float),
                age65=(h.age_max.values >= 65).astype(float), lninc=np.log(inc / 50000.0))


def build_X(h, alt, spec):
    """alt: dict of (N, J) arrays cost, bed, dtype(str), new5.  Returns X (N, J, K), names."""
    t = hh_terms(h)
    cost = alt["cost"]; b = np.minimum(12 * cost / t["inc"][:, None], 3.0)
    cols = {}
    cols["bur_lo"] = np.minimum(b, .3); cols["bur_mid"] = np.clip(b - .3, 0, .2); cols["bur_hi"] = np.maximum(b - .5, 0)
    if "linear_burden" in spec:
        cols = {"burden": b}
    cols["lncost"] = np.log(np.maximum(cost, 100.0))
    need = t["need"][:, None]
    cols["bed_short"] = np.maximum(0, need - alt["bed"]); cols["bed_extra"] = np.maximum(0, alt["bed"] - need)
    for ty in TYPES:
        d = (alt["dtype"] == ty).astype(float)
        cols[ty] = d
        if "type_inter" in spec:
            cols[f"{ty}_x_size"] = d * (t["size"][:, None] - 1)
            cols[f"{ty}_x_child"] = d * t["child"][:, None]
            cols[f"{ty}_x_age65"] = d * t["age65"][:, None]
            cols[f"{ty}_x_lninc"] = d * t["lninc"][:, None]
    cols["new5"] = alt["new5"]
    if "burden_x_child" in spec:
        cols["burden_x_child"] = b * t["child"][:, None]
    if "group_price" in spec:
        # price, size and age terms specific to the four SILO income groups; type terms common
        grp = h.inc_group.values
        for v in ["bur_lo", "bur_mid", "bur_hi", "burden", "lncost", "bed_short", "bed_extra", "new5"]:
            if v in cols:
                x = cols.pop(v)
                for g in INC_GROUPS:
                    cols[f"{v}_{g}"] = x * (grp == g)[:, None]
        # 2026-10-27: the above-50 % burden slope is not identified for the top group (+7.5, s.e. 4.2, wrong sign): one slope for
        # $75-125k and $125k+ (exported to both groups' names by s08)
        if "pool_bur_hi_top" in spec and "bur_hi_HIGH" in cols:
            cols["bur_hi_TOP"] = cols.pop("bur_hi_HIGH") + cols.pop("bur_hi_VERY_HIGH")
    names = list(cols)
    return np.stack([cols[k] for k in names], axis=2), names


def sample_alts(h, pool, J):
    """chosen alternative in column 0, J-1 draws from the PUMA market excluding the mover's own record."""
    N = len(h)
    out = {k: np.zeros((N, J)) for k in ("cost", "bed", "new5")}; out["dtype"] = np.empty((N, J), dtype=object)
    av = np.ones((N, J), dtype=bool)
    byp = {p: g for p, g in pool.groupby("puma7")}
    for i, (sid, p) in enumerate(zip(h.SERIALNO.values, h.puma7.values)):
        g = byp[p]; g = g[g.SERIALNO.values != sid]
        k = min(J - 1, len(g)); ix = RNG.choice(len(g), size=k, replace=False)
        rows = [i]
        out["cost"][i, 0] = h.cost.values[i]; out["bed"][i, 0] = h.BDSP.values[i]; out["dtype"][i, 0] = h.dtype.values[i]; out["new5"][i, 0] = h.age_dd.values[i] <= 5
        out["cost"][i, 1:k + 1] = g.cost.values[ix]; out["bed"][i, 1:k + 1] = g.BDSP.values[ix]; out["dtype"][i, 1:k + 1] = g.dtype.values[ix]
        out["new5"][i, 1:k + 1] = g.age_dd.values[ix] <= 5
        av[i, k + 1:] = False; out["dtype"][i, k + 1:] = "NA"
    return out, av


def estimate(h, pool, J, spec, label, drawn=None, idx=None):
    alt, av = sample_alts(h, pool, J) if drawn is None else drawn
    if idx is not None:
        alt = {k: v[idx] for k, v in alt.items()}; av = av[idx]; h = h[idx].reset_index(drop=True)
    X, names = build_X(h, alt, spec)
    C = np.zeros_like(av); C[:, 0] = True
    m = MNL(X, names, av, C).fit()
    return m, (alt, av)


def predictive_ll(m, h, pool, J, spec):
    alt, av = sample_alts(h, pool, J)
    X, _ = build_X(h, alt, spec)
    C = np.zeros_like(av); C[:, 0] = True
    v = MNL(X, m.names, av, C)
    ll = v.loglik_obs(m.b).sum(); ll0 = np.log(1.0 / av.sum(axis=1)).sum()
    return ll, ll0, alt, av, X


def main():
    mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    oot = pd.read_parquet(f"{WORK}/pums_movers_oot.parquet"); pool_oot = pd.read_parquet(f"{WORK}/pums_pool_oot.parquet")
    est = mv[mv.half == "estimation"].reset_index(drop=True); val = mv[mv.half == "validation"].reset_index(drop=True)
    J = 30
    stats, tables, search = [], {}, []
    specs = {"D0 linear burden, no type interactions": {"linear_burden"},
             "D1 piecewise burden": set(),
             "D2 + type interactions": {"type_inter"},
             "D3 + burden x children": {"type_inter", "burden_x_child"},
             "D4 D2 with income-group price, bedroom and age terms": {"type_inter", "group_price"},
             "D4p D4 with one above-50 % burden slope for $75k+": {"type_inter", "group_price", "pool_bur_hi_top"}}
    prev = None; models = {}
    drawn = sample_alts(est, pool, J)          # one set of draws for every model of the search and the segmentation tests
    for lab, sp in specs.items():
        m, _ = estimate(est, pool, J, sp, lab, drawn)
        s = m.stats(lab); stats.append(s); models[lab] = (m, sp)
        ref = models["D4 D2 with income-group price, bedroom and age terms"][0] if lab.startswith("D4p") else (models["D2 + type interactions"][0] if lab.startswith("D4") else prev)
        if ref is not None:
            lr = lr_test(ref.ll, m.ll, m.k - ref.k); s["LR_reference"] = "D4 (restriction test)" if lab.startswith("D4p") else ("D2" if lab.startswith("D4") else "previous"); s.update(LR_vs_previous=lr[0], df=lr[1], p=lr[2])
        prev = m
        print(f"{lab}: LL {m.ll:.1f} K {m.k} rho2 {s['rho2']:.4f}", flush=True)
    final_lab = "D4p D4 with one above-50 % burden slope for $75k+"
    m, sp = models[final_lab]
    # segmentation tests on the final specification: separate models per segment vs pooled
    segs = {"income group (4)": est.inc_group.values,
            "tenure of the mover (own / rent)": np.where(est.owner.values == 1, "own", "rent"),
            "household size (1 / 2 / 3+)": np.where(est.NP.values >= 3, "3+", est.NP.values.astype(str)),
            "children (yes / no)": np.where(est.n_child.values > 0, "children", "none"),
            "age of oldest member (<35 / 35-64 / 65+)": pd.cut(est.age_max.values, [0, 34, 64, 200], labels=["<35", "35-64", "65+"]).astype(str)}
    seg_rows = []
    for sname, lab in segs.items():
        llu, ku = 0.0, 0
        for g in np.unique(lab):
            mg, _ = estimate(est, pool, J, sp, g, drawn, idx=(lab == g))
            llu += mg.ll; ku += mg.k
            if sname.startswith("income"):
                tables[f"income_{g}"] = mg.table()
        lr = lr_test(m.ll, llu, ku - m.k)
        seg_rows.append(dict(segmentation=sname, LL_pooled=m.ll, K_pooled=m.k, LL_segmented=llu, K_segmented=ku, LR=lr[0], df=lr[1], p=lr[2],
                             AIC_pooled=-2 * m.ll + 2 * m.k, AIC_segmented=-2 * llu + 2 * ku))
        print(sname, f"LR {lr[0]:.1f} df {lr[1]} p {lr[2]:.3g}", flush=True)
    pd.DataFrame(seg_rows).to_csv(f"{TAB}/dwelling_segmentation_tests.csv", index=False)
    # sensitivity to the number of sampled alternatives
    sens = []
    for Js in (10, 20, 30, 50):
        ms, _ = estimate(est, pool, Js, sp, f"J={Js}")
        t = ms.table().set_index("parameter")
        sens.append(pd.concat([pd.Series({"J": Js, "LL": ms.ll}), t.estimate]).rename(f"J{Js}"))
    pd.DataFrame(sens).to_csv(f"{TAB}/dwelling_sensitivity_J.csv")
    # held-out and out-of-time predictive LL, and observed vs predicted type / cost shares
    val_rows = []
    for nm, hh, pl in (("estimation", est, pool), ("held-out 20 % (2014-18)", val, pool), ("out-of-time 2019-21", oot, pool_oot)):
        ll, ll0, alt, av, X = predictive_ll(m, hh, pl, J, sp)
        P = MNL(X, m.names, av, np.c_[np.ones((len(hh), 1), bool), np.zeros((len(hh), J - 1), bool)])._probs(m.b)
        row = dict(sample=nm, N=len(hh), LL=ll, LL0=ll0, rho2=1 - ll / ll0, LL_per_obs=ll / len(hh))
        for ty in ["SFD"] + TYPES:
            row[f"obs_{ty}"] = (alt["dtype"][:, 0] == ty).mean(); row[f"pred_{ty}"] = (P * (alt["dtype"] == ty)).sum(axis=1).mean()
            row[f"avail_{ty}"] = ((alt["dtype"] == ty) & av).sum() / av.sum()
        burden = 12 * alt["cost"] / np.maximum(hh.income.values, 5000)[:, None]
        row["obs_mean_burden"] = np.median(burden[:, 0]); row["pred_mean_burden"] = np.nan
        row["obs_share_burden_gt_.5"] = (burden[:, 0] > .5).mean(); row["pred_share_burden_gt_.5"] = (P * (burden > .5)).sum(axis=1).mean()
        row["obs_mean_cost"] = alt["cost"][:, 0].mean(); row["pred_mean_cost"] = (P * alt["cost"]).sum(axis=1).mean()
        for g in INC_GROUPS:
            s = hh.inc_group.values == g
            row[f"obs_cost_{g}"] = alt["cost"][s, 0].mean(); row[f"pred_cost_{g}"] = (P[s] * alt["cost"][s]).sum(axis=1).mean()
        val_rows.append(row)
    pd.DataFrame(val_rows).to_csv(f"{TAB}/dwelling_validation.csv", index=False)
    # elasticities of the choice probability with respect to the monthly cost (sample enumeration, own-cost, by income group)
    alt, av = drawn; X, names = build_X(est, alt, sp)
    C = np.zeros_like(av); C[:, 0] = True
    mm = MNL(X, names, av, C); P = mm._probs(m.b)
    Xp, _ = build_X(est, dict(alt, cost=alt["cost"] * 1.01), sp)
    dV = (Xp - X) @ m.b                      # utility change from a 1 % cost increase of each alternative
    el = dV * (1 - P) / 0.01                  # own elasticity per alternative
    el_rows = [dict(group="all", own_cost_elasticity=float((P * el).sum() / P.sum()))]
    for g in INC_GROUPS:
        s = est.inc_group.values == g
        el_rows.append(dict(group=g, own_cost_elasticity=float((P[s] * el[s]).sum() / P[s].sum())))
    pd.DataFrame(el_rows).to_csv(f"{TAB}/dwelling_elasticities.csv", index=False)
    t = m.table(); t.to_csv(f"{TAB}/dwelling_final_numpy.csv", index=False)
    pd.DataFrame(stats).to_csv(f"{TAB}/dwelling_specification_search.csv", index=False)
    for g, tg in tables.items():
        tg.to_csv(f"{TAB}/dwelling_segment_{g}.csv", index=False)
    json.dump({"final": final_lab, "spec": sorted(sp), "J": J}, open(f"{WORK}/dwelling_final.json", "w"))
    np.save(f"{WORK}/dwelling_beta.npy", m.b); pd.Series(m.names).to_csv(f"{WORK}/dwelling_names.csv", index=False)
    print(t.to_string()); print(pd.DataFrame(val_rows).T.to_string()); print(pd.DataFrame(el_rows).to_string())


if __name__ == "__main__":
    main()
