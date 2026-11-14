"""Helpers for the <model>_estimation.ipynb notebooks of the manual-estimation package.

Plain pandas / numpy / matplotlib; nothing here changes a model. The notebooks import it with
    sys.path.insert(0, "../../tools"); import nbtools as nt
"""
import os, re, subprocess, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ID_LIKE = re.compile(r"(^|_)(id|household|serial|person|student|worker|zone|puma\d*|migpuma|slot|j|idx|row|tour_id|record)$", re.I)


# ---------------------------------------------------------------- running scripts
def run(cmd, cwd):
    """Run a shell command and stream its output into the notebook line by line; raises if it fails."""
    print(f"$ cd {os.path.relpath(cwd)}\n$ {cmd}\n", flush=True)
    p = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         executable="/bin/bash")
    for line in p.stdout:
        if "warn" not in line.lower():
            print(line, end="", flush=True)
    if p.wait() != 0:
        raise RuntimeError(f"command failed (exit {p.returncode})")


def files_table(folder):
    """Files of a folder with their size (MB)."""
    rows = []
    for root, _, fs in os.walk(folder):
        for f in sorted(fs):
            if f.startswith("."):
                continue
            p = os.path.join(root, f)
            rows.append({"file": os.path.relpath(p, folder), "MB": round(os.path.getsize(p) / 1e6, 2)})
    return pd.DataFrame(rows)


def preview(path, n=5):
    """First rows of a csv / parquet file (other files: None)."""
    if path.endswith(".parquet"):
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(path)
        return pf.read_row_group(0).slice(0, n).to_pandas(), pf.metadata.num_rows
    if path.endswith((".csv", ".csv.gz")):
        return pd.read_csv(path, nrows=n), None
    return None, None


# ---------------------------------------------------------------- choice data
def alt_columns(df):
    """Alternative-specific columns <stem>_<j> -> {stem: [columns ordered by j]} (stems with at least 2 alternatives)."""
    out = {}
    for c in df.columns:
        m = re.match(r"^(.+)_(\d+)$", c)
        if m:
            out.setdefault(m.group(1), []).append((int(m.group(2)), c))
    return {s: [c for _, c in sorted(v)] for s, v in out.items() if len(v) >= 2}


def stack_alternatives(df, stems, av_stem="av", max_rows=400_000, seed=1):
    """Wide table (one row per decision maker, columns <stem>_<j>) -> long table of the available alternatives,
    one column per stem. A random sample of max_rows rows is kept for large tables (correlations only)."""
    alts = alt_columns(df)
    J = len(alts[stems[0]])
    parts = []
    for j in range(J):
        part = pd.DataFrame({s: df[alts[s][j]].to_numpy() for s in stems if j < len(alts[s])})
        if av_stem in alts and j < len(alts[av_stem]):
            part = part[df[alts[av_stem][j]].to_numpy() > 0]
        parts.append(part)
    long = pd.concat(parts, ignore_index=True)
    if len(long) > max_rows:
        long = long.sample(max_rows, random_state=seed)
    return long


def model_variables(expr):
    """Names of the data columns used by a Biogeme expression."""
    from biogeme.expressions import list_of_variables_in_expression
    return sorted({v.name for v in list_of_variables_in_expression(expr)})


def explanatory(X):
    """Numeric columns that vary and are not identifiers."""
    keep = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c]) and not ID_LIKE.search(c) and X[c].nunique() > 1]
    return X[keep].astype(float)


# ---------------------------------------------------------------- correlation
def corr_heatmap(X, title, annotate=None, ax=None):
    """Pearson correlation heatmap (diverging, -1..1)."""
    C = X.corr()
    k = len(C)
    annotate = k <= 22 if annotate is None else annotate
    if ax is None:
        size = max(5.5, min(0.42 * k + 2.5, 22))
        _, ax = plt.subplots(figsize=(size, size * 0.85))
    im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(k)); ax.set_xticklabels(C.columns, rotation=90, fontsize=8 if k < 40 else 6)
    ax.set_yticks(range(k)); ax.set_yticklabels(C.columns, fontsize=8 if k < 40 else 6)
    if annotate:
        for i in range(k):
            for j in range(k):
                v = C.values[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                            color="white" if abs(v) > 0.6 else "black")
    plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="correlation")
    ax.set_title(title, fontsize=11)
    plt.tight_layout(); plt.show()
    return C


