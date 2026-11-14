#!/usr/bin/env python3
"""Coefficient tables of the tour mode choice models (final models of m08_sequence.py): est_mc_<purpose>_new.tex, one row per
variable and one column per mode (reference: car driver).  Robust t from m08_coef.csv; s.e. = coefficient / t."""
import os
import numpy as np, pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
N = {"work": 9126, "shopping": 3206, "other": 10405, "school": 2651}
TITLE = {"work": "work", "shopping": "shopping", "other": "other (recreation, accompanying and other errands)", "school": "school",
         "shopping_joint": "joint household shopping", "other_joint": "joint household recreation and other"}
MODES = [("WK", "Walk"), ("BK", "Bike"), ("CP", "Car passenger"), ("BUS", "Bus"), ("TRAIN", "Train")]
GENERIC = [("gc", "Generalised cost (min)"), ("time", "Travel time (min)"), ("cost", "Travel cost (\\$)"),
           ("park_CD", "Car driver: paid-parking share at the destination"), ("stops_CD", "Car driver: tour with stops"),
           ("mu_auto", "Nest parameter, car driver and passenger"), ("mu_transit", "Nest parameter, bus and train")]
GROUPS = [("Constant and distance", [("ASC", "Constant"), ("km", "Round-trip distance (km)")]),
          ("Person", [("age", "Age (years)"), ("male", "Man"), ("lic", "Driving licence")]),
          ("Household", [("hhsize", "Household size"), ("autos", "Cars"), ("kids", "Member under 18"), ("short", "Fewer cars than drivers")]),
          ("Main activity zone", [("core_d", "Core city"), ("rural_d", "Rural")]),
          ("Tour", [("joint", "Joint household tour"), ("acc", "Accompanying"), ("rec", "Recreation")])]


def stars(p):
    return "$^{***}$" if p < 0.01 else "$^{**}$" if p < 0.05 else "$^{*}$" if p < 0.10 else ""


