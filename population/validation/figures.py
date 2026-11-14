#!/usr/bin/env python3
"""Stage-1 figures for the paper, all through reports/paperstyle.py (one style, no overlaps, PDF+PNG).
  fig_s1_counts      persons by Maryland county, synthetic / Census 2016 (bars, sorted), with the group-quarters share marked
  fig_s1_composition PUMA x attribute cells: absolute difference in percentage points (heatmap, one row per PUMA)
  fig_s1_commute     commute-time distribution, model vs 2023 survey
  fig_s1_jobs        filled jobs by county, model vs LODES 2016 (scatter, equality line)
Data: data/stage1_validation.parquet, data/stage1_workplace_check.csv, data/raw/pep, PUMS.  Output: 1_vae/figures/ and a row each in 5_reports/figure_list.md"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, sys, os, json
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; sys.path.insert(0, f"{ORIOLE_HOME}/reports"); import paperstyle as ps
import matplotlib.pyplot as plt
FIG = f"{V}/1_vae/figures"; os.makedirs(FIG, exist_ok=True); R = pd.read_parquet(f"{V}/data/stage1_validation.parquet")
names = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv").drop_duplicates("COUNTYFIPS").set_index("COUNTYFIPS").JUR_NAME.str.replace(", MD", "", regex=False)
rows = []
# ---- fig 1: persons by county
A = R[(R.section == "A counts") & R.table.str.startswith("persons")].copy(); A["county"] = A.geo.astype(int); A["name"] = A.county.map(names); A = A.sort_values("ratio")
fig, ax = ps.figure(ps.DOUBLE, 2.8)
from matplotlib.patches import Patch; from matplotlib.lines import Line2D
ax.barh(A.name, A.ratio, color=[ps.MODEL if 0.93 <= r <= 1.03 else ps.VARIANT for r in A.ratio], height=0.7)
ax.axvline(0.977, color=ps.OBSERVED, lw=1)
ax.legend(handles=[Patch(color=ps.MODEL, label="within ±5 % of the household share"), Patch(color=ps.VARIANT, label="outside"), Line2D([], [], color=ps.OBSERVED, lw=1, label="persons in households / all persons, ACS (0.977)")],
          loc="lower right", fontsize=6.5)
ax.set_xlabel("Synthetic persons in households / Census population estimate, 2016"); ax.set_xlim(0.7, 1.1); ax.set_ylabel(""); ax.tick_params(axis="y", labelsize=6.5); ax.grid(axis="y", visible=False)
rows.append(("fig_s1_counts", ps.finish(fig, f"{FIG}/fig_s1_counts"), "Synthetic persons in households by Maryland county relative to the Census 2016 population estimate, after the stage-1 corrections. Blue: within ±5 % of the household share of the population (0.977); orange: outside. Counties below the line are those with large group-quarters populations, which the synthesis does not contain."))
# ---- fig 2: composition heatmap
B = R[R.section == "B composition"].copy(); B["puma"] = B.geo.str.replace("PUMA ", "").astype(int)
LAB = {"age band": {"0": "0–17", "1": "18–34", "2": "35–64", "3": "65+"}, "sex": {"1": "male", "2": "female"}, "employed (16+)": {"0": "not employed", "1": "employed"},
       "household size": {"1": "1 person", "2": "2", "3": "3", "4": "4", "5": "5+"}, "autos": {"0": "0 cars", "1": "1", "2": "2", "3": "3+"},
       "income class": {"0": "< $25k", "1": "$25–50k", "2": "$50–75k", "3": "$75–100k", "4": "$100–150k", "5": "$150k+"}}
B["cell"] = [f"{tb}: {LAB.get(tb, {}).get(str(b), b)}" for tb, b in zip(B.table, B["bin"].astype(str))]
H = B.pivot_table(index="puma", columns="cell", values="diff_pp", aggfunc="first"); order = [c for t in B.table.unique() for c in H.columns if c.startswith(t)]; H = H[order]
fig, ax = ps.figure(ps.DOUBLE, 4.6); im = ax.imshow(H.values, cmap=ps.DIV, vmin=-10, vmax=10, aspect="auto")
ax.set_yticks(range(len(H))); ax.set_yticklabels(H.index, fontsize=5.5); ax.set_xticks(range(len(order))); ax.set_xticklabels(order, rotation=90, fontsize=5.5); ax.grid(False)
ax.set_ylabel("PUMA (Maryland)"); ax.set_xlabel("attribute and bin"); cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01); cb.set_label("synthetic minus ACS, percentage points")
rows.append(("fig_s1_composition", ps.finish(fig, f"{FIG}/fig_s1_composition"), "Synthetic minus ACS PUMS 2014–2018 share, in percentage points, for every attribute bin and Maryland PUMA (1,012 cells; 96.9 % within ±5 pp). The 1-person household cells reflect the choice to honour the ACS person counts over its household-size shares."))
# ---- fig 3: commute-time distribution
r = pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv", low_memory=False, usecols=["o_activity", "d_activity", "travel_mode", "reported_travel_time", "wttrdfin"])
r = r[(r.travel_mode == 4) & (((r.o_activity == 1) & (r.d_activity == 2)) | ((r.o_activity == 2) & (r.d_activity == 1))) & r.reported_travel_time.between(1, 120)]
obs = r.groupby((r.reported_travel_time // 5 * 5).astype(int)).wttrdfin.sum(); obs /= obs.sum()
import h5py; h = h5py.File(f"{ABIT_HOME}/input/mito_los/skims/traveltime_auto.omx", "r"); T = h["data/mat1"][:]; ids = h["lookup/destinations"][:]; idx = {int(z): i for i, z in enumerate(ids)}
jj = pd.read_parquet(f"{V}/1_vae/vae_outputs/05_workplace/jj.parquet"); pp = pd.read_parquet(f"{V}/1_vae/output/pp.parquet", columns=["pp_id", "hh_id"]); hh = pd.read_parquet(f"{V}/1_vae/output/hh.parquet", columns=["hh_id", "zone_id"])
w = jj.merge(pp, left_on="personId", right_on="pp_id").merge(hh, on="hh_id"); w = w[w.zone_id.isin(idx) & w.zone.isin(idx)]; t = T[w.zone_id.map(idx).values, w.zone.map(idx).values]
mod = pd.Series(t).groupby((pd.Series(t).clip(1, 120) // 5 * 5).astype(int)).size(); mod = mod / mod.sum()
fig, ax = ps.figure(ps.SINGLE, 2.4); x = np.arange(0, 120, 5)
ax.step(x + 5, obs.reindex(x, fill_value=0).values, where="pre", color=ps.OBSERVED, label="2023 household travel survey (reported, car driver)")
ax.step(x + 5, mod.reindex(x, fill_value=0).values, where="pre", color=ps.MODEL, label="synthetic population (AM-peak skim)")
ax.set_xlabel("home–work travel time (minutes, 5-minute bins)"); ax.set_ylabel("share of commuters"); ax.legend(loc="upper center", bbox_to_anchor=(0.6, 1.0)); ax.set_xlim(0, 120); ax.set_ylim(0, 0.19)
rows.append(("fig_s1_commute", ps.finish(fig, f"{FIG}/fig_s1_commute"), "Distribution of home–work travel time: synthetic workers (AM-peak network time) and reported car-driver times in the 2023 household travel survey (weighted)."))
# ---- fig 4: jobs by county
D = R[R.section == "D jobs"].copy(); D["name"] = D.geo.astype(int).map(names)
fig, ax = ps.figure(ps.SINGLE, 3.2); ax.scatter(D.observed, D.model, s=14, color=ps.MODEL, edgecolor="white", linewidth=0.4, zorder=3)
ps.equality_line(ax, 1e3, 1e6, band=0.1); ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("LODES 2016 jobs by county"); ax.set_ylabel("synthetic filled jobs by county")
for k, (_, q) in enumerate(D.nlargest(3, "model").iterrows()): ax.annotate(q["name"], (q.observed, q.model), xytext=(6, [-9, 5, -9][k]), textcoords="offset points", fontsize=6, color=ps.INK2, ha="left")
rows.append(("fig_s1_jobs", ps.finish(fig, f"{FIG}/fig_s1_jobs"), "Filled jobs by Maryland county: synthetic population against LODES 2016 (log scales; dashed lines ±10 %)."))
with open(f"{V}/5_reports/figure_list.md", "a") as f:
    for name, path, cap in rows: f.write(f"| {name} | `population/validation/figures.py` | `data/stage1_validation.parquet`, `data/stage1_workplace_check.csv` | {cap} |\n")
print("figures:", [r[1] for r in rows])