def high_pairs(C, threshold=0.7):
    """Pairs of variables with |r| >= threshold."""
    rows = []
    cols = list(C.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = C.iat[i, j]
            if np.isfinite(r) and abs(r) >= threshold:
                rows.append({"variable 1": cols[i], "variable 2": cols[j], "r": round(r, 3)})
    return pd.DataFrame(rows).sort_values("r", key=abs, ascending=False) if rows else pd.DataFrame(columns=["variable 1", "variable 2", "r"])


def vif(X):
    """Variance inflation factors (diagonal of the inverse correlation matrix); constant columns dropped."""
    X = X.loc[:, X.std() > 0]
    C = np.corrcoef(X.values, rowvar=False)
    inv = np.linalg.pinv(C)
    return pd.DataFrame({"variable": X.columns, "VIF": np.round(np.diag(inv), 2)}).sort_values("VIF", ascending=False)


# ---------------------------------------------------------------- results
def stars(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


def estimates_table(results):
    """Biogeme estimates in the article format: coefficient (stars), robust s.e. (4 digits), p."""
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=results)["Estimated parameters"]
    t = t.rename(columns={"Name": "parameter", "Value": "coefficient", "Robust std err.": "robust_se",
                          "Robust t-stat.": "t", "Robust p-value": "p"})
    t["stars"] = t["p"].map(stars)
    return t


def fmt_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def article_format(t):
    return pd.DataFrame({"parameter": t["parameter"],
                         "Coefficient": [f"{c:.4f}{s}" for c, s in zip(t["coefficient"], t["stars"])],
                         "Robust s.e.": [f"{s:.4f}" for s in t["robust_se"]],
                         "p": [fmt_p(p) for p in t["p"]]})


def compare(t, reference_csv):
    """Your estimates next to the article values (model/reference_estimates.csv)."""
    ref = reference_parameters(reference_csv)
    cc = "article_coefficient" if "article_coefficient" in ref else "coefficient"
    cs = "article_robust_se" if "article_robust_se" in ref else "robust_se"
    lab = next((c for c in ["article_label", "label"] if c in ref), None)
    r = ref[["parameter"] + ([lab] if lab else []) + [cc, cs]].rename(columns={cc: "article_coef", cs: "article_se", lab or "x": "label"})
    r = r.dropna(subset=["article_coef"])
    m = t[["parameter", "coefficient", "robust_se", "p"]].merge(r, on="parameter", how="outer", indicator=True)
    m["diff_coef"] = m["coefficient"] - m["article_coef"]
    m["diff_se"] = m["robust_se"] - m["article_se"]
    # the article prints 4 decimals: a difference of up to one unit in the 4th decimal is rounding
    tol = 1.0001e-4
    m["matches_article"] = (m["diff_coef"].abs() <= tol) & ((m["diff_se"].abs() <= tol) | m["article_se"].isna())
    m["_merge"] = m["_merge"].astype(str).map({"both": "", "left_only": "only in Biogeme", "right_only": "only in the article"})
    # reference categories: printed as 0 in the article without a standard error, not estimated
    ref0 = (m["_merge"] == "only in the article") & (m["article_coef"] == 0) & m["article_se"].isna()
    m.loc[ref0, "_merge"] = "reference category (0, not estimated)"
    m.loc[ref0, "matches_article"] = True
    return m.rename(columns={"_merge": "note"})


def reference_parameters(reference_csv):
    """Parameter rows of reference_estimates.csv (model statistics and heading rows removed)."""
    ref = pd.read_csv(reference_csv)
    ref = ref[ref["parameter"].notna() & ~ref["parameter"].isin(["LL0", "LL_beta", "LL_holdout", "N", "K"])]
    if "note" in ref:
        ref = ref[ref["note"].fillna("") != "model statistic"]
    return ref


def article_statistics(reference_csv):
    """Fit statistics reported in the article (rows 'model statistic' of reference_estimates.csv), if any."""
    ref = pd.read_csv(reference_csv)
    if "note" in ref:
        s = ref[ref["note"].fillna("") == "model statistic"]
        return s[["parameter", "coefficient"]].rename(columns={"parameter": "statistic", "coefficient": "article"})
    s = ref[ref["parameter"].isin(["LL0", "LL_beta", "LL_holdout", "N", "K"])]
    col = "article_coefficient" if "article_coefficient" in ref else "coefficient"
    s = s[["parameter", col]].rename(columns={"parameter": "statistic", col: "article"})
    s["statistic"] = s["statistic"].replace({"LL_beta": "LL(beta)", "LL0": "LL(0)"})
    return s


# ---------------------------------------------------------------- location models (ABIT): zone-by-zone variables
def location_long(df, zones, n_records=300, seed=1):
    """Stack the zone variables of the first configuration (imp_0_<zone>, cgt_0_<zone>) of a sample of records with the
    zone attributes of each zone: one row per record x zone."""
    zcols = {}
    for c in df.columns:
        m = re.match(r"^(imp|cgt)_0_(\d+)$", c)
        if m:
            zcols.setdefault(m.group(1), {})[int(m.group(2))] = c
    s = df.sample(min(n_records, len(df)), random_state=seed)
    nz = len(zones)
    out = {k: np.concatenate([s[v[j]].to_numpy() for j in range(nz)]) for k, v in zcols.items()}
    long = pd.DataFrame(out)
    za = zones.sort_values("idx").reset_index(drop=True)
    for a in ["lnretden", "mix", "cbd", "bc", "dcz", "va", "othst"]:
        if a in za:
            long[a] = np.repeat(za[a].to_numpy(), len(s))
    for a in ["pop", "ret", "off", "oth", "stu"]:
        if a in za:
            long[f"ln1p_{a}"] = np.repeat(np.log1p(za[a].to_numpy()), len(s))
    return long


def plot_against_article(m, title):
    """Estimated vs article coefficients, and estimates with 95 % robust intervals."""
    m = m.dropna(subset=["coefficient", "article_coef"])
    fig, axes = plt.subplots(1, 2, figsize=(13, max(4, 0.22 * len(m) + 1.5)), gridspec_kw={"width_ratios": [1, 1.4]})
    a = axes[0]
    lo, hi = np.nanmin(m[["coefficient", "article_coef"]].values), np.nanmax(m[["coefficient", "article_coef"]].values)
    a.plot([lo, hi], [lo, hi], color="0.6", lw=1, ls="--")
    a.scatter(m["article_coef"], m["coefficient"], s=22, color="#2b6cb0")
    a.set_xlabel("article coefficient"); a.set_ylabel("your Biogeme coefficient"); a.set_title("Agreement with the article")
    b = axes[1]
    y = np.arange(len(m))[::-1]
    b.errorbar(m["coefficient"], y, xerr=1.96 * m["robust_se"], fmt="o", ms=4, color="#2b6cb0", ecolor="#90b4dd", lw=1.5, capsize=0)
    b.scatter(m["article_coef"], y, marker="|", s=120, color="#c05621", label="article", zorder=3)
    b.axvline(0, color="0.5", lw=0.8)
    b.set_yticks(y); b.set_yticklabels(m["parameter"], fontsize=7)
    b.set_title("Estimates with 95 % robust intervals"); b.legend(loc="lower right", fontsize=8)
    fig.suptitle(title); plt.tight_layout(); plt.show()


def fit_statistics(results):
    """Goodness of fit of a Biogeme estimation."""
    g = {}
    for k, f in [("Observations", None), ("Parameters K", "number_of_free_parameters"), ("Final LL", "final_loglikelihood"),
                 ("rho-square (null)", "rho_square_null"), ("adjusted rho-square (null)", "rho_bar_square_null"),
                 ("AIC", "akaike_information_criterion"), ("BIC", "bayesian_information_criterion"),
                 ("Gradient norm", "gradient_norm"), ("Converged", "algorithm_has_converged")]:
        if f is None:
            continue
        try:
            v = getattr(results, f)
            v = v() if callable(v) else v
            g[k] = v
        except Exception:
            pass
    return pd.Series(g, name="value").to_frame()


def parameter_correlation(results, title, threshold=0.7):
    """Heatmap of the robust correlation of the estimates, and the pairs above the threshold."""
    names = list(results.get_beta_values().keys())
    V = results.robust_variance_covariance_matrix
    V = np.asarray(V() if callable(V) else V)
    sd = np.sqrt(np.diag(V))
    C = pd.DataFrame(V / np.outer(sd, sd), index=names, columns=names)
    k = len(C)
    size = max(6, min(0.32 * k + 2.5, 24))
    fig, ax = plt.subplots(figsize=(size, size * 0.85))
    im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(k)); ax.set_xticklabels(names, rotation=90, fontsize=7 if k < 50 else 5)
    ax.set_yticks(range(k)); ax.set_yticklabels(names, fontsize=7 if k < 50 else 5)
    plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="robust correlation of the estimates")
    ax.set_title(title); plt.tight_layout(); plt.show()
    return high_pairs(C, threshold)
