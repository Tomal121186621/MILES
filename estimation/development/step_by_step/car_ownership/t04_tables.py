#!/usr/bin/env python3
"""Car ownership step 4: income effect check of the chosen form and LaTeX tables (car_ownership/tab_step4_*.tex)."""
import os
import numpy as np, pandas as pd
from mnl import fit, probs, design
from s04_form import REST, pieces

HERE = os.path.dirname(os.path.abspath(__file__))


def num(x, d=1):
    return f"{x:,.{d}f}".replace("-", "$-$")


def main():
    d = pd.read_parquet(f"{HERE}/hh.parquet"); d = d[d.half == "estimation"].reset_index(drop=True)
    for c in ["workers", "nonworking_adults", "children"]: d[c] = d[c].clip(upper=6)
    P = pieces(d); V = REST + P; r = fit(d, V)
    ex = lambda x: probs(r["b"], design(x, V)) @ np.arange(4)
    e = d.copy(); e["ln_income"] = d.ln_income + np.log(1.1); pieces(e)
    dif = ex(e) - ex(d); inc = np.exp(d.ln_income) * 50
    bands = [(0, 25, "under \\$25k"), (25, 50, "\\$25--50k"), (50, 100, "\\$50--100k"), (100, 1e9, "\\$100k or more")]
    rows = []
    for lo, hi, lab in bands:
        m = (inc >= lo) & (inc < hi)
        rows.append((lab, m.sum(), dif[m].mean(), (dif[m] < 0).mean()))
    t = ["\\begin{tabular}{@{}lrrr@{}}", "\\toprule", "Household income & Households & Cars per household, income +10\\% & Share with a negative effect \\\\ \\midrule"]
    t += [f"{a} & {b:,} & {num(c, 4)} & {100 * s:.1f}\\% \\\\" for a, b, c, s in rows]
    t += ["\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step4_incfx.tex", "w").write("\n".join(t)); print(rows)
    I = pd.read_csv(f"{HERE}/s04_income.csv"); O = pd.read_csv(f"{HERE}/s04_ordered.csv")
    t = ["\\begin{tabular}{@{}lrrr@{}}", "\\toprule", "Form & Parameters & Log-likelihood & BIC \\\\ \\midrule"]
    for _, x in I.iloc[:2].iterrows(): t.append(f"{x.form.replace('$', '').replace('k,', 'k,')} & {int(x.K)} & {num(x.LL)} & {num(x.BIC)} \\\\")
    for _, x in O.iterrows(): t.append(f"{x.model} & {int(x.K)} & {num(x.LL)} & {num(x.BIC)} \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step4_fit.tex", "w").write("\n".join(t).replace("k, 50k, 100k", "k, \\$50k, \\$100k").replace("knots 25k", "bends at \\$25k"))
    s = I.iloc[2:].copy(); s["v"] = s.form.str.strip().str.replace("slope ", "")
    lab = {"inc_lt25": "under \\$25k", "inc_25_50": "\\$25--50k", "inc_50_100": "\\$50--100k", "inc_gt100": "above \\$100k"}
    t = ["\\begin{tabular}{@{}lrrr@{}}", "\\toprule", "Slope of ln income & 1 car & 2 cars & 3+ cars \\\\ \\midrule"]
    for k in lab:
        vals = [s[s.v == f"{k}|{a}"].iloc[0] for a in ["1", "2", "3+"]]
        t.append(lab[k] + " & " + " & ".join(f"{num(x.coef, 2)} ({num(x.t, 1)})" for x in vals) + " \\\\")
    t += ["\\bottomrule", "\\end{tabular}"]
    open(f"{HERE}/tab_step4_slopes.tex", "w").write("\n".join(t))
    W = pd.read_csv(f"{HERE}/s04_weights.csv")
    print("weights: n |z|>1.96", (W.z_diff.abs() > 1.96).sum(), "of", len(W), "; se ratio w/u median", (W.se_w / W.se_u).median().round(2))


if __name__ == "__main__":
    main()
