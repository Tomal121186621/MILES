#!/usr/bin/env python3
"""Article-format tables of the final pooled location models: est_dc_pooled.tex (dp_pooled.py) and est_stop_pooled.tex
(sp_pooled.py).  Rows = variables grouped (labels of ../primary_destination/t_dest_primary.py and ../stop_location/s_tables.py), columns =
Shopping, Recreation, Accompanying, Other; a coefficient shared by every purpose that has it spans the four columns, a
coefficient shared by a subset is repeated in its columns with a letter; coefficient with robust t below.  Compile check with
the preamble of ../../final_tables/estimation_tables_abit.tex (tectonic): <prefix>check.tex.
    python3 estimation/development/primary_destination_pooled/t_pooled.py dp|sp"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, subprocess
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
from scipy.stats import norm

CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{ESTIMATION_RESULTS}/dest_pooled"; SBS = os.path.dirname(HERE)
DEV = os.path.dirname(CODE)
sys.path.insert(0, f"{DEV}/tables"); sys.path.insert(0, f"{DEV}/primary_destination"); sys.path.insert(0, f"{DEV}/stop_location")
import t_new_tables as T        # noqa: E402
PURP = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
COLS = ["Shopping", "Recreation", "Accompanying", "Other"]
WORD = {"SHOPPING": "shopping", "RECREATION": "recreation", "ACCOMPANY": "accompanying", "OTHER": "other"}
ABBR = {"S": "shopping", "R": "recreation", "A": "accompanying", "O": "other"}
COMP = {"pop": "population", "ret": "retail jobs", "off": "office jobs", "oth": "other jobs", "stu": "school enrolment"}


def fam(prefix):
    if prefix == "dp":
        import t_dest_primary as TD
        return dict(groups=TD.groups(), out="est_dc_pooled.tex", label="tab:est_dc_pooled", unit="tours",
                    caption="Discretionary primary destination, pooled model of shopping, recreation, accompanying and other tours with "
                            "purpose-specific scale (multinomial logit over 1,588 zones).",
                    est=TD.EST, defs=TD.DEFS.replace("; logsum: mode-choice logsum from home.", "."))
    import s_tables as TS
    return dict(groups=TS.GROUPS, out="est_stop_pooled.tex", label="tab:est_stop_pooled", unit="stops",
                caption="Stop location, pooled model of shopping, recreation, accompanying and other stops with purpose-specific scale "
                        "(multinomial logit over 1,588 zones, sequential anchors).",
                est=TS.EST,
                defs="Detour: $d(a,j) + d(j,b) - d(a,b)$ by car (km) between the origin $a$ of the trip to the stop and the next anchor $b$ "
                     "of the tour (the primary destination for an outbound stop, home for an inbound stop), piecewise linear with the slope "
                     "per km in each band; interactions with person, household, tour and arrival-time flags; land-use mix: entropy of the job "
                     "and population shares (0--1); car generalised time: car time plus cost over the household's value of time (min); "
                     "logsum: mode-choice logsum of the detour.")


def num(b):
    return T.f(b)


def tt(t, b=None):
    """robust s.e. in brackets and p (small); a parameter held on its bound (no s.e.) is marked"""
    if not np.isfinite(t): return "{\\scriptsize (bound)}"
    p = 2 * norm.sf(abs(t)); return f"{{\\scriptsize ({abs(b / t):.4f}) {T.pval(p)}}}"


def stars(t):
    if not np.isfinite(t): return ""
    p = 2 * norm.sf(abs(t)); return "$^{***}$" if p < 0.01 else "$^{**}$" if p < 0.05 else "$^{*}$" if p < 0.10 else ""


def main(prefix):
    F = fam(prefix); C = pd.read_csv(f"{HERE}/{prefix}_coef.csv"); fit = pd.read_csv(f"{HERE}/{prefix}_fit.csv")
    c = C[C.step == "final"]; fin = fit[fit.step == "final"].iloc[0]
    val = {(r.purpose, r.param): (r.coef, r.t) for r in c.itertuples()}
    letters, rows, used = {}, [], set()
    idx = set(c.param); held = {"d_50_inf": "distance $>$ 50\\,km"} if prefix == "dp" else {}
    for g, terms in F["groups"]:
        body = []
        for v, lab in terms:
            if isinstance(v, T.Ref):
                if v.present(idx): body.append(f"    {v.label(idx)} & \\multicolumn{{4}}{{c}}{{reference}} \\\\")
                continue
            if v in held and v not in idx:
                body.append(f"    {lab} & \\multicolumn{{4}}{{c}}{{0 (fixed)}} \\\\"); continue
            keys = {p: None for p in PURP}
            for (grp, par) in val:
                if par != v or grp == "scale": continue
                if grp == "shared": keys = {p: "shared" for p in PURP}
                elif grp in PURP: keys[grp] = grp
                else:
                    for a in grp.split("+"): keys[{"S": "SHOPPING", "R": "RECREATION", "A": "ACCOMPANY", "O": "OTHER"}[a]] = grp
            if all(k is None for k in keys.values()): continue
            used.add(v)
            if set(keys.values()) == {"shared"}:
                b, t = val[("shared", v)]
                body += [f"    {lab} & \\multicolumn{{4}}{{c}}{{{num(b)}{stars(t)} (shared)}} \\\\",
                         f"     & \\multicolumn{{4}}{{c}}{{{tt(t, b)}}} \\\\"]
                continue
            cb, ct = [], []
            for p in PURP:
                k = keys[p]
                if k is None: cb.append("--"); ct.append(""); continue
                b, t = val[(k, v)]; mark = ""
                if k not in PURP and k != "shared":
                    if k not in letters: letters[k] = "abcdefgh"[len(letters)]
                    mark = f"$^{{\\mathrm{{{letters[k]}}}}}$"
                cb.append(f"{num(b)}{stars(t)}{mark}"); ct.append(tt(t, b))
            body += [f"    {lab} & " + " & ".join(cb) + " \\\\", "     & " + " & ".join(ct) + " \\\\"]
        if body: rows += [f"    \\multicolumn{{5}}{{@{{}}l}}{{\\emph{{{g}}}}} \\\\"] + body
    allp = set(c[c.purpose != "scale"].param) - {"scale"}
    assert allp <= used, ("unlabelled", allp - used)
    sc = []; st = []
    for p in PURP:
        r = c[(c.purpose == p) & (c.param == "scale")]
        if r.empty: sc.append("1 (normalised)" if p == "SHOPPING" else "1 (not identified)"); st.append("")
        else:
            b, se = float(r.coef.iloc[0]), float(r.se.iloc[0]); t1 = (b - 1) / se
            sc.append(f"{num(b)}{stars(t1)}"); st.append(f"{{\\scriptsize ({se:.4f}) {T.pval(2 * norm.sf(abs(t1)))}}}")
    rows += ["    \\multicolumn{5}{@{}l}{\\emph{Scale}} \\\\", "    scale $\\mu_p$ ($p$ against 1) & " + " & ".join(sc) + " \\\\",
             "     & " + " & ".join(st) + " \\\\"]
    f1 = lambda x: f"{x:,.1f}".replace("-", "$-$")
    nn = "; ".join(f"{WORD[p]} {int(fin[f'N_{p}']):,}" for p in PURP)
    nv = "; ".join(f"{WORD[p]} {f1(fin[f'validation_LL_{p}'])} ({int(fin[f'Nv_{p}']):,} records)" for p in PURP)
    cur = fit[fit.step.astype(str).str.startswith("current_")].set_index("step")
    nvc = "; ".join(f"{WORD[p]} {f1(cur.validation_LL[f'current_{p}'])}" for p in PURP)
    kc = int(cur.K.sum())
    lt = "; ".join(f"$^{{\\mathrm{{{l}}}}}$ shared by " + (lambda w: w[0] if len(w) == 1 else ", ".join(w[:-1]) + " and " + w[-1])([ABBR[a] for a in k.split('+')]) for k, l in letters.items())
    foot = [f"Observations (estimation half): {nn} {F['unit']}; alternatives: 1,588 zones (full choice set); parameters: {int(fin.K)} "
            f"(separate models of the four purposes: {kc}). LL($\\hat\\beta$) = {f1(fin.LL)}; BIC = {f1(fin.BIC)}.",
            f"Validation half, LL: {nv}. Separate models of the four purposes, validation LL: {nvc}.",
            "Utility of zone $j$ for purpose $p$: $U_{pj} = \\mu_p V_{pj}$, $\\mu = 1$ for shopping; a coefficient marked "
            "\\emph{shared} takes the same value in $V_p$ of every purpose that has the variable, so its effect on utility "
            "differs across purposes only through the scale" + (f"; {lt}" if lt else "") + ". --: not in the model of this purpose "
            "(size component whose weight runs to zero); (bound): held on its bound.",
            F["est"],
            "Size term $\\mu\\ln(1+S_j)$, $S_j=\\sum_c \\exp(\\theta_c)\\,x_{jc}$, with $\\theta = 0$ for the base component (retail jobs). " + F["defs"],
            "Coefficient with stars; below it the robust standard error in brackets and $p$ (scale: $p$ against 1). $^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$."]
    head = rf"""{{\footnotesize\setlength{{\tabcolsep}}{{3pt}}\nolinenumbers
\begin{{longtable}}{{@{{}}L{{0.36\linewidth}}cccc@{{}}}}
  \caption{{{F['caption']}}}
  \label{{{F['label']}}}\\
  \toprule
  Variable & {" & ".join(COLS)} \\
  \midrule
  \endfirsthead
  \multicolumn{{5}}{{@{{}}l@{{}}}}{{\footnotesize Table~\thetable\ (continued)}}\\[2pt]
  \toprule
  Variable & {" & ".join(COLS)} \\
  \midrule
  \endhead
  \midrule
  \multicolumn{{5}}{{@{{}}r@{{}}}}{{\emph{{continued on the next page}}}} \\
  \endfoot
  \bottomrule
  \endlastfoot
"""
    tail = ["    \\midrule"] + [f"    \\multicolumn{{5}}{{@{{}}L{{0.98\\linewidth}}}}{{{x}}} \\\\" for x in foot] + ["\\end{longtable}", "\\linenumbers}"]
    open(f"{HERE}/{F['out']}", "w").write(head + "\n".join(rows) + "\n" + "\n".join(tail) + "\n"); print("wrote", F["out"])
    pre = open(f"{os.path.dirname(SBS)}/final_tables/estimation_tables_abit.tex").read().split("\\begin{document}")[0]
    chk = f"{prefix}_check"
    open(f"{HERE}/{chk}.tex", "w").write(pre + "\\begin{document}\n\\input{" + F["out"][:-4] + "}\n\\end{document}\n")
    subprocess.run(["tectonic", "--keep-logs", f"{chk}.tex"], cwd=HERE, capture_output=True)
    lg = open(f"{HERE}/{chk}.log").read()
    print("errors:", lg.count("\n!"), "undefined:", lg.lower().count("undefined"), "overfull:", lg.count("Overfull"))


if __name__ == "__main__":
    main(sys.argv[1])
