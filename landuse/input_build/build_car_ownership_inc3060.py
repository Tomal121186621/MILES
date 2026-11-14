#!/usr/bin/env python3
"""Household car-ownership model (0/1/2/3+ vehicles) estimated on ACS PUMS Maryland households, for CarOwnershipModelMd.
Variables available in PUMS: household size (NP), workers (WIF), income class (HINCP, 12 classes as in the engine).
Transit accessibility and job density are not in PUMS: their coefficients are set to 0 here and the per-region constants
(calibrated later against vehicles by county) carry the spatial variation.  Weighted multinomial logit (WGTP), base = 0 cars.
Outputs: 2_silo/input/car_ownership_coefficients.csv (alternative,variable,value); region constants start at 0 and are
calibrated in the calibration loop; data/silo_target_vehicles_by_region.csv = observed shares by county (PUMA -> county map).

Baltimore 2026 (logsum accessibility, accessibility.model = logsum): with  --logsum <accessibility csv>  the model is re-estimated
with the variable accLogsumGain = A(<income group>_carge, nonwork) - A(<income group>_nocar, nonwork), the non-work logsum
accessibility gained by owning cars, at the household's PUMA (mean over the PUMA's zones weighted by 2010 housing units;
the engine uses the home zone), written to  --out  (default input/car_ownership_coefficients_logsum.csv; the default
coefficient file is not touched).  Income group = SILO household-type bounds 20/40/60k (2016 $)."""
import zipfile, pandas as pd, numpy as np, os, sys
import statsmodels.api as sm
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; V = f"{ROOT}/Validation_2026"
args = [a for a in sys.argv[1:]]
LOGSUM = args[args.index("--logsum") + 1] if "--logsum" in args else None
OUT = args[args.index("--out") + 1] if "--out" in args else (f"{V}/2_silo/input/car_ownership_coefficients_logsum.csv" if LOGSUM else f"{V}/2_silo/input/car_ownership_coefficients.csv")
pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or not args[i - 1].startswith("--"))]
VINTAGE = pos[0] if pos else "2018"
BOUNDS = [10000, 15000, 30000, 40000, 50000, 60000, 75000, 100000, 125000, 150000, 200000]
with zipfile.ZipFile(f"{ROOT}/inputs/pums_{VINTAGE}_5yr/csv_hmd.zip") as zf:
    n = [x for x in zf.namelist() if x.endswith(".csv")][0]
    H = pd.read_csv(zf.open(n), usecols=["PUMA", "NP", "WIF", "VEH", "HINCP", "WGTP", "TYPE" if VINTAGE < "2020" else "TYPEHUGQ", "ADJINC"], low_memory=False)
tcol = "TYPE" if "TYPE" in H.columns else "TYPEHUGQ"
H = H[(H[tcol] == 1) & (H.NP > 0) & H.VEH.notna() & (H.WGTP > 0)].copy()
H["inc"] = H.HINCP.fillna(0) * H.ADJINC / 1e6 if H.ADJINC.max() > 100 else H.HINCP.fillna(0) * H.ADJINC
H["inc_cls"] = np.searchsorted(BOUNDS, H.inc, side="right") + 1
H["workers"] = H.WIF.fillna(0).clip(upper=3); H["size"] = H.NP.clip(upper=8); H["veh"] = H.VEH.clip(upper=3).astype(int)
X = pd.DataFrame({"const": 1.0, "hhSize": H["size"], "workers": H.workers})
for k in range(2, 13): X[f"income_{k}"] = (H.inc_cls == k).astype(float)       # class 1 (< 10k) is the reference
if LOGSUM:
    acc = pd.read_csv(LOGSUM); acc = acc[acc.purpose == "nonwork"]
    pz = pd.read_csv(f"{V}/2_silo/resloc/work/geo_puma_zone.csv"); pz = pz[pz.puma7 // 100000 == 24]
    grp = np.array(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"])[np.searchsorted([20000, 40000, 60000], H.inc * 240.007 / 251.107, side="right")]
    gain = {}
    for g in ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]:
        a = acc[acc.segment == f"{g}_carge"].set_index("zone").A - acc[acc.segment == f"{g}_nocar"].set_index("zone").A
        t = pz.assign(gain=pz.zone.map(a)).dropna()
        gain[g] = t.groupby("puma7").apply(lambda d: np.average(d.gain, weights=d.hu))
    X["accLogsumGain"] = [gain[g].get(24 * 100000 + p, np.nan) for g, p in zip(grp, H.PUMA)]
    ok = X.accLogsumGain.notna().values
    X, H = X[ok], H[ok]
# weighted estimation by frequency weights (rounded to integers / 10 to keep the sample manageable)
w = np.maximum(1, np.round(H.WGTP / 10)).astype(int)
Xr, yr = X.loc[X.index.repeat(w)], H.veh.loc[H.index.repeat(w)]
res = sm.MNLogit(yr.values, Xr.values).fit(method="newton", maxiter=100, disp=False)
names = X.columns.tolist(); rows = []
for a in range(1, 4):
    for i, nm in enumerate(names):
        rows.append(dict(alternative=a, variable="asc" if nm == "const" else nm, value=round(float(np.asarray(res.params)[i][a - 1]), 5)))
    rows.append(dict(alternative=a, variable="transitAcc", value=0.0))
os.makedirs(f"{V}/2_silo/input", exist_ok=True)
pd.DataFrame(rows).to_csv(OUT, index=False)
if LOGSUM:
    # robust (sandwich-free here: frequency-weighted replication) standard errors of the accessibility coefficient
    se = np.asarray(res.bse); k = names.index("accLogsumGain")
    print("accLogsumGain by alternative (1, 2, 3+ cars): " + ", ".join(f"{np.asarray(res.params)[k][a]:.4f} (s.e. {se[k][a] * np.sqrt(10):.4f})" for a in range(3))
          + "   [s.e. scaled by sqrt(10) for the /10 weight replication]")
print(f"PUMS {VINTAGE} MD households {len(H):,} (weighted {H.WGTP.sum():,.0f}); vehicles shares: " + ", ".join(f"{k} cars {v:.3f}" for k, v in (H.groupby('veh').WGTP.sum() / H.WGTP.sum()).items()))
print("fitted shares:", np.round(res.predict(X.values).mean(axis=0), 3), " pseudo R2", round(res.prsquared, 3))
print(pd.DataFrame(rows).pivot(index="variable", columns="alternative", values="value").loc[["asc", "hhSize", "workers", "income_6", "income_12"] + (["accLogsumGain"] if LOGSUM else [])].to_string())
if LOGSUM: sys.exit(0)
obs = H.groupby(["PUMA", "veh"]).WGTP.sum().unstack(fill_value=0); obs = obs.div(obs.sum(axis=1), axis=0).round(4); obs.to_csv(f"{V}/data/silo_target_vehicles_by_puma_{VINTAGE}.csv")
