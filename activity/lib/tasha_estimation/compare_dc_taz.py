#!/usr/bin/env python3
"""Comparison of the TAZ variant with the destination models of record (2026-10-28).

    python3 activity/lib/tasha_estimation/compare_dc_taz.py   -> 5_reports/estimation_manual/abit/tables/tab_dc_taz_{counts,fit,coef,collin}.tex,
                                   tab_cx_heldout_taz.tex, tab_seq_heldout_taz.tex;
                                   5_reports/estimation_manual/abit/figures/dc_taz_collin_<segment>.png;
                                   tasha_estimation/results/dc_taz_coef_compare.csv, dc_taz_collin_flags.csv
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import json, os, pickle, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; A3 = os.path.dirname(HERE); sys.path.insert(0, f"{MILES_HOME}/activity/lib/destination_choice")
from export_dc import lab as ulab       # noqa: E402
RES = f"{HERE}/results"; WORK = f"{HERE}/work"
MAN = f"{os.path.dirname(A3)}/5_reports/estimation_manual/abit"; TAB = f"{MAN}/tables"; FIG = f"{MAN}/figures"; os.makedirs(FIG, exist_ok=True)
DCR = f"{A3}/destination_choice/results"
DISC = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]; PN = {"SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompany", "OTHER": "Other errands"}
SEGS = [f"{p}_primary" for p in DISC] + [f"{p}_stop" for p in DISC]


def segname(s): p, k = s.split("_"); return f"{PN[p]}, {k}"


def tex(s):
    s = str(s).replace("\\", "").replace("$", "\\$").replace("&", "\\&").replace("_", "\\_")
    for a, b in [("–", "--"), ("×", "$\\times$"), ("≥", "$\\geq$"), ("≤", "$\\leq$"), (" < ", " $<$ "), (" > ", " $>$ "), ("μ", "$\\mu$"), ("θ", "$\\theta$"), ("²", "$^2$")]:
        s = s.replace(a, b)
    return s


def lab(p):
    if p == "lnd_multi": return "ln(distance) × tour with at least one stop"
    if p == "intra_a": return "stop in the zone of anchor a"
    if p == "intra_b": return "stop in the zone of anchor b"
    return ulab(p)


def num(x, d=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)): return "--"
    s = f"{x:,.{d}f}"; return s.replace("-", "$-$") if s.startswith("-") else s


def pct(x): return "--" if not np.isfinite(x) else f"{100 * x:.1f}"


def longtable(path, caption, label, head, rows, note, spec):
    n = len(head)
    h = " & ".join(head) + " \\\\"
    L = ["{\\scriptsize\\setlength{\\tabcolsep}{2pt}", f"\\begin{{longtable}}{{{spec}}}", f"  \\caption{{{caption}}}\\label{{{label}}}\\\\", "  \\toprule", f"  {h}", "  \\midrule",
         "  \\endfirsthead", f"  \\multicolumn{{{n}}}{{@{{}}l}}{{\\scriptsize\\itshape Table \\thetable{{}} continued}}\\\\", "  \\toprule", f"  {h}", "  \\midrule", "  \\endhead",
         "  \\midrule", f"  \\multicolumn{{{n}}}{{r@{{}}}}{{\\scriptsize\\itshape continued on the next page}}\\\\", "  \\endfoot", "  \\bottomrule", "  \\endlastfoot"]
    L += [f"    {r} \\\\" if not r.startswith("\\") else f"    {r}" for r in rows]
    L += ["    \\midrule", f"    \\multicolumn{{{n}}}{{@{{}}p{{0.97\\linewidth}}@{{}}}}{{\\scriptsize {note}}} \\\\", "\\end{longtable}}"]
    open(path, "w").write("\n".join(L) + "\n")


def table(path, caption, label, head, rows, note, spec, size="\\footnotesize"):
    n = len(head)
    L = ["\\begin{table}[!htbp]", "  \\centering", f"  \\caption{{{caption}}}\\label{{{label}}}", f"  {size}\\setlength{{\\tabcolsep}}{{3pt}}", f"  \\resizebox{{\\linewidth}}{{!}}{{\\begin{{tabular}}{{{spec}}}", "    \\toprule",
         "    " + " & ".join(head) + " \\\\", "    \\midrule"]
    L += [f"    {r} \\\\" if not r.startswith("\\") else f"    {r}" for r in rows]
    L += ["    \\midrule", f"    \\multicolumn{{{n}}}{{@{{}}p{{0.97\\linewidth}}@{{}}}}{{\\scriptsize {note}}} \\\\", "    \\bottomrule", "  \\end{tabular}}", "\\end{table}"]
    open(path, "w").write("\n".join(L) + "\n")


# ------------------------------------------------------------------------------------------------ counts
def counts():
    S = pd.read_csv(f"{RES}/dc_taz_sources.csv"); rows = []
    S["o"] = S.half.map({"estimation": 0, "validation": 1}) * 100 + S.kind.map({"primary": 0, "stop": 1}) * 10 + S.purpose.map({p: i for i, p in enumerate(DISC)})
    for _, r in S.sort_values("o").iterrows():
        a = r["a_changed"] if r.kind == "stop" else r["home_changed"]; b = r["b_changed"] if r.kind == "stop" else np.nan
        tr = r.get("dloc_src:tract split", 0.0) + (r.get("dloc_src:tract point", 0.0) if np.isfinite(r.get("dloc_src:tract point", np.nan)) else 0.0)
        rows.append(" & ".join([segname(f"{r.purpose}_{r.kind}"), r.half, f"{int(r.N_tract):,}", f"{int(r.N_taz):,}", f"{int(r.N_both):,}", pct(r.dest_changed), pct(r.dest_split),
                                pct(a), pct(b), pct(r.any_changed), pct(r.n_cfg_gt1), pct(r["dloc_src:bmc"]), pct(r["dloc_src:tpb"]), pct(tr)]))
    table(f"{TAB}/tab_dc_taz_counts.tex", "Traffic-zone locations of the destination records and the share of records whose zone differs from the zone of the tract internal point.", "tab:dctazcounts",
          ["Segment", "Half", "$N$ tract", "$N$ TAZ", "$N$ both", "\\makecell[b]{Dest.\\\\changed}", "\\makecell[b]{Dest.\\\\split}", "\\makecell[b]{Home / $a$\\\\changed}",
           "\\makecell[b]{$b$\\\\changed}", "\\makecell[b]{Any\\\\changed}", "\\makecell[b]{$>1$\\\\config.}", "BMC", "TPB", "Tract"], rows,
          "Sources: \\texttt{tasha\\_estimation/prep\\_dc\\_taz.py}, \\texttt{results/dc\\_taz\\_sources.csv}. Percentages. Changed: the most likely TAZ zone differs from the zone of the tract "
          "internal point (destination; home for primaries, anchor $a$ = origin of the trip to the stop for stops; anchor $b$ for stops), among the records in both sets. Split: the destination "
          "is spread over two or more zones (weights $\\geq$1\\,\\%). $>1$ config.: more than one anchor configuration. BMC, TPB, Tract: source of the destination location (record rule of "
          "\\texttt{rts\\_11\\_data\\_v2.py}; tract = the tract split by LODES jobs, or the tract point).", "@{}llrrrrrrrrrrrr@{}", size="\\scriptsize")


# ------------------------------------------------------------------------------------------------ fit
def fit():
    cxo = pd.read_csv(f"{RES}/cx_tests.csv").set_index("segment"); cxn = pd.read_csv(f"{RES}/cx_tests_taz.csv").set_index("segment")
    so = pd.read_csv(f"{RES}/seq_estimates.csv"); sn = pd.read_csv(f"{RES}/seq_tests_taz.csv").set_index("segment")
    import glob
    fs = [f for f in sorted(glob.glob(f"{RES}/biogeme_check_*_taz.csv")) + sorted(glob.glob(f"{RES}/biogeme_check_*_taz_sub.csv")) if "_all_" not in f and not f.endswith("check_taz.csv")]
    bc = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("segment").set_index("segment") if fs else pd.DataFrame()
    if len(bc): bc["sample"] = bc["sample"].fillna("full") if "sample" in bc else "full"
    bc.reset_index().to_csv(f"{RES}/biogeme_check_taz.csv", index=False) if len(bc) else None
    cxe = pd.read_csv(f"{RES}/cx_estimates.csv")
    rows, out = [], []
    for s in SEGS:
        if s.endswith("primary"):
            o = cxo.loc[s]; n = cxn.loc[s]; K = int((cxe.segment == s).sum())
            r = dict(segment=s, N_old=int(o.N), LL_old=o.LL_FX, BIC_old=o.BIC_FX, N_new=int(n.N), K=K, LL_new=n.LL_FX, BIC_new=n.BIC_FX, LL_oldcoef_taz=n.LL_old_coef_on_taz)
        else:
            g = so[so.segment == s]; n = sn.loc[s]; K = len(g); N = int(g.N.iloc[0]); LL = float(g.LL.iloc[0])
            r = dict(segment=s, N_old=N, LL_old=LL, BIC_old=np.log(N) * K - 2 * LL, N_new=int(n.N), K=K, LL_new=n.LL, BIC_new=n.BIC, LL_oldcoef_taz=n.LL_old_coef_on_taz)
        r["dLL_same_data"] = r["LL_new"] - r["LL_oldcoef_taz"]
        r["biogeme_dLL"] = float(bc.loc[s, "dLL"]) if s in bc.index else np.nan
        r["biogeme_dcoef_se"] = float(bc.loc[s, "max_abs_dcoef_over_se"]) if s in bc.index else np.nan
        r["biogeme_sample"] = bc.loc[s, "sample"] if s in bc.index else "not run"; r["bio_mark"] = "$^*$" if r["biogeme_sample"] != "full" else ""
        out.append(r)
        rows.append(" & ".join([segname(s), str(r["K"]), f"{r['N_old']:,}", num(r["LL_old"], 1), num(r["BIC_old"], 1), f"{r['N_new']:,}", num(r["LL_new"], 1), num(r["BIC_new"], 1),
                                num(r["LL_oldcoef_taz"], 1), num(r["dLL_same_data"], 1), num(r["biogeme_dLL"], 4) + r["bio_mark"], num(r["biogeme_dcoef_se"], 3)]))
    pd.DataFrame(out).to_csv(f"{RES}/dc_taz_fit_compare.csv", index=False)
    table(f"{TAB}/tab_dc_taz_fit.tex", "Fit of the destination models of record (traffic zones) and of the tract-based estimates (primaries with the complexity term, sequential stops), estimation half.", "tab:dctazfit",
          ["Segment", "$K$", "$N$ tract", "LL tract", "BIC tract", "$N$ TAZ", "LL TAZ", "BIC TAZ", "\\makecell[b]{LL old coef.\\\\on TAZ sets}", "\\makecell[b]{$\\Delta$LL\\\\same data}",
           "\\makecell[b]{Biogeme\\\\$\\Delta$LL}", "\\makecell[b]{Biogeme\\\\max $|\\Delta\\beta|$/s.e.}"], rows,
          "Sources: \\texttt{cx\\_tests.csv}, \\texttt{seq\\_estimates.csv} (tract-based estimates) and \\texttt{cx\\_tests\\_taz.csv}, \\texttt{seq\\_tests\\_taz.csv}, \\texttt{biogeme\\_check\\_taz.csv}. "
          "The tract and TAZ log-likelihoods are not comparable: the tract model contains $\\ln b_{zt}$ with the area weights $b_{zt}=\\operatorname{area}(z\\cap t)/\\operatorname{area}(z)$ "
          "(Eq.~\\eqref{eq:meas}), the TAZ model the mixture weights that sum to one, and the samples differ. The comparison on the same data is the column LL old coef.\\ on TAZ sets "
          "(tract-based coefficients evaluated on the TAZ sampled sets) and $\\Delta$LL. Biogeme: re-estimation of the TAZ model in Biogeme 3.3.5 (BFGS, no second derivatives) from the warm start of the PyTorch fit (pooled Biogeme F), $\\Delta$LL = Biogeme $-$ PyTorch; "
          "$^*$: on a random subsample of 1,500 records with its own PyTorch fit (\\texttt{estimate\\_dc\\_taz.py biosub}), because the Biogeme mixture expression of these segments exceeded the time or memory budget on the full sample. --: not checked (recreation, accompany and other-errand stops: Biogeme grew beyond 13\\,GB even on the subsample and was stopped to respect the memory limit; the PyTorch mixture likelihood equals \\texttt{dc\\_model.ll\\_obs} exactly for one configuration).",
          "@{}lrrrrrrrrrrr@{}", size="\\scriptsize")


# ------------------------------------------------------------------------------------------------ coefficients
def coefs():
    old = pd.concat([pd.read_csv(f"{RES}/cx_estimates.csv"), pd.read_csv(f"{RES}/seq_estimates.csv")])
    new = pd.concat([pd.read_csv(f"{RES}/cx_estimates_taz.csv"), pd.read_csv(f"{RES}/seq_estimates_taz.csv")])
    gm = pd.read_csv(f"{RES}/seq_estimates_tract_male.csv") if os.path.exists(f"{RES}/seq_estimates_tract_male.csv") else pd.DataFrame(columns=["segment", "param", "value", "rob_se"])
    rows, out = [], []
    for s in SEGS:
        o = old[old.segment == s].set_index("param"); n = new[new.segment == s].set_index("param"); g = gm[gm.segment == s].set_index("param")
        rows.append(f"\\multicolumn{{8}}{{@{{}}l}}{{\\textbf{{{segname(s)}}}}} \\\\")
        for p in o.index:
            d = n.value[p] - o.value[p]; z = d / o.rob_se[p]; ratio = n.rob_se[p] / o.rob_se[p]
            gv = g.value[p] if p in g.index else np.nan
            out.append(dict(segment=s, param=p, old=o.value[p], old_se=o.rob_se[p], new=n.value[p], new_se=n.rob_se[p], diff=d, diff_over_se_old=z,
                            se_ratio=ratio, tract_male=gv, tract_male_se=g.rob_se[p] if p in g.index else np.nan, beyond_1se=abs(z) > 1))
            mark = "$^\\dagger$" if abs(z) > 1 else ""
            rows.append(" & ".join([tex(lab(p)), num(o.value[p], 4), num(o.rob_se[p], 4), num(n.value[p], 4) + mark, num(n.rob_se[p], 4), num(z, 2), num(ratio, 2), num(gv, 4)]))
    D = pd.DataFrame(out); D.to_csv(f"{RES}/dc_taz_coef_compare.csv", index=False)
    longtable(f"{TAB}/tab_dc_taz_coef.tex", "Destination models: tract-based estimates against the models of record on traffic zones (estimation half, robust s.e.).", "tab:dctazcoef",
              ["Variable", "\\makecell[b]{Tract\\\\$\\hat\\beta$}", "s.e.", "\\makecell[b]{TAZ\\\\$\\hat\\beta$}", "s.e.", "$\\Delta/\\text{s.e.}_{\\text{tract}}$", "\\makecell[b]{s.e. ratio\\\\TAZ/tract}",
               "\\makecell[b]{Tract,\\\\male fixed}"], rows,
              "Sources: \\texttt{cx\\_estimates.csv}, \\texttt{seq\\_estimates.csv} (tract-based), \\texttt{cx\\_estimates\\_taz.csv}, \\texttt{seq\\_estimates\\_taz.csv}, "
              "\\texttt{seq\\_estimates\\_tract\\_male.csv}; all in \\texttt{results/dc\\_taz\\_coef\\_compare.csv}. $^\\dagger$: the change exceeds one robust s.e.\\ of the tract-based estimate. "
              "Tract, male fixed: the sequential stop models on the tract records with only the gender recode of the logsum (attribution of the change).", "@{}L{0.36\\linewidth}rrrrrrr@{}")
    return D


# ------------------------------------------------------------------------------------------------ held-out
MLAB = {"old (tract)": "tract-based", "new (TAZ)": "record (TAZ)", "old coef on TAZ records": "tract-based coef., TAZ records", "new coef on tract records": "record coef., tract records"}


def heldout():
    H = pd.read_csv(f"{RES}/cx_heldout_taz.csv"); rows = []
    for s in [f"{p}_primary" for p in DISC]:
        for _, r in H[(H.segment == s)].iterrows():
            rows.append(" & ".join([segname(s), r.half, tex(MLAB.get(r.model, r.model)), r.tour, f"{int(r.N):,}", num(r.LL_per_obs, 3), num(r.km_obs, 2), num(r.km_pred, 2), num(r.KS, 3)]))
    longtable(f"{TAB}/tab_cx_heldout_taz.tex", "Primary destinations: predictive LL per observation, mean distance from home by tour type and KS of the trip length (full choice set).",
              "tab:cxheldouttaz", ["Segment", "Half", "Model", "Tour", "$N$", "LL/obs.", "km obs.", "km pred.", "KS"], rows,
              "Source: \\texttt{tasha\\_estimation/results/cx\\_heldout\\_taz.csv}. Tract-based: the tract-based estimates on the tract records, observed = zone of the tract internal point. Record (TAZ): "
              "the models of record on the TAZ records, observed = the TAZ location mixture. Cross rows (validation half): each model's coefficients on the other records; LL/obs.\\ is comparable "
              "only between rows on the same records (tract: area weights $b_{zt}$; TAZ: mixture weights). KS: binned Kolmogorov--Smirnov statistic of the trip length (bins of "
              "\\texttt{rts\\_common.DIST\\_BINS}), all tours. Weighted by the trip weight.", "@{}llp{0.2\\linewidth}lrrrrr@{}")
    H = pd.read_csv(f"{RES}/seq_heldout_taz.csv"); rows = []
    for s in [f"{p}_stop" for p in DISC]:
        for _, r in H[(H.segment == s)].iterrows():
            rows.append(" & ".join([segname(s), r.half, tex(MLAB.get(r.model, r.model)), r.position, f"{int(r.N):,}", num(r.LL_per_obs, 3), num(r.km_leg_obs, 2), num(r.km_leg_pred, 2), num(r.KS, 3)]))
    longtable(f"{TAB}/tab_seq_heldout_taz.tex", "Sequential stops: predictive LL per observation, mean leg to the stop from anchor $a$ and KS of the leg length (full choice set).",
              "tab:seqheldouttaz", ["Segment", "Half", "Model", "Position", "$N$", "LL/obs.", "km obs.", "km pred.", "KS"], rows,
              "Source: \\texttt{tasha\\_estimation/results/seq\\_heldout\\_taz.csv}. As Table~\\ref{tab:cxheldouttaz}; the new coefficients on the tract records use the recoded gender.",
              "@{}llp{0.2\\linewidth}lrrrrr@{}")


# ------------------------------------------------------------------------------------------------ collinearity
SHORT = {"ln_size": "ln size"}


def collinearity():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("bgr", ["#2a78d6", "#f0efec", "#e34948"])
    rows, flags = [], []
    for s in SEGS:
        R = pd.read_csv(f"{RES}/collin_{s}_taz.csv", index_col=0); V = pd.read_csv(f"{RES}/vif_{s}_taz.csv", index_col=0).iloc[:, 0]
        nm = list(R.index); A = R.values; k = len(nm)
        pairs = [(nm[i], nm[j], A[i, j]) for i in range(k) for j in range(i + 1, k) if abs(A[i, j]) > 0.8]
        for a, b, r in pairs: flags.append(dict(segment=s, var1=a, var2=b, r=r, VIF1=V[a], VIF2=V[b]))
        top = V.sort_values(ascending=False)
        rows.append(" & ".join([segname(s), str(k), num(float(np.abs(A - np.eye(k)).max()), 2), f"{tex(top.index[0])} ({top.iloc[0]:.1f})", str(int((V > 10).sum())),
                                "; ".join(f"{tex(a)}--{tex(b)} {r:+.2f}".replace("+", "") for a, b, r in pairs) or "none"]))
        fig, ax = plt.subplots(figsize=(0.32 * k + 2.4, 0.32 * k + 1.6), dpi=200)
        A_ = A.copy(); np.fill_diagonal(A_, np.nan); cmap.set_bad("#d9d8d4"); im = ax.imshow(A_, cmap=cmap, vmin=-1, vmax=1)
        ax.set_xticks(range(k)); ax.set_yticks(range(k)); ax.set_xticklabels(nm, rotation=90, fontsize=6.5); ax.set_yticklabels([f"{n}  (VIF {V[n]:.1f})" for n in nm], fontsize=6.5)
        for i in range(k):
            for j in range(k):
                if i != j and abs(A[i, j]) > 0.8:
                    ax.text(j, i, f"{A[i, j]:.2f}", ha="center", va="center", fontsize=4.8, color="#ffffff" if abs(A[i, j]) > 0.9 else "#1a1a19")
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec="#1a1a19", lw=1.0, zorder=3))
        ax.set_xticks(np.arange(-0.5, k, 1), minor=True); ax.set_yticks(np.arange(-0.5, k, 1), minor=True)
        ax.grid(which="minor", color="#fcfcfb", lw=0.6); ax.tick_params(which="minor", length=0)
        for sp in ax.spines.values(): sp.set_visible(False)
        cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02); cb.ax.tick_params(labelsize=6); cb.outline.set_visible(False)
        cb.set_label("within-choice-set correlation", fontsize=6.5)
        ax.set_title(f"{segname(s)}: demeaned correlation, |r| > 0.8 boxed", fontsize=8, loc="left")
        fig.tight_layout(); fig.savefig(f"{FIG}/dc_taz_collin_{s}.png", facecolor="#fcfcfb", bbox_inches="tight"); plt.close(fig)
    pd.DataFrame(flags).to_csv(f"{RES}/dc_taz_collin_flags.csv", index=False)
    table(f"{TAB}/tab_dc_taz_collin.tex", "Destination models of record: within-choice-set collinearity of the final models (sampled sets of the estimation half).", "tab:dctazcollin",
          ["Segment", "$K$", "max $|r|$", "largest VIF", "VIF $>10$", "pairs with $|r|>0.8$"], rows,
          "Sources: \\texttt{results/collin\\_<segment>\\_taz.csv}, \\texttt{vif\\_<segment>\\_taz.csv}, \\texttt{dc\\_taz\\_collin\\_flags.csv}; heatmaps "
          "\\path{figures/dc_taz_collin_<segment>.png}. Each variable is demeaned within the sampled choice set of the record (padding excluded; anchor configurations weighted by "
          "$w_k$); the size term enters as $\\ln(1+S_j)$ at the estimates. VIF $=$ diagonal of the inverse correlation matrix.", "@{}lrrlrp{0.5\\linewidth}@{}", size="\\scriptsize")
    return pd.DataFrame(flags)


if __name__ == "__main__":
    counts(); fit(); D = coefs(); heldout(); F = collinearity()
    print(D[D.beyond_1se].round(4).to_string()); print(F.round(3).to_string())
