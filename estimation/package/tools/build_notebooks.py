#!/usr/bin/env python3
"""Write <folder>_estimation.ipynb in every SILO and ABIT model folder (00_tasha_distributions.ipynb for the TASHA distributions): raw data -> data preparation -> estimation data -> descriptive
statistics and correlation heatmaps -> model specification -> log-likelihood at the article values -> Biogeme
estimation -> comparison with the article -> hold-out.

The notebooks call the folder's own model/estimate_*.py (model() and DATA), so the specification is the one of the
scripts; nothing is re-specified here.
Usage: python3 tools/build_notebooks.py            (from manual_estimation/)
"""
import json, os, re
import nbformat as nbf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# per model: estimation data layout and the hold-out that model() can read by swapping DATA
SILO = {
    "01_residential_county":              {"layout": "wide", "holdout": "county_holdout.parquet", "heavy": False},
    "02_residential_zone_structure_type": {"layout": "wide", "holdout": None, "heavy": False},
    "03_residential_dwelling":            {"layout": "wide", "holdout": "dwelling_holdout.parquet", "heavy": False},
    "04_car_ownership":                   {"layout": "flat", "holdout": "car_ownership_holdout.csv", "heavy": False},
    "05_workplace_choice":                {"layout": "wide", "holdout": None, "heavy": False},
    "06_school_location_K8":              {"layout": "school", "holdout": "school_k8_holdout", "heavy": True},
    "07_school_location_high_school":     {"layout": "school", "holdout": "school_hs_holdout", "heavy": True},
    "08_school_location_college":         {"layout": "school", "holdout": "school_col_holdout", "heavy": True},
}


def md(s):
    return nbf.v4.new_markdown_cell(s.strip("\n"))


def code(s):
    return nbf.v4.new_code_cell(s.strip("\n"))


def sources_md(R):
    out = ["## 1. Raw data", "",
           "Where each source comes from and where it goes (paths from `manual_estimation/`). "
           "*verify*: no download link is recorded in the project. The full download steps are in `INSTRUCTIONS.pdf`.", ""]
    for d in R.get("data_sources") or []:
        out.append(f"**{d.get('name', '')}**" + (f" — {d['provider']}" if d.get("provider") else ""))
        if d.get("url"):
            out.append(f"- Where: <{d['url']}>")
        if d.get("how"):
            h = d["how"] if isinstance(d["how"], list) else [d["how"]]
            out.append("- How: " + " ".join(h))
        if d.get("place_in"):
            out.append(f"- Put in: `{d['place_in']}`")
        if d.get("files"):
            f = d["files"] if isinstance(d["files"], list) else [d["files"]]
            out.append("- Files: " + ", ".join(f"`{x}`" for x in f))
        out.append("")
    return "\n".join(out)


def steps(R):
    """Split RUN.json steps: upstream (provided) / package data steps (run here) / model steps (done in the notebook)."""
    up, prep = [], []
    for s in R.get("steps", []):
        cwd = (s.get("cwd") or ".").lstrip("./") or "."
        if cwd.startswith("model"):
            continue
        local = cwd.startswith("input") or (cwd == "." and "input/code" in s.get("command", ""))
        (prep if local else up).append(s)
    return up, prep


