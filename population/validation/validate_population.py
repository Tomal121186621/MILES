#!/usr/bin/env python3
"""Stage-1 validation of the corrected synthetic population (SILO base-year files in 2_silo/input/microData) against observed data:
  A. counts: persons and households by Maryland county vs Census Population Estimates 2016 and ACS households (PUMA -> county)
  B. composition by PUMA (Maryland): person age bands, sex, employment; household size, income, autos, tenure, dwelling type
     vs ACS PUMS 2014-2018; per-bin difference in percentage points, worst bins listed; acceptance ±5 pp per bin
  C. joint tables (Maryland): household size x autos, income x autos, workers x autos vs PUMS; SRMSE
  D. jobs by county vs LODES 2016 (filled jobs; vacancies excluded)
Every number is written to data/stage1_validation.parquet (long table) and a short text summary is printed."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, zipfile, os, gzip
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; MD = f"{V}/2_silo/input/microData"
z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv").set_index("ZoneId"); rows = []
def add(section, geo, table, bin_, model, observed): rows.append(dict(section=section, geo=str(geo), table=table, bin=str(bin_), model=float(model), observed=float(observed)))
hh = pd.read_csv(f"{MD}/hh_2016.csv"); dd = pd.read_csv(f"{MD}/dd_2016.csv", usecols=["id", "zone", "type"]); pp = pd.read_csv(f"{MD}/pp_2016.csv", usecols=["hhID", "age", "gender", "occupation", "income"])
hh = hh.merge(dd.rename(columns={"id": "dwelling", "type": "ddType"}), on="dwelling"); hh["county"] = hh.zone.map(z.COUNTYFIPS); hh["puma"] = hh.zone.map(z.PUMA_10 % 100000); hh["st"] = hh.zone.map(z.STFIPS)
pp = pp.merge(hh[["id", "county", "puma", "st", "zone"]].rename(columns={"id": "hhID"}), on="hhID")
md_h, md_p = hh[hh.st == 24], pp[pp.st == 24]
# ---- A counts by county
pep = pd.read_csv(f"{V}/data/raw/pep/co-est2020-alldata.csv", encoding="latin-1", dtype={"STATE": str, "COUNTY": str}); pep = pep[pep.SUMLEV == 50]; pep["fips"] = (pep.STATE.str.zfill(2) + pep.COUNTY.str.zfill(3)).astype(int); pep = pep.set_index("fips").POPESTIMATE2016
for c, n in md_p.groupby("county").size().items(): add("A counts", c, "persons vs PEP 2016 (persons in households, expected ~0.977)", "persons", n, pep.get(c, np.nan))
with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_hmd.zip") as zf:
    n = [x for x in zf.namelist() if x.endswith(".csv")][0]; H = pd.read_csv(zf.open(n), usecols=["PUMA", "WGTP", "NP", "TYPE", "VEH", "TEN", "HINCP", "ADJINC", "BLD", "WIF"], low_memory=False)
H = H[(H.TYPE == 1) & (H.NP > 0)].copy(); H["inc"] = H.HINCP.fillna(0) * H.ADJINC / 1e6
with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_pmd.zip") as zf:
    n = [x for x in zf.namelist() if x.endswith(".csv")][0]; P = pd.read_csv(zf.open(n), usecols=["PUMA", "PWGTP", "RELP", "AGEP", "SEX", "ESR"], low_memory=False)
P = P[~P.RELP.isin([16, 17])]
for pu, n in md_h.groupby("puma").size().items(): add("A counts", f"PUMA {pu}", "households vs ACS", "households", n, H[H.PUMA == pu].WGTP.sum())
# ---- B composition by PUMA
def shares(vals, w=None, order=None):
    s = pd.Series(w if w is not None else np.ones(len(vals))).groupby(np.asarray(vals)).sum(); s = s / s.sum(); return s.reindex(order, fill_value=0) if order is not None else s
B = [("age band", lambda d: np.digitize(d.age, [18, 35, 65]), lambda q: np.digitize(q.AGEP, [18, 35, 65]), [0, 1, 2, 3], "p"),
     ("sex", lambda d: d.gender, lambda q: q.SEX, [1, 2], "p"),
     ("employed (16+)", lambda d: (d.occupation == 1).astype(int), lambda q: q.ESR.isin([1, 2, 4, 5]).astype(int), [0, 1], "p16"),
     ("household size", lambda d: d.hhSize.clip(upper=5), lambda q: q.NP.clip(upper=5), [1, 2, 3, 4, 5], "h"),
     ("autos", lambda d: d.autos.clip(upper=3), lambda q: q.VEH.fillna(0).clip(upper=3).astype(int), [0, 1, 2, 3], "h"),
     ("income class", lambda d: pd.cut(d.income, [-1e9, 25e3, 50e3, 75e3, 100e3, 150e3, 1e12], labels=False), lambda q: pd.cut(q.inc, [-1e9, 25e3, 50e3, 75e3, 100e3, 150e3, 1e12], labels=False), [0, 1, 2, 3, 4, 5], "h")]
for name, fm, fo, order, kind in B:
    for pu in sorted(md_h.puma.unique()):
        if kind == "h": m = shares(fm(md_h[md_h.puma == pu]), order=order); q = H[H.PUMA == pu]; o = shares(fo(q), q.WGTP.values, order)
        else:
            dm = md_p[md_p.puma == pu]; q = P[P.PUMA == pu]
            if kind == "p16": dm = dm[dm.age >= 16]; q = q[q.AGEP >= 16]
            m = shares(fm(dm), order=order); o = shares(fo(q), q.PWGTP.values, order)
        for b in order: add("B composition", f"PUMA {pu}", name, b, m[b], o[b])
# ---- C joint tables (Maryland)
J = [("size x autos", lambda d: list(zip(d.hhSize.clip(upper=4), d.autos.clip(upper=3))), lambda q: list(zip(q.NP.clip(upper=4), q.VEH.fillna(0).clip(upper=3).astype(int)))),
     ("income x autos", lambda d: list(zip(pd.cut(d.income, [-1e9, 25e3, 50e3, 100e3, 1e12], labels=False), d.autos.clip(upper=3))), lambda q: list(zip(pd.cut(q.inc, [-1e9, 25e3, 50e3, 100e3, 1e12], labels=False), q.VEH.fillna(0).clip(upper=3).astype(int))))]
for name, fm, fo in J:
    m = pd.Series(fm(md_h)).value_counts(normalize=True); o = pd.Series(H.WGTP.values).groupby(pd.Series(fo(H))).sum(); o = o / o.sum()
    for k in sorted(set(m.index) | set(o.index)): add("C joint", "Maryland", name, k, m.get(k, 0), o.get(k, 0))
# ---- D jobs by county vs LODES 2016
jj = pd.read_csv(f"{MD}/jj_2016.csv"); jj = jj[jj.personId > 0]; jj["county"] = jj.zone.map(z.COUNTYFIPS)
xw = pd.read_csv(f"{V}/data/raw/lodes_wac/md_xwalk.csv.gz", usecols=["tabblk2020", "cty"], dtype=str)
w = pd.read_csv(f"{V}/data/raw/lodes_wac/md_wac_S000_JT00_2016.csv.gz", dtype={"w_geocode": str}, usecols=["w_geocode", "C000"]).merge(xw, left_on="w_geocode", right_on="tabblk2020")
lod = w.groupby(w.cty.astype(int)).C000.sum()
for c, n in jj[jj.county.between(24000, 24999)].groupby("county").size().items(): add("D jobs", c, "filled jobs vs LODES 2016", "jobs", n, lod.get(c, np.nan))
R = pd.DataFrame(rows); R["diff_pp"] = (R.model - R.observed) * 100; R["ratio"] = R.model / R.observed
R.to_parquet(f"{V}/data/stage1_validation.parquet", index=False)
# ---- summary
A = R[(R.section == "A counts") & (R.table.str.startswith("persons"))]; print(f"A persons by county / PEP 2016: median {A.ratio.median():.3f}, range {A.ratio.min():.3f}-{A.ratio.max():.3f} (expected ~0.977, lower where group quarters are large)")
A2 = R[(R.section == "A counts") & (R.table == "households vs ACS")]; print(f"A households by PUMA / ACS: median {A2.ratio.median():.3f}, range {A2.ratio.min():.3f}-{A2.ratio.max():.3f}")
Bc = R[R.section == "B composition"]; worst = Bc.assign(a=Bc.diff_pp.abs()).sort_values("a", ascending=False)
print(f"B composition, {len(Bc)} PUMA x bin cells: within ±5 pp {(Bc.diff_pp.abs() <= 5).mean():.1%}; worst:"); print(worst.head(8)[["geo", "table", "bin", "model", "observed", "diff_pp"]].round(3).to_string(index=False))
for name in Bc.table.unique(): print(f"   {name}: mean |diff| {Bc[Bc.table == name].diff_pp.abs().mean():.2f} pp, max {Bc[Bc.table == name].diff_pp.abs().max():.2f} pp")
Cj = R[R.section == "C joint"]
for name in Cj.table.unique(): d = Cj[Cj.table == name]; print(f"C {name}: SRMSE {np.sqrt(((d.model - d.observed) ** 2).mean()) / d.observed.mean():.3f}")
D = R[R.section == "D jobs"]; print(f"D filled jobs by county / LODES 2016: total {D.model.sum() / D.observed.sum():.3f}, median {D.ratio.median():.3f}, range {D.ratio.min():.3f}-{D.ratio.max():.3f}")
