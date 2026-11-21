#!/usr/bin/env python3
"""Write <folder>_estimation.ipynb in every SILO and MAST model folder (00_tasha_distributions.ipynb for the TASHA distributions): raw data -> data preparation -> estimation data -> descriptive
statistics and correlation heatmaps -> model specification -> log-likelihood at the article values -> Biogeme
estimation -> comparison with the article -> hold-out.

The notebooks call the folder's own model/estimate_*.py (model() and DATA), so the specification is the one of the
scripts; nothing is re-specified here.
Usage: python3 tools/build_notebooks.py            (from manual_estimation/)
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbformat as nbf
import nb_walk as W
import nb_reader as RD
import shutil

HEAVY_CHECK = {"01_primary_destination_pooled", "02_stop_shopping", "03_stop_recreation", "04_stop_accompanying", "05_stop_other"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# per model: estimation data layout and the hold-out that model() can read by swapping DATA
SILO = {
    "01_residential_puma":                {"layout": "wide", "holdout": "puma_holdout.parquet", "heavy": False},
    "02_residential_dwelling":            {"layout": "wide", "holdout": "dwelling_holdout.parquet", "heavy": False},
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


INTERNAL = re.compile(r"respec|pre1117|_v2\b|_v3\b|\bv[23]\b|2_silo|3_abit|side_experiments|Validation_2026|/Use[r]s/|coef_respec|1110\.sh", re.I)


def clean(t):
    """Text from RUN.json without sentences that name internal folders, runs or versions."""
    if not t:
        return ""
    parts = re.split(r"(?<=[.;])\s+", str(t))
    return " ".join(x for x in parts if not INTERNAL.search(x))


def sources_md(R, heading="## 1. Raw data"):
    out = [heading, "",
           "Where each source comes from and where it goes (paths from `manual_estimation/`). "
           "*verify*: no download link is recorded in the project. The full download steps are in `INSTRUCTIONS.pdf`.", ""]
    for d in R.get("data_sources") or []:
        out.append(f"**{clean(d.get('name', ''))}**" + (f" — {clean(d['provider'])}" if d.get("provider") else ""))
        if d.get("url"):
            u = d["url"] if not INTERNAL.search(d["url"]) else " ".join(re.findall(r"https?://[^\s,;)]+", d["url"]))
            if u:
                out.append(f"- Where: {u}")
        if d.get("how"):
            h = d["how"] if isinstance(d["how"], list) else [d["how"]]
            out.append("- How: " + clean(" ".join(h)))
        if d.get("place_in"):
            out.append(f"- Put in: {clean(d['place_in'])}")
        if d.get("files"):
            f = d["files"] if isinstance(d["files"], list) else [d["files"]]
            out.append("- Files: " + ", ".join(f"`{x}`" for x in f if not INTERNAL.search(x)))
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
    mod = next(f for f in sorted(os.listdir(f"{ROOT}/SILO/{folder}/model")) if f.startswith("estimate_") and f.endswith(".py") and "_pre" not in f)[:-3]
    src = open(f"{ROOT}/SILO/{folder}/model/{mod}.py").read()
    name = [n for n in re.findall(r'model_name = "(\w+)"', src) if not n.endswith("_check")][0]
    weighted = "--biogeme-weight" in src
    ck = R.get("check") or {}
    chk_min = max([s["minutes"] for s in R.get("steps", []) if "--check" in s.get("command", "") and isinstance(s.get("minutes"), (int, float))] or [0])
    C = []

    C.append(md(RD.answers_md(folder, R)))
    C.append(md(RD.how_to_run_md(folder, cfg)))
    C.append(md(f"""
## Contents

Article table: `{R.get('article_table', '')}`. This notebook goes from the raw records to the estimates of this model:

