#!/usr/bin/env python3
"""Revised PUMA level (2026-11-19): r20 + the smallest block set chosen on the estimation half in r22_city_bias.py (lowest BIC among
the blocks with expected signs): ln dwelling density x single-person household, x oldest member under 35, x ln income, and the
core-city share of the PUMA (dwellings in DC or Baltimore City).  Dwelling level, data, draws and market size as r20.
Writes r22_fit.csv, r22_coef.csv (change vs r20 in r20 robust s.e.), r22_vif.csv, r22_county_before_after.csv (both halves),
r22_holdout_puma.csv and the hold-out map r22_holdout_map.pdf / .png of the adopted model (observed, model, model minus observed by
PUMA; counties with the largest differences).  Redraw only: REDRAW=1."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/residential"; sys.path.insert(0, CODE); sys.path.insert(0, os.path.dirname(CODE))   # HERE: results of this step (data); CODE: this folder
import r22_city_bias as B   # noqa: E402  (sets the r20 crosswalk; imports r19_final)
F, R = B.F, B.R
from mnl import MNL          # noqa: E402
NEW = ["dens2", "core", "dens_inc"]
LAB = {"lnddens_x_single": "ln dwelling density x single-person household", "lnddens_x_young": "ln dwelling density x oldest member under 35",
       "core": "core-city share of the PUMA (DC, Baltimore City)", "lnddens_x_lninc": "ln dwelling density x ln income"}


def main():
    D, G = B.designs(); A = B.puma_attrs(G); S = B.split_county(G); N = len(D[0]["w"])
    r0 = B.fit("r20", ["base"], D, A, S); r1 = B.fit("r22", NEW, D, A, S)
    m0, m1 = r0["m"], r1["m"]
    fit = [dict(level="PUMA (inclusive value at 1)", model=lab, N=N, K=m.k, LL0=float(np.log(1.0 / D[0]["av"].sum(1)).sum()), LL=m.ll, BIC=m.k * np.log(N) - 2 * m.ll,
                validation_N=len(D[1]["w"]), validation_LL=r["vll"]) for lab, m, r in (("r20", m0, r0), ("r22", m1, r1))]
    pd.DataFrame(fit).to_csv(f"{HERE}/r22_fit.csv", index=False)
    c0 = dict(zip(r0["names"], zip(m0.b, m0.rse)))
    co = pd.DataFrame([dict(level="PUMA", param=n, coef=b, robust_se=s, t=b / s, r20_coef=c0.get(n, (np.nan,))[0],
                            change_in_r20_se=(b - c0[n][0]) / c0[n][1] if n in c0 else np.nan, label=LAB.get(n, F.LABEL.get(n, n)))
                       for n, b, s in zip(r1["names"], m1.b, m1.rse)])
    co.to_csv(f"{HERE}/r22_coef.csv", index=False)
    pd.DataFrame([dict(level="PUMA", variable=k, VIF=v) for k, v in r1["vif"].items()]).to_csv(f"{HERE}/r22_vif.csv", index=False)
    cv = m1.cov_robust; pd.DataFrame(cv / np.sqrt(np.outer(np.diag(cv), np.diag(cv))), index=r1["names"], columns=r1["names"]).round(3).to_csv(f"{HERE}/r22_est_corr_PUMA.csv")
    rows = []
    for half in ("estimation", "holdout"):
        a = B.county(*r0["res"][half], S); b = B.county(*r1["res"][half], S)
        rows.append(pd.DataFrame({"half": half, "county": a.index, "observed_pct": a.observed_pct.values, "r20_model_pct": a.model_pct.values, "r20_diff_pp": a.diff_pp.values,
                                  "r22_model_pct": b.model_pct.values, "r22_diff_pp": b.diff_pp.values}))
    cb = pd.concat(rows); cb.to_csv(f"{HERE}/r22_county_before_after.csv", index=False)
    po, p0 = r0["res"]["holdout"]; _, p1 = r1["res"]["holdout"]
    hp = pd.DataFrame({"puma7": po.index, "observed_pct": po.values, "r20_model_pct": p0.values, "r22_model_pct": p1.values})
    hp["r20_diff_pp"] = hp.r20_model_pct - hp.observed_pct; hp["r22_diff_pp"] = hp.r22_model_pct - hp.observed_pct
    hp.to_csv(f"{HERE}/r22_holdout_puma.csv", index=False)
    print(pd.DataFrame(fit).round(2).to_string(index=False)); print(co.round(4).to_string(index=False))
    for half in ("estimation", "holdout"):
        t = cb[cb.half == half]
        print(f"{half}: county MAD r20 {t.r20_diff_pp.abs().mean():.3f} -> r22 {t.r22_diff_pp.abs().mean():.3f}; "
              f"corr r20 {np.corrcoef(t.observed_pct, t.r20_model_pct)[0, 1]:.3f} -> r22 {np.corrcoef(t.observed_pct, t.r22_model_pct)[0, 1]:.3f}")
        print(t.reindex(t.r20_diff_pp.abs().sort_values(ascending=False).index).head(8).round(2).to_string(index=False))
    print(f"hold-out PUMA: r20 r {np.corrcoef(hp.observed_pct, hp.r20_model_pct)[0, 1]:.3f} MAD {hp.r20_diff_pp.abs().mean():.3f}; "
          f"r22 r {np.corrcoef(hp.observed_pct, hp.r22_model_pct)[0, 1]:.3f} MAD {hp.r22_diff_pp.abs().mean():.3f}")
    draw(hp, cb[cb.half == "holdout"], fit)


def draw(hp, cb, fit):
    """Hold-out map of the adopted model: observed | model | model minus observed by PUMA, and the counties with the largest
    differences (model and observed share).  Uses the adopted (r22) columns only."""
    import holdout_maps as HM
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, Normalize
    PS = HM.PS; G = HM.geometry(); g = G["pu"].join(hp.set_index("puma7"))
    bins = [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 6.0]; norm = BoundaryNorm(bins, PS.SEQ.N)
    lim = float(np.ceil(g.r22_diff_pp.abs().max() * 10) / 10); dn = Normalize(-lim, lim)
    ext = HM.bounds(HM.BW)
    fr = [f for f in fit if f["model"] == "r22"][0]; llpm = fr["validation_LL"] / fr["validation_N"]
    fig = PS.new_figure(4.6); SF = fig.subfigures(3, 1, height_ratios=[1, 0.82, 0.13])
    gt = SF[0].add_gridspec(2, 3, height_ratios=[1, 0.07])
    def mp(ax, col, cmap, nm, title):
        ax.set_axis_off(); ax.set_aspect("equal"); g.plot(ax=ax, column=col, cmap=cmap, norm=nm, edgecolor="white", linewidth=0.35)
        G["lines"].plot(ax=ax, color=PS.INK2, linewidth=0.35); ax.set_xlim(ext[0], ext[2]); ax.set_ylim(ext[1], ext[3]); ax.set_title(title, fontsize=PS.FONT, loc="left")
    def cbar(ax, cmap, nm, seq):
        cb_ = fig.colorbar(plt.cm.ScalarMappable(norm=nm, cmap=cmap), cax=ax, orientation="horizontal"); cb_.outline.set_linewidth(0.3)
        cb_.ax.tick_params(labelsize=PS.TICK, length=2, width=0.4)
        if seq: cb_.set_ticks(bins); cb_.set_ticklabels([f"{b:g}" if b in (0, 0.5, 1, 2, 6) else "" for b in bins])
        else: t = np.round(np.linspace(-lim, lim, 3), 2); cb_.set_ticks(t); cb_.set_ticklabels([(f"{x:+g}" if x else "0").replace("-", "\u2212") for x in t])
    r = np.corrcoef(hp.observed_pct, hp.r22_model_pct)[0, 1]
    for j, (col, title, cmap, nm, seq) in enumerate([("observed_pct", "(a) Observed\n(%)", PS.SEQ, norm, True),
                                                     ("r22_model_pct", "(b) Model\n(%)", PS.SEQ, norm, True),
                                                     ("r22_diff_pp", "(c) Model minus\nobserved (pp)", PS.DIV, dn, False)]):
        ax = SF[0].add_subplot(gt[0, j]); mp(ax, col, cmap, nm, title)
        if j == 1: ax.text(0.0, -0.02, f"Correlation {r:.2f}", transform=ax.transAxes, ha="left", va="top", fontsize=PS.TICK, color=PS.INK)
        if j == 2: ax.text(0.0, -0.02, f"Mean absolute difference {hp.r22_diff_pp.abs().mean():.2f} pp", transform=ax.transAxes, ha="left", va="top", fontsize=PS.TICK, color=PS.INK)
        cbar(SF[0].add_subplot(gt[1, j]), cmap, nm, seq)
    # (d) counties with the largest differences, hold-out half
    gb = SF[1].add_gridspec(1, 3, width_ratios=[0.35, 1, 0.25]); ax = SF[1].add_subplot(gb[0, 1])
    top = cb.reindex(cb.r22_diff_pp.abs().sort_values(ascending=False).index).head(8).iloc[::-1]
    names = pd.read_csv(f"{HM.V}/2_silo/input/zoneSystem.csv").drop_duplicates("COUNTYFIPS").set_index("COUNTYFIPS").JUR_NAME
    lab = [{11001: "Washington DC", 24510: "Baltimore City", 24005: "Baltimore County", 51059: "Fairfax", 51919: "Fairfax"}.get(c, str(names.get(c, c)).split(",")[0].split("/")[0].replace(" County", "").strip()) for c in top.county]
    y = np.arange(len(top))
    ax.hlines(y, top.observed_pct, top.r22_model_pct, color=PS.GRID, lw=1.2, zorder=1)
    ax.scatter(top.observed_pct, y, s=18, color=PS.OBSERVED, marker="o", label="Observed", zorder=3)
    ax.scatter(top.r22_model_pct, y, s=18, color=PS.MODEL, marker="o", label="Model", zorder=3)
    for yi, (m, d) in enumerate(zip(top.r22_model_pct, top.r22_diff_pp)):
        ax.text(max(m, top.observed_pct.iloc[yi]) + 0.25, yi, f"{d:+.1f}".replace("-", "\u2212"), va="center", ha="left", fontsize=PS.TICK, color=PS.INK2)
    ax.set_yticks(y); ax.set_yticklabels(lab); ax.set_xlabel("Share of hold-out movers (%)")
    ax.set_xlim(0, max(top.observed_pct.max(), top.r22_model_pct.max()) + 1.6)
    ax.set_title("(d) Counties with the largest differences\n(labels: model minus observed, pp)", fontsize=PS.FONT, loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), ncol=1, fontsize=PS.TICK, handletextpad=0.2, frameon=False); ax.grid(axis="y", visible=False)
    SF[2].text(0.0, 0.0, "Hold-out movers, Baltimore\u2013Washington part of the model area; areas: Public Use Microdata\nAreas; lines: counties. "
               f"Model: sum of the predicted probabilities; hold-out log-likelihood per mover {llpm:.3f}.".replace("-", "\u2212"),
               ha="left", va="bottom", fontsize=PS.TICK, color=PS.INK2)
    PS.check(fig, "resloc_holdout_map"); fig.savefig(f"{HERE}/r22_holdout_map.pdf"); fig.savefig(f"{HERE}/r22_holdout_map.png", dpi=200); plt.close(fig)
    print("wrote r22_holdout_map.pdf / .png")


if __name__ == "__main__":
    if os.environ.get("REDRAW") == "1":
        cb = pd.read_csv(f"{HERE}/r22_county_before_after.csv")
        draw(pd.read_csv(f"{HERE}/r22_holdout_puma.csv"), cb[cb.half == "holdout"], pd.read_csv(f"{HERE}/r22_fit.csv").to_dict("records"))
    else:
        main()
