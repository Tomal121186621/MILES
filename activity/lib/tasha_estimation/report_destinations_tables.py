#!/usr/bin/env python3
"""Tables and figures of the short destination-model report (5_reports/estimation_manual/destinations_short/), 2026-10-29;
outings (OTHER_wbs) and the activity-model table updated 2026-11-03.  python3 activity/lib/tasha_estimation/report_destinations_tables.py [records estimates collin seconddraw heldout roorda outing]
TAZ re-estimate with the specification of record (results/*_taz.csv; the rows of coef_tasha_taz2)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, shutil, sys
import numpy as np
import pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/tasha_estimation"   # data folder; CODE = this folder
from compare_dc_taz import tex, lab, RES, FIG, DISC          # noqa: E402
V = os.path.dirname(os.path.dirname(HERE)); OUT = f"{V}/5_reports/estimation_manual/destinations_short"
T = f"{OUT}/tables"; F = f"{OUT}/figures"; os.makedirs(T, exist_ok=True); os.makedirs(F, exist_ok=True)
PN = {"SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompany", "OTHER": "Other errands"}
PSEG = [f"{p}_primary" for p in DISC]; SSEG = [f"{p}_stop" for p in DISC]


def n(x, d=3):
    if x is None or not np.isfinite(x): return ""
    s = f"{x:,.{d}f}"; return s.replace("-", "$-$")


def w(name, body): open(f"{T}/{name}.tex", "w").write(body + "\n")


def tab(spec, head, rows, size="\\footnotesize"):
    return f"{size}\\setlength{{\\tabcolsep}}{{3pt}}\\begin{{tabular}}{{{spec}}}\\toprule\n" + " & ".join(head) + " \\\\ \\midrule\n" + "\n".join(r if r.startswith("\\") else r + " \\\\" for r in rows) + "\n\\bottomrule\\end{tabular}"


def label(p):
    p2 = {"intra_a": "stop in the zone of the previous location", "intra_b": "stop in the zone of the next anchor", "lnd_multi": "ln(distance) × tour with stops",
          "ls": "mode-choice logsum (detour)", "cgt": "car generalized time, min"}.get(p)
    if p2: return tex(p2)
    s = lab(p)
    if p.startswith("dt_") or p.startswith("lndt_"): s = s.replace("detour", "detour")
    return tex(s)


def records():
    S = pd.read_csv(f"{RES}/dc_taz_sources.csv"); rows = []
    for kind in ["primary", "stop"]:
        for p in DISC:
            e = S[(S.half == "estimation") & (S.kind == kind) & (S.purpose == p)].iloc[0]; v = S[(S.half == "validation") & (S.kind == kind) & (S.purpose == p)].iloc[0]
            tr = e.get("dloc_src:tract split", 0) + (e.get("dloc_src:tract point", 0) if np.isfinite(e.get("dloc_src:tract point", np.nan)) else 0)
            rows.append(" & ".join([f"{PN[p]}, {'main activity' if kind == 'primary' else 'stop'}", f"{int(e.N_taz):,}", f"{int(v.N_taz):,}", n(100 * e["dloc_src:tpb"], 1), n(100 * e["dloc_src:bmc"], 1), n(100 * tr, 1),
                                    n(100 * e.dest_split, 1), n(100 * e.dest_changed, 1)]))
    w("records", tab("@{}lrrrrrrr@{}", ["Model", "\\shortstack{$N$\\\\estimation}", "\\shortstack{$N$\\\\hold-out}", "\\shortstack{TPB\\\\\\%}", "\\shortstack{BMC\\\\\\%}", "\\shortstack{tract\\\\\\%}",
                                         "\\shortstack{split\\\\\\%}", "\\shortstack{other zone than\\\\tract point, \\%}"], rows))


def estimates():
    for kind, segs, f, tests, ll in [("primary", PSEG, "cx_estimates_taz.csv", "cx_tests_taz.csv", "LL_FX"), ("stop", SSEG, "seq_estimates_taz.csv", "seq_tests_taz.csv", "LL")]:
        E = pd.read_csv(f"{RES}/{f}"); Ts = pd.read_csv(f"{RES}/{tests}").set_index("segment")
        params = list(dict.fromkeys(p for s in segs for p in E[E.segment == s].param))
        order = [p for p in params if not p.startswith("theta_") and p != "mu_size"] + [p for p in params if p.startswith("theta_")] + ["mu_size"]
        rows = []
        for p in order:
            cells = [label(p)]
            for s in segs:
                q = E[(E.segment == s) & (E.param == p)]
                cells.append(f"{n(q.value.iloc[0])} ({n(q.rob_se.iloc[0])})" if len(q) else "")
            rows.append(" & ".join(cells))
        rows.append("\\midrule")
        for key, fn in [("Observations", lambda t: f"{int(t.N):,}"), ("Parameters", lambda t: str(int(t.K))), ("LL(0)", lambda t: n(t.LL0, 1)), ("LL", lambda t: n(t[ll], 1)),
                        ("$\\rho^2$", lambda t: n(1 - t[ll] / t.LL0, 3)), ("BIC", lambda t: n((t.BIC_FX if kind == "primary" else t.BIC), 1))]:
            rows.append(" & ".join([key] + [fn(Ts.loc[s]) for s in segs]))
        w(f"est_{kind}", tab("@{}L{0.31\\linewidth}rrrr@{}", ["Variable"] + [PN[s.split('_')[0]] for s in segs], rows, size="\\scriptsize"))


FL = {"inc0": "inc<50k", "inc2": "inc 100k+", "car0": "no car", "car1": "cars<drivers", "child": "children", "kid": "age<18", "senior": "65+", "worker": "worker",
      "am": "AM", "pm": "PM", "ev": "evening", "nonauto": "not car", "worktour": "work tour", "inbound": "inbound", "multi": "tour w. stops"}


def short(p):
    d = {"intra": "same zone", "intra_a": "zone of prev.", "intra_b": "zone of next", "bc": "Baltimore City", "dcz": "DC", "va": "Virginia", "othst": "DE/PA/WV",
         "cbd": "CBD", "lnretden": "retail density", "mix": "land-use mix", "xcounty": "other county", "xstate": "other state", "cgt": "car gen. time",
         "ls": "logsum", "ln_size": "ln size"}
    if p in d: return d[p]
    if p.startswith(("d_", "dt_")):
        _, lo, hi = p.split("_"); return f"{'dist.' if p.startswith('d_') else 'detour'} {lo}-{'' if hi == 'inf' else hi}{'+' if hi == 'inf' else ''} km".replace("- km", "+ km").replace("-+", "+")
    if p.startswith(("lnd_", "lndt_")): return "ln d × " + FL.get(p.split("_", 1)[1], p)
    return p


def heat(s, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("bgr", ["#2a78d6", "#f0efec", "#e34948"]); cmap.set_bad("#d9d8d4")
    R = pd.read_csv(f"{RES}/collin_{s}_taz.csv", index_col=0); Vf = pd.read_csv(f"{RES}/vif_{s}_taz.csv", index_col=0).iloc[:, 0]
    nm = list(R.index); A = R.values; k = len(nm); A_ = A.copy(); np.fill_diagonal(A_, np.nan)
    fig, ax = plt.subplots(figsize=(0.3 * k + 2.6, 0.3 * k + 1.4), dpi=200); im = ax.imshow(A_, cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(k)); ax.set_yticks(range(k)); ax.set_xticklabels([short(x) for x in nm], rotation=90, fontsize=6.5); ax.set_yticklabels([f"{short(x)} ({Vf[x]:.1f})" for x in nm], fontsize=6.5)
    for i in range(k):
        for j in range(k):
            if i != j and abs(A[i, j]) > 0.85:
                ax.text(j, i, f"{A[i, j]:.2f}", ha="center", va="center", fontsize=4.8, color="#1a1a19"); ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=False, ec="#1a1a19", lw=1.0, zorder=3))
    ax.set_xticks(np.arange(-.5, k, 1), minor=True); ax.set_yticks(np.arange(-.5, k, 1), minor=True); ax.grid(which="minor", color="#fcfcfb", lw=.6); ax.tick_params(which="minor", length=0)
    for sp in ax.spines.values(): sp.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=.035, pad=.02); cb.ax.tick_params(labelsize=6); cb.outline.set_visible(False); cb.set_label("within-choice-set correlation", fontsize=6.5)
    fig.savefig(path, facecolor="#fcfcfb", bbox_inches="tight"); plt.close(fig)


def collin():
    rows = []
    for s in PSEG + SSEG:
        R = pd.read_csv(f"{RES}/collin_{s}_taz.csv", index_col=0); Vf = pd.read_csv(f"{RES}/vif_{s}_taz.csv", index_col=0).iloc[:, 0]
        A = R.values; k = len(A); nm = list(R.index)
        pairs = [f"{tex(short(nm[i]))} -- {tex(short(nm[j]))} {A[i, j]:.2f}".replace("-0", "$-$0") for i in range(k) for j in range(i + 1, k) if abs(A[i, j]) > 0.85]
        top = Vf.drop("ln_size").sort_values(ascending=False)
        rows.append(" & ".join([f"{PN[s.split('_')[0]]}, {'main' if s.endswith('primary') else 'stop'}", f"{tex(short(top.index[0]))} {top.iloc[0]:.1f}", str(int((top > 10).sum())), "; ".join(pairs) or "none"]))
    w("collin", tab("@{}lllL{0.5\\linewidth}@{}", ["Model", "largest VIF", "VIF $>10$", "pairs with $|r|>0.85$"], rows, size="\\scriptsize"))
    for s, tag in [("SHOPPING_primary", "a"), ("OTHER_stop", "b")]: heat(s, f"{F}/fig_within_corr_{tag}.png")


def seconddraw():
    D = pd.read_csv(f"{RES}/seconddraw_taz.csv"); rows = []
    for _, r in D[D.param.isin(["cgt", "ls"])].iterrows():
        rows.append(" & ".join([f"{PN[r.segment.split('_')[0]]}, {'main' if r.segment.endswith('primary') else 'stop'}", label(r.param), n(r.draw1, 4), n(r.se1, 4), n(r.draw2, 4), n(r.diff_over_se, 2)]))
    rows.append("\\midrule"); rows.append(f"All coefficients & & & & median $|\\Delta|$/s.e. {D.diff_over_se.abs().median():.2f} & max {D.diff_over_se.abs().max():.2f}")
    w("seconddraw", tab("@{}llrrrr@{}", ["Model", "Term", "draw 1", "s.e.", "draw 2", "$\\Delta$/s.e."], rows))


def heldout():
    rows = []
    for kind, f, g in [("primary", "cx_heldout_taz.csv", "tour"), ("stop", "seq_heldout_taz.csv", "position")]:
        H = pd.read_csv(f"{RES}/{f}"); H = H[(H.half == "validation") & (H.model == "new (TAZ)")]
        if kind == "stop": H = H.rename(columns={"km_leg_obs": "km_obs", "km_leg_pred": "km_pred"})
        for p in DISC:
            h = H[H.segment == f"{p}_{kind}"].set_index(g)
            a, b = (["simple", "with stops"] if kind == "primary" else ["out", "in"])
            rows.append(" & ".join([f"{PN[p]}, {'main' if kind == 'primary' else 'stop'}", f"{int(h.N['all']):,}", n(h.LL_per_obs["all"], 3), f"{n(h.km_obs[a], 1)} / {n(h.km_pred[a], 1)}",
                                    f"{n(h.km_obs[b], 1)} / {n(h.km_pred[b], 1)}", f"{n(h.km_obs['all'], 1)} / {n(h.km_pred['all'], 1)}", n(h.KS["all"], 3)]))
    w("heldout", tab("@{}lrrcccr@{}", ["Model", "$N$", "LL/obs.", "\\shortstack{simple tour / outbound\\\\km obs. / pred.}", "\\shortstack{with stops / inbound\\\\km obs. / pred.}",
                                        "\\shortstack{all\\\\km obs. / pred.}", "KS"], rows, size="\\scriptsize"))


def roorda():
    C = pd.read_csv(f"{V}/data/abit_roorda_compare_taz.csv"); B = pd.read_csv(f"{V}/data/abit_roorda_bench_compare_behavnow_rec1029.csv"); T_ = pd.read_csv(f"{V}/data/abit_roorda_tables.csv"); T_ = T_[T_.variant == "base"]; rows = []
    types = ["WORK", "SCHOOL", "SHOPPING", "OTHER", "HOME", "ALL"]
    for k in ["verification", "validation"]:
        # model of record after the 2 November 2026 re-estimation (runs *_reest); the earlier runs (*_rec1029) as 'before'
        # model of record (runs *_sched); rows 'without outings': the same chain without the outing components (runs *_rail)
        for sfx, lab in [("_sched", ""), ("_rail", ", without outings")]:
            g = T_[T_.setting == f"{k}{sfx}"].set_index("type")
            rows.append(" & ".join([{"verification": "Estimation half", "validation": "Hold-out half"}[k] + lab, "activities"] + [n(g.diff_pct[x], 1) for x in types]))
            rows.append(" & ".join(["", "distance"] + [n(g.diff_km_pct[x], 1) for x in types]))
    w("roorda", tab("@{}llrrrrrr@{}", ["Population", "Deviation, \\%", "Work", "School", "Shopping", "Other", "Return home", "All"], rows))
    rows = []
    for k in ["verification", "validation"]:
        cur = C[(C.setting == k) & (C.set == "behavnow")].iloc[0]; taz = C[(C.setting == k) & (C.set == "rec1029")].iloc[0]
        bt = B[(B.benchmark == "TAZ")].set_index("setting")
        rows.append(" & ".join([{"verification": "Estimation half", "validation": "Hold-out half"}[k], n(cur.act_ALL, 1), n(taz.act_ALL, 1), n(cur.km_ALL, 1), n(taz.km_ALL, 1),
                                n(bt.km_ALL[f"{k}_behavnow"], 1), n(bt.km_ALL[f"{k}_rec1029"], 1), f"{n(cur.km_SHOPPING, 1)} / {n(taz.km_SHOPPING, 1)}", f"{n(cur.km_OTHER, 1)} / {n(taz.km_OTHER, 1)}"]))
    w("sensitivity", tab("@{}lrrrrrrcc@{}", ["Population", "\\shortstack{activities\\\\tract}", "\\shortstack{activities\\\\TAZ}", "\\shortstack{km, tract\\\\benchmark: tract}",
                                              "\\shortstack{km, TAZ\\\\bm.: tract}", "\\shortstack{km, tract\\\\bm.: TAZ}", "\\shortstack{km, TAZ\\\\bm.: TAZ}", "\\shortstack{shopping km\\\\tract / TAZ}",
                                              "\\shortstack{other km\\\\tract / TAZ}"], rows, size="\\scriptsize"))


def outing():
    """destination of the first stop of an outing from the usual workplace (segment OTHER_wbs; estimate_subtour_dest.py)"""
    E = pd.read_csv(f"{RES}/wbs_dest_estimates.csv"); S = pd.read_csv(f"{RES}/wbs_dest_stats.csv").iloc[0]
    Q = pd.read_csv(f"{RES}/wbs_dest_search.csv")
    order = [p for p in E.param if not p.startswith("theta_") and p != "mu_size"] + [p for p in E.param if p.startswith("theta_")] + ["mu_size"]
    rows = []
    for p in order:
        r = E[E.param == p].iloc[0]; rows.append(" & ".join([label(p), n(r.value), n(r.rob_se), n(r.rob_t, 2)]))
    rows.append("\\midrule")
    K, N, LL = int(S.K), int(S.N), S.LL
    for key, v in [("Observations", f"{N:,}"), ("Parameters", str(K)), ("LL(0)", n(S.LL0, 1)), ("LL(same-zone constant)", n(S.LLc, 1)), ("LL", n(LL, 1)),
                   ("$\\rho^2$", n(1 - LL / S.LL0, 3)), ("$\\bar\\rho^2$", n(1 - (LL - K) / S.LL0, 3)), ("AIC", n(S.AIC, 1)), ("BIC", n(S.BIC, 1))]:
        rows.append(" & ".join([key, v, "", ""]))
    w("est_outing", tab("@{}L{0.42\\linewidth}rrr@{}", ["Variable", "Estimate", "Robust s.e.", "Robust $t$"], rows))
    rows = []
    for _, r in Q.iterrows():
        lr = "" if not np.isfinite(r.LR) else (n(abs(r.LR), 1)); df = "" if not np.isfinite(r.LR_df) else str(int(abs(r.LR_df)))
        pv = "" if not np.isfinite(r.LR_p) else ("$<$0.001" if r.LR_p < 0.001 else n(r.LR_p, 3))
        vs = "" if not isinstance(r.LR_vs, str) else r.LR_vs
        rows.append(" & ".join([r.model, tex(r.note.replace(" x ", " × ")), str(int(r.K)), n(r.LL, 1), n(r.AIC, 1), n(r.BIC, 1), n(r.rho2_adj, 3), vs, lr, df, pv]))
    w("search_outing", tab("@{}llrrrrrlrrr@{}", ["Step", "Content", "$K$", "LL", "AIC", "BIC", "$\\bar\\rho^2$", "vs.", "LR", "df", "$p$"], rows, size="\\scriptsize"))
    H = pd.read_csv(f"{RES}/wbs_dest_heldout.csv"); rows = []
    for _, r in H.iterrows():
        rows.append(" & ".join([{"estimation": "Estimation half", "validation": "Hold-out half"}[r.half], f"{int(r.N):,}", n(r.LL, 1), n(r.LL_per_obs, 3), n(r.km_obs, 2), n(r.km_pred, 2)]))
    w("heldout_outing", tab("@{}lrrrrr@{}", ["Population", "$N$", "LL", "LL/obs.", "km obs.", "km pred."], rows))


if __name__ == "__main__":
    import sys as _s
    fns = {"records": records, "estimates": estimates, "collin": collin, "seconddraw": seconddraw, "heldout": heldout, "roorda": roorda, "outing": outing}
    for k in (_s.argv[1:] or list(fns)): fns[k]()
    print("ok", T)
