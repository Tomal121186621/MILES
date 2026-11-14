#!/usr/bin/env python3
"""Destination models of record (TAZ locations, 2026-10-29): article estimation tables, robust covariances, parameter correlations.

    python3 activity/lib/tasha_estimation/article_dc_taz.py
      -> results/cov_<segment>_taz.csv (robust covariance of the estimates, from work/fit_<segment>_taz.pkl)
         5_reports/article/sections/est/est_dc_<P>_primary.tex, est_stop_<P>_stop.tex (rows, notes and fit of the TAZ estimates;
         the layout of the existing files is kept; stars from the unrounded robust t: *** p < 0.01, ** p < 0.05, * p < 0.10)
         5_reports/estimation_manual/destinations_short/figures/fig_param_corr_{a,b}.png, tables/param_corr.tex
"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, pickle, re, sys
import numpy as np
import pandas as pd
from scipy.stats import norm
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"; sys.path.insert(0, f"{os.path.dirname(CODE)}/destination_choice")
RES = f"{HERE}/results"; WORK = f"{HERE}/work"; V = os.path.dirname(os.path.dirname(HERE))
EST = f"{V}/5_reports/article/sections/est"; SHORT = f"{V}/5_reports/estimation_manual/destinations_short"
DISC = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
BIO = {"SHOPPING_primary": "full", "RECREATION_primary": "full", "ACCOMPANY_primary": "full", "OTHER_primary": "sub", "SHOPPING_stop": "sub"}


def m(x, d):
    s = f"{x:,.{d}f}"; return s.replace("-", "$-$", 1) if s.startswith("-") else s


def star(t):
    a = abs(t); s = "***" if a >= norm.ppf(0.995) else "**" if a >= norm.ppf(0.975) else "*" if a >= norm.ppf(0.95) else ""
    return f"$^{{{s}}}$" if s == "***" else (f"$^{{{s}\\phantom{{{'*' * (3 - len(s))}}}}}$" if s else "$^{\\phantom{***}}$")


def pval(t):
    p = 2 * norm.sf(abs(t)); return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def covs():
    for k in ["primary", "stop"]:
        for p in DISC:
            seg = f"{p}_{k}"; f = pickle.load(open(f"{WORK}/fit_{seg}_taz.pkl", "rb"))
            names = list(f["table"].param); pd.DataFrame(f["cov"], index=names, columns=names).to_csv(f"{RES}/cov_{seg}_taz.csv")


def tables():
    for kind, fe, ft, ll in [("primary", "cx_estimates_taz.csv", "cx_tests_taz.csv", "LL_FX"), ("stop", "seq_estimates_taz.csv", "seq_tests_taz.csv", "LL")]:
        E = pd.read_csv(f"{RES}/{fe}"); TT = pd.read_csv(f"{RES}/{ft}").set_index("segment")
        for p in DISC:
            seg = f"{p}_{kind}"; fn = f"{EST}/est_dc_{seg}.tex" if kind == "primary" else f"{EST}/est_stop_{seg}.tex"
            src = f"{EST}/est_dc_{seg}_pre_stars.tex" if kind == "primary" else f"{EST}/est_stop_{seg}_pre_stars.tex"
            old = open(fn).read(); lines = old.split("\n")
            rows_i = [i for i, l in enumerate(lines) if l.startswith("    ") and l.rstrip().endswith("\\\\") and " & " in l and "multicolumn" not in l and "Coefficient &" not in l]
            t = E[E.segment == seg].reset_index(drop=True)
            if len(rows_i) != len(t): raise SystemExit(f"{seg}: {len(rows_i)} rows in the table, {len(t)} estimates")
            for i, r in zip(rows_i, t.itertuples()):
                lab_ = lines[i].split(" & ")[0]
                lab_ = lab_.replace("stop in the home zone", "stop in the zone of the previous location").replace("stop in the primary-destination zone", "stop in the zone of the next anchor")
                lines[i] = f"{lab_} & {m(r.value, 4)}{star(r.rob_t)} & {r.rob_se:.4f} & {m(r.rob_t, 2)} & {pval(r.rob_t)} \\\\"
            s = TT.loc[seg]; N = int(s.N); K = int(s.K) if "K" in s else len(t); L = float(s[ll]); L0 = float(s.LL0)
            aic = 2 * K - 2 * L; bic = np.log(N) * K - 2 * L
            mu = t.set_index("param").loc["mu_size"]; tmu = (mu.value - 1) / mu.rob_se
            bio = {"full": " Re-estimated in Biogeme 3.3.5: the same log-likelihood to $10^{-5}$ and the same estimates to below 0.01 s.e.",
                   "sub": " Re-estimated in Biogeme 3.3.5 on a subsample of the records: the same log-likelihood to $10^{-5}$."}.get(BIO.get(seg), "")
            note = ("Estimation: maximum likelihood with a PyTorch implementation (robust sandwich covariance), unweighted." + bio +
                    " Locations: the survey's traffic zones, spread over the model zones by housing units (home ends) or jobs (activity ends);"
                    " the likelihood is averaged over the possible zones of the destination and of the anchors (location mixture)."
                    " Sampling of alternatives: 40 importance draws with the McFadden positive-conditioning correction."
                    + (" Size term $\\mu\\ln(1+S_j)$ with the size weights $\\exp(\\theta)$ relative to the base component;"
                       f" $\\mu=1$ is {'rejected' if abs(tmu) > 1.96 else 'not rejected'} (Wald $t$ = {m(tmu, 2)})."))
            stats = [f"Observations: {N:,}; alternatives: 1,588 zones; sampled sets of up to {int(s.J)}; parameters: {K}.",
                     f"LL(0) = {m(L0, 1)}; LL($\\hat\\beta$) = {m(L, 1)}; $\\rho^2$ = {1 - L / L0:.3f}; adjusted $\\rho^2$ = {1 - (L - K) / L0:.3f}; AIC = {m(aic, 1)}; BIC = {m(bic, 1)}.",
                     note, "$^{***}$ $p<0.01$, $^{**}$ $p<0.05$, $^{*}$ $p<0.10$ (robust $t$)."]
            mc = [i for i, l in enumerate(lines) if "\\multicolumn{5}{@{}L{0.98\\linewidth}}" in l]
            new = [f"    \\multicolumn{{5}}{{@{{}}L{{0.98\\linewidth}}}}{{{x}}} \\\\" for x in stats]
            lines = lines[:mc[0]] + new + lines[mc[-1] + 1:]
            ci = [i for i, l in enumerate(lines) if "\\caption{" in l][0]
            if "traffic zones" not in lines[ci]:
                lines[ci] = lines[ci].replace(" Dependent variable:", " Destinations located by the survey's traffic zones. Dependent variable:")
                lines[ci] = lines[ci].replace("(estimation half of the Regional Travel Survey)", "(estimation half of the Regional Travel Survey)")
            open(fn, "w").write("\n".join(lines))
            print(seg, "rows", len(t), "N", N, "LL", round(L, 1))


def short_figs():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from report_destinations_tables import short as sh
    cmap = LinearSegmentedColormap.from_list("bgr", ["#2a78d6", "#f0efec", "#e34948"]); cmap.set_bad("#d9d8d4")
    rows = []
    for k in ["primary", "stop"]:
        for p in DISC:
            seg = f"{p}_{k}"; C = pd.read_csv(f"{RES}/cov_{seg}_taz.csv", index_col=0); sd = np.sqrt(np.diag(C.values)); R = C.values / np.outer(sd, sd)
            nm = [("ln size (μ)" if x == "mu_size" else "θ " + x[6:] if x.startswith("theta_") else sh(x)) for x in C.index]
            A = np.abs(R - np.eye(len(R))); i, j = np.unravel_index(A.argmax(), A.shape)
            rows.append(f"{ {'SHOPPING': 'Shopping', 'RECREATION': 'Recreation', 'ACCOMPANY': 'Accompany', 'OTHER': 'Other errands'}[p]}, {'main' if k == 'primary' else 'stop'} & "
                        f"{nm[i].replace('μ', '$\\mu$').replace('θ', '$\\theta$')} -- {nm[j].replace('μ', '$\\mu$').replace('θ', '$\\theta$')} & {R[i, j]:.2f} & {int((A > 0.8).sum() // 2)} \\\\".replace("-0.", "$-$0."))
            if seg in ("SHOPPING_primary", "OTHER_stop"):
                R_ = R.copy(); np.fill_diagonal(R_, np.nan); n = len(R)
                fig, ax = plt.subplots(figsize=(0.3 * n + 2.4, 0.3 * n + 1.4), dpi=200); im = ax.imshow(R_, cmap=cmap, vmin=-1, vmax=1)
                ax.set_xticks(range(n)); ax.set_yticks(range(n)); ax.set_xticklabels(nm, rotation=90, fontsize=6.5); ax.set_yticklabels(nm, fontsize=6.5)
                for a in range(n):
                    for b in range(n):
                        if a != b and abs(R[a, b]) >= 0.6: ax.text(b, a, f"{R[a, b]:.2f}", ha="center", va="center", fontsize=4.6, color="#1a1a19")
                ax.set_xticks(np.arange(-.5, n, 1), minor=True); ax.set_yticks(np.arange(-.5, n, 1), minor=True); ax.grid(which="minor", color="#fcfcfb", lw=.6); ax.tick_params(which="minor", length=0)
                for s_ in ax.spines.values(): s_.set_visible(False)
                cb = fig.colorbar(im, ax=ax, fraction=.035, pad=.02); cb.ax.tick_params(labelsize=6); cb.outline.set_visible(False); cb.set_label("correlation of the estimates", fontsize=6.5)
                fig.savefig(f"{SHORT}/figures/fig_param_corr_{'a' if k == 'primary' else 'b'}.png", facecolor="#fcfcfb", bbox_inches="tight"); plt.close(fig)
    open(f"{SHORT}/tables/param_corr.tex", "w").write("\\footnotesize\\setlength{\\tabcolsep}{3pt}\\begin{tabular}{@{}llrr@{}}\\toprule\nModel & largest correlation of two estimates & $r$ & pairs $|r|>0.8$ \\\\ \\midrule\n"
                                                       + "\n".join(rows) + "\n\\bottomrule\\end{tabular}\n")


if __name__ == "__main__":
    covs(); tables(); short_figs()
