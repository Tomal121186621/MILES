#!/usr/bin/env python3
"""Article estimation tables of the residential location levels and the car-ownership model, written from the estimation outputs
(2026-10-27, income groups 40/75/125k): 5_reports/article/sections/est/est_{region,zone,dwelling,cars}.tex.  Layout and wording are
those of the earlier tables (kept as est_<name>_inc3060.tex.bak, used as templates): every coefficient row is refilled from
tables/region_R8c_final.csv, zone_final_final.csv, dwelling_final_numpy.csv, car_ownership_estimates.csv, the fit lines from the
specification-search tables, car_ownership_estimates_fit.csv and biogeme_summary.csv.  Usage: python3 landuse/lib/residential/s12_article_tables.py"""
import re, numpy as np, pandas as pd
from scipy.stats import norm
from rc import *
EST = f"{V}/5_reports/article/sections/est"
GRP = {"very high income": "VERY_HIGH", "medium income": "MEDIUM", "high income": "HIGH", "low income": "LOW"}   # 'very high' before 'high'
NEWLAB = {"LOW": "income under \\$40k", "MEDIUM": "income \\$40--75k", "HIGH": "income \\$75--125k", "VERY_HIGH": "income \\$125k or more"}
num = lambda x, d=4: f"{x:,.{d}f}".replace("-", "$-$")
def star(p):  # significance stars (two-sided p): *** <0.01, ** <0.05, * <0.10; fixed-width via phantom so columns stay aligned
    n = 3 if p < 0.01 else 2 if p < 0.05 else 1 if p < 0.10 else 0
    return "$^{" + "*" * n + ("\\phantom{" + "*" * (3 - n) + "}" if n < 3 else "") + "}$"
STARNOTE = "$^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$ (robust $t$)."
def pstr(t):
    if not np.isfinite(t): return "--"
    p = 2 * norm.sf(abs(t)); return "$<$0.001" if p < 0.001 else f"{p:.3f}"
def row(label, est, se, fixed=False):
    if fixed or not np.isfinite(se) or se == 0: return f"    {label} & {num(est)}$^{{\\phantom{{***}}}}$ & \\multicolumn{{3}}{{c}}{{fixed}} \\\\"
    return f"    {label} & {num(est)}{star(2 * norm.sf(abs(est / se)))} & {num(se)} & {num(est / se, 2)} & {pstr(est / se)} \\\\"
def relabel(lab):
    for k, g in GRP.items():
        if lab.endswith(", " + k) or (", " + k + " ") in lab: return lab.replace(k, NEWLAB[g]), g
    return lab, None
def split_rows(tex):
    lines = tex.split("\n"); out = []
    for i, l in enumerate(lines):
        if l.strip().endswith("\\\\") and l.count("&") == 4 and not l.strip().startswith(("Variable", "\\multicolumn")): out.append(i)
    return lines, out
def fill(name, params, footer):
    tex = open(f"{EST}/est_{name}_inc3060.tex.bak").read(); lines, idx = split_rows(tex)
    assert len(idx) == len(params), (name, len(idx), len(params))
    for i, (p, est, se, fx) in zip(idx, params):
        if p is None: lines[i] = None; continue   # row dropped (pooled into the previous one)
        lab = lines[i].split("&")[0].strip(); lab = lab.replace(" (fixed at 1)", ""); lab, g = relabel(lab)
        if p.endswith("_TOP"): lab = lab.replace(NEWLAB["HIGH"], "income \\$75k or more (one slope)")
        lines[i] = row(lab + (" (fixed at 1)" if fx else ""), est, se, fx)
    mc = [i for i, l in enumerate(lines) if l is not None and l.strip().startswith("\\multicolumn{5}{@{}L{0.98\\linewidth}}")]
    for i, txt in zip(mc, footer): lines[i] = "    \\multicolumn{5}{@{}L{0.98\\linewidth}}{" + txt + "} \\\\"
    open(f"{EST}/est_{name}.tex", "w").write("\n".join(l for l in lines if l is not None)); print("wrote", name)