def silo_notebook(folder, cfg, R):
    mod = os.path.basename(next(f for f in os.listdir(f"{ROOT}/SILO/{folder}/model") if f.startswith("estimate_")))[:-3]
    src = open(f"{ROOT}/SILO/{folder}/model/{mod}.py").read()
    name = [n for n in re.findall(r'model_name = "(\w+)"', src) if not n.endswith("_check")][0]
    weighted = "--biogeme-weight" in src
    ck = R.get("check") or {}
    up, prep = steps(R)
    C = []

    C.append(md(f"""
# {R.get('model', folder)}

{R.get('purpose', '')}

Article table: `{R.get('article_table', '')}`. This notebook goes from the raw data to the estimates of this model:

1. Raw data
2. Data preparation
3. Estimation data
4. Descriptive statistics
5. Correlation of the explanatory variables (heatmaps, VIF)
6. Model specification (the folder's `model/{mod}.py`, unchanged)
7. Log-likelihood at the article coefficients
8. Biogeme estimation
9. Results: article format, fit, comparison with the article, correlation of the estimates
10. Hold-out sample

**Kernel:** select *Python (biogeme)* (`~/.venvs/biogeme`) in VS Code, then *Run All*. The switches in the next cell decide what is recomputed.
"""))
    flags = f"""
RUN_DATA_PREP  = False   # True: rebuild the estimation tables from input/data/raw (section 2); a copy of the provided tables is kept first
RUN_CHECK      = {not cfg['heavy']}    # log-likelihood at the article coefficients{'  (this model: about 30 min, 4 GB and more)' if cfg['heavy'] else ''}
RUN_ESTIMATION = {not cfg['heavy']}    # Biogeme estimation, written to output/{'  (this model: several hours and more than 8 GB; False reads output/ if a result is there)' if cfg['heavy'] else ''}
RUN_HOLDOUT    = {bool(cfg['holdout']) and not cfg['heavy']}    # log-likelihood of the hold-out sample at your estimates
"""
    C.append(code(flags + f"""
import os, sys, json, glob, inspect, importlib, time
import numpy as np, pandas as pd, matplotlib.pyplot as plt
import biogeme.biogeme as bio
from biogeme.parameters import Parameters
from biogeme.results_processing import EstimationResults

FOLDER = os.path.abspath("")                       # this model folder (VS Code starts the notebook here)
sys.path.insert(0, os.path.join(FOLDER, "..", "..", "tools")); import nbtools as nt
sys.path.insert(0, os.path.join(FOLDER, "model"))
RUN = json.load(open(os.path.join(FOLDER, "RUN.json")))
OUT = os.path.join(FOLDER, "output"); os.makedirs(OUT, exist_ok=True)
NAME = "{name}"
pd.set_option("display.max_rows", 200, "display.max_columns", 60, "display.width", 200)
plt.rcParams.update({{"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False}})
print("model folder:", FOLDER)
"""))

    C.append(md(sources_md(R)))
    C.append(code("""
# files of input/data/raw (the model's own extracts; shared sources are in ../00_shared_data)
raw = os.path.join(FOLDER, "input", "data", "raw")
display(nt.files_table(raw))
for f in sorted(glob.glob(os.path.join(raw, "*")))[:6]:
    head, n = nt.preview(f)
    if head is not None:
        print(f"\\n{os.path.basename(f)}" + (f"  ({n:,} rows)" if n else ""))
        display(head)
"""))
    C.append(code("""
print(open(os.path.join(raw, "README.md")).read() if os.path.exists(os.path.join(raw, "README.md")) else "no README in input/data/raw")
"""))

    # data preparation
    lines = ["## 2. Data preparation", "",
             "Upstream stages (outputs provided in `00_shared_data` and `input/data/raw`; run them only for a full rebuild from the raw data, commands from the model folder):", ""]
    for s in up:
        lines.append(f"- **Step {s.get('step')}.** {s.get('what', '')}  \n  `cd {s.get('cwd')}` → `{s.get('command', '')}`")
    lines += ["", "Package steps, run below when `RUN_DATA_PREP = True`: they rebuild `input/data/estimation` and `input/data/holdout` "
              "with the original random draws and stop if the log-likelihood of the original run is not reproduced; "
              "`check_against_provided.py` must end with *ALL TABLES MATCH*."]
    C.append(md("\n".join(lines)))
    for s in prep:
        cmd = s.get("command", "").replace("~/.venvs/biogeme/bin/python", sys_py())
        C.append(md(f"**Step {s.get('step')}.** {s.get('what', '')}" + (f" (about {s['minutes']} min)" if isinstance(s.get("minutes"), (int, float)) else "")))
        C.append(code(f"""
if RUN_DATA_PREP:
    nt.run({cmd!r}, cwd=os.path.join(FOLDER, {s.get('cwd').lstrip('./')!r}))
else:
    print("skipped (RUN_DATA_PREP = False): the provided tables are used")
"""))

    # estimation data
    C.append(md("## 3. Estimation data\n\nThe table exactly as used in the estimation, and its data dictionary."))
    C.append(code("""
est = os.path.join(FOLDER, "input", "data", "estimation")
display(nt.files_table(est))
dd = pd.read_csv(os.path.join(est, "data_dictionary.csv"))
dd
"""))
    if cfg["layout"] == "school":
        C.append(code("""
import estimate_%s as M
st = pd.read_parquet(f"{M.DATA}_students.parquet")          # one row per student: person attributes, possible home and school zones
alt = pd.read_parquet(f"{M.DATA}_alternatives.parquet")     # sampled school zones of each possible home zone
cand = pd.read_parquet(f"{M.DATA}_candidates.parquet")      # the possible chosen school zones
for k, t in [("students", st), ("alternatives", alt), ("candidates", cand)]:
    print(f"{k:13s} {t.shape[0]:>10,} rows  {t.shape[1]:>3} columns")
display(st.head()); display(alt.head())
""" % mod[len('estimate_'):]))
    else:
        rd = "pd.read_csv(M.DATA)" if cfg["layout"] == "flat" else "pd.read_parquet(M.DATA)"
        C.append(code(f"""
import {mod} as M
df = {rd}
print(f"{{df.shape[0]:,}} rows (decision makers), {{df.shape[1]:,}} columns")
df.head()
"""))

    # descriptive
    C.append(md("## 4. Descriptive statistics"))
    if cfg["layout"] == "flat":
        C.append(code("""
y = df["cars"]
shares = y.value_counts().sort_index().rename("households").to_frame()
shares["share %"] = (100 * shares["households"] / len(y)).round(2)
display(shares)
ax = shares["share %"].plot.bar(color="#2b6cb0", rot=0, figsize=(5, 3)); ax.set_xlabel("cars (3 = 3 or more)"); ax.set_ylabel("%"); ax.set_title("Chosen alternative"); plt.show()
X = nt.explanatory(df.drop(columns=["cars"]))
display(X.describe().T.round(3))
display(X.groupby(y).mean().T.round(3).add_prefix("mean | cars = "))
"""))
    elif cfg["layout"] == "wide":
        C.append(code("""
alts = nt.alt_columns(df)
J = len(next(iter(alts.values())))
print(f"{J} alternatives per decision maker (columns <variable>_<j>)")
if "av" in alts:
    n_av = df[alts["av"]].sum(axis=1)
    print("available alternatives per decision maker:", n_av.describe().round(1).to_dict())
if "choice" in df:
    c = df["choice"].value_counts().sort_index()
    ax = (100 * c / c.sum()).plot.bar(figsize=(min(14, 3 + 0.12 * J), 3), color="#2b6cb0", width=0.8)
    ax.set_xlabel("position of the chosen alternative"); ax.set_ylabel("%"); ax.set_title("Chosen alternative (position in the set)")
    ax.set_xticks(ax.get_xticks()[::max(1, J // 20)]); plt.show()
person = [c for c in df.columns if not any(c in v for v in alts.values())]
display(nt.explanatory(df[person]).describe().T.round(3))
if "weight" in df:
    ax = df["weight"].plot.hist(bins=60, figsize=(5, 3), color="#2b6cb0"); ax.set_title("Estimation weight"); plt.show()
    print("weight: mean %.3f, min %.3f, max %.3f" % (df.weight.mean(), df.weight.min(), df.weight.max()))
"""))
    else:
        C.append(code("""
person = nt.explanatory(st[[c for c in st.columns if not c.startswith(("home_zone", "school_zone", "w_home", "w_school"))]])
display(person.describe().T.round(3))
print("possible home zones per student:", (st.filter(like="w_home_") > 0).sum(axis=1).value_counts().sort_index().to_dict())
print("possible school zones per student (slot 0):", (st.filter(like="w_school_") > 0).sum(axis=1).value_counts().sort_index().to_dict())
alt_x = nt.explanatory(alt.drop(columns=["av"]))
display(alt_x.describe().T.round(3))
"""))

    # spec + correlation
    C.append(md(f"""
## 5. Model specification

The specification is the folder's script `model/{mod}.py`, imported as it is. The start values are the article estimates.
"""))
    C.append(code("""
print(inspect.getsource(M.model))
"""))
    if cfg["layout"] != "school":
        C.append(code("""
t0 = time.time()
database, ll = M.model()
used = nt.model_variables(ll)
print(f"database: {database.num_rows():,} rows; {len(used)} data columns used by the model; built in {time.time()-t0:.1f} s")
"""))
    C.append(md("""
## 6. Correlation of the explanatory variables

Correlations of the variables that enter the utility, computed over the alternatives available to each decision maker
(alternative-specific variables) and over decision makers (person and household variables). |r| ≥ 0.7 and VIF ≥ 10 are
listed. Interaction terms are correlated with their main effects by construction.
"""))
    if cfg["layout"] == "flat":
        C.append(code("""
Xu = nt.explanatory(df[[c for c in used if c in df.columns and c != "cars"]])
Cm = nt.corr_heatmap(Xu, "Household variables of the car ownership model")
display(nt.high_pairs(Cm)); display(nt.vif(Xu))
"""))
    elif cfg["layout"] == "wide":
        C.append(code("""
stems = sorted({c.rsplit("_", 1)[0] for c in used if c.rsplit("_", 1)[0] in alts and c.rsplit("_", 1)[-1].isdigit()}
               - {"av", "chosen_set", "zone", "stype"})
long = nt.explanatory(nt.stack_alternatives(df, stems))
print(f"{len(stems)} alternative-specific variables, {len(long):,} available alternatives")
Ca = nt.corr_heatmap(long, "Alternative-specific variables (available alternatives)")
display(nt.high_pairs(Ca)); display(nt.vif(long))
plain = [c for c in used if c in df.columns and c not in sum(alts.values(), []) and c not in ("choice", "weight")]
if len(plain) > 1:
    Xp = nt.explanatory(df[plain]); Cp = nt.corr_heatmap(Xp, "Decision-maker variables"); display(nt.high_pairs(Cp))
"""))
    else:
        C.append(code("""
Ca = nt.corr_heatmap(alt_x, "School-zone variables (sampled alternatives)")
display(nt.high_pairs(Ca)); display(nt.vif(alt_x))
Cp = nt.corr_heatmap(person, "Student variables"); display(nt.high_pairs(Cp))
"""))

    # check
    target = ck.get("biogeme_LL_at_article_coefficients")
    C.append(md(f"""
## 7. Log-likelihood at the article coefficients

No estimation: the log-likelihood at the start values (the article estimates). Target: article {ck.get('article_LL', '')},
Biogeme {target if target is not None else ''} (N = {ck.get('N', '')}, K = {ck.get('K', '')}).
"""))
    C.append(code(("" if cfg["layout"] != "school" else """
if RUN_CHECK or RUN_ESTIMATION:
    t0 = time.time(); database, ll = M.model(); print(f"database built in {time.time()-t0:.0f} s")
""") + f"""
if RUN_CHECK:
    p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
    here = os.getcwd(); os.chdir(__import__("tempfile").mkdtemp())
    t0 = time.time()
    b = bio.BIOGEME(database, ll, parameters=p); b.model_name = NAME + "_check"
    ll0 = b.calculate_init_likelihood()
    os.chdir(here)
    print(f"N {{database.num_rows():,}}   LL at the article coefficients: {{ll0:,.4f}}   (target {target})   {{time.time()-t0:.0f}} s")
else:
    print("skipped (RUN_CHECK = False)")
"""))

    # estimation
    C.append(md(f"""
## 8. Biogeme estimation

The same call as `model/{mod}.py`: Biogeme with its defaults (read from `output/biogeme.toml`), start values = article estimates.
Report written to `output/{name}.html`, `.yaml`, and `output/{name}_estimates.csv`.
""" + ("""
Weight: inside the log-likelihood (w·ln P), which gives the article's WESML sandwich standard errors. Biogeme's own
`weight` formula gives the same estimates with smaller robust s.e. (script option `--biogeme-weight`).
""" if weighted else "")))
    C.append(code("""
if RUN_ESTIMATION:
    here = os.getcwd(); os.chdir(OUT)
    t0 = time.time()
    b = bio.BIOGEME(database, ll); b.model_name = NAME
    results = b.estimate()
    os.chdir(here)
    print(f"estimation time {time.time()-t0:.0f} s"); print(results.short_summary())
    nt.estimates_table(results)[["parameter", "coefficient", "robust_se", "t", "p"]].rename(
        columns={"coefficient": "Value", "robust_se": "Robust std err.", "t": "Robust t-stat.", "p": "Robust p-value", "parameter": "Name"}
    ).to_csv(os.path.join(OUT, f"{NAME}_estimates.csv"), index=False)
else:
    y = sorted(glob.glob(os.path.join(OUT, f"{NAME}*.yaml")), key=os.path.getmtime)
    results = EstimationResults.from_yaml_file(y[-1]) if y else None
    print(f"RUN_ESTIMATION = False: read {os.path.basename(y[-1])}" if y else "RUN_ESTIMATION = False and no result in output/: sections 9-10 are skipped")
"""))

    # results
    C.append(md("## 9. Results\n\n### Estimates in the article format\nCoefficient (stars: *** p < 0.001, ** p < 0.01, * p < 0.05), robust s.e., p."))
    C.append(code("""
if results is not None:
    est_t = nt.estimates_table(results)
    display(nt.article_format(est_t))
"""))
    C.append(md("### Goodness of fit"))
    C.append(code("""
if results is not None:
    display(nt.fit_statistics(results))
"""))
    C.append(md("### Comparison with the article (`model/reference_estimates.csv`)"))
    C.append(code("""
if results is not None:
    REF = os.path.join(FOLDER, "model", "reference_estimates.csv")
    cmp = nt.compare(est_t, REF)
    cmp.to_csv(os.path.join(OUT, "comparison_with_article_notebook.csv"), index=False)
    print(f"{int(cmp.matches_article.sum())} of {len(cmp)} parameters match the article (coefficient and robust s.e. within the 4th-decimal rounding); "
          f"largest |difference|: coefficient {cmp.diff_coef.abs().max():.5f}, s.e. {cmp.diff_se.abs().max():.5f}")
    display(cmp.round({"coefficient": 4, "robust_se": 4, "p": 4, "diff_coef": 5, "diff_se": 5}))
    stats = nt.article_statistics(REF)
    if len(stats):
        stats["Biogeme"] = stats["statistic"].map({"LL(beta)": results.final_loglikelihood, "N": database.num_rows() if "database" in dir() else None,
                                                   "K": results.number_of_free_parameters})
        display(stats)
    nt.plot_against_article(cmp, RUN.get("model", NAME))
"""))
    C.append(md("### Correlation of the estimates\nRobust correlation matrix of the estimated parameters; pairs with |r| ≥ 0.7 listed."))
    C.append(code("""
if results is not None:
    display(nt.parameter_correlation(results, "Robust correlation of the estimates"))
"""))

    # holdout
    C.append(md("## 10. Hold-out sample"))
    if cfg["holdout"]:
        hp = cfg["holdout"]
        C.append(code(f"""
if RUN_HOLDOUT and results is not None:
    import tempfile
    est_data = M.DATA
    M.DATA = os.path.join(FOLDER, "input", "data", "holdout", {hp!r})
    try:
        hdb, hll = M.model(start=results.get_beta_values())
    finally:
        M.DATA = est_data
    p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
    here = os.getcwd(); os.chdir(tempfile.mkdtemp())
    b = bio.BIOGEME(hdb, hll, parameters=p); b.model_name = NAME + "_holdout"
    llh = b.calculate_init_likelihood(); os.chdir(here)
    print(f"hold-out: N {{hdb.num_rows():,}}   LL at your estimates {{llh:,.2f}}   mean LL per observation {{llh/hdb.num_rows():.4f}}")
    print(f"estimation sample: mean LL per observation {{results.final_loglikelihood/database.num_rows():.4f}}")
else:
    print("skipped (RUN_HOLDOUT = False or no estimates)")
"""))
    else:
        C.append(md("The hold-out of this model is stored in another layout (the full choice set; see `input/data/holdout` and "
                    "`model/README.md`); its log-likelihood is computed by the project's validation scripts, not in this notebook."))
    return C


