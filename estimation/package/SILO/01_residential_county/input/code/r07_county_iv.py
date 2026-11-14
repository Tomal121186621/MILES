#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/residential/r07_county_iv.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""County level with the inclusive values of the re-specified lower parts: zone x structure type (r08_zone_multimodal.py, chosen form)
and dwelling (r06_dwelling_income.py, final model; its terms from the 'spec' column of r06_fit.csv).  Replaces IV_B and IV_A in the county data of s06_region.py (estimation and
validation movers, same rows and other variables) and writes county_data_{est,val}.pkl for r05_region_sequence.py.
Check first: the current inclusive values are recomputed from the current coefficients and must match the stored ones.
    python3 r07_county_iv.py [est val oot]   ->  county_data_<tag>.pkl  (oot: movers 2019-2021 with the 2019-2021 dwelling pool)"""
import os, sys, pickle, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
RAWD = os.path.abspath(f"{HERE}/../data/raw"); SHD = os.path.abspath(f"{HERE}/../../../00_shared_data")   # PATH (package)
OW = os.environ.get("TERP_WORKSPACE", "") + "/2_silo/resloc/work"   # PATH (package): region data of s06_region.py, not copied (see README)
ARGS = sys.argv[1:]   # read before r01 resets sys.argv for s05_zone
import r01_income_similarity as R1   # noqa: E402  (s05_zone with the final inputs; own-group shares SH)
import r06_dwelling_income as R6   # noqa: E402
DW = R6.DW
from rc import WORK, MICRO, ZONE_IDS, INC_GROUPS   # noqa: E402
import s06_region as RG   # noqa: E402

V = os.environ.get("TERP_WORKSPACE", "") + ""
CT = ["SFD", "SFA", "MF", "MH"]


def cells():
    D = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["zone", "type", "monthlyCost"])
    D["ct"] = D.type.replace({"MF234": "MF", "MF5plus": "MF"})
    Dm = D.groupby(["zone", "ct"]).size().unstack(fill_value=0).reindex(index=ZONE_IDS, columns=CT, fill_value=0).values.astype(float)
    lncost = np.log(np.maximum(D.groupby("zone").monthlyCost.mean().reindex(ZONE_IDS).values, 100.0))
    zi, ti = np.nonzero(Dm > 0)
    return Dm, lncost, zi, ti


LU = pd.read_csv(f"{HERE}/../../../00_shared_data/resloc_work/zone_landuse_2016.csv")   # PATH (package);.set_index("zone").reindex(ZONE_IDS)   # 2026-11-10: land-use terms of the zone part


def iv_B_new(h, z, b, A):
    """ln sum over the county's cells of exp(V_B) of the re-specified zone part, without its commute term."""
    Dm, lncost, zi, ti = cells()
    regs = np.sort(z.region.unique()); rix = np.searchsorted(regs, z.region.values[zi])
    out = np.full((len(h), len(regs)), -np.inf)
    lninc = np.log(np.maximum(h.income.values, 5000) / 50000); a = h.age_max.values.astype(float)
    hh = {"child": (h.n_child.values > 0).astype(float), "nocar": (h.car.values == "nocar").astype(float),
          "a65": (a >= 65).astype(float), "aU35": (a < 35).astype(float), "a50": ((a >= 50) & (a < 65)).astype(float),
          "hhs": np.minimum(h.NP.values, 6) - 1.0, "lninc": lninc}
    g = np.array([INC_GROUPS.index(x) for x in h.inc_group.values])
    seg = (h.inc_group + "_" + h.car).values; lc = lncost[zi]
    for s in np.unique(seg):
        idx = np.where(seg == s)[0]; aw = A[(s, "work")][zi]; an = A[(s, "nonwork")][zi]
        base = b["lnD"] * np.log(Dm[zi, ti]) + b.get("accW", 0.0) * aw + b["accN"] * an + b["lncost"] * lc
        for k in ("lnddens", "lnjden", "lnretden", "mix", "park"): base = base + b.get(k, 0.0) * LU[k].values[zi]
        dz = LU.lnddens.values[zi]
        for k0 in range(0, len(idx), 1000):
            ii = idx[k0:k0 + 1000]; x = {k: v[ii, None] for k, v in hh.items()}
            Vb = (base[None, :] + an[None, :] * (b.get("accN_x_child", 0.0) * x["child"] + b["accN_x_age65"] * x["a65"] + b["accN_x_ageU35"] * x["aU35"]
                  + b["accN_x_age50_64"] * x["a50"] + b["accN_x_hhs"] * x["hhs"]) + b.get("accW_x_nocar", 0.0) * aw[None, :] * x["nocar"]
                  + lc[None, :] * (b["lncost_x_inc"] * x["lninc"] + b["lncost_x_hhs"] * x["hhs"]) + b["sim"] * R1.SH[zi][:, g[ii]].T
                  + dz[None, :] * (b.get("lnddens_x_nocar", 0.0) * x["nocar"] + b.get("lnddens_x_child", 0.0) * x["child"]))
            m = Vb.max(axis=1, keepdims=True); S = np.zeros((len(ii), len(regs)))
            np.add.at(S.T, rix, np.exp(Vb - m).T); out[ii] = np.log(S) + m
    return out


