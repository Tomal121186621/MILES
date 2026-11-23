"""Section 4.1 of the notebooks: every explanatory variable of the final specification, as it enters the utility.

Location and destination models: the variable at the chosen alternative against the available (or sampled) alternatives.
Car ownership, mode and other small choice sets: the variable by chosen alternative.

The variable of a coefficient b is read from the model's own utility expressions: the utilities are linear in the
coefficients, so the variable of b is the part of V that b multiplies (lin() below). Scale, nest and size-weight parameters
are held at their reference values; constants are left out. Figures in the paper style (5_reports/paperstyle.py colours:
chosen / observed dark grey, available or sampled light neutral), panels labelled (a), (b), ...; each figure is followed by
a few lines read from the numbers of the figure."""
import re, textwrap
import numpy as np, pandas as pd
import matplotlib.pyplot as plt

OBS, AVAIL, MODEL, INK2 = "#3b4252", "#c3c2b7", "#e8811a", "#52514e"
FS, TICK = 8.0, 7.5


def _rc():
    plt.rcParams.update({"font.size": FS, "axes.titlesize": FS, "axes.labelsize": FS, "xtick.labelsize": TICK, "ytick.labelsize": TICK,
                         "legend.fontsize": FS, "axes.spines.top": False, "axes.spines.right": False, "axes.titlelocation": "left",
                         "axes.titleweight": "bold", "figure.dpi": 110})


def _show_lines(lines):
    from IPython.display import Markdown, display
    if lines:
        display(Markdown("  \n".join(lines)))


def clean_label(s):
    s = re.sub(r"(?i)\bln 1 plus (\w+)", r"log(1 + \1)", str(s))
    s = re.sub(r"(?i)\bln\b", "log", s).replace(" x ", " × ").replace("()", "($)").replace("washington", "Washington")
    return s[:1].upper() + s[1:]


def fmt(v):
    a = abs(v)
    s = f"{v:,.0f}" if a >= 100 else f"{v:.1f}" if a >= 10 else f"{v:.2f}" if a >= 0.1 or a == 0 else f"{v:.3f}"
    return s.replace("-", "−")


# ------------------------------------------------------------------------------------------------ utilities -> variables
class NonLinear(Exception):
    pass


_FUN = {"log": np.log, "exp": np.exp, "BinaryMin": np.minimum, "BinaryMax": np.maximum,
        "Equal": lambda a, b: (np.asarray(a) == np.asarray(b)) * 1.0, "NotEqual": lambda a, b: (np.asarray(a) != np.asarray(b)) * 1.0,
        "Less": lambda a, b: (np.asarray(a) < np.asarray(b)) * 1.0, "LessOrEqual": lambda a, b: (np.asarray(a) <= np.asarray(b)) * 1.0,
        "Greater": lambda a, b: (np.asarray(a) > np.asarray(b)) * 1.0, "GreaterOrEqual": lambda a, b: (np.asarray(a) >= np.asarray(b)) * 1.0,
        "And": lambda a, b: ((np.asarray(a) != 0) & (np.asarray(b) != 0)) * 1.0, "Or": lambda a, b: ((np.asarray(a) != 0) | (np.asarray(b) != 0)) * 1.0,
        "Power": np.power, "logzero": lambda a: np.where(np.asarray(a) == 0, 0.0, np.log(np.where(np.asarray(a) == 0, 1.0, a))),
        "sqrt": np.sqrt}


def _add(a, b, s=1.0):
    out = dict(a)
    for k, v in b.items():
        out[k] = out[k] + s * v if k in out else s * v
    return out


def _const(a):
    if set(a) - {None}:
        raise NonLinear("a coefficient inside a non-linear function")
    return a.get(None, 0.0)


def lin(e, data, fixed=None, cache=None):
    """Biogeme expression -> {coefficient name: array or scalar, None: constant part}, for an expression linear in the free
    coefficients. fixed: coefficients held at a value (scale, nest, size weights); coefficients with status 1 use their value."""
    fixed = fixed or {}; cache = {} if cache is None else cache
    if isinstance(e, (int, float, np.floating, np.integer)):
        return {None: float(e)}
    n = type(e).__name__
    if n == "Numeric":
        return {None: float(e.value)}
    if n == "Beta":
        if e.name in fixed:
            return {None: float(fixed[e.name])}
        if getattr(e, "status", 0) != 0:
            return {None: float(e.init_value)}
        return {e.name: 1.0}
    if n == "Variable":
        if e.name not in cache:
            cache[e.name] = np.asarray(data[e.name], float)
        return {None: cache[e.name]}
    ch = list(e.get_children())
    with np.errstate(all="ignore"):
        if n in ("Plus", "MultipleSum"):
            out = {}
            for c in ch:
                out = _add(out, lin(c, data, fixed, cache))
            return out
        if n == "Minus":
            return _add(lin(ch[0], data, fixed, cache), lin(ch[1], data, fixed, cache), -1.0)
        if n == "UnaryMinus":
            return {k: -v for k, v in lin(ch[0], data, fixed, cache).items()}
        if n == "Times":
            a, b = lin(ch[0], data, fixed, cache), lin(ch[1], data, fixed, cache)
            if set(a) <= {None}:
                c = a.get(None, 0.0); return {k: v * c for k, v in b.items()}
            if set(b) <= {None}:
                c = b.get(None, 0.0); return {k: v * c for k, v in a.items()}
            raise NonLinear("product of two coefficients")
        if n == "Divide":
            a, b = lin(ch[0], data, fixed, cache), _const(lin(ch[1], data, fixed, cache))
            return {k: v / b for k, v in a.items()}
        if n == "PowerConstant":
            return {None: np.power(_const(lin(ch[0], data, fixed, cache)), e.exponent)}
        if n in _FUN:
            return {None: _FUN[n](*[_const(lin(c, data, fixed, cache)) for c in ch])}
    raise NonLinear(f"expression type {n} not handled")


def find_choice(expr):
    """the logit / nested-logit node of a log-likelihood: (utilities, availabilities, choice)"""
    def f(x):
        if hasattr(x, "util") and hasattr(x, "choice"):
            return x
        for c in x.get_children():
            r = f(c)
            if r is not None:
                return r
    L = f(expr)
    if L is None:
        raise ValueError("no logit in the expression")
    return dict(L.util), dict(L.av), L.choice


