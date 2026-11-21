#!/usr/bin/env python3
"""Market size candidates of the PUMA level of the two-level residential model (2026-11-18).  One row per PUMA of the zone system:
  hu_all     PUMS 2014-2018 weighted housing units (housing-unit records TYPE 1, occupied + vacant; WGTP sum = average year)
  hu_occ     ... occupied (NP > 0);  hu_vac  ... vacant (NP 0)
  movers     PUMS weighted dwellings occupied by households that moved in within 12 months (pums_pool_est WGTP sum) = current M
  turnover   movers / hu_all (fixed PUMS turnover rate of the PUMA)
  silo_dw    SILO 2016 dwellings (dd_2016, occupied + vacant) of the PUMA: zones by f_member as r18_export_silo.py writes it
             (hu share of the zone; crosswalk-zero zones and zones without a tract point -> their zoneSystem PUMA_10)
  silo_vac   SILO 2016 vacant dwellings (hhID <= 0) of the PUMA, same membership
Writes r19_puma_market.csv.  No validation data and no SILO simulation output is used (silo_* = the 2016 base-year synthetic stock)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; V = WORKSPACE   # HERE: results of this step (data); CODE: this folder
sys.path.insert(0, f"{MILES_HOME}/landuse/lib/residential")
from rc import WORK, INP, MICRO, ZONE_IDS, ZIDX, STATES, pums_read   # noqa: E402


def membership():
    zs = pd.read_csv(f"{INP}/zoneSystem.csv").set_index("ZoneId")
    pz = pd.read_csv(f"{WORK}/geo_puma_zone.csv"); pz = pz[pz.zone.isin(ZIDX.index)].copy()
    tot = pz.groupby("zone").hu.transform("sum"); pz["f"] = np.where(tot > 0, pz.hu / tot.where(tot > 0, 1), 0.0)
    for zz in pz[tot == 0].zone.unique():
        m = pz.zone == zz; p10 = zs.PUMA_10[zz]
        pz.loc[m, "f"] = np.where(pz.loc[m, "puma7"] == p10, 1.0, 0.0) if (pz.loc[m, "puma7"] == p10).any() else 1.0 / m.sum()
    miss = [int(q) for q in ZONE_IDS if q not in set(pz.zone)]
    return pd.concat([pz[["zone", "puma7", "f"]], pd.DataFrame({"zone": miss, "puma7": zs.PUMA_10.reindex(miss).values, "f": 1.0})])


def main():
    H = []
    for s in STATES:
        h = pums_read(2018, "h", s, ["ST", "STATE", "PUMA", "WGTP", "NP", "TYPE", "TYPEHUGQ"])
        if "ST" not in h.columns: h = h.rename(columns={"STATE": "ST"})
        t = "TYPE" if "TYPE" in h.columns else "TYPEHUGQ"; h = h[h[t] == 1]; H.append(h); print(s, len(h), flush=True)
    H = pd.concat(H); H["puma7"] = H.ST * 100000 + H.PUMA
    mem = membership(); pumas = np.sort(mem.puma7.unique())
    out = pd.DataFrame(index=pd.Index(pumas, name="puma7"))
    out["hu_all"] = H.groupby("puma7").WGTP.sum().reindex(pumas)
    out["hu_occ"] = H[H.NP > 0].groupby("puma7").WGTP.sum().reindex(pumas)
    out["hu_vac"] = H[H.NP == 0].groupby("puma7").WGTP.sum().reindex(pumas).fillna(0)
    pool = pd.read_parquet(f"{WORK}/pums_pool_est.parquet")
    out["movers"] = pool.groupby("puma7").WGTP.sum().reindex(pumas).fillna(0)
    out["n_pool_records"] = pool.groupby("puma7").size().reindex(pumas).fillna(0).astype(int)
    out["turnover"] = out.movers / out.hu_all
    dd = pd.read_csv(f"{MICRO}/dd_2016.csv", usecols=["zone", "hhID"])
    zc = dd.zone.value_counts(); zv = dd[dd.hhID <= 0].zone.value_counts()
    mem["dw"] = mem.f * mem.zone.map(zc).fillna(0); mem["vac"] = mem.f * mem.zone.map(zv).fillna(0)
    out["silo_dw"] = mem.groupby("puma7").dw.sum().reindex(pumas); out["silo_vac"] = mem.groupby("puma7").vac.sum().reindex(pumas)
    assert out[["hu_all", "movers", "silo_dw"]].notna().all().all() and (out.hu_all > 0).all()
    out.to_csv(f"{HERE}/r19_puma_market.csv")
    print(out.describe().round(3).to_string())
    r = np.log(out.silo_dw / out.hu_all)
    print(f"ln(SILO 2016 dwellings / PUMS housing units): mean {r.mean():.3f} sd {r.std():.3f} min {r.min():.3f} max {r.max():.3f}")
    print(f"corr ln hu_all / ln movers {np.corrcoef(np.log(out.hu_all), np.log(out.movers))[0, 1]:.3f}; turnover min {out.turnover.min():.3f} max {out.turnover.max():.3f}")
    print(f"totals: PUMS HU {out.hu_all.sum():,.0f}, movers {out.movers.sum():,.0f} ({out.movers.sum() / out.hu_all.sum():.3f}), SILO dwellings {out.silo_dw.sum():,.0f}, SILO vacant {out.silo_vac.sum():,.0f}")


if __name__ == "__main__":
    main()
