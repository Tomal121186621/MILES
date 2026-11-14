#!/usr/bin/env python3
"""Tables and figures of the TAZ re-specification (2026-10-28): model of record (tract) vs TAZ re-estimate vs TAZ re-specified.

    python3 activity/lib/tasha_estimation/compare_dc_tazr.py  -> 5_reports/estimation_manual/abit/tables/tab_dc_tazr_{keepdrop,fit,coef,collin}.tex,
                                   tab_cx_heldout_tazr.tex, tab_seq_heldout_tazr.tex; figures/dc_tazr_collin_<segment>.png;
                                   results/dc_tazr_keepdrop.csv, dc_tazr_coef_compare.csv, dc_tazr_fit_compare.csv, dc_tazr_collin_flags.csv
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import glob, os, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
from compare_dc_taz import tex, lab, num, segname, longtable, table, RES, TAB, FIG, DISC, SEGS   # noqa: E402

NAMES = {"old (tract)": "model of record (tract)", "new (TAZ)": "TAZ re-estimate", "TAZ re-specified": "TAZ re-specified",
         "old coef on TAZ records": "model of record, TAZ records", "new coef on TAZ records": "TAZ re-estimate, TAZ records",
         "new coef on tract records": "TAZ re-estimate, tract records", "TAZ re-specified coef on tract records": "TAZ re-specified, tract records"}


def cands():
    return pd.concat([pd.read_csv(f"{RES}/respec_candidates_{k}_tazr.csv") for k in ["primary", "stop"]], ignore_index=True)


def keepdrop():
    D = cands(); rows, out = [], []
    for s in SEGS:
        g = D[D.segment == s]; b = g[g.candidate.str.startswith("far=separate") & ~g.candidate.str.contains("dropped")].iloc[0]; c = g[g.chosen].iloc[0]
        bt, ct_ = b.terms.split(), c.terms.split()
        dropped = [t for t in bt if t not in ct_]; added = [t for t in ct_ if t not in bt]
        changes = []
        for t in dropped:
            if t in ("cgt", "ls"): changes.append((t, "dropped"))
        mp = [t for t in dropped if t.startswith(("d_", "dt_"))]
        if mp: changes.append((" + ".join(mp) + " → " + " + ".join(added), "merged"))
        reason = f"{b.max_r_pair.replace('~', ' ~ ')} r = {self_r(s, b.max_r_pair):+.2f}; max VIF {b.max_VIF:.1f} ({b.max_VIF_term})"
        for t, act in changes:
            r = dict(segment=s, term=t, action=act, reason_before=reason, dBIC=c.dBIC_vs_taz, dheldout_LL_obs=c.dheldout_LL_vs_taz,
                     max_abs_r_after=c.max_abs_r, max_VIF_after=c.max_VIF, chosen=c.candidate)
            out.append(r)
        txt = "; ".join(f"{tex(lab(t)) if act == 'dropped' else tex(t.replace('_', ' '))} {act}" for t, act in changes)
        rows.append(" & ".join([segname(s), txt, tex(reason), num(c.dBIC_vs_taz, 1), num(c.dheldout_LL_vs_taz, 4), num(c.max_abs_r, 2), num(c.max_VIF, 1)]))
    pd.DataFrame(out).to_csv(f"{RES}/dc_tazr_keepdrop.csv", index=False)
    table(f"{TAB}/tab_dc_tazr_keepdrop.tex", "TAZ re-specification against within-choice-set collinearity: terms dropped or merged (estimation half; held-out LL on the validation half).",
          "tab:dctazrkeepdrop", ["Segment", "Change", "Reason (TAZ re-estimate)", "$\\Delta$BIC", "\\makecell[b]{$\\Delta$ held-out\\\\LL/obs.}", "\\makecell[b]{max $|r|$\\\\after}", "\\makecell[b]{max VIF\\\\after}"], rows,
          "Sources: \\texttt{tasha\\_estimation/respec\\_dc\\_taz.py}, \\texttt{results/respec\\_candidates\\_\\{primary,stop\\}\\_tazr.csv} (all candidates), \\texttt{dc\\_tazr\\_keepdrop.csv}. "
          "Candidates: every combination of the far-range form (separate pieces; one slope from 20 or 10 km for primaries, from 10 or 5 km for stops; shopping stops also 5--20 km), "
          "car generalized time kept or dropped and, for stops, the mode-choice logsum kept or dropped. Rule: smallest BIC among the candidates with every $|r|\\leq 0.85$ and "
          "every VIF $<10$ among the kept terms. $\\Delta$ against the TAZ re-estimate of the same specification as the model of record (positive $\\Delta$BIC = worse fit). "
          "No candidate that keeps the logsum meets the rule ($|r|\\geq 0.91$ with the far detour piece in every stop segment); no term is kept on theoretical grounds against the rule.",
          "@{}lp{0.27\\linewidth}p{0.25\\linewidth}rrrr@{}", size="\\scriptsize")
    return pd.DataFrame(out)


def self_r(s, pair):
    R = pd.read_csv(f"{RES}/collin_{s}_taz.csv", index_col=0); a, b = pair.split("~"); return float(R.loc[a, b])


def coefs():
    old = pd.concat([pd.read_csv(f"{RES}/cx_estimates.csv"), pd.read_csv(f"{RES}/seq_estimates.csv")])
    taz = pd.concat([pd.read_csv(f"{RES}/cx_estimates_taz.csv"), pd.read_csv(f"{RES}/seq_estimates_taz.csv")])
    new = pd.concat([pd.read_csv(f"{RES}/cx_estimates_tazr.csv"), pd.read_csv(f"{RES}/seq_estimates_tazr.csv")])
    rows, out = [], []
    for s in SEGS:
        o = old[old.segment == s].set_index("param"); t = taz[taz.segment == s].set_index("param"); n = new[new.segment == s].set_index("param")
        rows.append(f"\\multicolumn{{7}}{{@{{}}l}}{{\\textbf{{{segname(s)}}}}} \\\\")
        for p in list(dict.fromkeys(list(o.index) + list(n.index))):
            g = lambda d, c: float(d.loc[p, c]) if p in d.index else np.nan
            out.append(dict(segment=s, param=p, record=g(o, "value"), record_se=g(o, "rob_se"), taz=g(t, "value"), taz_se=g(t, "rob_se"), tazr=g(n, "value"), tazr_se=g(n, "rob_se")))
            rows.append(" & ".join([tex(lab(p)), num(g(o, "value"), 4), num(g(o, "rob_se"), 4), num(g(t, "value"), 4), num(g(t, "rob_se"), 4), num(g(n, "value"), 4), num(g(n, "rob_se"), 4)]))
    pd.DataFrame(out).to_csv(f"{RES}/dc_tazr_coef_compare.csv", index=False)
    longtable(f"{TAB}/tab_dc_tazr_coef.tex", "Final destination models: model of record (tract), TAZ re-estimate and TAZ re-specified (estimation half, robust s.e.).", "tab:dctazrcoef",
              ["Variable", "\\makecell[b]{Record\\\\$\\hat\\beta$}", "s.e.", "\\makecell[b]{TAZ\\\\$\\hat\\beta$}", "s.e.", "\\makecell[b]{TAZ re-spec.\\\\$\\hat\\beta$}", "s.e."], rows,
              "Sources: \\texttt{cx\\_estimates.csv}, \\texttt{seq\\_estimates.csv}; \\texttt{*\\_taz.csv}; \\texttt{*\\_tazr.csv} (\\texttt{results/dc\\_tazr\\_coef\\_compare.csv}). -- : not in the model. "
              "Merged pieces (e.g.\\ detour 5--20\\,km) have one slope over the merged range. The TAZ re-specified rows are exported to \\path{coef_tasha_taz} and \\path{coef_tasha_cal_taz}.",
              "@{}L{0.4\\linewidth}rrrrrr@{}")


def fit():
    D = cands(); rows, out = [], []
    cxo = pd.read_csv(f"{RES}/cx_tests.csv").set_index("segment"); so = pd.read_csv(f"{RES}/seq_estimates.csv")
    fs = sorted(glob.glob(f"{RES}/biogeme_check_*_taz_tazr_sub.csv")); fs = [f for f in fs if "_all_" not in f]; bc = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("segment").set_index("segment") if fs else pd.DataFrame()
    for s in SEGS:
        g = D[D.segment == s]; b = g[g.candidate.str.startswith("far=separate") & ~g.candidate.str.contains("dropped")].iloc[0]; c = g[g.chosen].iloc[0]
        if s.endswith("primary"): LLo, Ko = cxo.loc[s, "LL_FX"], len(pd.read_csv(f"{RES}/cx_estimates.csv").query("segment == @s")); No = int(cxo.loc[s, "N"])
        else: q = so[so.segment == s]; LLo, Ko, No = float(q.LL.iloc[0]), len(q), int(q.N.iloc[0])
        r = dict(segment=s, N_record=No, K_record=Ko, LL_record=LLo, BIC_record=np.log(No) * Ko - 2 * LLo, N=int(c.N), K_taz=int(b.K), LL_taz=b.LL, BIC_taz=b.BIC,
                 K_tazr=int(c.K), LL_tazr=c.LL, BIC_tazr=c.BIC, heldout_taz=b.heldout_LL_obs, heldout_tazr=c.heldout_LL_obs,
                 bio_N=int(bc.loc[s, "N"]) if s in bc.index else np.nan, bio_dLL=float(bc.loc[s, "dLL"]) if s in bc.index else np.nan,
                 bio_dcoef_se=float(bc.loc[s, "max_abs_dcoef_over_se"]) if s in bc.index else np.nan)
        out.append(r)
        rows.append(" & ".join([segname(s), f"{Ko} / {r['K_taz']} / {r['K_tazr']}", num(LLo, 1), num(r["BIC_record"], 1), num(b.LL, 1), num(b.BIC, 1), num(c.LL, 1), num(c.BIC, 1),
                                num(b.heldout_LL_obs, 4), num(c.heldout_LL_obs, 4), "--" if not np.isfinite(r["bio_N"]) else f"{int(r['bio_N']):,}", num(r["bio_dLL"], 5), num(r["bio_dcoef_se"], 3)]))
    pd.DataFrame(out).to_csv(f"{RES}/dc_tazr_fit_compare.csv", index=False)
    table(f"{TAB}/tab_dc_tazr_fit.tex", "Fit of the final destination models: model of record (tract), TAZ re-estimate, TAZ re-specified; Biogeme check of the TAZ re-specified models.", "tab:dctazrfit",
          ["Segment", "$K$ rec./TAZ/re-spec.", "LL rec.", "BIC rec.", "LL TAZ", "BIC TAZ", "LL re-spec.", "BIC re-spec.", "\\makecell[b]{Held-out\\\\LL/obs. TAZ}", "\\makecell[b]{Held-out\\\\LL/obs. re-spec.}",
           "\\makecell[b]{Biogeme\\\\$N$}", "\\makecell[b]{Biogeme\\\\$\\Delta$LL}", "\\makecell[b]{max $|\\Delta\\beta|$\\\\/s.e.}"], rows,
          "Sources: \\texttt{results/dc\\_tazr\\_fit\\_compare.csv}, \\texttt{respec\\_candidates\\_*\\_tazr.csv}, \\texttt{biogeme\\_check\\_<segment>\\_taz\\_tazr\\_sub.csv}. The record and TAZ log-likelihoods are on different "
          "measurement models and are not comparable (Table~\\ref{tab:dctazfit}); TAZ and re-specified share data and sampled sets. Held-out: validation half, TAZ records, full choice set. "
          "Biogeme: Biogeme 3.3.5 (BFGS) on a random subsample (records, seed 7) against the PyTorch fit of the same subsample, started at the pooled Biogeme F; $\\Delta$LL = Biogeme $-$ PyTorch; -- : not completed (11\\,GB guard, or stopped under memory pressure from other jobs); the primaries share the mixture code that Biogeme confirmed on the full TAZ re-estimates (Table~\\ref{tab:dctazfit}).",
          "@{}lcrrrrrrrrrrr@{}", size="\\scriptsize")


def heldout():
    for kind, f_old, gcol, gl in [("primary", "cx", "tour", ["simple", "with stops", "all"]), ("stop", "seq", "position", ["out", "in", "all"])]:
        a = pd.read_csv(f"{RES}/{f_old}_heldout_taz.csv").rename(columns={gcol: "group"})
        if kind == "stop": a = a.rename(columns={"km_leg_obs": "km_obs", "km_leg_pred": "km_pred"})
        b = pd.read_csv(f"{RES}/{f_old}_heldout_tazr.csv")
        H = pd.concat([a, b], ignore_index=True); rows = []
        order = ["old (tract)", "new (TAZ)", "TAZ re-specified", "old coef on TAZ records", "new coef on tract records", "TAZ re-specified coef on tract records"]
        for s in [f"{p}_{kind}" for p in DISC]:
            for half in ["estimation", "validation"]:
                for m in order:
                    for g in gl:
                        q = H[(H.segment == s) & (H.half == half) & (H.model == m) & (H.group == g)]
                        if not len(q): continue
                        r = q.iloc[0]
                        rows.append(" & ".join([segname(s), half, tex(NAMES[m]), r.data, g, f"{int(r.N):,}", num(r.LL_per_obs, 3), num(r.km_obs, 2), num(r.km_pred, 2), num(r.KS, 3)]))
        H.to_csv(f"{RES}/{f_old}_heldout_compare_tazr.csv", index=False)
        longtable(f"{TAB}/tab_{f_old}_heldout_tazr.tex",
                  ("Primaries" if kind == "primary" else "Sequential stops") + ": held-out checks of the model of record, the TAZ re-estimate and the TAZ re-specified model (full choice set).",
                  f"tab:{f_old}heldouttazr", ["Segment", "Half", "Model", "Records", "Group", "$N$", "LL/obs.", "km obs.", "km pred.", "KS"], rows,
                  f"Sources: \\texttt{{results/{f_old}\\_heldout\\_taz.csv}}, \\texttt{{{f_old}\\_heldout\\_tazr.csv}} (combined: \\texttt{{{f_old}\\_heldout\\_compare\\_tazr.csv}}). "
                  "Distance " + ("from home by tour type" if kind == "primary" else "of the leg to the stop from anchor $a$ by position") +
                  "; observed on tract records = zone of the tract internal point, on TAZ records = the TAZ location mixture. LL/obs.\\ is comparable only between rows on the same records. KS: binned "
                  "trip-length distribution, all records. Weighted by the trip weight.", "@{}llp{0.17\\linewidth}llrrrrr@{}")


def collinearity():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("bgr", ["#2a78d6", "#f0efec", "#e34948"]); cmap.set_bad("#d9d8d4")
    rows, flags = [], []
    for s in SEGS:
        R = pd.read_csv(f"{RES}/collin_{s}_tazr.csv", index_col=0); V = pd.read_csv(f"{RES}/vif_{s}_tazr.csv", index_col=0).iloc[:, 0]
        nm = list(R.index); A = R.values; k = len(nm)
        pairs = [(nm[i], nm[j], A[i, j]) for i in range(k) for j in range(i + 1, k) if abs(A[i, j]) > 0.8]
        for a, b, r in pairs: flags.append(dict(segment=s, var1=a, var2=b, r=r, VIF1=V[a], VIF2=V[b]))
        top = V.sort_values(ascending=False)
        rows.append(" & ".join([segname(s), str(k), num(float(np.abs(A - np.eye(k)).max()), 2), f"{tex(top.index[0])} ({top.iloc[0]:.1f})", str(int((V > 10).sum())),
                                "; ".join(f"{tex(a)}--{tex(b)} {r:.2f}" for a, b, r in pairs) or "none"]))
        A_ = A.copy(); np.fill_diagonal(A_, np.nan)
        fig, ax = plt.subplots(figsize=(0.32 * k + 2.4, 0.32 * k + 1.6), dpi=200)
        im = ax.imshow(A_, cmap=cmap, vmin=-1, vmax=1)
        ax.set_xticks(range(k)); ax.set_yticks(range(k)); ax.set_xticklabels(nm, rotation=90, fontsize=6.5); ax.set_yticklabels([f"{n}  (VIF {V[n]:.1f})" for n in nm], fontsize=6.5)
        for i in range(k):
            for j in range(k):
                if i != j and abs(A[i, j]) > 0.8:
                    ax.text(j, i, f"{A[i, j]:.2f}", ha="center", va="center", fontsize=4.8, color="#1a1a19")
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec="#1a1a19", lw=1.0, zorder=3))
        ax.set_xticks(np.arange(-0.5, k, 1), minor=True); ax.set_yticks(np.arange(-0.5, k, 1), minor=True)
        ax.grid(which="minor", color="#fcfcfb", lw=0.6); ax.tick_params(which="minor", length=0)
        for sp in ax.spines.values(): sp.set_visible(False)
        cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02); cb.ax.tick_params(labelsize=6); cb.outline.set_visible(False); cb.set_label("within-choice-set correlation", fontsize=6.5)
        ax.set_title(f"{segname(s)} (TAZ re-specified): demeaned correlation, |r| > 0.8 boxed", fontsize=8, loc="left")
        fig.tight_layout(); fig.savefig(f"{FIG}/dc_tazr_collin_{s}.png", facecolor="#fcfcfb", bbox_inches="tight"); plt.close(fig)
    pd.DataFrame(flags).to_csv(f"{RES}/dc_tazr_collin_flags.csv", index=False)
    table(f"{TAB}/tab_dc_tazr_collin.tex", "TAZ re-specified models: within-choice-set collinearity (sampled sets of the estimation half).", "tab:dctazrcollin",
          ["Segment", "$K$", "max $|r|$", "largest VIF", "VIF $>10$", "pairs with $|r|>0.8$"], rows,
          "Sources: \\texttt{results/collin\\_<segment>\\_tazr.csv}, \\texttt{vif\\_<segment>\\_tazr.csv}; heatmaps \\path{figures/dc_tazr_collin_<segment>.png}. Method as Table~\\ref{tab:dctazcollin}.",
          "@{}lrrlrp{0.45\\linewidth}@{}", size="\\scriptsize")
    return pd.DataFrame(flags)


if __name__ == "__main__":
    K = keepdrop(); coefs(); fit(); heldout(); F = collinearity()
    print(K.to_string()); print(F.to_string())
