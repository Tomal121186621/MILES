#!/usr/bin/env python3
"""LaTeX tables of car ownership steps 0 and 3 for modeling_step_by_step.tex (written to car_ownership/tab_*.tex)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/car_ownership"   # results of this step (data); CODE = this folder
LAB = {"constant": "Constant", "workers": "Workers", "nonworking_adults": "Non-working persons 16+", "children": "Children under 16",
       "any_65plus": "Member 65+", "single_person": "Single person", "ln_income": "ln income (\\$50k = 0)",
       "sfd": "Single-family detached", "multifamily": "Multifamily", "bedrooms": "Bedrooms", "ln_density": "ln dwelling density (PUMA)",
       "acc_gain": "Accessibility gain from a car"}
ADDED = {"M1": "constants only", "M2": "household composition", "M3": "ln income", "M4": "dwelling type, bedrooms",
         "M5": "ln dwelling density", "M6": "accessibility gain from a car"}


def num(x, d=1):
    s = f"{x:,.{d}f}"; return s.replace("-", "$-$")


def main():
    F = pd.read_csv(f"{HERE}/s03_fit.csv"); C = pd.read_csv(f"{HERE}/s03_coef.csv"); E = pd.read_csv(f"{HERE}/s03_effects.csv")
    O = pd.read_csv(f"{HERE}/s00_original.csv")
    m6 = F.set_index("step").loc["M6"]
    # step 0: existing models on the same households
    rows = [("Original SILO Maryland model, as coded (density in jobs per square mile)", "own coefficients", O.LL[0], O.pred_shares[0]),
            ("Original SILO Maryland model, density in jobs per acre", "own coefficients", O.LL[1], O.pred_shares[1]),
            ("Original variables, re-estimated", "72", O.LL[2], None),
            ("Current model (article)", "45", -91811.7, None),
            ("New model after step 3 (M6)", "36", m6.LL, None)]
    obs = eval(O.pred_shares[3])
    t = ["\\begin{tabular}{@{}L{0.43\\linewidth}rrL{0.22\\linewidth}@{}}", "\\toprule",
         "Model & Parameters & Log-likelihood & Predicted 0 / 1 / 2 / 3+ cars (\\%) \\\\ \\midrule"]
    for a, k, ll, sh in rows:
        s = " / ".join(f"{100 * v:.1f}" for v in eval(sh)) if isinstance(sh, str) else "as observed"
        t.append(f"{a} & {k} & {num(ll)} & {s} \\\\")
    t += ["\\midrule", f"Observed & & & {' / '.join(f'{100 * v:.1f}' for v in obs)} \\\\", "\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step0.tex", "w").write("\n".join(t))
    # step 3: fit by step
    t = ["\\begin{tabular}{@{}llrrrrr@{}}", "\\toprule",
         "Step & Added & Parameters & Log-likelihood & LR (df) against previous & BIC & $\\rho^2$ \\\\ \\midrule"]
    for _, r in F.iterrows():
        lr = "" if np.isnan(r.get("LR", np.nan)) else f"{num(r.LR)} ({int(r.dK)})"
        t.append(f"{r.step} & {ADDED[r.step]} & {int(r.K)} & {num(r.LL)} & {lr} & {num(r.BIC)} & {r.rho2_const:.3f} \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step3_fit.tex", "w").write("\n".join(t))
    # step 3: final coefficients
    c = C[C.step == "M6"]; t = ["\\begin{tabular}{@{}lrrr@{}}", "\\toprule", "Variable & 1 car & 2 cars & 3+ cars \\\\ \\midrule"]
    for v in c.variable.unique():
        x = c[c.variable == v].set_index("alt")
        t.append(LAB[v] + " & " + " & ".join(f"{num(x.at[a, 'coef'], 2)} ({num(x.at[a, 't'], 1)})" for a in ["1", "2", "3+"]) + " \\\\")
    t += ["\\bottomrule", "\\multicolumn{4}{@{}p{0.8\\linewidth}}{\\footnotesize Coefficient (robust $t$); reference: no car. "
          f"91,348 households, unweighted. Log-likelihood {num(m6.LL)}.}} \\\\", "\\end{tabular}"]
    open(f"{HERE}/tab_step3_coef.tex", "w").write("\n".join(t))
    # step 3: average effects
    exp = {"workers": "+", "nonworking_adults": "+", "children": "+", "any_65plus": "$-$", "single_person": "$-$", "ln_income": "+",
           "sfd": "+", "multifamily": "$-$", "bedrooms": "+", "ln_density": "$-$", "acc_gain": "+"}
    t = ["\\begin{tabular}{@{}llrcc@{}}", "\\toprule", "Variable & Change & Effect on cars per household & Expected & Agrees \\\\ \\midrule"]
    for _, r in E.iterrows():
        ok = (r.effect_cars > 0) == (exp[r.variable] == "+")
        t.append(f"{LAB[r.variable]} & {r.change.replace('->', '$\\to$').replace('x 2', '$\\times$ 2')} & {num(r.effect_cars, 3)} & {exp[r.variable]} & {'yes' if ok else '\\textbf{no}'} \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step3_effects.tex", "w").write("\n".join(t))
    # step 3: how coefficients change as groups enter (3+ cars)
    keys = ["workers", "single_person", "ln_income", "sfd", "multifamily", "ln_density"]
    t = ["\\begin{tabular}{@{}lrrrrr@{}}", "\\toprule", "Coefficient for 3+ cars & M2 & M3 & M4 & M5 & M6 \\\\ \\midrule"]
    for v in keys:
        vals = []
        for s in ["M2", "M3", "M4", "M5", "M6"]:
            x = C[(C.step == s) & (C.variable == v) & (C.alt == "3+")]
            vals.append(num(x.coef.iloc[0], 2) if len(x) else "")
        t.append(LAB[v] + " & " + " & ".join(vals) + " \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step3_track.tex", "w").write("\n".join(t))
    L = pd.read_csv(f"{HERE}/s03_location_choice.csv")
    print(L)


if __name__ == "__main__":
    main()