def sys_py():
    return os.path.expanduser("~/.venvs/biogeme/bin/python")


def setup_cell(flags, name):
    return code(flags + f"""
import os, sys, json, glob, inspect, importlib, time
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from biogeme.results_processing import EstimationResults

FOLDER = os.path.abspath("")                       # this model folder (VS Code starts the notebook here)
sys.path.insert(0, os.path.join(FOLDER, "..", "..", "tools")); import nbtools as nt
sys.path.insert(0, os.path.join(FOLDER, "model"))
RUN = json.load(open(os.path.join(FOLDER, "RUN.json")))
OUT = os.path.join(FOLDER, "output"); os.makedirs(OUT, exist_ok=True)
NAME = "{name}"
pd.set_option("display.max_rows", 200, "display.max_columns", 60, "display.width", 200)
plt.rcParams.update({{"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False}})
print("model folder:", FOLDER)
""")


def prep_cells(R, local_root="model folder"):
    up, prep = steps(R)
    lines = ["## 2. Data preparation", "",
             "Shared and upstream stages (outputs provided in `../00_shared_data` and `input/data/raw`; run them only for a full rebuild from the raw data; "
             "`cd` paths from this model folder):", ""]
    for s in up:
        lines.append(f"- **Step {s.get('step')}.** {s.get('what', '')}  \n  `cd {s.get('cwd')}` → `{s.get('command', '')}`")
    lines += ["", "Package steps, run below when `RUN_DATA_PREP = True`: they rebuild `input/data/estimation` and `input/data/holdout`; "
              "`check_against_provided.py` compares the rebuilt tables with the provided ones."]
    C = [md("\n".join(lines))]
    for s in prep:
        cmd = s.get("command", "").replace("~/.venvs/biogeme/bin/python", sys_py())
        cwd = (s.get("cwd") or ".").lstrip("./")
        C.append(md(f"**Step {s.get('step')}.** {s.get('what', '')}" + (f" (about {s['minutes']} min)" if isinstance(s.get("minutes"), (int, float)) else "")))
        C.append(code(f"""
if RUN_DATA_PREP:
    nt.run({cmd!r}, cwd=os.path.join(FOLDER, {cwd!r}))
else:
    print("skipped (RUN_DATA_PREP = False): the provided tables are used")
"""))
    return C


