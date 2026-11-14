#!/usr/bin/env python3
"""Car ownership, step by step. Step 1-2 data: one row per ACS PUMS 2014-2018 Maryland household with every candidate variable
that is both in PUMS and producible by the chain.  Output: hh.parquet (small).   Usage: python3 estimation/development/car_ownership/s01_data.py"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, zipfile, hashlib
import numpy as np, pandas as pd

ROOT = f"{PROJECT_ROOT}"
V = f"{WORKSPACE}"
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
INC_BOUNDS = [40000, 75000, 125000]
GROUPS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]


def puma_location():
    """PUMA-level location variables: non-work accessibility with and without a car by income group, dwelling density."""
    pz = pd.read_csv(f"{V}/2_silo/resloc/work/geo_puma_zone.csv"); pz = pz[pz.puma7 // 100000 == 24]
    zs = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv", usecols=["ZoneId", "AREA_SQMI", "COUNTYFIPS"])
    pz = pz.merge(zs, left_on="zone", right_on="ZoneId")
    pz["km2"] = pz.AREA_SQMI * 2.58999
    acc = pd.read_csv(f"{V}/data/accessibility_2016.csv"); acc = acc[acc.purpose == "nonwork"]
    out = pd.DataFrame(index=sorted(pz.puma7.unique()))
    for g in GROUPS:
        for c, seg in [("car", f"{g}_carge"), ("nocar", f"{g}_nocar")]:
            a = pz.zone.map(acc[acc.segment == seg].set_index("zone").A)
            out[f"acc_{c}_{g}"] = (a * pz.hu).groupby(pz.puma7).sum() / pz.hu.where(a.notna(), 0).groupby(pz.puma7).sum()
    # zones split between PUMAs: area shared in proportion to the zone's housing units
    zshare = pz.hu / pz.groupby("zone").hu.transform("sum").replace(0, np.nan)
    out["dens"] = pz.hu.groupby(pz.puma7).sum() / (pz.km2 * zshare.fillna(0)).groupby(pz.puma7).sum()
    out["balt_city"] = (pz.groupby("puma7").COUNTYFIPS.agg(lambda s: s.mode()[0]) == 24510).astype(float)
    return out


def main():
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_hmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        H = pd.read_csv(zf.open(n), usecols=["SERIALNO", "PUMA", "NP", "VEH", "HINCP", "WGTP", "TYPE", "ADJINC", "BLD", "BDSP"],
                        low_memory=False, dtype={"SERIALNO": str})
    H = H[(H.TYPE == 1) & (H.NP > 0) & H.VEH.notna() & (H.WGTP > 0)].copy()
    H["inc"] = H.HINCP.fillna(0) * H.ADJINC / 1e6 * 240.007 / 251.107          # 2016 $
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_pmd.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]
        P = pd.read_csv(zf.open(n), usecols=["SERIALNO", "ESR", "AGEP"], low_memory=False, dtype={"SERIALNO": str})
    g = P.groupby("SERIALNO")
    m = lambda s: H.SERIALNO.map(s).fillna(0).values
    d = pd.DataFrame({"serial": H.SERIALNO.values, "puma7": 24 * 100000 + H.PUMA.values, "w": H.WGTP.values})
    d["cars"] = H.VEH.clip(upper=3).astype(int).values
    d["hhsize"] = H.NP.clip(upper=8).values
    d["workers"] = m(P[P.ESR.isin([1, 2, 4, 5])].groupby("SERIALNO").size())
    d["adults16"] = m(P[P.AGEP >= 16].groupby("SERIALNO").size())
    d["nonworking_adults"] = d.adults16 - d.workers.clip(upper=d.adults16)
    d["children"] = m(P[P.AGEP < 16].groupby("SERIALNO").size())
    d["any_65plus"] = m(g.AGEP.max() >= 65).astype(float)
    d["single_person"] = (d.hhsize == 1).astype(float)
    d["income_k"] = H.inc.values / 1000
    d["ln_income"] = np.log(np.maximum(H.inc.values, 5000) / 50000)
    bld = H.BLD.values
    d["sfd"] = (bld == 2).astype(float); d["sfa"] = (bld == 3).astype(float)
    d["multifamily"] = np.isin(bld, [4, 5, 6, 7, 8, 9]).astype(float)
    d["bedrooms"] = H.BDSP.fillna(0).clip(upper=5).values
    loc = puma_location()
    grp = np.array(GROUPS)[np.searchsorted(INC_BOUNDS, H.inc.values, side="right")]
    d["acc_car"] = [loc.at[p, f"acc_car_{q}"] for p, q in zip(d.puma7, grp)]
    d["acc_nocar"] = [loc.at[p, f"acc_nocar_{q}"] for p, q in zip(d.puma7, grp)]
    d["acc_gain"] = d.acc_car - d.acc_nocar
    d["ln_density"] = np.log(d.puma7.map(loc.dens).values)
    d["balt_city"] = d.puma7.map(loc.balt_city).values
    d = d.dropna().reset_index(drop=True)
    d["half"] = np.where(d.serial.map(lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 5) == 0, "holdout", "estimation")
    d.to_parquet(f"{HERE}/hh.parquet", index=False)
    print(len(d), d.half.value_counts().to_dict())
    print(d.drop(columns=["serial", "puma7", "half"]).describe().T[["mean", "std", "min", "max"]].round(3).to_string())


if __name__ == "__main__":
    main()