def util_terms(util, data, fixed=None):
    """{alternative: {coefficient: array (records)}} of the coefficients in each utility"""
    n = len(data); cache = {}; out = {}
    for j, e in util.items():
        L = lin(e, data, fixed, cache)
        out[j] = {k: np.broadcast_to(np.asarray(v, float), (n,)).copy() for k, v in L.items() if k is not None}
    return out


def _arr(e, data, n, cache):
    return np.broadcast_to(np.asarray(_const(lin(e, data, None, cache)), float), (n,)).copy()


def label_groups(params, labels):
    """params in label order -> {label: [params]} and {label: group}; constants (label 'Constant') left out"""
    G, grp = {}, {}
    for p in params:
        if p not in labels:
            continue
        lab, g = labels[p]
        if lab.lower().startswith("constant"):
            continue
        G.setdefault(lab, []).append(p); grp.setdefault(lab, g)
    return G, grp


def silo_labels(folder):
    import nb_reader as RD
    est, _ = RD.reference(folder); out = {}
    for p in est.parameter:
        t, _s = RD.term(folder, p)
        if t is not None:
            out[p] = (clean_label(t["label"]), t.get("group") or "")
    if "MU_size" in out:                         # the variable of the size coefficient: log of the size of the alternative
        out["MU_size"] = ("Log size of the zone (" + ("jobs" if folder.startswith("05") else "enrolment, size weights at their estimates") + ")", out["MU_size"][1])
    return out


def abit_labels(folder):
    import abit_figs as AF
    r = AF.reference(folder); rows = AF.coef_rows(folder)
    return {p: (clean_label(l), g) for p, l, g in zip(r.parameter, rows.label, rows.group)}


# ------------------------------------------------------------------------------------------------ panel data
def _panel(label, group, c, cw, crid, a, aw, arid, n_rec):
    """continuous terms: only the records the term applies to (a non-zero value at the chosen or at an available alternative,
    e.g. the persons of an interaction); 0/1 terms: all records (a zone dummy is zero for most alternatives)"""
    c, a = np.asarray(c, float), np.asarray(a, float)
    vals = np.unique(np.r_[c[np.isfinite(c)][:20000], a[np.isfinite(a)][:200000]])
    binary = set(np.round(vals, 9)).issubset({0.0, 1.0})
    nz = np.union1d(crid[(c != 0) & np.isfinite(c)], arid[(a != 0) & np.isfinite(a)])
    if len(nz) == 0:
        return None
    share, n = 1.0, n_rec
    if not binary and len(nz) < n_rec:
        mc, ma = np.isin(crid, nz), np.isin(arid, nz)
        c, cw, a, aw = c[mc], cw[mc], a[ma], aw[ma]; share, n = len(nz) / n_rec, len(nz)
    okc, oka = np.isfinite(c) & (cw > 0), np.isfinite(a) & (aw > 0)
    return dict(label=label, group=group, c=c[okc], cw=cw[okc], a=a[oka], aw=aw[oka], share=share, n=n, binary=binary)


def location_from_util(util, av, choice, data, labels, fixed=None, sampled=False):
    """SILO wide tables (residential PUMA, dwelling, workplace): chosen against the available (sampled=False) or against the
    sampled, non-chosen alternatives (sampled=True); every record counts once."""
    n = len(data); cache = {}
    T = util_terms(util, data, fixed); J = list(util)
    A = np.column_stack([_arr(av[j], data, n, cache) for j in J]) > 0
    ch = _arr(choice, data, n, cache).astype(int); jpos = {j: i for i, j in enumerate(J)}; ci = np.array([jpos[x] for x in ch])
    r = np.arange(n)
    Aa = A.copy()
    if sampled:
        Aa[r, ci] = False
    w_av = 1.0 / np.maximum(Aa.sum(1), 1)
    rr, jj = np.nonzero(Aa)
    G, grp = label_groups([p for p in labels if any(p in T[j] for j in J)], labels)
    out = []
    for lab, ps in G.items():
        X = np.zeros((n, len(J)), np.float32)
        for i, j in enumerate(J):
            for p in ps:
                if p in T[j]:
                    X[:, i] += T[j][p]
        if np.allclose(X[A], 1.0):
            continue                                   # a constant
        P_ = _panel(lab, grp[lab], X[r, ci], np.ones(n), r, X[rr, jj], w_av[rr], rr, n)
        if P_ is not None:
            out.append(P_)
    return out


def location_from_at(M, files, labels, fixed=None, n_rows=600, n_zones=150, seed=1):
    """DAYMAP destination models (full choice set of 1,588 zones, location mixtures): chosen = the candidate zones of the
    observed location (weights w_c x b_k), available = n_zones zones drawn at random per record (weight w_c / n_zones).
    Purpose-specific copies of a term (same label) apply to different records: their values are added."""
    import pyarrow.parquet as pq
    rng = np.random.default_rng(seed)
    sizes = [pq.read_metadata(f).num_rows for f in files]; tot = sum(sizes)
    take = [max(1, int(round(n_rows * s / tot))) for s in sizes]
    G, grp = label_groups(list(labels), labels)
    NZ = int(M.NZ); store = {lab: dict(c=[], cw=[], cr=[], a=[], aw=[], ar=[]) for lab in G}; base = 0
    def by_label(T, n):
        return {lab: sum((np.broadcast_to(np.asarray(T[p], float), (n,)) for p in ps if p in T), np.zeros(n)) for lab, ps in G.items()}
    for f, m in zip(files, take):
        df = pd.read_parquet(f)
        df = df.iloc[np.sort(rng.choice(len(df), min(m, len(df)), replace=False))].reset_index(drop=True).astype("float64")
        if hasattr(M, "add_lnarea"):
            df = M.add_lnarea(df)
        n = len(df); rid = base + np.arange(n); base += n; cache = {}
        ncfg = sum(bool(re.fullmatch(r"w_\d+", c)) for c in df.columns); ncand = sum(bool(re.fullmatch(r"b_\d+", c)) for c in df.columns)
        zsel = np.argsort(rng.random((n, NZ)), axis=1)[:, :n_zones]
        pos = np.full((n, NZ), -1); pos[np.arange(n)[:, None], zsel] = np.arange(n_zones)[None, :]
        for c in range(ncfg):
            wc = df[f"w_{c}"].to_numpy(float)
            for k in range(ncand):
                w = wc * df[f"b_{k}"].to_numpy(float); m_ = w > 0
                if not m_.any():
                    continue
                X = by_label(lin(M.utility(M.At(c, k=k)), df, fixed, cache), n)
                for lab, v in X.items():
                    s = store[lab]; s["c"].append(v[m_]); s["cw"].append(w[m_]); s["cr"].append(rid[m_])
            ok = wc > 0
            if not ok.any():
                continue
            AV = {lab: np.zeros((n, n_zones), np.float32) for lab in G}
            for j in range(NZ):
                rj = np.nonzero(pos[:, j] >= 0)[0]
                if not len(rj):
                    continue
                X = by_label(lin(M.utility(M.At(c, j=j)), df, fixed, cache), n)
                for lab, v in X.items():
                    AV[lab][rj, pos[rj, j]] = v[rj]
            for lab, X in AV.items():
                s = store[lab]; s["a"].append(X[ok].ravel()); s["aw"].append(np.repeat(wc[ok] / n_zones, n_zones)); s["ar"].append(np.repeat(rid[ok], n_zones))
    out = []
    for lab in G:
        s = {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in store[lab].items()}
        if not len(s["c"]) or not len(s["a"]):
            continue
        if np.allclose(s["a"], 1.0) and np.allclose(s["c"], 1.0):
            continue
        P_ = _panel(lab, grp[lab], s["c"], s["cw"], s["cr"].astype(int), s["a"], s["aw"], s["ar"].astype(int), base)
        if P_ is not None:
            out.append(P_)
    return out, base


