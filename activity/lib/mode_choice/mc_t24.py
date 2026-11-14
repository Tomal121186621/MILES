#!/usr/bin/env python3
"""2024 forecast test of the tour mode choice: commute mode by Maryland county, model (work tours of the 2024 runs, frozen model
with the estimated tour mode choice, temporal_2024 T24_MODEL=mc) against the ACS 2024 1-year PUMS (JWTRNS of commuters: at
work last week, not working at home; carpools split as in t24common.acs_mode_shares), and the NTD 2024 ridership of the MTA.

    python3 activity/lib/mode_choice/mc_t24.py       -> results/t24_commute_mode_county.csv, results/ntd_mta.csv, 5_reports/figures/fig_mc_t24_county.pdf

Model: tours with a WORK main activity of employed persons of the 2024 observed population (setting acs2024: ACS 2024 PUMS
households placed in zones) by home county, 10 replications (mean); mode as ABIT writes it (car driver, car passenger, bus, train,
walk, bike).  Counties with fewer than 200 ACS commuter records are not shown."""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__))
HERE = f"{WORKSPACE}/3_abit/mode_choice"; A3 = os.path.dirname(HERE); V = os.path.dirname(A3)
sys.path.insert(0, f"{TERP_HOME}/activity/lib/reporting_2024"); sys.path.insert(0, CODE)
os.environ.setdefault("T24_MODEL", "mc")
import t24common as C   # noqa: E402
import mc_common as M   # noqa: E402
MAP = {"CAR_DRIVER": "Car, driver", "CAR_PASSENGER": "Car, passenger", "BUS": "Bus", "TRAIN": "Rail", "WALK": "Walk", "BIKE": "Bicycle"}
MODES = ["Car, driver", "Car, passenger", "Bus", "Rail", "Walk", "Bicycle"]


def acs_county():
    import bench_acs as B
    p = B.load("acs2024"); cm = p[p.commuter & (p.county > 0)]; rows = []
    for c, g in cm.groupby("county"):
        if len(g) < 200: continue
        s = C.acs_mode_shares(g); s = s.drop("Other") / s.drop("Other").sum()
        for m in MODES: rows.append(dict(county=int(c), mode=m, acs=float(s[m]), n_acs=len(g)))
    return pd.DataFrame(rows)


def model_county(setting="acs2024"):
    cty = M.C.zones().set_index("id").countyfips; rows = []
    for s in range(1, 11):
        d = f"{C.T24}/run/{C.PFX}{setting}_s{s:02d}/output/mc_tours.csv"
        if not os.path.exists(d): continue
        j = pd.read_csv(d); j = j[j.purpose.eq("WORK")]; j["county"] = cty.reindex(j.home_zone.values).values; j["m"] = j["mode"].map(MAP)
        x = j.groupby("county").m.value_counts(normalize=True).rename("share").reset_index(); x["rep"] = s; rows.append(x)
    r = pd.concat(rows); return r.groupby(["county", "m"]).share.mean().rename("model").reset_index().rename(columns={"m": "mode"})


def ntd():
    d = pd.read_csv(f"{V}/data/raw/ntd_2024/ntd_monthly_mta_30034.csv"); d["year"] = pd.to_datetime(d.date).dt.year
    lab = {"MB": "Local bus", "CB": "Commuter bus", "LR": "Light rail", "HR": "Metro subway", "CR": "MARC commuter rail", "DR": "Demand response"}
    t = d[d.year.isin([2017, 2018, 2024])].groupby(["mode", "year"]).upt.sum().unstack(); t.index = t.index.map(lab); t.to_csv(f"{M.RES}/ntd_mta.csv")
    return t


def figure(r):
    sys.path.insert(0, f"{TERP_HOME}/reports"); import paperstyle as ps
    fig, axs = ps.figure(height=3.4, ncols=2)
    col = {m: ps.CAT[i] for i, m in enumerate(MODES)}
    for ax, ms, lo, hi in [(axs[0], ["Car, driver"], 40, 100), (axs[1], [m for m in MODES if m != "Car, driver"], 0, None)]:
        for m in ms:
            x = r[r["mode"] == m]; ax.scatter(100 * x.acs, 100 * x.model, s=14, color=col[m], label=m)
        hi = hi or 100 * r[r["mode"].isin(ms)][["acs", "model"]].max().max() * 1.08
        ax.plot([lo, hi], [lo, hi], color=ps.OBSERVED, lw=0.8, ls=(0, (4, 2))); ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.set_xlabel("Observed commute share (%)"); ax.set_ylabel("Model commute share (%)")
    h, l = [], []
    for ax in axs:
        a, b = ax.get_legend_handles_labels(); h += a; l += b
    fig.legend(h, l, loc="outside lower center", ncol=6)
    out = f"{V}/5_reports/figures/fig_mc_t24_county"; ps.finish(fig, out, panel_labels=["a", "b"])
    import shutil; shutil.copy(out + ".pdf", f"{V}/5_reports/article/figures/fig_mc_t24_county.pdf")


if __name__ == "__main__":
    a = acs_county(); m = model_county(); r = a.merge(m, on=["county", "mode"], how="left").fillna({"model": 0.0})
    r.to_csv(f"{M.RES}/t24_commute_mode_county.csv", index=False)
    print(r.pivot_table(index="county", columns="mode", values=["acs", "model"]).round(3).to_string())
    print(ntd()); figure(r)
