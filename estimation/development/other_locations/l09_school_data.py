#!/usr/bin/env python3 -I
"""Data for the l09 school location tests (new variables; nothing in 2_silo/schoolchoice is changed).

Inputs (public downloads, data/raw; READMEs there): CCD 2024-25 membership 052 (race x grade), directory 029 (charter),
CCD 2017-18 characteristics 129 (magnet), PSS 2023-24 (race counts), IPEDS EF2023A (race, fall 2023), IC2023 (ROOMCAP),
EDFacts school proficiency 2016-17 (fallback 2018-19) for Maryland (msde_reportcard/), RTS 2017/18 person file (race).
School points = 2_silo/schoolchoice/work/school_points.parquet (inventory of the estimation, one point per school x band).

Outputs (next to this script):
  l09_student_race.parquet  person_id, race (0 white non-Hispanic, 1 Black non-Hispanic, 2 Hispanic, 3 other, -1 unknown)
  l09_school_attr.parquet   school point attributes (race counts of the band, charter, magnet, proficiency, dorm capacity)
  l09_zone_attr.parquet     zone x band: enrolment by race, quality (enrolment-weighted mean % proficient of MD public schools of
                            the band, missing flag), charter / magnet enrolment; postsec: commuting / resident enrolment by component
  l09_dorm_share_md.csv     Maryland institutions: enrolment, dormitory capacity, share (top by enrolment)
  l09_data.log
RTS race coding: the flat file mixes two codings.  BMC-region households (1 white, 2 Black, 3 Asian, 6 other, Hispanic origin only
in race_ethnicity_hispanic) and TPB-region households (codebook RACEETHNICITY: 1 Hispanic, 2 Black, 3 Asian, 4 white, 5 other).
The coding is identified by home county (a county is TPB-coded if code 4 is more frequent than code 1 among non-Hispanics)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, json, zipfile, numpy as np, pandas as pd
sys.dont_write_bytecode = True
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/locations"   # HERE: results of this step (data); CODE: this folder
V = WORKSPACE; RAW = f"{V}/data/raw"; W = f"{V}/2_silo/schoolchoice/work"
LOG = open(f"{HERE}/l09_data.log", "w")
def log(s): print(s, flush=True); LOG.write(str(s) + "\n"); LOG.flush()
RC = ["white", "black", "hisp", "other"]
STATES = {"10", "11", "24", "42", "51", "54"}

# ---------------------------------------------------------------- RTS student race
r = pd.read_csv(f"{V}/../ABIT/input/rts/RTS_raw_flat_data.csv", usecols=["person_id", "household_id", "race_ethnicity", "race_ethnicity_hispanic", "home_state_county_fips"],
                low_memory=False).drop_duplicates("person_id")
nh = r[r.race_ethnicity_hispanic != 1]
cc = nh.groupby("home_state_county_fips").race_ethnicity.agg(c4=lambda x: (x == 4).sum(), c1=lambda x: (x == 1).sum())
tpb_cty = set(cc.index[cc.c4 > cc.c1]); tpb = r.home_state_county_fips.isin(tpb_cty).values
code = r.race_ethnicity.values; hf = r.race_ethnicity_hispanic.values
hisp = (hf == 1) | (tpb & (code == 1))
white = ~hisp & ((~tpb & (code == 1)) | (tpb & (code == 4)))
black = ~hisp & (code == 2)
unk = ~hisp & (code == -9)
race = np.select([white, black, hisp, unk], [0, 1, 2, -1], 3)
SR = pd.DataFrame({"person_id": r.person_id.values, "race": race})
P = pd.read_parquet(f"{W}/students.parquet")
SR = SR[SR.person_id.isin(P.person_id)]; SR.to_parquet(f"{HERE}/l09_student_race.parquet", index=False)
t = SR.merge(P[["person_id", "seg", "half"]]).groupby(["seg", "half"]).race.value_counts().unstack(fill_value=0)
log("RTS students by race (0 white NH, 1 Black NH, 2 Hispanic, 3 other, -1 unknown):\n" + t.to_string())
log(f"TPB-coded home counties: {sorted(tpb_cty)}")

# ---------------------------------------------------------------- school points
S = pd.read_parquet(f"{W}/school_points.parquet")
S["sid"] = S.source_id.astype(str).str.replace(r"\.0$", "", regex=True)
pubm = (S.sector == "public"); prvm = (S.sector == "private"); psm = (S.band == "postsec")
S.loc[pubm, "sid"] = S.loc[pubm, "sid"].str.zfill(12)

# public race by band (CCD 052 2024-25, Category Set A), cached extract
cache = f"{HERE}/l09_ccd052_race_extract.parquet"
GB = {"Kindergarten": "elementary", **{f"Grade {g}": "elementary" for g in range(1, 6)}, **{f"Grade {g}": "middle" for g in range(6, 9)},
      **{f"Grade {g}": "high" for g in range(9, 14)}}
RMAP = {"White": "white", "Black or African American": "black", "Hispanic/Latino": "hisp"}
if not os.path.exists(cache):
    import subprocess   # the 052 zip uses Deflate64 (not supported by zipfile): stream with unzip -p
    zp = f"{RAW}/nces/ccd_sch_052_2425_l_1a_073025.zip"; fn = "ccd_sch_052_2425_l_1a_073025.csv"; parts = []
    pr = subprocess.Popen(["unzip", "-p", zp, fn], stdout=subprocess.PIPE)
    for ch in pd.read_csv(pr.stdout, usecols=["FIPST", "NCESSCH", "GRADE", "RACE_ETHNICITY", "STUDENT_COUNT", "TOTAL_INDICATOR"], dtype=str, chunksize=2_000_000):
        ch = ch[ch.FIPST.isin(STATES) & ch.TOTAL_INDICATOR.str.startswith("Category Set A")]
        ch = ch.assign(n=pd.to_numeric(ch.STUDENT_COUNT, errors="coerce").fillna(0))
        parts.append(ch.groupby(["NCESSCH", "GRADE", "RACE_ETHNICITY"]).n.sum().reset_index())
    X = pd.concat(parts).groupby(["NCESSCH", "GRADE", "RACE_ETHNICITY"]).n.sum().reset_index(); X.to_parquet(cache, index=False)
X = pd.read_parquet(cache)
log(f"CCD 052 race labels: {sorted(X.RACE_ETHNICITY.unique())}")
X = X[X.RACE_ETHNICITY != "Not Specified"].copy()
X["band"] = X.GRADE.map(GB); X["r"] = X.RACE_ETHNICITY.map(RMAP).fillna("other")
sb = X.dropna(subset=["band"]).pivot_table(index=["NCESSCH", "band"], columns="r", values="n", aggfunc="sum", fill_value=0).reindex(columns=RC, fill_value=0)
sa = X.pivot_table(index="NCESSCH", columns="r", values="n", aggfunc="sum", fill_value=0).reindex(columns=RC, fill_value=0)   # all grades
def shares(tab):
    tt = tab.sum(1); return tab[tt > 0].div(tt[tt > 0], axis=0)
shb, sha = shares(sb), shares(sa)
for c in RC: S[f"sh_{c}"] = np.nan
key = list(zip(S.sid, S.band)); idx_b = shb.index
for i in np.flatnonzero(pubm.values):
    k = key[i]
    if k in idx_b: S.loc[S.index[i], [f"sh_{c}" for c in RC]] = shb.loc[k].values
    elif k[0] in sha.index: S.loc[S.index[i], [f"sh_{c}" for c in RC]] = sha.loc[k[0]].values
# private: PSS 2023-24 school race counts (P330 white, P325 Black, P320 Hispanic; others; checked against county composition)
pss = pd.read_csv(zipfile.ZipFile(f"{RAW}/nces/pss2324_pu_csv.zip").open("pss2324_pu.csv"), low_memory=False, encoding="latin1",
                  usecols=["PPIN", "P310", "P316", "P318", "P320", "P325", "P330", "P332", "NUMSTUDS"])
pss["white"], pss["black"], pss["hisp"] = pss.P330, pss.P325, pss.P320; pss["other"] = pss[["P310", "P316", "P318", "P332"]].sum(axis=1)
ps = shares(pss.set_index(pss.PPIN.astype(str))[RC])
m = prvm.values & S.sid.isin(ps.index).values
S.loc[m, [f"sh_{c}" for c in RC]] = ps.loc[S.sid[m]].values
# post-secondary: IPEDS EF2023A all students (EFALEVEL 1); unknown race excluded, non-resident aliens -> other
ef = pd.read_csv(zipfile.ZipFile(f"{RAW}/ipeds/EF2023A.zip").open("ef2023a.csv" if "ef2023a.csv" in zipfile.ZipFile(f"{RAW}/ipeds/EF2023A.zip").namelist() else zipfile.ZipFile(f"{RAW}/ipeds/EF2023A.zip").namelist()[0]),
                 low_memory=False, encoding="latin1")
ef.columns = [c.strip().replace("﻿", "").replace("ï»¿", "") for c in ef.columns]; ef = ef[ef.EFALEVEL == 1].set_index("UNITID")
ef["white"], ef["black"], ef["hisp"] = ef.EFWHITT, ef.EFBKAAT, ef.EFHISPT; ef["other"] = ef.EFTOTLT - ef.EFUNKNT - ef.white - ef.black - ef.hisp
es = shares(ef[RC].clip(lower=0)); es.index = es.index.astype(str)
m = psm.values & S.sid.isin(es.index).values
S.loc[m, [f"sh_{c}" for c in RC]] = es.loc[S.sid[m]].values
for c in RC: S[f"n_{c}"] = S[f"sh_{c}"] * S.capacity
S["race_ok"] = S.sh_white.notna()
log("race composition coverage (share of enrolment with race data) by band x sector:\n"
    + S.groupby(["band", "sector"]).apply(lambda g: g.capacity[g.race_ok].sum() / g.capacity.sum()).round(3).to_string())

# charter (CCD 029 2024-25) and magnet (CCD 129 2017-18)
d29 = pd.read_csv(zipfile.ZipFile(f"{RAW}/nces/ccd_sch_029_2425_w_1a_073025.zip").open("ccd_sch_029_2425_w_1a_073025.csv"), usecols=["NCESSCH", "CHARTER_TEXT"], dtype=str, encoding="latin1")
ch = set(d29.NCESSCH[d29.CHARTER_TEXT == "Yes"])
z129 = zipfile.ZipFile(f"{RAW}/nces/ccd_sch_129_1718_w_1a_083118.zip")
d129 = pd.read_csv(z129.open([n for n in z129.namelist() if n.endswith(".csv")][0]), usecols=["NCESSCH", "MAGNET_TEXT"], dtype=str, encoding="latin1")
mg = set(d129.NCESSCH[d129.MAGNET_TEXT == "Yes"])
S["charter"] = (pubm & S.sid.isin(ch)).astype(int); S["magnet"] = (pubm & S.sid.isin(mg)).astype(int)
log("charter / magnet enrolment share of the public enrolment, by band (MSTM states):\n"
    + S[pubm].groupby("band").apply(lambda g: pd.Series({"charter": (g.capacity * g.charter).sum() / g.capacity.sum(), "magnet": (g.capacity * g.magnet).sum() / g.capacity.sum()})).round(3).to_string())
log("Maryland: " + S[pubm & (S.state_fips == 24)].groupby("band").apply(lambda g: pd.Series({"charter": (g.capacity * g.charter).sum() / g.capacity.sum(), "magnet": (g.capacity * g.magnet).sum() / g.capacity.sum()})).round(3).to_string())

# quality: % proficient (mean of ELA and math), 2016-17, fallback 2018-19; Maryland public schools only
def edf(y):
    q = pd.DataFrame(json.load(open(f"{RAW}/msde_reportcard/edfacts_assessments_md_{y}_grade99.json"))["results"])
    q = q[(q.race == 99) & (q.sex == 99) & (q.disability == 99) & (q.econ_disadvantaged == 99) & (q.lep == 99)]
    a = q.read_test_pct_prof_midpt.where(q.read_test_pct_prof_midpt >= 0); b = q.math_test_pct_prof_midpt.where(q.math_test_pct_prof_midpt >= 0)
    return pd.Series(pd.concat([a, b], axis=1).mean(axis=1).values, index=q.ncessch.astype(str).str.zfill(12)).dropna()
q16, q18 = edf(2016), edf(2018)
md = pubm & (S.state_fips == 24)
S["prof"] = np.where(md, S.sid.map(q16), np.nan); S["prof_src"] = np.where(S.prof.notna(), "2016-17", "")
fb = md & S.prof.isna() & S.sid.isin(q18.index); S.loc[fb, "prof"] = S.loc[fb, "sid"].map(q18); S.loc[fb, "prof_src"] = "2018-19"
log("MD public school points with proficiency: " + S[md].groupby("band").apply(lambda g: f"{g.prof.notna().sum()}/{len(g)} points, "
    f"{g.capacity[g.prof.notna()].sum() / g.capacity.sum():.3f} of enrolment ({(g.prof_src == '2018-19').sum()} from 2018-19)").to_string())
log("proficiency (% proficient, mean ELA/math) of MD public points: " + S.loc[md, "prof"].describe().round(1).to_dict().__repr__())

# dormitory capacity (IPEDS IC2023, ROOMCAP; ROOM = 1 provides housing)
ic = pd.read_csv(zipfile.ZipFile(f"{RAW}/ipeds/IC2023.zip").open("IC2023_RV.csv"), low_memory=False, encoding="latin1")
ic.columns = [c.strip().replace("﻿", "").replace("ï»¿", "") for c in ic.columns]
ic["roomcap"] = pd.to_numeric(ic.ROOMCAP, errors="coerce").where(ic.ROOM == 1, 0).fillna(0)
S["roomcap"] = 0.0; S.loc[psm, "roomcap"] = S.loc[psm, "sid"].map(ic.set_index(ic.UNITID.astype(str)).roomcap).fillna(0).values
S["res"] = np.minimum(S.roomcap, S.capacity); S["commute"] = S.capacity - S.res
S.to_parquet(f"{HERE}/l09_school_attr.parquet", index=False)
dm = S[psm & (S.state_fips == 24)].assign(dorm_share=lambda d: d.res / d.capacity).sort_values("capacity", ascending=False)
dm[["name", "comp", "zone", "capacity", "roomcap", "dorm_share"]].to_csv(f"{HERE}/l09_dorm_share_md.csv", index=False)
log(f"post-secondary: dormitory share of enrolment {S.loc[psm, 'res'].sum() / S.loc[psm, 'capacity'].sum():.3f} (MSTM), Maryland "
    f"{dm.res.sum() / dm.capacity.sum():.3f}; by component:\n" + S[psm].groupby("comp").apply(lambda g: g.res.sum() / g.capacity.sum()).round(3).to_string())
log("Maryland institutions with the highest dormitory share (enrolment >= 1,000):\n"
    + dm[dm.capacity >= 1000].sort_values("dorm_share", ascending=False).head(15)[["name", "comp", "capacity", "roomcap", "dorm_share"]].round(3).to_string(index=False))

# ---------------------------------------------------------------- zone x band aggregates
S["w_prof"] = np.where(S.prof.notna(), S.capacity, 0.0); S["prof_x"] = S.w_prof * S.prof.fillna(0)
for c in RC: S[f"n_{c}"] = S[f"n_{c}"].fillna(0)
S["n_race"] = np.where(S.race_ok, S.capacity, 0.0); S["n_charter"] = S.capacity * S.charter; S["n_magnet"] = S.capacity * S.magnet
agg = S.groupby(["zone", "band"]).agg(n=("capacity", "sum"), n_race=("n_race", "sum"), **{f"n_{c}": (f"n_{c}", "sum") for c in RC},
                                      w_prof=("w_prof", "sum"), prof_x=("prof_x", "sum"), n_charter=("n_charter", "sum"), n_magnet=("n_magnet", "sum")).reset_index()
agg["qual"] = np.where(agg.w_prof > 0, agg.prof_x / agg.w_prof.where(agg.w_prof > 0, 1), np.nan)
for c in ("pub4", "priv4", "cc"):
    g = S[psm & (S.comp == c)].groupby("zone")[["commute", "res"]].sum()
    agg[f"commute_{c}"] = agg.zone.map(g.commute).where(agg.band == "postsec").fillna(0); agg[f"res_{c}"] = agg.zone.map(g.res).where(agg.band == "postsec").fillna(0)
agg.to_parquet(f"{HERE}/l09_zone_attr.parquet", index=False)
log(f"zone x band rows {len(agg)}; zones with quality by band: {agg[agg.qual.notna()].groupby('band').size().to_dict()}")