def results_cells(stats_n="N"):
    C = [md("## 9. Results\n\n### Estimates in the article format\nCoefficient (stars: *** p < 0.001, ** p < 0.01, * p < 0.05), robust s.e., p.")]
    C.append(code("""
if results is not None:
    est_t = nt.estimates_table(results)
    display(nt.article_format(est_t))
"""))
    C.append(md("### Goodness of fit"))
    C.append(code("""
if results is not None:
    display(nt.fit_statistics(results))
"""))
    C.append(md("### Comparison with the article (`model/reference_estimates.csv`)"))
    C.append(code(f"""
if results is not None:
    REF = os.path.join(FOLDER, "model", "reference_estimates.csv")
    cmp = nt.compare(est_t, REF)
    cmp.to_csv(os.path.join(OUT, "comparison_with_article_notebook.csv"), index=False)
    print(f"{{int(cmp.matches_article.sum())}} of {{len(cmp)}} parameters match the article (coefficient and robust s.e. within the 4th-decimal rounding); "
          f"largest |difference|: coefficient {{cmp.diff_coef.abs().max():.5f}}, s.e. {{cmp.diff_se.abs().max():.5f}}")
    display(cmp.round({{"coefficient": 4, "robust_se": 4, "p": 4, "diff_coef": 5, "diff_se": 5}}))
    stats = nt.article_statistics(REF)
    if len(stats):
        stats["Biogeme"] = stats["statistic"].map({{"LL(beta)": results.final_loglikelihood, "K": results.number_of_free_parameters, "N": {stats_n}}})
        display(stats)
    nt.plot_against_article(cmp, RUN.get("model", NAME))
"""))
    C.append(md("### Correlation of the estimates\nRobust correlation matrix of the estimated parameters; pairs with |r| ≥ 0.7 listed."))
    C.append(code("""
if results is not None:
    display(nt.parameter_correlation(results, "Robust correlation of the estimates"))
"""))
    return C