def fitline(r, llc="n/a"):
    return (f"LL(0) = {num(r.LL0, 1)}; LL(constants) = {llc}; LL($\\hat\\beta$) = {num(r.LL, 1)}; $\\rho^2$ = {r.rho2:.3f}; "
            f"adjusted $\\rho^2$ = {r.rho2_adj:.3f}; AIC = {r.AIC:,.1f}; BIC = {r.BIC:,.1f}.")
B = pd.read_csv(f"{TAB}/biogeme_summary.csv").set_index("model")
def bg(m):
    d = B.loc[m, "LL_numpy"] - B.loc[m, "LL_biogeme"]
    s = f"cross-checked with Biogeme 3.3.5 on the final data, started from these estimates (log-likelihood difference {abs(d):.2g}; largest coefficient difference {B.loc[m, 'max_abs_diff']:.2g})"
    return s + (" -- Biogeme's optimizer stopped below this maximum" if d > 0.05 else "")
GROUPS = "Income groups (2016 \\$, household income): under \\$40k, \\$40--75k, \\$75--125k, \\$125k or more (rounded quartiles of the 2016 Maryland households)."
# ---- region (county): template order = parameter base x group L, M, H, VH, then the generic terms
R = pd.read_csv(f"{TAB}/region_R8c_final.csv").set_index("parameter"); order = []
for b in ["d1", "d2", "d3", "same_region", "IV_B", "IV_A", "commute_log"]:
    for g in ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]: order.append(f"{b}_{g}")
order += ["same_state", "commute_log_x_inc", "school", "school_x_child", "crime", "crime_x_child"]
par = [(p, R.loc[p, "estimate"], R.loc[p, "robust_se"], str(R.loc[p, "fixed"]) == "True") for p in order]
S = pd.read_csv(f"{TAB}/region_specification_search_final.csv"); r = S[S.model.str.startswith("R8c")].iloc[0]
fx = [p for p in order if str(R.loc[p, "fixed"]) == "True"]; gl = {"LOW": "under \\$40k", "MEDIUM": "\\$40--75k", "HIGH": "\\$75--125k", "VERY_HIGH": "\\$125k or more"}
fill("region", par, [f"Observations: {int(r.N):,}; alternatives: all 44 counties (no sampling); parameters: {int(r.K)}.", fitline(r),
     f"Estimation: own maximum-likelihood code (BFGS, then Newton; robust sandwich covariance); {bg('region_R8c')}. {GROUPS} $\\lambda_A$ of the groups "
     + ", ".join(gl[p.split('IV_A_')[1]] for p in fx) + f" is fixed at 1 (free estimates above 1; LR {r.LR:.1f} on {int(r.df)} df)."])
# ---- zone x dwelling type
Zt = pd.read_csv(f"{TAB}/zone_final_final.csv"); S = pd.read_csv(f"{TAB}/zone_specification_search_final.csv"); r = S[S.model.str.startswith("Z7")].iloc[0]
fill("zone", [(x.parameter, x.estimate, x.robust_se, False) for x in Zt.itertuples()],
     [f"Observations: {int(r.N):,}; alternatives: 30 (chosen + 29 uniformly sampled; no correction needed); parameters: {int(r.K)}.", fitline(r),
      f"Estimation: own maximum-likelihood code (BFGS, then Newton; robust sandwich covariance); {bg('zone_Z7')}. WESML weights; robust standard errors with squared weights."])
