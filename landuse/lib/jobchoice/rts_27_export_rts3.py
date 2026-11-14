#!/usr/bin/env python3
"""Export of the extended RTS workplace choice (model of record FINAL_FULLSET, rts_24_final_checks.py) for SILO, as new files:
  input/workplace_choice_zone_attributes.csv   zone, hiearn (LODES WAC 2017, fixed), off_sh / ret_sh / ind_sh (shares of the zone's jobs
                                               by SILO type; here from the 2016 base_v2 jobs, to be recomputed from SILO's jobs every
                                               year), rural (area type 40 of the zone, fixed; used for the HOME zone)
  input/job_choice_coefficients_rts3.csv       all coefficients, engine names b_<base>[X<var>] (spec in job_choice_rts3_spec.md)
  input/job_choice_coefficients_rts3_dcacs.csv the same with b_dc shifted so that the base_v3 Maryland residents' DC share = ACS 9.82 %
  jobchoice/job_choice_rts3_spec.md            the formula of every term for the engine implementer
  jobchoice/tables_rts/verification_rts3_workers.csv, verification_rts3_probs.csv.gz, verification_rts3_top20.csv,
  verification_rts3_zone_jobs.csv              200 test workers: full probability vectors, top 20 zones, log-sum
DC calibration: exact by cell (base_v3 workers of MD/DC/VA and the other states' non-DC homes, home zone x attributes): b_dc moves the
utility of every DC zone equally for a non-DC home, so P_DC(delta) = e^delta p / (1 - p + e^delta p).
The job-mix shares used here (calibration, verification) are those of the attribute file (base_v2 jobs); the estimation used the
2016 base jobs of the first base (work/zones.parquet); the size term N_jk of the verification is given in verification_rts3_zone_jobs.csv.
Usage: python3 landuse/lib/jobchoice/rts_27_export_rts3.py"""
import os, sys, json, numpy as np, pandas as pd
from scipy.optimize import brentq
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import rts_21_engine as G   # noqa: E402
R = G.R; T = R.T; I = f"{R.S}/input"; z = G.z; st = G.st; az = G.az; NZ = G.NZ
fm = json.load(open(f"{R.W}/v2x_final_model.json")); terms = fm["terms"]; assert fm["name"] == "FINAL_FULLSET" and not fm.get("size_inter")
E = pd.read_csv(f"{T}/estimates_X_{fm['name']}.csv").set_index("parameter").estimate
# ---- zone attributes (job mix from the base_v2 jobs)
jj = pd.read_csv(f"{R.S}/run/base_v2/microData/jj_2016.csv", usecols=["zone", "type"]); jj["type"] = jj.type.astype(str).str.replace('"', "")
c = jj.groupby(["zone", "type"]).size().unstack(fill_value=0).reindex(z.zone.values, fill_value=0); tot = c.sum(axis=1).replace(0, np.nan)
ZA = pd.DataFrame({"zone": z.zone.values, "hiearn": G.ZA.hiearn.values, "off_sh": (c.get("OFF", 0) / tot).fillna(0).values, "ret_sh": (c.get("RET", 0) / tot).fillna(0).values,
                   "ind_sh": (c.get("IND", 0) / tot).fillna(0).values, "rural": G.ZA.rural.values.astype(int)})
ZA.to_csv(f"{I}/workplace_choice_zone_attributes.csv", index=False)
for k in ("off_sh", "ret_sh", "ind_sh"): G.ZATTR[k] = ZA[k].values
NJ = np.stack([c.get(k, pd.Series(0, index=c.index)).values for k in R.SEC], 1).astype(float)   # base_v2 jobs by type (RET, OFF, IND, OTH)
# ---- coefficients in engine names: ls*notcar1 -> b_ls (enough cars / no car), b_lsXcar1 = 1 - b_ls (fewer cars than workers: logsum coefficient 1)
coef = {}
for n, v in E.items():
    if n == "b_lsXnotcar1": coef["b_ls"] = v
    else: coef[n] = v
coef["b_lsXcar1"] = 1.0 - coef["b_ls"]
C1 = pd.DataFrame({"parameter": list(coef), "estimate": list(coef.values())}); C1.to_csv(f"{I}/job_choice_coefficients_rts3.csv", index=False)
th = E.values.copy(); names = list(E.index)

def probs(P, h):
    """P over az for cells P (DataFrame with female, age, car_seg, g, lic, hhsize, state_h) living in zone index h (array)"""
    c_ = dict(zip(names, th)); b = np.array([c_[f"b_{t.replace('*', 'X')}"] for t in terms]); ew = np.exp([c_["g_OFF"], c_["g_IND"], c_["g_OTH"]])
    lnS = c_["mu_size"] * np.log(np.maximum(NJ[az, 0] + ew[0] * NJ[az, 1] + ew[1] * NJ[az, 2] + ew[2] * NJ[az, 3], 1e-300))
    rr = np.arange(len(P)); A = np.broadcast_to(az, (len(P), len(az)))
    U = lnS[None, :] + sum(b[k] * G.feat(t, h, A, P, rr) for k, t in enumerate(terms)) + G.feat("ls*car1", h, A, P, rr)
    m = U.max(axis=1, keepdims=True); E_ = np.exp(U - m); S = E_.sum(axis=1, keepdims=True); return E_ / S, (m + np.log(S))[:, 0], U