def school_panels(M, st, alt, cand, labels, ref, n_students=2000, seed=1):
    """SILO school location: chosen school zones (location weights) against the available zones (enrolment of the band),
    from the model's TERMS (alternative variable x person variable) and the size term with the reference size weights"""
    rng = np.random.default_rng(seed)
    if len(st) > n_students:
        st = st.iloc[np.sort(rng.choice(len(st), n_students, replace=False))]
    S = st.set_index("student"); ids = S.index.values; rmap = {s: i for i, s in enumerate(ids)}
    A = alt[alt.student.isin(ids) & (alt.av > 0)]; C = cand[cand.student.isin(ids)]
    wh = lambda d: np.array([S.at[s, f"w_home_{h}"] for s, h in zip(d.student, d.home_slot)], float)
    cw = wh(C) * np.array([S.at[s, f"w_school_{k}"] for s, k in zip(C.student, C.school_slot)], float)
    cw = cw / pd.Series(cw).groupby(C.student.values).transform("sum").to_numpy()
    nav = A.groupby(["student", "home_slot"]).j.transform("size").to_numpy()
    aw = wh(A) / nav
    cr, ar = C.student.map(rmap).to_numpy(), A.student.map(rmap).to_numpy()
    def size(d):
        s = 0.0
        for i, g in enumerate(M.SIZE_W):
            s = s + (1.0 if g is None else np.exp(ref[g])) * d[f"nk{i}"].to_numpy(float)
        return np.log(s + 1e-12)
    out = []
    if "MU_size" in labels:
        P_ = _panel(labels["MU_size"][0], labels["MU_size"][1], size(C), cw, cr, size(A), aw, ar, len(ids))
        if P_ is not None:
            out.append(P_)
    for p, (x, pv) in M.TERMS.items():
        if p not in labels:
            continue
        fc = C[x].to_numpy(float) * (S[pv].reindex(C.student).to_numpy(float) if pv else 1.0)
        fa = A[x].to_numpy(float) * (S[pv].reindex(A.student).to_numpy(float) if pv else 1.0)
        P_ = _panel(labels[p][0], labels[p][1], fc, cw, cr, fa, aw, ar, len(ids))
        if P_ is not None:
            out.append(P_)
    return out, len(ids)


def by_choice(util, av, choice, data, labels, alt_names, fixed=None):
    """small choice sets: each variable by chosen alternative. Person / household variables (the same value in every
    utility they enter): mean or share among the records that chose each alternative. Alternative attributes (values that
    differ between alternatives): mean at the chosen alternative against the mean over the records where it is available."""
    n = len(data); cache = {}
    T = util_terms(util, data, fixed); J = list(util)
    AVm = {j: _arr(av[j], data, n, cache) > 0 for j in J}
    ch = _arr(choice, data, n, cache).astype(int)
    G, grp = label_groups([p for p in labels if any(p in T[j] for j in J)], labels)
    out = []
    for lab, ps in G.items():
        where = {p: [j for j in J if p in T[j]] for p in ps}
        alts = [j for j in J if any(p in T[j] for p in ps)]
        X = {j: sum(T[j][p] for p in ps if p in T[j]) for j in alts}
        if all(np.allclose(X[j][AVm[j]], 1.0) for j in alts):
            continue                                   # a constant
        person = all(len(w) == 1 for w in where.values()) and all(np.allclose(X[alts[0]], X[j]) for j in alts[1:])
        if person:
            v = X[alts[0]]
            applies = np.ones(n, bool)
            binary = set(np.round(np.unique(v), 9)).issubset({0.0, 1.0})
            rows = []
            for j in J:
                m = (ch == j) & applies
                rows.append(dict(alt=alt_names.get(j, str(j)), n=int(m.sum()), mean=float(v[m].mean()) if m.any() else np.nan,
                                 q1=float(np.percentile(v[m], 25)) if m.any() else np.nan, q3=float(np.percentile(v[m], 75)) if m.any() else np.nan))
            out.append(dict(kind="person", label=lab, group=grp[lab], binary=binary, t=pd.DataFrame(rows), overall=float(v.mean()),
                            sd=float(v.std()) if not binary else float(np.sqrt(max(v.mean() * (1 - v.mean()), 1e-12)))))
        else:
            rows = []
            for j in alts:
                mc, ma = (ch == j) & AVm[j], AVm[j]
                rows.append(dict(alt=alt_names.get(j, str(j)), n=int(mc.sum()), chosen=float(X[j][mc].mean()) if mc.any() else np.nan,
                                 available=float(X[j][ma].mean()) if ma.any() else np.nan))
            binary = all(set(np.round(np.unique(X[j]), 9)).issubset({0.0, 1.0}) for j in alts)
            out.append(dict(kind="alternative", label=lab, group=grp[lab], binary=binary, t=pd.DataFrame(rows)))
    return out


