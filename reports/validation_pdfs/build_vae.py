#!/usr/bin/env python3
"""Validation of the synthetic population (stage 1, conditional VAE).

    python3 reports/validation_pdfs/build_vae.py [--vae-run full] [--validation PARQUET] [--shares CSV] [--puma96 CSV] [--pairs CSV] [--out PDF] [--work DIR]

--vae-run   name of the held-out validation folder of the generator (VAE_HOME/outputs/07_validation/<name>/results.json)
--validation  Maryland counts, composition by PUMA, joint tables, jobs   (population/validation/validate_population.py)
--shares    Maryland category shares, model and observed                 (default: the table used by the staged figures)
--puma96    composition of all 96 PUMAs of the six states                (population/validation/validate_by_puma.py)
--pairs     SRMSE of every attribute pair against the held-out split
--base      base-year microdata that the land-use model starts from (jj_2016, pp_2016, hh_2016, dd_2016); jobs by county and the commute
            of the synthetic workers are computed from these files (default: the re-assigned base workplaces of the final land-use runs)
"""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, json, os, shutil, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("--vae-run", default="full")
ap.add_argument("--validation", default=f"{DATA}/stage1_validation.parquet")
ap.add_argument("--shares", default=f"{REPORTS}/article/figures/val_data/stage1_md_shares.csv")
ap.add_argument("--puma96", default=f"{DATA}/stage1_composition_puma96.csv")
ap.add_argument("--pairs", default=f"{DATA}/pop_pairs_srmse.csv")
ap.add_argument("--base", default=f"{V}/2_silo/run/base_v5_respec/microData")
ap.add_argument("--out", default=f"{OUTDIR}/vae_validation.pdf")
ap.add_argument("--work", default=f"{OUTDIR}/work/vae")
a = ap.parse_args()
WORK = os.path.abspath(a.work); FIG = f"{WORK}/fig"; os.makedirs(FIG, exist_ok=True)
fv = patch_fig_dirs(FIG)
import paperstyle as ps
import composite as K
import fig_pop_landuse as PL
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

