#!/usr/bin/env python3
"""Coefficient tables of the re-specified zone x structure-type part (r03_sequence.py, final model) and dwelling part
(r06_dwelling_income.py, chosen form): est_zone_new.tex, est_dwelling_new.tex, in the layout of the article tables, terms grouped."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/residential"   # results of this step (data); CODE = this folder
sys.path.insert(0, os.path.join(os.path.dirname(CODE), "tables"))
import t_new_tables as T     # noqa: E402  (format helpers and reference bands)
f = T.f
AGE = lambda pre, fmt: T.Ref(fmt, [(f"{pre}ageU35", "under 35"), (None, "35--49"), (f"{pre}age50_64", "50--64"), (f"{pre}age65", "65+")])
TYPES = [("SFA", "single-family attached"), ("MF234", "multifamily 2--4 units"), ("MF5plus", "multifamily 5+ units"), ("MH", "mobile home or other")]
ZONE = [("Size", [("lnD", "ln dwellings of the structure type in the zone ($\\theta$)")]),
        ("Accessibility (logsum of the household's segment)", [("accW", "Work accessibility"), ("accW_x_nocar", "Work accessibility $\\times$ no car"),
            ("accN", "Non-work accessibility"), ("accN_x_child", "Non-work accessibility $\\times$ children"),
            ("accN_x_ageU35", "Non-work accessibility $\\times$ oldest member under 35"), ("accN_x_age50_64", "Non-work accessibility $\\times$ oldest member 50--64"),
            ("accN_x_age65", "Non-work accessibility $\\times$ oldest member 65+"), ("accN_x_hhs", "Non-work accessibility $\\times$ (household size $-$ 1, at most 5)")]),
        ("Commute", [("commute_log", "Commute: $\\sum_{\\text{workers}} \\ln(1+t)$")]),
        ("Zone price level", [("lncost", "ln mean monthly housing cost of the zone"), ("lncost_x_inc", "ln zone cost $\\times$ ln income"),
            ("lncost_x_hhs", "ln zone cost $\\times$ (household size $-$ 1, at most 5)")]),
        ("Neighbours", [("sim", "Share of same-income households in the zone")]),
        ("Land use of the zone", [("lnddens", "ln dwellings per acre"), ("lnddens_x_nocar", "ln dwellings per acre $\\times$ no car"),
            ("lnddens_x_child", "ln dwellings per acre $\\times$ children"), ("lnjden", "ln(1 + jobs per acre)"), ("lnretden", "ln(1 + retail jobs per km$^2$)"),
            ("mix", "Land-use mix (entropy of retail, office, other jobs and dwellings)"), ("park", "Paid-parking share")])]
DWEL = [("Housing cost", [("bur_lo", "Cost share of income, slope below 30\\,\\%"), ("bur_lo_x_lninc", "\\quad $\\times$ ln income"),
            ("bur_mid", "Cost share of income, slope 30--50\\,\\%"), ("bur_mid_x_lninc", "\\quad $\\times$ ln income"),
            ("bur_hi", "Cost share of income, slope above 50\\,\\%"), ("bur_hi_x_lninc", "\\quad $\\times$ ln income"),
            ("lncost", "ln monthly housing cost"), ("lncost_x_lninc", "\\quad $\\times$ ln income")]),
        ("Size and age of the dwelling", [("bed_short", "Bedroom shortfall (per bedroom)"), ("bed_short_x_lninc", "\\quad $\\times$ ln income"),
            ("bed_extra", "Bedroom excess (per bedroom)"), ("bed_extra_x_lninc", "\\quad $\\times$ ln income"),
            ("new5", "Built in the last five years"), ("new5_x_lninc", "\\quad $\\times$ ln income")])] + \
       [(f"Structure type: {lab} (reference: single-family detached)", [(t, "Constant"), (f"{t}_x_size", "$\\times$ (household size $-$ 1)"),
            (f"{t}_x_child", "$\\times$ children"), (f"{t}_x_ageU35", "$\\times$ oldest member under 35"), (f"{t}_x_age50_64", "$\\times$ oldest member 50--64"),
            (f"{t}_x_age65", "$\\times$ oldest member 65+"), (f"{t}_x_lninc", "$\\times$ ln income")]) for t, lab in TYPES]


def write(fn, caption, label, c, groups, foot):
    c = c.drop(columns="se").rename(columns={"estimate": "coef", "robust_se": "se"})
    groups = [(g, T.with_refs(t, [AGE("accN_x_", "Non-work accessibility $\\times$ oldest member {}")]
                              + [AGE(f"{s}_x_", "$\\times$ oldest member {}") for s, _ in TYPES])) for g, t in groups]
    open(f"{HERE}/{fn}", "w").write(T.longtable(caption, label, c, groups, foot, fn))


def main():
    zf = pd.read_csv(f"{HERE}/r08_fit.csv"); z = zf[zf.chosen.fillna(False).astype(bool)].iloc[0]
    zc = pd.read_csv(f"{HERE}/r08_coef.csv"); zc = zc[zc.model == z.model].set_index("parameter")
    mm = z.model.startswith("multimodal")
    write("est_zone_new.tex", "Residential location, zone and structure type within the county.", "tab:est_zone", zc, ZONE,
          [f"Observations: {int(z.N):,} households of the Regional Travel Survey 2017/18 (estimation half; households with the age of their members); alternatives: 30 (chosen + 29 uniformly sampled; no correction needed); parameters: {int(z.K)}.",
           f"LL($\\hat\\beta$) = {f(z.LL, 1)}; BIC = {f(z.BIC, 1)}; validation half, full choice set: LL = {f(z.validation_LL_fullset, 1)}. Commute $t$: peak car time (min) to the worker's workplace, transit door-to-door time for households without a car.",
           "Accessibility: logsum of the destination-choice models over all zones for the household's income group and car availability" + (", with the mode-choice logsum (car, transit, walk, bike) as impedance." if mm else ", with car-based impedance."),
           "Estimation: weighted exogenous sample maximum likelihood with the survey household weights; robust standard errors. Income: ln(household income / \\$50k). Structure types: single-family detached, single-family attached, multifamily, mobile home. Land use: 2016 dwellings and jobs of the synthetic population per acre of the zone; retail jobs per km$^2$."])
    df = pd.read_csv(f"{HERE}/r06_fit.csv"); d = df[df.validation_LL.notna()].iloc[0]
    dc = pd.read_csv(f"{HERE}/r06_coef.csv"); dc = dc[dc.model == d.model].set_index("parameter")
    write("est_dwelling_new.tex", "Residential location, dwelling within the PUMA.", "tab:est_dwelling", dc, DWEL,
          [f"Observations: {int(d.N):,} ACS PUMS movers 2014--2018 (estimation sample); alternatives: 30 (chosen + 29 uniformly sampled); parameters: {int(d.K)}.",
           f"LL(0) = {f(d.LL0, 1)}; LL($\\hat\\beta$) = {f(d.LL, 1)}; $\\rho^2$ = {d.rho2:.3f}; BIC = {f(d.BIC, 1)}; validation sample LL = {f(d.validation_LL, 1)}.",
           "Cost share: 12 $\\times$ monthly housing cost / household income, piecewise linear with bends at 30\\,\\% and 50\\,\\%. Income: ln(household income / \\$50k). Bedroom need: 1 for one person, else household size $-$ 1 (at most 4)."])
    print("zone N", int(z.N), "K", int(z.K), "| dwelling K", int(d.K))


if __name__ == "__main__":
    main()
