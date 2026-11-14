"""Shared helpers of the collinearity check (c_silo_*.py): within-choice correlations, VIF, estimate correlations, heatmaps in the
style of car_ownership/s02_correlation.py, flags and pair classification, refit summaries.  Estimation half only."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, re, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import chi2

OUT = f"{ESTIMATION_RESULTS}/collinearity"   # results of the collinearity check (data)
SBS = ESTIMATION_RESULTS
R_VAR, VIF_MAX, R_EST = 0.7, 10.0, 0.8


def wcorr(X, w):
    """weighted correlation of the columns of X (rows x K); as s02_correlation.wcorr"""
    w = w / w.sum(); m = (X * w[:, None]).sum(0); Z = X - m
    C = (Z * w[:, None]).T @ Z; s = np.sqrt(np.diag(C)); return C / np.outer(s, s)


def within(X, av):
    """demean (N, J, K) attributes within each choice situation over its available alternatives (unweighted mean over alternatives)"""
    a = av.astype(float); cnt = np.maximum(a.sum(1), 1.0)
    m = np.einsum("nj,njk->nk", a, X) / cnt[:, None]
    return (X - m[:, None, :]) * a[:, :, None]


def within_corr(X, av, w):
    """correlation over all available (situation, alternative) cells of the within-situation deviations; a situation counts with its
    observation weight w_n, spread evenly over its available alternatives"""
    Z = within(np.asarray(X, float), av); a = av.astype(float); cw = (w / np.maximum(a.sum(1), 1.0))[:, None] * a
    C = np.einsum("nj,njk,njl->kl", cw, Z, Z); s = np.sqrt(np.diag(C)); return C / np.outer(s, s)


def vif(R):
    return np.diag(np.linalg.inv(R))


def est_corr(cov):
    s = np.sqrt(np.diag(cov)); return cov / np.outer(s, s)


def heatmap(R, labels, path, title, cblab):
    """lower-triangle heatmap, diverging blue-grey-red, -1..1, values printed (car_ownership/s02_correlation.py style)"""
    n = len(labels); cmap = LinearSegmentedColormap.from_list("div", ["#2166ac", "#d9d9d9", "#b2182b"])
    sz = max(7.0, 0.42 * n + 3.0); fs = 7 if n <= 20 else 6 if n <= 30 else 5 if n <= 42 else 4
    lf = 8 if n <= 20 else 7 if n <= 30 else 6 if n <= 42 else 5
    fig, ax = plt.subplots(figsize=(sz * 1.12, sz))
    mask = np.triu(np.ones_like(R, bool), 1)
    im = ax.imshow(np.ma.masked_where(mask, R), cmap=cmap, vmin=-1, vmax=1)
    for i in range(n):
        for j in range(i + 1):
            ax.text(j, i, f"{R[i, j]:.2f}".replace("-0.", "−0.").replace("0.", ".").replace("-1.00", "−1").replace("1.00", "1") if i != j else "",
                    ha="center", va="center", fontsize=fs, color="white" if abs(R[i, j]) > 0.6 else "#222222")
    ax.set_xticks(range(n)); ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=lf)
    ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=lf)
    for s in ax.spines.values(): s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.6); cb.set_label(cblab, fontsize=8); cb.ax.tick_params(labelsize=7)
    ax.set_title(title, fontsize=10); fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


def pairs(R, names, thr):
    return [(names[i], names[j], float(R[i, j])) for i in range(len(names)) for j in range(i) if abs(R[i, j]) >= thr]


def lr(ll_full, k_full, ll_r, k_r):
    s = 2 * (ll_full - ll_r); df = k_full - k_r
    return s, df, (float(chi2.sf(s, df)) if df > 0 else np.nan)


def save_part(model, rows, notes):
    """per-model rows of silo_summary.csv and the facts for silo_notes.md (collected by c_silo_summary.py)"""
    pd.DataFrame(rows).to_csv(f"{OUT}/{model}_pairs.csv", index=False)
    json.dump(notes, open(f"{OUT}/{model}_facts.json", "w"), indent=1, default=float)


def refit_row(base, alt, member, label):
    """base, alt: dict(LL, K, N, names, b, se); member: parameter whose estimate and s.e. are followed"""
    s, df, p = lr(base["LL"], base["K"], alt["LL"], alt["K"])
    bi = dict(zip(base["names"], zip(base["b"], base["se"]))); ai = dict(zip(alt["names"], zip(alt["b"], alt["se"])))
    flips = [n for n in ai if n in bi and np.sign(ai[n][0]) != np.sign(bi[n][0])]
    r = dict(refit=label, LL=alt["LL"], K=alt["K"], BIC=-2 * alt["LL"] + alt["K"] * np.log(alt["N"]), dBIC=(-2 * alt["LL"] + alt["K"] * np.log(alt["N"])) - (-2 * base["LL"] + base["K"] * np.log(base["N"])),
             LR=s if df > 0 else np.nan, df=df, p=p, sign_changes=";".join(flips))
    if member in ai and member in bi:
        r.update(member=member, b_final=bi[member][0], se_final=bi[member][1], b_refit=ai[member][0], se_refit=ai[member][1],
                 se_ratio=ai[member][1] / bi[member][1])
    return r


def tex_labels(path):
    """row labels of a .tex estimation table, in order, LaTeX turned into plain text"""
    out = []
    for line in open(path):
        if "&" not in line or "Variable &" in line or "Parameter &" in line or "{reference}" in line: continue   # reference rows carry no estimate
        lab = line.split("&")[0].strip()
        out.append(plain(lab))
    return out


def plain(s):
    s = s.replace("\\$", "\x00").replace("\\quad", "").replace("$\\times$", "×").replace("\\times", "×").replace("$-$", "−").replace("--", "–")
    s = s.replace("\\,", " ").replace("\\%", "%").replace("\\$", "$").replace("$^2$", "²").replace("\\text{time}", "time")
    s = s.replace("$\\lambda_B$", "λB").replace("$\\lambda_A$", "λA").replace("$\\mu$", "μ").replace("$<$", "<").replace("$<", "<")
    s = re.sub(r"\$([^$]*)\$", r"\1", s); s = s.replace("\\ln", "ln").replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", s.replace("$", "").replace("\x00", "$")).strip()


def classify(a, b, inter, sets):
    """inter: {interaction: (main, z, set_name or None)}; sets: [(names, kind)].  Returns (type, why, centring applicable)"""
    if a in inter and inter[a][0] == b or b in inter and inter[b][0] == a: return "STRUCTURAL", "main effect vs its own interaction", True
    for S, kind in sets:
        if a in S and b in S: return "STRUCTURAL", kind, kind.startswith("interactions")
    for x, y in ((a, b), (b, a)):   # interaction of a variable vs another functional term of the same variable (e.g. t x licence vs ln(1+t))
        if x in inter and any(inter[x][0] in S and y in S for S, kind in sets if kind.startswith("functional form")):
            return "STRUCTURAL", "interaction of a variable vs another functional term of the same variable", True
    if a in inter and b in inter and inter[a][0] == inter[b][0]:
        if inter[a][2] and inter[a][2] == inter[b][2]: return "STRUCTURAL", "members of one band set (interactions of one attribute)", True
        return "STRUCTURAL", "two interactions of the same attribute", True
    return "SUBSTANTIVE", "", False


def run_alt_model(model, title, X, names, av, w, labels, inter, sets, base, refit, protect=(), extra_vars=None, est_names=None):
    """(a)-(e) for a model whose attributes vary over alternatives.
    X (N, J, K) attributes of the free coefficients named `names` (extra_vars: further (N, J, k) columns shown in (a) only, e.g. a size term);
    av (N, J); w (N,) situation weights; labels {name: label}; inter {interaction: (main, z (N,), band set)}; sets [(names, kind)];
    base: dict(LL, K, N, names, b, se, cov) of the final model (names may include non-variable parameters, e.g. size weights);
    refit(drop=[...], replace={name: (N, J) column}) -> dict like base.  protect: parameters never dropped."""
    vnames = list(names); Xa = X
    if extra_vars:
        Xa = np.concatenate([X] + [v for _, v in extra_vars], axis=2); vnames = vnames + [n for n, _ in extra_vars]
    R = within_corr(Xa, av, w); k0 = len(names); vf = np.r_[vif(R[:k0, :k0]), np.full(len(vnames) - k0, np.nan)]   # VIF over the free coefficients
    heatmap(R, [labels[v] for v in vnames], f"{OUT}/{model}_var_corr.png",
            f"{title}: correlations of the explanatory variables\nwithin choice situation (demeaned over its alternatives), estimation half", "Correlation (within choice situation)")
    en = est_names or base["names"]; Re = est_corr(base["cov"])
    heatmap(Re, [labels[n] for n in en], f"{OUT}/{model}_est_corr.png",
            f"{title}: correlations of the estimates (robust covariance)\nestimation half, LL {base['LL']:,.1f}, {base['K']} parameters", "Correlation of the estimates")
    pd.DataFrame(R, index=vnames, columns=vnames).round(3).to_csv(f"{OUT}/{model}_var_corr.csv")
    pd.DataFrame(Re, index=base["names"], columns=base["names"]).round(3).to_csv(f"{OUT}/{model}_est_corr.csv")
    zbar = {k: float(np.sum(w * v[1]) / np.sum(w)) for k, v in inter.items()}
    vi = {n: i for i, n in enumerate(vnames)}; bi = {n: i for i, n in enumerate(base["names"])}

    def centred_col(k):
        m, z, _ = inter[k]; return Xa[:, :, vi[m]] * (z - zbar[k])[:, None]

    def var_r_centred(a, b):
        cols = []
        for v in (a, b):
            cols.append(centred_col(v) if v in inter else Xa[:, :, vi[v]])
        return float(within_corr(np.stack(cols, axis=2), av, w)[0, 1])

    def est_r_centred(a, b):
        T = np.eye(len(base["names"]))
        for k in (a, b):
            if k in inter and inter[k][0] in bi: T[bi[inter[k][0]], bi[k]] += zbar[k]
        return float(est_corr(T @ base["cov"] @ T.T)[bi[a], bi[b]])

    rows = []
    for a, b, r in pairs(R, vnames, R_VAR):
        t, why, cen = classify(a, b, inter, sets)
        rows.append(dict(model=model, pair=f"{labels[a]} / {labels[b]}", p1=a, p2=b, source="variables", type=t, why=why, var_r=r,
                         var_r_centred=var_r_centred(a, b) if cen else np.nan,
                         est_r=Re[bi[a], bi[b]] if a in bi and b in bi else np.nan,
                         est_r_centred=est_r_centred(a, b) if cen and a in bi and b in bi else np.nan))
    for v, x in zip(vnames, vf):
        if x >= VIF_MAX: rows.append(dict(model=model, pair=labels[v], p1=v, source="VIF", VIF=x))
    for a, b, r in pairs(Re, base["names"], R_EST):
        t, why, cen = classify(a, b, inter, sets)
        if a in protect or b in protect: t, why, cen = ("STRUCTURAL", "size-term parameters", False) if a in protect and b in protect else (t, why, cen)
        rows.append(dict(model=model, pair=f"{labels[a]} / {labels[b]}", p1=a, p2=b, source="estimates", type=t, why=why, est_r=r,
                         var_r=R[vi[a], vi[b]] if a in vi and b in vi else np.nan,
                         var_r_centred=var_r_centred(a, b) if cen and a in vi and b in vi else np.nan, est_r_centred=est_r_centred(a, b) if cen else np.nan))
    P = pd.DataFrame(rows)
    for c in ["var_r_centred", "est_r_centred", "why"]:
        if c not in P: P[c] = np.nan
    P["centring_removes"] = np.where(P.var_r_centred.notna() | P.est_r_centred.notna(),
                                     ~((P.var_r_centred.abs().fillna(0) >= R_VAR) & (P.source == "variables") | (P.est_r_centred.abs().fillna(0) >= R_EST) & (P.source == "estimates")), np.nan)
    P["VIF_p1"] = [vf[vi[x]] if x in vi else np.nan for x in P.p1]; P["VIF_p2"] = [vf[vi[x]] if isinstance(x, str) and x in vi else np.nan for x in P.p2]
    need = P[(P.source != "VIF") & ((P.type == "SUBSTANTIVE") | (P.centring_removes == False) | P.why.astype(str).str.startswith("functional form"))]   # noqa: E712
    # functional-form pairs (t, ln(1+t)): centring cannot change their correlation, so they are refitted as well
    ref, done, cache = [], set(), {}
    for _, q in need.iterrows():
        a, b = q.p1, q.p2
        if frozenset((a, b)) in done: continue
        done.add(frozenset((a, b)))
        runs = [(f"without {a}", [a], {}, b), (f"without {b}", [b], {}, a)]
        rep = {k: centred_col(k) for k in (a, b) if k in inter}
        if rep: runs.append(("interaction centred: " + ", ".join(rep), [], rep, a if a not in rep else b))
        for lab, drop, repl, follow in runs:
            if set(drop) & set(protect): continue
            print(model, q.pair, lab, flush=True)
            key = (tuple(sorted(drop)), tuple(sorted(repl)))
            if key not in cache: cache[key] = refit(drop=drop, replace=repl)
            m = cache[key]
            rr = refit_row(base, m, follow, lab); rr.update(model=model, pair=q.pair)
            if repl:
                ia, ib = m["names"].index(a), m["names"].index(b); rr["est_r_after"] = float(est_corr(m["cov"])[ia, ib])
            ref.append(rr); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rr.items()}, flush=True)
    save_part(model, P.to_dict("records") + ref, dict(LL=base["LL"], K=base["K"], N=base["N"], max_vif=float(np.nanmax(vf)), vif=dict(zip(vnames, np.round(vf, 2)))))
    print(P.drop(columns=["pair"]).to_string()); return P, ref


def zratio(X, i, j, av):
    """person variable of the interaction column i of main column j (X_i = X_j z): median ratio over the alternatives with X_j != 0"""
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(av & (np.abs(X[:, :, j]) > 1e-9), X[:, :, i] / X[:, :, j], np.nan)
    z = np.nanmedian(r, axis=1); return np.nan_to_num(z)