def base_checks(base, work):
    """Filled jobs by Maryland county (against LODES 2016) and the commute of the synthetic workers (AM-peak car skim; distance skim),
    from the base-year files the land-use model reads; cached in the work directory by file time."""
    cj, cc = f"{work}/base_jobs.csv", f"{work}/base_commute.csv"; src = [f"{base}/{f}_2016.csv" for f in ("jj", "pp", "hh", "dd")]
    if all(os.path.exists(c) and os.path.getmtime(c) >= max(os.path.getmtime(f) for f in src) for c in (cj, cc)):
        return pd.read_csv(cj), pd.read_csv(cc, dtype={"bin": str})
    import h5py
    z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").set_index("ZoneId")
    jj = pd.read_csv(src[0], usecols=["id", "zone", "personId"]); jj = jj[jj.personId > 0]
    xw = pd.read_csv(f"{V}/data/raw/lodes_wac/md_xwalk.csv.gz", usecols=["tabblk2020", "cty"], dtype=str)
    w = pd.read_csv(f"{V}/data/raw/lodes_wac/md_wac_S000_JT00_2016.csv.gz", dtype={"w_geocode": str}, usecols=["w_geocode", "C000"]).merge(xw, left_on="w_geocode", right_on="tabblk2020")
    lod = w.groupby(w.cty.astype(int)).C000.sum(); jc = jj.zone.map(z.COUNTYFIPS); jm = jj[jc.between(24000, 24999)].groupby(jc).size()
    J = pd.DataFrame({"geo": jm.index.astype(int), "model": jm.values, "observed": lod.reindex(jm.index).values}); J["ratio"] = J.model / J.observed
    pp = pd.read_csv(src[1], usecols=["id", "hhID"]); hh = pd.read_csv(src[2], usecols=["id", "dwelling"]); dd = pd.read_csv(src[3], usecols=["id", "zone"])
    hz = hh.merge(dd.rename(columns={"id": "dwelling", "zone": "hzone"}), on="dwelling")[["id", "hzone"]].rename(columns={"id": "hhID"})
    wk = jj.rename(columns={"zone": "wzone"}).merge(pp.rename(columns={"id": "personId"}), on="personId").merge(hz, on="hhID")
    wk = wk[wk.hzone.map(z.STFIPS).eq(24)]
    h = h5py.File(f"{ABIT_HOME}/input/mito_los/skims/traveltime_auto.omx", "r"); T = h["data/mat1"][:]; ids = h["lookup/destinations"][:]; idx = {int(q): i for i, q in enumerate(ids)}
    Dk = h5py.File(f"{ABIT_HOME}/input/mito_los/skims/distance_auto.omx", "r")["data/mat1"][:] / 1000.0
    wk = wk[wk.hzone.isin(idx) & wk.wzone.isin(idx)]; i, j = wk.hzone.map(idx).values, wk.wzone.map(idx).values; t, km = T[i, j], Dk[i, j]; intra = float((i == j).mean()); del T, Dk
    old = pd.read_csv(f"{DATA}/stage1_commute_curves.csv", dtype={"bin": str})          # the survey side (2017/18 RTS car-driver commutes) is unchanged
    tb = np.arange(0, 125, 5); ts_ = pd.Series(1.0, index=range(len(t))).groupby((np.clip(t, 0, 119.99) // 5 * 5).astype(int)).sum(); ts_ = (ts_ / ts_.sum()).reindex(tb[:-1], fill_value=0).values
    C = old.copy()
    C.loc[C.quantity == "time", "model"] = ts_; C.loc[C.quantity == "distance", "model"] = fv.dist_pmf(km)
    C.loc[C.quantity == "mean_min", "model"] = float(np.mean(t)); C.loc[C.quantity == "mean_km", "model"] = float(np.mean(km))
    C = pd.concat([C, pd.DataFrame([dict(quantity="intrazonal_share", bin="", model=intra, observed=np.nan), dict(quantity="workers", bin="", model=len(t), observed=np.nan)])])
    J.to_csv(cj, index=False); C.to_csv(cc, index=False); return J, pd.read_csv(cc, dtype={"bin": str})


class S1(fv.Stage1):
    """Stage1 data class of figures_validation with the inputs of this build (jobs and commute from the land-use base files)."""
    def __init__(self):
        self.R = R; self.J = RES; self.W = None; self.C = CB


RES = json.load(open(f"{VAE_HOME}/outputs/07_validation/{a.vae_run}/results.json"))
R = pd.read_parquet(a.validation); SH = pd.read_csv(a.shares, keep_default_na=False, na_values=[""]); P96 = pd.read_csv(a.puma96); P96["bin"] = P96["bin"].astype(str)
JB, CB = base_checks(os.path.abspath(a.base), WORK)
R = pd.concat([R[R.section != "D jobs"], pd.DataFrame(dict(section="D jobs", geo=JB.geo.astype(str), table="filled jobs vs LODES 2016", bin="jobs", model=JB.model, observed=JB.observed,
                                                             diff_pp=(JB.model - JB.observed) * 100, ratio=JB.ratio))], ignore_index=True)
def num(x, d=2, sign=False, pct=False):
    """num of common, without a sign on values that round to zero."""
    from common import num as num0
    if x is not None and isinstance(x, (float, int, np.floating)) and np.isfinite(x) and round(abs(x * (100 if pct else 1)), d) == 0: x = 0.0; sign = False
    return num0(x, d, sign, pct)
PAIRS = pd.read_csv(a.pairs)
STN = {24: "Maryland", 11: "District of Columbia", 10: "Delaware", 42: "Pennsylvania", 51: "Virginia", 54: "West Virginia"}

# ------------------------------------------------------------------ computed quantities
def tvd(g): return 0.5 * (g.model - g.observed).abs().sum() * 100
PRIMARY = ["age band", "sex", "employed (16+)", "employment status", "race and ethnicity", "nationality", "relationship", "person income (2016 $)",
           "household size", "cars", "household income (2016 $)", "tenure", "dwelling type", "bedrooms", "year built", "monthly housing cost (2016 $)"]
SHp = SH[SH.variable.isin(PRIMARY)].copy()
mdrows = []
for v in PRIMARY:
    g = SHp[SHp.variable == v]; d = (g.model - g.observed) * 100; k = d.abs().idxmax()
    mdrows.append((v, len(g), tvd(g), d.abs().max(), g.category.loc[k], d.loc[k]))
MD = pd.DataFrame(mdrows, columns=["variable", "k", "tvd", "maxdiff", "maxcat", "maxsigned"])
A = R[(R.section == "A counts") & R.table.str.startswith("persons")].copy(); A["county"] = A.geo.astype(int)
Hh = R[(R.section == "A counts") & (R.table == "households vs ACS")]
Dj = R[R.section == "D jobs"]
Bc = R[R.section == "B composition"]; Cj = R[R.section == "C joint"]
names = fv.NAMES
P96["a"] = P96.diff_pp.abs()
P96["one"] = ~(((P96.table == "sex") & (P96.bin == "1")) | ((P96.table == "employed (16+)") & (P96.bin == "0")))   # one class per binary attribute
P1 = P96[P96.one]
within = (P1.a <= 5).mean(); within_both = (P96.a <= 5).mean(); npuma = P96[["state", "puma"]].drop_duplicates().shape[0]
sl = {}
for (t, b, lab) in [("household size", "1", "One-person households"), ("household size", "5", "Households of five or more"), ("autos", "0", "Households without a car"),
                    ("income class", "0", "Household income under $25,000"), ("income class", "5", "Household income $150,000 or more"), ("employed (16+)", "1", "Employed persons aged 16 and over")]:
    d = P96[(P96.table == t) & (P96.bin == b)]; x, y = 100 * d.observed.values, 100 * d.model.values; s, c = np.polyfit(x, y, 1)
    sl[lab] = (s, float(np.corrcoef(x, y)[0, 1]), float((y - x).mean()))

def pop_quality(S):
    J = S.J; hh = J["2_marginals_hh"]; pp = J["2_marginals_pp"]; fl = J["12_identifiability_floor_hh"]
    fig = K.new(3.3); gs = fig.add_gridspec(1, 2); a, b = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    names = [f"HH {PL.LAB[k].lower()}" for k in hh] + [f"P {PL.LAB[k].lower()}" for k in pp]
    tv = [hh[k]["tv"] for k in hh] + [pp[k]["tv"] for k in pp]; sr = [hh[k]["srmse"] for k in hh] + [pp[k]["srmse"] for k in pp]
    y = K.rows_axis(a, names); a.grid(axis="x", visible=True)
    a.scatter(tv, y + 0.25, s=14, color=K.MODEL, lw=0, zorder=4); a.scatter(sr, y, s=14, marker="D", facecolor="white", edgecolor=K.MODEL, lw=0.9, zorder=4)
    a.scatter([fl[k] for k in hh], y[:len(hh)] - 0.27, marker="^", s=16, color=K.OBSERVED, lw=0, zorder=3)
    a.set_xlim(0, 0.105); a.set_xticks([0, 0.025, 0.05, 0.075, 0.1]); a.set_xticklabels(["0", "0.025", "0.05", "0.075", "0.1"]); a.set_xlabel("Error against held-out households (–)")
    W = J["3_joints_pp"]["worst_pairs"] + J["3_joints_hh"]["worst_pairs"]; npp = len(J["3_joints_pp"]["worst_pairs"])
    def nm(p_, i):
        for x_, z in [("_bin", ""), ("dwellingType", "dwelling"), ("autos", "cars"), ("driversLicense", "licence"), ("gender", "sex"), ("relationship", "relation"), ("occupation", "occup.")]: p_ = p_.replace(x_, z)
        return ("HH " if i >= npp else "P ") + p_.replace("×", " × ")
    W = sorted([(nm(p_, i), v) for i, (p_, v) in enumerate(W)], key=lambda t: -t[1])[:10]
    y2 = K.rows_axis(b, [n for n, _ in W]); b.grid(axis="x", visible=True)
    b.scatter([v for _, v in W], y2, s=14, marker="D", facecolor="white", edgecolor=K.MODEL, lw=0.9, zorder=4)
    b.set_xlim(0, 0.25); b.set_xticks([0, 0.05, 0.1, 0.15, 0.2, 0.25]); b.set_xlabel("SRMSE (–)")
    K.title(a, "a", "Single attributes"); K.title(b, "b", "Ten largest pair errors")
    K.legend(fig, [K.Line2D([], [], color=K.MODEL, marker="o", ms=K.MS, ls="", label="Total variation distance"),
                   K.Line2D([], [], marker="D", ms=K.MS - 0.5, ls="", mfc="white", mec=K.MODEL, mew=0.9, label="SRMSE"),
                   K.Line2D([], [], marker="^", ms=K.MS - 0.5, ls="", color=K.OBSERVED, label="Sampling floor of SRMSE (two halves)")])
    return K.save(fig, "fig_pop_quality")


doc = Doc("Validation of the synthetic population", "Stage 1 of the Baltimore chain: conditional VAE", WORK)

# ------------------------------------------------------------------ 1 data and targets
doc.section("Data and targets")
nstate = P96.state.nunique(); nmd = R[(R.section == "A counts") & (R.table == "households vs ACS")].shape[0]
doc.para(f"The generator is a conditional variational autoencoder trained on households of the American Community Survey public use microdata (PUMS) and "
         f"conditioned on the PUMA. It produces households with their persons for {npuma} PUMAs in {nstate} states. "
         f"Each household is placed in a zone, and workers receive a job location. The population is the base year 2016 of the land-use model; the job locations "
         f"are those of the land-use model's base year, re-assigned with its workplace choice model.")
doc.para("Controls. In each PUMA the generated households are re-drawn so that the number of households, persons by age band (0--17, 18--34, 35--64, 65 and over) and, with a smaller weight, "
         "households by size match the ACS. Households are placed in zones in proportion to the occupied housing units of the zone. Age and the number of households are therefore controls, "
         "not tests; household size is partly controlled.")
doc.para(f"Targets. Persons and households by attribute: ACS PUMS 2014--2018, 5-year file, households and persons outside group quarters. "
         f"Persons by county: Census population estimates for 2016. Jobs by county: LODES workplace area characteristics, 2016. "
         f"Commute: home-to-work car-driver trips of the 2017/18 Regional Travel Survey. Held-out households: a test split of the PUMS that the generator did not see in training "
         f"({thousands(RES['1_totals']['gen_hh'])} households generated for the comparison).")
doc.para(f"The tests are of three kinds. First, shares of single attributes against the ACS for Maryland and for every PUMA. "
         f"Second, joint distributions of pairs and triples of attributes against held-out households. Third, totals by county for persons and jobs.")

# ------------------------------------------------------------------ 2 marginals
doc.section("Marginal fit, Maryland")
rows = []
for r in MD.itertuples():
    rows.append([tx(r.variable), str(r.k), num(r.tvd, 1), num(r.maxdiff, 1), tx(r.maxcat) + f" ({num(r.maxsigned, 1, sign=True)})"])
doc.table(["Attribute", "Classes", "Distance (pp)", "Largest class gap (pp)", "Class (signed gap)"], rows, "lrrrl",
          "Synthetic population against the ACS PUMS 2014--2018, Maryland, by attribute.",
          note="Distance: total variation distance between the synthetic and the observed shares over the classes, in percentage points (pp). "
               "Class gap: synthetic minus observed share of one class. Income in 2016 dollars. Age band is a control.")
emp = MD.set_index("variable")
doc.para(f"Employment is too low: the employed share of persons aged 16 and over is {abs(emp.loc['employed (16+)', 'maxsigned']):.1f} pp below the ACS, and retired persons are "
         f"{abs(SHp[(SHp.variable == 'employment status') & (SHp.category == 'Retired')].pipe(lambda g: (g.model - g.observed).iloc[0] * 100)):.1f} pp too few. The generator under-represents "
         "the employed in every PUMA (Table 9, Figure 6), and the land-use model starts from this population, so its employed share is also too low.")
fig_cols = ["age band", "employed (16+)", "household size", "cars", "household income (2016 $)", "dwelling type", "tenure", "race and ethnicity", "relationship"]
fig_lab = {"age band": "Age band", "employed (16+)": "Employment, age 16 and over", "household size": "Household size", "cars": "Cars per household",
           "household income (2016 $)": "Household income (2016 $)", "dwelling type": "Dwelling type", "tenure": "Tenure", "race and ethnicity": "Race and ethnicity", "relationship": "Relationship to householder"}
fig, axs = ps.figure(6.4, nrows=5, ncols=2); axs = axs.ravel()
for ax, v in zip(axs, fig_cols):
    g = SH[SH.variable == v]; x = np.arange(len(g)); w = 0.4
    ax.bar(x - w / 2, g.observed * 100, w, color=ps.OBSERVED, lw=0); ax.bar(x + w / 2, g.model * 100, w, color=ps.MODEL, lw=0)
    ax.set_xticks(x); ax.set_xticklabels([c.replace("\\$", "$") for c in g.category], rotation=40, ha="right", rotation_mode="anchor"); ax.grid(axis="x", visible=False)
    ax.set_title(fig_lab[v], loc="left", fontsize=ps.TICK, fontweight="normal", color=ps.INK2); ax.set_title(f"{tvd(g):.1f} pp", loc="right", fontsize=ps.TICK, fontweight="normal", color=ps.INK2)
    ax.set_ylabel("Share (%)")
for ax in axs[len(fig_cols):]: ax.set_axis_off()
axs[-1].set_axis_off()
fig.legend(handles=[K.h_obs_dot("ACS PUMS"), Line2D([], [], color=ps.MODEL, marker="s", ms=5, ls="", label="Synthetic population")], loc="outside upper center", ncol=2)
doc.figure(ps.finish(fig, f"{FIG}/fig_marginals"), "Shares of nine attributes, synthetic population and ACS PUMS, Maryland. The number in each panel is the total variation distance from Table 1, in pp.")

# ------------------------------------------------------------------ 3 joint fit
doc.section("Joint fit")
hh_m, pp_m, fl = RES["2_marginals_hh"], RES["2_marginals_pp"], RES["12_identifiability_floor_hh"]
LAB = {"dwellingType": "dwelling type", "tenure": "tenure", "autos": "cars", "income_bin": "income", "age_bin": "age", "gender": "sex", "race": "race", "occupation": "occupation",
       "driversLicense": "driving licence", "relationship": "relationship", "nationality": "nationality"}
rows = [[f"Household: {LAB[k]}", num(v["tv"], 3), num(v["srmse"], 3), num(fl[k], 3), num(fl[k] / np.sqrt(2), 3)] for k, v in hh_m.items()]
rows += [[f"Person: {LAB[k]}", num(v["tv"], 3), num(v["srmse"], 3), "--", "--"] for k, v in pp_m.items()]
doc.table(["Attribute", "Distance", "SRMSE", hd("Floor,", "two halves"), hd("Floor,", "full split")], rows, "lrrrr", "Generated households against the held-out test split of the PUMS, single attributes.",
          note="Distance: total variation distance, as a share. SRMSE: standardised root-mean-square error. Floor, two halves: SRMSE between two random halves of the test split (households only). "
               "Each half has half the households of the split, so this floor overstates the sampling error of the comparison; the full-split column divides it by $\\sqrt{2}$, an approximation. "
               "Household size is not among the single-attribute tests of the generator; it enters the pair tests (Figure 3) and is partly controlled.",
          midrules=(len(hh_m),))
jp, jh = RES["3_joints_pp"], RES["3_joints_hh"]
pr = PAIRS.dropna(subset=["b"]); med_s, med_t = pr.synthetic.median(), pr.training.median()
rows = [["Persons, single attributes", num(jp["1way_mean_srmse"], 3)], ["Persons, pairs", num(jp["2way_mean_srmse"], 3)], ["Persons, triples", num(jp["3way_mean_srmse"], 3)],
        ["Households, single attributes", num(jh["1way_mean_srmse"], 3)], ["Households, pairs", num(jh["2way_mean_srmse"], 3)],
        [f"All {len(pr)} attribute pairs, median", num(med_s, 3)], ["The same pairs, training split against test split, median", num(med_t, 3)]]
doc.table(["Table", "Mean SRMSE"], rows, "lr", "Joint distributions of generated households against the held-out test split.",
          note="Pairs with a person attribute are formed over persons, with the household attributes of their household.")
worst = pr.sort_values("synthetic", ascending=False).head(6)
PFX = {"age": "P age", "pincome": "P income", "income": "HH income", "occupation": "P occupation", "race": "P race", "gender": "P sex", "relationship": "P relationship", "nationality": "P nationality",
       "driversLicense": "P licence", "autos": "HH cars", "dwellingType": "HH dwelling type", "tenure": "HH tenure", "hhSizeVAE": "HH size", "hhSize": "HH size"}
def pl(v): v = str(v).replace("_bin", ""); return PFX.get(v, v)
rows = [[f"{tx(pl(r.a))} $\\times$ {tx(pl(r.b))}", num(r.synthetic, 3), num(r.training, 3)] for r in worst.itertuples()]
doc.table(["Pair of attributes", "Synthetic", "Training split"], rows, "lrr", "The six attribute pairs with the largest error, over persons and households.",
          note="SRMSE against the held-out test split. HH: household attribute; P: person attribute. Figure 2b shows the ten largest pair errors of the generator's own test, which forms person pairs and household pairs separately.")
Cj_tab = []
for t, lab in [("size x autos", "Household size by cars"), ("income x autos", "Household income by cars")]:
    d = Cj[Cj.table == t]; srm = np.sqrt(((d.model - d.observed) ** 2).mean()) / d.observed.mean()
    Cj_tab.append([lab, str(len(d)), num(srm, 3), num(d.diff_pp.abs().max(), 1)])
doc.table(["Table", "Cells", "SRMSE", "Largest cell gap (pp)"], Cj_tab, "lrrr", "Joint tables of Maryland households against the ACS PUMS.",
          note="Cell gap: synthetic minus observed share of the cell, in percentage points.")
S = S1()
doc.figure(pop_quality(S), "Left: distance and SRMSE of each single attribute against the held-out households, with the sampling floor of two halves (households only). Right: the ten largest pair errors (HH: household, P: person).")
pq = f"{REPORTS}/article/figures/fig_val_pop_quality.pdf"
doc.figure(pq, "SRMSE of every pair of attributes against the held-out test split. Below the diagonal: generated households. Above: the training split.")

# ------------------------------------------------------------------ 4 totals
doc.section("Totals by county")
Am = A.assign(name=A.county.map(names)).sort_values("ratio")
rows = [[tx(r.name), thousands(r.model), thousands(r.observed), num(r.ratio, 3)] for r in Am.itertuples()]
doc.table(["County", "Synthetic persons", "Census estimate", "Ratio"], rows, "lrrr", "Persons in households by Maryland county against the Census estimate of 2016.",
          note="The synthetic population holds persons in households only, while the Census estimate counts all persons; about 2.3\\% of Marylanders live in group quarters, so the expected ratio is about 0.977. "
               "Households are controlled by PUMA and placed in zones by occupied housing units, so a county that shares a PUMA with others can also deviate through this placement.")
doc.para("The ratio is lowest where group quarters are large: Somerset (prisons and a university) and Allegany (prisons and colleges). Other counties deviate through the placement within the PUMA. "
         "Caroline has few group quarters but shares its PUMA with other Eastern Shore counties, and its households are placed in proportion to housing units, not to the persons of each county.")
Dj = R[R.section == "D jobs"]
Dm = Dj.assign(name=Dj.geo.astype(int).map(names)).sort_values("ratio")
rows = [[tx(r.name), thousands(r.model), thousands(r.observed), num(r.ratio, 3)] for r in Dm.itertuples()]
rows.append(["Maryland", thousands(Dj.model.sum()), thousands(Dj.observed.sum()), num(Dj.model.sum() / Dj.observed.sum(), 3)])
doc.table(["County", "Synthetic jobs", "LODES jobs", "Ratio"], rows, "lrrr", "Filled jobs by Maryland county against LODES 2016.", midrules=(len(rows) - 1,),
          note="Synthetic jobs: filled jobs of the land-use base year. Tolerance: 10\\%. LODES counts jobs covered by unemployment insurance and federal civilian jobs at the employer's reported address; "
               "it leaves out the self-employed and uniformed military.")
hi_j = Dm[Dm.ratio > 1.10].sort_values("ratio", ascending=False)
doc.para(f"{len(hi_j)} counties are more than 10\\% above LODES, the largest " + ", ".join(f"{NM} ({r:.2f})" for NM, r in zip(hi_j.name.head(5), hi_j.ratio.head(5))) + ". "
         "The synthetic jobs follow the employed persons of the ACS, who include the self-employed and members of the armed forces; LODES does not. "
         "The gap is largest in counties with military installations (Patuxent River in St Mary's, Aberdeen Proving Ground in Harford) and in rural counties with many self-employed workers.")
doc.figure(PL.population(S), "Left: synthetic minus ACS share of every attribute class, one mark per PUMA. Middle: persons by county; grey band: the expected ratio of 0.977 (persons in households) "
           "plus and minus 5\\%. Right: filled jobs by county; grey band: plus and minus 10\\%. The jobs panel uses the county order of the persons panel. Orange: outside the band. "
           "Age band is a control and lies near zero in every PUMA.")

# ------------------------------------------------------------------ 5 PUMA level
doc.section("Fit by PUMA")
doc.para(f"Composition was compared in {npuma} PUMAs of {nstate} states, {len(P1[['state','puma','table','bin']].drop_duplicates())} cells of PUMA and class in all, counting one class of each binary "
         f"attribute (female; employed). {within * 100:.1f}\\% of the cells are within 5 percentage points of the ACS ({within_both * 100:.1f}\\% when both classes of sex and employment are counted).")
rows = []
for st, g in P1.groupby("state"):
    rows.append([STN[st], str(g.puma.nunique()), num((g.a <= 5).mean(), 1, pct=True), num(g.a.mean(), 2), num(g.a.max(), 1)])
rows.append(["All states", str(npuma), num(within, 1, pct=True), num(P1.a.mean(), 2), num(P1.a.max(), 1)])
doc.table(["State", "PUMAs", "Cells within 5 pp", "Mean gap (pp)", "Largest gap (pp)"], rows, "lrrrr", "Composition by PUMA against the ACS PUMS, by state.",
          note="Gap: absolute difference between the synthetic and the observed share of one class in one PUMA, in percentage points. Classes: age band (a control), female, employed, household size, cars, income.",
          midrules=(len(rows) - 1,))
rows = [[tx(k), num(v[0], 2), num(v[1], 2), num(v[2], 1, sign=True)] for k, v in sl.items()]
doc.table(["Share of", "Slope", "Correlation", "Mean difference (pp)"], rows, "lrrr", "Synthetic share against ACS share across PUMAs, six classes.",
          note="Slope: least-squares slope of the synthetic on the observed share. A slope below one means that the PUMAs are drawn toward the common mean.")
doc.para(f"The PUMAs are drawn toward the common mean. One-person households have a slope of {sl['One-person households'][0]:.2f} and are {abs(sl['One-person households'][2]):.1f} pp too few on average, "
         f"employed persons {sl['Employed persons aged 16 and over'][0]:.2f} and incomes under \\$25,000 {sl['Household income under $25,000'][0]:.2f}; households of five or more have a slope of "
         f"{sl['Households of five or more'][0]:.2f}, and incomes of \\$150,000 or more are {abs(sl['Household income $150,000 or more'][2]):.1f} pp too few. The generator conditions on the PUMA, but its "
         "conditional distributions are smoother than the PUMAs, so PUMAs that differ most from the average differ less in the synthetic population. The land-use model starts from this population; "
         "its county shares of one-person households and of low incomes show the same pattern in the base year and drift with its own events afterwards.")
# scatter figure
ST6 = list(STN); COL = dict(zip(ST6, ps.CAT)); MK = dict(zip(ST6, ["o", "s", "^", "D", "v", "P"]))
PAN = [("household size", "1", "One person"), ("household size", "5", "5+ persons"), ("autos", "0", "No car"), ("income class", "0", "Income under $25k"),
       ("income class", "5", "Income $150k+"), ("employed (16+)", "1", "Employed (16+)")]
fig, axs = ps.figure(5.2, nrows=2, ncols=3)
for ax, (t, b, lab) in zip(axs.flat, PAN):
    d = P96[(P96.table == t) & (P96.bin == b)]; x, y = 100 * d.observed.values, 100 * d.model.values
    s_, c_ = np.polyfit(x, y, 1); hi = float(np.ceil(max(x.max(), y.max()) / 10) * 10)
    ax.plot([0, hi], [0, hi], color=ps.INK2, lw=0.8, zorder=1); ax.plot([0, hi], [c_, c_ + s_ * hi], color=ps.INK2, lw=0.8, ls="--", zorder=1)
    for st in ST6:
        k = d.state.values == st; ax.scatter(x[k], y[k], s=13, color=COL[st], marker=MK[st], lw=0.4, edgecolor="white", zorder=3 if st == 24 else 2)
    lo = float(np.floor(min(x.min(), y.min()) / 10) * 10) if min(x.min(), y.min()) > 30 else 0.0
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    ax.set_title(lab.replace("$", "\\$"), loc="right", fontsize=ps.TICK, fontweight="normal", color=ps.INK2); ax.set_xlabel(f"ACS (%)\nslope {s_:.2f}"); ax.set_ylabel("Synthetic (%)")
h = [Line2D([], [], ls="", marker=MK[s_], color=COL[s_], markersize=5, label=STN[s_]) for s_ in ST6] + [Line2D([], [], color=ps.INK2, lw=0.8, label="Equality"), Line2D([], [], color=ps.INK2, lw=0.8, ls="--", label="Fitted line")]
fig.legend(handles=h, loc="outside lower center", ncol=4)
doc.figure(ps.finish(fig, f"{FIG}/fig_puma_scatter", panel_labels="abcdef"), "Synthetic share against ACS share in each of the PUMAs, six classes. Dashed: least-squares line.")
# heatmap
B_ = P96.rename(columns={"table": "table"}); cols = fv.bin_rows(B_)
order = []
for st in ST6: order += [(st, p) for p in P96[P96.state == st].drop_duplicates("puma").sort_values("households", ascending=False).puma]
Hm = np.array([[P96[(P96.state == s_) & (P96.puma == p) & (P96.table == t) & (P96.bin == b)].diff_pp.iloc[0] for t, b, *_ in cols] for s_, p in order])
fig = ps.new_figure(ps.MAX_HEIGHT); ax = fig.add_subplot(111)
im = fv.heat_groups(ax, Hm, cols, annotate=99)
pos, prev = [], None
for i, (s_, p) in enumerate(order):
    if s_ != prev:
        if prev is not None: ax.axhline(i - 0.5, color="white", lw=2.0)
        pos.append([s_, i, i])
    pos[-1][2] = i; prev = s_
ax.set_yticks([(x_ + y_) / 2 for s_, x_, y_ in pos]); ax.set_yticklabels([f"{STN[s_]} ({y_ - x_ + 1})" for s_, x_, y_ in pos]); ax.set_ylabel("PUMAs by state, largest at the top")
fv.pp_colorbar(fig, im, ax, orientation="horizontal", label=ps.PP_LABEL.replace("\n", " "), fraction=0.03, pad=0.01, aspect=50, shrink=0.6)
doc.figure(ps.finish(fig, f"{FIG}/fig_puma_heat"), "Synthetic minus ACS share for every class and PUMA, in percentage points. Rows are PUMAs grouped by state.")
lv = f"{REPORTS}/article/figures/fig_val_pop_levels.pdf"
doc.figure(lv, "Total variation distance of seven household attributes against held-out households in 96 PUMAs (left) and against ACS tract tables in 411 tract-zone clusters (right), with the sampling floor of the observed data.")
doc.para("Below the PUMA the fit is weaker. In the 411 tract-zone clusters the distance is far above the sampling floor for dwelling type (about 21 pp against a floor of about 4), tenure (about 11 against 2) "
         "and cars (about 10 against 4). The generator draws households for the PUMA, and the placement puts them in zones by the number of housing units only, so a zone receives the PUMA's mix of "
         "single-family and multi-family households, owners and renters. This placement error passes to every later stage: the land-use model starts from these locations, and car ownership and dwelling type "
         "near each zone feed the activity and mode choices of its households.")

# ------------------------------------------------------------------ 6 commute
doc.section("Commute of the synthetic workers")
C = S.C; t_ = C[C.quantity == "time"]; mt = C[C.quantity == "mean_min"].iloc[0]; mk = C[C.quantity == "mean_km"].iloc[0]
iz = float(C[C.quantity == "intrazonal_share"].model.iloc[0]); nwk = int(C[C.quantity == "workers"].model.iloc[0])
d12 = C[(C.quantity == "distance") & (C.bin == "1-2")].iloc[0]
doc.para(f"The workplaces are those of the land-use model's base year ({thousands(nwk)} Maryland workers with a job). Their home-to-work time, from the fixed AM-peak car skim of the statewide model, "
         f"averages {mt.model:.1f} minutes; the reported car-driver commute in the 2017/18 travel survey averages {mt.observed:.1f} minutes. The mean distance is {mk.model:.1f} km against {mk.observed:.1f} km. "
         "The skim is the one all upstream stages read; in the traffic assignment the congested car times are 18--31\\% shorter than this skim, so the agreement of the mean time rests on the skim.")
doc.para(f"The model puts {100 * d12.model:.0f}\\% of the commuters at 1--2 km against {100 * d12.observed:.0f}\\% in the survey. These are mostly workers whose job is in their home zone "
         f"({100 * iz:.0f}\\% of all workers): the skim gives every trip inside a zone a distance of 1 km, so all of them fall into this band, and almost none into 2--3 km, while the survey reports the real distance. "
         "The agreement of the mean distance hides this spike.")
fig = K.new(2.6); ax_ = K.grid(fig, 1, 2)
for ax, q, lab_, ticks in [(ax_[0], "distance", "Commute distance (km)", fv.DIST_TICKS), (ax_[1], "time", "Commute time (min)", None)]:
    d = C[C.quantity == q]; x = np.arange(len(d)); w = 0.4
    ax.bar(x - w / 2, 100 * d.observed.values, w, color=ps.OBSERVED, lw=0); ax.bar(x + w / 2, 100 * d.model.values, w, color=ps.MODEL, lw=0); ax.grid(axis="x", visible=False)
    if ticks is not None: ax.set_xticks(x); ax.set_xticklabels(ticks, rotation=45, ha="right", rotation_mode="anchor")
    else: ax.set_xticks(np.arange(0, 25, 6) - 0.5); ax.set_xticklabels(["0", "30", "60", "90", "120"]); ax.set_xlim(-0.6, len(d) - 0.4)
    ax.set_xlabel(lab_); ax.set_ylabel("Share of commuters (%)")
K.title(ax_[0], "a", "Distance"); K.title(ax_[1], "b", "Time")
K.legend(fig, [Line2D([], [], color=ps.MODEL, marker="s", ms=5, ls="", label="Synthetic workers"), Line2D([], [], color=ps.OBSERVED, marker="s", ms=5, ls="", label="Travel survey 2017/18, car drivers")])
doc.figure(K.save(fig, "fig_commute_bars"), "Home-to-work distance (left; bins of unequal width, as labelled) and time (right; 5-minute bins): synthetic workers of the land-use base year and the 2017/18 travel survey, car drivers.")
pages, errs, over = doc.build(a.out)
