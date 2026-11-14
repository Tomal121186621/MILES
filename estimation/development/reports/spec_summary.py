#!/usr/bin/env python3
"""Specification summary of every estimated model, read from the row labels of the published coefficient tables
(build/est/*.tex, as assembled by make_pdf.py), so it cannot differ from them: rows = models, columns = variable groups, cells =
the form of the impedance and distance terms and a tick for the other groups.  Reference rows are not counted.
    python3 estimation/development/reports/make_pdf.py && python3 estimation/development/reports/spec_summary.py   ->  spec_summary.tex (table for the article), model_specification_summary.pdf"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re, shutil, subprocess

HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/final_tables"   # templates (.tex), build/ and PDFs (data)
B = os.path.join(HERE, "build")
MODELS = [("Residential location and car ownership", [("est_region", "County"), ("est_zone", "Zone $\\times$ structure type"),
                                                       ("est_dwelling", "Dwelling"), ("est_cars", "Car ownership")]),
          ("Workplace and school location", [("est_jobchoice", "Workplace"), ("est_school", "School (three levels)")]),
          ("Tour mode choice", [("est_mc_work", "Work"), ("est_mc_school", "School"), ("est_mc_shopping", "Shopping"), ("est_mc_other", "Other")]),
          ("Destination and stop location", [("est_dc_pooled", "Primary destination (pooled)"), ("est_stop_SHOPPING_stop", "Stop: shopping"),
                                             ("est_stop_RECREATION_stop", "Stop: recreation"), ("est_stop_ACCOMPANY_stop", "Stop: accompanying"),
                                             ("est_stop_OTHER_stop", "Stop: other")]),
          ("Other episode locations", [("est_loc_edu", "Non-student school, daycare (pooled)"), ("est_loc_wahb", "Work, home-based workers"),
                                       ("est_loc_wbhome", "Work business from home"), ("est_loc_wbwork", "Work business from work")]),
          ("Activity models", [("est_subtour", "Outings from work (3 parts)"), ("est_return", "Return home")])]
# impedance and distance: codes; other groups: tick.  Patterns are applied to the row label (lower case).
IMP = [("GC", r"generalised cost"), ("CT", r"car generalised time|car time|^time \(min\)|^\\quad car time|^under 20|^20--60|^over 60"),
       ("ln CT", r"ln\(1\+\\text\{time\}\)"), ("T+C", r"travel time|travel cost"), ("LS", r"logsum, detour|school-tour logsum|^mode-choice logsum"),
       ("km", r"round-trip distance"), ("commute", r"sum over workers of")]
DIST = [("PW", r"^(\\quad )?(distance|detour) [0-9]|^distance \$>\$|^detour \$>\$"), ("lin", r"^(distance|detour via home|distance from home) .*\(km\)$|^distance \(km\)"),
        ("ln", r"^ln\(distance, km\)|^ln\(1 \+ (home--workplace )?distance|^ln\(1 \+ detour via home|^ln\(1 \+ distance")]
GROUPS = [("Size", r"\\theta|\\mu\$, ln size|size coefficient|log weight|ln dwellings|enrolment"),
          ("Area, boundaries", r"baltimore|washington|virginia|delaware|dc workplace|county|state|intrazonal|same zone|zone of the|home zone|workplace zone|central business|montgomery|arlington|maryland|core city|rural|10,000 jobs"),
          ("Land use", r"^(?!.*public share)(.*)(retail jobs per|land-use mix|density|share \$\\times\$|share$|high-wage|crime|school learning)"),
          ("Dwelling, cost", r"cost share|housing cost|zone cost|bedroom|built in|dwelling$|single-family|multifamily"),
          ("Access.", r"accessibility"),
          ("Income", r"income"), ("Cars", r"\bcars\b|no car"),
          ("Age", r"\bage\b|person \$<\$ 18|person 65|oldest member|retiree|person 18|under 5|age \(\(age|age \(years\)"),
          ("Children, hh size", r"child|household size|one-person|single-person|household with|persons aged|workers \$|^workers$|two or more workers"),
          ("Gender", r"\bman\b|woman|\bmale\b|female"), ("Licence", r"licence"),
          ("Worker, person type", r"^(?!sum over workers).*(worker|person type|non-working)"),
          ("Time of day", r"\bam\b|\bpm\b|evening|midday|arrival|end of the preceding|secondary work"),
          ("Tour, episode", r"tour|stop|episode|joint|inbound|outing|arrived at work|accompanying$|recreation$")]
SKIP = r"^constant|nest parameter|scale|^parameter$|students \$n\$|alternatives|log-likelihood|^bic$|validation|reference"


def rows_of(t):
    s = open(f"{B}/est/{t}.tex").read(); out = []
    for l in s.split("\n"):
        if "&" not in l or "\\\\" not in l or l.strip().startswith("&"): continue
        lab, rest = l.split("&", 1)
        lab = lab.strip()
        if not lab or lab.startswith("\\multicolumn") or lab.startswith("Variable") or "reference" in rest or "0 (fixed)" in rest: continue
        out.append(lab.lower())
    k = re.search(r"parameters: ([0-9,]+)", s)
    return out, (k.group(1) if k else "")


def classify(labs):
    imp = [c for c, p in IMP if any(re.search(p, x) and not re.search(r"\$\\times\$", x) for x in labs)]
    dist = [c for c, p in DIST if any(re.search(p, x) for x in labs)]
    used = {g for g, p in GROUPS for x in labs if not re.search(SKIP, x) and re.search(p, x)}
    return " + ".join(imp) or "--", " + ".join(dist) or "--", used


def main():
    cols = [g for g, _ in GROUPS]
    head = "Model & Impedance & Distance & " + " & ".join(f"\\rotatebox{{90}}{{{c}}}" for c in cols) + " & $K$ \\\\"
    body = []
    for fam, ms in MODELS:
        body.append(f"\\multicolumn{{{len(cols) + 4}}}{{@{{}}l}}{{\\emph{{{fam}}}}} \\\\")
        for t, name in ms:
            if not os.path.exists(f"{B}/est/{t}.tex"): continue
            labs, k = rows_of(t); imp, dist, used = classify(labs)
            body.append(f"\\quad {name} & {imp} & {dist} & " + " & ".join("$\\bullet$" if c in used else "" for c in cols) + f" & {k} \\\\")
    note = ("Impedance: GC generalised cost (time plus cost over the value of time); T+C travel time and cost; CT car (generalised) time; "
            "ln CT $\\ln(1+\\text{time})$; LS mode-choice logsum; km round-trip distance; commute: $\\sum \\ln(1+t)$ over the household's workers. Distance: PW piecewise linear (bends at 1, 2, 5, 10, "
            "20, 50\\,km; detour at 1, 2, 5, 10, 20\\,km); lin linear; ln logarithmic. A dot marks a variable group with at least one term in "
            "the final model (main effect or interaction); reference categories and terms held at 0 are not counted. $K$: estimated parameters.")
    tab = ("{\\footnotesize\\setlength{\\tabcolsep}{2.5pt}\\renewcommand{\\arraystretch}{1.15}\n\\begin{longtable}{@{}l ll " + "c" * len(cols) + " r@{}}\n"
           "  \\caption{Specification of the estimated models: impedance and distance forms and the variable groups in each final model.}\n"
           "  \\label{tab:spec_summary}\\\\\n  \\toprule\n  " + head + "\n  \\midrule\n  \\endfirsthead\n  \\toprule\n  " + head + "\n  \\midrule\n  \\endhead\n"
           "  \\bottomrule\n  \\endlastfoot\n" + "\n".join("  " + x for x in body) + "\n\\end{longtable}\n"
           f"\\vspace{{-6pt}}\\noindent {note}\\par}}\n")
    open(f"{HERE}/spec_summary.tex", "w").write(tab)
    pre = open(f"{HERE}/estimation_tables_abit.tex").read().split("\\begin{document}")[0]
    if "graphicx" not in pre: pre = pre.replace("\\begin{document}", "") + "\\usepackage{graphicx}\n"
    doc = pre + "\\usepackage{pdflscape}\n\\begin{document}\n\\input{spec_summary}\n\\end{document}\n"
    shutil.copy(f"{HERE}/spec_summary.tex", B); open(f"{B}/model_specification_summary.tex", "w").write(doc)
    for _ in range(2):
        r = subprocess.run(["tectonic", "-X", "compile", "-k", "--keep-logs", "model_specification_summary.tex"], cwd=B, capture_output=True, text=True)
        if r.returncode: print(r.stderr[-3000:]); raise SystemExit(1)
    shutil.copy(f"{B}/model_specification_summary.pdf", HERE)
    log = open(f"{B}/model_specification_summary.log").read(); print("ok; overfull:", log.count("Overfull \\hbox"))


if __name__ == "__main__":
    main()
