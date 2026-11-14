#!/usr/bin/env python3
"""LaTeX tables of the tour mode choice for the article (5_reports/article/sections/est/ and sections/) from results/.

    python3 activity/lib/mode_choice/report_tables.py
Writes: est/est_mc_<segment>.tex (one estimation table per segment, the standard format of the other estimation tables),
tab_mc_fit.tex (structures and tests), tab_mc_vot.tex (VOT rule by income and the sensitivity of the fit),
tab_mc_elast.tex (aggregate elasticities against the literature), tab_mc_tasha.tex (TASHA mode-choice features followed),
tab_mc_val.tex (tour mode shares, observed-tour validation and chain test)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/mode_choice"; RES = f"{HERE}/results"
V = WORKSPACE; ART = f"{V}/5_reports/article/sections"
CHOSEN = {"work": "nl_dest_gen", "school": "mnl", "shopping": "mnl_gen", "other": "nl_dest_gen"}
SEGW = {"work": "work", "school": "school", "shopping": "shopping", "other": "other (incl. recreation and accompanying)"}
MODEW = {"CD": "car driver", "WK": "walk", "BK": "bike", "CP": "car passenger", "BUS": "bus", "TRAIN": "train"}
VARW = {"ASC": "Constant", "age": "Age (years)", "male": "Male", "lic": "Driving licence", "hhsize": "Household size", "autos": "Household cars",
        "core_o": "Home zone core city", "rural_o": "Home zone rural", "core_d": "Main-activity zone core city", "rural_d": "Main-activity zone rural",
        "km": "Tour length (km, round trip)", "gc": "Generalised cost (min)"}
STRW = {"mnl": "multinomial logit", "nl": "nested logit", "mnl_dest": "multinomial logit, area type at both ends", "nl_dest": "nested logit, area type at both ends",
        "mnl_gen": "multinomial logit, generic GC", "nl_gen": "nested logit, generic GC", "mnl_dest_gen": "multinomial logit, generic GC, area type at both ends",
        "nl_dest_gen": "nested logit, generic GC, area type at both ends"}


def star(p):  # significance stars (two-sided p): *** <0.01, ** <0.05, * <0.10; fixed-width via phantom so columns stay aligned
    n = 3 if p < 0.01 else 2 if p < 0.05 else 1 if p < 0.10 else 0
    return "$^{" + "*" * n + ("\\phantom{" + "*" * (3 - n) + "}" if n < 3 else "") + "}$"
STARNOTE = "$^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$ (robust $t$)."
def num(x, d=4):
    s = f"{x:,.{d}f}"
    return s.replace("-", "$-$")


def p_(p): return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def est_table(seg):
    m = CHOSEN[seg]; t = pd.read_csv(f"{RES}/gc_{seg}_{m}.csv").set_index("Name"); S = pd.read_csv(f"{RES}/gc_summary.csv")
    st = S[(S.segment == seg) & (S.model == m)].iloc[0]
    rows = []
    def row(lab, k):
        r = t.loc[k]; rows.append(f"    {lab} & {num(r.Value)}{star(r['Robust p-value'])} & {r['Robust std err.']:.4f} & {num(r['Robust t-stat.'], 2)} & {p_(r['Robust p-value'])} \\\\")
    gen = [k for k in t.index if k == "gc" or k.startswith("gc_") or k.startswith("mu_")]
    rows.append("    \\multicolumn{5}{@{}l}{\\emph{Generalised cost and nests}} \\\\")
    for k in gen:
        lab = ("Generalised cost (min), all motorised modes" if k == "gc" else f"Generalised cost (min), {MODEW[k[3:]]}") if k.startswith("gc") else f"Nest parameter $\\mu$, {dict(auto='auto', transit='transit', nonmot='non-motorised')[k[3:]]}"
        row(lab, k)
    for a in ["CP", "BUS", "TRAIN", "WK", "BK"]:
        ks = [k for k in t.index if k.endswith(f"_{a}") and not k.startswith("gc_")]
        if not ks: continue
        rows.append(f"    \\multicolumn{{5}}{{@{{}}l}}{{\\emph{{{MODEW[a].capitalize()} (reference: car driver)}}}} \\\\")
        order = ["ASC", "age", "male", "lic", "hhsize", "autos", "core_o", "rural_o", "core_d", "rural_d", "km"]
        for v in order:
            k = f"{v}_{a}"
            if k in t.index: row(VARW[v], k)
    alts = 6
    body = "\n".join(rows)
    fit = (f"Observations: {int(st.N):,}; alternatives: {alts}; parameters: {int(st.K)}. LL(0) = {num(st.LL0, 1)}; LL(constants) = {num(st.LLc, 1)}; "
           f"LL($\\hat\\beta$) = {num(st.LL, 1)}; $\\rho^2$ = {st.rho2_0:.3f} (against constants {st.rho2_c:.3f}); adjusted $\\rho^2$ = {st.rho2bar_0:.3f}; AIC = {st.AIC:,.1f}; BIC = {st.BIC:,.1f}.")
    note = ("Generalised cost $GC_m = T_m + 60\\,C_m / VOT_h$ (minutes), $VOT_h = 0.5 \\times$ household income / 2,080\\,h (USDOT 2016 guidance); "
            "round trip by period. Estimation: maximum likelihood in Biogeme 3.3.5 without survey weights (exogenous sampling of households); robust (sandwich) standard errors."
            + (" Nests: auto (car driver, car passenger), transit (bus, train), non-motorised (walk, bike); $\\mu \\geq 1$ (1 = no nesting; a value of 1.000 is on the bound)." if m.startswith("nl") else ""))
    cap = (f"Tour mode choice, {SEGW[seg]} tours ({STRW[m]}). Dependent variable: main mode of the home-based tour (estimation half of the Regional Travel Survey).")
    hdr = "  \\toprule\n  Variable & Coefficient & Robust s.e. & Robust $t$ & $p$ \\\\\n  \\midrule\n"
    tex = (f"{{\\footnotesize\\setlength{{\\tabcolsep}}{{4pt}}\\nolinenumbers\n\\begin{{longtable}}{{@{{}}L{{0.47\\linewidth}}rrrr@{{}}}}\n"
           f"  \\caption{{{cap}}}\n  \\label{{tab:est_mc_{seg}}}\\\\\n" + hdr + "  \\endfirsthead\n"
           "  \\multicolumn{5}{@{}l@{}}{\\footnotesize Table~\\thetable\\ (continued)}\\\\[2pt]\n" + hdr + "  \\endhead\n"
           "  \\midrule\n  \\multicolumn{5}{@{}r@{}}{\\emph{continued on the next page}} \\\\\n  \\endfoot\n  \\bottomrule\n  \\endlastfoot\n\n"
           f"{body}\n    \\midrule\n    \\multicolumn{{5}}{{@{{}}L{{0.98\\linewidth}}}}{{{fit}}} \\\\\n"
           f"    \\multicolumn{{5}}{{@{{}}L{{0.98\\linewidth}}}}{{{note}}} \\\\\n    \\multicolumn{{5}}{{@{{}}L{{0.98\\linewidth}}}}{{{STARNOTE}}} \\\\\n\\end{{longtable}}\n\\linenumbers}}\n")
    open(f"{ART}/est/est_mc_{seg}.tex", "w").write(tex)


def fit_table():
    S = pd.read_csv(f"{RES}/gc_summary.csv"); T = pd.read_csv(f"{RES}/gc_tests.csv")
    rows = []
    for seg in ["work", "school", "shopping", "other"]:
        for m in ["mnl", "nl", "mnl_dest", "nl_dest", "mnl_gen", "nl_gen", "mnl_dest_gen", "nl_dest_gen"]:
            r = S[(S.segment == seg) & (S.model == m)]
            if not len(r): continue
            r = r.iloc[0]; mark = " $\\ast$" if CHOSEN[seg] == m else ""
            rows.append(f"    {seg.capitalize() if m == 'mnl' else ''} & {STRW[m]}{mark} & {int(r.K)} & {num(r.LL, 1)} & {r.rho2_c:.3f} & {r.AIC:,.1f} \\\\")
        rows.append("    \\addlinespace")
    tr = []
    for r in T.itertuples():
        tt = r.test
        for k in sorted(STRW, key=len, reverse=True): tt = tt.replace(f"({k})", f"({STRW[k]})")
        tt = tt.replace("_", " ").replace("(MNL", "(multinomial logit").replace("MNL", "multinomial logit").replace("NL", "nested logit").replace("GC", "cost")
        tr.append(f"    {r.segment.capitalize()} & {tt} & {r.LR:,.1f} & {int(r.df)} & {p_(r.p) if np.isfinite(r.p) and r.df > 0 else '--'} \\\\")
    tex = f"""\\begin{{table}}[!tbp]
  \\centering
  \\caption{{Tour mode choice: structures estimated per segment and tests (estimation half). $\\ast$: model of record (lowest AIC among the models with no significantly positive cost coefficient and interior nest parameters).}}
  \\label{{tab:mc_fit}}
  \\footnotesize\\setlength{{\\tabcolsep}}{{4pt}}
  \\begin{{tabular}}{{@{{}}lL{{0.47\\linewidth}}rrrr@{{}}}}
    \\toprule
    Segment & Structure & $K$ & LL($\\hat\\beta$) & $\\rho^2$, constants & AIC \\\\
    \\midrule
{chr(10).join(rows)}
    \\bottomrule
  \\end{{tabular}}

  \\vspace{{6pt}}
  \\begin{{tabular}}{{@{{}}lL{{0.62\\linewidth}}rrr@{{}}}}
    \\toprule
    Segment & Likelihood-ratio test & LR & df & $p$ \\\\
    \\midrule
{chr(10).join(tr)}
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
"""
    open(f"{ART}/tab_mc_fit.tex", "w").write(tex)


def vot_table():
    S = pd.read_csv(f"{RES}/gc_summary.csv"); rows = []
    for inc in [25000, 50000, 84216, 150000]:
        rows.append(f"    \\${inc:,} & {0.35 * inc / 2080:.2f} & {0.5 * inc / 2080:.2f} & {0.7 * inc / 2080:.2f} \\\\")
    srows = []
    for seg in ["work", "school", "shopping", "other"]:
        m = CHOSEN[seg]; ll = [S[(S.segment == seg) & (S.model == x)].LL.iloc[0] for x in [f"{m}_s35", m, f"{m}_s70"]]
        t = {s: pd.read_csv(f"{RES}/gc_{seg}_{x}.csv").set_index("Name") for s, x in [("35", f"{m}_s35"), ("50", m), ("70", f"{m}_s70")]}
        k = "gc" if "gc" in t["50"].index else "gc_CD"
        g = " / ".join(f"{num(t[s].loc[k].Value)} ({num(t[s].loc[k]['Robust t-stat.'], 1)})" for s in ["35", "50", "70"])
        srows.append(f"    {seg.capitalize()} & {num(ll[0], 1)} & {num(ll[1], 1)} & {num(ll[2], 1)} & {g} \\\\")
    tc = pd.read_csv(f"{RES}/timecost_cost.csv") if os.path.exists(f"{RES}/timecost_cost.csv") else None
    tcr = "" if tc is None else " ".join(f"{r.segment} {num(r.b_cost)} ($t$ = {num(r.t, 1)});" for r in tc.itertuples())
    tex = f"""\\begin{{table}}[!tbp]
  \\centering
  \\caption{{Value of time in the generalised cost: the USDOT rule for local personal travel (50\\% of the hourly household income) and the sensitivity cases of 35\\% and 70\\% (2017 dollars per hour), and the fit of the models of record with each value. The value of time is not estimated: in the specification with separate time and cost terms the cost coefficient is positive in every segment ({tcr} car operating cost tracks car time, $r = 0.94$, and the survey records no parking or toll amounts).}}
  \\label{{tab:mc_vot}}
  \\footnotesize\\setlength{{\\tabcolsep}}{{5pt}}
  \\begin{{tabular}}{{@{{}}lrrr@{{}}}}
    \\toprule
    Household income (per year) & 35\\% & 50\\% (USDOT) & 70\\% \\\\
    \\midrule
{chr(10).join(rows)}
    \\bottomrule
  \\end{{tabular}}

  \\vspace{{6pt}}
  \\begin{{tabular}}{{@{{}}lrrrl@{{}}}}
    \\toprule
    Segment & LL, 35\\% & LL, 50\\% & LL, 70\\% & Cost coefficient ($t$), 35 / 50 / 70\\% \\\\
    \\midrule
{chr(10).join(srows)}
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
"""
    open(f"{ART}/tab_mc_vot.tex", "w").write(tex)


def elast_table():
    e = pd.read_csv(f"{RES}/elasticities.csv"); e = e[e.segment == "all"].pivot(index="variable", columns="alt", values="elasticity")
    order = [("car time", "Car travel time", "CD", "--"), ("car operating cost", "Car operating cost", "CD", "$-0.1$ short run, $-0.3$ long run (car traffic, fuel price) [b]"),
             ("transit time", "Transit door-to-door time", None, "--"), ("transit fare", "Transit fare", None, "$-0.3$ to $-0.4$ (fare) [c]")]
    rows = []
    for k, lab, _, lit in order:
        r = e.loc[k]
        rows.append(f"    {lab} & {num(r.CD, 3)} & {num(r.CP, 3)} & {num(r.BUS, 3)} & {num(r.TRAIN, 3)} & {num(r.WK, 3)} & {num(r.BK, 3)} & {lit} \\\\")
    tex = f"""\\begin{{table}}[!tbp]
  \\centering
  \\caption{{Aggregate elasticities of the tour mode shares (sample enumeration on the observed tours of the estimation half, survey weights, a 1\\% increase of the variable for every tour), against ranges reported in the literature.}}
  \\label{{tab:mc_elast}}
  \\footnotesize\\setlength{{\\tabcolsep}}{{2.5pt}}
  \\begin{{tabular}}{{@{{}}L{{0.17\\linewidth}}rrrrrrL{{0.25\\linewidth}}@{{}}}}
    \\toprule
    Variable & \\begin{{tabular}}[b]{{@{{}}r@{{}}}}Car\\\\driver\\end{{tabular}} & \\begin{{tabular}}[b]{{@{{}}r@{{}}}}Car\\\\passenger\\end{{tabular}} & Bus & Train & Walk & Bike & Literature (own elasticity) \\\\
    \\midrule
{chr(10).join(rows)}
    \\bottomrule
  \\end{{tabular}}

  \\parbox{{\\linewidth}}{{\\footnotesize\\vspace{{3pt}}[b]\\,\\citet{{Goodwin2004}}; [c]\\,\\citet{{Litman2004}}.}}
