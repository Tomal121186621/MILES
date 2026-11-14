#!/usr/bin/env python3
"""Engine input files of the re-specified car-ownership model (car.ownership.spec = respec), from the final model of the article
table (estimation/development/car_ownership/t_final_table.py: fit of the s07 final specification on the estimation sample).  New files only:
  2_silo/input/car_ownership_estimated_coefficients.csv   alternative,variable,value  (1, 2, 3 = 3+ cars; alternative 0 holds
                                                       ln_density_centre, the estimation-sample mean of ln density used in inc_x_dens)
  2_silo/input/car_ownership_puma_attributes.csv           puma,zone,hu,density_2016   (PUMA-zone housing units of resloc/work/geo_puma_zone.csv
                                                       for all states, density = units per km2 of the PUMA as in s01_data.puma_location)
  2_silo/input/car_ownership_county_constants.csv  region,asc1,asc2,asc3 = 0 (no calibration yet)
    python3 landuse/coefficients/write_car_ownership.py [--coefficients-only]"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
V = f"{WORKSPACE}"; ROOT = PROJECT_ROOT
C = f"{ESTIMATION_RESULTS}/car_ownership"; INP = f"{V}/2_silo/input"
sys.path.insert(0, f"{TERP_HOME}/estimation/development/car_ownership")   # estimation code; C holds its results (data)
from mnl import fit   # noqa: E402
from s06_age import oldest_age, prep   # 2026-11-09: age of the oldest member (was the householder, s06_age.head_age)   # noqa: E402
from s04_form import pieces   # noqa: E402
import s01_data as S1   # noqa: E402


def new(p):
    assert not os.path.exists(p), f"exists, not overwritten: {p}"; return p


def puma_density_all():
    """s01_data.puma_location density for the PUMAs of every state"""
    pz = pd.read_csv(f"{V}/2_silo/resloc/work/geo_puma_zone.csv")
    zs = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv", usecols=["ZoneId", "AREA_SQMI"])
    pz = pz.merge(zs, left_on="zone", right_on="ZoneId"); pz["km2"] = pz.AREA_SQMI * 2.58999
    zshare = pz.hu / pz.groupby("zone").hu.transform("sum").replace(0, np.nan)
    dens = pz.hu.groupby(pz.puma7).sum() / (pz.km2 * zshare.fillna(0)).groupby(pz.puma7).sum()
    return pz, dens


def main():
    d = pd.read_parquet(f"{C}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    md = d.ln_density.mean(); d = prep(d, md, oldest_age()); pieces(d)
    V_ = pd.read_csv(f"{C}/s07_fit.csv").query("step == 'final'").spec.iloc[0].split()
    r = fit(d, V_)
    i1 = pd.read_csv(f"{C}/s07_coef.csv").query("step == 'final'").set_index("param").coef
    print("refit vs s07 step final, max |diff|", float(np.abs(pd.Series(r["b"], index=r["names"]) - i1.reindex(r["names"])).max()), "LL", r["LL"], "K", r["K"])
    rows = [dict(alternative=0, variable="ln_density_centre", value=md)]
    for n, b in zip(r["names"], r["b"]):
        v, a = n.split("|"); rows.append(dict(alternative={"1": 1, "2": 2, "3+": 3}[a], variable="asc" if v == "constant" else v, value=b))
    cf = f"{INP}/car_ownership_estimated_coefficients.csv"
    pd.DataFrame(rows).to_csv(cf if "--coefficients-only" in sys.argv else new(cf), index=False)   # --coefficients-only: rewrite (backup *_pre1109x first)
    if "--coefficients-only" in sys.argv: return
    pz, dens = puma_density_all()
    md_loc = S1.puma_location()
    print("density vs s01_data.puma_location (MD), max rel diff", float((dens.reindex(md_loc.index) / md_loc.dens - 1).abs().max()))
    out = pz[["puma7", "zone", "hu"]].rename(columns={"puma7": "puma"}); out["density_2016"] = out.puma.map(dens)
    out.to_csv(new(f"{INP}/car_ownership_puma_attributes.csv"), index=False)
    reg = pd.read_csv(f"{INP}/car_ownership_region_constants.csv")[["region"]].assign(asc1=0.0, asc2=0.0, asc3=0.0)
    reg.to_csv(new(f"{INP}/car_ownership_county_constants.csv"), index=False)
    print("written; ln density centre", md, "PUMAs", out.puma.nunique(), "zones", out.zone.nunique())


if __name__ == "__main__":
    main()
