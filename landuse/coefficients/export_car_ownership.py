#!/usr/bin/env python3
"""Car ownership (adopted model, 56 parameters, Biogeme names) -> the two SILO engine files.

Reproduces the engine files byte for byte from the full-precision estimates of the original run (verified against
landuse/engine_inputs):
  car_ownership_estimated_coefficients.csv   alternative,variable,value   (alternative 0 carries ln_density_centre only)
  car_ownership_county_constants.csv         region,asc1,asc2,asc3        (Baltimore City = region 24510 gets the estimated
                                             B_baltimore_city_* terms; every other region 0)

Input: a CSV with the 56 estimates, either `parameter,value` (start_values_full_precision.csv of the estimation folder
estimation/package/SILO/04_car_ownership/model) or the Biogeme report `Name,Value,...` (<model>_estimates.csv).
Region ids: the Region column of WORKSPACE/2_silo/input/zoneSystem.csv.

    python3 landuse/coefficients/export_car_ownership.py ESTIMATES.csv [OUT_DIR]          (OUT_DIR default: WORKSPACE/2_silo/input)
    python3 landuse/coefficients/export_car_ownership.py ESTIMATES.csv OUT_DIR --check     (also compares with landuse/engine_inputs)
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE  # noqa: E402
import filecmp, os, sys
import pandas as pd

INPUT = f"{WORKSPACE}/2_silo/input"
REF = f"{MILES_HOME}/landuse/engine_inputs"
LN_DENSITY_CENTRE = 5.485957407613654                      # mean ln density of the estimation sample (centring of ln income x ln density)
ALT = {"1car": 1, "2cars": 2, "3pluscars": 3}
# Biogeme parameter stem -> SILO variable name (order = the order of the engine file)
VARS = [("ASC", "asc"), ("B_workers", "workers"), ("B_children_under16", "children"), ("B_single_person", "single_person"),
        ("B_single_family_detached", "sfd"), ("B_multifamily", "multifamily"), ("B_bedrooms", "bedrooms"),
        ("B_ln_density_puma", "ln_density"), ("B_acc_gain_car", "acc_gain"), ("B_lninc_under25k", "inc_lt25"),
        ("B_lninc_25_50k", "inc_25_50"), ("B_lninc_50_100k", "inc_50_100"), ("B_lninc_above100k", "inc_gt100"),
        ("B_age_oldest", "age10"), ("B_age_oldest_sq", "age10_sq"), ("B_lninc_x_ln_density", "inc_x_dens"),
        ("B_persons16_2", "p16_2"), ("B_persons16_3", "p16_3"), ("B_persons16_4plus", "p16_4p")]
CITY_REGION = 24510


def read_estimates(path):
    d = pd.read_csv(path)
    name, value = ("parameter", "value") if "parameter" in d.columns else ("Name", "Value")
    return dict(zip(d[name], d[value]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    est = read_estimates(args[0]); out = args[1] if len(args) > 1 else INPUT; os.makedirs(out, exist_ok=True)
    rows = [dict(alternative=0, variable="ln_density_centre", value=LN_DENSITY_CENTRE)]
    used = set()
    for suf, a in ALT.items():
        for stem, var in VARS:
            p = f"{stem}_{suf}"
            if p in est:                                   # terms fixed at 0 are absent from the estimates
                rows.append(dict(alternative=a, variable=var, value=float(est[p]))); used.add(p)
    city = [float(est[f"B_baltimore_city_{s}"]) for s in ALT]; used |= {f"B_baltimore_city_{s}" for s in ALT}
    left = set(est) - used
    assert not left, f"estimates not mapped: {sorted(left)}"
    f_coef = os.path.join(out, "car_ownership_estimated_coefficients.csv")
    pd.DataFrame(rows).to_csv(f_coef, index=False)
    regions = sorted(pd.read_csv(os.path.join(INPUT, "zoneSystem.csv"), usecols=["Region"]).Region.unique())
    k = pd.DataFrame({"region": regions, "asc1": 0.0, "asc2": 0.0, "asc3": 0.0})
    k.loc[k.region == CITY_REGION, ["asc1", "asc2", "asc3"]] = city
    f_k = os.path.join(out, "car_ownership_county_constants.csv")
    k.to_csv(f_k, index=False)
    print(f"wrote {f_coef} ({len(rows)} rows) and {f_k} ({len(k)} regions)")
    if "--check" in sys.argv:
        for f in (f_coef, f_k):
            ref = os.path.join(REF, os.path.basename(f))
            print(os.path.basename(f), "identical to landuse/engine_inputs" if filecmp.cmp(f, ref, shallow=False) else "DIFFERS from landuse/engine_inputs")


if __name__ == "__main__":
    main()
