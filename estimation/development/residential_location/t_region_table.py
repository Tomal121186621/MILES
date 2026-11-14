#!/usr/bin/env python3
"""Article-format table of the re-specified county model (r05_region_sequence.py, step 12): est_region_new.tex, same layout as
5_reports/article/sections/est/est_region.tex, terms grouped and income groups in ascending order."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
sys.dont_write_bytecode = True
import pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/residential"   # results of this step (data); CODE = this folder
sys.path.insert(0, os.path.join(os.path.dirname(CODE), "tables"))
import t_new_tables as T     # noqa: E402  (format helpers)
f = T.f
INC = [("LOW", "under \\$40k"), ("MEDIUM", "\\$40--75k"), ("HIGH", "\\$75--125k"), ("VERY_HIGH", "\\$125k or more")]
GROUPS = [("Car time to another county (per min)", [("d1", "under 20\\,min"), ("d2", "20--60\\,min"), ("d3", "over 60\\,min"),
                                                    ("d2_x_lninc", "20--60\\,min $\\times$ ln income"), ("d3_x_lninc", "over 60\\,min $\\times$ ln income")]),
          ("Staying near the origin", [("same_region", "Previous county"), ("adjacent", "County bordering the previous county"), ("same_state", "Same state as the origin")]),
          ("Inclusive values of the dwelling choice", [("IV_B", "Zone $\\times$ structure type, $\\lambda_B$"), ("IV_A", "Dwelling, $\\lambda_A$")]),
          ("Commute", [("commute_log", "Commute: $\\sum_{\\text{workers}} \\ln(1+t)$"), ("commute_log_x_inc", "Commute $\\times$ ln income")]),
          ("Age of the oldest member", [("same_x_age", "Previous county $\\times$ (age $-$ 50)/10"), ("d2_x_age", "Car time 20--60\\,min $\\times$ (age $-$ 50)/10"),
                                         ("same_x_hhs", "Previous county $\\times$ (household size $-$ 1)"), ("d2_x_hhs", "Car time 20--60\\,min $\\times$ (household size $-$ 1)")]),
          ("Schools and crime", [("growth", "School learning growth (SD per grade)"), ("crime_x_child", "Crime index $\\times$ children")])]


def main():
    F = pd.read_csv(f"{HERE}/r05_fit.csv"); s = F[F.final].iloc[0]
    c = pd.read_csv(f"{HERE}/r05_coef.csv"); c = c[c.step == s.step].set_index("parameter")
    fixed = [x for x in str(s.fixed_at_1).split(";") if x and x != "nan"]

    def row(lab, n):
        if n in fixed:
            return f"    {lab} & 1.0000 & \\multicolumn{{2}}{{c}}{{fixed}} \\\\"
        return T.coef_row(lab, c.estimate[n], c.robust_se[n])

    rows = []
    for g, terms in GROUPS:
        body = []
        for v, lab in terms:
            if v in c.index or v in fixed:
                body.append(row(lab, v))
            elif v == "d1":
                body.append(f"    {lab} & 0 & \\multicolumn{{2}}{{c}}{{fixed}} \\\\")
            elif any(f"{v}_{k}" in c.index for k, _ in INC):
                for k, il in INC:
                    body.append(row(f"{lab}, income {il}", f"{v}_{k}"))
        if body:
            rows += [f"    \\multicolumn{{4}}{{@{{}}l}}{{\\emph{{{g}}}}} \\\\"] + body
    shown = {v for _, t in GROUPS for v, _ in t}
    assert all(n in shown or any(n == f"{v}_{k}" for v in shown for k, _ in INC) for n in c.index), sorted(set(c.index) - shown)
    foot = [f"Observations: {int(s.N):,}; alternatives: all 44 counties (no sampling); parameters: {int(s.K)}.",
            f"LL(0) = {f(s.LL0, 1)}; LL($\\hat\\beta$) = {f(s.LL, 1)}; $\\rho^2$ = {s.rho2:.3f}; AIC = {f(s.AIC, 1)}; BIC = {f(s.BIC, 1)}.",
            f"Car time applies to counties other than the current one; it has no effect below 20\\,min. Commute $t$: peak car time (min) from the county (mean over its zones, weighted by dwellings) to the worker's workplace area, transit door-to-door time for households without a car. Previous county: share of the household's origin migration area (ACS) that lies in the county (in the simulation, 1 for the current county). Income: ln(household income / \\$50k), 2016 \\$. School learning growth: SEDA 4.1 county change in mean achievement per grade (grades 3--8, 2009--2018).",
            "Dependent variable: chosen county of ACS PUMS movers 2014--2018 (estimation sample)."]
    open(f"{HERE}/est_region_new.tex", "w").write(T.wrap("Residential location: county of moving households (44 counties).", "tab:est_region", rows, foot))
    print(int(s.K), s.LL, len(rows))


if __name__ == "__main__":
    main()
