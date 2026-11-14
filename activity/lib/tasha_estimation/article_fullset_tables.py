#!/usr/bin/env python3
"""Article estimation tables from the full-choice-set estimates (2026-11-04): rewrites the coefficient rows and the fit lines of
sections/est/est_dc_<P>_primary.tex, est_stop_<P>_stop.tex, est_loc_<seg>.tex and the outing-destination table in est_subtour.tex
with results/fullset_estimates_taz.csv and results/fullset_loc_estimates.csv (estimate_fullset_taz.py, estimate_fullset_loc.py).
Row order of every table = parameter order of the estimates (as article_dc_taz.py); the labels are kept.

    python3 activity/lib/tasha_estimation/article_fullset_tables.py
"""
import os
import numpy as np
import pandas as pd
from article_dc_taz import m, star, pval, EST, RES, DISC

STARS = "$^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$ (robust $t$)."
LOC = {"WORK_wbwork": "est_loc_wbwork", "WORK_wbhome": "est_loc_wbhome", "WORK_wahb": "est_loc_wahb", "EDUCATION_nonstud": "est_loc_nonstud",
       "EDUCATION_daycare": "est_loc_daycare"}


def is_row(l):
    return l.startswith("    ") and l.rstrip().endswith("\\\\") and " & " in l and "multicolumn" not in l and "Coefficient &" not in l


def rewrite(lines, t, stats):
    """lines of one table; t = estimates in parameter order; stats = lines of the fit block (multicolumn rows)."""
    rows_i = [i for i, l in enumerate(lines) if is_row(l)]
    if len(rows_i) != len(t): raise SystemExit(f"{len(rows_i)} rows in the table, {len(t)} estimates")
    for i, r in zip(rows_i, t.itertuples()):
        lab = lines[i].split(" & ")[0]
        lines[i] = f"{lab} & {m(r.value, 4)}{star(r.rob_t)} & {r.rob_se:.4f} & {m(r.rob_t, 2)} & {pval(r.rob_t)} \\\\"
    head = "    \\multicolumn{5}{@{}L{0.98\\linewidth}}{"
    mc = [i for i, l in enumerate(lines) if l.startswith(head)]
    txt = {i: lines[i][len(head):] for i in mc}
    obs, ll, note, stars = [f"{head}{x}}} \\\\" for x in stats]
    out, done_note = [], False
    for i, l in enumerate(lines):
        if i in txt:
            t = txt[i]
            if t.startswith("Observations"): out.append(obs); continue
            if t.startswith("LL(0)"): out.append(ll); continue
            if t.startswith("Full choice set: mean distance"): continue          # computed with the sampled-set estimates
            if t.startswith("Estimation: maximum likelihood"): out.append(note); done_note = True; continue
            if t.startswith("$^{***}$") and not done_note: out.append(note); done_note = True
        out.append(l)
    return out


def fit_lines(t, extra_note):
    N, K, L, L0 = int(t.N.iloc[0]), int(t.K.iloc[0]), float(t.LL.iloc[0]), float(t.LL0.iloc[0])
    mu = t.set_index("param").loc["mu_size"]; tmu = (mu.value - 1) / mu.rob_se
    note = ("Estimation: maximum likelihood on the full choice set, PyTorch implementation, robust sandwich covariance, unweighted." + extra_note
            + " Size term $\\mu\\ln(1+S_j)$ with the size weights $\\exp(\\theta)$ relative to the base component;"
            f" $\\mu=1$ is {'rejected' if abs(tmu) > 1.96 else 'not rejected'} (Wald $t$ = {m(tmu, 2)}).")
    return [f"Observations: {N:,}; alternatives: 1,588 zones (full choice set); parameters: {K}.",
            f"LL(0) = {m(L0, 1)}; LL($\\hat\\beta$) = {m(L, 1)}; $\\rho^2$ = {1 - L / L0:.3f}; adjusted $\\rho^2$ = {1 - (L - K) / L0:.3f}; "
            f"AIC = {m(2 * K - 2 * L, 1)}; BIC = {m(np.log(N) * K - 2 * L, 1)}.", note, STARS]


def main():
    E = pd.read_csv(f"{RES}/fullset_estimates_taz.csv")
    mix = (" Locations: the survey's traffic zones, spread over the model zones by housing units (home ends) or jobs (activity ends);"
           " the likelihood is averaged over the possible zones of the destination and of the anchors (location mixture).")
    for kind in ["primary", "stop"]:
        for p in DISC:
            seg = f"{p}_{kind}"; fn = f"{EST}/est_dc_{seg}.tex" if kind == "primary" else f"{EST}/est_stop_{seg}.tex"
            t = E[E.segment == seg].reset_index(drop=True)
            txt = "\n".join(rewrite(open(fn).read().split("\n"), t, fit_lines(t, mix))); open(fn, "w").write(txt)
            print(seg, "rows", len(t))
    L_ = pd.read_csv(f"{RES}/fullset_loc_estimates.csv")
    tract = " Destinations: the survey's census tract, matched to the model zones by the area of their overlap."
    for seg, f in LOC.items():
        fn = f"{EST}/{f}.tex"; t = L_[L_.segment == seg].reset_index(drop=True)
        txt = "\n".join(rewrite(open(fn).read().split("\n"), t, fit_lines(t, tract))); open(fn, "w").write(txt); print(seg, "rows", len(t))
    # outing destination: second longtable of est_subtour.tex
    fn = f"{EST}/est_subtour.tex"; s = open(fn).read(); k = s.index("\\label{tab:est_subtour_dest}"); a = s.rfind("{\\footnotesize", 0, k)
    t = L_[L_.segment == "OTHER_wbs"].reset_index(drop=True)
    b = s.index("\\end{longtable}", k)
    part = "\n".join(rewrite(s[a:b].split("\n"), t, fit_lines(t, tract))); open(fn, "w").write(s[:a] + part + s[b:]); print("OTHER_wbs rows", len(t))


if __name__ == "__main__":
    main()