# ------------------------------------------------------------------------------------------------ figures and readings
def _chunks(panels, size=9):
    out, cur = [], []
    for p in panels:
        if len(cur) == size:
            out.append(cur); cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def _wpct(x, w, q):
    o = np.argsort(x); x, w = x[o], w[o]; c = np.cumsum(w); c = c / c[-1]
    return np.interp(np.asarray(q) / 100, c, x)


def _stats(p):
    mc, ma = np.average(p["c"], weights=p["cw"]), np.average(p["a"], weights=p["aw"])
    if p["binary"]:
        sd = np.sqrt(max(ma * (1 - ma), 1e-6))
    else:
        sd = np.sqrt(np.average((p["a"] - ma) ** 2, weights=p["aw"]))
        if sd == 0:
            sd = np.sqrt(np.average((p["c"] - mc) ** 2, weights=p["cw"])) or 1.0
    return mc, ma, (mc - ma) / sd


def _value(p, v):
    return f"{100 * v:.1f} %" if p["binary"] else f"mean {fmt(v)}"


def _header(fig, H, title, groups, handles, labels):
    """title on the first line (left), legend on the first line (right), variable groups on the second line"""
    fig.text(0.01, 1 - 0.08 / H, title, ha="left", va="top", fontsize=9, fontweight="bold")
    if groups:
        fig.text(0.01, 1 - 0.30 / H, "\n".join(textwrap.wrap("Variables: " + ", ".join(groups).lower().replace(" x ", " × "), 110)), ha="left", va="top", fontsize=FS, color=INK2)
    fig.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.995, 1 - 0.02 / H), ncol=len(handles), frameon=False)
    plt.tight_layout(rect=(0, 0, 1, 1 - 0.62 / H))


def location_figures(panels, what="available", unit="records", ncol=3, size=9, title="Chosen against {what} alternatives"):
    """one figure per (up to) nine variables; histograms (share of the alternatives, %) or bars for 0/1 variables;
    each figure followed by its readings"""
    _rc(); lab_av = what.capitalize()
    for chunk in _chunks(panels, size):
        nrow = int(np.ceil(len(chunk) / ncol))
        H = 2.2 * nrow + 0.65; fig, axs = plt.subplots(nrow, ncol, figsize=(8.2, H), squeeze=False)
        for i, (ax, p) in enumerate(zip(axs.flat, chunk)):
            mc, ma, _ = _stats(p)
            if p["binary"]:
                ax.bar([0, 1], [100 * mc, 100 * ma], color=[OBS, AVAIL], width=0.6)
                for x, v in ((0, mc), (1, ma)):
                    ax.text(x, 100 * v, f"{100 * v:.1f}", ha="center", va="bottom", fontsize=TICK, color=INK2)
                ax.set_xticks([0, 1]); ax.set_xticklabels(["Chosen", lab_av]); ax.set_ylabel("Share with value 1 (%)")
                ax.set_ylim(0, max(100 * mc, 100 * ma, 1) * 1.2)
            else:
                allv, allw = np.r_[p["c"], p["a"]], np.r_[p["cw"] / p["cw"].sum(), p["aw"] / p["aw"].sum()]
                lo, hi = _wpct(allv, allw, [1, 99])
                if hi <= lo:
                    lo, hi = allv.min(), allv.max() + 1e-9
                b = np.linspace(lo, hi, 26)
                ha, _ = np.histogram(np.clip(p["a"], lo, hi), b, weights=p["aw"]); hc, _ = np.histogram(np.clip(p["c"], lo, hi), b, weights=p["cw"])
                ax.bar(b[:-1], 100 * ha / ha.sum(), width=np.diff(b), align="edge", color=AVAIL, lw=0)
                ax.step(b, 100 * np.r_[hc, hc[-1]] / hc.sum(), where="post", color=OBS, lw=1.4)
                ax.axvline(mc, color=OBS, lw=0.9, ls="--"); ax.axvline(ma, color="#8f8e88", lw=0.9, ls="--")
                ax.set_ylabel("Share (%)" if i % ncol == 0 else "")
            t = f"({chr(97 + i)}) " + p["label"] + (f" [{100 * p['share']:.0f} % of {unit}]" if p["share"] < 0.995 else "")
            ax.set_title("\n".join(textwrap.wrap(t, 40)), fontsize=FS)
        for ax in list(axs.flat)[len(chunk):]:
            ax.axis("off")
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        groups = list(dict.fromkeys(p["group"] for p in chunk if p["group"]))
        _header(fig, H, title.format(what=what), groups, [Line2D([], [], color=OBS, lw=1.6), Patch(color=AVAIL)], ["Chosen", lab_av])
        plt.show()
        _show_lines(location_lines(chunk, what, unit))


def location_lines(chunk, what, unit):
    S = [(chr(97 + i), p) + _stats(p) for i, p in enumerate(chunk)]
    S2 = sorted(S, key=lambda s: -abs(s[4]))
    big = [s for s in S2 if abs(s[4]) >= 0.1][:3]
    lines = []
    if big:
        lines.append("Largest differences, chosen against " + what + ": " + "; ".join(
            f"({s[0]}) {s[1]['label']}, {_value(s[1], s[2])} against {_value(s[1], s[3])}" for s in big) + ".")
    small = [s for s in S2[::-1] if abs(s[4]) < 0.1][:2]
    if small:
        lines.append("Almost no difference: " + "; ".join(f"({s[0]}) {s[1]['label']} ({_value(s[1], s[2])} against {_value(s[1], s[3])})" for s in small) + ".")
    hi = sum(s[2] > s[3] for s in S)
    if len(S) >= 3:
        lines.append(f"The chosen value is higher than the {what} one in {hi} of {len(S)} panels (dashed lines: means).")
    part = [s for s in S if s[1]["share"] < 0.995]
    if part:
        lines.append(("Panels " if len(part) > 1 else "Panel ") + ", ".join(f"({s[0]})" for s in part)
                     + (" show" if len(part) > 1 else " shows") + f" only the {unit} for whom the variable is not zero at every alternative (share in the title).")
    return lines


