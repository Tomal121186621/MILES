#!/usr/bin/env python3
"""Article-format table of the final pooled tour mode-choice model (mp_pooled.py): est_mc_pooled.tex.
Rows = variables grouped (level of service, person, household, tour, main-activity zone, constants), columns = Walk, Bike,
Car passenger, Bus, Train (reference: car driver).  One panel for the coefficients shared by all purposes, one per subset
of purposes sharing a coefficient (if any), one per purpose for its own coefficients and its scale.
    ~/.venvs/biogeme/bin/python estimation/development/tour_mode_choice_pooled/t_mp_table.py   (then compile-check with check_tex.sh)"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import sys
sys.dont_write_bytecode = True
import os
import numpy as np, pandas as pd
from scipy.stats import norm

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/mode_pooled"   # results of this step (data); CODE = this folder
PURP = ["work", "shopping", "other", "school"]
PNAME = {"work": "Work", "shopping": "Shopping", "other": "Other (recreation, accompanying, errands)", "school": "School"}
MODES = [("WK", "Walk"), ("BK", "Bike"), ("CP", "Car passenger"), ("BUS", "Bus"), ("TRAIN", "Train")]
GENERIC = [("Level of service", [("time", "Travel time, car driver, car passenger, bus, train (min)"),
                                 ("cost", "Travel cost, car driver, bus, train (\\$)")]),
           ("Tour", [("park_CD", "Car driver: paid-parking share at the destination"), ("stops_CD", "Car driver: tour with stops")])]
GROUPS = [("Level of service", [("km", "Round-trip distance (km)")]),
          ("Person", [("age", "Age (years)"), ("male", "Man"), ("lic", "Driving licence")]),
          ("Household", [("hhsize", "Household size"), ("autos", "Cars"), ("kids", "Children under 16"), ("short", "Fewer cars than drivers")]),
          ("Tour", [("joint", "Joint household tour"), ("acc", "Purpose: accompanying"), ("rec", "Purpose: recreation")]),
          ("Main-activity zone", [("core_d", "Core city"), ("rural_d", "Rural")]),
          ("Constants", [("ASC", "Constant")])]
NEST = [("nest_auto", "Nest parameter, car driver and passenger"), ("nest_transit", "Nest parameter, bus and train")]
NC = 6


def cell(b, t):
    p = 2 * norm.sf(abs(t)); s = "$^{***}$" if p < 0.01 else "$^{**}$" if p < 0.05 else "$^{*}$" if p < 0.10 else ""
    return f"{b:.3f}{s} ({t:.1f})".replace("-", "$-$")


def panel(title, c, work=False):
    """c: DataFrame indexed by param (base name) with coef, se, t"""
    rows = [r"    \midrule", f"    \\multicolumn{{{NC}}}{{@{{}}l}}{{\\textbf{{{title}}}}} \\\\"]
    if work:
        rows.append(r"    Scale & \multicolumn{5}{l}{1 (normalisation)} \\")
    if "scale" in c.index:
        b, se = c.loc["scale", "coef"], c.loc["scale", "se"]
        rows.append(f"    Scale ($t$ against 1) & \\multicolumn{{5}}{{l}}{{{cell(b, (b - 1) / se)}}} \\\\")
    for p, lab in NEST:
        if p in c.index:
            b, se = c.loc[p, "coef"], c.loc[p, "se"]
            rows.append(f"    {lab} ($t$ against 1) & \\multicolumn{{5}}{{l}}{{{cell(b, (b - 1) / se)}}} \\\\")
    groups = {}
    for g, terms in GENERIC:
        for p, lab in terms:
            if p in c.index: groups.setdefault(g, []).append(f"    {lab} & \\multicolumn{{5}}{{l}}{{{cell(c.loc[p, 'coef'], c.loc[p, 't'])}}} \\\\")
    for g, terms in GROUPS:
        for v, lab in terms:
            cs = [cell(c.loc[f"{v}_{m}", "coef"], c.loc[f"{v}_{m}", "t"]) if f"{v}_{m}" in c.index else "" for m, _ in MODES]
            if any(cs): groups.setdefault(g, []).append(f"    {lab} & " + " & ".join(cs) + " \\\\")
    for g in ["Level of service", "Person", "Household", "Tour", "Main-activity zone", "Constants"]:
        if g in groups: rows += [f"    \\multicolumn{{{NC}}}{{@{{}}l}}{{\\emph{{{g}}}}} \\\\"] + groups[g]
    return rows


def main():
    C = pd.read_csv(f"{HERE}/mp_coef.csv"); F = pd.read_csv(f"{HERE}/mp_fit.csv")
    c = C[C.step == "final"]; f = F[F.step == "final"].iloc[0]
    N = {p: int(F[F.step == f"sep_{p}"].iloc[0].N) for p in PURP}
    rows = panel("Coefficients shared by all four purposes", c[c.purpose == "shared"].set_index("param"))
    subsets = [g for g in c.purpose.unique() if "+" in str(g)]
    for g in subsets:
        rows += panel("Coefficients shared by " + " and ".join(PNAME[q].split(" (")[0].lower() for q in g.split("+")) + " tours",
                      c[c.purpose == g].set_index("param"))
    for p in PURP:
        rows += panel(f"{PNAME[p]} tours: own coefficients", c[c.purpose == p].set_index("param"), work=p == "work")
    with open(f"{HERE}/mp.log", "a") as L:
        L.write("final pooled model, scales and nest parameters (t against 1):\n")
        for _, r in c[c.param.isin(["scale", "nest_auto", "nest_transit"])].iterrows():
            L.write(f"   {r.purpose} {r.param}: {r.coef:.3f} (se {r.se:.3f}, t against 1 {(r.coef - 1) / r.se:.2f})\n")
    head = rf"""{{\footnotesize\setlength{{\tabcolsep}}{{3pt}}\nolinenumbers
\begin{{longtable}}{{@{{}}L{{0.27\linewidth}}lllll@{{}}}}
  \caption{{Tour mode choice, pooled model of work, shopping, other and school tours with purpose-specific scale: coefficient (robust $t$); reference mode: car driver.}}
  \label{{tab:est_mc_pooled}}\\
  \toprule
  Variable & {" & ".join(l for _, l in MODES)} \\
  \endfirsthead
  \toprule
  Variable & {" & ".join(l for _, l in MODES)} \\
  \endhead
  \bottomrule
  \endlastfoot
"""
    vl = ", ".join(f"{PNAME[p].split(' (')[0].lower()} {f[f'validation_LL_{p}']:,.1f}" for p in PURP)
    nn = ", ".join(f"{PNAME[p].split(' (')[0].lower()} {N[p]:,}" for p in PURP)
    nest = bool(f.nest) if "nest" in f else False
    foot = [r"    \midrule",
            f"    \\multicolumn{{{NC}}}{{@{{}}p{{0.98\\linewidth}}}}{{Observations (estimation half of the Regional Travel Survey 2017/18): {nn} tours; alternatives: 6; parameters: {int(f.K)}; LL = {f.LL:,.1f}; BIC = {f.BIC:,.1f}. Validation half, LL: {vl}.}} \\\\".replace("-", "$-$"),
            f"    \\multicolumn{{{NC}}}{{@{{}}p{{0.98\\linewidth}}}}{{Utility of a {('tour of purpose $p$: $U = \\mu_p V_p$, with $\\mu$ = 1 for work tours')}; a shared coefficient takes the same value in $V_p$ of every purpose that shares it, so its effect on utility differs across purposes only through the scale. Times, costs and distances of the round trip; car-passenger cost is zero. Core city and rural: area type of the zone of the main activity. Empty cells: term not in the model, or not identified because no tour of that class chooses the mode (e.g.\\ train to a rural zone). Work tours weighted with choice-based sample weights. {'Other tours: nested logit with car driver and passenger in one nest and bus and train in another; the other purposes: multinomial logit.' if nest else 'Multinomial logit.'}}} \\\\",
            f"    \\multicolumn{{{NC}}}{{@{{}}p{{0.98\\linewidth}}}}{{$^{{***}}$ $p<0.01$, $^{{**}}$ $p<0.05$, $^{{*}}$ $p<0.10$ (scale and nest parameters: against 1).}} \\\\",
            r"\end{longtable}", r"\linenumbers}"]
    open(f"{HERE}/est_mc_pooled.tex", "w").write(head + "\n".join(rows) + "\n" + "\n".join(foot) + "\n")
    print("rows", len(rows))


if __name__ == "__main__":
    main()
