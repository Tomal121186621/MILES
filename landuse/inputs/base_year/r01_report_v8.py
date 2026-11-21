"""base_v8 report (2026-11-16b): the SILO base files of run/base_v8/microData against ACS PUMS 2014-18, six study counties (Baltimore City =
24510) and their total: households, persons (in households), mean size, one-person share, dwellings (occupied + vacant), vacancy, licence
16+ (ACS has no licence item: reference = RTS 2017-18 estimation half, weighted, the target source of the base licence step), and the
ACS-style table household size (1, 2, 3, 4+) x vehicles available (0, 1, 2, 3+) = B08201 computed from PUMS (WGTP, VEH; check only).
ACS vacancy: market vacant units (VACS 1-4, the definition of the base's vacant stock) and all vacant units, over occupied + vacant.
Outputs: base_v8/r01_report_v8.csv, base_v8/r01_size_x_cars_v8.csv (+ printed)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, zipfile, os
ROOT = PROJECT_ROOT; V = f"{WORKSPACE}"; HERE = f"{WORKSPACE}/2_silo/input_build/base_v8"
MD = f"{V}/2_silo/run/base_v8/microData"; SIX = [24003, 24005, 24013, 24025, 24027, 24510]
GEOS = [(str(c), [c]) for c in SIX[:-1]] + [("Baltimore City", [24510]), ("six counties", SIX)]
z = pd.read_csv(f"{V}/2_silo/input/zoneSystem.csv", usecols=["ZoneId", "COUNTYFIPS"]).set_index("ZoneId").COUNTYFIPS
dd = pd.read_csv(f"{MD}/dd_2016.csv", usecols=["id", "zone", "hhID"]); dd["county"] = dd.zone.map(z)
hh = pd.read_csv(f"{MD}/hh_2016.csv", usecols=["id", "dwelling", "hhSize", "autos"]); hh["county"] = hh.dwelling.map(dd.set_index("id").county)
pp = pd.read_csv(f"{MD}/pp_2016.csv", usecols=["hhID", "age", "driversLicense"]); pp["county"] = pp.hhID.map(hh.set_index("id").county)
pp["lic"] = pp.driversLicense.astype(str).str.lower().eq("true")
# ---- ACS PUMS 2014-18 (PUMAs of the study counties nest in them)
pcty = {**{p: 24003 for p in (1201, 1202, 1203, 1204)}, **{p: 24005 for p in range(501, 508)}, 400: 24013, 601: 24025, 602: 24025, 901: 24027, 902: 24027, **{p: 24510 for p in range(801, 806)}}
with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_hmd.zip") as zf:
    n = [x for x in zf.namelist() if x.endswith(".csv")][0]; H = pd.read_csv(zf.open(n), usecols=["PUMA", "WGTP", "NP", "TYPE", "VEH", "VACS"], low_memory=False)
with zipfile.ZipFile(f"{ROOT}/inputs/pums_2018_5yr/csv_pmd.zip") as zf:
    n = [x for x in zf.namelist() if x.endswith(".csv")][0]; Pm = pd.read_csv(zf.open(n), usecols=["PUMA", "PWGTP", "RELP"], low_memory=False)
H = H[H.TYPE == 1].copy(); H["county"] = H.PUMA.map(pcty).fillna(0).astype(int); Ho = H[H.NP > 0]; Hv = H[H.NP == 0]
Pm = Pm[~Pm.RELP.isin([16, 17])].copy(); Pm["county"] = Pm.PUMA.map(pcty).fillna(0).astype(int)
sp = f"{V}/3_abit/survey_pop/estimation"; q = pd.read_csv(f"{sp}/pp.csv", usecols=["id", "age", "driversLicense"]).merge(pd.read_csv(f"{sp}/persons_map.csv", usecols=["id", "w", "county"]), on="id")
q = q[q.age >= 16]; q["lic"] = q.driversLicense.astype(str).str.lower().eq("true")
SZ = lambda s: np.minimum(np.asarray(s), 4); CR = lambda c: np.minimum(np.asarray(c), 3)
rows, xt = [], []
for g, cs in GEOS:
    h = hh[hh.county.isin(cs)]; d = dd[dd.county.isin(cs)]; p = pp[pp.county.isin(cs)]; p16 = p[p.age >= 16]
    rows.append(dict(geo=g, source="v8", households=len(h), persons=int(h.hhSize.sum()), mean_size=h.hhSize.mean(), one_person=(h.hhSize == 1).mean(),
                     dwellings=len(d), vacancy=(d.hhID <= 0).mean(), licence_16plus=p16.lic.mean()))
    a = Ho[Ho.county.isin(cs)]; v = Hv[Hv.county.isin(cs)]; mk = v.WGTP[v.VACS.isin([1, 2, 3, 4])].sum(); qq = q[q.county.isin(cs)]
    rows.append(dict(geo=g, source="ACS 2014-18", households=a.WGTP.sum(), persons=Pm.PWGTP[Pm.county.isin(cs)].sum(), mean_size=(a.NP * a.WGTP).sum() / a.WGTP.sum(),
                     one_person=a.WGTP[a.NP == 1].sum() / a.WGTP.sum(), dwellings=a.WGTP.sum() + v.WGTP.sum(), dwellings_market=a.WGTP.sum() + mk,
                     vacancy=mk / (a.WGTP.sum() + mk), vacancy_all=v.WGTP.sum() / (a.WGTP.sum() + v.WGTP.sum()),
                     licence_16plus=np.average(qq.lic, weights=qq.w)))
    for src, s_, c_, w_ in [("v8", h.hhSize, h.autos, np.ones(len(h))), ("ACS 2014-18", a.NP, a.VEH.fillna(0), a.WGTP.values.astype(float))]:
        T = pd.crosstab(SZ(s_), CR(c_), values=w_, aggfunc="sum").reindex(index=[1, 2, 3, 4], columns=[0, 1, 2, 3]).fillna(0)
        for si in T.index:
            for ci in T.columns: xt.append(dict(geo=g, source=src, size=si, cars=ci, households=T.at[si, ci], share_of_size=T.at[si, ci] / T.loc[si].sum(), share_of_all=T.at[si, ci] / T.values.sum()))
R = pd.DataFrame(rows); R.to_csv(f"{HERE}/r01_report_v8.csv", index=False); X = pd.DataFrame(xt); X.to_csv(f"{HERE}/r01_size_x_cars_v8.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print("licence reference for ACS rows: RTS 2017-18 estimation half (ACS has no licence item); ACS vacancy = market vacant (VACS 1-4), vacancy_all = all vacant")
print(R.round(4).to_string(index=False))
W = X.pivot_table(index=["geo", "size"], columns=["source", "cars"], values="share_of_size", sort=False) * 100
print("\nP(cars | household size) %, v8 vs ACS 2014-18 (B08201 from PUMS); last block = v8 - ACS (pp)")
D = W["v8"] - W["ACS 2014-18"]; print(pd.concat({"v8": W["v8"], "ACS": W["ACS 2014-18"], "diff": D}, axis=1).round(1).to_string())
