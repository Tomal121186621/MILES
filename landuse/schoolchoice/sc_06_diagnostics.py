#!/usr/bin/env python3
"""Collinearity diagnostics of the school choice (the method of jobchoice/rts_23_diagnostics.py), by segment.
1 Within-choice-set correlation (estimation half, sampled sets, available entries of each row demeaned within the row): every
  stepwise candidate, ln S at the final size weights and ln of the in-boundary public enrolment (K-12); heatmap; pairs |r| > 0.6;
  VIFs of all variables and of the selected ones.
2 Parameter correlations of the final full-set model (tables/cov_<seg>_FULLSET.csv): heatmap, pairs |r| > 0.8, condition number.
Outputs tables/diag_within_corr_<seg>.csv, diag_within_pairs.csv, diag_vif.csv, diag_param_corr_<seg>.csv, diag_param_pairs.csv,
diag_condition.csv; figures/fig_within_corr_<seg>.png, fig_param_corr_<seg>.png.   Usage: sc_06_diagnostics.py"""
import os, sys, json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sc_03_engine as G; import sc_common as C; import sc_04_stepwise as S   # noqa: E402
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.linewidth": 0.6})
CMAP = LinearSegmentedColormap.from_list("div", ["#2b5c8a", "#9fb7cc", "#e6e6e6", "#e0b48a", "#a8571a"])   # rts_23: two hues, neutral gray midpoint
LAB = {"t": "time", "lt": "ln(1+time)", "ls": "logsum", "intra": "same zone", "cc": "other county", "ccpub": "other county x public share", "cs": "other state",
       "t*agec": "time x age", "t*female": "time x female", "t*g1": "time x <40k", "t*g4": "time x 125k+", "t*car0": "time x no car", "t*carlow": "time x fewer cars",
       "lnS": "ln size", "lnPin": "ln(1+in-boundary public)", "lnPriv": "ln(1+private)", "lnCC": "ln(1+2-year)", "lnPriv4": "ln(1+private 4-year)",
       "mu_size": "size coefficient", "g_pub_in": "in-boundary weight", "g_priv": "private weight", "g_priv4": "private 4-year weight", "g_cc": "2-year weight",
       "h_privXg1": "private x <40k"}
def lab(k): return LAB.get(k, LAB.get(k.replace("b_", "").replace("X", "*"), k))
def heat(M, names, fname, title):
    n = len(names); fig, ax = plt.subplots(figsize=(0.32 * n + 2.0, 0.32 * n + 1.5), dpi=300)
    im = ax.imshow(M, cmap=CMAP, vmin=-1, vmax=1); ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels([lab(x) for x in names], rotation=90, fontsize=6); ax.set_yticklabels([lab(x) for x in names], fontsize=6)
    ax.set_xticks(np.arange(-.5, n), minor=True); ax.set_yticks(np.arange(-.5, n), minor=True); ax.grid(which="minor", color="white", linewidth=0.6); ax.tick_params(which="minor", length=0)
    for i in range(n):
        for j in range(n):
            if i != j and abs(M[i, j]) > 0.6: ax.text(j, i, f"{M[i, j]:.2f}".replace("0.", "."), ha="center", va="center", fontsize=4.5, color="black")
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02); cb.set_label("correlation", fontsize=7); cb.ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=7, loc="left"); fig.tight_layout(); fig.savefig(f"{C.FIG}/{fname}", dpi=300); plt.close(fig)
pairs, vifs, pp, cond = [], [], [], []
for seg in C.SEG:
    D = G.Design(seg); fj = json.load(open(f"{C.W}/final_{seg}.json")); c = fj["coef_fullset"]
    steps = S.STEPS["col" if seg == "col" else "k12"]; cands = ["t"] + [k for _, g in steps for k in g if ":" not in k]
    ew = np.ones(len(D.comps))
    for k, cn in enumerate(D.comps):
        if f"g_{cn}" in c: ew[k] = np.exp(c[f"g_{cn}"])
    lnS = np.log((ew[:, None, None] * D.NK).sum(0) + 1e-9); av = D.av; cols = {}
    def dm(x): x = np.where(av, x, np.nan); return (x - np.nanmean(x, axis=1, keepdims=True))[av]
    cols["lnS"] = dm(lnS)
    if seg != "col": cols["lnPin"] = dm(np.log1p(D.NK[1])); cols["lnPriv"] = dm(np.log1p(D.NK[2]))
    else: cols["lnPriv4"] = dm(np.log1p(D.NK[1])); cols["lnCC"] = dm(np.log1p(D.NK[2]))
    for k in cands: cols[k] = dm(D.X(k).astype(float))
    X = pd.DataFrame(cols); X = X.loc[:, X.std() > 1e-12]; R = X.corr(); R.to_csv(f"{C.T}/diag_within_corr_{seg}.csv")
    pairs += [dict(seg=seg, var1=a, var2=b, r=R.loc[a, b]) for i, a in enumerate(R.index) for b in R.index[i + 1:] if abs(R.loc[a, b]) > 0.6]
    v = np.diag(np.linalg.pinv(R.values)); vifs += [dict(seg=seg, set="all candidates", variable=k, VIF=x) for k, x in zip(R.index, v)]
    sel = ["lnS"] + [k for k in fj["spec"] if k in R.index] + [k for k in fj.get("fixed", {}) if k in R.index]
    vs = np.diag(np.linalg.inv(R.loc[sel, sel].values)); vifs += [dict(seg=seg, set="selected (incl. fixed logsum)", variable=k, VIF=x) for k, x in zip(sel, vs)]
    heat(R.values, list(R.index), f"fig_within_corr_{seg}.png", f"{C.SEG_LABEL[seg]}: within-choice-set correlation of the candidate variables")
    Cv = pd.read_csv(f"{C.T}/cov_{seg}_FULLSET.csv", index_col=0); s = np.sqrt(np.diag(Cv.values)); Rp = Cv.values / np.outer(s, s); nm = list(Cv.index)
    pd.DataFrame(Rp, index=nm, columns=nm).to_csv(f"{C.T}/diag_param_corr_{seg}.csv")
    pp += [dict(seg=seg, par1=nm[i], par2=nm[j], r=Rp[i, j]) for i in range(len(nm)) for j in range(i + 1, len(nm)) if abs(Rp[i, j]) > 0.8]
    ev = np.linalg.eigvalsh(Rp); cond.append(dict(seg=seg, condition_number_param_corr=ev.max() / ev.min(), smallest_eig=ev.min(), max_abs_r=float(np.abs(Rp - np.eye(len(nm))).max())))
    heat(Rp, nm, f"fig_param_corr_{seg}.png", f"{C.SEG_LABEL[seg]}: correlation of the full-set estimates (robust)")
pd.DataFrame(pairs).sort_values("r", key=np.abs, ascending=False).to_csv(f"{C.T}/diag_within_pairs.csv", index=False)
pd.DataFrame(vifs).to_csv(f"{C.T}/diag_vif.csv", index=False); pd.DataFrame(pp, columns=["seg", "par1", "par2", "r"]).to_csv(f"{C.T}/diag_param_pairs.csv", index=False)
pd.DataFrame(cond).to_csv(f"{C.T}/diag_condition.csv", index=False)
pd.set_option("display.width", 200)
print(pd.DataFrame(pairs).round(3).to_string(index=False)); print(pd.DataFrame(vifs).round(2).to_string(index=False)); print(pd.DataFrame(pp).round(3).to_string(index=False)); print(pd.DataFrame(cond).round(3).to_string(index=False))
