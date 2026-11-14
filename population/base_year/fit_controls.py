#!/usr/bin/env python3
"""Stage-1 correction of the synthetic population (all six states; placement fix Maryland only):
 1. Person controls. The generated households match the ACS household weights per PUMA (0.994) but carry 6.4 % too few persons,
    because household frequencies followed the household weights, which under-represent large households' people (mean size 2.52
    vs 2.67). Per PUMA, households are re-drawn (with replacement) from the generated pool with weights found by iterative
    proportional fitting so that (a) the number of households equals the ACS household count, (b) persons by age band (0-17, 18-34, 35-64, 65+) match the
    ACS person weights of persons living in households (group quarters excluded, stated) and (c) households by size (1-5+) match the
    ACS household weights. (b) and (c) are mutually inconsistent in the ACS by about 6 % (the person weights are controlled to the Census population,
    the household weights to housing units); persons get full weight, size shares a mild one (SIZE_WEIGHT), the deviation is reported.
 2. Placement. Households are placed in zones inside their PUMA in proportion to the 2016 occupied housing units (interpolated between the 2010 and 2020 Censuses) of each
    zone (zone_weights_2016.csv, 2010-2020 interpolated to 2016); non-Maryland PUMAs keep the original placement.
Inputs: VAE_HOME/outputs/04_generated/{hh,pp}.parquet, PUMS 2014-2018 (centred on 2016).  Outputs: 1_vae/output/{hh,pp}.parquet
with new ids, and 1_vae/output/rebalance_report.csv (per PUMA: households, persons, mean size before/after vs ACS)."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, zipfile, os
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; OUT = f"{V}/1_vae/output"; os.makedirs(OUT, exist_ok=True)
BANDS = [(0, 17), (18, 34), (35, 64), (65, 120)]; rng = np.random.default_rng(2026)
import sys; SIZE_WEIGHT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15   # exponent of the household-size constraints (persons by age use 1.0)
hh = pd.read_parquet(f"{VAE_HOME}/outputs/04_generated/hh.parquet"); pp = pd.read_parquet(f"{VAE_HOME}/outputs/04_generated/pp.parquet")
pp["band"] = np.digitize(pp.age, [18, 35, 65]); pp["st"] = pp.puma_key.str[:2]
# ---- ACS targets per PUMA, all six states (person weights of persons in households; household weights by size)
ST = {"24": "md", "11": "dc", "10": "de", "42": "pa", "51": "va", "54": "wv"}
tp, th, ts = [], [], []
for fips, ab in ST.items():
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_p{ab}.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]; P = pd.read_csv(zf.open(n), usecols=["PUMA", "PWGTP", "RELP", "AGEP"], low_memory=False)
    P = P[~P.RELP.isin([16, 17])]; P["band"] = np.digitize(P.AGEP, [18, 35, 65]); P["puma_key"] = fips + "_" + P.PUMA.astype(int).astype(str).str.zfill(5)
    tp.append(P.groupby(["puma_key", "band"]).PWGTP.sum().unstack(fill_value=0))
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_h{ab}.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]; H = pd.read_csv(zf.open(n), usecols=["PUMA", "WGTP", "NP", "TYPE"], low_memory=False)
    Hh = H[(H.TYPE == 1) & (H.NP > 0)].copy(); Hh["puma_key"] = fips + "_" + Hh.PUMA.astype(int).astype(str).str.zfill(5)
    th.append(Hh.groupby("puma_key").WGTP.sum()); ts.append(Hh.assign(s=Hh.NP.clip(upper=5)).groupby(["puma_key", "s"]).WGTP.sum().unstack(fill_value=0).reindex(columns=range(1, 6), fill_value=0))
tgt_pp = pd.concat(tp); tgt_hh = pd.concat(th); tgt_size = pd.concat(ts)
# ---- per household: persons by band
comp = pp.groupby(["hh_id", "band"]).size().unstack(fill_value=0).reindex(columns=range(4), fill_value=0)
hh = hh.set_index("hh_id"); hh["puma"] = hh.puma_key.str[-5:].astype(int); hh["st"] = hh.puma_key.str[:2]
report, keep_ids, new_rows = [], [], []
for pk, g in hh.groupby("puma_key"):
    if pk not in tgt_pp.index or pk not in tgt_hh.index:      # PUMA without ACS targets (partly covered): kept as generated
        keep_ids.extend([(i, 1) for i in g.index]); continue
    puma = pk; C = comp.reindex(g.index, fill_value=0).values.astype(float); n_hh = len(g); T = tgt_pp.loc[puma].values.astype(float) * (len(g) / tgt_hh[puma])   # partly covered PUMAs: targets scaled to the generated share
    # size-band constraints (1,2,3,4,5+ persons) from the household weights, with equal standing to the person constraints:
    # the ACS household and person weights are mutually inconsistent by ~6 %, so the fit settles on a compromise (damped IPF)
    S = np.stack([(g.hhSize.clip(upper=5).values == s).astype(float) for s in range(1, 6)], axis=1); TS = tgt_size.loc[puma].values.astype(float)
    w = np.ones(len(g))
    for it in range(80):
        for k in range(4):
            cur = (w * C[:, k]).sum()
            if cur > 0: w *= np.where(C[:, k] > 0, (T[k] / cur) ** 1.0, 1.0)      # persons by age: full weight (hard control)
        for s in range(5):
            cur = (w * S[:, s]).sum()
            if cur > 0: w *= np.where(S[:, s] > 0, (TS[s] / cur) ** SIZE_WEIGHT, 1.0)   # size shares: mild regularization
        w *= n_hh / w.sum()
    w = np.clip(w, 0.2, 5.0); w *= n_hh / w.sum()
    draw = rng.choice(len(g), size=n_hh, replace=True, p=w / w.sum())
    ids = g.index.values[draw]; keep_ids.extend([(i, 0) for i in ids])
    before = dict(hh=len(g), pp=C.sum(), size=C.sum() / len(g)); after_pp = C[draw].sum()
    report.append(dict(puma_key=pk, acs_hh=n_hh, acs_pp=T.sum(), hh_before=len(g), pp_before=int(before["pp"]), hh_after=n_hh, pp_after=int(after_pp),
                       size_before=round(before["size"], 3), size_after=round(after_pp / n_hh, 3), size_acs=round(T.sum() / n_hh, 3),
                       **{f"band{k}_after/acs": round(C[draw][:, k].sum() / T[k], 3) for k in range(4)}, **{f"size{s+1}_after/acs": round(S[draw][:, s].sum() / TS[s], 3) for s in range(5)}))
# ---- rebuild hh and pp with new ids (duplicates get fresh ids)
sel = pd.DataFrame(keep_ids, columns=["old_hh_id", "untouched"]); sel["hh_id"] = np.arange(1, len(sel) + 1)
hh2 = hh.loc[sel.old_hh_id].reset_index(drop=True); hh2["hh_id"] = sel.hh_id.values
pp2 = pp.merge(sel[["old_hh_id", "hh_id"]].rename(columns={"hh_id": "new_hh_id"}), left_on="hh_id", right_on="old_hh_id", how="inner").drop(columns=["hh_id", "old_hh_id"]).rename(columns={"new_hh_id": "hh_id"})
pp2 = pp2.sort_values(["hh_id", "sporder"]); pp2["pp_id"] = np.arange(1, len(pp2) + 1)
# ---- placement in zones (Maryland): 2020 occupied units within the PUMA
zw = pd.read_csv(f"{OUT}/zone_weights_2016.csv"); zs = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv")[["ZoneId", "PUMA_10"]].rename(columns={"ZoneId": "zone_id"})
zw = zw.merge(zs, on="zone_id"); zw["puma_key"] = zw.STFIPS.astype(int).astype(str).str.zfill(2) + "_" + (zw.PUMA_10 % 100000).astype(int).astype(str).str.zfill(5)
md = hh2.st == "24"
for pk, g in hh2[md].groupby("puma_key"):
    cand = zw[(zw.puma_key == pk) & (zw.occupied_units_2016.fillna(0) > 0)]
    if cand.empty: continue
    p = cand.occupied_units_2016.values / cand.occupied_units_2016.sum()
    z = rng.choice(cand.zone_id.values, size=len(g), p=p); hh2.loc[g.index, "zone_id"] = z; hh2.loc[g.index, "county_fips"] = cand.set_index("zone_id").county_fips.reindex(z).values
hh2 = hh2.drop(columns=["puma", "st"]); pp2 = pp2.drop(columns=["band", "st"])
hh2.to_parquet(f"{OUT}/hh.parquet", index=False); pp2.to_parquet(f"{OUT}/pp.parquet", index=False)
R = pd.DataFrame(report); R.to_csv(f"{OUT}/rebalance_report.csv", index=False)
print(f"PUMAs rebalanced (six states): {len(R)}; persons/ACS before {R.pp_before.sum() / R.acs_pp.sum():.3f} -> after {R.pp_after.sum() / R.acs_pp.sum():.3f}; mean size before {R.pp_before.sum() / R.hh_before.sum():.3f} after {R.pp_after.sum() / R.hh_after.sum():.3f} ACS {R.acs_pp.sum() / R.acs_hh.sum():.3f}")
print("age bands after/ACS (mean over PUMAs):", {k: round(R[f'band{k}_after/acs'].mean(), 3) for k in range(4)}); print("size bands after/ACS:", {s: round(R[f'size{s}_after/acs'].mean(), 3) for s in range(1, 6)})
print(f"output households {len(hh2):,} persons {len(pp2):,}")
