#!/usr/bin/env python3
"""Summary tables and figures of the residential location estimation.
  tables/zone_shares_puma.csv      RTS halves: observed vs predicted shares of households by PUMA within the six Baltimore-region
                                   counties, all and by income group (full choice sets, RTS weights)
  tables/wtp.csv                   willingness to pay: $ per month per minute of one worker's commute, by income group
                                   (zone model commute term / dwelling model cost derivative, evaluated at the group means)
  figures/fig_resloc_region_shares.(pdf|png), fig_resloc_income_shares, fig_resloc_zone_puma, fig_resloc_elasticities
Figures follow reports/paperstyle.py (finish() refuses figures that break its rules)."""
import sys, json
import numpy as np, pandas as pd
from rc import *
sys.path.insert(0, f"{ORIOLE_HOME}/reports"); import paperstyle as ps

TAG = sys.argv[1] if len(sys.argv) > 1 else "prov"
BALT = {24003: "Anne Arundel", 24005: "Baltimore County", 24013: "Carroll", 24025: "Harford", 24027: "Howard", 24510: "Baltimore City"}
GN = {"LOW": "Below $20,000", "MEDIUM": "$20,000–40,000", "HIGH": "$40,000–60,000", "VERY_HIGH": "Above $60,000"}


def zone_shares():
    sh = pd.read_parquet(f"{WORK}/zone_predictions_{TAG}.parquet")
    z = pd.read_csv(ZONES)[["ZoneId", "PUMA_10", "Region"]].set_index("ZoneId")
    sh["puma"] = sh.zone.map(z.PUMA_10); sh["region"] = sh.zone.map(z.Region)
    sh = sh[sh.region.isin(BALT)]
    out = []
    for (samp, grp), g in pd.concat([sh.assign(grp="all"), sh.assign(grp=sh.inc_group)]).groupby(["sample", "grp"]):
        for r, gr in g.groupby("region"):
            o = (gr.obs * gr.w).groupby(gr.puma).sum(); p = (gr.p * gr.w).groupby(gr.puma).sum()
            for pu in o.index:
                out.append(dict(sample=samp, group=grp, county=BALT[r], puma=pu, obs=o[pu] / o.sum(), pred=p[pu] / p.sum(), n=int(gr[gr.obs > 0].shape[0])))
    d = pd.DataFrame(out); d.to_csv(f"{TAB}/zone_shares_puma.csv", index=False)
    s = d.assign(ad=(d.obs - d.pred).abs() * 100).groupby(["sample", "group"]).ad.agg(["mean", "max"]).round(2)
    s.to_csv(f"{TAB}/zone_shares_puma_summary.csv")
    print(s.to_string())
    return d


def wtp():
    zb = dict(zip(pd.read_csv(f"{WORK}/zone_names_{TAG}.csv").iloc[:, 0], np.load(f"{WORK}/zone_beta_{TAG}.npy")))
    db = pd.read_csv(f"{TAB}/dwelling_final_numpy.csv").set_index("parameter").estimate
    mv = pd.read_parquet(f"{WORK}/pums_movers_est.parquet"); mv = mv[mv.half == "estimation"]
    rows = []
    for g in INC_GROUPS:
        h = mv[mv.inc_group == g]
        inc = np.maximum(h.income, 5000); cost = np.maximum(h.cost, 100); b = np.minimum(12 * cost / inc, 3)
        slope = np.select([b < .3, b < .5], [db[f"bur_lo_{g}"], db[f"bur_mid_{g}"]], db[f"bur_hi_{g}"])
        dVdc = slope * 12 / inc + db[f"lncost_{g}"] / cost                 # per $ of monthly cost, each mover at its own dwelling
        t = 30.0; lninc = np.log(inc / 50000)
        dVdt = (zb["commute_log"] + zb["commute_log_x_inc"] * lninc) / (1 + t)
        w = dVdt / dVdc                                                     # $ per month per minute saved (both derivatives negative)
        rows.append(dict(group=g, mean_income=float(inc.mean()), mean_cost=float(cost.mean()), mean_burden=float(b.mean()),
                         dV_dcost_per_100usd=float(dVdc.mean() * 100), dV_dmin_at_30min=float(dVdt.mean()),
                         share_negative_cost_derivative=float((dVdc < 0).mean()),
                         wtp_usd_per_month_per_min_median=float(np.median(w[dVdc < 0])) if (dVdc < 0).any() else np.nan,
                         wtp_usd_per_month_per_min_at_means=float(dVdt.mean() / dVdc.mean()) if dVdc.mean() < 0 else np.nan))
    d = pd.DataFrame(rows); d.to_csv(f"{TAB}/wtp.csv", index=False); print(d.round(3).to_string())