def abit_notebook(folder, R):
    d = f"{ROOT}/ABIT/{folder}"
    mod = next(f for f in os.listdir(f"{d}/model") if f.startswith("estimate_"))[:-3]
    src = open(f"{d}/model/{mod}.py").read()
    m = re.search(r'^NAME = "(\w+)"', src, re.M) or re.search(r'model_name = "(\w+)"', src)
    name = m.group(1) if m else mod[len("estimate_"):]
    location = bool(glob_any(f"{d}/input/data/estimation", "biogeme_part"))
    ck = R.get("check") or {}
    est_steps = [s for s in R.get("steps", []) if (s.get("cwd") or "").startswith("model") and "--evaluate" not in s.get("command", "")
                 and "compare" not in s.get("command", "")]
    chk_steps = [s for s in R.get("steps", []) if "--evaluate" in s.get("command", "")]
    heavy_est = any(not isinstance(s.get("minutes"), (int, float)) or s["minutes"] > 30 for s in est_steps)
    heavy_chk = any(not isinstance(s.get("minutes"), (int, float)) or s["minutes"] > 30 for s in chk_steps)
    has_hold = os.path.isdir(f"{d}/input/data/holdout") and bool(os.listdir(f"{d}/input/data/holdout"))
    C = [md(f"""
# {R.get('model', folder)}

{R.get('purpose', '')}

This notebook goes from the raw data to the estimates of this model:

1. Raw data
2. Data preparation
3. Estimation data
4. Descriptive statistics
5. Correlation of the explanatory variables (heatmaps, VIF)
6. Model specification (the folder's `model/{mod}.py`, unchanged)
7. Log-likelihood at the article coefficients
8. Biogeme estimation
9. Results: article format, fit, comparison with the article, correlation of the estimates
10. Hold-out sample

**Kernel:** select *Python (biogeme)* (`~/.venvs/biogeme`) in VS Code, then *Run All*. The switches in the next cell decide what is recomputed.
""")]
    flags = f"""
RUN_DATA_PREP  = False   # True: rebuild the estimation tables (section 2)
RUN_CHECK      = {not heavy_chk}    # log-likelihood at the article coefficients{'  (this model: longer than 30 min)' if heavy_chk else ''}
RUN_ESTIMATION = {not heavy_est}    # Biogeme estimation, written to output/{'  (this model: beyond the memory of this machine, see RUN.json notes; False reads output/ if a result is there)' if heavy_est else ''}
RUN_HOLDOUT    = {has_hold and not heavy_chk}    # log-likelihood of the hold-out half at the full-precision estimates
"""
    C.append(setup_cell(flags, name))
    C.append(md(sources_md(R)))
    C.append(code("""
raw = os.path.join(FOLDER, "input", "data", "raw")
if os.path.isdir(raw):
    display(nt.files_table(raw))
    for f in sorted(glob.glob(os.path.join(raw, "*")))[:6]:
        head, n = nt.preview(f)
        if head is not None:
            print(f"\\n{os.path.basename(f)}" + (f"  ({n:,} rows)" if n else ""))
            display(head)
shared = os.path.join(FOLDER, "..", "00_shared_data")
print("shared data folders:", sorted(os.listdir(shared)))
"""))
    C += prep_cells(R)
    C.append(md("## 3. Estimation data\n\nThe tables exactly as used in the estimation, and the data dictionary."))
    C.append(code(f"""
import {mod} as M
est = os.path.join(FOLDER, "input", "data", "estimation")
display(nt.files_table(est))
dd = pd.read_csv(os.path.join(est, "data_dictionary.csv")) if os.path.exists(os.path.join(est, "data_dictionary.csv")) else None
dd
"""))
    if location:
        C.append(code("""
# Biogeme table: one row per record; imp_<c>_<zone>, cgt_<c>_<zone> = zone variables of configuration c for all zones,
# cand_* / b_* = the candidate zones of the observed location and their weights. Only the first two parts are read here.
meta = json.load(open(os.path.join(est, "biogeme_meta.json")))
print({k: v for k, v in meta.items() if k != "parts"})
parts = sorted(glob.glob(os.path.join(est, "biogeme_part*.parquet")))
df = pd.concat([pd.read_parquet(p) for p in parts[:2]], ignore_index=True)
print(f"{len(parts)} parts; read {len(df):,} of {meta['N']:,} records, {df.shape[1]:,} columns")
rec_f = os.path.join(est, "records.parquet")
records = pd.read_parquet(rec_f) if os.path.exists(rec_f) else None
display(records.head() if records is not None else df.iloc[:5, :30])
ZONES = pd.read_csv(os.path.join(FOLDER, "..", "00_shared_data", "zones", "zones_model_attributes.csv"))
"""))
    else:
        C.append(code("""
r = M.read("estimation")
df = r[0] if isinstance(r, tuple) else r
print(f"{df.shape[0]:,} rows, {df.shape[1]} columns")
df.head()
"""))
    C.append(md("## 4. Descriptive statistics"))
    if location:
        C.append(code("""
person = nt.explanatory(df[[c for c in df.columns if c.startswith("f_")]])
display(person.describe().T.round(3))
if "purpose_id" in df and records is not None and "purpose" in records:
    display(records["purpose"].value_counts().rename("records").to_frame())
if "n_cand" in df:
    ax = df["n_cand"].value_counts().sort_index().plot.bar(figsize=(5, 3), color="#2b6cb0", rot=0)
    ax.set_xlabel("candidate zones of the observed location"); ax.set_ylabel("records"); plt.show()
if records is not None:
    display(nt.explanatory(records).describe().T.round(3))
"""))
    else:
        C.append(code("""
ycol = "y" if "y" in df else None
if ycol:
    c = df[ycol].value_counts().sort_index()
    t = c.rename("observations").to_frame(); t["share %"] = (100 * c / c.sum()).round(2)
    av = [x for x in df.columns if x.startswith("av_")]
    display(t)
    if av:
        display(df[av].mean().round(3).rename("share available").to_frame())
    ax = t["share %"].plot.bar(figsize=(5, 3), color="#2b6cb0", rot=0); ax.set_title("Chosen alternative (code y; see the data dictionary)"); plt.show()
wcol = next((w for w in ["wesml", "w", "weight"] if w in df), None)
if wcol:
    print(f"weight column {wcol}: mean {df[wcol].mean():.3f}, min {df[wcol].min():.3f}, max {df[wcol].max():.3f}")
X = nt.explanatory(df.drop(columns=[c for c in df.columns if c.startswith("av_") or c in ("y", "wesml", "w", "weight", "row_index")]))
display(X.describe().T.round(3))
"""))
    C.append(md(f"## 5. Model specification\n\nThe folder's script `model/{mod}.py`, imported as it is. Its utility functions:"))
    C.append(code("""
src = inspect.getsource(M)
print(src[:src.find("def read(")])
"""))
    C.append(md("""
## 6. Correlation of the explanatory variables

|r| ≥ 0.7 and VIF ≥ 10 are listed. Interaction terms are correlated with their main effects by construction.
"""))
    if location:
        C.append(code("""
long = nt.explanatory(nt.location_long(df, ZONES))
print(f"zone variables of {min(300, len(df))} records x {len(ZONES):,} zones = {len(long):,} rows")
Cz = nt.corr_heatmap(long, "Destination variables (impedance, generalised time, zone attributes)")
display(nt.high_pairs(Cz)); display(nt.vif(long))
Cp = nt.corr_heatmap(person, "Person and tour variables of the records"); display(nt.high_pairs(Cp))
"""))
    else:
        C.append(code("""
f = M.formulas() if hasattr(M, "formulas") else M.loglike()
expr = f["loglike"] if isinstance(f, dict) else f
used = [c for c in nt.model_variables(expr) if c in df and not c.startswith("av_") and c not in ("y", "wesml", "w", "weight")]
Xu = nt.explanatory(df[used])
print(f"{len(used)} data columns enter the utilities")
Cu = nt.corr_heatmap(Xu, "Variables of the utilities")
display(nt.high_pairs(Cu)); display(nt.vif(Xu))
"""))
    target = ck.get("biogeme_LL_at_article_coefficients") or ck.get("biogeme_LL_at_reference_coefficients") or ck.get("biogeme_LL_at_full_precision_coefficients")
    C.append(md(f"""
## 7. Log-likelihood at the article coefficients

No estimation: the script's `evaluate("estimation", "article")`. Target: article {ck.get('article_LL', ck.get('reference_LL', ''))},
Biogeme {target if target is not None else ''} (N = {ck.get('N', '')}, K = {ck.get('K', '')}).
"""))
    C.append(code("""
def evaluate(half, at):
    here = os.getcwd()
    try:
        return M.evaluate(half, at) if "at" in inspect.signature(M.evaluate).parameters else M.evaluate(half)
    finally:
        os.chdir(here)

if RUN_CHECK:
    t0 = time.time(); ll_article = evaluate("estimation", "article"); print(f"{time.time()-t0:.0f} s")
else:
    print("skipped (RUN_CHECK = False)")
"""))
    C.append(md(f"""
## 8. Biogeme estimation

The script's `estimate()`: Biogeme with its defaults (`output/biogeme.toml`), robust standard errors. Report in
`output/{name}.html` and `.yaml`; table `output/estimated_parameters.csv`.
"""))
    C.append(code("""
if RUN_ESTIMATION:
    here = os.getcwd(); t0 = time.time()
    try:
        M.estimate(OUT)
    finally:
        os.chdir(here)
    print(f"estimation time {time.time()-t0:.0f} s")
y = [f for f in sorted(glob.glob(os.path.join(OUT, "*.yaml")), key=os.path.getmtime) if "eval" not in os.path.basename(f)]
results = EstimationResults.from_yaml_file(y[-1]) if y else None
print(f"results read from {os.path.basename(y[-1])}" if y else "no result in output/: sections 9-10 are skipped")
"""))
    C += results_cells(stats_n=str(ck.get("N")) if ck.get("N") else "None")
    C.append(md("## 10. Hold-out sample\n\nLog-likelihood of the hold-out half at the full-precision estimates (`evaluate(\"holdout\", \"full\")`)."))
    C.append(code("""
if RUN_HOLDOUT:
    ll_hold = evaluate("holdout", "full")
else:
    print("skipped (RUN_HOLDOUT = False)")
"""))
    return C


