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
def run(cmd, cwd, env=None, quiet=False):
    """Run a shell command and stream its output into the notebook line by line (quiet: only the last 12 lines); raises if it fails."""
    print(_scrub(f"$ cd {os.path.relpath(cwd)}\n$ {cmd.replace(sys.executable, 'python')}\n"), flush=True)
    e = dict(os.environ); e.update(env or {}); e["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         executable="/bin/bash", env=e)
    if quiet:
        lines = [_scrub(l) for l in p.stdout if "warn" not in l.lower()]
        print("".join(lines[-12:]), end="", flush=True)
        if p.wait() != 0:
            raise RuntimeError(f"command failed (exit {p.returncode})")
        return
    for line in p.stdout:
        if "warn" not in line.lower():
            print(_scrub(line), end="", flush=True)
    if p.wait() != 0:
        raise RuntimeError(f"command failed (exit {p.returncode})")


def _scrub(line):
    """Machine-specific path prefix removed from printed lines (paths shown from manual_estimation/)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return line.replace(root + "/", "").replace(os.path.dirname(root) + "/", "")


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
    """significance stars as in the article tables: *** p < 0.01, ** p < 0.05, * p < 0.10"""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


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


# ---------------------------------------------------------------- location models (MAST): zone-by-zone variables
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


# ================================================================ data walk-through (sections 1-4)
OBS = "#3b4252"        # observed data (paper figure style)
MODEL = "#e8811a"      # model (paper figure style)
LIGHT = "#9a9a9a"      # second observed series (hold-out half)
_ME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZONE_SHP = os.path.join(_ME, "ABIT", "00_shared_data", "raw", "mstm_zone_system", "SMZ_RMZ_02152011inMSTM_EPSG26918")
ZONE_SYSTEM = os.path.join(_ME, "ABIT", "00_shared_data", "raw", "mstm_zone_system", "zoneSystem.csv")
AREA_GROUPS = ["Baltimore City", "Baltimore suburbs", "Washington DC", "MD Washington suburbs", "Northern Virginia",
               "rest of Maryland", "outside (DE, PA, WV, rest of VA)"]
_BALT = {24003, 24005, 24013, 24025, 24027, 24035}
_WASH_MD = {24009, 24017, 24021, 24031, 24033}
_NOVA = {51013, 51107, 51510, 51919, 51942, 51059, 51600, 51610, 51153, 51683, 51685}


def area_group_of_county(fips):
    """County FIPS -> area group of the study region (Baltimore City / suburbs, Washington DC / MD suburbs, Northern Virginia...)."""
    f = pd.Series(fips).astype(float)
    out = np.select([f.eq(24510), f.isin(_BALT), f.eq(11001), f.isin(_WASH_MD), f.isin(_NOVA), (f // 1000).eq(24)],
                    AREA_GROUPS[:6], AREA_GROUPS[6])
    return pd.Categorical(out, categories=AREA_GROUPS, ordered=True)


_ZS = None
def zone_table():
    """Zone id -> county FIPS, jurisdiction name and area group (zoneSystem.csv of the MSTM)."""
    global _ZS
    if _ZS is None:
        z = pd.read_csv(ZONE_SYSTEM)[["ZoneId", "COUNTYFIPS", "JUR_NAME", "AREA_SQMI"]].rename(columns={"ZoneId": "zone", "COUNTYFIPS": "county"})
        z["area_group"] = area_group_of_county(z["county"])
        _ZS = z.set_index("zone")
    return _ZS


def area_group_of_zone(zones):
    return pd.Categorical(pd.Series(zones).map(zone_table()["area_group"].astype(str)), categories=AREA_GROUPS, ordered=True)


class Funnel:
    """Records kept / dropped by each preparation step."""
    def __init__(self, start_label, n):
        self.rows = [{"step": start_label, "records": int(n), "dropped": 0, "reason": ""}]

    def add(self, label, n, reason=""):
        prev = self.rows[-1]["records"]
        self.rows.append({"step": label, "records": int(n), "dropped": int(prev - n), "reason": reason})

    def table(self):
        t = pd.DataFrame(self.rows)
        t["dropped"] = t["dropped"].map(lambda v: "" if v == 0 else f"{v:,}")
        t["records"] = t["records"].map(lambda v: f"{v:,}")
        return t.set_index("step")


def counts(**tables):
    """Rows (and columns) of several tables."""
    return pd.DataFrame([{"table": k, "rows": f"{len(v):,}", "columns": v.shape[1] if hasattr(v, "shape") and len(v.shape) > 1 else 1}
                         for k, v in tables.items()]).set_index("table")


def checksum(df):
    """Order-independent checksum of a table: sum of the row hashes (64-bit), as hex."""
    d = df.reindex(sorted(df.columns), axis=1).copy()
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].astype(str)
    h = pd.util.hash_pandas_object(d, index=False).to_numpy(np.uint64)
    return f"{int(h.sum(dtype=np.uint64)):016x}"


def compare_frames(rebuilt, provided, key=None, tol=1e-9, name=""):
    """Rebuilt vs provided table: rows, columns, largest absolute difference of the numeric columns, differing values of the
    other columns, checksums. Returns a one-row summary."""
    r, p = rebuilt, provided
    if key:
        r = r.sort_values(key, kind="stable").reset_index(drop=True); p = p.sort_values(key, kind="stable").reset_index(drop=True)
    else:
        r = r.reset_index(drop=True); p = p.reset_index(drop=True)
    cols = [c for c in p.columns if c in r.columns]
    n = min(len(r), len(p)); mx = 0.0; ndiff = 0; dcols = []
    num = [c for c in cols if pd.api.types.is_numeric_dtype(r[c]) and pd.api.types.is_numeric_dtype(p[c])]
    oth = [c for c in cols if c not in num]
    if num and n:
        xv = r[num].iloc[:n].to_numpy(np.float64); yv = p[num].iloc[:n].to_numpy(np.float64)
        d = np.where(np.isnan(xv) & np.isnan(yv), 0.0, np.abs(xv - yv)); d = np.where(np.isnan(d), np.inf, d)
        mx = float(d.max()); bad = (d > tol).sum(axis=0); ndiff += int(bad.sum())
        dcols += [c for c, k in zip(num, bad) if k]
    for c in oth:
        k = int((r[c].iloc[:n].astype(str).to_numpy() != p[c].iloc[:n].astype(str).to_numpy()).sum())
        ndiff += k
        if k:
            dcols.append(c)
    same_cols = set(r.columns) == set(p.columns)
    ok = len(r) == len(p) and same_cols and ndiff == 0
    return pd.DataFrame([{"table": name, "rows rebuilt": f"{len(r):,}", "rows shipped": f"{len(p):,}",
                          "same columns": same_cols, "max abs difference": mx, "differing values": ndiff,
                          "differing columns": ", ".join(dcols[:8]) + (" ..." if len(dcols) > 8 else ""),
                          "checksum rebuilt": checksum(r[cols]), "checksum shipped": checksum(p[cols]),
                          "result": "identical" if ok and mx <= tol else "DIFFERENT"}])


def read_table(path):
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    if path.endswith((".pkl", ".pickle")):
        return pd.read_pickle(path)
    return pd.read_csv(path, low_memory=False)


def compare_folders(rebuilt_dir, provided_dir, pattern="*", key=None, tol=1e-9):
    """compare_frames for every table file of provided_dir that also exists in rebuilt_dir."""
    import glob as _g
    rows = []
    for p in sorted(_g.glob(os.path.join(provided_dir, pattern))):
        f = os.path.basename(p)
        if not f.endswith((".parquet", ".csv", ".csv.gz")) or f.startswith("data_dictionary"):
            continue
        q = os.path.join(rebuilt_dir, f)
        if not os.path.exists(q):
            rows.append(pd.DataFrame([{"table": f, "result": "not rebuilt"}])); continue
        rows.append(compare_frames(read_table(q), read_table(p), key=key, tol=tol, name=f))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


# ---------------------------------------------------------------- simple observed-data charts
def bar(s, xlabel, ylabel, ax=None, color=OBS, rot=0, horizontal=False, fmt=None, figsize=(6, 3)):
    """Bar chart of one observed series (index = categories)."""
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    s = pd.Series(s)
    if horizontal:
        ax.barh([str(i) for i in s.index][::-1], s.values[::-1], color=color)
        ax.set_xlabel(ylabel); ax.set_ylabel(xlabel)
    else:
        ax.bar([str(i) for i in s.index], s.values, color=color)
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        plt.setp(ax.get_xticklabels(), rotation=rot, ha="right" if rot else "center")
    return ax


def shares_table(y, w=None, labels=None, name="records"):
    """Counts and shares (unweighted, and weighted when w is given) of a categorical variable."""
    y = pd.Series(y)
    t = y.value_counts().sort_index().rename(name).to_frame()
    t["share %"] = (100 * t[name] / t[name].sum()).round(2)
    if w is not None:
        ws = pd.Series(np.asarray(w, float), index=y.index).groupby(y).sum().reindex(t.index)
        t["weighted share %"] = (100 * ws / ws.sum()).round(2)
    if labels:
        t.index = [f"{i} {labels.get(i, '')}".strip() for i in t.index]
    return t


def grouped_bars(t, xlabel, ylabel, colors=None, ax=None, rot=0, figsize=(7, 3.2)):
    """Bars of several observed columns side by side (e.g. estimation / hold-out half)."""
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    k = t.shape[1]; x = np.arange(len(t)); w = 0.8 / k
    colors = colors or [OBS, LIGHT, MODEL][:k]
    for i, c in enumerate(t.columns):
        ax.bar(x + (i - (k - 1) / 2) * w, t[c].to_numpy(float), w, color=colors[i % len(colors)], label=str(c))
    ax.set_xticks(x); ax.set_xticklabels([str(i) for i in t.index], rotation=rot, ha="right" if rot else "center")
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.legend(frameon=False, fontsize=8)
    return ax


def hist(x, xlabel, ylabel="records", bins=40, ax=None, weights=None, color=OBS, range=None, figsize=(6, 3)):
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    x = pd.Series(x).astype(float)
    m = x.notna().to_numpy()
    ax.hist(x[m], bins=bins, weights=None if weights is None else np.asarray(weights)[m], color=color, range=range)
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    return ax


def binned(x, edges, labels=None, w=None):
    """Shares (%) of x in the bins [edges_i, edges_i+1)."""
    c = pd.cut(pd.Series(x).astype(float), edges, right=False, labels=labels)
    s = (pd.Series(1.0 if w is None else np.asarray(w, float), index=c.index)).groupby(c, observed=False).sum()
    return 100 * s / s.sum()


def panels(n, ncol=3, w=4.2, h=2.8):
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(w * ncol, h * nrow), squeeze=False)
    for a in axes.flat[n:]:
        a.axis("off")
    return fig, list(axes.flat[:n])


def half_comparison(est, hold, name, w_est=None, w_hold=None):
    """Shares (%) of a categorical variable in the estimation and the hold-out half."""
    a = shares_table(est, w_est)
    b = shares_table(hold, w_hold)
    col = "weighted share %" if w_est is not None else "share %"
    t = pd.DataFrame({"estimation half %": a[col], "hold-out half %": b[col]}).fillna(0).round(2)
    t["difference (points)"] = (t["estimation half %"] - t["hold-out half %"]).round(2)
    t.index.name = name
    return t


# ---------------------------------------------------------------- zone map (shapefile read without geopandas)
def _read_dbf(path):
    import struct
    b = open(path, "rb").read()
    n, hl, rl = struct.unpack("<IHH", b[4:12])
    fields, p = [], 32
    while b[p] != 0x0D:
        fields.append((b[p:p + 11].split(b"\0")[0].decode(), chr(b[p + 11]), b[p + 16])); p += 32
    rows = []
    for i in range(n):
        r = b[hl + i * rl: hl + (i + 1) * rl]; o = 1; row = {}
        for name, typ, ln in fields:
            v = r[o:o + ln].decode("latin1").strip(); o += ln
            if typ in "NF":
                try:
                    v = float(v)
                except ValueError:
                    v = np.nan
            row[name] = v
        rows.append(row)
    return pd.DataFrame(rows)


def _read_shp(path):
    import struct
    b = open(path, "rb").read(); p = 100; out = []
    while p < len(b):
        _, clen = struct.unpack(">II", b[p:p + 8]); p += 8
        st = struct.unpack("<i", b[p:p + 4])[0]
        if st in (5, 15, 25):
            nparts, npts = struct.unpack("<ii", b[p + 36:p + 44])
            parts = list(np.frombuffer(b, "<i4", nparts, p + 44))
            pts = np.frombuffer(b, "<f8", 2 * npts, p + 44 + 4 * nparts).reshape(-1, 2)
            out.append([pts[s:e] for s, e in zip(parts, parts[1:] + [npts])])
        else:
            out.append([])
        p += 2 * clen
    return out


_SHAPES = None
def zone_shapes():
    """Polygons of the 1,588 model zones (MSTM SMZ/RMZ shapefile, UTM 18N metres): list of (zone id, rings)."""
    global _SHAPES
    if _SHAPES is None:
        a = _read_dbf(ZONE_SHP + ".dbf"); g = _read_shp(ZONE_SHP + ".shp")
        _SHAPES = list(zip(a["id"].astype(int).tolist(), g))
    return _SHAPES


def zone_map(values, label, ax=None, log=False, zoom="core", cmap="Greys", figsize=(7.5, 6), vmin=None, vmax=None):
    """Choropleth of a value per zone (Series indexed by zone id; zones without a value in white).
    zoom='core': Baltimore-Washington area; 'md': Maryland and DC; None: all zones."""
    from matplotlib.collections import PolyCollection
    v = pd.Series(values).astype(float)
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    polys, vals = [], []
    for z, rings in zone_shapes():
        x = v.get(z, np.nan)
        for r in rings:
            polys.append(r); vals.append(x)
    vals = np.array(vals, float)
    if log:
        vals = np.where(vals > 0, np.log10(np.where(vals > 0, vals, 1)), np.nan)
        if vmin is None and np.isfinite(vals).any():
            vmin = max(np.nanmin(vals), np.nanmax(vals) - 3)
    from matplotlib.colors import ListedColormap
    cm = ListedColormap(plt.get_cmap(cmap)(np.linspace(0.18, 1.0, 256))) if isinstance(cmap, str) else cmap
    pc = PolyCollection(polys, array=np.ma.masked_invalid(vals), cmap=cm, edgecolors="0.8", linewidths=0.08)
    pc.cmap.set_bad("white")
    if vmin is not None or vmax is not None:
        pc.set_clim(vmin, vmax)
    ax.add_collection(pc); ax.autoscale_view(); ax.set_aspect("equal"); ax.set_axis_off()
    if zoom == "core":
        ax.set_xlim(265_000, 425_000); ax.set_ylim(4_235_000, 4_395_000)
    elif zoom == "md":
        st = zone_table()["county"] // 1000
        xy = np.vstack([np.vstack(r) for z, r in zone_shapes() if r and st.get(z, 0) in (11, 24)])
        ax.set_xlim(xy[:, 0].min(), xy[:, 0].max()); ax.set_ylim(xy[:, 1].min(), xy[:, 1].max())
    cb = plt.colorbar(pc, ax=ax, fraction=0.035, pad=0.01)
    cb.set_label(("log10 " if log else "") + label)
    return ax


# ---------------------------------------------------------------- RTS 2017/18 survey (MAST): raw files and the half split
ABIT_SHARED = os.path.join(_ME, "ABIT", "00_shared_data")
ABIT_PREP = os.path.join(_ME, "ABIT", "00_shared_prep", "code")
RTS_RAW = os.path.join(ABIT_SHARED, "rts_2017_18", "raw")
RACE = re.compile(r"race|ethnic|hispanic", re.I)


def no_race(df):
    """Drop race / ethnicity columns (not used by any model, never shown)."""
    return df[[c for c in df.columns if not RACE.search(str(c))]]


def rts_raw():
    """The three survey files: flat file (one row per trip x household vehicle record), cleaned trips, tours."""
    flat = pd.read_csv(os.path.join(RTS_RAW, "RTS_raw_flat_data.csv.gz"), low_memory=False,
                       usecols=lambda c: not RACE.search(c))
    trips = pd.read_csv(os.path.join(RTS_RAW, "rts_trips_clean.csv.gz"), low_memory=False)
    tours = pd.read_csv(os.path.join(RTS_RAW, "rts_tours.csv.gz"))
    return flat, no_race(trips), tours


def rts_counts(flat, trips, tours, split):
    """Households, persons, trips and tours of the raw survey files and of both halves."""
    h = split.set_index("household_id")["half"]
    rows = [{"file": "RTS_raw_flat_data.csv.gz", "rows": len(flat), "households": flat.household_id.nunique(),
             "persons": flat.person_id.nunique(), "trips": flat.tripid.nunique()},
            {"file": "rts_trips_clean.csv.gz", "rows": len(trips), "households": trips.household_id.nunique(),
             "persons": trips.person_id.nunique(), "trips": trips.tripid.nunique()},
            {"file": "rts_tours.csv.gz", "rows": len(tours), "households": tours.household_id.nunique(),
             "persons": tours.person_id.nunique(), "trips": int(tours.n_trips.sum())}]
    for half in ["estimation", "validation"]:
        ids = set(h[h.eq(half)].index)
        rows.append({"file": f"{half} half (rts_split.csv)", "rows": len(ids), "households": len(ids),
                     "persons": flat[flat.household_id.isin(ids)].person_id.nunique(),
                     "trips": trips[trips.household_id.isin(ids)].tripid.nunique()})
    t = pd.DataFrame(rows).set_index("file")
    return t.apply(lambda c: c.map(lambda v: f"{v:,}"))


def run_quiet(cmd, cwd, env=None):
    """Run a shell command; print its last lines; return the exit code."""
    e = dict(os.environ); e.update(env or {}); e["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, env=e, executable="/bin/bash")
    out = [_scrub(l) for l in (p.stdout + p.stderr).splitlines() if l.strip() and "warn" not in l.lower()]
    print("\n".join(out[-15:]))
    return p.returncode


# ---------------------------------------------------------------- rebuild in a scratch copy (provided files are never touched)
def scratch_tree(folder, raw_files=(), link_files=()):
    """Copy of the model's input/code in a temporary sibling folder _rebuild_<model> (same depth as the model folder, so the
    scripts' relative paths to the shared data resolve). raw_files are copied into its input/data/raw, link_files linked
    there (large files the scripts only read). Returns the path of the copy."""
    import shutil
    folder = os.path.abspath(folder)
    S = os.path.join(os.path.dirname(folder), "_rebuild_" + os.path.basename(folder))
    shutil.rmtree(S, ignore_errors=True)
    shutil.copytree(os.path.join(folder, "input", "code"), os.path.join(S, "input", "code"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    raw = os.path.join(S, "input", "data", "raw"); os.makedirs(raw, exist_ok=True)
    for f in raw_files:
        shutil.copy2(os.path.join(folder, "input", "data", "raw", f), raw)
    for f in link_files:
        os.symlink(os.path.join(folder, "input", "data", "raw", f), os.path.join(raw, f))
    return S


def drop_scratch(S):
    import shutil
    if os.path.basename(S).startswith("_rebuild_"):
        shutil.rmtree(S, ignore_errors=True)


def compare_trees(rebuilt_dir, shipped_dir, key=None, tol=1e-9, skip=("data_dictionary.csv",), only=None):
    """compare_frames for every table (.parquet, .csv, .csv.gz) under shipped_dir that the rebuild wrote under rebuilt_dir
    (same relative path); .json files are compared as dictionaries."""
    rows = []
    for root, _, fs in os.walk(shipped_dir):
        for f in sorted(fs):
            rel = os.path.relpath(os.path.join(root, f), shipped_dir)
            if f in skip or "_pre" in f or (only and not re.search(only, rel)):
                continue
            q = os.path.join(rebuilt_dir, rel)
            if f.endswith(".json"):
                if os.path.exists(q):
                    import json as _j
                    same = _j.load(open(q)) == _j.load(open(os.path.join(root, f)))
                    rows.append(pd.DataFrame([{"table": rel, "result": "identical" if same else "DIFFERENT"}]))
                continue
            if not f.endswith((".parquet", ".csv", ".csv.gz")):
                continue
            if not os.path.exists(q):
                rows.append(pd.DataFrame([{"table": rel, "result": "not rebuilt"}])); continue
            rows.append(compare_frames(read_table(q), read_table(os.path.join(root, f)), key=key, tol=tol, name=rel))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def funnel2(steps, reasons=None):
    """Records kept by each step in both halves. steps: {half: [(label, n), ...]} (same labels in each half)."""
    reasons = reasons or {}
    halves = list(steps)
    labels = [l for l, _ in steps[halves[0]]]
    t = pd.DataFrame(index=pd.Index(labels, name="step"))
    for h in halves:
        n = pd.Series(dict(steps[h])).reindex(labels)
        t[f"{h}: records"] = n.map(lambda v: f"{int(v):,}")
        t[f"{h}: dropped"] = (-n.diff()).map(lambda v: "" if not np.isfinite(v) or v == 0 else f"{int(v):,}")
    t["reason"] = [reasons.get(l, "") for l in labels]
    return t


def rebuild_verdict(res, model_file=None):
    """One-line reading of a rebuild comparison."""
    bad = res[res["result"] != "identical"]
    if bad.empty:
        print(f"All {len(res)} rebuilt files are identical to the shipped ones.")
        return
    cols = set()
    for v in bad.get("differing columns", pd.Series(dtype=str)).fillna(""):
        cols |= {c.strip() for c in str(v).split(",") if c.strip()}
    nr = bad["result"].eq("not rebuilt").sum()
    src = open(model_file).read() if model_file and os.path.exists(model_file) else ""
    used = sorted(c for c in cols if re.search(r"[\"']" + re.escape(c) + r"[\"']|Variable\(f?[\"']" + re.escape(c), src))
    print(f"{len(res) - len(bad)} of {len(res)} files identical; differing columns: {', '.join(sorted(cols)) or '-'}"
          + (f"; {nr} not rebuilt" if nr else ""))
    if cols:
        print("used by the model script:", ", ".join(used) if used else "none of them")


# ================================================================ reader figures of the SILO notebooks (paper style: model orange, observed dark grey)
def paper_rc():
    plt.rcParams.update({"font.size": 8.5, "axes.labelsize": 8.5, "axes.titlesize": 9, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
                         "legend.fontsize": 8, "axes.titlelocation": "left", "axes.titleweight": "bold", "axes.spines.top": False,
                         "axes.spines.right": False})


def funnel_plot(f, unit="records", title="(a) Records kept at each step"):
    """Horizontal bars of the records kept at each step of a Funnel (dropped records in light grey)."""
    paper_rc(); t = pd.DataFrame(f.rows)
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(t) + 1.0))
    y = np.arange(len(t))[::-1]
    ax.barh(y, t.records, color=OBS, height=0.6)
    ax.barh(y, t.dropped, left=t.records, color="#d9d8d2", height=0.6)
    for yy, n, d in zip(y, t.records, t.dropped):
        ax.text(n, yy, f" {n:,}" + (f"  (−{d:,})" if d else ""), va="center", fontsize=7.5)
    ax.set_yticks(y); ax.set_yticklabels(t.step); ax.set_xlabel(f"{unit.capitalize()} (dark: kept; light: dropped at this step)")
    ax.set_xlim(0, t.records.max() * 1.35); ax.set_title(title); plt.tight_layout(); plt.show()


def coef_plot(est, labels, groups, title="(a) Estimates with 95 % robust intervals"):
    """est: parameter, coefficient, robust_se.  One row per parameter, grouped by block, zero line."""
    paper_rc(); d = est.assign(label=labels, group=groups).reset_index(drop=True)
    order = list(dict.fromkeys(d.group)); d["g"] = d.group.map({g: i for i, g in enumerate(order)}); d = d.sort_values(["g"], kind="stable")
    fig, ax = plt.subplots(figsize=(7.5, 0.24 * len(d) + 0.3 * len(order) + 1.0))
    y, ticks, yy = 0, [], []
    for g, s in d.groupby("g", sort=True):
        ax.text(-0.01, y + 0.4, order[g], transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=8, fontweight="bold")
        y += 1
        for r in s.itertuples():
            ax.errorbar(r.coefficient, y, xerr=1.96 * r.robust_se, fmt="o", ms=3.5, color=MODEL, ecolor=MODEL, elinewidth=1.2, capsize=0)
            ticks.append(y); yy.append(r.label); y += 1
    ax.axvline(0, color="0.4", lw=0.8); ax.set_yticks(ticks); ax.set_yticklabels(yy); ax.invert_yaxis()
    ax.set_xlabel("Coefficient (95 % robust interval)"); ax.set_title(title); plt.tight_layout(); plt.show()


def chosen_vs_available(pairs, title="Chosen against available alternatives"):
    """pairs: list of (label, chosen values, available values[, available weights]); paired histograms, density scale."""
    paper_rc(); n = len(pairs); fig, axs = plt.subplots(1, n, figsize=(3.2 * n, 2.8)); axs = np.atleast_1d(axs)
    for i, (ax, p) in enumerate(zip(axs, pairs)):
        lab, c, a = p[:3]; w = p[3] if len(p) > 3 else None
        c, a = np.asarray(c, float), np.asarray(a, float); ok = np.isfinite(a)
        lo, hi = np.nanpercentile(np.r_[c, a[ok]], [1, 99]); bins = np.linspace(lo, hi, 30)
        ax.hist(a[ok], bins=bins, weights=None if w is None else np.asarray(w)[ok], density=True, color="#c9c8c2", label="Available")
        ax.hist(c, bins=bins, density=True, histtype="step", lw=1.6, color=OBS, label="Chosen")
        ax.set_xlabel(lab); ax.set_ylabel("Density" if i == 0 else ""); ax.set_title(f"({chr(97 + i)})")
    axs[0].legend(loc="upper right", frameon=False); fig.suptitle(title, fontsize=9, x=0.01, ha="left"); plt.tight_layout(); plt.show()


def holdout_scatter(t, obs="observed_pct", mod="model_pct", names=None, unit="Movers", title="(a) Counties, hold-out", label_top=5, ax=None):
    """Observed against model share by county (one point per county), equality line, the largest differences labelled."""
    paper_rc(); show = ax is None
    if ax is None: fig, ax = plt.subplots(figsize=(4.2, 4.0))
    hi = max(t[obs].max(), t[mod].max()) * 1.08
    ax.plot([0, hi], [0, hi], color="0.5", lw=0.8); ax.scatter(t[obs], t[mod], s=14, color=MODEL, zorder=3)
    for r in t.reindex((t[mod] - t[obs]).abs().sort_values(ascending=False).index).head(label_top).itertuples():
        c = getattr(r, "county", None); ax.annotate((names or {}).get(c, str(c)), (getattr(r, obs), getattr(r, mod)), fontsize=7.5, xytext=(3, 3), textcoords="offset points")
    ax.set_xlim(0, hi); ax.set_ylim(0, hi); ax.set_xlabel(f"Observed, {unit.lower()} (%)"); ax.set_ylabel(f"Model, {unit.lower()} (%)"); ax.set_title(title)
    if show: plt.tight_layout(); plt.show()


def grouped_model_obs(t, xlabel, ylabel, title, ax=None):
    """t: index = category, columns observed, model (shares %); bars observed dark grey, model orange."""
    paper_rc(); show = ax is None
    if ax is None: fig, ax = plt.subplots(figsize=(5.5, 3.0))
    x = np.arange(len(t)); w = 0.38
    ax.bar(x - w / 2, t.observed, w, color=OBS, label="Observed"); ax.bar(x + w / 2, t.model, w, color=MODEL, label="Model")
    ax.set_xticks(x); ax.set_xticklabels(t.index); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(title); ax.legend(frameon=False)
    if show: plt.tight_layout(); plt.show()


def predicted_probabilities(database, ll, betas):
    """Choice probabilities of every alternative for every row, from the logit inside a Biogeme log-likelihood (possibly weighted)."""
    import biogeme.biogeme as bio
    from biogeme.models import logit
    from biogeme.expressions.logit_expressions import LogLogit
    def find(e):
        if isinstance(e, LogLogit): return e
        for c in e.get_children():
            r = find(c)
            if r is not None: return r
    L = find(ll); util, av = dict(L.util), dict(L.av)
    here = os.getcwd(); import tempfile; os.chdir(tempfile.mkdtemp())
    try:
        from biogeme.parameters import Parameters
        pr = Parameters(); pr.set_value("generate_html", False); pr.set_value("generate_yaml", False)
        b = bio.BIOGEME(database, {f"P_{k}": logit(util, av, k) for k in util}, parameters=pr); b.model_name = "probabilities"
        P = b.simulate(betas)
    finally:
        os.chdir(here)
    return P.rename(columns=lambda c: c[2:])


def show_png(path, width=900):
    from IPython.display import Image, display
    display(Image(filename=path, width=width))


def market_plot(market_csv):
    """Residential PUMA level: market size against the PUMA's 2016 dwellings, and the turnover rate."""
    paper_rc(); m = pd.read_csv(market_csv)
    fig, ax = plt.subplots(1, 2, figsize=(8.5, 3.3))
    ax[0].scatter(m.silo_dwellings_2016 / 1000, m.M_2016 / 1000, s=12, color=MODEL)
    ax[0].set_xlabel("Dwellings of the PUMA, 2016 (thousands)"); ax[0].set_ylabel("Market size M (thousand dwellings)"); ax[0].set_title("(a) Market size and stock")
    ax[1].hist(100 * m.turnover_r, bins=25, color=OBS); ax[1].set_xlabel("Turnover rate r (% of dwellings per year)"); ax[1].set_ylabel("PUMAs"); ax[1].set_title("(b) Turnover rate")
    plt.tight_layout(); plt.show()


def sample_size_dots(coef_csv, labels=None):
    """Sampled-alternatives check: change of each coefficient against the 30-alternative estimate, in its robust s.e."""
    paper_rc(); c = pd.read_csv(coef_csv); c = c[c.case != "J30"]
    cases = list(dict.fromkeys(c.case)); col = {cases[0]: OBS, cases[1]: MODEL, cases[2]: "#2a78d6"} if len(cases) == 3 else {}
    params = list(dict.fromkeys(zip(c.level, c.param))); y = {p: i for i, p in enumerate(params)}
    fig, ax = plt.subplots(figsize=(6.5, 0.2 * len(params) + 1.2))
    mk = dict(zip(cases, ["o", "^", "s"]))
    for k, g in c.groupby("case", sort=False):
        ax.scatter(g.diff_in_se, [y[(a, b)] for a, b in zip(g.level, g.param)], s=14, marker=mk.get(k, "o"), color=col.get(k, MODEL), label=k.replace("J", "").replace(",", " alternatives,") if "draw" in k else k.replace("J", "") + " alternatives")
    ax.axvline(0, color="0.4", lw=0.8); ax.axvspan(-1, 1, color="#eeede8", zorder=0)
    ax.set_yticks(range(len(params))); ax.set_yticklabels([(labels or {}).get(b, b) + f" ({a})" for a, b in params], fontsize=7.5); ax.invert_yaxis()
    ax.set_xlabel("Change against 30 alternatives (robust s.e.)"); ax.set_title("(a) Sampled-alternatives check"); ax.legend(frameon=False, loc="lower right")
    plt.tight_layout(); plt.show()
