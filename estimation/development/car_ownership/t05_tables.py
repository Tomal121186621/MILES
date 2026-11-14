#!/usr/bin/env python3
"""Car ownership step 5: final model (step-4 model + ln income x density), the effect of density by income, and LaTeX tables."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd
from mnl import fit, probs, design
from s04_form import REST, pieces

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
LAB = {"constant": "Constant", "workers": "Workers", "nonworking_adults": "Non-working persons 16+", "children": "Children under 16",
       "any_65plus": "Member 65+", "single_person": "Single person", "sfd": "Single-family detached", "multifamily": "Multifamily",
       "bedrooms": "Bedrooms", "ln_density": "ln dwelling density (PUMA)", "acc_gain": "Accessibility gain from a car",
       "inc_lt25": "ln income, slope under \\$25k", "inc_25_50": "ln income, slope \\$25--50k", "inc_50_100": "ln income, slope \\$50--100k",
       "inc_gt100": "ln income, slope above \\$100k", "inc_x_dens": "ln income $\\times$ density (centred)"}


def num(x, d=1):
    return f"{x:,.{d}f}".replace("-", "$-$")


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    for c in ["workers", "nonworking_adults", "children"]: d[c] = d[c].clip(upper=6)
    V = REST + pieces(d); mean_dens = d.ln_density.mean(); d["inc_x_dens"] = d.ln_income * (d.ln_density - mean_dens); V = V + ["inc_x_dens"]
    r = fit(d, V)
    t = ["\\begin{longtable}{@{}lrrr@{}}", "\\toprule", "Variable & 1 car & 2 cars & 3+ cars \\\\ \\midrule", "\\endhead"]
    for v in ["constant"] + V:
        x = {a: (b, s) for n, b, s in zip(r["names"], r["b"], r["se"]) for a in [n.split("|")[1]] if n.split("|")[0] == v}
        t.append(LAB[v] + " & " + " & ".join(f"{num(x[a][0], 2)} ({num(x[a][0] / x[a][1], 1)})" for a in ["1", "2", "3+"]) + " \\\\")
    t += ["\\bottomrule", f"\\multicolumn{{4}}{{@{{}}p{{0.85\\linewidth}}}}{{\\footnotesize Coefficient (robust $t$); reference: no car. 91,348 households, unweighted. "
          f"Parameters {r['K']}; log-likelihood {num(r['LL'])}; BIC {num(r['BIC'])}. Density centred at its mean (ln {mean_dens:.2f}); ln income centred at \\$50k.}} \\\\",
          "\\end{longtable}"]
    open(f"{HERE}/tab_step5_coef.tex", "w").write("\n".join(t))
    # effect of +1 s.d. density on cars per household, by income band
    ex = lambda x: probs(r["b"], design(x, V)) @ np.arange(4)
    e = d.copy(); e["ln_density"] = d.ln_density + d.ln_density.std(); e["inc_x_dens"] = e.ln_income * (e.ln_density - mean_dens)
    dif = ex(e) - ex(d); inc = np.exp(d.ln_income) * 50
    rows = []
    for lo, hi, lab in [(0, 25, "under \\$25k"), (25, 50, "\\$25--50k"), (50, 100, "\\$50--100k"), (100, 1e9, "\\$100k or more")]:
        m = (inc >= lo) & (inc < hi); rows.append(f"{lab} & {m.sum():,} & {num(dif[m].mean(), 3)} \\\\")
    t = ["\\begin{tabular}{@{}lrr@{}}", "\\toprule", "Household income & Households & Cars per household, density +1 s.d. \\\\ \\midrule"] + rows + ["\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step5_dens.tex", "w").write("\n".join(t))
    R = pd.read_csv(f"{HERE}/s05_interactions.csv")
    lab = {"step-4 model": "Step-4 model", "+ ln income x density": "+ ln income $\\times$ density", "+ workers x density": "+ workers $\\times$ density",
           "+ children x single-family detached": "+ children $\\times$ single-family detached", "+ member 65+ x ln income": "+ member 65+ $\\times$ ln income",
           "+ single person x density": "+ single person $\\times$ density"}
    t = ["\\begin{tabular}{@{}lrrrr@{}}", "\\toprule", "Model & Parameters & Log-likelihood & Change in BIC & Baltimore City, no car (\\%) \\\\ \\midrule"]
    for _, x in R.iterrows():
        nm = lab.get(x.model, "+ both that lower the BIC (income and workers $\\times$ density)")
        t.append(f"{nm} & {int(x.K)} & {num(x.LL)} & {'' if np.isnan(x.dBIC) else num(x.dBIC)} & {x.balt_nocar:.1f} \\\\")
    t += ["\\midrule", f"Observed & & & & {R.balt_nocar_observed.iloc[0]:.1f} \\\\", "\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step5_tests.tex", "w").write("\n".join(t))
    print(r["LL"], r["K"], r["BIC"]); print(rows)


if __name__ == "__main__":
    main()
