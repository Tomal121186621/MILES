#!/usr/bin/env python3
"""Build the instruction PDFs of the manual-estimation package.

Reads <stage>/<model>/RUN.json and <stage>/RUN_ORDER.json and writes
  <stage>/<model>/INSTRUCTIONS.pdf   one page (or two) per model folder
  RUN_ORDER.pdf                      the run order of all folders, SILO then DAYMAP
Usage: python3 tools/build_instructions.py        (from manual_estimation/; needs tectonic)
"""
import json, os, re, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGES = ["SILO", "ABIT"]
TECTONIC = shutil.which("tectonic") or "/opt/homebrew/bin/tectonic"

PREAMBLE = r"""\documentclass[10pt]{article}
\usepackage[a4paper,margin=18mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{booktabs,longtable,array,xcolor,enumitem}
\usepackage{xurl}
\usepackage[hidelinks]{hyperref}
\sloppy\emergencystretch=3em
\setlist{nosep,leftmargin=*}
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\definecolor{cmd}{RGB}{240,240,240}
\newcommand{\cmd}[1]{\par\noindent\colorbox{cmd}{\parbox{\dimexpr\linewidth-2\fboxsep}{\ttfamily\small #1}}\par}
\pagestyle{plain}
\begin{document}
"""

URL_RE = re.compile(r"https?://[^\s,;)'\"]+")

def tex(s):
    """Escape plain text for LaTeX; web addresses become breakable \\url{}, long paths may break at /."""
    if s is None:
        return ""
    s = str(s)
    parts, last = [], 0
    for m in URL_RE.finditer(s):
        parts.append(_esc(s[last:m.start()]))
        u = m.group(0).rstrip(".")
        parts.append(r"\url{" + u.replace("%", r"\%").replace("#", r"\#") + "}")
        last = m.start() + len(u)
    parts.append(_esc(s[last:]))
    return "".join(parts)

def _esc(s):
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    out = "".join(rep.get(c, c) for c in s)
    return out.replace("/", r"/\allowbreak{}").replace(r"\_", r"\_\allowbreak{}")

def texcmd(s):
    """Escape a shell command and allow line breaks at / and spaces."""
    t = tex(s)
    return t.replace("/", r"/\allowbreak{}").replace(" ", r" \allowbreak{}")

def fmt(v):
    if isinstance(v, float):
        return f"{v:,.1f}" if abs(v) >= 100 else f"{v:.4g}"
    if isinstance(v, int):
        return f"{v:,}"
    return tex(v)

