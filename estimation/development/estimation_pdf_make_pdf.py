#!/usr/bin/env python3
"""Estimation tables of the re-specified models (side experiment, 2026-11-06). Tables come from ../article_tables; a model
whose new table is not there yet gets a 'pending' note. Compiles estimation_tables_respec.tex with tectonic.
Usage: python3 estimation/development/estimation_pdf_make_pdf.py"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re, shutil, subprocess

HERE = f"{WORKSPACE}/side_experiments/respec_2026-11/estimation_pdf"   # template, build/ and PDF (data)
NEW = os.path.join(HERE, "..", "article_tables")
ART = os.path.join(WORKSPACE, "5_reports", "article")
B = os.path.join(HERE, "build")
TABLES = ["est_region", "est_zone", "est_dwelling", "est_cars", "est_jobchoice", "est_school", "est_subtour", "est_return",
          "est_dc_SHOPPING_primary", "est_dc_RECREATION_primary", "est_dc_ACCOMPANY_primary", "est_dc_OTHER_primary",
          "est_stop_SHOPPING_stop", "est_stop_RECREATION_stop", "est_stop_ACCOMPANY_stop", "est_stop_OTHER_stop",
          "est_loc_wbwork", "est_loc_wbhome", "est_loc_wahb", "est_loc_nonstud", "est_loc_daycare",
          "est_mc_work", "est_mc_school", "est_mc_shopping", "est_mc_other"]
PENDING = "\\par\\smallskip\\noindent\\fbox{\\parbox{0.97\\linewidth}{\\small\\emph{Re-estimation still running; the table is added when it is finished.}}}\\par\\smallskip\n"


def clean(s):
    s = re.sub(r"Variables: defined in Table~\\ref\{[^}]*\}; base component", "Base component", s)
    s = "\n".join(l for l in s.split("\n") if not re.search(r"\{Variables: Table", l))
    s = re.sub(r" \(Section~\\ref\{[^}]*\}\)", "", s)
    s = re.sub(r" ?\(Table~\\ref\{[^}]*\}\)", "", s)
    return s


def main():
    os.makedirs(f"{B}/est", exist_ok=True)
    done = []
    for t in TABLES:
        src = f"{NEW}/{t}.tex"
        if os.path.exists(src):
            open(f"{B}/est/{t}.tex", "w").write(clean(open(src).read())); done.append(t)
        else:
            open(f"{B}/est/{t}.tex", "w").write(PENDING)
    shutil.copy(f"{ART}/references.bib", f"{B}/references.bib")
    shutil.copy(f"{HERE}/estimation_tables_respec.tex", f"{B}/estimation_tables_respec.tex")
    for _ in range(2):
        r = subprocess.run(["tectonic", "-X", "compile", "-k", "--keep-logs", "estimation_tables_respec.tex"], cwd=B, capture_output=True, text=True)
        if r.returncode: print(r.stderr[-3000:]); raise SystemExit(1)
    shutil.copy(f"{B}/estimation_tables_respec.pdf", f"{HERE}/estimation_tables_respec.pdf")
    log = open(f"{B}/estimation_tables_respec.log").read()
    print("new tables:", len(done), "of", len(TABLES), "; pending:", [t for t in TABLES if t not in done])
    print("undefined:", sorted(set(re.findall(r"(?:Reference|Citation) `([^']+)'", log))))
    print("overfull:", len(re.findall(r"Overfull \\hbox", log)))


if __name__ == "__main__":
    main()
