#!/usr/bin/env python3
"""Tour mode shares of the ABIT runs (output/mc_tours.csv) against the RTS tours, 10 replications, and the figures of the mode
choice validation.

    python3 activity/lib/mode_choice/mc_validation.py tables      -> results/abit_mode_validation.csv, results/reallocation.csv
    python3 activity/lib/mode_choice/mc_validation.py figures     -> 5_reports/figures/fig_mc_*.pdf/png (+ article/figures)

Settings (Roorda et al. 2008 design; mode choice of the tours ABIT generates):
  verification  survey-population runs of the estimation half (run_survey/svy_est_<v>_s01..10), person weights of the half
  validation    survey-population runs of the held-out half (svy_val_<v>_s..), person weights
  chain         synthetic population, 5 % household sample (run/val_<v>_s..), unweighted, persons living in the counties of the
                survey's households; observed = the held-out half
Variants v: behav (behavioural, no ASC adjustment), cal (ASC adjustments to the estimation half).  Observed: the RTS home-based
tours of the half (prep_tours.py), weighted, tour mode by the main-mode hierarchy, transit = TRAIN when a trip of the tour is by rail.
Groups: purpose of the main activity, one-way home - main distance band (car-distance skim), period of the main activity's start,
car sufficiency (0 cars / fewer cars than drivers / cars >= drivers), household income group, home county, all.
The observed-tour test (mode choice isolated) is mc_apply.py observed -> results/obs_validation.csv.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
HERE = f"{WORKSPACE}/3_abit/mode_choice"   # data folder; CODE = this folder
import mc_common as M   # noqa: E402
A3 = os.path.dirname(HERE); V = os.path.dirname(A3)
MODES = ["CAR_DRIVER", "CAR_PASSENGER", "BUS", "TRAIN", "WALK", "BIKE"]
DBANDS = [0, 2, 5, 10, 20, 40, 80, 1e9]; DLAB = ["0-2", "2-5", "5-10", "10-20", "20-40", "40-80", "80+"]
ALT2MODE = {"CD": "CAR_DRIVER", "CP": "CAR_PASSENGER", "BUS": "BUS", "TRAIN": "TRAIN", "WK": "WALK", "BK": "BIKE"}


def groups(purpose, km_rt, start, autos, drivers, inc, county):
    return {"purpose": np.asarray(purpose), "distance": pd.cut(np.asarray(km_rt) / 2, DBANDS, labels=DLAB, right=False).astype(str),
            "period": np.array(M.PERIODS)[M.period(np.asarray(start))],
            "cars": np.select([np.asarray(autos) <= 0, np.asarray(autos) < np.asarray(drivers)], ["0 cars", "cars < drivers"], "cars >= drivers"),
            "income": np.select([np.asarray(inc) < 50000, np.asarray(inc) < 100000], ["< $50k", "$50-100k"], "$100k+"),
            "county": np.asarray(county).astype(int).astype(str), "all": np.full(len(purpose), "all")}


def observed(half):
    t = pd.read_parquet(f"{M.WORK}/tours_{half}.parquet")
    g = groups(t.purpose, t.km, t.start, t.autos, t.drivers, t.inc_year, t.county)
    return g, t.choice2.map(ALT2MODE).values, t.w.values


def persons_survey(half):
    sp = f"{A3}/survey_pop/{half}"; pp = pd.read_csv(f"{sp}/pp.csv"); hh = pd.read_csv(f"{sp}/hh.csv").set_index("id"); pm = pd.read_csv(f"{sp}/persons_map.csv").set_index("id")
    pp["lic"] = pp.driversLicense.astype(str).eq("True"); pp["inc_m"] = np.floor(pp.income / 12.0)
    g = pp.groupby("hhID").agg(drivers=("lic", "sum"), inc=("inc_m", "sum"))
    p = pp.set_index("id").join(g, on="hhID").join(hh[["autos"]], on="hhID"); p["inc"] = 12 * p.inc; p["w"] = pm.w.reindex(p.index).values
    return p[["autos", "drivers", "inc", "w"]]


_SILO = {}


def persons_silo():
    if "p" in _SILO: return _SILO["p"]
    md = f"{V}/2_silo/input/microData"
    pp = pd.read_csv(f"{md}/pp_2016.csv", usecols=["id", "hhid", "driversLicense", "income"]) if False else pd.read_csv(f"{md}/pp_2016.csv")
    hc = "hhid" if "hhid" in pp else "hhID"
    pp["lic"] = pp.driversLicense.astype(str).str.lower().eq("true"); pp["inc_m"] = np.floor(pp.income / 12.0)
    g = pp.groupby(hc).agg(drivers=("lic", "sum"), inc=("inc_m", "sum"))
    hh = pd.read_csv(f"{md}/hh_2016.csv", usecols=lambda c: c in ("id", "autos")).set_index("id")
    p = pp.set_index("id")[[hc]].join(g, on=hc).join(hh, on=hc); p["inc"] = 12 * p.inc; p["w"] = 1.0
    _SILO["p"] = p[["autos", "drivers", "inc", "w"]]; return _SILO["p"]


def model_tours(run_dir, persons):
    j = pd.read_csv(f"{run_dir}/output/mc_tours.csv"); p = persons.reindex(j.person_id.values)
    cty = M.C.zones().set_index("id").countyfips
    g = groups(j.purpose.values, j.km.values, j.start.values, p.autos.values, p.drivers.values, p.inc.values, cty.reindex(j.home_zone.values).fillna(-1).values)
    return g, j["mode"].values, p.w.values, j


def shares(g, mode, w, keep=None):
    rows = []
    keep = np.ones(len(mode), bool) if keep is None else keep
    for dim, lab in g.items():
        for gv in np.unique(lab[keep]):
            m = keep & (lab == gv); tot = w[m].sum()
            for mo in MODES: rows.append(dict(dim=dim, group=gv, mode=mo, share=w[m & (mode == mo)].sum() / tot if tot > 0 else np.nan, n=int(m.sum())))
    return pd.DataFrame(rows)


def tables():
    out, realloc = [], []
    for setting, half, root, pfx in [("verification", "estimation", "run_survey", "svy_est_"), ("validation", "validation", "run_survey", "svy_val_"), ("chain", "validation", "run", "val_")]:
        go, mo, wo = observed(half); O = shares(go, mo, wo).rename(columns={"share": "observed", "n": "n_obs"})
        counties = set(np.unique(go["county"]))
        for v in os.environ.get("MC_VARIANTS", "behav,cal,reest,rail").split(","):   # e.g. MC_VARIANTS=respec MC_OUT_SUFFIX=_respec
            reps = []
            for s in range(1, 11):
                d = f"{A3}/{root}/{pfx}{v}_s{s:02d}"
                if not os.path.exists(f"{d}/output/mc_tours.csv"): continue
                P = persons_silo() if setting == "chain" else persons_survey(half)
                g, mm, w, j = model_tours(d, P); keep = np.isin(g["county"], list(counties)) if setting == "chain" else None
                x = shares(g, mm, w, keep); x["rep"] = s; reps.append(x)
                ms = pd.read_csv(f"{d}/output/mc_summary.csv").set_index("measure").value
                realloc.append(dict(setting=setting, variant=v, rep=s, **{k: ms.get(m_, np.nan) for k, m_ in [("cd_tours", "car_driver_tours_before_allocation"), ("reallocated", "car_driver_tours_reallocated"), ("households", "households"),
                                    ("households_conflict", "households_with_a_car_conflict"), ("joint_groups", "joint_groups"), ("joint_tours", "joint_tours"), ("tours", "tours")]}))
            if not reps: print("no runs:", setting, v); continue
            R = pd.concat(reps); a = R.groupby(["dim", "group", "mode"]).share.agg(model="mean", model_sd="std", p05=lambda x: np.percentile(x, 5), p95=lambda x: np.percentile(x, 95), n_reps="size").reset_index()
            a = a.merge(R.groupby(["dim", "group", "mode"]).n.mean().rename("n_model_per_rep").reset_index(), on=["dim", "group", "mode"])
            a = a.merge(O, on=["dim", "group", "mode"], how="left"); a["setting"] = setting; a["variant"] = v; out.append(a)
    r = pd.concat(out); r.to_csv(f"{M.RES}/abit_mode_validation{os.environ.get('MC_OUT_SUFFIX', '')}.csv", index=False)
    pd.DataFrame(realloc).to_csv(f"{M.RES}/reallocation{os.environ.get('MC_OUT_SUFFIX', '')}.csv", index=False)
    print(r[r.dim.eq("all")].pivot_table(index=["setting", "variant"], columns="mode", values=["model", "observed"]).round(3).to_string())


# ------------------------------------------------------------------------------------------------ figures
MLAB = {"CAR_DRIVER": "Car driver", "CAR_PASSENGER": "Car passenger", "BUS": "Bus", "TRAIN": "Train", "WALK": "Walk", "BIKE": "Bike"}
PLAB = {"WORK": "Work", "EDUCATION": "School", "SHOPPING": "Shopping", "RECREATION": "Recreation", "ACCOMPANY": "Accompany", "OTHER": "Other"}


def figures():
    sys.path.insert(0, f"{MILES_HOME}/reports"); import paperstyle as ps; import matplotlib.pyplot as plt
    OUT = f"{V}/5_reports/figures"; ART = f"{V}/5_reports/article/figures"
    obs = pd.read_csv(f"{M.RES}/obs_validation.csv"); ab = pd.read_csv(f"{M.RES}/abit_mode_validation.csv")
    tests = [("validation", obs[(obs.setting == "validation") & (obs.variant == "behavioural")], "obs"), ("chain", ab[(ab.setting == "chain") & (ab.variant == "behav")], "chain")]
    def bars(ax, d, cats, labels, mode):
        x = np.arange(len(cats)); r = d[d["mode"] == mode].set_index("group").reindex(cats)
        ax.bar(x - 0.2, 100 * r.observed, 0.38, color=ps.OBSERVED, label=ps.LEG["observed"])
        ax.bar(x + 0.2, 100 * r.model, 0.38, color=ps.MODEL, label=ps.LEG["model"])
        ax.errorbar(x + 0.2, 100 * r.model, yerr=[100 * (r.model - r.p05), 100 * (r.p95 - r.model)], fmt="none", ecolor="#0d366b", lw=0.8, capsize=1.5, label="90 % band of 10 replications")
        ax.set_xticks(x); ax.set_xticklabels(labels, rotation=45, ha="right")
    for tag, d, key in tests:
        # (1) tour mode share by activity purpose
        dp = d[d.dim == "purpose"]; cats = [p for p in PLAB if p in set(dp.group)]
        fig, axs = ps.figure(height=4.6, nrows=2, ncols=3)
        for ax, mo in zip(axs.flat, MODES):
            bars(ax, dp, cats, [PLAB[c] for c in cats], mo); ax.set_title(MLAB[mo]); ax.set_ylabel("Share of tours (%)")
        h, l = axs.flat[0].get_legend_handles_labels(); fig.legend(h, l, loc="outside lower center", ncol=3)
        ps.finish(fig, f"{OUT}/fig_mc_purpose_{key}")
        # (2) mode share by tour distance (curves)
        dd = d[d.dim == "distance"]; cats = [c for c in DLAB if c in set(dd.group)]
        fig, axs = ps.figure(height=4.4, nrows=2, ncols=3)
        for ax, mo in zip(axs.flat, MODES):
            r = dd[dd["mode"] == mo].set_index("group").reindex(cats); x = np.arange(len(cats))
            ax.fill_between(x, 100 * r.p05, 100 * r.p95, color=ps.SEED_BAND, lw=0, label="90 % band of 10 replications")
            ax.plot(x, 100 * r.observed, color=ps.OBSERVED, ls=(0, (5, 2.5)), label=ps.LEG["observed"]); ax.plot(x, 100 * r.model, color=ps.MODEL, label=ps.LEG["model"])
            ax.set_xticks(x); ax.set_xticklabels(cats, rotation=45, ha="right"); ax.set_title(MLAB[mo]); ax.set_xlabel("One-way distance (km)"); ax.set_ylabel("Share of tours (%)")
        h, l = axs.flat[0].get_legend_handles_labels(); fig.legend(h, l, loc="outside lower center", ncol=3)
        ps.finish(fig, f"{OUT}/fig_mc_distance_{key}")
        # (3) by car sufficiency
        dc = d[d.dim == "cars"]; cats = ["0 cars", "cars < drivers", "cars >= drivers"]; labs = ["No car", "Fewer cars than drivers", "Cars ≥ drivers"]
        fig, axs = ps.figure(height=4.6, nrows=2, ncols=3)
        for ax, mo in zip(axs.flat, MODES):
            bars(ax, dc, cats, labs, mo); ax.set_title(MLAB[mo]); ax.set_ylabel("Share of tours (%)")
        h, l = axs.flat[0].get_legend_handles_labels(); fig.legend(h, l, loc="outside lower center", ncol=3)
        ps.finish(fig, f"{OUT}/fig_mc_cars_{key}")
    for f in os.listdir(OUT):
        if f.startswith("fig_mc_") and f.endswith(".pdf"):
            import shutil; shutil.copy(f"{OUT}/{f}", f"{ART}/{f}")


if __name__ == "__main__":
    {"tables": tables, "figures": figures}[sys.argv[1]]()