def tasha_notebook(R):
    C = [md(f"""
# {R.get('model', 'TASHA distributions')}

{R.get('purpose', '')}

Not a Biogeme model: empirical distributions from the estimation half of the survey. Sections: 1. raw data,
2. building the distributions, 3. comparison with the files used by the model runs, 4. the distributions as charts.
"""), code("""
RUN_BUILD = False   # True: rebuild the distributions into output/ (about 10 s)
import os, sys, json, glob
import numpy as np, pandas as pd, matplotlib.pyplot as plt
FOLDER = os.path.abspath("")
sys.path.insert(0, os.path.join(FOLDER, "..", "..", "tools")); import nbtools as nt
RUN = json.load(open(os.path.join(FOLDER, "RUN.json")))
REF = os.path.join(FOLDER, "data", "reference_outputs")
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})
"""), md(sources_md(R))]
    C += prep_cells(R)
    for s in R.get("steps", []):
        if (s.get("cwd") or "").startswith("code"):
            C.append(md(f"**Step {s.get('step')}.** {s.get('what', '')}"))
            C.append(code(f"""
if RUN_BUILD:
    nt.run({s.get('command', '')!r}, cwd=os.path.join(FOLDER, "code"))
else:
    print("skipped (RUN_BUILD = False)")
"""))
    C.append(md("## 3. Files\n\n`data/reference_outputs` holds the files used by the model runs; `output/` your rebuild."))
    C.append(code("""
display(nt.files_table(REF))
src = os.path.join(FOLDER, "output") if glob.glob(os.path.join(FOLDER, "output", "tasha_*.csv")) else REF
print("charts below from:", os.path.relpath(src, FOLDER))
def probs(t):
    return np.vstack(t["probs"].map(lambda s: np.array([float(x) for x in str(s).split(";")])).to_numpy())
"""))
    C.append(md("## 4. The distributions\n\n### Frequency P(n | type, segment, household, prior): mean episodes per person-day"))
    C.append(code("""
fq = pd.read_csv(os.path.join(src, "tasha_frequency.csv"))
fq = fq[fq["level"] == fq["level"].iloc[0]] if "level" in fq else fq
m = fq.groupby(["type", "seg"]).apply(lambda g: np.average(g["mean"], weights=g["n"])).unstack()
fig, ax = plt.subplots(figsize=(1.1 * m.shape[1] + 3, 0.45 * m.shape[0] + 1.5))
im = ax.imshow(m.values, cmap="Blues"); plt.colorbar(im, ax=ax, label="mean episodes")
ax.set_xticks(range(m.shape[1])); ax.set_xticklabels(m.columns, rotation=45, ha="right"); ax.set_yticks(range(m.shape[0])); ax.set_yticklabels(m.index)
for i in range(m.shape[0]):
    for j in range(m.shape[1]):
        if np.isfinite(m.values[i, j]): ax.text(j, i, f"{m.values[i, j]:.2f}", ha="center", va="center", fontsize=7, color="white" if m.values[i, j] > np.nanmax(m.values) * 0.6 else "black")
ax.set_title("Mean episodes per person-day (weighted by cell size)"); plt.tight_layout(); plt.show()
"""))
    C.append(md("### Start time P(t | type, …): 15-minute bins from midnight, averaged over the cells of each type"))
    C.append(code("""
stt = pd.read_csv(os.path.join(src, "tasha_start.csv"))
P = probs(stt); hours = np.arange(P.shape[1]) * 0.25
types = sorted(stt["type"].unique())
fig, axes = plt.subplots(int(np.ceil(len(types) / 4)), 4, figsize=(15, 2.3 * np.ceil(len(types) / 4)), sharex=True)
for ax, t in zip(axes.flat, types):
    i = (stt["type"] == t).to_numpy(); w = stt.loc[i, "n"].to_numpy()
    ax.fill_between(hours, (P[i] * w[:, None]).sum(0) / w.sum(), step="mid", color="#2b6cb0", alpha=0.8); ax.set_title(t, fontsize=9)
for ax in axes.flat[len(types):]: ax.axis("off")
fig.supxlabel("start (hour of day)"); plt.tight_layout(); plt.show()
"""))
    C.append(md("### Duration P(δ | type, …): 5-minute bins to 2 h, then 15 minutes"))
    C.append(code("""
du = pd.read_csv(os.path.join(src, "tasha_duration.csv"))
edges = np.array(list(range(0, 121, 5)) + list(range(135, 1441, 15)), float); mids = (edges[:-1] + edges[1:]) / 2 / 60
P = probs(du)[:, :len(mids)]
types = sorted(du["type"].unique())
fig, axes = plt.subplots(int(np.ceil(len(types) / 4)), 4, figsize=(15, 2.3 * np.ceil(len(types) / 4)), sharex=True)
for ax, t in zip(axes.flat, types):
    i = (du["type"] == t).to_numpy(); w = du.loc[i, "n"].to_numpy()
    dens = (P[i] * w[:, None]).sum(0) / w.sum() / np.diff(edges) * 60
    ax.plot(mids, dens, color="#2b6cb0"); ax.set_xlim(0, 12); ax.set_title(t, fontsize=9)
for ax in axes.flat[len(types):]: ax.axis("off")
fig.supxlabel("duration (hours)"); fig.supylabel("density per hour"); plt.tight_layout(); plt.show()
"""))
    C.append(md("### Joint episodes and location bands"))
    C.append(code("""
for f in ["tasha_joint_propensity.csv", "tasha_joint_propensity_mand.csv", "tasha_joint_participants.csv", "tasha_location_bands.csv", "tasha_params.csv"]:
    p = os.path.join(src, f)
    if os.path.exists(p):
        print(f); display(pd.read_csv(p))
"""))
    return C


