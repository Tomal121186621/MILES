"""Shared figures of the estimation PDF and the notebooks (paper style of 5_reports/paperstyle.py: model orange, observed dark grey,
fixed categorical order, fonts >= 7.5 pt, labelled panels).  Every function draws into a given figure (the PDF scripts pass a
paperstyle figure and run its checks; the notebooks pass none and get an inline figure).

  coef_figure(rows, fig)            estimates with 95 % robust intervals, grouped by block, zero line; optional series (e.g. number of cars)
  income_effect_figure(folder, ...) effect on utility against household income with 95 % delta-method bands (nb_reader.EFFECTS)
  group_effect_figure(folder, ...)  effect by person group with 95 % delta-method intervals (nb_reader.EFFECTS, kind 'group')
  obs_model_figure(panels, fig)     observed (dark grey) and model (orange) bars per category, one panel each
  scatter_obs_model(t, ax)          observed against model share, equality line"""
import numpy as np, pandas as pd
import nb_reader as RD

MODEL, OBS, INK, INK2, AXIS, GRID = "#e8811a", "#3b4252", "#0b0b0b", "#52514e", "#c3c2b7", "#e1e0d9"
CAT = ["#e8811a", "#2a78d6", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BAND = "#fbd9b5"
WIDTH = 390.0 / 72.27          # 137 mm
FS, TICK = 8.0, 7.5
XT = [25000, 50000, 100000, 150000, 250000]
GRIDI = np.exp(np.linspace(np.log(15000), np.log(250000), 60))
MINUS = "−"


def _fig(fig, h):
    import matplotlib.pyplot as plt
    if fig is not None: return fig
    plt.rcParams.update({"font.size": FS, "axes.titlesize": FS, "axes.labelsize": FS, "xtick.labelsize": TICK, "ytick.labelsize": TICK,
                         "legend.fontsize": TICK, "axes.spines.top": False, "axes.spines.right": False, "axes.titlelocation": "left",
                         "axes.titleweight": "bold"})
    return plt.figure(figsize=(WIDTH, h), layout="constrained")


def dl(s):
    """display label: natural log written as log (ln reads as In in the sans font)"""
    import re
    return re.sub(r"\bln\b", "log", str(s))


def num(v, d=2):
    return f"{v:+.{d}f}".replace("-", MINUS)


# ------------------------------------------------------------------------------------------------ coefficient plot
def coef_rows(folder, est):
    """est: parameter, coefficient, robust_se -> rows label, group, coef, se, series (car ownership: number of cars)"""
    S = RD.SPEC[folder]; out = []
    for p, c, s in zip(est.parameter, est.coefficient, est.robust_se):
        t, suf = RD.term(folder, p)
        if t is None: continue
        out.append(dict(label=t["label"], group=t["group"], coef=c, se=s, series=S["alt_suffix"][suf] if suf else ""))
    return pd.DataFrame(out)


def coef_figure(rows, fig=None, title=None, xlabel="Coefficient (95 % robust interval)", max_rows=None):
    rows = rows.copy(); series = [s for s in dict.fromkeys(rows.series) if s]
    labs = list(dict.fromkeys(zip(rows.group, rows.label)))
    groups = list(dict.fromkeys(g for g, _ in labs))
    n = len(labs) + len(groups)
    fig = _fig(fig, min(6.6, 0.16 * n + 0.9)); ax = fig.subplots(1, 1)
    y, yt, yl, bold, pos = 0, [], [], [], {}
    for g in groups:
        yt.append(y); yl.append(g); bold.append(True); y += 1
        for gg, l in labs:
            if gg != g: continue
            pos[(gg, l)] = y; yt.append(y); yl.append(l); bold.append(False); y += 1
    st = min(0.22, 0.7 / max(1, len(series))); off = {s: (k - (len(series) - 1) / 2) * st for k, s in enumerate(series)} if series else {"": 0}
    for k, s in enumerate(series or [""]):
        r = rows[rows.series == s]; yy = [pos[(g, l)] + off[s] for g, l in zip(r.group, r.label)]
        ax.errorbar(r.coef, yy, xerr=1.96 * r.se, fmt="o", ms=2.8, color=CAT[k] if series else MODEL, elinewidth=1.0, capsize=0, label=s or None)
    ax.axvline(0, color=INK2, lw=0.6); ax.set_yticks(yt); ax.set_yticklabels([(dl(x)[:46] + "...") if len(dl(x)) > 49 else dl(x) for x in yl], fontsize=TICK); ax.set_ylim(y - 0.4, -0.6)
    for t, bd in zip(ax.get_yticklabels(), bold):
        if bd: t.set_fontweight("bold")
    ax.tick_params(axis="y", length=0, pad=3); ax.set_xlabel(xlabel); ax.grid(axis="x", color=GRID, lw=0.4)
    ax.set_title(title or ("(a) Estimates against no car" if series else "(a) Estimates with 95 % robust intervals"), loc="left")
    if series and len(series) <= 3: ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=len(series), borderaxespad=0.1)
    elif series: fig.legend(*ax.get_legend_handles_labels(), frameon=False, loc="outside lower center", ncol=min(len(series), 4))
    return fig