def by_choice_figures(panels, alt_order, ncol=3, size=9, unit="records", title="Variables by chosen alternative"):
    _rc()
    for chunk in _chunks(panels, size):
        nrow = int(np.ceil(len(chunk) / ncol))
        H = 2.35 * nrow + 0.65; fig, axs = plt.subplots(nrow, ncol, figsize=(8.2, H), squeeze=False)
        for i, (ax, p) in enumerate(zip(axs.flat, chunk)):
            t = p["t"]
            if p["kind"] == "person":
                t = t.set_index("alt").reindex([a for a in alt_order if a in set(t.alt)])
                k = 100 if p["binary"] else 1
                x = np.arange(len(t))
                ax.bar(x, k * t["mean"], color=OBS, width=0.65)
                if not p["binary"]:
                    ax.vlines(x, t.q1, t.q3, color=AVAIL, lw=2.2)
                ax.axhline(k * p["overall"], color="#8f8e88", lw=0.9, ls="--")
                ax.set_ylabel("Share (%)" if p["binary"] else "Mean")
            else:
                t = t.set_index("alt").reindex([a for a in alt_order if a in set(t.alt)])
                k = 100 if p["binary"] else 1
                x = np.arange(len(t))
                ax.bar(x - 0.18, k * t.chosen, width=0.36, color=OBS); ax.bar(x + 0.18, k * t.available, width=0.36, color=AVAIL)
                ax.set_ylabel("Share (%)" if p["binary"] else "Mean")
            ax.set_xticks(x); ax.set_xticklabels(t.index, rotation=35 if len(t) > 3 else 0, ha="right" if len(t) > 3 else "center")
            ax.set_title("\n".join(textwrap.wrap(f"({chr(97 + i)}) " + p["label"], 40)), fontsize=FS)
        for ax in list(axs.flat)[len(chunk):]:
            ax.axis("off")
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        h = [Patch(color=OBS), Line2D([], [], color="#8f8e88", lw=0.9, ls="--")]; l = ["Chosen (mean or share)", f"All {unit}"]
        if any(p["kind"] == "alternative" for p in chunk):
            h.append(Patch(color=AVAIL)); l.append("Where available (attributes)")
        groups = list(dict.fromkeys(p["group"] for p in chunk if p["group"]))
        _header(fig, H, title, groups, h, l)
        plt.show()
        _show_lines(by_choice_lines(chunk, unit))


def by_choice_lines(chunk, unit, min_n=20):
    lines, spread, few = [], [], set()
    for i, p in enumerate(chunk):
        few |= set(p["t"].alt[p["t"].n < min_n])
        if p["kind"] != "person":
            continue
        t = p["t"][p["t"].n >= min_n].dropna(subset=["mean"])
        if len(t) < 2:
            continue
        hi, lo = t.loc[t["mean"].idxmax()], t.loc[t["mean"].idxmin()]
        spread.append(((hi["mean"] - lo["mean"]) / max(p["sd"], 1e-9), chr(97 + i), p, hi, lo))
    spread.sort(key=lambda s: -s[0])
    v = lambda p, x: f"{100 * x:.1f} %" if p["binary"] else fmt(x)
    if spread:
        lines.append("Largest differences between the chosen alternatives: " + "; ".join(
            f"({s[1]}) {s[2]['label']}, {v(s[2], s[3]['mean'])} for {s[3]['alt'].lower()} against {v(s[2], s[4]['mean'])} for {s[4]['alt'].lower()}"
            for s in spread[:3]) + ".")
        if len(spread) > 3:
            s = spread[-1]
            lines.append(f"Smallest: ({s[1]}) {s[2]['label']}, from {v(s[2], s[4]['mean'])} to {v(s[2], s[3]['mean'])} (all {unit}: {v(s[2], s[2]['overall'])}).")
        else:
            s = spread[0]
            lines.append(f"({s[1]}) {s[2]['label']}, all {unit}: {v(s[2], s[2]['overall'])}.")
    for i, p in enumerate(chunk):
        if p["kind"] != "alternative":
            continue
        t = p["t"][p["t"].n >= min_n].dropna(subset=["chosen", "available"])
        if len(t):
            lo = int((t.chosen < t.available).sum())
            lines.append(f"({chr(97 + i)}) {p['label']}: the mean at the chosen alternative is lower than where it is available for {lo} of {len(t)} alternatives.")
    if few:
        lines.append(f"Not used in these lines (chosen by fewer than {min_n} {unit}): " + ", ".join(sorted(a.lower() for a in few)) + ".")
    return lines[:4]


def choice_counts_line(data_choice, alt_names, unit="records"):
    c = pd.Series(np.asarray(data_choice).astype(int)).value_counts()
    return f"{unit.capitalize()} by chosen alternative: " + ", ".join(f"{alt_names.get(j, j).lower()} {c.get(j, 0):,}" for j in alt_names) + "."


# ------------------------------------------------------------------------------------------------ residential PUMA level: ACS migration fields
MIG_LAB = {1: "Same house", 2: "Abroad", 3: "Other U.S. house"}
MV_LAB = {1: "12 months\nor less", 2: "13-23\nmonths", 3: "2-4\nyears", 4: "5-9\nyears", 5: "10-19\nyears", 6: "20-29\nyears", 7: "30 years\nor more"}


def _bars(ax, s, ylab, color=OBS, rot=0, fmt_=lambda v: f"{v:.1f}"):
    x = np.arange(len(s)); ax.bar(x, s.values, color=color, width=0.65)
    for xi, v in zip(x, s.values):
        ax.text(xi, v, fmt_(v), ha="center", va="bottom", fontsize=TICK, color=INK2)
    ax.set_xticks(x); ax.set_xticklabels(s.index, rotation=rot, ha="right" if rot else "center"); ax.set_ylabel(ylab)
    ax.set_ylim(0, max(s.max(), 1e-9) * 1.18)


def _grouped(ax, t, cols, colors, ylab, rot=0):
    x = np.arange(len(t)); w = 0.8 / len(cols)
    for i, (c, col) in enumerate(zip(cols, colors)):
        ax.bar(x + (i - (len(cols) - 1) / 2) * w, t[c].values, width=w, color=col, label=c)
    ax.set_xticks(x); ax.set_xticklabels(t.index, rotation=rot, ha="right" if rot else "center"); ax.set_ylabel(ylab)


