#!/usr/bin/env python3
# Copy of 2_silo/resloc/s07_region_validation.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Validation and elasticities of the region model (level 1) and the region-to-region mover flows against ACS.

  - predictive log-likelihood: estimation sample, held-out 20 % of 2014-2018, out-of-time 2019-2021 movers
  - observed vs predicted destination shares by region, all movers and by income group (observed shares of a PUMA that spans
    several regions are split by the predicted shares within the PUMA)
  - region-to-region mover flows (persons: household weight WGTP x persons NP) vs ACS county-to-county migration flows
    2014-2018 and 2016-2020 (data/raw/resloc/CtyxCty_US_*.txt), aggregated to SILO regions, both ends in the zone-system area
  - elasticities of the regional shares (sample enumeration) with respect to: the monthly cost of all dwellings in the region
    (+1 %), the commute time from the region (+1 %), and the logsum accessibility (+0.1 utils = about +10 % in the destination
    size of every zone of the region)
Outputs tables/region_validation_<tag>.csv, region_shares_<tag>.csv, region_flows_<tag>.csv, region_elasticities_<tag>.csv
"""
import sys, pickle, json
import numpy as np, pandas as pd
from rc import *
from mnl import MNL

TAG = sys.argv[1] if len(sys.argv) > 1 else "prov"
FINAL = sys.argv[2] if len(sys.argv) > 2 else "R8 R7 with income-group IV, distance, inertia, commute"
COMBINED = {51919: [51059, 51600, 51610], 51942: [51153, 51683, 51685], 51951: [51069, 51840]}
M = pickle.load(open(f"{WORK}/region_models_{TAG}.pkl", "rb"))
import s06_region as RG


def X_of(D, names):
    """rebuild the design for a saved parameter list"""
    F = D["F"]; g = D["h"].inc_group.values; cols = []
    for n in names:
        if n.startswith("asc_"):
            r = int(n[4:]); j = list(D["regs"]).index(r); e = np.zeros_like(F["d1"]); e[:, j] = 1; cols.append(e); continue
        base, grp = n, None
        for G in INC_GROUPS[::-1]:
            if n.endswith("_" + G) and n[:-len(G) - 1] in F:
                base, grp = n[:-len(G) - 1], G; break
        x = F[base]
        cols.append(x * (g == grp)[:, None] if grp else x)
    return np.stack(cols, axis=2)


def county_region():
    r = pd.read_csv(f"{INP}/regions.csv")
    m = {}
    for reg, cs in zip(r.region, r.counties.astype(str)):
        for c in cs.split(";"):
            for f in COMBINED.get(int(c), [int(c)]):
                if f == 10005 and reg == 7:
                    continue
                m[f] = reg
    return m


def acs_flows(path, c2r):
    rows = []
    with open(path, encoding="latin-1") as f:
        for line in f:
            if len(line) < 300:
                continue
            a = int(line[0:3]) * 1000 + int(line[3:6]); b_st = line[6:9]
            if not b_st.strip().isdigit():
                continue
            b = int(b_st) * 1000 + int(line[9:12])
            tok = line.split()
            flow = tok[-2]
            if a in c2r and b in c2r and flow.replace(".", "").isdigit():
                rows.append((c2r[b], c2r[a], float(flow)))
    fl = pd.DataFrame(rows, columns=["orig", "dest", "flow"]).groupby(["orig", "dest"]).flow.sum()
    # same-county movers of each county (A's 'movers within the same county' column) on the diagonal
    same = {}
    with open(path, encoding="latin-1") as f:
        for line in f:
            a = int(line[0:3]) * 1000 + int(line[3:6])
            if a in c2r and a not in same:
                tok = line[78:].split()
                try:
                    same[a] = float(tok[6])
                except (ValueError, IndexError):
                    pass
    d = pd.Series(same).groupby(lambda f: c2r[f]).sum()
    fl = fl.add(pd.Series(d.values, index=pd.MultiIndex.from_arrays([d.index, d.index], names=["orig", "dest"])), fill_value=0)
    return fl


def main():
    names, b, V = M["models"][FINAL]
    out_v, out_s, out_f = [], [], []
    c2r = county_region()
    acs = {k: acs_flows(f"{RAW}/CtyxCty_US_{k}.txt", c2r) for k in ("2014_2018", "2016_2020")}
    for samp in ("est", "val", "oot"):
        D = pickle.load(open(f"{WORK}/region_data_{samp}_{TAG}.pkl", "rb"))
        X = X_of(D, names)
        m = MNL(X, names, D["av"], D["C"], weights=D["w"])
        P, Q, ll = m._logs(b)
        ll0 = np.log(D["C"].sum(axis=1) / D["av"].sum(axis=1))
        out_v.append(dict(sample=samp, N=len(D["h"]), LL=float((D["w"] * ll).sum()), LL0=float((D["w"] * ll0).sum()),
                          rho2=float(1 - (D["w"] * ll).sum() / (D["w"] * ll0).sum()), LL_per_obs=float((D["w"] * ll).sum() / D["w"].sum()),
                          share_same_region_obs=float((D["w"] * (Q * D["F"]["same_region"]).sum(axis=1)).sum() / D["w"].sum()),
                          share_same_region_pred=float((D["w"] * (P * D["F"]["same_region"]).sum(axis=1)).sum() / D["w"].sum())))
        obs = Q * D["w"][:, None]; pred = P * D["w"][:, None]
        g = D["h"].inc_group.values
        for grp in ["all"] + INC_GROUPS:
            s = np.ones(len(g), bool) if grp == "all" else g == grp
            out_s.append(pd.DataFrame({"sample": samp, "group": grp, "region": D["regs"], "obs": obs[s].sum(0) / obs[s].sum(), "pred": pred[s].sum(0) / pred[s].sum(),
                                       "n_obs": obs[s].sum(0)}))
        # flows (persons)
        wp = (D["h"].WGTP * D["h"].NP).values * D["w"]
        # origin region shares of the MIGPUMA (dwelling weights)
        z = pd.read_csv(f"{WORK}/geo_zone.csv").set_index("zone").loc[ZONE_IDS]
        Rz = (z.region.values[:, None] == D["regs"][None, :]).astype(float)
        org = D["om"] @ Rz                                         # (N, regions)
        Fo = (org * wp[:, None]).T @ Q; Fp = (org * wp[:, None]).T @ P
        for i, ro in enumerate(D["regs"]):
            for j, rd in enumerate(D["regs"]):
                out_f.append(dict(sample=samp, orig=ro, dest=rd, pums_obs=Fo[i, j], model=Fp[i, j],
                                  acs_2014_2018=acs["2014_2018"].get((ro, rd), 0.0), acs_2016_2020=acs["2016_2020"].get((ro, rd), 0.0)))
    pd.DataFrame(out_v).to_csv(f"{TAB}/region_validation_{TAG}.csv", index=False)
    sh = pd.concat(out_s); sh.to_csv(f"{TAB}/region_shares_{TAG}.csv", index=False)
    fl = pd.DataFrame(out_f); fl.to_csv(f"{TAB}/region_flows_{TAG}.csv", index=False)
    # flow comparison statistics (scaled to the same total)
    st = []
    for samp, g in fl.groupby("sample"):
        for ref in ("pums_obs", "acs_2014_2018", "acs_2016_2020"):
            a = g.model / g.model.sum(); o = g[ref] / g[ref].sum()
            off = g.orig != g.dest
            st.append(dict(sample=samp, reference=ref, corr_all=np.corrcoef(a, o)[0, 1], corr_offdiag=np.corrcoef(a[off], o[off])[0, 1],
                           diag_share_model=a[~off].sum(), diag_share_ref=o[~off].sum(),
                           srmse=np.sqrt(((a - o) ** 2).mean()) / o.mean(),
                           md_inflow_share_model=a[(g.dest // 1000 == 24) | (g.dest == 24510)].sum(), md_inflow_share_ref=o[(g.dest // 1000 == 24)].sum()))
    pd.DataFrame(st).to_csv(f"{TAB}/region_flow_stats_{TAG}.csv", index=False)
    print(pd.DataFrame(out_v).to_string()); print(pd.DataFrame(st).round(3).to_string())
    # elasticities on the estimation sample
    D = pickle.load(open(f"{WORK}/region_data_est_{TAG}.pkl", "rb"))
    X = X_of(D, names); m = MNL(X, names, D["av"], D["C"], weights=D["w"]); P = m._probs(b)
    w = D["w"]
    el = []
    # (a) commute time +1 %: d ln(1+t)/d ln t ~ t/(1+t); use finite difference on the stored commute: recompute is costly, so use
    #     dV = b_c * sum_workers t/(1+t) * 0.01 ~ b_c * 0.01 * n_workers_in * (1 - 1/(1+t)) ~ b_c * 0.01 * (n_in - sum 1/(1+t))
    bnames = dict(zip(names, b)); g = D["h"].inc_group.values
    def coef(base):
        return np.array([bnames.get(f"{base}_{x}", bnames.get(base, 0.0)) for x in g])
    com = D["F"]["commute_log"]; nin = D["nw_in"][:, None]
    sum_inv = nin * np.exp(-com / np.maximum(nin, 1))          # approximation: equal times across workers
    dV_c = (coef("commute_log")[:, None] + bnames.get("commute_log_x_inc", 0) * np.log(np.maximum(D["h"].income.values, 5000) / 50000)[:, None]) * 0.01 * (nin - sum_inv)
    for j, r in enumerate(D["regs"]):
        sh0 = (w * P[:, j]).sum() / w.sum()
        for lab, dV in (("commute_time", dV_c[:, j]), ("IV_B_plus_0.1", coef("IV_B") * 0.1)):
            V = np.log(np.maximum(P, 1e-300)); V[:, j] += dV
            P1 = np.exp(V - V.max(1, keepdims=True)); P1 /= P1.sum(1, keepdims=True)
            sh1 = (w * P1[:, j]).sum() / w.sum()
            el.append(dict(region=r, variable=lab, share=sh0, elasticity=(sh1 / sh0 - 1) / (0.01 if lab == "commute_time" else 1.0)))
    # (c) monthly cost of every dwelling of region j +1 %: IV_A recomputed on a fixed market sample at cost and 1.01 x cost;
    #     IV_B shifts by (b_lncost + b_lncost_x_inc ln inc) ln 1.01 (zone mean cost)
    import s04_dwelling as DW
    pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet"); pr = pd.read_csv(f"{WORK}/geo_puma_region.csv")
    db = np.load(f"{WORK}/dwelling_beta.npy"); dspec = set(json.load(open(f"{WORK}/dwelling_final.json"))["spec"])
    zb = dict(zip(pd.read_csv(f"{WORK}/zone_names_{TAG}.csv").iloc[:, 0], np.load(f"{WORK}/zone_beta_{TAG}.npy")))
    lninc = np.log(np.maximum(D["h"].income.values, 5000) / 50000)
    dIVB = (zb.get("lncost", 0) + zb.get("lncost_x_inc", 0) * lninc) * np.log(1.01)
    rng = np.random.default_rng(7)
    for j, r in enumerate(D["regs"]):
        gp = pool[pool.puma7.isin(pr[pr.region == r].puma7)]
        gp = gp.iloc[rng.choice(len(gp), size=min(200, len(gp)), replace=False)]
        iv = []
        for f in (1.0, 1.01):
            vals = np.zeros(len(D["h"]))
            for k0 in range(0, len(D["h"]), 3000):
                hh = D["h"].iloc[k0:k0 + 3000]; n = len(hh)
                alt = {"cost": np.tile(gp.cost.values * f, (n, 1)), "bed": np.tile(gp.BDSP.values.astype(float), (n, 1)),
                       "dtype": np.tile(gp.dtype.values, (n, 1)), "new5": np.tile((gp.age_dd.values <= 5).astype(float), (n, 1))}
                Xd, _ = DW.build_X(hh, alt, dspec); Vd = Xd @ db; mx = Vd.max(1, keepdims=True)
                vals[k0:k0 + n] = np.log(np.exp(Vd - mx).mean(1)) + mx[:, 0]
            iv.append(vals)
        dV = coef("IV_A") * (iv[1] - iv[0]) + coef("IV_B") * dIVB
        V = np.log(np.maximum(P, 1e-300)); V[:, j] += dV
        P1 = np.exp(V - V.max(1, keepdims=True)); P1 /= P1.sum(1, keepdims=True)
        sh0 = (w * P[:, j]).sum() / w.sum(); sh1 = (w * P1[:, j]).sum() / w.sum()
        el.append(dict(region=r, variable="monthly_cost", share=sh0, elasticity=(sh1 / sh0 - 1) / 0.01))
        for grp in INC_GROUPS:
            s_ = g == grp
            a0 = (w[s_] * P[s_, j]).sum() / w[s_].sum(); a1 = (w[s_] * P1[s_, j]).sum() / w[s_].sum()
            el.append(dict(region=r, variable=f"monthly_cost_{grp}", share=a0, elasticity=(a1 / a0 - 1) / 0.01))
    pd.DataFrame(el).to_csv(f"{TAB}/region_elasticities_{TAG}.csv", index=False)
    e = pd.DataFrame(el); print(e.groupby("variable").apply(lambda x: np.average(x.elasticity, weights=x.share)))


if __name__ == "__main__":
    main()