# ---- base_v3 workers by cell (home zone x attributes of the utility)
B3 = f"{R.S}/run/base_v3/microData"
pp = pd.read_csv(f"{B3}/pp_2016.csv", usecols=["id", "hhID", "age", "gender", "occupation", "workplace", "income", "driversLicense"])
hh = pd.read_csv(f"{B3}/hh_2016.csv", usecols=["id", "dwelling", "hhSize", "autos"]).rename(columns={"id": "hhID"})
dd = pd.read_csv(f"{B3}/dd_2016.csv", usecols=["id", "zone"]).rename(columns={"id": "dwelling", "zone": "hz"})
g_ = pp.groupby("hhID").agg(nemp=("occupation", lambda o: int((o == 1).sum())), hinc=("income", "sum"))
w = pp[pp.workplace > 0].merge(hh, on="hhID").merge(dd, on="dwelling").join(g_, on="hhID"); del pp
zi = R.zidx(); w["hidx"] = zi.reindex(w.hz).values.astype(int)
w["female"] = (w.gender == 2).astype(int); w["ab"] = np.select([w.age < 30, w.age >= 55], [0, 2], 1); wk = w.nemp.clip(lower=1)
w["car_seg"] = np.select([w.autos <= 0, w.autos < wk], [0, 1], 2); w["g"] = np.digitize(w.hinc.values, [40000, 75000, 125000]) + 1
w["lic"] = w.driversLicense.astype(str).eq("True").astype(int); w["hhs"] = w.hhSize.clip(upper=8)
key = ["hidx", "female", "ab", "car_seg", "g", "lic", "hhs"]
cells = w.groupby(key).size().rename("n").reset_index(); cells = cells[st[cells.hidx.values] != 11].reset_index(drop=True)
def cellP(cg, h):
    return pd.DataFrame({"female": cg.female.values, "age": np.choose(cg.ab.values, [25, 40, 60]), "car_seg": cg.car_seg.values, "g": cg.g.values, "lic": cg.lic.values,
                         "hhsize": cg.hhs.values, "state_h": st[h], "children": 0, "workers": 1})
pdc = np.zeros(len(cells)); dcz = st[az] == 11
for h, cg in cells.groupby("hidx", sort=False):
    Pm, _, _ = probs(cellP(cg, h), np.full(len(cg), h)); pdc[cg.index.values] = Pm[:, dcz].sum(axis=1)
n = cells.n.values; md = st[cells.hidx.values] == 24; va = st[cells.hidx.values] == 51
share = lambda d, m: float((n[m] * np.exp(d) * pdc[m] / (1 - pdc[m] + np.exp(d) * pdc[m])).sum() / n[m].sum())
delta = brentq(lambda d: share(d, md) - 0.0982, -3, 1)
DA = pd.DataFrame([dict(delta=delta, b_dc_estimated=coef["b_dc"], b_dc_anchored=coef["b_dc"] + delta, md_dc_share_estimated=share(0, md), md_dc_share_anchored=share(delta, md),
                        va_dc_share_estimated=share(0, va), va_dc_share_anchored=share(delta, va), target_md_dc_acs=0.0982, workers="base_v3 (2016)")])
DA.to_csv(f"{T}/dc_anchor_rts3.csv", index=False); print(DA.T, flush=True)
C2 = C1.copy(); C2.loc[C2.parameter == "b_dc", "estimate"] += delta; C2.to_csv(f"{I}/job_choice_coefficients_rts3_dcacs.csv", index=False)
th[names.index("b_dc")] += delta   # the verification uses the DC-anchored set (the one SILO runs)
# ---- verification: 200 test workers (MD/DC/VA homes, varied attributes), DC-anchored coefficients
rng = np.random.default_rng(20261029); W = w[np.isin(st[w.hidx.values], [24, 11, 51])]
strata = W.groupby(["female", "ab", "car_seg", "g", "lic"]).indices; pick = []
for k_, ix in strata.items(): pick.append(rng.choice(ix, 1)[0])
pick = list(rng.choice(pick, min(140, len(pick)), replace=False)) + list(rng.choice(len(W), 200 - min(140, len(pick)), replace=False))
V_ = W.iloc[pick].reset_index(drop=True); h = V_.hidx.values
Pv = cellP(V_, h); Pv["state_h"] = st[h]
Pm, lse, U = probs(Pv, h)
VW = pd.DataFrame({"test_id": np.arange(len(V_)), "person_id": V_.id.values, "home_zone": z.zone.values[h], "home_state": st[h], "female": V_.female.values, "age": V_.age.values,
                   "hh_cars": V_.autos.values, "hh_workers": V_.nemp.clip(lower=1).values, "car_segment": V_.car_seg.values, "hh_income": V_.hinc.values, "income_group": V_.g.values,
                   "driving_licence": V_.lic.values, "hh_size_capped_8": V_.hhs.values, "rural_home": G.RURAL[h].astype(int), "logsum_of_V": lse})
VW.to_csv(f"{T}/verification_rts3_workers.csv", index=False)
long = pd.DataFrame({"test_id": np.repeat(VW.test_id.values, len(az)), "zone": np.tile(z.zone.values[az], len(VW)), "V": U.ravel(), "probability": Pm.ravel()})
long.to_csv(f"{T}/verification_rts3_probs.csv.gz", index=False, compression="gzip")
long.sort_values(["test_id", "probability"], ascending=[True, False]).groupby("test_id").head(20).to_csv(f"{T}/verification_rts3_top20.csv", index=False)
pd.DataFrame({"zone": z.zone.values, "RET": NJ[:, 0], "OFF": NJ[:, 1], "IND": NJ[:, 2], "OTH": NJ[:, 3]}).to_csv(f"{T}/verification_rts3_zone_jobs.csv", index=False)
print("verification workers", len(VW), VW.home_state.value_counts().to_dict(), flush=True)