def pval(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def cell(b, t):
    """coefficient with stars; robust s.e. (4 digits) and p below it"""
    p = 2 * norm.sf(abs(t)); se = abs(b / t)
    return f"{b:.4f}".replace("-", "$-$") + stars(p), f"{{\\scriptsize ({se:.4f}) {pval(p)}}}"


def table(seg, c, fit):
    rows = [r"    \multicolumn{6}{@{}l}{\emph{Generic and car-driver terms}} \\"]
    for p, lab in GENERIC:
        if p in c.index:
            b, t = c.loc[p, "coef"], c.loc[p, "t"]
            se = abs(b / t)
            if p.startswith("mu_"): t = (b - 1) / se      # p against 1
            top, _ = cell(b, t)
            rows.append(f"    {lab} & \\multicolumn{{5}}{{l}}{{{top}\\ {{\\scriptsize ({se:.4f}) {pval(2 * norm.sf(abs(t)))}}}}} \\\\")
    for g, terms in GROUPS:
        body = []
        for v, lab in terms:
            key = lambda m: f"{v}_{m}" if f"{v}_{m}" in c.index else (f"{v}_PT" if m in ("BUS", "TRAIN") and f"{v}_PT" in c.index else None)
            cs = [cell(c.loc[key(m), "coef"], c.loc[key(m), "t"]) if key(m) else ("", "") for m, _ in MODES]
            if v == "lic" and not cs[0][0]: cs[0] = ("0", "{\\scriptsize normalised}")
            if any(a for a, _ in cs):
                if v == "core_d": body.append(f"    Suburban (reference) & \\multicolumn{{5}}{{l}}{{reference}} \\\\")
                body += [f"    {lab} & " + " & ".join(a for a, _ in cs) + " \\\\", "     & " + " & ".join(b for _, b in cs) + " \\\\"]
        if body: rows += [f"    \\multicolumn{{6}}{{@{{}}l}}{{\\emph{{{g}}}}} \\\\"] + body
    los = {"work": "generalised cost $GC = T + 60\\,C / VOT$ (minutes), $VOT$ = 0.5 $\\times$ household income / 2,080\\,h; choice-based sample weights (ACS commute shares)",
           "shopping": "travel time and cost separately", "other": "travel time and cost separately; nested logit with car driver and passenger in one nest and bus and train in another (nest parameters $\\mu \\geq 1$)",
           "school": "round-trip distance on every mode (travel time is not significant for school tours); bus and train share the person and household coefficients (one value shown in both columns)",
           "shopping_joint": "travel time and cost separately; one observation per joint household group, variables of the group's representative (the oldest member with car driver available); car driver when a member drove; modes chosen by fewer than 20 groups have only the constant (train: not chosen, not available)",
           "other_joint": "travel time and cost separately; nested logit as for individual other tours; one observation per joint household group, variables of the group's representative (the oldest member with car driver available); car driver when a member drove; modes chosen by fewer than 20 groups have only the constant"}[seg]
    head = rf"""{{\footnotesize\setlength{{\tabcolsep}}{{3pt}}\nolinenumbers
\begin{{longtable}}{{@{{}}L{{0.27\linewidth}}lllll@{{}}}}
  \caption{{Tour mode choice, {TITLE[seg]} tours; reference mode: car driver.}}
  \label{{tab:est_mc_{seg}}}\\
  \toprule
  Variable & {" & ".join(l for _, l in MODES)} \\
  \midrule
  \endfirsthead
  \toprule
  Variable & {" & ".join(l for _, l in MODES)} \\
  \midrule
  \endhead
  \bottomrule
  \endlastfoot
"""
    foot = [r"    \midrule",
            f"    \\multicolumn{{6}}{{@{{}}p{{0.98\\linewidth}}}}{{Observations: {N[seg]:,} {"joint groups" if seg.endswith("_joint") else "tours"} (estimation half of the Regional Travel Survey 2017/18); alternatives: 6; parameters: {int(fit.K)}; LL = {fit.LL:,.1f}; BIC = {fit.BIC:,.1f}; validation half: LL = {fit.holdout_LL:,.1f}.}} \\\\".replace("-", "$-$"),
            f"    \\multicolumn{{6}}{{@{{}}p{{0.98\\linewidth}}}}{{Level of service: {los}. Times and costs of the round trip. Core city and rural: area type of the zone of the main activity.}} \\\\",
            r"    \multicolumn{6}{@{}p{0.98\linewidth}}{Coefficient with stars; below it the robust standard error in brackets and $p$ (nest parameters: $p$ against 1). $^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$.} \\",
            r"\end{longtable}", r"\linenumbers}"]
    open(f"{HERE}/est_mc_{seg}_new.tex", "w").write(head + "\n".join(rows) + "\n" + "\n".join(foot) + "\n")


def main():
    C = pd.read_csv(f"{HERE}/m08_coef.csv"); F = pd.read_csv(f"{HERE}/m08_fit.csv")
    C = pd.concat([C[C.segment != "school"], pd.read_csv(f"{HERE}/m09_coef.csv")]); F = pd.concat([F[F.segment != "school"], pd.read_csv(f"{HERE}/m09_fit.csv").assign(segment="school")])
    for seg in N:
        c = C[(C.segment == seg) & (C.step == "final")].set_index("param"); fit = F[(F.segment == seg) & (F.step == "final")].iloc[0]
        table(seg, c, fit); print(seg, len(c), int(fit.K))
    # group-level models of the joint household tours (m11_joint_group.py): one file with both tables
    J = pd.read_csv(f"{HERE}/m11_joint_coef.csv"); FJ = pd.read_csv(f"{HERE}/m11_joint_fit.csv"); parts = []
    for seg in ["shopping_joint", "other_joint"]:
        fit = FJ[FJ.segment == seg].iloc[0]; N[seg] = int(fit.N)
        table(seg, J[J.segment == seg].set_index("param"), fit); parts.append(open(f"{HERE}/est_mc_{seg}_new.tex").read())
    open(f"{HERE}/est_mc_joint_new.tex", "w").write("\n".join(parts)); print("joint tables written")


if __name__ == "__main__":
    main()
