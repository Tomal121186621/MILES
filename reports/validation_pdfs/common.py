"""Shared helpers of the four validation builders: paths, LaTeX writing, table and figure blocks, build and log check."""
import os, re, shutil, subprocess, sys, glob
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(os.path.dirname(HERE))                     # Validation_2026
ROOT = os.path.dirname(V)
REPORTS = f"{V}/5_reports"
DATA = f"{V}/data"
for p in (REPORTS, f"{REPORTS}/composites", HERE):
    if p not in sys.path: sys.path.insert(0, p)


def tx(s):
    """Escape a string for LaTeX text."""
    s = str(s)
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    return s


def num(x, d=2, sign=False, pct=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)): return "--"
    s = f"{x * (100 if pct else 1):{'+' if sign else ''}.{d}f}".replace("-", "\u2212")
    return s + (r"\%" if pct else "")


def hd(*lines):
    """Multi-line right-aligned header cell."""
    return r"\begin{tabular}[b]{@{}r@{}}" + r"\\".join(lines) + r"\end{tabular}"


def thousands(x, d=0):
    return f"{x:,.{d}f}".replace(",", r"\,")


class Doc:
    """A LaTeX document written in pieces; build() compiles it with tectonic in a work directory and checks the log."""

    def __init__(self, title, subtitle, workdir):
        self.title, self.subtitle, self.work = title, subtitle, workdir
        os.makedirs(workdir, exist_ok=True); self.parts = []; self.nfig = 0; self.ntab = 0; self.figfiles = []

    def raw(self, s): self.parts.append(s)

    def section(self, t): self.parts.append(f"\\section{{{tx(t)}}}\n")

    def sub(self, t): self.parts.append(f"\\subsection{{{tx(t)}}}\n")

    def para(self, s, escape=False): self.parts.append((tx(s) if escape else s) + "\n\n")

    def clear(self): self.parts.append("\\clearpage\n")

    def figure(self, path, caption, height=None, width=r"\textwidth"):
        """Figure block; path is copied into the work directory."""
        if not path or not os.path.exists(path):
            raise FileNotFoundError(path)
        self.nfig += 1; name = f"f{self.nfig:02d}{os.path.splitext(path)[1]}"; shutil.copy(path, f"{self.work}/{name}"); self.figfiles.append(name)
        opt = f"width={width}" + (f",height={height},keepaspectratio" if height else "")
        self.parts.append(f"\\begin{{figure}}[H]\n\\centering\n\\includegraphics[{opt}]{{{name}}}\n\\caption{{{caption}}}\n\\end{{figure}}\n")

    def table(self, header, rows, colspec, caption, note=None, small="\\footnotesize", stripe=None, midrules=(), tabsep=4):
        """header: list of strings (LaTeX); rows: list of lists of strings (LaTeX); midrules: row indices before which a rule is drawn."""
        self.ntab += 1
        L = [f"\\begin{{table}}[H]\n\\centering\n\\caption{{{caption}}}\n{small}\\setlength{{\\tabcolsep}}{{{tabsep}pt}}\n\\begin{{adjustbox}}{{max width=\\textwidth}}\n\\begin{{tabular}}{{{colspec}}}\n\\toprule"]
        L.append(" & ".join(header) + " \\\\\n\\midrule")
        for i, r in enumerate(rows):
            if i in midrules: L.append("\\midrule")
            L.append(" & ".join(r) + " \\\\")
        L.append("\\bottomrule\n\\end{tabular}\n\\end{adjustbox}")
        if note: L.append(f"\\par\\vspace{{3pt}}\\parbox{{\\textwidth}}{{\\footnotesize {note}}}")
        L.append("\\end{table}\n"); self.parts.append("\n".join(L))

    def longtable(self, header, rows, colspec, caption, small="\\footnotesize"):
        self.ntab += 1
        L = [f"{small}\\setlength{{\\tabcolsep}}{{2pt}}\n\\begin{{longtable}}{{{colspec}}}\n\\caption{{{caption}}}\\\\\n\\toprule", " & ".join(header) + " \\\\\n\\midrule\n\\endfirsthead",
             "\\toprule\n" + " & ".join(header) + " \\\\\n\\midrule\n\\endhead", "\\bottomrule\n\\endfoot"]
        for r in rows: L.append(" & ".join(r) + " \\\\")
        L.append("\\end{longtable}\n\\normalsize\n"); self.parts.append("\n".join(L))

    def build(self, out_pdf):
        pre = open(f"{HERE}/preamble.tex").read()
        head = (f"\\begin{{document}}\n\\begin{{center}}{{\\LARGE\\bfseries {tx(self.title)}}}\\\\[4pt]{{\\large {tx(self.subtitle)}}}\\end{{center}}\n\\vspace{{4pt}}\n")
        src = pre + head + "\n".join(self.parts) + "\n\\end{document}\n"
        tex = f"{self.work}/doc.tex"; open(tex, "w").write(src)
        r = subprocess.run(["tectonic", "-X", "compile", "--keep-logs", "--keep-intermediates", "doc.tex"], cwd=self.work, capture_output=True, text=True)
        log = open(f"{self.work}/doc.log", errors="ignore").read() if os.path.exists(f"{self.work}/doc.log") else r.stderr
        errs = [l for l in log.splitlines() if l.startswith("!")]
        over = [l for l in log.splitlines() if l.startswith("Overfull")]
        under_missing = [l for l in log.splitlines() if "not found" in l or "Missing" in l]
        pdf = f"{self.work}/doc.pdf"
        if r.returncode != 0 or not os.path.exists(pdf):
            print(r.stdout[-3000:], r.stderr[-3000:]); raise SystemExit("LaTeX build failed")
        os.makedirs(os.path.dirname(out_pdf), exist_ok=True); shutil.copy(pdf, out_pdf)
        pages = int(re.search(r"Output written on .*\((\d+) page", log).group(1)) if re.search(r"Output written on .*\((\d+) page", log) else None
        print(f"{out_pdf}: {pages} pages, {len(errs)} LaTeX errors, {len(over)} overfull boxes, {self.nfig} figures, {self.ntab} tables")
        for l in errs + over + under_missing: print("   ", l)
        return pages, errs, over


def patch_fig_dirs(workdir):
    """Point the figure modules of 5_reports at a work directory so that no existing figure file is overwritten."""
    os.makedirs(workdir, exist_ok=True)
    import figures_validation as fv
    os.makedirs(workdir + "/_copy", exist_ok=True); fv.OUT = workdir; fv.PAPERFIG = workdir + "/_copy"
    try:
        import composite as K
        K.OUT = workdir; K.ART = workdir + "/_copy"
    except Exception: pass
    return fv


def pdf_pages_to_png(pdf, outdir, dpi=70, pages=None):
    os.makedirs(outdir, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", pdf, f"{outdir}/p"] + (["-f", str(pages[0]), "-l", str(pages[1])] if pages else []), check=True)
