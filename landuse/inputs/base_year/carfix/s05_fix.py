# base_v8 (2026-11-16b): copy of base_v7/carfix/s05_fix.py with v7 -> v8; licence-selection logit without the fewer_cars covariate (zero_car kept); cars step unchanged
# base_v8 (2026-11-15d) copy of input_build/carfix_1115/s05_fix.py: unchanged, new work dir
"""Corrected base: (1) cars re-assigned within Maryland county x persons-16+ cells to the ACS PUMS 2014-18 joint (IPF to the synthetic
adults and cars margins of the county, rank-preserving by the original car count, ties by the ACS expected cars given adults x workers x
income class); (2) driver's licences brought to the RTS 2017-18 estimation-half rates by age band x area (Baltimore City, other study
counties, rest of Maryland), persons chosen by a licence logit fitted on the same survey half; car-owning households keep >= 1 licence.
Output: new licence / cars vectors (parquet) for s06_write.py."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os  # PROJECT_ROOT
from common import *
import statsmodels.api as sm
V = WORKSPACE
rng = np.random.default_rng(1115)
hh = pd.read_parquet(f"{OUT}/hh_base.parquet"); pp = pd.read_parquet(f"{OUT}/pp_base.parquet")
H = pd.read_parquet(f"{OUT}/acs1418_h.parquet"); zw = pd.read_parquet(f"{OUT}/county_puma_w.parquet")
zw["frac"] = zw.n / zw.groupby("puma").n.transform("sum")      # share of the PUMA's zones in the county (households of a PUMA counted once)
A = H.merge(zw, left_on="PUMA", right_on="puma"); A["w"] = A.WGTP * A.frac
ad4 = lambda a: np.minimum(np.asarray(a), 4)                    # persons 16+: 1, 2, 3, 4+
INC = [-1e18, 25e3, 50e3, 75e3, 100e3, 150e3, 1e18]
icl = lambda x: np.digitize(np.asarray(x, float), INC[1:-1])
# ACS expected cars by adults x workers x income class (statewide), tie-break score
A["a4"] = ad4(A.adults); A["w3"] = np.minimum(A.workers, 3); A["ic"] = icl(A.inc16)
E = A.groupby(["a4", "w3", "ic"]).apply(lambda g: np.average(g.cars, weights=g.w)).rename("ecars")
PST = pd.crosstab(A.a4, A.cars, values=A.w, aggfunc="sum", normalize="index")       # statewide P(cars | adults), smoothing prior
md = hh.st == 24
hh["a4"] = ad4(hh.adults); hh["w3"] = np.minimum(hh.workers, 3); hh["ic"] = icl(hh.pinc)
hh["score"] = E.reindex(pd.MultiIndex.from_arrays([hh.a4, hh.w3, hh.ic])).values
hh["score"] = hh.score.fillna(hh.groupby("a4").score.transform("mean")).fillna(0)
hh["u"] = rng.random(len(hh)); hh["cars_new"] = hh.autos
log = []
for c in sorted(hh[md].county.unique()):
    idx = md & (hh.county == c) & (hh.adults >= 1); s = hh[idx]; a = A[A.county == c]
    row = s.groupby("a4").size().reindex([1, 2, 3, 4], fill_value=0).astype(float); col = s.groupby("autos").size().reindex(range(4), fill_value=0).astype(float)
    W = pd.crosstab(a.a4, a.cars, values=a.w, aggfunc="sum").reindex(index=[1, 2, 3, 4], columns=range(4)).fillna(0)
    seed = W.values + 30 * a.w.mean() * PST.reindex(index=[1, 2, 3, 4], columns=range(4)).fillna(0).values + 1e-9
    T = seed.copy()
    for _ in range(500):
        T *= (row.values / T.sum(1))[:, None]; T *= (col.values / T.sum(0))[None, :]
        if np.abs(T.sum(1) - row.values).max() < 1e-6: break
    N = np.floor(T).astype(int)                                   # integer cells: largest remainder within each adults row (rows exact)
    for i in range(4):
        k = int(row.values[i] - N[i].sum())
        if k > 0: N[i, np.argsort(-(T[i] - N[i]))[:k]] += 1
    for i, ai in enumerate([1, 2, 3, 4]):
        g = s[s.a4 == ai].sort_values(["autos", "score", "u"])
        hh.loc[g.index, "cars_new"] = np.repeat(np.arange(4), N[i])
    log.append(dict(county=c, changed=float((hh.loc[idx, "cars_new"] != hh.loc[idx, "autos"]).mean()), col_dev=int(np.abs(N.sum(0) - col.values).sum())))
L = pd.DataFrame(log); print("households with a changed car count (Maryland, by county):", L.changed.round(3).tolist(), "car margin deviation (households):", L.col_dev.sum())
# ---------- licences
sp = f"{V}/3_abit/survey_pop/estimation"
q = pd.read_csv(f"{sp}/pp.csv", usecols=["id", "hhID", "age", "gender", "occupation", "driversLicense"]).merge(pd.read_csv(f"{sp}/persons_map.csv", usecols=["id", "w", "county"]), on="id")
qh = pd.read_csv(f"{sp}/hh.csv", usecols=["id", "autos", "income"]).set_index("id")
q["lic"] = q.driversLicense.astype(str).str.lower().eq("true"); q = q[q.county.astype(str).str.startswith("24")]
q["adults"] = q.hhID.map(q[q.age >= 16].groupby("hhID").size()); q["autos"] = q.hhID.map(qh.autos); q["hinc"] = q.hhID.map(qh.income)
q = q[q.age >= 16].copy()
BANDS = [16, 18, 20, 25, 35, 45, 55, 65, 75, 200]; BL = ["16-17", "18-19", "20-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
area = lambda cty: np.where(np.asarray(cty) == 24510, "Baltimore City", np.where(np.isin(np.asarray(cty), SIX), "other study counties", "rest of Maryland"))
def X(d, cars, adults, hinc):
    cars = np.asarray(cars); adults = np.asarray(adults)
    b = pd.cut(d.age, BANDS, right=False, labels=BL).astype(str)
    M = pd.get_dummies(b).reindex(columns=BL, fill_value=0).drop(columns="35-44").astype(float)
    M["female"] = (np.asarray(d.gender) == 2) * 1.0; M["employed"] = (np.asarray(d.occupation) == 1) * 1.0
    M["zero_car"] = (cars == 0) * 1.0   # v8 (2026-11-16b): the fewer-cars-than-persons-16+ covariate of v7 dropped (user decision: no such measure as a model variable)
    M["city"] = (np.asarray(d.county) == 24510) * 1.0; M["ln_inc"] = np.log(np.clip(np.asarray(hinc, float), 5000, None) / 50000)
    M["const"] = 1.0; return M
fit = sm.GLM(q.lic.astype(float).values, X(q, q.autos, q.adults, q.hinc).values, family=sm.families.Binomial(), freq_weights=q.w.values / q.w.mean()).fit()
print(pd.Series(fit.params, index=X(q.head(2), [1, 1], [1, 1], [1, 1]).columns).round(3).to_dict())
q["band"] = pd.cut(q.age, BANDS, right=False, labels=BL).astype(str); q["area"] = area(q.county)
pool = q.groupby("band").apply(lambda g: np.average(g.lic, weights=g.w))
TG = q.groupby(["area", "band"]).apply(lambda g: pd.Series(dict(n=len(g), raw=np.average(g.lic, weights=g.w), sw=g.w.sum(), swl=(g.w * g.lic).sum(), wbar=g.w.mean())))
TG["target"] = [(r.swl + 30 * r.wbar * pool[b]) / (r.sw + 30 * r.wbar) for (ar, b), r in TG.iterrows()]   # shrunk to the pooled band rate (30 persons)
TG.round(3).to_csv(f"{OUT}/licence_targets_rts_estimation.csv"); print(TG.round(3).to_string())
P = pp.merge(hh[["id", "county", "st", "cars_new", "adults", "pinc"]].rename(columns={"id": "hhID"}), on="hhID", how="left")
P["lic_new"] = P.lic.values; m16 = (P.st == 24) & (P.age >= 16)
P["p"] = np.nan; P.loc[m16, "p"] = fit.predict(X(P[m16], P.loc[m16, "cars_new"], P.loc[m16, "adults"], P.loc[m16, "pinc"]).values)
P["band"] = pd.cut(P.age, BANDS, right=False, labels=BL).astype(str); P["area"] = area(P.county)
# households that own a car and have exactly k licences: removing the last one is not allowed
for (ar, b), r in TG.iterrows():
    cell = m16 & (P.area == ar) & (P.band == b); n = int(cell.sum()); target = int(round(r.target * n)); have = int(P.loc[cell, "lic_new"].sum())
    if have > target:      # remove licences: draw among licensed persons with weight 1 - p (Efraimidis-Spirakis keys), protect the last licence of car owners
        cand = P[cell & P.lic_new]; key = np.log(rng.random(len(cand))) / np.clip(1 - cand.p.values, 1e-6, None)
        order = cand.index[np.argsort(-key)]; nlic = P[P.lic_new & (P.age >= 16)].groupby("hhID").size()
        removed = 0; left = nlic.reindex(P.loc[order, "hhID"].unique()).to_dict(); carown = P.loc[order, "cars_new"].values > 0
        for i, o in enumerate(order):
            if removed >= have - target: break
            hid = P.at[o, "hhID"]
            if carown[i] and left.get(hid, 0) <= 1: continue
            P.at[o, "lic_new"] = False; left[hid] = left.get(hid, 0) - 1; removed += 1
    elif have < target:    # add licences: weight p
        cand = P[cell & ~P.lic_new]; key = np.log(rng.random(len(cand))) / np.clip(cand.p.values, 1e-6, None)
        P.loc[cand.index[np.argsort(-key)][: target - have], "lic_new"] = True
P[["id", "lic_new"]].to_parquet(f"{OUT}/lic_new.parquet", index=False); hh[["id", "autos", "cars_new"]].to_parquet(f"{OUT}/cars_new.parquet", index=False)
print("licence 16+ Maryland before/after", P.loc[m16, "lic"].mean().round(4), P.loc[m16, "lic_new"].mean().round(4))