def scatter(ax, x, y, label=None):
    ax.scatter(x, y, s=12, color=ps.MODEL, edgecolor="white", lw=0.3, zorder=3)
    hi = max(x.max(), y.max()) * 1.08
    ps.equality_line(ax, 0, hi); ax.set_xlim(0, hi); ax.set_ylim(0, hi)


def figures(zs):
    sh = pd.read_csv(f"{TAB}/region_shares_{TAG}.csv"); sm = pd.read_csv(f"{TAB}/smoke_region_shares.csv")
    fig, axs = ps.figure(2.3, ncols=3)
    for ax, s, t in ((axs[0], "val", "held-out"), (axs[1], "oot", "2019–2021")):
        g = sh[(sh["sample"] == s) & (sh.group == "all")]
        scatter(ax, g.obs * 100, g.pred * 100); ax.set_xlabel("Observed share of movers (%)")
    axs[0].set_ylabel("Model share of movers (%)")
    a = sm[(sm.run == "acs_2016_2020")].set_index("region").share; m = sm[(sm.run == "resloc_smoke") & (sm.year == 2017)].set_index("region").share
    scatter(axs[2], a * 100, m.reindex(a.index) * 100); axs[2].set_xlabel("Observed share of movers (%)")
    ps.finish(fig, f"{FIG}/fig_resloc_region_shares", panel_labels="abc")
    fig, axs = ps.figure(4.6, nrows=2, ncols=2)
    for ax, gname in zip(axs.flat, INC_GROUPS):
        g = sh[(sh["sample"] == "val") & (sh.group == gname)]
        scatter(ax, g.obs * 100, g.pred * 100)
        ax.set_xlabel("Observed share of movers (%)"); ax.set_ylabel("Model share (%)")
    ps.finish(fig, f"{FIG}/fig_resloc_income_shares", panel_labels="abcd")
    fig, axs = ps.figure(2.6, ncols=2)
    for ax, s in zip(axs, ("estimation", "validation")):
        g = zs[(zs["sample"] == s) & (zs.group != "all")]
        scatter(ax, g.obs * 100, g.pred * 100); ax.set_xlabel("Observed share within the county (%)")
    axs[0].set_ylabel("Model share within the county (%)")
    ps.finish(fig, f"{FIG}/fig_resloc_zone_puma", panel_labels="ab")
    el = pd.read_csv(f"{TAB}/region_elasticities_{TAG}.csv"); de = pd.read_csv(f"{TAB}/dwelling_elasticities.csv").set_index("group")
    w = lambda v: np.average(el[el.variable == v].elasticity, weights=el[el.variable == v].share)
    fig, axs = ps.figure(2.5, ncols=2)
    x = np.arange(4); lab = [GN[g] for g in INC_GROUPS]
    axs[0].bar(x - 0.2, [de.loc[g, "own_cost_elasticity"] for g in INC_GROUPS], 0.38, color=ps.MODEL, label="Dwelling within its area")
    axs[0].bar(x + 0.2, [w(f"monthly_cost_{g}") for g in INC_GROUPS], 0.38, color=ps.VARIANT, label="Region")
    axs[0].axhline(0, color=ps.INK2, lw=0.7); axs[0].set_xticks(x); axs[0].set_xticklabels(lab, rotation=30, ha="right")
    axs[0].set_ylabel("Elasticity of the choice\nprobability to housing cost (–)"); axs[0].set_ylim(-1.6, 1.0)
    axs[0].legend(loc="upper left", fontsize=ps.FONT)
    vals = [w("commute_time"), w("monthly_cost"), w("IV_B_plus_0.1") * 10]
    axs[1].bar(np.arange(3), vals, 0.5, color=ps.MODEL); axs[1].axhline(0, color=ps.INK2, lw=0.7)
    axs[1].set_xticks(np.arange(3)); axs[1].set_xticklabels(["Commute time", "Housing cost", "Accessibility\n(per util)"])
    axs[1].set_ylabel("Elasticity of the regional share (–)")
    ps.finish(fig, f"{FIG}/fig_resloc_elasticities", panel_labels="ab")


if __name__ == "__main__":
    zs = zone_shares(); wtp(); figures(zs)