# ------------------------------------------------------------------------------------------------ effects by income / group
def _xaxis(ax, label=True):
    ax.set_xscale("log"); ax.set_xticks(XT); ax.set_xticklabels([f"${x // 1000}k" for x in XT]); ax.minorticks_off(); ax.set_xlim(15000, 250000)
    for t in ax.get_xticklabels(): t.set_rotation(45)
    if label: ax.set_xlabel("Household income (2016 $)")


def income_effect_figure(folder, b, V, fig=None):
    E = RD.EFFECTS[folder]; t = RD.effects(folder, b, V, cols=list(GRIDI)); v50 = RD.effects(folder, b, None, cols=[50000])
    if folder == "02_residential_dwelling":
        feats = [r for r in E["rows"]]
        fig = _fig(fig, 5.6); axs = fig.subplots(3, 3, sharex=True)
        for k, (ax, (blk, f, _)) in enumerate(zip(axs.ravel(), feats)):
            s = t[t.feature == f]
            if s.se.notna().all(): ax.fill_between(s.column, s.value - 1.96 * s.se, s.value + 1.96 * s.se, color=BAND, lw=0)
            ax.plot(s.column, s.value, color=MODEL, lw=1.3); ax.axhline(0, color=INK2, lw=0.6)
            v = float(v50[v50.feature == f].value.iloc[0]); ax.plot([50000], [v], "o", color=MODEL, ms=3)
            import matplotlib.patheffects as pe
            span = np.nanmax(s.value) - np.nanmin(s.value); up = s.value.iloc[-1] < s.value.iloc[0]
            ax.annotate(num(v), (50000, v), xytext=(-34, -13) if up else (5, -13), textcoords="offset points", fontsize=TICK,
                        path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
            ax.set_title(f"({chr(97 + k)}) " + {"Cost above 30 % of income": "Cost above 30 %", "Built in the last five years": "Built in last 5 yrs", "Mobile home or other": "Mobile home",
                                                 "ln monthly housing cost": "Log housing cost", "Single-family attached": "Attached house", "Multifamily 2-4 units": "Multifamily 2-4",
                                                 "Multifamily 5+ units": "Multifamily 5+"}.get(f, f), loc="left")
            _xaxis(ax, label=k >= 6)
            if k % 3 == 0: ax.set_ylabel({0: "Effect on utility\n(per unit)", 3: "Effect on utility\n(per unit)", 6: "Effect on utility\n(vs detached house)"}[k])
            ax.grid(axis="y", color=GRID, lw=0.4)
    else:
        fig = _fig(fig, 3.0); ax = fig.subplots(1, 1)
        for k, (blk, f, _) in enumerate(E["rows"]):
            s = t[t.feature == f]; c = CAT[k]
            if s.se.notna().all(): ax.fill_between(s.column, s.value - 1.96 * s.se, s.value + 1.96 * s.se, color=c, alpha=0.18, lw=0)
            ax.plot(s.column, s.value, color=c, lw=1.3, label=f)
            v = float(v50[v50.feature == f].value.iloc[0]); ax.plot([50000], [v], "o", color=c, ms=3)
            ax.annotate(num(v), (50000, v), xytext=(-24, 0), textcoords="offset points", fontsize=TICK, va="center")
        ax.axhline(0, color=INK2, lw=0.6); _xaxis(ax); ax.set_ylabel("Effect of log dwelling density\non utility")
        ax.set_title("(a) Log dwelling density of the PUMA, by household type", loc="left"); ax.grid(axis="y", color=GRID, lw=0.4)
        ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    return fig


def group_effect_figure(folder, b, V, fig=None):
    E = RD.EFFECTS[folder]; t = RD.effects(folder, b, V); feats = list(dict.fromkeys(t.feature))
    fig = _fig(fig, 2.4); axs = np.atleast_1d(fig.subplots(1, len(feats)))
    for k, (ax, f) in enumerate(zip(axs, feats)):
        s = t[t.feature == f]; x = np.arange(len(s))
        ax.errorbar(x, s.value, yerr=None if s.se.isna().all() else 1.96 * s.se, fmt="o", ms=3.5, color=MODEL, elinewidth=1.1, capsize=0)
        ax.axhline(0, color=INK2, lw=0.6); ax.set_xticks(x); ax.set_xticklabels(s.column, rotation=0); ax.set_xlabel("Household income"); ax.set_xlim(-0.6, len(s) - 0.4)
        ax.set_title(f"({chr(97 + k)}) {dl(f)}", loc="left"); ax.grid(axis="y", color=GRID, lw=0.4)
        if k == 0: ax.set_ylabel("Coefficient for the group")
    return fig


# ------------------------------------------------------------------------------------------------ observed against model
def obs_model_figure(panels, fig=None, h=2.6):
    """panels: list of (title, DataFrame index=category, columns observed, model; xlabel; ylabel)"""
    fig = _fig(fig, h); axs = np.atleast_1d(fig.subplots(1, len(panels), gridspec_kw={"width_ratios": [max(2, len(p[1])) for p in panels]}))
    for k, (ax, (title, t, xl, yl)) in enumerate(zip(axs, panels)):
        x = np.arange(len(t)); w = 0.38
        ax.bar(x - w / 2, t.observed, w, color=OBS, label="Observed"); ax.bar(x + w / 2, t.model, w, color=MODEL, label="Model")
        ax.set_xticks(x); ax.set_xticklabels(t.index, rotation=0 if max(len(str(i)) for i in t.index) * len(t) < 30 else 45, ha="center" if max(len(str(i)) for i in t.index) * len(t) < 30 else "right")
        ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(f"({chr(97 + k)}) {title}", loc="left"); ax.grid(axis="y", color=GRID, lw=0.4)
        ax.set_ylim(0, max(t.observed.max(), t.model.max()) * 1.25)
    fig.legend(*axs[0].get_legend_handles_labels(), frameon=False, loc="outside lower center", ncol=2)
    return fig


# ------------------------------------------------------------------------------------------------ hold-out panels of the SILO models (shared by PDF and notebooks)
def dwelling_holdout_panels(H, P):
    """H: hold-out dwelling table; P: probabilities of the 30 alternatives (columns '0'..'29' or 0..29)"""
    J = [c for c in P.columns]; TY = {"SFD": "Detached", "SFA": "Attached", "MF234": "MF 2-4", "MF5plus": "MF 5+", "MH": "Mobile"}
    typ = np.stack([H[f"type_{j}"].values for j in J], 1); pm = P[J].values
    obs_t = H.type_0.value_counts(normalize=True).reindex(list(TY)).fillna(0) * 100
    mod_t = pd.Series({t: (pm * (typ == t)).sum() for t in TY}) / len(H) * 100
    g = pd.cut(H.income_2016usd, [-np.inf, 40000, 75000, 125000, np.inf], labels=["<$40k", "$40-75k", "$75-125k", "$125k+"])
    mf = np.isin(typ, ["MF234", "MF5plus"]); cost = np.stack([H[f"cost_{j}"].values for j in J], 1)
    t2 = pd.DataFrame({"observed": 100 * pd.Series(np.isin(H.type_0, ["MF234", "MF5plus"])).groupby(g.values, observed=False).mean(),
                       "model": 100 * pd.Series((pm * mf).sum(1)).groupby(g.values, observed=False).mean()})
    t3 = pd.DataFrame({"observed": pd.Series(H.cost_0.values).groupby(g.values, observed=False).mean(),
                       "model": pd.Series((pm * cost).sum(1)).groupby(g.values, observed=False).mean()})
    return [("Type", pd.DataFrame({"observed": obs_t.values, "model": mod_t.values}, index=list(TY.values())), "", "Hold-out movers (%)"),
            ("Multifamily", t2, "", "Movers in multifamily (%)"), ("Monthly cost", t3, "", "Mean monthly cost (2016 $)")]


def cars_holdout_panels(H, P):
    P = P.copy(); P.columns = ["0", "1", "2", "3+"]
    O = pd.get_dummies(H.cars.map({0: "0", 1: "1", 2: "2", 3: "3+"})).reindex(columns=P.columns, fill_value=0).astype(float)
    wk = H.workers.clip(upper=3).astype(int).astype(str).replace({"3": "3+"}).values
    dw = np.select([H.sfd == 1, H.multifamily == 1], ["Detached", "Multifamily"], "Other")
    return [("All", pd.DataFrame({"observed": 100 * O.mean(), "model": 100 * P.mean()}), "Cars", "Hold-out households (%)"),
            ("By workers", pd.DataFrame({"observed": 100 * O["0"].groupby(wk).mean(), "model": 100 * P["0"].groupby(wk).mean()}), "Workers", "Without a car (%)"),
            ("By dwelling", pd.DataFrame({"observed": 100 * O["0"].groupby(dw).mean(), "model": 100 * P["0"].groupby(dw).mean()}), "", "Without a car (%)")]


# ------------------------------------------------------------------------------------------------ sampled-alternatives check
SS_LABEL = {"over30": "Cost above 30 %", "over30_x_lninc": "  x ln income", "lncost": "ln housing cost", "lncost_x_lninc": "  x ln income",
            "bed_short": "Bedroom shortfall", "bed_short_x_lninc": "  x ln income", "bed_extra": "Bedroom excess", "bed_extra_x_lninc": "  x ln income",
            "new5": "Built in last 5 years", "new5_x_lninc": "  x ln income", "SFA": "Attached house", "SFA_x_lninc": "  x ln income",
            "MF234": "Multifamily 2-4", "MF234_x_lninc": "  x ln income", "MF5plus": "Multifamily 5+", "MF5plus_x_lninc": "  x ln income",
            "MH": "Mobile home", "MH_x_lninc": "  x ln income", "lnM": "ln market size", "d2": "Car time 20-60 min", "d3": "Car time over 60 min",
            "same": "Inside previous migration area", "adjacent": "Bordering it", "same_state": "Same state", "commute_log": "Commute",
            "crime_x_child": "Crime x children", "lnddens": "ln dwelling density", "own_race": "Own-race share", "lnddens_x_single": "ln density x single",
            "lnddens_x_young35": "ln density x under 35", "lnddens_x_lninc": "ln density x ln income", "core_share": "Core-city share"}


def sample_size_figure(coef_csv, level, fig=None, title=None):
    """change of each coefficient against the 30-alternative estimate, in its robust s.e.; band +-1 s.e."""
    c = pd.read_csv(coef_csv); c = c[(c.level == level) & (c.case != "J30")]
    params = list(dict.fromkeys(c.param)); cases = list(dict.fromkeys(c.case))
    lab = {"J30, second draw": "30, second draw", "J60": "60 alternatives", "J100": "100 alternatives"}
    fig = _fig(fig, 0.17 * len(params) + 1.1); ax = fig.subplots(1, 1); y = {p: i for i, p in enumerate(params)}
    ax.axvspan(-1, 1, color="#eeede8", lw=0, zorder=0); ax.axvline(0, color=INK2, lw=0.6)
    for k, cs in enumerate(cases):
        g = c[c.case == cs]
        ax.scatter(g.diff_in_se, [y[p] + (k - 1) * 0.18 for p in g.param], s=12, marker=["o", "^", "s"][k % 3], color=CAT[k], label=lab.get(cs, cs), zorder=3)
    ax.set_yticks(range(len(params))); ax.set_yticklabels([dl(SS_LABEL.get(p, p)) for p in params]); ax.set_ylim(len(params) - 0.5, -0.5)
    lim = max(1.2, float(np.ceil(c.diff_in_se.abs().max() * 10) / 10) + 0.1); ax.set_xlim(-lim, lim)
    ax.set_xlabel("Change against 30 alternatives (robust s.e.)"); ax.tick_params(axis="y", length=0)
    ax.set_title(title or f"(a) {'Dwelling' if level == 'dwelling' else 'PUMA'} level", loc="left")
    fig.legend(*ax.get_legend_handles_labels(), frameon=False, loc="outside lower center", ncol=3)
    return fig