def md_to_tex(md):
    """the small Markdown of nb_reader.glance_md (## headings, **bold**, pipe tables, paragraphs) as LaTeX"""
    out, tab = [], []
    def inline(t):
        parts = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", t)
        return "".join(r"\textbf{" + tex(x[2:-2]) + "}" if x.startswith("**") else r"\texttt{" + tex(x[1:-1]) + "}" if x.startswith("`") else tex(x) for x in parts)
    def flush():
        if not tab: return
        rows = [r for r in tab if not re.match(r"^\|[-|]+\|$", r.replace(" ", ""))]
        n = len(rows[0].strip("|").split("|")); w = {3: [40, 70, 50], 4: [24, 46, 62, 24], 6: [20, 40, 50, 16, 16, 16]}.get(n, [160 // n] * n)
        out.append(r"{\small\begin{longtable}{@{}" + "".join(f"L{{{x}mm}}" for x in w) + r"@{}}\toprule")
        for k, r in enumerate(rows):
            out.append(" & ".join(inline(c.strip()) for c in r.strip().strip("|").split("|")) + r" \\" + (r" \midrule" if k == 0 else ""))
        out.append(r"\bottomrule\end{longtable}}"); tab.clear()
    for line in md.split("\n"):
        if line.startswith("|"): tab.append(line); continue
        flush()
        if line.startswith("## "): out.append(r"\section*{" + tex(line[3:]) + "}")
        elif line.strip(): out.append(r"\par " + inline(line.strip()))
    flush()
    return "\n".join(out)


def model_doc(stage, folder, R):
    out = [PREAMBLE]
    out.append(r"{\Large\bfseries " + tex(R.get("model", folder)) + r"}\\[2pt]")
    out.append(r"{\small " + tex(stage) + r" \,/\, \texttt{" + tex(folder) + r"}}")
    if R.get("purpose"):
        out.append(r"\par " + tex(R["purpose"]))
    # model at a glance (the same text as the notebook, generated from the folder's files)
    try:
        import nb_reader as RD
        if stage == "SILO" and folder in RD.SPEC:
            out.append(md_to_tex(RD.glance_md(folder)))
        elif stage == "ABIT" and folder in RD.ABIT_SPEC:
            import abit_figs as AF
            out.append(md_to_tex(RD.abit_glance_md(folder, AF.coef_rows(folder), (R.get("check") or {}).get("N"))))
    except Exception as e:   # the instructions build must not fail on the summary
        print(f"  (no 'at a glance' for {folder}: {e})")
    # folder layout
    out.append(r"\section*{Folder}")
    out.append(r"\begin{tabular}{@{}L{38mm}L{120mm}@{}}\toprule")
    for p, d in [("input/code/", "data-preparation scripts (copies of the project scripts, paths fixed)"),
                 ("input/data/raw/", "source extracts, or a pointer to the shared data folder"),
                 ("input/data/estimation/", "the estimation table exactly as used, with data\\_dictionary.csv"),
                 ("input/data/holdout/", "hold-out sample, where the model has one"),
                 ("model/", "Biogeme script, reference\\_estimates.csv (article values), README.md"),
                 ("output/", "empty: your Biogeme results are written here")]:
        out.append(r"\texttt{" + tex(p) + "} & " + d + r" \\")
    out.append(r"\bottomrule\end{tabular}")
    # raw data
    src = R.get("data_sources") or []
    if src:
        out.append(r"\section*{1. Get the raw data}")
        out.append(r"Download each source below and place the files where shown (paths from the \texttt{manual\_estimation} folder). Sources marked \emph{verify} have no download link recorded in the project; check the provider's page.")
        for d in src:
            out.append(r"\par\textbf{" + tex(d.get("name", "")) + "}" + (r" \,---\, " + tex(d.get("provider")) if d.get("provider") else ""))
            out.append(r"\begin{itemize}")
            if d.get("url"):
                out.append(r"\item Where: \url{" + str(d["url"]).replace("%", r"\%").replace("#", r"\#") + "}")
            if d.get("how"):
                h = d["how"] if isinstance(d["how"], list) else [d["how"]]
                out.append(r"\item How: " + " ".join(tex(x) for x in h))
            if d.get("place_in"):
                out.append(r"\item Put in: \texttt{" + texcmd(d["place_in"]) + "}")
            if d.get("files"):
                f = d["files"] if isinstance(d["files"], list) else [d["files"]]
                out.append(r"\item Files: " + ", ".join(r"\texttt{" + tex(x) + "}" for x in f))
            if d.get("notes"):
                for n in (d["notes"] if isinstance(d["notes"], list) else [d["notes"]]):
                    out.append(r"\item " + tex(n))
            out.append(r"\end{itemize}")
    # dependencies
    dep = R.get("depends_on") or []
    out.append(r"\section*{2. Run these folders first}")
    if dep:
        out.append(r"\begin{itemize}")
        for d in dep:
            if isinstance(d, dict):
                out.append(r"\item \texttt{" + tex(d.get("folder", "")) + "}: " + tex(d.get("why", "")))
            else:
                out.append(r"\item " + tex(d))
        out.append(r"\end{itemize}")
    else:
        out.append("Nothing: this model can be run on its own.")
    # setup
    out.append(r"\section*{3. Set-up (once)}")
    out.append(r"Use the Biogeme environment: \texttt{\textasciitilde/.venvs/biogeme}. In VS Code select this interpreter, or run the commands below from a terminal. Each step starts with its own \texttt{cd}, given from the \texttt{manual\_estimation} folder.")
    # steps
    out.append(r"\section*{4. Prepare the data, estimate, compare}")
    base = f"{stage}/{folder}"
    for s in R.get("steps", []):
        s = dict(s)
        cwd = s.get("cwd") or "."
        s["cwd"] = base if cwd in (".", "") else f"{base}/{cwd.strip('./') if cwd.startswith('./') else cwd}"
        head = f"Step {s.get('step', '')}: " + tex(s.get("what", ""))
        meta = []
        if s.get("minutes") not in (None, ""):
            meta.append(f"about {fmt(s['minutes'])} min")
        if s.get("memory_gb") not in (None, ""):
            meta.append(f"about {fmt(s['memory_gb'])} GB memory")
        out.append(r"\textbf{" + head + "}" + (r" {\small(" + ", ".join(meta) + ")}" if meta else ""))
        out.append(r"\cmd{cd " + texcmd(s["cwd"]) + "}")
        if s.get("command"):
            out.append(r"\cmd{" + texcmd(s["command"]) + "}")
        cr = s.get("creates")
        if cr:
            cr = cr if isinstance(cr, list) else [cr]
            out.append(r"{\small Creates: " + ", ".join(r"\texttt{" + tex(c) + "}" for c in cr) + r"}\par")
        out.append(r"\medskip")
    # check
    ck = R.get("check") or {}
    if ck:
        out.append(r"\section*{5. Check your result}")
        out.append(r"Compare your estimates with \texttt{model/reference\_estimates.csv} (the article values: coefficient, robust s.e., $p$). The final log-likelihood should equal the article value; small differences in the last digit come from the optimiser.")
        out.append(r"\begin{tabular}{@{}lr@{}}\toprule")
        labels = {"N": "Observations $N$", "K": "Parameters $K$", "article_LL": "Article LL($\\hat\\beta$)",
                  "biogeme_LL_at_article_coefficients": "Biogeme LL at the article coefficients (checked)"}
        for k, v in ck.items():
            out.append(labels.get(k, tex(k)) + " & " + fmt(v) + r" \\")
        out.append(r"\bottomrule\end{tabular}")
    notes = R.get("notes") or []
    if notes:
        out.append(r"\section*{6. Notes}")
        out.append(r"\begin{itemize}")
        for n in notes:
            out.append(r"\item " + tex(n))
        out.append(r"\end{itemize}")
    out.append(r"\end{document}")
    return "\n".join(out)

def order_doc(orders):
    out = [PREAMBLE, r"{\Large\bfseries Manual estimation: what to run, in which order}\par",
           r"Each folder holds one model with its own \texttt{INSTRUCTIONS.pdf}. Run the folders top to bottom; a folder needs only the folders listed before it. All commands use the Biogeme environment \texttt{\textasciitilde/.venvs/biogeme}. Your results go to each folder's \texttt{output/}; compare them with \texttt{model/reference\_estimates.csv}. The tables produced by Claude are in \texttt{CLAUDE\_TABLES/} (current article tables, and the Route B proposals in \texttt{route\_B\_2026-11-13/}, which are not in the model runs)."]
    for stage, items in orders:
        out.append(r"\section*{" + {"SILO": "SILO (folder SILO)", "ABIT": "DAYMAP, Daily Activity Model for Agent Plans (folder ABIT)"}.get(stage, stage) + "}")
        out.append(r"\begin{longtable}{@{}r L{62mm} L{96mm}@{}}\toprule No. & Folder & Why at this point \\ \midrule")
        for i, it in enumerate(items, 1):
            f = it.get("folder", it) if isinstance(it, dict) else it
            why = it.get("why", it.get("reason", "")) if isinstance(it, dict) else ""
            out.append(f"{i} & \\texttt{{{tex(f)}}} & {tex(why)} \\\\")
        out.append(r"\bottomrule\end{longtable}")
    out.append(r"\end{document}")
    return "\n".join(out)

def compile_pdf(src, dest):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "doc.tex")
        open(p, "w").write(src)
        r = subprocess.run([TECTONIC, "-X", "compile", p], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FAILED {dest}\n{r.stderr[-1500:]}")
            return False
        shutil.copy(os.path.join(td, "doc.pdf"), dest)
    return True

def main():
    orders, n_ok, missing = [], 0, []
    for stage in STAGES:
        sd = os.path.join(ROOT, stage)
        if not os.path.isdir(sd):
            continue
        for folder in sorted(os.listdir(sd)):
            fd = os.path.join(sd, folder)
            if not os.path.isdir(fd) or folder == "00_shared_data":
                continue
            rj = os.path.join(fd, "RUN.json")
            if not os.path.exists(rj):
                missing.append(f"{stage}/{folder}")
                continue
            R = json.load(open(rj))
            n_ok += compile_pdf(model_doc(stage, folder, R), os.path.join(fd, "INSTRUCTIONS.pdf"))
        ro = os.path.join(sd, "RUN_ORDER.json")
        if os.path.exists(ro):
            O = json.load(open(ro))
            items = O.get("order", O) if isinstance(O, dict) else O
            orders.append((stage, items))
    if orders:
        compile_pdf(order_doc(orders), os.path.join(ROOT, "RUN_ORDER.pdf"))
    print(f"{n_ok} instruction PDFs built; RUN_ORDER.pdf {'built' if orders else 'not built (no RUN_ORDER.json)'}")
    if missing:
        print("No RUN.json yet:", ", ".join(missing))

if __name__ == "__main__":
    main()