# ---- dwelling
Dt = pd.read_csv(f"{TAB}/dwelling_final_numpy.csv").set_index("parameter"); S = pd.read_csv(f"{TAB}/dwelling_specification_search.csv")
r = S[S.model.str.startswith("D4p")].iloc[0]; r4 = S[S.model.str.startswith("D4 ")].iloc[0]
from scipy.stats import chi2
lrp = 2 * (r4.LL - r.LL)
tmpl = pd.read_csv(f"{RL}/tables_inc3060/dwelling_final_numpy.csv").parameter.tolist()   # template row order
dpar = []
for p in tmpl:
    if p == "bur_hi_VERY_HIGH": dpar.append((None, 0, 0, False))
    elif p == "bur_hi_HIGH": dpar.append(("bur_hi_TOP", Dt.loc["bur_hi_TOP", "estimate"], Dt.loc["bur_hi_TOP", "robust_se"], False))
    else: dpar.append((p, Dt.loc[p, "estimate"], Dt.loc[p, "robust_se"], False))
fill("dwelling", dpar,
     [f"Observations: {int(r.N):,}; alternatives: 30 (chosen + 29 uniformly sampled); parameters: {int(r.K)}.", fitline(r),
      f"Estimation: own maximum-likelihood code (BFGS, then Newton; robust sandwich covariance); {bg('dwelling_D4')}. {GROUPS} The slope above 50 \\% is shared by the two upper groups (separate slopes: LR {lrp:.2f} on 1 df, $p$ = {chi2.sf(lrp, 1):.3f})."])
# ---- cars: per alternative asc, hhSize, workers, income_2..12, accLogsumGain
C = pd.read_csv(f"{TAB}/car_ownership_estimates.csv"); F = pd.read_csv(f"{TAB}/car_ownership_estimates_fit.csv").iloc[0]; par = []
for a in (1, 2, 3):
    c = C[C.alternative == a].set_index("variable")
    for v in ["asc", "hhSize", "workers"] + [f"income_{k}" for k in range(2, 13)] + ["accLogsumGain"]: par.append((v, c.loc[v, "estimate"], c.loc[v, "se"], False))
tex = open(f"{EST}/est_cars_inc3060.tex.bak").read().replace("Coefficients from the saved estimation; standard errors are saved for the accessibility-gain terms only.",
      "Weighted estimation on ACS PUMS Maryland households; the accessibility gain is that of the household's income group (2016 \\$: under \\$40k, \\$40--75k, \\$75--125k, \\$125k or more).")
open(f"{EST}/est_cars_inc3060.tex.tmp", "w").write(tex)
import shutil; shutil.copy(f"{EST}/est_cars_inc3060.tex.tmp", f"{EST}/est_cars_tmpl.tex.bak")
def fill_cars():
    lines, idx = split_rows(open(f"{EST}/est_cars_tmpl.tex.bak").read()); assert len(idx) == len(par)
    for i, (p, e, s, fx) in zip(idx, par): lines[i] = row(lines[i].split("&")[0].strip(), e, s)
    mc = [i for i, l in enumerate(lines) if l.strip().startswith("\\multicolumn{5}{@{}L{0.98\\linewidth}}")]
    foot = [f"Observations: {int(F.N):,} Maryland households (weighted 2,192,515; ACS PUMS 2014--2018); alternatives: 4 (0, 1, 2, 3 or more cars); parameters: {int(F.K)}.",
            f"LL(0) = {num(F.LL0, 1)}; LL(constants) = {num(F.LLc, 1)}; LL($\\hat\\beta$) = {num(F.LL, 1)}; $\\rho^2$ = {F.rho2:.3f}; $\\rho^2$ against constants = {F.rho2_c:.3f}; AIC = {F.AIC:,.1f}; BIC = {F.BIC:,.1f} (household weights, log-likelihoods rescaled to the number of households).",
            "Estimation: weighted multinomial logit (statsmodels, Newton); standard errors from the frequency-weight replication rescaled by $\\sqrt{10}$."]
    for i, txt in zip(mc, foot): lines[i] = "    \\multicolumn{5}{@{}L{0.98\\linewidth}}{" + txt + "} \\\\"
    open(f"{EST}/est_cars.tex", "w").write("\n".join(lines)); print("wrote cars")
fill_cars()
import os; os.remove(f"{EST}/est_cars_inc3060.tex.tmp"); os.remove(f"{EST}/est_cars_tmpl.tex.bak")
