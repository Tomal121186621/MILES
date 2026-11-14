#!/usr/bin/env python3
"""Article-format table of the re-specified car ownership model (final model of s07_sequence.py): est_cars_new.tex, same layout as
5_reports/article/sections/est/est_cars.tex."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
from mnl import fit
from s06_age import oldest_age, prep

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
sys.path.insert(0, os.path.join(os.path.dirname(CODE), "tables"))
import t_new_tables as T     # noqa: E402  (format helpers)
f = T.f
LAB = {"constant": "Constant", "workers": "Workers", "nonworking_adults": "Non-working persons aged 16+", "children": "Children under 16",
       "any_65plus": "Member aged 65+", "single_person": "Single-person household", "inc_lt25": "ln income, slope under \\$25k",
       "inc_25_50": "ln income, slope \\$25--50k", "inc_50_100": "ln income, slope \\$50--100k", "inc_gt100": "ln income, slope above \\$100k",
       "sfd": "Single-family detached dwelling", "multifamily": "Multifamily dwelling", "bedrooms": "Bedrooms",
       "ln_density": "ln dwelling density of the PUMA (per km$^2$)", "acc_gain": "Non-work accessibility gain from a car (logsum)",
       "inc_x_dens": "ln income $\\times$ ln dwelling density (centred)",
       "age10": "Age of the oldest member ((age $-$ 45) / 10)", "age10_sq": "Age of the oldest member, squared"}
ORDER = ["constant", "workers", "nonworking_adults", "children", "any_65plus", "single_person", "age10", "age10_sq", "inc_lt25", "inc_25_50", "inc_50_100",
         "inc_gt100", "sfd", "multifamily", "bedrooms", "ln_density", "acc_gain", "inc_x_dens"]
ALT = {"1": "One car versus none", "2": "Two cars versus none", "3+": "Three or more cars versus none"}


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    md = d.ln_density.mean(); d = prep(d, md, oldest_age())   # 2026-11-09: age of the oldest member (s08_oldest_age.py)
    sf = pd.read_csv(f"{HERE}/s07_fit.csv"); V = sf[sf.step == "final"].spec.iloc[0].split()
    from s04_form import pieces; pieces(d)
    r = fit(d, V); c0 = fit(d, []); N = r["N"]; L0 = N * np.log(0.25)
    est = {n: (b, s) for n, b, s in zip(r["names"], r["b"], r["se"])}
    rows = []
    for a in ["1", "2", "3+"]:
        rows.append(f"    \\multicolumn{{4}}{{@{{}}l}}{{\\emph{{{ALT[a]}}}}} \\\\")
        for v in [v for v in ORDER if v == "constant" or v in V]:
            if v == "sfd" or (v == "multifamily" and "sfd" not in V):
                rows.append(T.ref_row("Single-family attached and other dwelling"))
            b, s = est[f"{v}|{a}"]; rows.append(T.coef_row(LAB[v], b, s))
    K = r["K"]; LL = r["LL"]
    foot = [f"Observations: {N:,} Maryland households (ACS PUMS 2014--2018, estimation sample: 80\\%); alternatives: 4 (0, 1, 2, 3 or more cars); parameters: {K}.",
            f"LL(0) = {f(L0, 1)}; LL(constants) = {f(c0['LL'], 1)}; LL($\\hat\\beta$) = {f(LL, 1)}; $\\rho^2$ = {1 - LL / L0:.3f}; $\\rho^2$ against constants = {1 - LL / c0['LL']:.3f}; AIC = {f(-2 * LL + 2 * K, 1)}; BIC = {f(r['BIC'], 1)}.",
            "Estimation: unweighted multinomial logit (maximum likelihood, Newton); robust (sandwich) standard errors.",
            f"Income in 2016 \\$, ln(income / \\$50k), at least \\$5k, piecewise linear with bends at \\$25k, \\$50k and \\$100k. Density centred at its mean ({md:.2f}). The accessibility gain is that of the household's income group (under \\$40k, \\$40--75k, \\$75--125k, \\$125k or more)."]
    open(f"{HERE}/est_cars_new.tex", "w").write(T.wrap("Car-ownership model (multinomial logit; reference: no car).", "tab:est_cars", rows, foot))
    print(N, K, LL, r["BIC"])


if __name__ == "__main__":
    main()
