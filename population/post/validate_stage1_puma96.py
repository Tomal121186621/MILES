#!/usr/bin/env python3
"""Composition of the synthetic base population 2016 by PUMA, all 96 PUMAs of the six states the population is generated for
(the Maryland part of validate_stage1.py, section B, extended to DC, DE, PA, VA and WV).  Same bins and same observed data:
ACS PUMS 2014-2018 5-year file of each state, households (TYPE 1, NP > 0) and persons outside group quarters.
In the five PUMAs that the zone system covers only in part, the synthetic households stand for the covered part; shares are compared.
Outputs: data/stage1_composition_puma96.csv (state, puma, table, bin, model, observed, diff_pp) and
5_reports/article/figures/fig_val_pop_puma.{pdf,png} (rows: PUMAs grouped by state, largest first; columns: attribute bins)."""
import sys, zipfile, numpy as np, pandas as pd
ROOT = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM"; V = f"{ROOT}/Validation_2026"; MD = f"{V}/2_silo/input/microData"
sys.path.insert(0, f"{V}/5_reports")
import paperstyle as ps, figures_validation as fv
import matplotlib.pyplot as plt
ST = {24: ("md", "Maryland"), 11: ("dc", "District of Columbia"), 10: ("de", "Delaware"), 42: ("pa", "Pennsylvania"), 51: ("va", "Virginia"), 54: ("wv", "West Virginia")}

z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").set_index("ZoneId")
hh = pd.read_csv(f"{MD}/hh_2016.csv"); dd = pd.read_csv(f"{MD}/dd_2016.csv", usecols=["id", "zone"])
pp = pd.read_csv(f"{MD}/pp_2016.csv", usecols=["hhID", "age", "gender", "occupation"])
hh = hh.merge(dd.rename(columns={"id": "dwelling"}), on="dwelling"); hh["st"] = hh.zone.map(z.STFIPS); hh["puma"] = hh.zone.map(z.PUMA_10 % 100000)
pp = pp.merge(hh[["id", "st", "puma"]].rename(columns={"id": "hhID"}), on="hhID")

def pums(st, kind, cols):
    with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_{kind}{ST[st][0]}.zip") as zf:
        n = [x for x in zf.namelist() if x.endswith(".csv")][0]; return pd.read_csv(zf.open(n), usecols=cols, low_memory=False)
def shares(vals, w=None, order=None):
    s = pd.Series(w if w is not None else np.ones(len(vals))).groupby(np.asarray(vals)).sum(); s = s / s.sum(); return s.reindex(order, fill_value=0)

# bins exactly as validate_stage1.py, section B
B = [("age band", lambda d: np.digitize(d.age, [18, 35, 65]), lambda q: np.digitize(q.AGEP, [18, 35, 65]), [0, 1, 2, 3], "p"),
     ("sex", lambda d: d.gender, lambda q: q.SEX, [1, 2], "p"),
     ("employed (16+)", lambda d: (d.occupation == 1).astype(int), lambda q: q.ESR.isin([1, 2, 4, 5]).astype(int), [0, 1], "p16"),
     ("household size", lambda d: d.hhSize.clip(upper=5), lambda q: q.NP.clip(upper=5), [1, 2, 3, 4, 5], "h"),
     ("autos", lambda d: d.autos.clip(upper=3), lambda q: q.VEH.fillna(0).clip(upper=3).astype(int), [0, 1, 2, 3], "h"),
     ("income class", lambda d: pd.cut(d.income, [-1e9, 25e3, 50e3, 75e3, 100e3, 150e3, 1e12], labels=False),
      lambda q: pd.cut(q.inc, [-1e9, 25e3, 50e3, 75e3, 100e3, 150e3, 1e12], labels=False), [0, 1, 2, 3, 4, 5], "h")]
rows = []
for st in ST:
    H = pums(st, "h", ["PUMA", "WGTP", "NP", "TYPE", "VEH", "HINCP", "ADJINC"]); H = H[(H.TYPE == 1) & (H.NP > 0)].copy()
    H["inc"] = H.HINCP.fillna(0) * H.ADJINC / 1e6
    P = pums(st, "p", ["PUMA", "PWGTP", "RELP", "AGEP", "SEX", "ESR"]); P = P[~P.RELP.isin([16, 17])]
    mh, mp = hh[hh.st == st], pp[pp.st == st]
    for pu in sorted(mh.puma.unique()):
        for name, fm, fo, order, kind in B:
            if kind == "h": m = shares(fm(mh[mh.puma == pu]), order=order); q = H[H.PUMA == pu]; o = shares(fo(q), q.WGTP.values, order)
            else:
                dm, q = mp[mp.puma == pu], P[P.PUMA == pu]
                if kind == "p16": dm, q = dm[dm.age >= 16], q[q.AGEP >= 16]
                m = shares(fm(dm), order=order); o = shares(fo(q), q.PWGTP.values, order)
            for b in order: rows.append(dict(state=st, puma=int(pu), households=int((mh.puma == pu).sum()), table=name, bin=str(b), model=m[b], observed=o[b]))
R = pd.DataFrame(rows); R["diff_pp"] = 100 * (R.model - R.observed)
R.to_csv(f"{V}/data/stage1_composition_puma96.csv", index=False)
a = R.assign(a=R.diff_pp.abs())
print(f"{R[['state', 'puma']].drop_duplicates().shape[0]} PUMAs; cells within ±5 pp: {(a.a <= 5).mean():.1%}")
print(a.groupby("state").a.agg(["mean", "max", lambda s: (s <= 5).mean()]).round(2).rename(index={k: v[1] for k, v in ST.items()}))
print(a.groupby("table").a.agg(["mean", "max"]).round(2))

# ---- figure: rows grouped by state (Maryland first), largest PUMA first within a state
B_ = R.rename(columns={"table": "table"}); cols = fv.bin_rows(B_)
order = []
for st in ST: order += [(st, p) for p in R[R.state == st].drop_duplicates("puma").sort_values("households", ascending=False).puma]
Hm = np.array([[R[(R.state == s) & (R.puma == p) & (R.table == t) & (R.bin == b)].diff_pp.iloc[0] for t, b, *_ in cols] for s, p in order])
fig = ps.new_figure(ps.MAX_HEIGHT); ax = fig.add_subplot(111)
im = fv.heat_groups(ax, Hm, cols, annotate=99)                                  # no cell labels at 96 rows
pos, prev = [], None
for i, (s, p) in enumerate(order):
    if s != prev:
        if prev is not None: ax.axhline(i - 0.5, color="white", lw=2.0)
        pos.append([s, i, i])
    pos[-1][2] = i; prev = s
ax.set_yticks([(a_ + b_) / 2 for s, a_, b_ in pos]); ax.set_yticklabels([f"{ST[s][1]} ({b_ - a_ + 1})" for s, a_, b_ in pos])
ax.set_ylabel("PUMAs by state, largest at the top")
fv.pp_colorbar(fig, im, ax, orientation="horizontal", label=ps.PP_LABEL.replace("\n", " "), fraction=0.03, pad=0.01, aspect=50, shrink=0.6)
ps.finish(fig, f"{V}/5_reports/article/figures/fig_val_pop_puma_heat")   # heatmap; the article uses fig_pop_puma_shrink.py