\\end{{table}}
"""
    open(f"{ART}/tab_mc_elast.tex", "w").write(tex)


def tasha_table():
    rows = [("Tour-based mode: one main mode per home-based tour, stops inherit it", "followed", "the hierarchy transit $>$ car driver $>$ car passenger $>$ bike $>$ walk defines the survey tour mode"),
            ("Mode chosen given the tour's destination, timing and stops", "followed", "level of service of the round trip by the periods of the main activity's start and end"),
            ("Car consistency: a car-driver tour keeps the car from leaving home to returning", "followed", "all legs of a tour take the tour mode"),
            ("Household vehicle allocation among overlapping car-driver tours", "followed", "cars go to the tours with the largest utility advantage of car driver; the others take the next choice without car driver"),
            ("Joint activities travel together", "followed", "one mode from the summed utilities of the participants, one participant drives"),
            ("Within-household ride sharing (who drives whom; serve-passenger episodes)", "not modelled", "car passenger is a person-level alternative \\citep{Roorda2006}"),
            ("Drive-access transit with station choice", "approximated", "drive access is part of the train alternative (raptor search within 15 km of home), no station choice"),
            ("Estimation of the person-level model", "different", "maximum likelihood (Biogeme) per segment; TASHA's household-level estimation uses a genetic algorithm \\citep{Roorda2006}")]
    body = "\n".join(f"    {a} & {b} & {c} \\\\" for a, b, c in rows)
    tex = f"""\\begin{{table}}[!tbp]
  \\centering
  \\caption{{Features of the TASHA tour mode choice \\citep{{Miller2005,Roorda2006}} and their treatment in \\abit{{}}.}}
  \\label{{tab:mc_tasha}}
  \\footnotesize\\setlength{{\\tabcolsep}}{{4pt}}
  \\begin{{tabular}}{{@{{}}L{{0.38\\linewidth}}lL{{0.43\\linewidth}}@{{}}}}
    \\toprule
    TASHA feature & In \\abit{{}} & Treatment \\\\
    \\midrule
{body}
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
"""
    open(f"{ART}/tab_mc_tasha.tex", "w").write(tex)


def val_table():
    o = pd.read_csv(f"{RES}/obs_validation.csv"); a = pd.read_csv(f"{RES}/abit_mode_validation.csv") if os.path.exists(f"{RES}/abit_mode_validation.csv") else None
    M6 = ["CAR_DRIVER", "CAR_PASSENGER", "BUS", "TRAIN", "WALK", "BIKE"]; PL = {"WORK": "Work", "EDUCATION": "School", "SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompany", "OTHER": "Other", "all": "All tours"}
    rows = []
    blocks = [("Verification, observed tours (estimation half)", o[(o.setting == "verification") & (o.variant == "behavioural")]),
              ("Validation, observed tours (held-out half)", o[(o.setting == "validation") & (o.variant == "behavioural")])]
    if a is not None:
        blocks += [("Validation, \\abit{} tours (held-out half)", a[(a.setting == "validation") & (a.variant == "behav")]), ("Chain test, synthetic population", a[(a.setting == "chain") & (a.variant == "behav")])]
    for title, d in blocks:
        rows.append(f"    \\multicolumn{{7}}{{@{{}}l}}{{\\emph{{{title}}}}} \\\\")
        for g in ["WORK", "EDUCATION", "SHOPPING", "RECREATION", "ACCOMPANY", "OTHER", "all"]:
            x = d[(d.group == g) & d.dim.isin(["purpose", "all"])].set_index("mode")
            if not len(x): continue
            cells = " & ".join(f"{100 * x.loc[m].model:.1f} ({100 * x.loc[m].observed:.1f})" for m in M6)
            rows.append(f"    {PL[g]} & {cells} \\\\")
    tex = f"""\\begin{{table}}[!tbp]
  \\centering
  \\caption{{Tour mode share comparison, \\abit{{}} vs RTS, by activity purpose of the main activity (\\%; model mean of 10 replications, observed in parentheses; behavioural model, no calibration). Observed tours: each survey tour with its observed destination, timing and stops, mode choice alone; \\abit{{}} tours: the tours \\abit{{}} generates for the observed (held-out) or the synthetic population.}}
  \\label{{tab:mc_val}}
  \\footnotesize\\setlength{{\\tabcolsep}}{{3pt}}
  \\begin{{tabular}}{{@{{}}lrrrrrr@{{}}}}
    \\toprule
    Purpose & Car driver & Car passenger & Bus & Train & Walk & Bike \\\\
    \\midrule
{chr(10).join(rows)}
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
"""
    open(f"{ART}/tab_mc_val.tex", "w").write(tex)


if __name__ == "__main__":
    for s in CHOSEN: est_table(s)
    fit_table(); vot_table(); elast_table(); tasha_table(); val_table(); print("tables written to", ART)
