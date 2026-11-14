#!/usr/bin/env python3
"""Tables and figures of the 2024 forecast validation of ABIT in the form of Roorda, Miller & Habib (2008), section 5 and Table 2.

    python3 activity/lib/reporting_2024/report.py      -> temporal_2024/tables/*.md|*.tex|*.csv, temporal_2024/figures/fig_t24_*.pdf|png
                              (figures and LaTeX tables also copied to 5_reports/paper/figures and 5_reports/paper/sections/t24_tables)

Reads the per-replication measures (measures.py: data/measures/<setting>_s<NN>.pkl) and the observed benchmarks (bench_acs.py,
bench_atus.py, bench_lodes.py, obs_surveys.py).  Model = mean and standard deviation (ddof = 1) over the replications present.
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import glob, os, pickle, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import t24common as C
sys.path.insert(0, f"{ORIOLE_HOME}/reports")
import paperstyle as ps                                    # noqa: E402
import matplotlib.pyplot as plt                            # noqa: E402
from matplotlib.patches import Patch                       # noqa: E402
from matplotlib.lines import Line2D                        # noqa: E402
from matplotlib.ticker import MultipleLocator              # noqa: E402

# T24_NO_OUTPUT=1: main() writes no table, csv or figure and returns the figure arguments (ARGS) for the composite figure
# (5_reports/composites/fig_forecast.py)
WRITE = os.environ.get("T24_NO_OUTPUT", "") != "1"; ARGS = {}
MD = f"{C.OUT}/measures"; TAB = f"{C.T24}/tables"; FIG = f"{C.T24}/figures"
PFIG = f"{C.V}/5_reports/paper/figures"; PTAB = f"{C.V}/5_reports/paper/sections/t24_tables"
for d in (TAB, FIG, PTAB): os.makedirs(d, exist_ok=True)
HOUR_ORDER = list(range(4, 24)) + list(range(0, 4))
COL = {"acs2024": ps.MODEL, "silo2024": "#86b6ef", "obs": ps.OBSERVED, "obs2": "#b5b3ab"}
SETLAB = {"acs2024": "ABIT, observed 2024 population", "silo2024": "ABIT, forecast 2024 population", "base": "ABIT, observed 2017/18 population"}
TTITLE = {"WORK": "Work activities", "SCHOOL": "School activities", "SHOPPING": "Shopping activities", "OTHER": "Other activities", "HOME": "Return home activities"}


# ------------------------------------------------------------------------------------------------ data
def load_model(setting):
    fs = sorted(glob.glob(f"{MD}/{C.PFX}{setting}_s??.pkl"))
    if not fs: return None
    S, H, F = [], [], []
    for i, f in enumerate(fs):
        s, h, fl = pickle.load(open(f, "rb")); S.append(s.assign(rep=i)); H.append(h.assign(rep=i)); F.append(fl.assign(rep=i))
    S = pd.concat(S); H = pd.concat(H); F = pd.concat(F)
    agg = lambda d, keys: d.groupby(keys).value.agg(["mean", "std", "count"]).reset_index()
    return dict(n=len(fs), S=agg(S, ["key", "metric", "type"]), H=agg(H, ["key", "metric", "type", "hour"]),
                F=agg(F, ["key", "home_unit", "work_unit"]) if len(F) else None, Hrep=H)


def sval(M, key, metric, typ="ALL", col="mean"):
    d = M["S"]; r = d[(d.key == key) & (d.metric == metric) & (d.type == typ)]
    return float(r[col].iloc[0]) if len(r) else np.nan


def oval(S, key, metric, typ="ALL"):
    r = S[(S.key == key) & (S.metric == metric) & (S.type == typ)]
    return float(r.value.iloc[0]) if len(r) else np.nan


def hser(M, key, metric, typ, col="mean"):
    d = M["H"]; r = d[(d.key == key) & (d.metric == metric) & (d.type == typ)].set_index("hour")[col]
    return r.reindex(range(24))


def ohser(Hd, key, metric, typ):
    r = Hd[(Hd.key == key) & (Hd.metric == metric) & (Hd.type == typ)].set_index("hour").value
    return r.reindex(range(24))


def pct(a, b): return 100 * (a - b) / b if b else np.nan


def f0(v): return "–" if not np.isfinite(v) else f"{v:,.0f}"
def f1(v): return "–" if not np.isfinite(v) else f"{v:,.1f}"
def f2(v): return "–" if not np.isfinite(v) else f"{v:.2f}"
def f3(v): return "–" if not np.isfinite(v) else f"{v:.3f}"
def sg(v, d=1): return "–" if not np.isfinite(v) else f"{v:+.{d}f}"
def hm(m): return "–" if not np.isfinite(m) else f"{int(m // 60)}:{int(round(m % 60)):02d}"


def md_table(title, cols, rows, notes):
    L = [f"**{title}**", "", "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] + ["---:"] * (len(cols) - 1)) + "|"]
    L += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(L + [""] + [f"{n}" for n in notes] + [""])


def tex_table(title, label, cols, rows, notes, fname):
    """LaTeX table at full size, never scaled: \\footnotesize (9 pt) body, notes 8 pt; data columns are X columns of tabularx, so the
    long headers wrap. Tables with more than six data columns are set on a landscape page (sidewaystable, width = \\textheight).
    Needs \\usepackage{tabularx} and \\usepackage{rotating} in main.tex."""
    esc = lambda s: str(s).replace("%", "\\%").replace("±", "$\\pm$").replace("–", "--").replace("−", "$-$").replace("→", "$\\rightarrow$").replace("&", "\\&").replace("#", "\\#").replace("ᵃ", "\\textsuperscript{a}").replace("ᵇ", "\\textsuperscript{b}").replace("≥", "$\\geq$").replace("÷", "/")
    n = len(cols) - 1; wide = n > 6; env = "sidewaystable" if wide else "table"
    import re as _re
    # a text cell in a data column (e.g. "ACS 2017–19") breaks at its first space only, never inside a word or a year range
    cell = lambda x: esc(x) if _re.fullmatch(r"[-+−–]?[\d.,]+%?|–|", str(x).strip()) or " " not in str(x) else esc(str(x)).replace(" ", "\\newline ", 1)
    head = "\\scriptsize " + esc(cols[0]) + " & " + " & ".join("\\multicolumn{1}{>{\\centering\\arraybackslash}X}{\\scriptsize " + esc(c).replace(" / ", " ") + "}" for c in cols[1:]) + " \\\\"
    w0 = 0.26 if wide else 0.30            # first column wraps at a fixed width, so long row labels cannot squeeze the data columns
    body = [(f"\\multicolumn{{{len(cols)}}}{{@{{}}l}}{{\\emph{{{esc(r[0].strip('*'))}}}}}" if str(r[0]).startswith("*") else " & ".join([esc(r[0])] + [cell(x) for x in r[1:]])) + " \\\\" for r in rows]
    t = ["% generated by 3_abit/temporal_2024/report.py; do not edit by hand", f"\\begin{{{env}}}" + ("" if wide else "[!tbp]"), "  \\centering", f"  \\caption{{{esc(title)}}}",
         f"  \\label{{{label}}}", "  \\footnotesize\\setlength{\\tabcolsep}{3pt}",
         f"  \\begin{{tabularx}}{{\\linewidth}}{{@{{}}>{{\\raggedright\\arraybackslash}}p{{{w0}\\linewidth}}*{{{n}}}{{>{{\\raggedleft\\arraybackslash}}X}}@{{}}}}", "    \\toprule", "    " + head, "    \\midrule"] + ["    " + b for b in body] + [
         "    \\bottomrule", "  \\end{tabularx}", "", "  \\parbox{\\linewidth}{\\scriptsize\\vspace{3pt}" + "\\\\[1pt]".join(esc(n_) for n_ in notes) + "}",
         f"\\end{{{env}}}", ""]
    if not WRITE: return
    open(f"{TAB}/{fname}.tex", "w").write("\n".join(t)); shutil.copy(f"{TAB}/{fname}.tex", f"{PTAB}/{fname}.tex")


def save(fig, name):
    p = ps.finish(fig, f"{FIG}/{name}"); shutil.copy(p, f"{PFIG}/{name}.pdf"); return p


def ptxt(p): return "P < 0.001" if p < 0.001 else f"P = {p:.3f}"


def clear_space(fig, ax, artists, grow=1.12, tries=16):
    sys.path.insert(0, f"{ORIOLE_HOME}/reports"); import tasha_stage3 as TS
    return TS.clear_space(fig, ax, artists, grow, tries)


def paired_bars(ax, x, series, width=0.8):
    k = len(series); w = width / k
    for i, (v, c) in enumerate(series): ax.bar(x + (i - (k - 1) / 2) * w, v, w, color=c, edgecolor=c, lw=0)


def nice_top(v, steps=(5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100)):
    return next((s for s in steps if s >= v), v)


# ------------------------------------------------------------------------------------------------ build
def main():
    obs = pickle.load(open(f"{MD}/obs.pkl", "rb"))
    M = {s: load_model(s) for s in ["acs2024", "silo2024", "base", "acs2024_tw", "silo2024_tw", "base_tw"]}
    have = {s: m for s, m in M.items() if m is not None}
    print("replications:", {s: m["n"] for s, m in have.items()})
    acs = pd.read_csv(f"{C.OUT}/acs_commute.csv"); acsH = pd.read_csv(f"{C.OUT}/acs_commute_hourly.csv"); acsT = pd.read_csv(f"{C.OUT}/acs_commute_tt.csv")
    acsM = pd.read_csv(f"{C.OUT}/acs_mode.csv"); acsF = pd.read_csv(f"{C.OUT}/acs_flows.csv"); lod = pd.read_csv(f"{C.OUT}/lodes2022_flows.csv")
    A = lambda v, area, metric: float(acs[(acs.vintage == v) & (acs.area == area) & (acs.metric == metric)].value.iloc[0])
    Ase = lambda v, area, metric: float(acs[(acs.vintage == v) & (acs.area == area) & (acs.metric == metric)].se.iloc[0])
    md = []; csv_out = {}
    m24 = have.get("acs2024"); ms = have.get("silo2024"); mb = have.get("base")
    nrep = {s: (m["n"] if m else 0) for s, m in M.items()}
    atus = {k: obs[k] for k in obs if k.startswith("atus_")}
    S_md24, H_md24 = atus["atus_md_2021-2024"][0], atus["atus_md_2021-2024"][1]
    S_md19 = atus["atus_md_2017-2019"][0]; S_dmv24 = atus["atus_dmv_2021-2024"][0]; S_dmv19 = atus["atus_dmv_2017-2019"][0]
    kA = "Maryland|15+"; nA24 = int(oval(S_md24, kA, "persons")); nA19 = int(oval(S_md19, kA, "persons")); nD24 = int(oval(S_dmv24, kA, "persons"))

    VARS = [(lab_, suf) for lab_, suf in [("Frozen model", ""), ("With 2024 telework input", "_tw")] if have.get("acs2024" + suf) is not None]
    blk = lambda lab_, ncol: [f"*{lab_}*"] + [""] * (ncol - 1)
    TWNOTE = ("Rows 'with 2024 telework input': the same frozen model and inputs, except that the attendance step reads the observed work-at-home share of the simulated "
              "year by home county (ACS 2024 1-year; ACS 2017–2019 for the 2017/18 runs) instead of the base-year table; the day factor estimated on the base survey is unchanged. "
              "In these rows the share of workers working at home is an input, so the work-activity share is not a validation measure."
              if C.MODEL in ("final", "mc") else
              "Rows 'with 2024 telework input': the same frozen model and inputs, except that the attendance step reads the observed work-at-home share of the simulated "
              "year by home county (ACS 2024 1-year; ACS 2017–2019 for the 2017/18 runs) instead of the fixed table; the day factor estimated on the base survey is unchanged. "
              "In these rows the share of workers working at home is an input, so the work-activity share is not a validation measure.")

    # ---------------- Table 1: activity frequency (TASHA Table 2 form), Maryland residents 15+, vs ATUS
    rows, rc = [], []
    for vlab, suf in VARS:
        m24 = have.get("acs2024" + suf); ms = have.get("silo2024" + suf); mb = have.get("base" + suf)
        if len(VARS) > 1: rows.append(blk(vlab, 11))
        for t in C.TYPES + ["ALL"]:
            mv = sval(m24, kA, "acts_per_person", t); sd = sval(m24, kA, "acts_per_person", t, "std")
            ov = oval(S_md24, kA, "acts_per_person", t); od = oval(S_dmv24, kA, "acts_per_person", t)
            sv = sval(ms, kA, "acts_per_person", t) if ms else np.nan
            bv = sval(mb, kA, "acts_per_person", t) if mb else np.nan
            o19 = oval(S_md19, kA, "acts_per_person", t); d19 = oval(S_dmv19, kA, "acts_per_person", t)
            rows.append([C.TLAB[t], f3(mv), f3(sd), f3(ov), sg(mv - ov, 3), sg(pct(mv, ov)), f3(od), f3(sv), sg(pct(mv, bv)), sg(pct(ov, o19)), sg(pct(od, d19))])
            rc.append(dict(variant=vlab, type=t, model=mv, model_sd=sd, atus_md=ov, atus_dmv=od, model_silo=sv, model_base=bv, atus_md_1719=o19, atus_dmv_1719=d19))
    m24 = have.get("acs2024"); ms = have.get("silo2024"); mb = have.get("base")
    cols = ["Activity type", "Model average activities per person (ABIT)ᵇ", "Model std. dev.ᵇ", "Observed (ATUS, Maryland)", "Model ± activities", "Model ± %",
            "Observed (ATUS, DC + MD + VA)", "Model, forecast population (SILO 2024)ᵇ", "Increase in model 2017/18–2024 (%)", "Increase in observed, Maryland 2017–19 to 2021–24 (%)",
            "Increase in observed, DC + MD + VA (%)"]
    notes = [f"ᵃ Maryland residents aged 15 and over, weekdays. Model: ABIT on the observed 2024 population (ACS 2024 households of Maryland, 5 % sample) with the base-year coefficients unchanged; "
             f"2017/18 model: the same model on the observed survey households of 2017/18. Observed: ATUS weekday diaries 2021–2024 pooled (Maryland n = {nA24}; DC + Maryland + Virginia n = {nD24}; "
             f"Maryland 2017–2019 n = {nA19}). One activity per trip, at its destination; ATUS activities are the stays between travel episodes. " + (TWNOTE if len(VARS) > 1 else ""),
             f"ᵇ Average (standard deviation) of {nrep['acs2024']} replications (forecast population: {nrep['silo2024']}; 2017/18: {nrep['base']})."]
    title = "Activity frequency comparison, ABIT vs ATUS, 2024 forecast validationᵃ"
    md.append(md_table("Table T1. " + title, cols, rows, notes)); tex_table(title.replace("ᵃ", "\\textsuperscript{a}"), "tab:t24_freq", cols, rows, notes, "tab_t24_freq")
    if WRITE: pd.DataFrame(rc).to_csv(f"{TAB}/t24_frequency.csv", index=False)

    # participation
    rows = []
    for vlab, suf in VARS:
        m24 = have.get("acs2024" + suf); ms = have.get("silo2024" + suf); mb = have.get("base" + suf)
        if len(VARS) > 1: rows.append(blk(vlab, 9))
        for t in C.TYPES + ["ALL"]:
            mv = sval(m24, kA, "participation", t); sd = sval(m24, kA, "participation", t, "std")
            ov = oval(S_md24, kA, "participation", t); od = oval(S_dmv24, kA, "participation", t); sv = sval(ms, kA, "participation", t) if ms else np.nan
            bv = sval(mb, kA, "participation", t) if mb else np.nan; o19 = oval(S_md19, kA, "participation", t)
            rows.append([C.TLAB[t], f1(100 * mv), f1(100 * sd), f1(100 * ov), sg(100 * (mv - ov)), f1(100 * od), f1(100 * sv), sg(100 * (mv - bv)), sg(100 * (ov - o19))])
    m24 = have.get("acs2024"); ms = have.get("silo2024"); mb = have.get("base")
    cols = ["Activity type", "Model share of persons with ≥ 1 activity (%)ᵇ", "Model std. dev.ᵇ", "Observed (ATUS, Maryland) (%)", "Model ± (pp)", "Observed (ATUS, DC + MD + VA) (%)",
            "Model, forecast population (%)ᵇ", "Change in model 2017/18–2024 (pp)", "Change in observed, Maryland 2017–19 to 2021–24 (pp)"]
    title = "Activity participation comparison, ABIT vs ATUS, 2024 forecast validationᵃ"
    md.append(md_table("Table T2. " + title, cols, rows, notes)); tex_table(title.replace("ᵃ", "\\textsuperscript{a}"), "tab:t24_part", cols, rows, notes, "tab_t24_part")

    # ---------------- Table 3: work activity and commute, Maryland workers 16+, vs ACS 2024 and ATUS
    kW = "Maryland|workers"; a24 = atus["atus_md_2021-2024_commute"]; d24 = atus["atus_dmv_2021-2024_commute"]
    am = acsM[(acsM.vintage == "acs2024") & (acsM.area == "Maryland")].set_index("mode")
    rows = []
    for vlab, suf in VARS:
        m24 = have.get("acs2024" + suf); ms = have.get("silo2024" + suf)
        def mrow(lab, metric, typ, obs_v, obs_se, scale=1.0, fmt=f1, atus_v=np.nan):
            mv = sval(m24, kW, metric, typ) * scale; sd = sval(m24, kW, metric, typ, "std") * scale
            sv = sval(ms, kW, metric, typ) * scale if ms else np.nan
            return [lab, fmt(mv), fmt(sd), fmt(obs_v), fmt(obs_se) if np.isfinite(obs_se) else "–", sg(mv - obs_v), fmt(atus_v), fmt(sv)]
        if len(VARS) > 1: rows.append(blk(vlab, 8))
        rows += [mrow("Workers with a work activity on the weekday (%)" + (" (input-driven)" if suf else ""), "work_share", "WORK",
                      100 * A("acs2024", "Maryland", "commuting on the reference day, share of workers"), 100 * Ase("acs2024", "Maryland", "commuting on the reference day, share of workers"), 100, f1, 100 * a24["work_share"]),
                 mrow("Mean departure from home to work (min after midnight)", "commute_dep_mean", "WORK", A("acs2024", "Maryland", "mean departure time from home"),
                      Ase("acs2024", "Maryland", "mean departure time from home"), 1, f1, a24["dep_mean"]),
                 mrow("Departing 6:00–8:59 (% of commuters)", "commute_dep_6_9", "WORK", 100 * A("acs2024", "Maryland", "departing 6:00-8:59, share of commuters"),
                      100 * Ase("acs2024", "Maryland", "departing 6:00-8:59, share of commuters"), 100, f1),
                 mrow("Mean travel time to work (min)", "commute_tt_mean", "WORK", A("acs2024", "Maryland", "mean travel time to work"), Ase("acs2024", "Maryland", "mean travel time to work"), 1, f1, a24["tt_mean"]),
                 mrow("Median travel time to work (min)", "commute_tt_median", "WORK", A("acs2024", "Maryland", "median travel time to work"), np.nan, 1, f1)]
        for m in C.COMMUTE_MODES: rows.append(mrow(f"Mode to work: {m.lower()} (%)", "commute_mode", m, 100 * am.loc[m, "share"], 100 * am.loc[m, "se"], 100, f1))
    m24 = have.get("acs2024"); ms = have.get("silo2024"); mb = have.get("base")
    cols = ["Measure", "Model (ABIT)ᵇ", "Model std. dev.ᵇ", "Observed (ACS 2024)", "ACS standard error", "Model ± observed", "Observed (ATUS 2021–24, Maryland)", "Model, forecast population (SILO 2024)ᵇ"]
    nW = int(sval(m24, kW, "workers")) if m24 else 0
    notes = [f"ᵃ Maryland residents employed, aged 16 and over (model: {nW:,} workers of the 5 % observed 2024 population). Model: Monday of the simulated week; departure = the last trip "
             "leaving home before the first work activity; travel time = the trips from that departure to the arrival at work (stops excluded); mode = the trip arriving at work. "
             "ACS 2024 1-year: workers commuting = at work last week and not working at home (JWTRNS ≠ 11) among employed; departure JWDP, travel time JWMNP, mode JWTRNS "
             "(a k-person carpool counts 1/k driver); standard errors from the 80 replicate weights. ATUS: employed respondents with a work stay away from home on the weekday diary "
             f"day (n = {a24['n_employed']} employed, {a24['n_commutes']} commutes). " + (TWNOTE if len(VARS) > 1 else ""),
             f"ᵇ Average (standard deviation) of {nrep['acs2024']} replications."]
    title = "Work activity and commute comparison, ABIT vs ACS and ATUS, 2024 forecast validationᵃ"
    md.append(md_table("Table T3. " + title, cols, rows, notes)); tex_table(title.replace("ᵃ", "\\textsuperscript{a}"), "tab:t24_work", cols, rows, notes, "tab_t24_work")

    # departure-time KS (TASHA hourly form)
    ks = {}
    oh = acsH[(acsH.vintage == "acs2024") & (acsH.area == "Maryland")].set_index("hour").share.reindex(range(24))
    for s, m in have.items():
        if s.startswith("base"): continue
        hmv = hser(m, kW, "commute_dep_share", "WORK"); nz = (hmv > 0) | (oh > 0)
        ks[s] = C.ks_values(100 * hmv[nz], 100 * oh[nz])

    # ---------------- Table 4: change 2017/18 -> 2024 (TASHA Table 2 'increase' columns)
    kB = "Maryland|workers"; rts = obs["rts"][0]; rows = []
    for vlab, suf in VARS:
        m24 = have.get("acs2024" + suf); ms = have.get("silo2024" + suf); mb = have.get("base" + suf)
        def chg(lab, metric, typ, scale, o_base, o_24, o_base_lab, rts_v=np.nan, fmt=f1):
            b = sval(mb, kB, metric, typ) * scale if mb else np.nan; f = sval(m24, kB, metric, typ) * scale
            sfc = sval(ms, kB, metric, typ) * scale if ms else np.nan
            return [lab, fmt(b), fmt(f), sg(f - b), fmt(sfc), fmt(o_base), fmt(o_24), sg(o_24 - o_base), o_base_lab, fmt(rts_v)]
        if len(VARS) > 1: rows.append(blk(vlab, 10))
        wl = " (input-driven)" if suf else ""
        rows += [chg("Workers with a work activity on the weekday (%)" + wl, "work_share", "WORK", 100, 100 * A("acs2017_19", "Maryland", "commuting on the reference day, share of workers"),
                     100 * A("acs2024", "Maryland", "commuting on the reference day, share of workers"), "ACS 2017–19", 100 * oval(rts, kB, "work_share", "WORK")),
                 chg("  idem, observed in time-use diaries (%)" + wl, "work_share", "WORK", 100, 100 * atus["atus_md_2017-2019_commute"]["work_share"], 100 * a24["work_share"], "ATUS 2017–19"),
                 chg("Mean departure to work (min after midnight)", "commute_dep_mean", "WORK", 1, A("acs2017_19", "Maryland", "mean departure time from home"),
                     A("acs2024", "Maryland", "mean departure time from home"), "ACS 2017–19", oval(rts, kB, "commute_dep_mean", "WORK")),
                 chg("Departing 6:00–8:59 (% of commuters)", "commute_dep_6_9", "WORK", 100, 100 * A("acs2017_19", "Maryland", "departing 6:00-8:59, share of commuters"),
                     100 * A("acs2024", "Maryland", "departing 6:00-8:59, share of commuters"), "ACS 2017–19", 100 * oval(rts, kB, "commute_dep_6_9", "WORK")),
                 chg("Mean travel time to work (min)", "commute_tt_mean", "WORK", 1, A("acs2017_19", "Maryland", "mean travel time to work"), A("acs2024", "Maryland", "mean travel time to work"),
                     "ACS 2017–19", oval(rts, kB, "commute_tt_mean", "WORK"))]
        for t in ["WORK", "SHOPPING", "OTHER", "ALL"]:
            b = sval(mb, kA, "acts_per_person", t) if mb else np.nan; f = sval(m24, kA, "acts_per_person", t); sfc = sval(ms, kA, "acts_per_person", t) if ms else np.nan
            rows.append([f"{C.TLAB[t]} activities per person 15+", f3(b), f3(f), sg(f - b, 3), f3(sfc), f3(oval(S_md19, kA, "acts_per_person", t)), f3(oval(S_md24, kA, "acts_per_person", t)),
                         sg(oval(S_md24, kA, "acts_per_person", t) - oval(S_md19, kA, "acts_per_person", t), 3), "ATUS 2017–19", f3(oval(rts, kA, "acts_per_person", t))])
    m24 = have.get("acs2024"); ms = have.get("silo2024"); mb = have.get("base")
    cols = ["Measure", "Model 2017/18ᵇ", "Model 2024ᵇ", "Increase in model 2017/18–2024", "Model 2024, forecast population", "Observed base", "Observed 2024",
            "Increase in observed", "Observed base source", "Base survey (RTS 2017/18)"]
    notes = ["ᵃ Maryland residents (workers 16+; activities: persons 15+). Model 2017/18: ABIT on the observed survey households of 2017/18 (both halves, base skims, 2016 land use); "
             "model 2024: the same coefficients on the observed 2024 population (2024 land use and transit skims). Observed change: ACS 2017–2019 interview years (2015–19 5-year file) to "
             "ACS 2024 1-year; ATUS weekday diaries 2017–2019 to 2021–2024. The RTS column gives the base survey's own level (survey day; usual work location for work at home). "
             + (TWNOTE if len(VARS) > 1 else ""),
             f"ᵇ Average of {nrep['base']} (2017/18) and {nrep['acs2024']} (2024) replications."]
    title = "Increase in model vs observed, 2017/18 to 2024 forecast validationᵃ"
    md.append(md_table("Table T4. " + title, cols, rows, notes)); tex_table(title.replace("ᵃ", "\\textsuperscript{a}"), "tab:t24_change", cols, rows, notes, "tab_t24_change")
    rts_wfh = obs["rts_usual_wfh"]

    # ---------------- Table 5: county-to-county work flows, own-unit share
    cg = C.county_group(); lab = cg.drop_duplicates("unit").set_index("unit").unit_label
    def own_share(f, hcol="home_unit", wcol="work_unit", vcol="workers"):
        g = f.groupby(hcol)[vcol].sum(); o = f[f[hcol] == f[wcol]].groupby(hcol)[vcol].sum(); return (o / g).rename("own")
    def out_state(f, hcol="home_unit", wcol="work_unit", vcol="workers"):
        g = f[vcol].sum(); return float(f[(f[wcol] // 100000) != 24][vcol].sum() / g)
    a24f = acsF[acsF.vintage == "acs2024"]; lo = lod.rename(columns={"jobs": "workers"})
    F24 = m24["F"].rename(columns={"mean": "workers"}) if m24 and m24["F"] is not None else None
    FS = ms["F"].rename(columns={"mean": "workers"}) if ms and ms["F"] is not None else None
    if F24 is not None: F24 = F24[F24.key == "Maryland|workers"]
    if FS is not None: FS = FS[FS.key == "Maryland|workers"]
    units = sorted(set(a24f.home_unit.dropna().astype(int)) & set(cg.unit[cg.index // 1000 == 24]))
    sh = pd.DataFrame({"ACS 2024": own_share(a24f), "LODES 2022": own_share(lo)})
    if F24 is not None: sh["model"] = own_share(F24)
    if FS is not None: sh["model_silo"] = own_share(FS)
    rows = []; order = [cg.unit[c] for c in [24510, 24005, 24003, 24027, 24025, 24013]] + [u for u in units if u not in [cg.unit[c] for c in C.BALTIMORE]]
    for u in order:
        r = sh.loc[u] if u in sh.index else pd.Series(dtype=float)
        rows.append([lab.get(u, str(u)), f1(100 * r.get("model", np.nan)), f1(100 * r.get("model_silo", np.nan)), f1(100 * r.get("ACS 2024", np.nan)), f1(100 * r.get("LODES 2022", np.nan))])
    def tot_row(name, fsub):
        return name
    all_md = lambda f: float(f[f.home_unit == f.work_unit].workers.sum() / f.workers.sum())
    rows.append(["Maryland, all residents", f1(100 * all_md(F24)) if F24 is not None else "–", f1(100 * all_md(FS)) if FS is not None else "–", f1(100 * all_md(a24f)), f1(100 * all_md(lo))])
    rows.append(["Maryland residents working outside Maryland (%)", f1(100 * out_state(F24)) if F24 is not None else "–", f1(100 * out_state(FS)) if FS is not None else "–",
                 f1(100 * out_state(a24f)), f1(100 * out_state(lo))])
    cols = ["Home county (place-of-work area)", "Model, observed population (%)ᵇ", "Model, forecast population (%)ᵇ", "Observed ACS 2024 (%)", "Observed LODES 2022 (%)"]
    notes = ["ᵃ Share of the workers with a work activity (model, Monday) or of the commuters (ACS: place of work last week; LODES: all jobs, JT00) of each home area whose workplace is in the same area. "
             "Areas: counties, or the group of counties of one place-of-work PUMA (Eastern Shore and Western Maryland groups). In the observed-population runs the workplace zone is drawn inside "
             "the ACS place-of-work area of each commuter, so the model's own-area share reproduces the ACS by construction except for workers without a recorded workplace; the forecast-population "
             "runs carry the workplaces of the land-use model.", f"ᵇ Average of {nrep['acs2024']} (observed) and {nrep['silo2024']} (forecast) replications."]
    title = "Own-county work share comparison, ABIT vs ACS and LODES, 2024 forecast validationᵃ"
    md.append(md_table("Table T5. " + title, cols, rows, notes)); tex_table(title.replace("ᵃ", "\\textsuperscript{a}"), "tab:t24_flows", cols, rows, notes, "tab_t24_flows")
    # flow-matrix agreement (Maryland residents, share of all commuters by home-work unit pair)
    def shares(f): s = f.groupby(["home_unit", "work_unit"]).workers.sum(); return s / s.sum()
    flow_fit = {}
    for nm, f in [("model, observed population", F24), ("model, forecast population", FS), ("ACS 2024", a24f)]:
        if f is None: continue
        a, b = shares(f).align(shares(lo), fill_value=0); flow_fit[nm] = dict(corr=float(np.corrcoef(a, b)[0, 1]), srmse=float(np.sqrt(((a - b) ** 2).mean()) / b.mean()),
                                                                          tad=float(0.5 * np.abs(a - b).sum()))

    # ---------------- Table 6: NHTS 2017 Baltimore check
    kN = "Baltimore CBSA|5+"; nh = obs["nhts"][0]; nhn = int(oval(nh, kN, "persons"))
    rows = []; mbt = have.get("base_tw")
    bt = lambda metric, t_, fmt: fmt(sval(mbt, kN, metric, t_)) if mbt else "–"
    for t in C.TYPES + ["ALL"]:
        b = sval(mb, kN, "acts_per_person", t) if mb else np.nan; bs = sval(mb, kN, "acts_per_person", t, "std") if mb else np.nan
        rows.append([f"{C.TLAB[t]}: activities per person", f3(b), f3(bs), f3(oval(rts, kN, "acts_per_person", t)), f3(oval(nh, kN, "acts_per_person", t)), sg(pct(b, oval(nh, kN, "acts_per_person", t))),
                     bt("acts_per_person", t, f3)])
    for t in C.TYPES + ["ALL"]:
        b = sval(mb, kN, "mean_km", t) if mb else np.nan; bs = sval(mb, kN, "mean_km", t, "std") if mb else np.nan
        rows.append([f"{C.TLAB[t]}: average distance (km)", f2(b), f2(bs), f2(oval(rts, kN, "mean_km", t)), f2(oval(nh, kN, "mean_km", t)), sg(pct(b, oval(nh, kN, "mean_km", t))), bt("mean_km", t, f2)])
    b = sval(mb, kN, "trips_per_chain") if mb else np.nan
    rows.append(["Trips per home-based chain", f2(b), f2(sval(mb, kN, "trips_per_chain", "ALL", "std") if mb else np.nan), f2(oval(rts, kN, "trips_per_chain")), f2(oval(nh, kN, "trips_per_chain")),
                 sg(pct(b, oval(nh, kN, "trips_per_chain"))), bt("trips_per_chain", "ALL", f2)])
    cols = ["Measure", "Model 2017/18 (ABIT)ᵇ", "Model std. dev.ᵇ", "Observed RTS 2017/18", "Observed NHTS 2017", "Model ± NHTS (%)", "Model 2017/18 with 2017–19 telework inputᵇ"]
    notes = [f"ᵃ Residents of the Baltimore–Columbia–Towson metropolitan area aged 5 and over, weekdays. NHTS 2017: {nhn} persons of the area's weekday households (public file; the area is "
             "identified only by its CBSA). Model: ABIT on the observed 2017/18 survey households of the area. Distance: model network distance between zones; surveys: reported trip distance "
             "(RTS driving distance, NHTS TRPMILES), capped at 300 km.", f"ᵇ Average (standard deviation) of {nrep['base']} replications."]
    title = "Activity frequency, distance and chain comparison, ABIT vs RTS and NHTS 2017, Baltimore metropolitan area (same-period check)ᵃ"
    md.append(md_table("Table T6. " + title, cols, rows, notes)); tex_table(title.replace("ᵃ", "\\textsuperscript{a}"), "tab:t24_nhts", cols, rows, notes, "tab_t24_nhts")

    # ---------------- figures
    figs = []
    G.update(have)
    ARGS.update(oh=oh, ks=ks, acsT=acsT, am=am, H_md24=H_md24, nA24=nA24, H_dmv24=atus['atus_dmv_2021-2024'][1], nD24=nD24,
                sh=sh if F24 is not None else None, order=order, lab=lab, acs=acs, atus=atus, S_md19=S_md19, S_md24=S_md24, mb=mb, obs=obs, md=md)
    if not WRITE: return ARGS
    if m24 is not None:
        figs.append(fig_departure(oh, ks)); figs.append(fig_traveltime(acsT)); figs.append(fig_mode(am))
        H_dmv24 = atus['atus_dmv_2021-2024'][1]
        figs.append(fig_start(H_md24, nA24, H_dmv24, nD24)); figs.append(fig_duration(H_md24, nA24, H_dmv24, nD24))
        if F24 is not None: figs.append(fig_ownshare(sh, order, lab))
    if mb is not None and m24 is not None: figs.append(fig_change(acs, atus, S_md19, S_md24))
    if mb is not None: figs.append(fig_chains(mb, obs))
    summary = dict(ks=ks, flow_fit=flow_fit, rts_usual_wfh=rts_wfh, nrep=nrep, atus_n=dict(md24=nA24, md19=nA19, dmv24=nD24))
    pickle.dump(summary, open(f"{TAB}/summary.pkl", "wb"))
    open(f"{TAB}/t24_tables.md", "w").write("\n".join(md))
    print("\n".join(md)); print(summary); return figs


# ------------------------------------------------------------------------------------------------ figures
G = {}                                     # model results by setting, filled by main()
# model series drawn in the figures: frozen model first (TASHA), then the variant with the 2024 telework input
SER = [("acs2024", "ABIT, observed 2024 population", ps.MODEL), ("silo2024", "ABIT, forecast 2024 population", "#86b6ef"),
       ("acs2024_tw", "ABIT with 2024 telework input, observed population", ps.VARIANT)]
SER_STAT = {"acs2024": "Observed population", "silo2024": "Forecast population", "acs2024_tw": "With 2024 telework input", "silo2024_tw": "Forecast population with telework input"}


def series():
    return [(s, l, c) for s, l, c in SER if s in G]


def handles(obs_label, kind="bar"):
    h = [Patch(facecolor=c, label=l) for _, l, c in series()] if kind == "bar" else []
    return h + [Patch(facecolor=COL["obs"], label=obs_label)]


def p_departure(ax, oh, ks=None, every=1):
    """Departure from home to work by hour (share of the 24-h frequency); KS text box when ks is given."""
    x = np.arange(24); k = "Maryland|workers"
    ser = [(100 * hser(G[s], k, "commute_dep_share", "WORK").loc[HOUR_ORDER].values, c) for s, _, c in series()] + [(100 * oh.loc[HOUR_ORDER].values, COL["obs"])]
    paired_bars(ax, x, ser)
    ax.set_xticks(x[::every]); ax.set_xticklabels([str(h) for h in HOUR_ORDER][::every]); ax.set_xlim(-0.6, 23.6); ax.grid(axis="x", visible=False)
    ax.set_xlabel("Departure from home to work (hh)"); ax.set_ylabel("% of 24hr Frequency")
    top = max(v.max() for v, _ in ser); ax.set_ylim(0, nice_top(top * 1.2)); ax.yaxis.set_major_locator(MultipleLocator(5))
    if ks is None: return None
    txt = "Kolmogorov–Smirnov test\n" + "\n".join(f"{SER_STAT[s]}: D = {d:.3f}, {ptxt(p)}" for s, (d, p, n) in ks.items())
    return ax.text(0.98, 0.96, txt, transform=ax.transAxes, ha="right", va="top", fontsize=ps.FONT, color=ps.INK)


def fig_departure(oh, ks):
    fig, ax = ps.figure(2.9); t = p_departure(ax, oh, ks)
    fig.legend(handles=handles("ACS 2024"), loc="outside upper center", ncol=2)
    clear_space(fig, ax, [t]); return save(fig, "fig_t24_departure")


def p_traveltime(ax, acsT):
    x = np.arange(len(C.TT_LABELS)); k = "Maryland|workers"
    o = acsT[(acsT.vintage == "acs2024") & (acsT.area == "Maryland")].set_index("bin").share.reindex(C.TT_LABELS).values
    get = lambda m: m["H"][(m["H"].key == k) & (m["H"].metric == "commute_tt_share")].set_index("type")["mean"].reindex(C.TT_LABELS).values
    ser = [(100 * get(G[s]), c) for s, _, c in series()] + [(100 * o, COL["obs"])]
    paired_bars(ax, x, ser); ax.set_xticks(x); ax.set_xticklabels(C.TT_LABELS); ax.grid(axis="x", visible=False)
    ax.set_xlabel("Travel time to work (minutes)"); ax.set_ylabel("Share of commuters (%)"); ax.set_ylim(0, nice_top(max(v.max() for v, _ in ser) * 1.15))


def fig_traveltime(acsT):
    fig, ax = ps.figure(2.7); p_traveltime(ax, acsT)
    fig.legend(handles=handles("ACS 2024"), loc="outside upper center", ncol=2)
    return save(fig, "fig_t24_traveltime")


def p_mode(ax, am):
    y = np.arange(len(C.COMMUTE_MODES)); k = "Maryland|workers"
    get = lambda m: np.array([sval(m, k, "commute_mode", md_) for md_ in C.COMMUTE_MODES])
    ser = [(100 * get(G[s]), c) for s, _, c in series()] + [(100 * am.reindex(C.COMMUTE_MODES).share.values, COL["obs"])]
    n = len(ser); h = 0.8 / n
    for i, (v, c) in enumerate(ser): ax.barh(y - (i - (n - 1) / 2) * h, v, h, color=c, lw=0)
    ax.set_yticks(y); ax.set_yticklabels([m.capitalize() for m in C.COMMUTE_MODES]); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share of commuters (%)"); ax.set_xlim(0, 100)


def fig_mode(am):
    fig, ax = ps.figure(2.9); p_mode(ax, am)
    fig.legend(handles=handles("ACS 2024"), loc="outside upper center", ncol=2)
    return save(fig, "fig_t24_mode")


def p_start(ax, Hobs, ty, stats=True, every=2, k="Maryland|15+"):
    """Start-time distribution of one activity type, model series (no forecast population) against the Maryland diaries; KS text
    box (returned) when stats is True."""
    x = np.arange(24); mods = [(s, l, c) for s, l, c in series() if s != "silo2024"]
    nacts = Hobs[(Hobs.key == k) & (Hobs.metric == "dur_n")].groupby("type").value.sum()
    ov = 100 * ohser(Hobs, k, "start_share", ty).fillna(0).loc[HOUR_ORDER].values
    ser = [(100 * hser(G[s], k, "start_share", ty).loc[HOUR_ORDER].values, c) for s, _, c in mods]
    paired_bars(ax, x, ser + [(ov, COL["obs"])])
    ax.set_ylim(0, nice_top(max(max(v.max() for v, _ in ser), ov.max()) * 1.25)); ax.set_xticks(x[::every]); ax.set_xticklabels([str(h) for h in HOUR_ORDER[::every]]); ax.set_xlim(-0.6, 23.6)
    ax.grid(axis="x", visible=False); ax.set_xlabel("Activity Start Time (hh)"); ax.set_ylabel("% of 24hr Frequency")
    lines = ["Kolmogorov–Smirnov test"]; ksv = {}
    for (s, _, _), (mv, _) in zip(mods, ser):
        nz = (mv > 0) | (ov > 0); d, p, _ = C.ks_values(mv[nz], ov[nz]); ksv[s] = (d, p)
        lines.append(f"{'Frozen' if s == 'acs2024' else 'Telework input'}: D = {d:.3f}, {ptxt(p)}")
    lines.append(f"Diary activities: {int(nacts.get(ty, 0))}")
    if not stats: return ksv
    left = ov[:12].sum() < ov[12:].sum()
    return ax.text(0.03 if left else 0.97, 0.96, "\n".join(lines), transform=ax.transAxes, ha="left" if left else "right", va="top", fontsize=ps.FONT, color=ps.INK)


def fig_start(Hobs, n_obs, Hdmv, n_dmv):
    fig = ps.new_figure(6.6); gs = fig.add_gridspec(3, 2)
    pos = {"WORK": gs[0, 0], "SHOPPING": gs[1, 0], "OTHER": gs[2, 0], "SCHOOL": gs[0:2, 1], "HOME": gs[2, 1]}
    mods = [(s, l, c) for s, l, c in series() if s != "silo2024"]
    fig.legend(handles=[Patch(facecolor=c, label=l) for _, l, c in mods] + [Patch(facecolor=COL["obs"], label=f"ATUS 2021–2024, Maryland ({n_obs} diaries)")],
               loc="outside upper center", ncol=2)
    placed = []
    for ty in C.TYPES:
        ax = fig.add_subplot(pos[ty]); t = p_start(ax, Hobs, ty)
        ax.set_title(TTITLE[ty], loc="center", fontsize=ps.FONT, fontweight="bold", color=ps.INK)
        clear_space(fig, ax, [t]); placed.append((ax, t))
    for _ in range(2):                                   # the layout re-flows when another panel's limits change
        for ax, t in placed: clear_space(fig, ax, [t])
    return save(fig, "fig_t24_start")


def p_duration(ax, Hobs, Hdmv, ty, stats=True, MIN_N=10, k="Maryland|15+"):
    """Roorda Fig. 7 form: mean duration by start hour; diary curves only at hours with >= MIN_N diary activities; KS on the
    hours both curves cover (Maryland diaries).  Returns the KS text box (stats) or the KS values."""
    xh = np.arange(24) + 4 + 0.5; mods = [(s, l, c) for s, l, c in series() if s != "silo2024"]; obs = []
    for Hd in (Hobs, Hdmv):
        nn = ohser(Hd, k, "dur_n", ty).fillna(0).loc[HOUR_ORDER].values
        obs.append(np.where(nn >= MIN_N, ohser(Hd, k, "dur_mean", ty).loc[HOUR_ORDER].values, np.nan))
    late = np.arange(24) >= 17; curves = []; lines = ["Kolmogorov–Smirnov test"]; ksv = {}
    for s, l, c in mods:
        mv = hser(G[s], k, "dur_mean", ty).loc[HOUR_ORDER].values; mv = np.where(late & ~np.isfinite(obs[1]), np.nan, mv); curves.append(mv)
        ax.plot(xh, mv, color=c, lw=1.4)
        both = np.isfinite(mv) & np.isfinite(obs[0])
        nm = "Frozen" if s == "acs2024" else "Telework input"
        if both.sum() >= 3: d, p, _ = C.ks_values(mv[both], obs[0][both]); lines.append(f"{nm}: D = {d:.3f}, {ptxt(p)}"); ksv[s] = (d, p)
        else: lines.append(f"{nm}: too few diaries")
    ax.plot(xh, obs[1], color=COL["obs2"], lw=1.2, ls=(0, (2, 1.5)), marker="s", ms=2.5)
    ax.plot(xh, obs[0], color=COL["obs"], lw=1.4, ls=(0, (5, 2.5)), marker="o", ms=2.5)
    top = np.nanmax(np.r_[np.concatenate(curves), obs[0], obs[1]]); step = 120 if top > 200 else (30 if top < 100 else 60); ax.set_ylim(0, np.ceil(top * 1.4 / step) * step)
    ax.yaxis.set_major_locator(MultipleLocator(step)); ax.set_xlim(4, 25); ax.set_xticks(range(4, 25, 2)); ax.set_xticklabels([str(h % 24) for h in range(4, 25, 2)])
    ax.grid(axis="x", visible=False); ax.set_xlabel("Activity Start Time (hh)"); ax.set_ylabel("Duration (minutes)")
    if not stats: return ksv
    return ax.text(0.97, 0.97, "\n".join(lines), transform=ax.transAxes, ha="right", va="top", fontsize=ps.FONT, color=ps.INK)


def fig_duration(Hobs, n_obs, Hdmv, n_dmv, MIN_N=10):
    fig = ps.new_figure(5.0); gs = fig.add_gridspec(2, 2)
    mods = [(s, l, c) for s, l, c in series() if s != "silo2024"]
    for i, ty in enumerate(["WORK", "SCHOOL", "SHOPPING", "OTHER"]):
        ax = fig.add_subplot(gs[i // 2, i % 2]); t = p_duration(ax, Hobs, Hdmv, ty, MIN_N=MIN_N)
        ax.set_title(TTITLE[ty], loc="center", fontsize=ps.FONT, fontweight="bold", color=ps.INK)
        clear_space(fig, ax, [t])
    fig.legend(handles=[Line2D([], [], color=c, lw=1.4, label=l) for _, l, c in mods] +
                       [Line2D([], [], color=COL["obs"], lw=1.4, ls=(0, (5, 2.5)), marker="o", ms=2.5, label=f"ATUS 2021–2024, Maryland ({n_obs} diaries)"),
                        Line2D([], [], color=COL["obs2"], lw=1.2, ls=(0, (2, 1.5)), marker="s", ms=2.5, label=f"ATUS 2021–2024, DC, Maryland and Virginia ({n_dmv} diaries)")],
               loc="outside upper center", ncol=1)
    return save(fig, "fig_t24_duration")


def p_ownshare(ax, sh, order, lab):
    y = np.arange(len(order))
    series = [("model", COL["acs2024"], "o", SETLAB["acs2024"]), ("model_silo", COL["silo2024"], "s", SETLAB["silo2024"]), ("ACS 2024", COL["obs"], "D", "ACS 2024"),
              ("LODES 2022", COL["obs2"], "^", "LODES 2022")]
    for c, colr, mk, l in series:
        if c not in sh: continue
        ax.plot(100 * sh[c].reindex(order).values, y, ls="none", marker=mk, ms=4.5, color=colr, label=l, markeredgecolor="white", markeredgewidth=0.4)
    ax.set_yticks(y); ax.set_yticklabels([lab.get(u, str(u)) for u in order]); ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel("Workers employed in their home area (%)")
    ax.grid(axis="y", visible=False)


def fig_ownshare(sh, order, lab):
    fig, ax = ps.figure(3.2); p_ownshare(ax, sh, order, lab)
    h, l = ax.get_legend_handles_labels(); fig.legend(h, l, loc="outside upper center", ncol=2)
    return save(fig, "fig_t24_ownshare")


def p_change(ax, acs, atus, S19, S24):
    """Model change vs observed change 2017/18 -> 2024 (Roorda Table 2 'increase' columns as a figure).  Every model value is
    also marked with a dot, so that changes too small to show as a bar (the frozen model's) remain visible."""
    kW, kA = "Maryland|workers", "Maryland|15+"
    A = lambda v, metric: float(acs[(acs.vintage == v) & (acs.area == "Maryland") & (acs.metric == metric)].value.iloc[0])
    mods = [(b, f, l, c) for b, f, l, c in [("base", "acs2024", "Model, frozen", ps.MODEL), ("base_tw", "acs2024_tw", "Model with telework input", ps.VARIANT)] if b in G and f in G]
    def dm(metric, typ, key=kW, scale=1.0, rel=False):
        return [(pct(sval(G[f], key, metric, typ), sval(G[b], key, metric, typ)) if rel else scale * (sval(G[f], key, metric, typ) - sval(G[b], key, metric, typ))) for b, f, _, _ in mods]
    items = [("Workers with a work activity\non the weekday (pp)", dm("work_share", "WORK", scale=100),
              100 * (A("acs2024", "commuting on the reference day, share of workers") - A("acs2017_19", "commuting on the reference day, share of workers")),
              100 * (atus["atus_md_2021-2024_commute"]["work_share"] - atus["atus_md_2017-2019_commute"]["work_share"])),
             ("Departing 6:00–8:59\n(pp of commuters)", dm("commute_dep_6_9", "WORK", scale=100),
              100 * (A("acs2024", "departing 6:00-8:59, share of commuters") - A("acs2017_19", "departing 6:00-8:59, share of commuters")), np.nan),
             ("Mean departure\nto work (min)", dm("commute_dep_mean", "WORK"), A("acs2024", "mean departure time from home") - A("acs2017_19", "mean departure time from home"), np.nan),
             ("Mean travel time\nto work (min)", dm("commute_tt_mean", "WORK"), A("acs2024", "mean travel time to work") - A("acs2017_19", "mean travel time to work"), np.nan),
             ("Activities per person\n15+ (% change)", dm("acts_per_person", "ALL", key=kA, rel=True), np.nan,
              pct(oval(S24, kA, "acts_per_person", "ALL"), oval(S19, kA, "acts_per_person", "ALL")))]
    nb = len(mods) + 2; h = 0.8 / nb; y = np.arange(len(items))
    for j, (_, _, l, c) in enumerate(mods):
        v = np.array([it[1][j] for it in items]); yy = y - 0.4 + h * (j + 0.5)
        ax.barh(yy, v, h, color=c, label=l); ax.plot(v, yy, ls="none", marker="o", ms=3.2, color=c, markeredgecolor="white", markeredgewidth=0.4)
    ax.barh(y - 0.4 + h * (len(mods) + 0.5), [it[2] for it in items], h, color=COL["obs"], label="Observed, ACS 2017–19 to 2024")
    ax.barh(y - 0.4 + h * (len(mods) + 1.5), [it[3] for it in items], h, color=COL["obs2"], label="Observed, ATUS 2017–19 to 2021–24")
    ax.axvline(0, color=ps.INK2, lw=0.7); ax.set_yticks(y); ax.set_yticklabels([it[0] for it in items]); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Increase, 2017/18 to 2024"); vals = [v for it in items for v in list(it[1]) + [it[2], it[3]]]
    lo = np.nanmin(vals + [0]); hi = np.nanmax(vals + [0]); ax.set_xlim(np.floor(lo / 5) * 5 - 5, np.ceil(hi / 5) * 5 + 5)
    return items


def fig_change(acs, atus, S19, S24):
    """Model change vs observed change 2017/18 -> 2024 (Roorda Table 2 'increase' columns as a figure)."""
    fig, ax = ps.figure(3.6); p_change(ax, acs, atus, S19, S24)
    h_, l_ = ax.get_legend_handles_labels(); fig.legend(h_, l_, loc="outside upper center", ncol=2)
    return save(fig, "fig_t24_change")


def p_chains(ax, mb, obs):
    x = np.arange(1, 9); k = "Baltimore CBSA|5+"
    m = mb["H"][(mb["H"].key == k) & (mb["H"].metric == "chain_share")].set_index("hour")["mean"].reindex(range(1, 9)).values
    g = lambda S: S[(S.key == k) & (S.metric == "chain_share")].set_index("hour").value.reindex(range(1, 9)).values
    paired_bars(ax, x, [(100 * m, COL["acs2024"]), (100 * g(obs["rts"][1]), COL["obs"]), (100 * g(obs["nhts"][1]), COL["obs2"])], width=0.75)
    ax.set_xticks(x); ax.set_xticklabels([str(i) for i in range(1, 8)] + ["8+"]); ax.set_xlim(0.4, 8.6); ax.grid(axis="x", visible=False)
    ax.set_xlabel("No. of Trips Per Chain"); ax.set_ylabel("% of Total No. of Chains"); ax.set_ylim(0, 80); ax.yaxis.set_major_locator(MultipleLocator(10))


def fig_chains(mb, obs):
    fig, ax = ps.figure(2.3); p_chains(ax, mb, obs)
    lg = ax.legend(handles=[Patch(facecolor=COL["acs2024"], label=SETLAB["base"]), Patch(facecolor=COL["obs"], label="RTS 2017/18"), Patch(facecolor=COL["obs2"], label="NHTS 2017")],
                   loc="upper right"); clear_space(fig, ax, [lg])
    return save(fig, "fig_t24_chains_nhts")


if __name__ == "__main__":
    for f in main(): print(f)
