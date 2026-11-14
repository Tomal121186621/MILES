#!/usr/bin/env python3
# Copy of side_experiments/respec_2026-11/step_by_step/residential/r11_zone_landuse.py
# (manual-estimation package; only file paths changed, marked "# PATH (package)")
"""Zone land-use attributes for the zone x structure-type part (2026-11-10, author approval), all for the 1,588 zones:
  lnddens   ln(dwellings / acre)                      SILO 2016 dwellings (2_silo/input/microData/dd_2016.csv), zoneSystem ACRES
  lnjden    ln(1 + jobs / acre)                       SILO 2016 jobs (jj_2016_v4.csv: same zones and types as every base version)
  lnretden  ln(1 + retail jobs / km2)
  mix       land-use entropy of retail, office, other (industrial + other) jobs and dwellings, -sum p ln p / ln 4 (0 = one use)
  park      paid-parking share of car-driver tours to the zone's area class (3_abit/coef_respec/parking_paid_share.csv, the
            mode-choice 'park' variable; classes of 3_abit/mode_choice/prep_tours.park_area: Baltimore CBD, rest of Baltimore City,
            DC CBD, rest of DC, other CBD zones, elsewhere), fixed
In the engine lnddens, lnjden, lnretden and mix are recomputed every year from SILO's current dwellings and jobs; park is fixed.
    python3 r11_zone_landuse.py   ->  zone_landuse_2016.csv"""
import os, sys
import numpy as np, pandas as pd
V = os.environ.get("MILES_WORKSPACE", "") + ""; HERE = os.path.dirname(os.path.abspath(__file__))
MD = f"{V}/2_silo/input/microData"


def landuse(dd_zone, jj_zone_type, zs, park):
    """dd_zone: dwellings by zone (Series); jj_zone_type: DataFrame zone x RET/OFF/IND/OTH; zs: zone, ACRES"""
    z = zs.set_index("zone"); D = dd_zone.reindex(z.index).fillna(0); J = jj_zone_type.reindex(z.index).fillna(0)
    acres = z.ACRES.values; km2 = acres * 0.00404686
    n = np.column_stack([J.RET.values, J.OFF.values, J.IND.values + J.OTH.values, D.values]).astype(float); p = n / np.maximum(n.sum(1, keepdims=True), 1e-12)
    mix = -(np.where(p > 0, p * np.log(np.where(p > 0, p, 1)), 0)).sum(1) / np.log(4)
    return pd.DataFrame({"zone": z.index.values, "lnddens": np.log(np.maximum(D.values, 1) / acres), "lnjden": np.log1p(J.sum(1).values / acres),
                         "lnretden": np.log1p(J.RET.values / km2), "mix": mix, "park": park.reindex(z.index).values})


def park_by_zone():
    sys.path.insert(0, f"{V}/3_abit/mode_choice"); import mc_common as M   # noqa: E402  (read only)
    z = M.C.zones(); sh = pd.read_csv(f"{V}/3_abit/coef_respec/parking_paid_share.csv").set_index("park_area").share
    cls = np.select([(z.bc == 1) & (z.cbd == 1), z.bc == 1, (z.dcz == 1) & (z.cbd == 1), z.dcz == 1, z.cbd == 1], [0, 1, 2, 3, 4], 5)
    return pd.Series(sh.reindex(cls).values, index=z.id.values)


def main():
    zs = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv")[["ZoneId", "ACRES"]].rename(columns={"ZoneId": "zone"})
    dd = pd.read_csv(f"{MD}/dd_2016.csv", usecols=["zone"]).zone.value_counts()
    jj = pd.read_csv(f"{MD}/jj_2016_v4.csv", usecols=["zone", "type"]); jj["type"] = jj.type.astype(str).str.replace('"', "")
    J = jj.groupby(["zone", "type"]).size().unstack(fill_value=0).reindex(columns=["RET", "OFF", "IND", "OTH"], fill_value=0)
    L = landuse(dd, J, zs, park_by_zone()); assert L.notna().all().all(), L.isna().sum()
    L.to_csv(f"{HERE}/zone_landuse_2016.csv", index=False); print(L.describe().T.round(3).to_string())
    print(L.drop(columns="zone").corr().round(2).to_string())


if __name__ == "__main__":
    main()