def glob_any(folder, prefix):
    return os.path.isdir(folder) and any(f.startswith(prefix) for f in os.listdir(folder))


def write(nb_cells, path):
    nb = nbf.v4.new_notebook()
    nb.cells = nb_cells
    nb.metadata["kernelspec"] = {"name": "biogeme", "display_name": "Python (biogeme)", "language": "python"}
    nbf.write(nb, path)


def main():
    import sys
    only = sys.argv[1:]
    n = 0
    for folder, cfg in SILO.items():
        if only and folder not in only:
            continue
        d = f"{ROOT}/SILO/{folder}"
        write(silo_notebook(folder, cfg, json.load(open(f"{d}/RUN.json"))), f"{d}/{folder}_estimation.ipynb"); n += 1
    for folder in sorted(os.listdir(f"{ROOT}/ABIT")):
        d = f"{ROOT}/ABIT/{folder}"
        if (only and folder not in only) or not os.path.exists(f"{d}/RUN.json"):
            continue
        R = json.load(open(f"{d}/RUN.json"))
        if folder == "00_tasha_distributions":
            write(tasha_notebook(R), f"{d}/{folder}.ipynb"); n += 1
        elif os.path.isdir(f"{d}/model") and any(f.startswith("estimate_") for f in os.listdir(f"{d}/model")):
            write(abit_notebook(folder, R), f"{d}/{folder}_estimation.ipynb"); n += 1
    print(f"{n} notebooks written")


if __name__ == "__main__":
    main()