def main():
    z, R = RG.region_frame()
    zf = pd.read_csv(f"{RAWD}/r08_fit.csv"); zch = zf[zf.chosen.fillna(False).astype(bool)].model.iloc[0]
    acc = pd.read_csv(os.environ.get("ACC_MM", f"{SHD}/accessibility/accessibility_2016_new_multimodal.csv") if zch.startswith("multimodal") else os.environ.get("ACC_CAR", f"{V}/data/accessibility_2016.csv"))
    acc0 = pd.read_csv(f"{SHD}/accessibility/accessibility_2016.csv")
    A0 = {(s, p): g.set_index("zone").A.reindex(ZONE_IDS).values for (s, p), g in acc0.groupby(["segment", "purpose"])}
    A = {(s, p): g.set_index("zone").A.reindex(ZONE_IDS).values for (s, p), g in acc.groupby(["segment", "purpose"])}
    zc = pd.read_csv(f"{RAWD}/r08_coef.csv"); zb = zc[zc.model == zch].set_index("parameter").estimate.to_dict()
    print("zone part:", zch, flush=True)
    df = pd.read_csv(f"{RAWD}/r06_fit.csv"); fin = df[df.validation_LL.notna()].iloc[0]; best = fin.model
    dc = pd.read_csv(f"{RAWD}/r06_coef.csv"); dc = dc[dc.model == best]
    dspec = set(fin.spec.split(";")) if "spec" in fin and isinstance(fin.spec, str) else {"type_inter", "age_bands", "income_slope"}; DW.build_X = R6.build_X
    print("dwelling part:", best, sorted(dspec), flush=True)
    pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    # check: current IV_B from the current zone coefficients reproduces the stored values
    De = pickle.load(open(f"{OW}/region_data_est_final.pkl", "rb"))
    zb0 = np.load(f"{OW}/zone_beta_final.npy"); zn0 = pd.read_csv(f"{OW}/zone_names_final.csv").iloc[:, 0].tolist()
    chk = RG.iv_B(De["h"].iloc[:500], z, zb0, zn0, A0)
    print("check IV_B, max abs difference", float(np.nanmax(np.abs(np.where(np.isfinite(chk), chk - De["F"]["IV_B"][:500], 0)))), flush=True)
    RG.RNG = np.random.default_rng(44)
    tags = ARGS or ["est", "val"]
    for tag in tags:
        if tag == "oot": pool = pd.read_parquet(f"{OW}/pums_pool_oot.parquet")
        D = De if tag == "est" else pickle.load(open(f"{OW}/region_data_{tag}_final.pkl", "rb"))
        h = D["h"]; regs = D["regs"]
        ivb = iv_B_new(h, z, zb, A)
        # the dwelling part's design must list the names in the order of the coefficients
        X0, names = DW.build_X(h.iloc[:2], {"cost": np.ones((2, 1)) * 1000, "bed": np.ones((2, 1)), "dtype": np.array([["SFD"], ["MF5plus"]]),
                                            "new5": np.zeros((2, 1))}, dspec)
        beta = dc.set_index("parameter").estimate.reindex(names).values; assert not np.isnan(beta).any()
        iva = RG.iv_A(h, pool, regs, beta, names, dspec)
        assert np.isfinite(ivb[D["C"]]).all(), "chosen county without cells"
        for k, new in (("IV_B", ivb), ("IV_A", iva)):
            old = D["F"][k]; ok = np.isfinite(old) & np.isfinite(new)
            print(tag, k, "corr old/new %.3f" % np.corrcoef(old[ok], new[ok])[0, 1], "mean old %.2f new %.2f" % (old[ok].mean(), new[ok].mean()), flush=True)
        D["F"]["IV_B"], D["F"]["IV_A"] = ivb, iva
        pickle.dump(D, open(f"{RAWD}/county_data_{tag}.pkl", "wb"))


if __name__ == "__main__":
    main()