1. Raw data
2. Data preparation: filters from the raw records to the estimation sample (records kept and dropped), rebuild check
3. Estimation data and choice set
4. Descriptive statistics and figures; 4.1 every explanatory variable of the model in the data{SILO_EXTRA_TOC.get(folder, "")}
5. Model specification (the folder's `model/{mod}.py`, unchanged)
6. Correlation of the explanatory variables (heatmaps, VIF)
7. Log-likelihood at the article coefficients
8. Biogeme estimation
9. Results: article format, fit, comparison with the article, correlation of the estimates
10. Hold-out sample

11. Glossary
"""))
    C.append(md(RD.glance_md(folder)))
    flags = f"""
RUN_DATA_PREP  = True    # rebuild the estimation sample and tables into output/rebuild_check and compare with the shipped tables (section 2)
RUN_CHECK      = True    # log-likelihood at the article coefficients{'  (this model: ' + str(round(chk_min)) + ' min)' if chk_min > 5 else ''}
RUN_ESTIMATION = False   # Biogeme estimation, written to output/ (False: results are read from output/ if there are any){'  (this model: several hours and more than 8 GB)' if cfg['heavy'] else ''}
RUN_HOLDOUT    = {bool(cfg['holdout']) and folder != '06_school_location_K8'}    # log-likelihood of the hold-out sample (at your estimates if there are any, else at the article coefficients){'  (this model: as long as the check)' if folder == '06_school_location_K8' else ''}
"""
    C.append(code(flags + f"""
import os, sys, json, glob, inspect, importlib, time, re
import numpy as np, pandas as pd, matplotlib.pyplot as plt
import biogeme.biogeme as bio
from biogeme.parameters import Parameters
from biogeme.results_processing import EstimationResults

FOLDER = os.path.abspath("")                       # this model folder (VS Code starts the notebook here)
sys.path.insert(0, os.path.join(FOLDER, "..", "..", "tools")); import nbtools as nt; import nb_reader as rd; import figs as fg
fg = importlib.reload(fg)
from IPython.display import Markdown
sys.path.insert(0, os.path.join(FOLDER, "model"))
RUN = json.load(open(os.path.join(FOLDER, "RUN.json")))
OUT = os.path.join(FOLDER, "output"); os.makedirs(OUT, exist_ok=True)
NAME = "{name}"; MODEL_FOLDER = "{folder}"
pd.set_option("display.max_rows", 200, "display.max_columns", 60, "display.width", 200)
plt.rcParams.update({{"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False}})
print("model folder:", os.path.basename(FOLDER))
"""))

    C += sample_size_cells(folder)
    C += W.silo_cells(folder)
    C.append(md(sources_md(R, heading="### Data sources")))
    # estimation data
    C.append(md("## 3. Estimation data and choice set\n\n" + SILO_CHOICE[folder] + "\n\nThe table exactly as used in the estimation, and its data dictionary."))
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
    C += W.silo_desc(folder)
    C.append(code(SILO_DEFS[cfg["layout"]]))
    C += silo_var_cells(folder, cfg)
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
    ref_time = os.path.getmtime(os.path.join(FOLDER, "model", "reference_estimates.csv"))
    y = [f for f in sorted(glob.glob(os.path.join(OUT, f"{NAME}*.yaml")), key=os.path.getmtime) if os.path.getmtime(f) > ref_time and "_check" not in f]
    results = EstimationResults.from_yaml_file(y[-1]) if y else None
    print(f"RUN_ESTIMATION = False: read {os.path.basename(y[-1])} (newer than model/reference_estimates.csv)" if y else "RUN_ESTIMATION = False and no current result in output/: sections 9-10 are skipped")
"""))

    # results
    C.append(md("## 9. Results\n\n### Estimates in the article format\nCoefficient (stars: *** p < 0.01, ** p < 0.05, * p < 0.10, as in the article), robust s.e., p."))
    C.append(code("""
if results is not None:
    est_t = nt.estimates_table(results)
    display(nt.article_format(est_t))
"""))
    C.append(md("### What the coefficients say\n\nOne plain line per term, from your estimates (from the article estimates if there are none). "
                "Income interactions are given at $25k, $50k and $100k; odds change = exp(coefficient) per unit."))
    C.append(code("""
# plain readings of the coefficients and the coefficient plot (95 % robust intervals, grouped by block)
est_v = est_t if results is not None else rd.reference(MODEL_FOLDER)[0]
display(rd.readings(MODEL_FOLDER, est_v).style.hide(axis="index").set_properties(**{"text-align": "left"}))
fg.coef_figure(fg.coef_rows(MODEL_FOLDER, est_v)); plt.show()
"""))
    C.append(md("How to read it: a point right of zero makes the alternative more likely; an interval that crosses zero is not significant."))
    C += effect_cells(folder)
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
if RUN_HOLDOUT:
    import tempfile
    est_data = M.DATA
    M.DATA = os.path.join(FOLDER, "input", "data", "holdout", {hp!r})
    at = "your estimates" if results is not None else "the article coefficients"
    try:
        hdb, hll = M.model(start=results.get_beta_values() if results is not None else None)
    finally:
        M.DATA = est_data
    p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
    here = os.getcwd(); os.chdir(tempfile.mkdtemp())
    b = bio.BIOGEME(hdb, hll, parameters=p); b.model_name = NAME + "_holdout"
    llh = b.calculate_init_likelihood(); os.chdir(here)
    print(f"hold-out: N {{hdb.num_rows():,}}   LL at {{at}} {{llh:,.2f}}   mean LL per observation {{llh/hdb.num_rows():.4f}}")
    if results is not None:
        print(f"estimation sample: mean LL per observation {{results.final_loglikelihood/database.num_rows():.4f}}")
else:
    print("skipped (RUN_HOLDOUT = False)")
"""))
    else:
        C.append(md("The hold-out of this model is stored in another layout (the full choice set; see `input/data/holdout` and "
                    "`model/README.md`); its log-likelihood is computed by the project's validation scripts, not in this notebook."))
    C += holdout_extra(folder)
    C.append(md(RD.glossary_md(folder)))
    return finish_silo(C, folder)


# ------------------------------------------------------------------------------------------------ reader layer (SILO)
HOLD_SRC = os.path.join(os.path.dirname(ROOT), "side_experiments", "respec_2026-11", "step_by_step")
HOLD_FILES = {
    "05_workplace_choice": {"holdout_map.png": "workplace/w12_holdout_map.png", "holdout_puma.csv": "workplace/w12_holdout_puma.csv",
                            "holdout_county.csv": "workplace/w12_holdout_county.csv"},
}
for _f in ("06_school_location_K8", "07_school_location_high_school", "08_school_location_college"):
    HOLD_FILES[_f] = {"holdout_map.png": "locations/l12_holdout_map.png", "holdout_puma.csv": "locations/l12_holdout_puma.csv",
                      "holdout_county.csv": "locations/l12_holdout_county.csv", "holdout_stats.csv": "locations/l12_holdout_stats.csv"}
_MD = {"01_primary_destination_pooled": "dest_pooled", "02_stop_shopping": "stop_shopping", "03_stop_recreation": "stop_recreation", "04_stop_accompanying": "stop_accompanying",
       "05_stop_other": "stop_other", "06_outing_first_stop_destination": "outing_dest", "07_work_business_usual_workplace": "loc_wbwork",
       "08_work_business_other_persons": "loc_wbother", "09_work_trips_home_workers": "loc_wahb", "10_school_daycare_without_record_pooled": "loc_edu"}
ABIT_HOLD = {f: {"holdout_map.png": f"milesday/m12_{sh}_holdout_map.png", "holdout_puma.csv": f"milesday/m12_{sh}_holdout_puma.csv",
                 "holdout_county.csv": f"milesday/m12_{sh}_holdout_county.csv", "holdout_stats.json": f"milesday/m12_{sh}_holdout_stats.json"} for f, sh in _MD.items()}
BAND = {"06_school_location_K8": "k8", "07_school_location_high_school": "hs", "08_school_location_college": "college"}


def copy_holdout(folder):
    """copy the hold-out map and its tables of the project into the folder's output/ (the notebook reads them there)"""
    if folder == "01_residential_puma":
        return resloc_holdout()
    for dst, src in HOLD_FILES.get(folder, {}).items():
        shutil.copy2(os.path.join(HOLD_SRC, src), os.path.join(ROOT, "SILO", folder, "output", dst))


def resloc_holdout():
    """residential location, PUMA level: hold-out map and tables of the adopted model only (observed, model, model minus
    observed), from the project's hold-out shares (residential/r22_holdout_puma.csv, r22_county_before_after.csv, r22_fit.csv)"""
    import pandas as pd
    sys.path.insert(0, HOLD_SRC); import holdout_maps as HM
    out = os.path.join(ROOT, "SILO", "01_residential_puma", "output")
    P = pd.read_csv(os.path.join(HOLD_SRC, "residential", "r22_holdout_puma.csv"))
    P = pd.DataFrame({"puma7": P.puma7, "observed_pct": P.observed_pct, "model_pct": P.r22_model_pct, "diff_pp": P.r22_diff_pp})
    C = pd.read_csv(os.path.join(HOLD_SRC, "residential", "r22_county_before_after.csv")); C = C[C.half == "holdout"]
    C = pd.DataFrame({"county": C.county, "observed_pct": C.observed_pct, "model_pct": C.r22_model_pct, "diff_pp": C.r22_diff_pp})
    P.to_csv(os.path.join(out, "holdout_puma.csv"), index=False); C.to_csv(os.path.join(out, "holdout_county.csv"), index=False)
    f = pd.read_csv(os.path.join(HOLD_SRC, "residential", "r22_fit.csv")).set_index("model").loc["r22"]
    n = int(f.validation_N); sp = HM.stats(P)
    ext = HM.bounds(HM.BW); zb = HM.bounds([24510, 24005], 2000)
    bins = [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 6.0]
    rows = [dict(table=P, level="puma", who="movers", label="Baltimore\u2013Washington", extent=ext, box=zb, bins=bins),
            dict(table=P, level="puma", who="movers", label="Baltimore City and County", extent=zb, bins=bins,
                 stat_b=f"Correlation {sp['r']:.2f}",
                 stat_c=f"Mean absolute difference {sp['mad']:.2f} pp\nLog-likelihood per mover {f.validation_LL / n:.3f}")]
    tmp = os.path.join(out, "holdout_map_tmp")
    HM.draw(rows, tmp, f"Areas: Public Use Microdata Areas; lines: counties; {n:,} hold-out movers of the ACS PUMS.\n"
            "The hold-out sample was also used in the specification search.", height=4.6)
    os.replace(tmp + ".png", os.path.join(out, "holdout_map.png")); os.remove(tmp + ".pdf")


def holdout_extra(folder):
    C = []
    ZSP = 'os.path.join(FOLDER, "..", "00_shared_data", "zone_system", "zoneSystem.csv")'
    if folder in HOLD_FILES or folder == "01_residential_puma":
        copy_holdout(folder)
        C.append(md("### Hold-out check by area\n\nObserved and model shares of the hold-out records by area (model share = sum of the predicted "
                    "probabilities). The map and its tables are in `output/holdout_map.png`, `output/holdout_puma.csv`, `output/holdout_county.csv`."))
        C.append(code(f"""
# hold-out map (copied into output/) and its reading, numbers from output/holdout_*.csv
nt.show_png(os.path.join(OUT, "holdout_map.png"))
display(Markdown(rd.holdout_md(MODEL_FOLDER, OUT, {ZSP})))
"""))
        if folder == "01_residential_puma":
            hc = 'HC = pd.read_csv(os.path.join(OUT, "holdout_county.csv")); u = "Movers"'
        elif folder == "05_workplace_choice":
            hc = 'HC = pd.read_csv(os.path.join(OUT, "holdout_county.csv")); u = "Workers"'
        else:
            hc = f'HC = pd.read_csv(os.path.join(OUT, "holdout_county.csv")); HC = HC[HC.band == {BAND[folder]!r}]; u = "Students"'
        C.append(code(f"""
# observed against model share by county (hold-out); the counties with the largest differences are labelled
{hc}
nt.holdout_scatter(HC, names=rd.county_names({ZSP}), unit=u, title="(a) Counties, hold-out")
"""))
        C.append(md("How to read it: one point per county; on the line the share is predicted exactly, above the line the model is too high."))
    if folder == "02_residential_dwelling":
        C.append(md("### Hold-out shares by structure type\n\nShare of the hold-out movers' chosen dwellings by structure type, observed and predicted "
                    "(sum over the 30 alternatives of probability x type)."))
        C.append(code("""
# predicted against observed structure type of the chosen dwelling, hold-out movers (article coefficients if there are no estimates)
est_data = M.DATA; M.DATA = os.path.join(FOLDER, "input", "data", "holdout", "dwelling_holdout.parquet")
try:
    hdb, hll = M.model(); hdf = pd.read_parquet(M.DATA)
finally:
    M.DATA = est_data
ref_ = rd.reference(MODEL_FOLDER)[0]
betas = results.get_beta_values() if results is not None else dict(zip(ref_.parameter, ref_.coefficient))
P = nt.predicted_probabilities(hdb, hll, betas)
fg.obs_model_figure(fg.dwelling_holdout_panels(hdf, P)); plt.show()
"""))
        C.append(md("How to read it: dark grey observed, orange model: (a) structure type of the chosen dwelling, (b) share in multifamily and (c) mean monthly cost by income group; equal bars mean the model reproduces the hold-out."))
    if folder == "04_car_ownership":
        C.append(md("### Hold-out shares by number of cars and by household\n\nObserved and predicted shares of the hold-out households (predicted = "
                    "mean of the probabilities)."))
        C.append(code("""
# predicted against observed car shares on the hold-out, overall, by workers and by dwelling (article coefficients if no estimates)
est_data = M.DATA; M.DATA = os.path.join(FOLDER, "input", "data", "holdout", "car_ownership_holdout.csv")
try:
    hdb, hll = M.model(); hdf = pd.read_csv(M.DATA)
finally:
    M.DATA = est_data
ref_ = rd.reference(MODEL_FOLDER)[0]
betas = results.get_beta_values() if results is not None else dict(zip(ref_.parameter, ref_.coefficient))
P = nt.predicted_probabilities(hdb, hll, betas)
fg.obs_model_figure(fg.cars_holdout_panels(hdf, P)); plt.show()
"""))
        C.append(md("How to read it: dark grey observed, orange model; (b) and (c) test the share without a car within groups of households."))
    return C


def effect_cells(folder):
    """effect on utility by income (residential) or by income group (workplace, K-8), 95 % delta-method bands"""
    if folder not in RD.EFFECTS or folder in ("08_school_location_college",):
        return []
    cov = {"06_school_location_K8": 'b = dict(zip(est_v.parameter, est_v.coefficient)); V = pd.read_csv(os.path.join(FOLDER, "model", "robust_covariance.csv"), index_col=0)'}.get(
        folder, 'b = results.get_beta_values() if results is not None else dict(zip(est_v.parameter, est_v.coefficient))\n'
                'names_ = list(b); V = pd.DataFrame(np.asarray(results.robust_variance_covariance_matrix), index=names_, columns=names_) if results is not None else None')
    fn = "income_effect_figure" if RD.EFFECTS[folder]["kind"] == "income" else "group_effect_figure"
    how = RD.HOW_INCOME.get(folder, "How to read it: the coefficient for each income group (main term plus its interaction) with a 95 % interval; "
                                    "where the interval crosses zero the effect is not significant for that group.")
    return [md("### Effects by income\n\nMain term plus its income interaction, with 95 % delta-method bands from the robust covariance."),
            code(f"""
# effect on utility by household income (or income group), 95 % delta-method bands
{cov}
fg.{fn}(MODEL_FOLDER, b, V); plt.show()
"""), md(how)]


def sample_size_cells(folder):
    """the sampled-alternatives check (output of the project's check, copied into 02_residential_dwelling/output)"""
    if folder not in ("01_residential_puma", "02_residential_dwelling"):
        return []
    lv = "dwelling" if folder == "02_residential_dwelling" else "PUMA"
    what = ("the 30 alternatives (chosen + 29 sampled)" if lv == "dwelling" else "the 200 sampled dwellings of the inclusive value")
    return [md(f"### Sampled-alternatives check\n\nWhy the sampled {'alternatives' if lv == 'dwelling' else 'dwellings'} are enough: the model was re-estimated "
               f"with a second random draw of 30, and with 60 and 100 alternatives (each draw also redraws {what}). Read from "
               "`02_residential_dwelling/output/sample_size_coef.csv` and `sample_size_fit.csv` (the check runs in the project, not in this package)."),
            code(f"""
# change of every coefficient against the 30-alternative estimate, in its robust s.e. (grey band: within 1 s.e.), and the fits
SS = os.path.join(FOLDER, "..", "02_residential_dwelling", "output")
fg.sample_size_figure(os.path.join(SS, "sample_size_coef.csv"), {lv!r}); plt.show()
ssf = pd.read_csv(os.path.join(SS, "sample_size_fit.csv")); n_est = int(RUN["check"]["N"])
ssf["N"] = n_est; ssf["LL per mover ({lv} level)"] = ssf[{'"dwelling_LL"' if lv == "dwelling" else '"PUMA_LL"'}] / n_est
display(ssf[["case", "J", "N", "LL per mover ({lv} level)"]].round(4))
"""),
            md("How to read it: all points inside the grey band (within one standard error) mean the results do not depend on the number of sampled "
               + ("dwellings. The dwelling-level log-likelihood falls with more alternatives because the choice set is larger; it is not a comparison of fit."
                  if lv == "dwelling" else "dwellings."))]


# ------------------------------------------------------------------------------------------------ 4.1 variables in the data
SILO_EXTRA_TOC = {"01_residential_puma": "; 4.2 moves in the ACS: migration fields, origin and destination",
                  "02_residential_dwelling": "; 4.2 new dwellings, bedrooms and housing cost"}
VAR_HOW = ("Each explanatory variable of the final specification as it enters the utility, interactions included (read from the model's own "
           "utility functions: the part of the utility that each coefficient multiplies; coefficients that share a label, e.g. the copies of a "
           "term for several purposes, are shown in one panel). ")
LOC_READ = ("How to read it: dark grey line = the chosen alternatives, light bars = the {what} alternatives, as a share of each (%); dashed lines are "
            "the two means; 0/1 variables are shown as the share with value 1. A continuous variable that is zero at every alternative of a record "
            "cannot affect that record's choice, so such records are left out of its panel (e.g. an interaction with a person group; the share "
            "kept is in the panel title). The further apart the two, the more the variable separates the choices.")


def silo_var_cells(folder, cfg):
    lay = cfg["layout"]
    unit = {"01_residential_puma": "movers", "02_residential_dwelling": "movers", "05_workplace_choice": "workers", "04_car_ownership": "households"}.get(folder, "students")
    if lay == "wide":
        sampled = folder != "01_residential_puma"; what = "sampled" if sampled else "available"
        alt = {"01_residential_puma": "chosen PUMA against all available PUMAs (every mover counts once)",
               "02_residential_dwelling": "chosen dwelling against the 29 sampled dwellings of the same PUMA",
               "05_workplace_choice": "chosen workplace zone against the 99 sampled zones"}[folder]
        C = [md("### 4.1 Variables in the data\n\n" + VAR_HOW + f"Here: the {alt}; unweighted."
                + (" The car-time interactions use centred person variables, as in the model: car time x (person variable minus its mean)."
                   if folder == "05_workplace_choice" else "")),
             code(f"""
# every explanatory variable of the specification: chosen against {what} alternatives
import varplots as vp
_db, _ll = M.model(); U_, AV_, CH_ = vp.find_choice(_ll)
VP = vp.location_from_util(U_, AV_, CH_, df, vp.silo_labels(MODEL_FOLDER), sampled={sampled})
print(f"{{len(VP)}} variables, {{len(df):,}} {unit}")
vp.location_figures(VP, what={what!r}, unit={unit!r})
"""), md(LOC_READ.format(what=what, unit=unit))]
    elif lay == "flat":
        C = [md("### 4.1 Variables in the data\n\n" + VAR_HOW + "Here: each variable by the number of cars the household owns (the chosen alternative); unweighted."),
             code("""
# every explanatory variable of the specification by chosen number of cars
import varplots as vp
_db, _ll = M.model(); U_, AV_, CH_ = vp.find_choice(_ll)
ALT_NAMES = {0: "No car", 1: "1 car", 2: "2 cars", 3: "3+ cars"}
VP = vp.by_choice(U_, AV_, CH_, df, vp.silo_labels(MODEL_FOLDER), ALT_NAMES)
display(Markdown(vp.choice_counts_line(vp.choices(CH_, df), ALT_NAMES, "households")))
vp.by_choice_figures(VP, list(ALT_NAMES.values()), unit="households")
"""), md("How to read it: one bar per number of cars: the mean of the variable (or the share with value 1) among the households that own that many cars; "
                 "the grey range is the 25th-75th percentile, the dashed line the mean of all households. A variable enters the utilities of 1, 2 and 3+ cars "
                 "(no car is the reference) with one coefficient each.")]
    else:
        C = [md("### 4.1 Variables in the data\n\n" + VAR_HOW + "Here: the chosen school zone (spread over the student's possible home and school "
                "zones by their weights) against all zones with enrolment of the student's band (each student counts once); the size term with the "
                "size weights at their estimates."),
             code("""
# every explanatory variable of the specification: chosen against available school zones
import varplots as vp
VP, NST = vp.school_panels(M, st, alt, cand, vp.silo_labels(MODEL_FOLDER), dict(zip(rd.reference(MODEL_FOLDER)[0].parameter, rd.reference(MODEL_FOLDER)[0].coefficient)))
print(f"{len(VP)} variables, {NST:,} students")
vp.location_figures(VP, what="available", unit="students")
"""), md(LOC_READ.format(what="available", unit="students"))]
    if folder == "01_residential_puma":
        C += [md("### 4.2 Moves in the ACS: migration fields\n\nThe ACS fields behind the movers: where the householder lived a year ago (`MIG`), when "
                 "the household moved into the unit (`MV`), how the two agree, and the share of persons who moved by survey year. All PUMS households "
                 "of the six states (not group quarters), weighted by the household weight (`WGTP`); persons by the person weight (`PWGTP`, read "
                 "again from the person files)."),
              code("""
# MIG, MV and their agreement (households, WGTP), persons who moved by survey year (PWGTP)
import varplots as vp
vp.acs_fields_figure(H, vp.persons_moved(S3))
"""),
              md("### Origin and destination of the estimation movers\n\nThe destination PUMA against the origin migration area (MIGPUMA): inside it, "
                 "bordering it, elsewhere in the same state, or in another state (from the table columns `same`, `adjacent`, `same_state` at the "
                 "chosen PUMA), and the car time moved (AM-peak car skim between the housing units of origin and destination)."),
              code("""
# class of each move, car time moved, and the MIGPUMA -> PUMA flows
import rc
M_ = MOV.set_index("SERIALNO").reindex(df.household.values)
DEST = IDX.puma7.values[df.choice.values]
CLS = vp.od_class(df, len(IDX)); TMOVE = vp.move_times(M_.mig7.values, DEST, SH, rc)
vp.od_figure(CLS, TMOVE, df.weight)
vp.flow_map(M_.mig7.values, DEST, CLS, SH, ZS)
"""),
              md(vp_acs_limits())]
    if folder == "02_residential_dwelling":
        C += [md("### 4.2 New dwellings, bedrooms and housing cost\n\nThe chosen dwelling against the 29 sampled dwellings: built in the last five "
                 "years, bedrooms against the bedrooms needed (household size, at most 5, as in the model: shortfall, exact, extra), and the housing "
                 "cost as a share of income by income group (2016 $)."),
              code("""
# new dwellings, bedrooms against need, cost share of income; chosen against sampled
import varplots as vp
vp.dwelling_figure(df)
""")]
    return C


def vp_acs_limits():
    import varplots as VPM
    return VPM.ACS_LIMITS


def abit_var_cells(folder, location):
    unit = RD.ABIT_SPEC.get(folder, {}).get("unit", "records")
    if location:
        return [md("### 4.1 Variables in the data\n\n" + VAR_HOW + f"Here: the zones of the observed location (the candidate zones of the location "
                   f"mixture, by their weights) against all zones of the full choice set; for speed, 1,000 {unit} drawn at random from the estimation "
                   "half and 150 zones drawn at random for each as the available alternatives. Scale and size-weight parameters at their estimates."),
                code("""
# every explanatory variable of the specification: chosen against available zones
import varplots as vp
MV_ = af.module(MODEL_FOLDER); R_ = af.reference(MODEL_FOLDER)
FIX = {p: (1.0 if p.startswith("SCALE_") else v) for p, v in zip(R_.parameter, R_.coef) if p.startswith(("SCALE_", "THETA_"))}
PARTS = sorted(glob.glob(os.path.join(FOLDER, "input", "data", "estimation", "biogeme_part*.parquet")))
t0 = time.time()
VP, NREC = vp.location_from_at(MV_, PARTS, vp.abit_labels(MODEL_FOLDER), FIX, n_rows=1000, n_zones=150)
print(f"{len(VP)} variables; %s drawn: {NREC:,}; {time.time() - t0:.0f} s")
vp.location_figures(VP, what="available", unit=%r)
""" % (unit, unit)), md(LOC_READ.format(what="available", unit=unit))]
    return [md("### 4.1 Variables in the data\n\n" + VAR_HOW + "Here: each variable by the chosen alternative, estimation half, unweighted. Person and "
               "household variables (the same value in every utility they enter) are shown as the mean or share among the records that chose "
               "each alternative; attributes of the alternatives (values that differ between alternatives, e.g. cost) as the mean at the chosen "
               "alternative against the mean where the alternative is available."),
            code("""
# every explanatory variable of the specification by chosen alternative
import varplots as vp
MV_ = af.module(MODEL_FOLDER); r_ = MV_.read("estimation"); D_ = r_[0] if isinstance(r_, tuple) else r_
e_ = MV_.formulas() if hasattr(MV_, "formulas") else MV_.loglike(); e_ = e_["loglike"] if isinstance(e_, dict) else e_
U_, AV_, CH_ = vp.find_choice(e_); ALT_NAMES = af.ALTS[MODEL_FOLDER]
VP = vp.by_choice(U_, AV_, CH_, D_, vp.abit_labels(MODEL_FOLDER), ALT_NAMES)
display(Markdown(vp.choice_counts_line(vp.choices(CH_, D_), ALT_NAMES, %r)))
vp.by_choice_figures(VP, list(ALT_NAMES.values()), unit=%r)
""" % (unit, unit)),
            md("How to read it: dark grey bars = mean (or share with value 1) among the records that chose the alternative, grey range = 25th-75th "
               "percentile, dashed line = all records; for attributes of the alternatives, the light bar is the mean where the alternative is available.")]


def abit_coef_cells():
    return [md("### What the coefficients say\n\nOne plain line per term (article estimates of `model/reference_estimates.csv`) and the coefficient plot."),
            code("""
# plain readings of the coefficients and the coefficient plot (95 % robust intervals, grouped by block)
rows = af.coef_rows(MODEL_FOLDER)
display(rd.abit_readings(rows).style.hide(axis="index").set_properties(**{"text-align": "left"}))
fg.coef_figure(rows); plt.show()
"""), md("How to read it: a point right of zero makes the alternative more likely; an interval that crosses zero is not significant; colours are the alternatives or purposes a term belongs to.")]


def finish_silo(C, folder):
    """section notes under each numbered heading; a one-line comment on top of every code cell"""
    import re as _re
    out, heading = [], ""
    for i, c in enumerate(C):
        if c.cell_type == "markdown":
            m = _re.match(r"^##\s+(\d+)\.\s*(.*)", c.source)
            if m and int(m.group(1)) in RD.SECTION:
                first, _, rest = c.source.partition("\n")
                c.source = first + "\n\n*" + RD.SECTION[int(m.group(1))] + "*" + ("\n" + rest if rest.strip() else "")
                heading = m.group(2).split("\n")[0]
            elif c.source.startswith("#"):
                heading = c.source.lstrip("#").strip().split("\n")[0]
        elif c.cell_type == "code" and c.source.lstrip().startswith("RUN_"):
            c.source = "# switches (see How to run) and set-up: imports, folders, helper modules\n" + c.source
        elif c.cell_type == "code" and not c.source.lstrip().startswith("#"):
            nxt = C[i + 1] if i + 1 < len(C) else None
            cap = nxt.source.strip().split("\n")[0] if nxt is not None and nxt.cell_type == "markdown" and not nxt.source.startswith("#") else ""
            txt = (cap.split(". ")[0] if cap else heading).replace("`", "").rstrip(".")
            if txt:
                c.source = "# " + txt[:110] + "\n" + c.source
        out.append(c)
    return out


SILO_CHOICE = {
    "01_residential_puma": "Alternatives: the 97 PUMAs of the zone-system area (`av_<j>`; all available), no sampling; `puma_index.csv` gives the PUMA of each index j. The observed choice is the destination PUMA (`choice`). The inclusive value of the dwelling level (`IV_<j>`) enters as data with coefficient 1. Weight: expected in-area share of destination and origin, divided by its mean.",
    "02_residential_dwelling": "Alternatives: the chosen dwelling (alternative 0) and 29 dwellings drawn without replacement from the dwellings of the same PUMA occupied by households that moved in within 12 months (`cost_<j>`, `bedrooms_<j>`, `type_<j>`).",
    "04_car_ownership": "Alternatives: 0, 1, 2, 3+ cars (ordered as an MNL with alternative-specific coefficients), all available.",
    "05_workplace_choice": "Alternatives: the chosen workplace zone (alternative 0) and 99 zones drawn uniformly from the other zones with jobs (`zone_<j>`, car time `t_<j>`, job mix and region of the zone). The hold-out is evaluated on all 1,587 zones with jobs.",
    "06_school_location_K8": "Alternatives: all zones with enrolment of the student's band (elementary up to age 10, else middle school); availability = enrolment of the band. Home and school locations are mixtures over up to 4 home and 2 school zones (`w_home_<h>`, `w_school_<c>`).",
    "07_school_location_high_school": "Alternatives: all zones with high-school enrolment; availability = enrolment. Home and school locations are mixtures over up to 3 home and 2 school zones (`w_home_<h>`, `w_school_<c>`).",
    "08_school_location_college": "Alternatives: all zones with post-secondary enrolment; availability = enrolment. Home and school locations are mixtures over up to 3 home zones and 1 school zone (`w_home_<h>`, `w_school_<c>`).",
}

SILO_DEFS = {
    "wide": """
alts = nt.alt_columns(df)          # alternative-specific columns <variable>_<j>, used in section 6
""",
    "flat": """
pass
""",
    "school": """
person = nt.explanatory(st[[c for c in st.columns if not c.startswith(("home_zone", "school_zone", "w_home", "w_school"))]])
alt_x = nt.explanatory(alt.drop(columns=["av"]))      # used in section 6
""",
}


def sys_py():
    return os.path.expanduser("~/.venvs/biogeme/bin/python")


def setup_cell(flags, name, folder=""):
    return code(flags + f"""
import os, sys, json, glob, inspect, importlib, time, re
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from biogeme.results_processing import EstimationResults

FOLDER = os.path.abspath("")                       # this model folder (VS Code starts the notebook here)
sys.path.insert(0, os.path.join(FOLDER, "..", "..", "tools")); import nbtools as nt; import nb_reader as rd; import figs as fg; import abit_figs as af
from IPython.display import Markdown
sys.path.insert(0, os.path.join(FOLDER, "model"))
RUN = json.load(open(os.path.join(FOLDER, "RUN.json")))
OUT = os.path.join(FOLDER, "output"); os.makedirs(OUT, exist_ok=True)
NAME = "{name}"; MODEL_FOLDER = "{folder}"
pd.set_option("display.max_rows", 200, "display.max_columns", 60, "display.width", 200)
plt.rcParams.update({{"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False}})
print("model folder:", os.path.basename(FOLDER))
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
    C = [md("## 9. Results\n\n### Estimates in the article format\nCoefficient (stars: *** p < 0.01, ** p < 0.05, * p < 0.10, as in the article), robust s.e., p.")]
    C.append(code("""
if results is not None:
    est_t = nt.estimates_table(results)
    display(nt.article_format(est_t))
"""))
    C += abit_coef_cells()
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
    mod = next(f for f in sorted(os.listdir(f"{d}/model")) if f.startswith("estimate_") and f.endswith(".py") and "_pre" not in f)[:-3]   # not backups
    src = open(f"{d}/model/{mod}.py").read()
    m = re.search(r'^NAME = "(\w+)"', src, re.M) or re.search(r'model_name = "(\w+)"', src)
    name = m.group(1) if m else mod[len("estimate_"):]
    location = bool(glob_any(f"{d}/input/data/estimation", "biogeme_part"))
    ck = R.get("check") or {}
    chk_steps = [s for s in R.get("steps", []) if "--evaluate" in s.get("command", "")]
    chk_min = max([s["minutes"] for s in chk_steps if isinstance(s.get("minutes"), (int, float))] or [0])
    heavy_chk = folder in HEAVY_CHECK or chk_min > 30
    has_hold = os.path.isdir(f"{d}/input/data/holdout") and bool(os.listdir(f"{d}/input/data/holdout"))
    at_arg = "full" if "--at" in src or "def evaluate(half, at" in src else None
    ll_beta = reference_ll(f"{d}/model/reference_estimates.csv")
    import abit_figs as AF
    _rows = AF.coef_rows(folder)
    C = [md(RD.abit_answers_md(folder, R)), md(RD.how_to_run_md_abit(folder, chk_min, heavy_chk)), md(f"""
## Contents

This notebook goes from the survey records to the estimates of this model:

1. Raw data: survey files, estimation and hold-out halves, the records of this model
2. Data preparation: filters from the survey to the records (records kept and dropped), rebuild check against the shipped tables
3. Choice set and estimation data
4. Descriptive statistics and figures; 4.1 every explanatory variable of the model in the data
5. Model specification (the folder's `model/{mod}.py`, unchanged)
6. Correlation of the explanatory variables (heatmaps, VIF)
7. Log-likelihood at the reference coefficients
8. Biogeme estimation
9. Results: article format, what the coefficients say, fit, comparison with the article, correlation of the estimates
10. Hold-out sample
11. Glossary
"""), md(RD.abit_glance_md(folder, _rows, ck.get("N")))]
    prep_min = sum(s["minutes"] for s in R.get("steps", []) if (s.get("cwd") or "").startswith("input") and isinstance(s.get("minutes"), (int, float)))
    flags = f"""
RUN_DATA_PREP  = True    # rebuild the records and estimation tables in a scratch copy and compare with the shipped tables (about {max(1, round(prep_min * 1.5))} min)
RUN_CHECK      = True    # log-likelihood at the reference coefficients{f'  (this model: about {round(chk_min)} min)' if chk_min > 5 else ''}
RUN_ESTIMATION = False   # Biogeme estimation, written to output/ (False: results are read from output/ if there are any)
RUN_HOLDOUT    = {has_hold and not heavy_chk}    # log-likelihood of the hold-out half at the reference coefficients{'  (this model: as long as the check)' if heavy_chk else ''}
"""
    C.append(setup_cell(flags, name, folder))
    if folder in W.LOCATION:
        C += W.location_cells(folder)
    elif folder in W.FAMILY:
        C += W.FAMILY[folder](folder)
    C += abit_var_cells(folder, location)
    C.append(md(sources_md(R, heading="### Data sources")))
    C.append(md(f"## 5. Model specification\n\nThe folder's script `model/{mod}.py`, imported as it is. Its utility functions:"))
    C.append(code(f"""
sys.path.insert(0, os.path.join(FOLDER, "model")); sys.modules.pop("{mod}", None)   # the model folder's script (input/code may hold a namesake)
import {mod} as M
src = inspect.getsource(M)
print(src[:src.find("def read(")])
"""))
    if location:
        C.append(code("""
# Biogeme table: one row per record; imp_<c>_<zone>, cgt_<c>_<zone> = zone variables of configuration c for all zones,
# cand_* / b_* = the candidate zones of the observed location and their weights. Only the first two parts are read here.
est = os.path.join(FOLDER, "input", "data", "estimation")
parts = sorted(glob.glob(os.path.join(est, "biogeme_part*.parquet")))
df = pd.concat([pd.read_parquet(p) for p in parts[:2]], ignore_index=True)
person = nt.explanatory(df[[c for c in df.columns if c.startswith("f_")]])
ZONES = pd.read_csv(os.path.join(FOLDER, "..", "00_shared_data", "zones", "zones_model_attributes.csv"))
"""))
    else:
        C.append(code("""
r = M.read("estimation")
df = r[0] if isinstance(r, tuple) else r
print(f"estimation table as read by the script: {df.shape[0]:,} rows, {df.shape[1]} columns")
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
    at_txt = f'evaluate("estimation", "{at_arg}")' if at_arg else 'evaluate("estimation")'
    C.append(md(f"""
## 7. Log-likelihood at the reference coefficients

No estimation: the script's `{at_txt}`, i.e. the log-likelihood of the estimation half at the full-precision coefficients
of `model/reference_estimates.csv`. Target: LL(beta) of that file, {ll_beta if ll_beta is not None else 'n/a'} (article {ck.get('article_LL', ck.get('reference_LL', ''))};
N = {ck.get('N', '')}, K = {ck.get('K', '')}).{' This model takes about ' + str(round(chk_min)) + ' min.' if chk_min > 5 else ''}
"""))
    C.append(code(f"""
LL_BETA = {ll_beta!r}
def evaluate(half):
    here = os.getcwd()
    try:
        return M.evaluate(half, {at_arg!r}) if "at" in inspect.signature(M.evaluate).parameters else M.evaluate(half)
    finally:
        os.chdir(here)

if RUN_CHECK:
    t0 = time.time(); ll_ref = evaluate("estimation")
    print(f"{{(time.time() - t0) / 60:.1f}} min")
    if isinstance(ll_ref, (int, float)) and LL_BETA is not None:
        print(f"LL at the reference coefficients {{ll_ref:,.4f}}; LL(beta) of reference_estimates.csv {{LL_BETA:,.4f}}; difference {{ll_ref - LL_BETA:+.4f}}")
else:
    print("skipped (RUN_CHECK = False)")
"""))
    C.append(md(f"""
## 8. Biogeme estimation

The script's `estimate()`: Biogeme with its defaults (`output/biogeme.toml`), robust standard errors. Report in
`output/{name}.html` and `.yaml`. Not run here (`RUN_ESTIMATION = False`); a result in `output/` is read only if it is
newer than `model/reference_estimates.csv`.
"""))
    C.append(code("""
if RUN_ESTIMATION:
    here = os.getcwd(); t0 = time.time()
    try:
        M.estimate(OUT)
    finally:
        os.chdir(here)
    print(f"estimation time {time.time()-t0:.0f} s")
ref_time = os.path.getmtime(os.path.join(FOLDER, "model", "reference_estimates.csv"))
y = [f for f in sorted(glob.glob(os.path.join(OUT, "*.yaml")), key=os.path.getmtime) if "eval" not in os.path.basename(f) and os.path.getmtime(f) > ref_time]
results = EstimationResults.from_yaml_file(y[-1]) if y else None
print(f"results read from {os.path.basename(y[-1])}" if y else "no current result in output/: the estimate tables of section 9 are skipped")
"""))
    C += results_cells(stats_n=str(ck.get("N")) if ck.get("N") else "None")
    hold_call = f'evaluate("holdout", "{at_arg}")' if at_arg else 'evaluate("holdout")'
    C.append(md(f"## 10. Hold-out sample\n\nLog-likelihood of the hold-out half at the reference coefficients (`{hold_call}`)."))
    C.append(code("""
if RUN_HOLDOUT:
    ll_hold = evaluate("holdout")
else:
    print("skipped (RUN_HOLDOUT = False)")
"""))
    C += abit_reader_cells(folder)
    C.append(md(RD.abit_glossary_md(folder)))
    return finish_silo(C, folder)


def abit_reader_cells(folder):
    """plain readings, coefficient plot and (small choice sets) the hold-out shares; inserted at the end, before the glossary"""
    import abit_figs as AF
    C = []
    if folder in AF.SEGMENT:
        C += [md("### Hold-out shares\n\nObserved and model shares of the hold-out half (model: mean of the probabilities at the reference coefficients, simulated with this script's own log-likelihood)."),
              code("""
# observed against model shares on the hold-out half, overall and for one segment
t1, (title, t2, xl), n_hold = af.holdout_tables(MODEL_FOLDER)
t2 = t2[(t2.observed > 0.01) | (t2.model > 0.01)]
A = af.ALTS[MODEL_FOLDER]
fg.obs_model_figure([("All" if len(A) > 2 else t1.index[0], t1, "", "Hold-out records (%)"), (title, t2, xl, f"{t1.index[0] if len(A) == 2 else A[1]} (%)")]); plt.show()
print(f"hold-out records: {n_hold:,}")
"""), md("How to read it: dark grey observed, orange model; equal bars mean the model reproduces the hold-out shares overall and within the segment. "
                 "The hold-out half was also used in the specification search.")]
    elif folder in ABIT_HOLD:
        for dst, src in ABIT_HOLD[folder].items():
            shutil.copy2(os.path.join(HOLD_SRC, src), os.path.join(ROOT, "ABIT", folder, "output", dst))
        C += [md("### Hold-out check by area\n\nObserved and model shares of the hold-out records by area. The model share is the sum of the predicted "
                 "probabilities over all 1,588 zones (computed with this model's utilities; the hold-out log-likelihood recomputed from them equals section 10). "
                 "Map and tables: `output/holdout_map.png`, `output/holdout_puma.csv`, `output/holdout_county.csv`, `output/holdout_stats.json`."),
              code("""
# hold-out map (copied into output/) and its reading, numbers from output/holdout_stats.json and output/holdout_county.csv
nt.show_png(os.path.join(OUT, "holdout_map.png"))
st = json.load(open(os.path.join(OUT, "holdout_stats.json"))); HC = pd.read_csv(os.path.join(OUT, "holdout_county.csv"))
top = HC.reindex(HC.diff_pp.abs().sort_values(ascending=False).index).head(3)
nm = rd.county_names(os.path.join(FOLDER, "..", "..", "SILO", "00_shared_data", "zone_system", "zoneSystem.csv"))
display(Markdown(
    "How to read it: (a) observed share of the hold-out records by area (the observed location spread over its candidate zones), (b) model share, same scale, "
    "(c) model minus observed in percentage points: red = model too high, blue = too low.\\n\\n"
    f"Correlation {st['puma_r']:.2f} by PUMA and {st['county_r']:.2f} by county; mean absolute difference {st['puma_mad']:.2f} pp by PUMA "
    f"({'mapped by county: fewer than 10 records per PUMA' if st['level'] == 'county' else 'mapped by PUMA'}). "
    "Largest county differences: " + ", ".join(f"{nm.get(c, c)} {d:+.1f} pp" for c, d in zip(top.county, top.diff_pp)) + ".\\n\\n"
    "The hold-out half was also used in the specification search."))
""")]
    return C


def reference_ll(path):
    import csv
    try:
        for r in csv.DictReader(open(path)):
            if r.get("parameter") == "LL_beta":
                v = r.get("coefficient") or r.get("article_coefficient")
                return float(v) if v not in (None, "") else None
    except FileNotFoundError:
        return None
    return None


def tasha_notebook(R):
    C = [md(f"""
# {clean(R.get('model', 'TASHA distributions'))}

{clean(R.get('purpose', ''))}

Part of MAST (Maryland Activity Scheduling and Travel model), the activity-based model of the MILES platform, built on the ABIT code base. Not a Biogeme model: empirical distributions of the activity generator, built from the estimation half of the survey.

1. Raw data: survey files, half split
2. Data preparation: trips to typed activity episodes, building the distributions, rebuild check
3. Files
4. Descriptive statistics
5. The distributions
"""), code("""
RUN_DATA_PREP = True    # rebuild the split and the distributions into output/ (about 30 s) and compare with the shipped files
RUN_BUILD = RUN_DATA_PREP
import os, sys, json, glob
import numpy as np, pandas as pd, matplotlib.pyplot as plt
FOLDER = os.path.abspath("")
sys.path.insert(0, os.path.join(FOLDER, "..", "..", "tools")); import nbtools as nt
RUN = json.load(open(os.path.join(FOLDER, "RUN.json")))
REF = os.path.join(FOLDER, "data", "reference_outputs")
OUT = os.path.join(FOLDER, "output"); os.makedirs(OUT, exist_ok=True)
pd.set_option("display.max_rows", 200, "display.max_columns", 60, "display.width", 200)
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})
"""), md("## 1. Raw data")]
    C += W.rts_cells()
    C.append(md("""
## 2. Data preparation

### 2.1 From trips to activity episodes

`code/tasha_distributions.py` reads the trips of the estimation half and makes one episode per trip destination
(start = arrival, duration = departure of the next trip minus arrival; unknown for the last trip of the day). The destination
activity gives the episode type: work at the usual work tract before / after 15:00 (PW / SW), other work (WB), work at home
(WAHB), return home between two work episodes (RHW), school (SCH), shopping, recreation, accompany and other, each joint
(same household, purpose and tract, arrivals within 15 min, reported by 2+ members) or individual. The functions of the script
are called here as they are.
"""))
    C.append(code("""
sys.path.insert(0, os.path.join(FOLDER, "code")); import tasha_distributions as T
pm, per, t_est = T.load()
hh_child = pm.groupby("household_id").age.min().lt(16)
pm, wshares = T.segments(pm, per, hh_child)
e = T.episodes(t_est, per)
pseg = pm[~pm.imputed].drop_duplicates("person_id").set_index("person_id")
f = nt.Funnel("trips of the survey (clean file)", len(trips))
f.add("trips of the estimation half", len(t_est), "households of the hold-out half removed")
e = e[e.person_id.isin(pseg.index)].copy()
f.add("episodes of persons in the survey population", len(e), "person not in persons_map (no segment)")
f.add("out-of-home episodes", int((~e.is_home).sum()), "home episodes (only RHW is a type)")
e = T.subtours(e)
rt = e.wbs_n.gt(0); e.loc[rt, "dur"] = e.loc[rt, "merged_dur"]; e.loc[e.wbs | e.wbs_cont, "type"] = None
ev = e[e.type.notna()].copy()
f.add("typed episodes", len(ev), "stops of work-based outings and returns to the workplace are generated inside the work episode")
display(f.table())
print(f"persons of the estimation half: {pm.id.nunique():,} ({pm.imputed.sum():,} rows imputed for members without trips)")
"""))
    C.append(code("""
ev["seg"] = ev.person_id.map(pseg.seg); ev["group"] = ev.seg.map(T.GROUP)
ty = ev.groupby("type").agg(episodes=("type", "size"), weighted=("wttrdfin", "sum")).reindex(T.TYPES)
ty["share %"] = (100 * ty.episodes / ty.episodes.sum()).round(2); ty["weighted share %"] = (100 * ty.weighted / ty.weighted.sum()).round(2)
ty["purpose"] = [T.PURPOSE_OF[k] for k in ty.index]
ty.drop(columns="weighted")
"""))
    C.append(md("""
### 2.2 Building the distributions

The script groups the episodes into cells (type x person segment x household class x episodes earlier in the day) and writes
one probability vector per cell with at least 50 (frequency) or 40 (start, duration, location) records; smaller cells fall
back to coarser ones. With `RUN_BUILD = True` it is run as shipped into `output/` and compared with the files used by the
model runs (`data/reference_outputs`).
"""))
    for s in R.get("steps", []):
        if (s.get("cwd") or "").startswith("code"):
            C.append(code(f"""
if RUN_BUILD:
    nt.run({s.get('command', '')!r}, cwd=os.path.join(FOLDER, "code"))
else:
    print("skipped (RUN_BUILD = False)")
"""))
    C.append(md("""
Three files differ from the reference by design: the joint participants and propensities were kept from an earlier build
(before work-based outings were removed from the episodes; differences of a few episodes), and `tasha_params.csv` of the
reference also holds engine settings appended when the coefficient files were assembled.
"""))
    C.append(md("## 3. Files\n\n`data/reference_outputs` holds the files used by the model runs; `output/` the rebuild."))
    C.append(code("""
display(nt.files_table(REF))
src = OUT if glob.glob(os.path.join(OUT, "tasha_*.csv")) else REF
print("charts of section 5 from:", os.path.relpath(src, FOLDER))
def probs(t):
    return np.vstack(t["probs"].map(lambda s: np.array([float(x) for x in str(s).split(";")])).to_numpy())
"""))
    C.append(md("""
## 4. Descriptive statistics

### Persons and households of the estimation half
Person segments (weighted by the person weight `w`), household size and age.
"""))
    C.append(code("""
P = pm.drop_duplicates("id")
fig, ax = nt.panels(3, ncol=3, w=4.4, h=3)
s = (P.groupby("seg").w.sum() / P.w.sum() * 100).reindex(T.SEGS)
nt.bar(s, "person segment", "weighted share of persons (%)", ax=ax[0], rot=45)
H = P.drop_duplicates("household_id")
nt.bar(H.hhsize.clip(upper=6).value_counts().sort_index(), "household size (6 = 6+)", "households", ax=ax[1])
nt.hist(P.age, "age (years)", "persons", bins=range(0, 96, 5), ax=ax[2])
plt.tight_layout(); plt.show()
w = P.w
print(f"person weight w: mean {w.mean():.1f}, median {w.median():.1f}, min {w.min():.1f}, max {w.max():.1f}; sum {w.sum():,.0f} persons")
"""))
    C.append(md("### Episodes by start hour and duration\nArrival hour and duration of the typed episodes by group of types (unweighted)."))
    C.append(code("""
grp = {"work": ["WB", "WAHB", "PW", "SW", "RHW"], "school": ["SCH"], "shopping": ["JS", "IS"],
       "recreation / other": ["JO_REC", "JO_OTH", "IO_REC", "IO_OTH"], "accompany": ["IO_ACC"]}
fig, ax = nt.panels(len(grp), ncol=5, w=3.1, h=2.6)
for a, (g, tys) in zip(ax, grp.items()):
    x = ev[ev.type.isin(tys)]
    a.hist(x.arr_min / 60, bins=np.arange(0, 24.5, 0.5), color=nt.OBS); a.set_xlabel(f"arrival hour ({g})"); a.set_xticks([0, 6, 12, 18, 24])
ax[0].set_ylabel("episodes"); plt.tight_layout(); plt.show()
fig, ax = nt.panels(len(grp), ncol=5, w=3.1, h=2.6)
for a, (g, tys) in zip(ax, grp.items()):
    x = ev[ev.type.isin(tys) & ev.dur.notna()]
    a.hist(x.dur / 60, bins=np.arange(0, 12.25, 0.25), color=nt.OBS); a.set_xlabel(f"duration, h ({g})")
ax[0].set_ylabel("episodes"); plt.tight_layout(); plt.show()
"""))
    C.append(md("### Estimation half vs hold-out half\nTrip purposes (destination activity, weighted by the trip weight) in the two halves."))
    C.append(code("""
half = trips.household_id.map(split.set_index("household_id")["half"])
pur = trips.d_activity.map(T.ACT_PURPOSE).fillna("OTHER")
display(nt.half_comparison(pur[half.eq("estimation")], pur[half.eq("validation")], "destination purpose",
                           trips.wttrdfin[half.eq("estimation")], trips.wttrdfin[half.eq("validation")]))
"""))
    C.append(md("## 5. The distributions\n\n### Frequency P(n | type, segment, household, prior): mean episodes per person-day"))
    C.append(code("""
fq = pd.read_csv(os.path.join(src, "tasha_frequency.csv"))
fq = fq[fq["level"] == fq["level"].iloc[0]] if "level" in fq else fq
fq = fq[fq["seg"].isin(T.SEGS)]
m = fq.groupby(["type", "seg"])[["mean", "n"]].apply(lambda g: np.average(g["mean"], weights=g["n"])).unstack().reindex(columns=[c for c in T.SEGS if c in set(fq["seg"])])
fig, ax = plt.subplots(figsize=(min(14, 1.0 * m.shape[1] + 3), 0.42 * m.shape[0] + 1.5))
im = ax.imshow(m.values, cmap="Greys"); plt.colorbar(im, ax=ax, label="mean episodes per person-day (weighted by cell size)")
ax.set_xticks(range(m.shape[1])); ax.set_xticklabels(m.columns, rotation=45, ha="right"); ax.set_yticks(range(m.shape[0])); ax.set_yticklabels(m.index)
ax.set_xlabel("person segment"); ax.set_ylabel("episode type")
for i in range(m.shape[0]):
    for j in range(m.shape[1]):
        if np.isfinite(m.values[i, j]): ax.text(j, i, f"{m.values[i, j]:.2f}", ha="center", va="center", fontsize=7, color="white" if m.values[i, j] > np.nanmax(m.values) * 0.6 else "black")
plt.tight_layout(); plt.show()
"""))
    C.append(md("### Start time P(t | type, …): 15-minute bins from midnight, averaged over the cells of each type"))
    C.append(code("""
stt = pd.read_csv(os.path.join(src, "tasha_start.csv"))
P_ = probs(stt); hours = np.arange(P_.shape[1]) * 0.25
types = sorted(stt["type"].unique())
fig, axes = nt.panels(len(types), ncol=4, w=3.7, h=2.3)
for ax, t_ in zip(axes, types):
    i = (stt["type"] == t_).to_numpy(); w_ = stt.loc[i, "n"].to_numpy()
    ax.fill_between(hours, 100 * (P_[i] * w_[:, None]).sum(0) / w_.sum(), step="mid", color=nt.OBS, alpha=0.85)
    ax.set_xlabel(f"start hour ({t_})"); ax.set_xticks([0, 6, 12, 18, 24])
fig.supylabel("probability per 15 min (%)"); plt.tight_layout(); plt.show()
"""))
    C.append(md("### Duration P(δ | type, …): 5-minute bins to 2 h, then 15 minutes"))
    C.append(code("""
du = pd.read_csv(os.path.join(src, "tasha_duration.csv"))
edges = np.array(list(range(0, 121, 5)) + list(range(135, 1441, 15)), float); mids = (edges[:-1] + edges[1:]) / 2 / 60
P_ = probs(du)[:, :len(mids)]
types = sorted(du["type"].unique())
fig, axes = nt.panels(len(types), ncol=4, w=3.7, h=2.3)
for ax, t_ in zip(axes, types):
    i = (du["type"] == t_).to_numpy(); w_ = du.loc[i, "n"].to_numpy()
    dens = (P_[i] * w_[:, None]).sum(0) / w_.sum() / np.diff(edges) * 60
    ax.plot(mids, dens, color=nt.OBS); ax.set_xlim(0, 12); ax.set_xlabel(f"duration, h ({t_})")
fig.supylabel("density per hour"); plt.tight_layout(); plt.show()
"""))
    C.append(md("### Joint episodes, location bands and scheduling parameters"))
    C.append(code("""
for f_ in ["tasha_joint_propensity.csv", "tasha_joint_propensity_mand.csv", "tasha_joint_participants.csv", "tasha_location_bands.csv", "tasha_params.csv"]:
    p = os.path.join(src, f_)
    if os.path.exists(p):
        print(f_); display(pd.read_csv(p))
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