def persons_moved(S3):
    """persons aged 1+ of the six states by survey year: weighted share (PWGTP) who lived in another house a year ago (MIG 2 or 3)"""
    rows = []
    for s in S3.STATES:
        p = S3.pums_read(2018, "p", s, ["SERIALNO", "PWGTP", "MIG", "AGEP"])
        p = p[p.MIG.notna()]; p["svy"] = p.SERIALNO.str[:4].astype(int)
        rows.append(p.assign(moved=p.MIG.isin([2, 3]) * p.PWGTP).groupby("svy")[["moved", "PWGTP"]].sum())
    t = sum(rows); return 100 * t.moved / t.PWGTP


def acs_fields_figure(H, moved_by_year):
    """(a) MIG of the householder, (b) MV, (c) MV 1 by MIG, (d) persons moved by survey year; all weighted"""
    _rc(); w = H.WGTP.astype(float)
    mig = (H.mig.map(MIG_LAB).fillna("Not reported")); a = (100 * w.groupby(mig).sum() / w.sum()).reindex(list(MIG_LAB.values()))
    mv = (100 * w.groupby(H.MV).sum() / w[H.MV.notna()].sum()).reindex(list(MV_LAB)); mv.index = [MV_LAB[i] for i in mv.index]
    m1 = H.MV == 1; c = (100 * w[m1].groupby(mig[m1]).sum() / w[m1].sum()).reindex(list(MIG_LAB.values())).fillna(0)
    m3 = H.mig == 3; mv1_of_mig3 = 100 * w[m3 & m1].sum() / w[m3].sum()
    fig, ax = plt.subplots(2, 2, figsize=(8.2, 5.4))
    _bars(ax[0, 0], a, "Households (%)"); ax[0, 0].set_title("(a) Where the householder lived a year ago (MIG)")
    _bars(ax[0, 1], mv, "Households (%)"); ax[0, 1].set_title("(b) When the household moved into the unit (MV)")
    _bars(ax[1, 0], c, "Households with MV 1 (%)"); ax[1, 0].set_title("(c) Moved in within 12 months: householder a year ago")
    y = moved_by_year; ax[1, 1].plot(y.index, y.values, "o-", color=OBS); ax[1, 1].set_xticks(y.index)
    for xi, v in zip(y.index, y.values):
        ax[1, 1].text(xi, v, f" {v:.1f}", fontsize=TICK, color=INK2, va="bottom")
    ax[1, 1].set_ylabel("Persons aged 1+ (%)"); ax[1, 1].set_xlabel("Survey year"); ax[1, 1].set_title("(d) Persons who lived in another house a year ago")
    ax[1, 1].set_ylim(0, y.max() * 1.25)
    plt.tight_layout(); plt.show()
    _show_lines([
        f"(a) {a['Same house']:.1f} % of households have a householder who lived in the same house a year ago, {a['Other U.S. house']:.1f} % in another U.S. house, {a['Abroad']:.1f} % abroad (weighted, six states, 2014-2018).",
        f"(b) {mv.iloc[0]:.1f} % moved into their unit within 12 months (MV 1). (c) Of these, {c['Other U.S. house']:.1f} % have a householder from another U.S. house (the movers of the model), "
        f"{c['Same house']:.1f} % a householder who reports the same house and {c['Abroad']:.1f} % one from abroad; of the householders from another U.S. house, {mv1_of_mig3:.1f} % report MV 1.",
        f"(d) The share of persons who moved within the year is {y.min():.1f} to {y.max():.1f} % across the survey years ({int(y.idxmin())} lowest, {int(y.idxmax())} highest)."])


def od_class(df, J):
    """class of the move from the PUMA-level table: inside the previous MIGPUMA / bordering / rest of the same state / other state"""
    r = np.arange(len(df)); ch = df.choice.to_numpy()
    g = lambda v: df[[f"{v}_{j}" for j in range(J)]].to_numpy()[r, ch]
    same, adj, st = g("same"), g("adjacent"), g("same_state")
    return pd.Series(np.select([same > 0, adj > 0, st > 0], ["Inside the previous\nMIGPUMA", "Bordering\nMIGPUMA", "Rest of the\nsame state"], "Other state"), index=df.index)


def move_times(mig7, puma7, SH, rc):
    """expected car time (min, AM peak skim) between the housing units of the origin MIGPUMA and of the destination PUMA"""
    import os
    car = rc.read_skim(rc.SKIM_CAR); car = np.where(np.isnan(car), np.nanmax(car), car)
    zi = pd.Series(np.arange(len(rc.ZONE_IDS)), index=rc.ZONE_IDS)
    mz = pd.read_csv(os.path.join(SH, "resloc_work", "geo_mig_zone_all.csv")); pz = pd.read_csv(os.path.join(SH, "resloc_work", "geo_puma_zone_all.csv"))
    def W(t, key):
        t = t[t.zone.isin(zi.index)]; out = {}
        for k, g in t.groupby(key):
            w = np.zeros(len(zi)); w[zi[g.zone].values] = g.hu.values; s = w.sum()
            out[k] = w / s if s > 0 else None
        return out
    O, D = W(mz, "mig7"), W(pz, "puma7"); cache = {}
    res = []
    for m, p in zip(mig7, puma7):
        if (m, p) not in cache:
            cache[(m, p)] = float(O[m] @ car @ D[p]) if O.get(m) is not None and D.get(p) is not None else np.nan
        res.append(cache[(m, p)])
    return np.array(res)


OD_TXT = {"Inside the previous\nMIGPUMA": "inside the previous MIGPUMA", "Bordering\nMIGPUMA": "bordering MIGPUMA",
          "Rest of the\nsame state": "rest of the same state", "Other state": "other state"}


