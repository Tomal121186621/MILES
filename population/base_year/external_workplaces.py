#!/usr/bin/env python3
"""Workplace assignment for the corrected population, doubly constrained to observed data (replaces the VAE pipeline's sequential
allocator, whose friction-only draw left filled jobs by county at 0.71-1.04 of LODES):
  origins      O_i = employed persons by home zone (corrected population)
  destinations D_j = 2016 job inventory by zone (Maryland: LODES 2016 jobs / (1 - JOLTS rate); other states: MSTM 2016 inventory,
                     scaled so that total jobs = total workers)
  county pairs  flows by residence and workplace county from the ACS 2016-2020 commuting-flow table (third constraint)
  deterrence   f(t) = exp(-beta t) on the AM-peak car travel time, beta calibrated so that the mean assigned commute time equals
                     the mean reported home-work travel time of car-driver trips in the 2023 household travel survey
  T_ij = A_i O_i B_j D_j f(t_ij) by iterative balancing (Furness); each home zone's workers are drawn to destinations with a
  multinomial on T_ij / O_i, so column sums match D_j up to sampling noise.
Outputs (same layout as VAE step 05): 1_vae/vae_outputs/05_workplace/{jj,workplace}.parquet and data/stage1_workplace_check.csv
(jobs by county vs LODES, same-county share, commute-time distribution vs survey)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, h5py, json, os
ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; OUT = f"{V}/1_vae/vae_outputs/05_workplace"; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(0)
# ---- skim
h = h5py.File(f"{ABIT_HOME}/input/mito_los/skims/traveltime_auto.omx", "r"); T = h["data/mat1"][:]; ids = h["lookup/destinations"][:]; idx = {int(z): i for i, z in enumerate(ids)}; n = len(ids)
import sys; KM = "km" in sys.argv   # deterrence and target on network distance (km) instead of AM-peak time: the survey's reported driving distance
Dk = h5py.File(f"{ABIT_HOME}/input/mito_los/skims/distance_auto.omx", "r")["data/mat1"][:] / 1000.0   # metres -> km
# ---- workers by home zone
hh = pd.read_parquet(f"{V}/1_vae/output/hh.parquet", columns=["hh_id", "zone_id"]); pp = pd.read_parquet(f"{V}/1_vae/output/pp.parquet", columns=["pp_id", "hh_id", "occupation"])
emp = pp[pp.occupation == 1].merge(hh, on="hh_id"); emp = emp[emp.zone_id.isin(idx)]; emp["i"] = emp.zone_id.map(idx)
O = np.bincount(emp.i, minlength=n).astype(float)
# ---- jobs by zone
F = pd.read_csv(f"{V}/1_vae/output/employment_2016_lodes.csv"); F = F[F.SMZ.isin(idx)]; D = np.zeros(n)
RATE = json.load(open(f"{V}/1_vae/vacancy_rate.json"))["job_openings_rate_2016"]
D[[idx[z] for z in F.SMZ]] = F.TOT2016.values.astype(float); D[[idx[z] for z in F.SMZ[F.State == 24]]] *= (1 - RATE)   # Maryland: filled jobs only (vacancies added later)
md = np.zeros(n, bool); md[[idx[z] for z in F.SMZ[F.State == 24]]] = True
other = ~md; scale = (O.sum() - D[md].sum()) / D[other].sum(); D[other] *= scale
print(f"workers {O.sum():,.0f}; jobs: Maryland (LODES+vacancies) {D[md].sum():,.0f}, other states scaled x{scale:.3f} to {D[other].sum():,.0f}")
# ---- survey target: mean reported home-work travel time, car driver
r = pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv", low_memory=False, usecols=["o_activity", "d_activity", "travel_mode", "reported_travel_time", "wttrdfin"])
r = r[(r.travel_mode == 4) & (((r.o_activity == 1) & (r.d_activity == 2)) | ((r.o_activity == 2) & (r.d_activity == 1))) & r.reported_travel_time.between(1, 180)]
target_mean = (r.reported_travel_time * r.wttrdfin).sum() / r.wttrdfin.sum(); obs_pmf = r.groupby(r.reported_travel_time.round().clip(1, 120)).wttrdfin.sum(); obs_pmf /= obs_pmf.sum()
print(f"survey: {len(r):,} home-work car-driver trips, mean reported time {target_mean:.1f} min (weighted)")
rd = pd.read_csv(f"{ABIT_HOME}/input/rts/rts_trips_clean.csv", low_memory=False, usecols=["o_activity", "d_activity", "travel_mode", "distance", "wttrdfin"])
rd = rd[(rd.travel_mode == 4) & (((rd.o_activity == 1) & (rd.d_activity == 2)) | ((rd.o_activity == 2) & (rd.d_activity == 1))) & rd.distance.between(0.2, 120)]; rd["km"] = rd.distance * 1.609344
target_km = (rd.km * rd.wttrdfin).sum() / rd.wttrdfin.sum(); obs_km_pmf = rd.groupby(rd.km.round().clip(1, 150)).wttrdfin.sum(); obs_km_pmf /= obs_km_pmf.sum()
print(f"survey: {len(rd):,} home-work car-driver trips with driving distance, mean {target_km:.1f} km (weighted)")
if KM: X, target_x, unit = Dk, target_km, "km"
else: X, target_x, unit = T, target_mean, "min"
# ---- third constraint: county-to-county commuting flows (ACS 2016-2020, workers by residence and workplace county), for all
#      county pairs inside the zone system; each home county's ACS flow shares are applied to that county's synthetic workers
zs0 = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv").set_index("ZoneId"); zc = np.array([int(zs0.COUNTYFIPS[int(z)]) for z in ids])
acs = pd.read_excel(f"{PRICING_HOME}/data/census/acs_commuting_flows_2016_2020.xlsx", header=None, skiprows=8, dtype=str).iloc[:, [0, 1, 4, 5, 8]]
acs.columns = ["hs", "hc", "ws", "wc", "nw"]; acs = acs.dropna(subset=["hs", "hc", "ws", "wc", "nw"]); acs = acs[acs.hc.str.strip().str.isdigit() & acs.wc.str.strip().str.isdigit()]; acs["nw"] = pd.to_numeric(acs.nw, errors="coerce")
acs["h"] = (acs.hs.str.zfill(2) + acs.hc.str.zfill(3)).astype(int); acs["w"] = (acs.ws.str[-2:].str.zfill(2) + acs.wc.str.zfill(3)).astype(int)
cset = set(zc.tolist()); acs = acs[acs.h.isin(cset) & acs.w.isin(cset)]
Fhw = acs.groupby(["h", "w"]).nw.sum(); Oc = pd.Series(O).groupby(zc).sum()
cty_target = {}                                       # (h, w) -> target workers = synthetic workers of h x ACS share of w among h's in-region destinations
for hcty, g in Fhw.groupby(level=0):
    sh = g / g.sum()
    for (hh_, ww_), s in sh.items(): cty_target[(hh_, ww_)] = float(Oc.get(hcty, 0)) * s
cidx = {c: k for k, c in enumerate(sorted(cset))}; ci = np.array([cidx[c] for c in zc]); K = len(cidx)
Ctar = np.zeros((K, K))
for (h_, w_), v in cty_target.items(): Ctar[cidx[h_], cidx[w_]] = v
def county_sums(Tm):
    S = np.zeros((K, K)); np.add.at(S, (ci[:, None].repeat(n, 1), ci[None, :].repeat(n, 0)), Tm); return S
def balance(beta, iters=40):
    Fm = np.exp(-beta * X); A = np.ones(n); B = np.ones(n); Cf = np.ones((K, K))
    for _ in range(iters):
        W = Fm * Cf[ci[:, None], ci[None, :]]
        A = 1.0 / np.maximum((W * (B * D)[None, :]).sum(1), 1e-12)
        B = 1.0 / np.maximum((W * (A * O)[:, None]).sum(0), 1e-12)
        Tm = (A * O)[:, None] * (B * D)[None, :] * W; S = county_sums(Tm)
        Cf *= np.where((S > 0) & (Ctar > 0), Ctar / np.maximum(S, 1e-12), 1.0) ** 0.7     # damped: the three constraints are not fully consistent
    W = Fm * Cf[ci[:, None], ci[None, :]]; Tm = (A * O)[:, None] * (B * D)[None, :] * W
    return Tm
lo, hi = 0.01, 0.3
for _ in range(14):                      # bisection on beta for the mean commute (time or distance)
    beta = 0.5 * (lo + hi); Tm = balance(beta); mean_t = (Tm * X).sum() / Tm.sum()
    if mean_t > target_x: lo = beta
    else: hi = beta
Tm = balance(beta, 80); mean_t = (Tm * X).sum() / Tm.sum()
S = county_sums(Tm); mask = Ctar > 0; print(f"beta {beta:.4f} per {unit}: mean modelled commute {mean_t:.1f} {unit}; column sums vs jobs, Maryland: {Tm[:, md].sum() / D[md].sum():.3f}; county-pair flows vs ACS: corr {np.corrcoef(S[mask], Ctar[mask])[0, 1]:.3f}, mean |ratio-1| {np.abs(S[mask] / Ctar[mask] - 1).mean():.3f}")
# ---- draw destinations per home zone
emp = emp.sample(frac=1, random_state=0).reset_index(drop=True); dest = np.empty(len(emp), int); jid = 1; rows = []
for i, grp in emp.groupby("i", sort=False):
    p = Tm[i] / Tm[i].sum(); counts = rng.multinomial(len(grp), p)
    d = np.repeat(np.arange(n), counts); rng.shuffle(d); dest[grp.index.values] = d
emp["zone"] = ids[dest]; emp["id"] = np.arange(1, len(emp) + 1)
jj = emp[["id", "zone", "pp_id"]].rename(columns={"pp_id": "personId"}).assign(type="job"); jj.to_parquet(f"{OUT}/jj.parquet", index=False)
pd.DataFrame({"pp_id": emp.pp_id.values, "workplace": emp.id.values}).to_parquet(f"{OUT}/workplace.parquet", index=False)
# ---- checks
zs = pd.read_csv(f"{ROOT}/inputs/zoneSystem.csv").set_index("ZoneId"); emp["t"] = T[emp.i.values, dest]; emp["km"] = Dk[emp.i.values, dest]
emp["home_cty"] = emp.zone_id.map(zs.COUNTYFIPS); emp["work_cty"] = emp.zone.map(zs.COUNTYFIPS)
mdres = emp[emp.zone_id.map(zs.STFIPS) == 24]
same = (mdres.home_cty == mdres.work_cty).mean(); bmr = mdres[mdres.home_cty.isin([24003, 24005, 24013, 24025, 24027, 24510]) & mdres.work_cty.isin([24003, 24005, 24013, 24025, 24027, 24510])]
mod_pmf = emp.groupby(emp.t.round().clip(1, 120)).size(); mod_pmf = mod_pmf / mod_pmf.sum()
ks = np.abs(mod_pmf.reindex(range(1, 121), fill_value=0).cumsum() - obs_pmf.reindex(range(1, 121), fill_value=0).cumsum()).max()
jobs_cty = emp.groupby("work_cty").size(); lodes = F[F.State == 24].groupby("FIPS").TOT2016.sum() * (1 - json.load(open(f"{V}/1_vae/vacancy_rate.json"))["job_openings_rate_2016"])
chk = pd.DataFrame({"filled_jobs": jobs_cty, "lodes_2016": lodes}).dropna(); chk["ratio"] = chk.filled_jobs / chk.lodes_2016
print(f"Maryland residents working in their own county: {same:.3f} (survey 2023: 0.58; ACS 2016-20 flows: 0.625 incl. work-from-home); six-county residents working in the six counties: {(bmr.home_cty == bmr.work_cty).mean():.3f}")
mod_km_pmf = emp.groupby(emp.km.round().clip(1, 150)).size(); mod_km_pmf = mod_km_pmf / mod_km_pmf.sum()
ks_km = np.abs(mod_km_pmf.reindex(range(1, 151), fill_value=0).cumsum() - obs_km_pmf.reindex(range(1, 151), fill_value=0).cumsum()).max()
print(f"commute time: modelled mean {emp.t.mean():.1f} min, median {emp.t.median():.1f}; KS distance to the survey distribution {ks:.3f}")
print(f"commute distance: modelled mean {emp.km.mean():.1f} km, median {emp.km.median():.1f} (survey mean {target_km:.1f}); KS {ks_km:.3f}")
print(f"filled jobs by Maryland county / LODES 2016: median {chk.ratio.median():.3f}, range {chk.ratio.min():.3f}-{chk.ratio.max():.3f}")
chk.assign(same_county_share=same, six_county_share=(bmr.home_cty == bmr.work_cty).mean(), county_pair_corr=np.corrcoef(S[mask], Ctar[mask])[0, 1], county_pair_mean_abs_dev=np.abs(S[mask] / Ctar[mask] - 1).mean(),
           beta=beta, deterrence_unit=unit, mean_commute=emp.t.mean(), ks=ks, mean_commute_km=emp.km.mean(), survey_mean_km=target_km, ks_km=ks_km).to_csv(f"{V}/data/stage1_workplace_check.csv")
