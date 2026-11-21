#!/usr/bin/env python3
"""Final specification of the two-level residential location model (copy of the project's final script, functions only).

  dwelling within the PUMA (18 terms): cost above 30 % of income (share, one slope) and ln monthly housing cost, each x ln income;
     bedroom shortfall and excess, each x ln income; built in the last 5 years, x ln income; structure-type constants SFA,
     MF 2-4, MF 5+, mobile home (SFD reference), each x ln income.   ln income = ln(max(income, 5000) / 50000).
  PUMA (10 terms), inclusive value of the dwelling level with coefficient 1: ln market size, car time 20-60 and > 60 min from
     the previous home, destination inside the previous migration area, destination bordering it, same state, commute
     sum ln(1 + t), crime x children, ln dwelling density, own-race share of the PUMA's households.
SEED: the generator of two_level.sample / upper_data is reset to this seed before the first draw (dwelling sets of the estimation
half, then of the validation half, then the 200 market dwellings per PUMA of the inclusive values, estimation then validation)."""
import os
os.environ["RACE_TEST"] = "1"; os.environ["DW_INC"] = "1"   # two_level: own-race share computed, income interactions in the dwelling design
import numpy as np
import two_level as R   # noqa: E402

SEED = 20261117
DWF = ["over30", "over30_x_lninc", "lncost", "lncost_x_lninc", "bed_short", "bed_short_x_lninc", "bed_extra", "bed_extra_x_lninc",
       "new5", "new5_x_lninc"] + [v for t in R.TYPES for v in (t, f"{t}_x_lninc")]
UPF = ["lnM", "d2", "d3", "same", "adjacent", "same_state", "commute_log", "crime_x_child", "lnddens", "own_race"]
LABEL = {"over30": "cost above 30 % of income (share)", "lncost": "ln monthly housing cost", "bed_short": "bedroom shortfall", "bed_extra": "bedroom excess",
         "new5": "built in the last 5 years", "SFA": "single-family attached", "MF234": "multi-family 2-4 units", "MF5plus": "multi-family 5+ units", "MH": "mobile home",
         "lnM": "ln market size of the PUMA", "d2": "car time 20-60 min from the previous home (min)", "d3": "car time over 60 min (min)",
         "same": "destination inside the previous migration area (PUMA group)", "adjacent": "destination bordering the previous migration area",
         "same_state": "same state", "commute_log": "commute, sum over workers of ln(1 + min)", "crime_x_child": "crime index x children",
         "lnddens": "ln dwelling density", "own_race": "own-race share of the PUMA's households"}
# Biogeme parameter names of the package scripts (model/estimate_*.py)
BIOGEME = {"over30": "B_cost_share_above30", "over30_x_lninc": "B_cost_share_above30_x_lninc", "lncost": "B_ln_cost", "lncost_x_lninc": "B_ln_cost_x_lninc",
           "bed_short": "B_bedroom_shortfall", "bed_short_x_lninc": "B_bedroom_shortfall_x_lninc", "bed_extra": "B_bedroom_excess",
           "bed_extra_x_lninc": "B_bedroom_excess_x_lninc", "new5": "B_built_last5yrs", "new5_x_lninc": "B_built_last5yrs_x_lninc",
           "SFA": "ASC_SFA", "SFA_x_lninc": "B_SFA_x_lninc", "MF234": "ASC_MF2_4", "MF234_x_lninc": "B_MF2_4_x_lninc",
           "MF5plus": "ASC_MF5plus", "MF5plus_x_lninc": "B_MF5plus_x_lninc", "MH": "ASC_mobile_home", "MH_x_lninc": "B_mobile_home_x_lninc",
           "lnM": "B_ln_market_size", "d2": "B_cartime_20_60", "d3": "B_cartime_over60", "same": "B_previous_migration_area",
           "adjacent": "B_bordering_previous_area", "same_state": "B_same_state", "commute_log": "B_commute_sum_ln1p_time",
           "crime_x_child": "B_crime_x_children", "lnddens": "B_ln_dwelling_density", "own_race": "B_own_race_share"}
_full = R.dw_X


def dw_final(h, alt):
    """design of the final dwelling level (also used for the inclusive value of the PUMA level)"""
    X = _full(h, alt); F = {n: X[:, :, k] for k, n in enumerate(R.DW)}
    inc = np.maximum(h.income.values, 5000.0)[:, None]; lninc = np.log(inc / 50000.0); b = np.minimum(12 * alt["cost"] / inc, 3.0)
    F["over30"] = np.maximum(b - .3, 0); F["over30_x_lninc"] = F["over30"] * lninc
    return np.stack([F[n] for n in DWF], 2)