def od_figure(cls, t, weight):
    _rc(); order = ["Inside the previous\nMIGPUMA", "Bordering\nMIGPUMA", "Rest of the\nsame state", "Other state"]
    s = pd.DataFrame({"Unweighted": 100 * cls.value_counts(normalize=True), "Estimation weight": 100 * weight.groupby(cls).sum() / weight.sum()}).reindex(order).fillna(0)
    fig, ax = plt.subplots(1, 3, figsize=(8.2, 2.9))
    _grouped(ax[0], s, ["Unweighted", "Estimation weight"], [OBS, AVAIL], "Movers (%)"); ax[0].legend(frameon=False, fontsize=TICK)
    ax[0].set_title("(a) Destination against origin"); ax[0].tick_params(axis="x", labelsize=TICK)
    ok = np.isfinite(t); b = np.arange(0, min(np.nanpercentile(t, 99), 240) + 5, 5)
    ax[1].hist(np.clip(t[ok], 0, b[-1]), bins=b, color=OBS); ax[1].axvline(np.median(t[ok]), color=INK2, ls="--", lw=0.9)
    ax[1].set_xlabel("Car time moved (min)"); ax[1].set_ylabel("Movers"); ax[1].set_title("(b) Car time from origin to destination")
    med = pd.Series(t).groupby(cls.values).median().reindex(order)
    _bars(ax[2], med, "Median car time (min)", fmt_=lambda v: f"{v:.0f}"); ax[2].tick_params(axis="x", labelsize=TICK)
    ax[2].set_title("(c) Median car time by class")
    plt.tight_layout(); plt.show()
    _show_lines([
        "(a) " + ", ".join(f"{OD_TXT[k]} {v:.1f} %" for k, v in s["Unweighted"].items()) + " of the estimation movers (unweighted; "
        + ", ".join(f"{v:.1f}" for v in s["Estimation weight"]) + " % with the estimation weight).",
        f"(b) Median car time moved {np.median(t[ok]):.0f} min; {100 * np.mean(t[ok] <= 20):.0f} % of the movers moved 20 min or less, {100 * np.mean(t[ok] > 60):.0f} % more than 60 min "
        "(car time between the housing units of the origin MIGPUMA and of the destination PUMA, so a move inside a MIGPUMA also has a time above 0).",
        "(c) Median by class: " + ", ".join(f"{OD_TXT[k]} {v:.0f} min" for k, v in med.items()) + "."])


def flow_map(mig7, puma7, cls, SH, ZS, top=150):
    """MIGPUMA -> PUMA flows: lines between the housing-unit centroids for moves that leave the origin MIGPUMA (the largest
    pairs), circles at the destination for moves inside it; Maryland and DC"""
    import os
    import nbtools as nt
    from matplotlib.collections import PolyCollection, LineCollection
    _rc()
    shp = nt.zone_shapes(); cen = {z: np.vstack(r).mean(0) for z, r in shp if r}
    mz = pd.read_csv(os.path.join(SH, "resloc_work", "geo_mig_zone_all.csv")); pz = pd.read_csv(os.path.join(SH, "resloc_work", "geo_puma_zone_all.csv"))
    def C(t, key):
        t = t[t.zone.isin(cen.keys()) & (t.hu > 0)].copy(); xy = np.vstack(t.zone.map(cen).values)
        t["x"], t["y"] = xy[:, 0] * t.hu, xy[:, 1] * t.hu
        g = t.groupby(key)[["x", "y", "hu"]].sum(); return pd.DataFrame({"x": g.x / g.hu, "y": g.y / g.hu})
    Cm, Cp = C(mz, "mig7"), C(pz, "puma7")
    f = pd.DataFrame({"o": mig7, "d": puma7}); f["inside"] = np.asarray(cls) == "Inside the previous\nMIGPUMA"   # as panel (a) above
    out = f[~f.inside].groupby(["o", "d"]).size().sort_values(ascending=False); ins = f[f.inside].groupby("d").size()
    sel = out.head(top)
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    polys = [r for z, rings in shp for r in rings]
    ax.add_collection(PolyCollection(polys, facecolors="#f4f3ef", edgecolors="#d9d8d2", linewidths=0.15))
    segs, lw = [], []
    for (o, d), n in sel.items():
        if o in Cm.index and d in Cp.index:
            segs.append([(Cm.at[o, "x"], Cm.at[o, "y"]), (Cp.at[d, "x"], Cp.at[d, "y"])]); lw.append(n)
    lw = np.array(lw, float)
    ax.add_collection(LineCollection(segs, linewidths=0.3 + 3.2 * lw / lw.max(), colors=OBS, alpha=0.55))
    di = ins[ins.index.isin(Cp.index)]
    ax.scatter(Cp.loc[di.index, "x"], Cp.loc[di.index, "y"], s=4 + 120 * di.values / di.max(), color=MODEL, alpha=0.8, lw=0, zorder=3)
    st = nt.zone_table()["county"] // 1000
    xy = np.vstack([np.vstack(r) for z, r in shp if r and st.get(z, 0) in (11, 24)])
    ax.set_xlim(xy[:, 0].min(), xy[:, 0].max()); ax.set_ylim(xy[:, 1].min(), xy[:, 1].max()); ax.set_aspect("equal"); ax.set_axis_off()
    from matplotlib.lines import Line2D
    ax.legend([Line2D([], [], color=OBS, lw=2), Line2D([], [], marker="o", color=MODEL, lw=0, ms=7)],
              [f"Move to another area (the {len(sel)} largest origin-destination pairs; width = movers)", "Move inside the origin MIGPUMA (size = movers)"],
              loc="lower left", frameon=False, fontsize=TICK)
    ax.set_title("(a) Moves from the origin MIGPUMA to the destination PUMA, estimation movers", fontsize=FS)
    plt.tight_layout(); plt.show()
    zc = ZS.drop_duplicates("PUMA_10").set_index("PUMA_10")
    cty = ZS.groupby("PUMA_10").JUR_NAME.agg(lambda s: s.mode().iloc[0])
    mcty = mz.merge(ZS[["zone", "JUR_NAME"]], on="zone").groupby("mig7").JUR_NAME.agg(lambda s: s.mode().iloc[0])
    (o, d), n = out.index[0], out.iloc[0]
    _show_lines([
        f"{100 * f.inside.mean():.1f} % of the movers stay inside their origin MIGPUMA (circles); the {len(sel)} pairs drawn carry {100 * sel.sum() / max(out.sum(), 1):.0f} % of the moves between areas.",
        f"Largest pair between areas: from {mcty.get(o, o)} to {cty.get(d, d)} ({n} movers). Lines run between housing-unit centroids, so they show direction and volume, not the addresses."])


ACS_LIMITS = """What the ACS does not give:
- no previous address: the origin is known only as the migration PUMA (MIGPUMA), a group of PUMAs with at least 100,000 people;
- no reason for the move and no information on the previous dwelling (type, tenure, cost);
- a one-year recall window: a household that moved twice in the year shows only the place a year ago;
- not a panel: each household is seen once, so the same household's earlier and later moves are not observed;
- MIG is asked of persons (the householder is used here) and MV of the housing unit, so the two can disagree (panel c)."""


# ------------------------------------------------------------------------------------------------ residential dwelling level
INC_G = [("Under $25k", 0, 25000), ("$25-50k", 25000, 50000), ("$50-100k", 50000, 100000), ("$100k or more", 100000, np.inf)]


def dwelling_figure(df, J=30):
    """new dwellings, bedrooms against need (need = household size, at most 5, as in the model) and cost share of income;
    chosen dwelling against the 29 sampled dwellings"""
    _rc()
    inc = df.income_2016usd.to_numpy(float); g = pd.Series(pd.cut(inc, [-np.inf] + [x[2] for x in INC_G], labels=[x[0] for x in INC_G], right=False), index=df.index)
    S = range(1, J)
    av = df[[f"av_{j}" for j in S]].to_numpy() > 0
    def ch(v):
        return df[f"{v}_0"].to_numpy(float)
    def sm(v):
        X = df[[f"{v}_{j}" for j in S]].to_numpy(float); X = np.where(av, X, np.nan); return X
    new_c, new_s = ch("new5"), sm("new5")
    short_c, extra_c = ch("bed_short"), ch("bed_extra"); short_s, extra_s = sm("bed_short"), sm("bed_extra")
    cat = lambda s, e: np.where(s > 0, "Shortfall", np.where(e > 0, "Extra", "Exact"))
    need = np.minimum(df.persons.to_numpy(float), 5)
    share_c = 12 * ch("cost") / np.maximum(inc, 5000); share_s = 12 * sm("cost") / np.maximum(inc, 5000)[:, None]
    def by_g(c, s, f):
        return pd.DataFrame({"Chosen": [f(c[(g == k).values]) for k in g.cat.categories],
                             "Sampled": [f(s[(g == k).values][np.isfinite(s[(g == k).values])]) for k in g.cat.categories]}, index=g.cat.categories)
    pct = lambda x: 100 * np.mean(x)
    t_new = by_g(new_c, new_s, pct)
    cc = pd.Series(cat(short_c, extra_c)).value_counts(normalize=True) * 100
    cs_ = pd.Series(cat(short_s[av], extra_s[av])).value_counts(normalize=True) * 100
    t_bed = pd.DataFrame({"Chosen": cc, "Sampled": cs_}).reindex(["Shortfall", "Exact", "Extra"]).fillna(0)
    bc, bs = ch("bedrooms"), sm("bedrooms")
    t_nb = pd.DataFrame({"Chosen": [bc[need == k].mean() for k in range(1, 6)], "Sampled": [np.nanmean(bs[need == k]) for k in range(1, 6)]},
                        index=["1", "2", "3", "4", "5+"])
    t_sh = by_g(short_c > 0, short_s > 0, pct)
    t_med = by_g(share_c, share_s, lambda x: 100 * np.median(x))
    t_30 = by_g(share_c > 0.3, share_s > 0.3, pct)
    fig, ax = plt.subplots(2, 3, figsize=(8.2, 5.6)); ax = ax.ravel(); cols = ["Chosen", "Sampled"]; colors = [OBS, AVAIL]
    _grouped(ax[0], t_new, cols, colors, "Dwellings (%)", rot=25); ax[0].set_title("(a) Built in the last 5 years")
    _grouped(ax[1], t_bed, cols, colors, "Dwellings (%)"); ax[1].set_title("(b) Bedrooms against need")
    _grouped(ax[2], t_nb, cols, colors, "Mean bedrooms"); ax[2].plot(range(5), range(1, 6), color=INK2, lw=0.8, ls="--")
    ax[2].set_xlabel("Bedrooms needed"); ax[2].set_title("(c) Bedrooms by bedrooms needed")
    _grouped(ax[3], t_sh, cols, colors, "Dwellings (%)", rot=25); ax[3].set_title("(d) Bedroom shortfall by income")
    _grouped(ax[4], t_med, cols, colors, "Median cost / income (%)", rot=25); ax[4].set_title("(e) Housing cost share of income")
    _grouped(ax[5], t_30, cols, colors, "Dwellings (%)", rot=25); ax[5].set_title("(f) Cost above 30 % of income")
    for a in (ax[0], ax[3], ax[4], ax[5]):
        a.set_xlabel("Household income (2016 $)")
    fig.legend([plt.Rectangle((0, 0), 1, 1, color=OBS), plt.Rectangle((0, 0), 1, 1, color=AVAIL)], ["Chosen dwelling", "Sampled dwellings (29 per mover)"],
               loc="upper right", ncol=2, frameon=False)
    plt.tight_layout(rect=(0, 0, 1, 0.95)); plt.show()
    lo, hi = "income " + INC_G[0][0].lower(), "income " + INC_G[-1][0]
    _show_lines([
        f"(a) New dwellings: {pct(new_c):.1f} % of the chosen against {100 * np.nanmean(new_s):.1f} % of the sampled; households with {lo}: {t_new.Chosen.iloc[0]:.1f} against {t_new.Sampled.iloc[0]:.1f} %, with {hi}: {t_new.Chosen.iloc[-1]:.1f} against {t_new.Sampled.iloc[-1]:.1f} %.",
        f"(b) Exact number of bedrooms: {t_bed.Chosen['Exact']:.1f} % of the chosen against {t_bed.Sampled['Exact']:.1f} % of the sampled; shortfall {t_bed.Chosen['Shortfall']:.1f} against {t_bed.Sampled['Shortfall']:.1f} %. "
        f"(c) Households that need 5+ bedrooms choose {t_nb.Chosen.iloc[-1]:.1f} bedrooms on average (sampled {t_nb.Sampled.iloc[-1]:.1f}).",
        f"(e) Median cost share of income, {lo}: {t_med.Chosen.iloc[0]:.0f} % chosen against {t_med.Sampled.iloc[0]:.0f} % sampled; {hi}: {t_med.Chosen.iloc[-1]:.0f} against {t_med.Sampled.iloc[-1]:.0f} %. "
        f"(f) Above 30 % of income: {t_30.Chosen.iloc[0]:.0f} % of the chosen dwellings of the lowest group, {t_30.Chosen.iloc[-1]:.0f} % of the highest.",
        "Bedrooms needed = household size, at most 5, as in the model (the data column bedroom_need follows an older rule and is not used by the model); income at least $5,000 in the cost share."])


def choices(choice, data):
    return _arr(choice, data, len(data), {}).astype(int)
