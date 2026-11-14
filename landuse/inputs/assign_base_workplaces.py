#!/usr/bin/env python3
"""Re-specified workplace choice: (1) the DC term anchored to the ACS, (2) the 2016 base workplaces re-assigned with it (2026-11-09).
Same rules as the earlier model (landuse/lib/jobchoice/rts_27_export_rts3.py for the anchor, base_assign_rts_v4.py for the base); new files only:
  2_silo/input/workplace_choice_coefficients.csv   b_dc + delta, delta such that the Maryland residents' share of workplaces in DC,
        applied to the 2016 base workers (base_v2 homes and attributes, all jobs of base_v2 as size term, no shadow prices) = ACS 2016-20
        9.82 %; exact by cell: P_DC(delta) = e^delta p / (1 - p + e^delta p) for a non-DC home.
  2_silo/input/microData/pp_2016_v5respec.csv, jj_2016_v5respec.csv   base_v2 with the workers of MD/DC/VA homes re-assigned by the
        anchored respec model + zone shadow prices (D_j = 95.99 % of the zone's jobs minus those of PA/DE/WV residents, drawn with exact
        capacities, matched to random pool jobs of the zone; as base_assign_rts_v4.py); only the fields workplace (pp) / personId (jj) change.
  2_silo/run/base_v5_respec/microData/{pp,jj,hh,dd}_2016.csv   links (hh, dd as base_v4)
  WORKSPACE/side_experiments/respec_2026-11/engine_check/tables/w01_*.csv   anchor, metrics, convergence, checks
Utility = the engine's (JobDataManagerImpl.rtsUtility, job.choice.model = respec) by cell home zone x sex x age band x car segment x income
group x licence x household size (cap 8) x children x 2+ workers; checked against the estimation code (wdc.py) for test cells.
    python3 landuse/inputs/assign_base_workplaces.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, time
import numpy as np, pandas as pd
from scipy.optimize import brentq
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; I = f"{S}/input"; MD = f"{I}/microData"
T = f"{V}/side_experiments/respec_2026-11/engine_check/tables"; os.makedirs(T, exist_ok=True)   # outputs (workspace)
SRC = f"{S}/run/base_v2/microData"; FILL = 6453136 / 6722717; TYPES = ["RET", "OFF", "IND", "OTH"]; MNL_STATES = (24, 11, 51)
COEF = f"{I}/workplace_choice_coefficients_unanchored.csv"; COEF_A = f"{I}/workplace_choice_coefficients.csv"
OUT_PP, OUT_JJ = f"{MD}/pp_2016_v5respec.csv", f"{MD}/jj_2016_v5respec.csv"; B5 = f"{S}/run/base_v5_respec"
ACS_DC = 0.0982; TOL, MAXIT, SEED = 1e-6, 5000, 20261109
rng = np.random.default_rng(SEED); t0 = time.time()
log = lambda *a: print(f"[{time.time() - t0:7.1f}s]", *a, flush=True)
for p in (COEF_A, OUT_PP, OUT_JJ): assert not os.path.exists(p), f"exists: {p}"

# ---------------------------------------------------------------- engine inputs
zr = pd.read_csv(f"{I}/workplace_choice_zones.csv").sort_values("zone").reset_index(drop=True)
zones = zr.zone.values; n = len(zones); zi = pd.Series(np.arange(n), index=zones); st = zr.state.values; ct = zr.county.values; reg = zr.region.astype(str).values
sk = pd.read_csv(f"{I}/skims/auto_peak_time.csv.gz"); TT = np.full((n, n), np.nan); TT[zi[sk.FROM].values, zi[sk.TO].values] = sk.VALUE.values; del sk
ZA = pd.read_csv(f"{I}/workplace_choice_zone_attributes.csv").set_index("zone").reindex(zones)
acc = pd.read_csv(f"{V}/data/accessibility_2016.csv"); acc = acc[acc.purpose == "nonwork"]
ACC = np.zeros((3, 4, n))
for c, cn in enumerate(["nocar", "carlt", "carge"]):
    for g, gn in enumerate(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]):
        ACC[c, g] = acc[acc.segment == f"{gn}_{cn}"].set_index("zone").A.reindex(zones).fillna(0).values
coef = pd.read_csv(COEF).set_index("parameter").estimate.to_dict()
mu = coef["mu_size"]; gk = np.array([1.0] + [np.exp(coef[f"g_{k}"]) for k in TYPES[1:]])
ZB = {"hiearn": ZA.hiearn.values, "off_sh": ZA.off_sh.values, "ret_sh": ZA.ret_sh.values, "ind_sh": ZA.ind_sh.values}
RUR = ZA.rural.values.astype(float)


def utility(cg, h, A, c):
    """engine rtsUtility for the cells cg (DataFrame female, young, old, g, lic, hhs, kids, w2, car) at home zone index h over zone indices A"""
    pv = {"female": cg.female.values, "young": cg.young.values, "old": cg.old.values, "g1": (cg.g.values == 1) * 1.0, "g3": (cg.g.values == 3) * 1.0,
          "g4": (cg.g.values == 4) * 1.0, "lic": cg.lic.values, "hhs": cg.hhs.values, "kids": cg.kids.values, "w2": cg.w2.values, "rurh": np.full(len(cg), RUR[h])}
    t = TT[h][A][None, :]; e = {}
    for k, v in c.items():
        if not k.startswith("b_"): continue
        p = k[2:].split("X"); x = np.full(len(cg), v, float)
        for q in p[1:]: x = x * pv[q]
        e[p[0]] = e.get(p[0], 0) + x
    z0 = np.zeros(len(cg)); U = e.get("t", z0)[:, None] * t + e.get("lt", z0)[:, None] * np.log1p(np.maximum(t, 0))
    U = U + e.get("intra", z0)[:, None] * (A == h)[None, :] + e.get("cs", z0)[:, None] * (st[A] != st[h])[None, :] + e.get("cc", z0)[:, None] * (ct[A] != ct[h])[None, :]
    U = U + e.get("dc", z0)[:, None] * ((st[A] == 11) & (st[h] != 11))[None, :]
    for b in ("hiearn", "off_sh", "ret_sh", "ind_sh"): U = U + e.get(b, z0)[:, None] * ZB[b][A][None, :]
    for k in e:
        if k.startswith("reg_"): U = U + e[k][:, None] * (reg[A] == k[4:])[None, :]
    if "accw" in e: U = U + e["accw"][:, None] * ACC[cg.car.values, cg.g.values - 1][:, A]
    return U


# ---------------------------------------------------------------- check against the estimation code (wdc.py, centred terms)
sys.path.insert(0, f"{MILES_HOME}/estimation/development/workplace_choice"); import wdc   # noqa: E402
wdc.TT = TT
for k in ("off_sh", "ret_sh", "ind_sh", "hiearn"): wdc.D[f"z_{k}"] = ZB[k]
wdc.D["z_rural"] = RUR; wdc.D["acc_nonwork"] = ACC
cw = pd.read_csv(f"{ESTIMATION_RESULTS}/workplace/w04_coef.csv"); cw = cw[cw.step == "final"].drop_duplicates("param", keep="last").set_index("param").coef
P_ = wdc.persons(True); ix = rng.choice(len(P_["g"]), 40, replace=False); Q = {k: v[ix] for k, v in P_.items()}
dmax = 0.0
for i in range(len(ix)):
    q = {k: v[i:i + 1] for k, v in Q.items()}; h = int(q["hidx"][0]); A = wdc.AZ
    ue = sum(cw[k] * wdc.feat(k, q["hidx"], A[None, :], q) for k in cw.index if k not in ("mu", "g_OFF", "g_IND", "g_OTH"))[0]
    cg = pd.DataFrame({"female": q["female"], "young": (q["age"] < 30) * 1.0, "old": (q["age"] >= 55) * 1.0, "g": q["g"], "lic": q["lic"],
                       "hhs": np.minimum(q["hhsize"], 8), "kids": (q["kids"] > 0) * 1.0, "w2": (q["workers"] >= 2) * 1.0, "car": q["car_seg"]})
    dmax = max(dmax, float(np.abs(utility(cg, h, A, coef)[0] - ue).max()))
log(f"check: utility of this script vs the estimation code for 40 workers x all zones with jobs, max |diff| {dmax:.2e}"); assert dmax < 1e-9

# ---------------------------------------------------------------- base workers
pp = pd.read_csv(f"{SRC}/pp_2016.csv", usecols=["id", "hhID", "age", "gender", "occupation", "workplace", "income", "driversLicense"])
hh = pd.read_csv(f"{SRC}/hh_2016.csv", usecols=["id", "dwelling", "autos", "hhSize"]).rename(columns={"id": "hhID"})
dd = pd.read_csv(f"{MD}/dd_2016.csv", usecols=["id", "zone"]).rename(columns={"id": "dwelling", "zone": "hz"})
jj = pd.read_csv(f"{SRC}/jj_2016.csv", usecols=["id", "zone", "personId", "type"])
g_ = pp.groupby("hhID").agg(hinc=("income", "sum"), nemp=("occupation", lambda o: int((o == 1).sum())), nkid=("age", lambda a: int((a < 18).sum())))
w = pp[(pp.workplace > 0) | (pp.occupation == 1)].merge(hh, on="hhID", how="left").merge(dd, on="dwelling", how="left").join(g_, on="hhID")
w = w.merge(jj[["id", "zone"]].rename(columns={"id": "workplace", "zone": "wz"}), on="workplace", how="left"); w["has_job"] = w.workplace > 0
w["h"] = zi[w.hz].values; w["w_old"] = np.where(w.has_job, zi.reindex(w.wz.fillna(-1).astype(int)).fillna(-1).values, -1).astype(int); w["hs"] = st[w.h.values]
w["female"] = (w.gender == 2).astype(np.int8); w["young"] = (w.age < 30).astype(np.int8); w["old"] = (w.age >= 55).astype(np.int8)
wk = 1 + w.nemp - (w.occupation == 1).astype(int)                      # engine Seeker: the seeker plus the other EMPLOYED members
w["car"] = np.select([w.autos <= 0, w.autos < wk], [0, 1], 2).astype(np.int8); w["w2"] = (wk >= 2).astype(np.int8)
w["g"] = np.select([w.hinc < 40000, w.hinc < 75000, w.hinc < 125000], [1, 2, 3], 4).astype(np.int8)
w["lic"] = w.driversLicense.astype(str).eq("True").astype(np.int8); w["hhs"] = w.hhSize.clip(upper=8).astype(np.int8); w["kids"] = (w.nkid > 0).astype(np.int8)
w["mnl"] = np.isin(w.hs, MNL_STATES)
KEY = ["h", "female", "young", "old", "car", "g", "lic", "hhs", "kids", "w2"]
log(f"workers {len(w):,}; re-assigned (MD/DC/VA homes) {int(w.mnl.sum()):,}")

# ---------------------------------------------------------------- (1) DC anchor: all base_v2 jobs as size term, no shadow prices
jj["zi"] = zi[jj.zone].values; ty = jj.type.astype(str).str.replace('"', '').map({k: i for i, k in enumerate(TYPES)}).fillna(3).astype(int).values
NJ = np.zeros((n, 4)); np.add.at(NJ, (jj.zi.values, ty), 1); azA = np.where(NJ.sum(1) > 0)[0]; lnSA = mu * np.log(NJ[azA] @ gk); dcz = st[azA] == 11
cells = w[w.hs != 11].groupby(KEY).size().rename("n").reset_index(); pdc = np.zeros(len(cells))
for h, idx in cells.groupby("h").indices.items():
    u = lnSA[None, :] + utility(cells.iloc[idx], h, azA, coef); u -= u.max(axis=1, keepdims=True); E = np.exp(u); pdc[idx] = E[:, dcz].sum(1) / E.sum(1)
nn = cells.n.values; md = st[cells.h.values] == 24; va = st[cells.h.values] == 51
share = lambda d, m: float((nn[m] * np.exp(d) * pdc[m] / (1 - pdc[m] + np.exp(d) * pdc[m])).sum() / nn[m].sum())
delta = brentq(lambda d: share(d, md) - ACS_DC, -4, 2)
DA = pd.DataFrame([dict(delta=delta, b_dc_estimated=coef["b_dc"], b_dc_anchored=coef["b_dc"] + delta, md_dc_share_estimated=share(0, md), md_dc_share_anchored=share(delta, md),
                        va_dc_share_estimated=share(0, va), va_dc_share_anchored=share(delta, va), target_md_dc_acs=ACS_DC, workers="base_v2 (2016), all jobs, no shadow prices")])
DA.to_csv(f"{T}/w01_dc_anchor.csv", index=False); log("DC anchor\n" + DA.T.to_string())
coef["b_dc"] += delta
pd.read_csv(COEF).assign(estimate=lambda d: np.where(d.parameter == "b_dc", coef["b_dc"], d.estimate)).to_csv(COEF_A, index=False)
log(f"written {COEF_A}")

# ---------------------------------------------------------------- (2) base re-assignment (base_assign_rts_v4.py rules)
kept_jobs = set(w.workplace[~w.mnl].values); jj["pool"] = ~jj.id.isin(kept_jobs)
ALLJ = np.bincount(jj.zi.values, minlength=n).astype(float); KEPT = np.bincount(jj.zi.values[~jj.pool.values], minlength=n).astype(float)
POOLJ = ALLJ - KEPT; Nr = int(w.mnl.sum())
x = np.clip(FILL * ALLJ - KEPT, 0, POOLJ); x *= Nr / x.sum(); D = np.floor(x); rem = int(Nr - D.sum())
order_ = np.argsort(-(x - D)); add = [j for j in order_ if D[j] < POOLJ[j]][:rem]; D[add] += 1; assert int(D.sum()) == Nr and (D <= POOLJ).all()
pool = jj[jj.pool]; NK = np.zeros((n, 4)); np.add.at(NK, (pool.zi.values, ty[jj.pool.values]), 1)
az = np.where(D > 0)[0]; nA = len(az); Da = D[az]; lnS = mu * np.log(NK[az] @ gk)
W = w[w.mnl].reset_index(drop=True)
cells = W.groupby(KEY, sort=True).size().rename("n").reset_index(); C = len(cells)
W["cell"] = W.merge(cells.reset_index().rename(columns={"index": "cell"}), on=KEY, how="left")["cell"].values
nc = cells.n.values.astype(float); ch = cells.h.values
U = np.empty((C, nA), np.float32)
for h, idx in cells.groupby("h").indices.items():
    u = lnS[None, :] + utility(cells.iloc[idx], h, az, coef); U[idx] = (u - u.max(axis=1, keepdims=True)).astype(np.float32)
E0 = np.exp(U); log(f"cells {C:,}; utility matrix {C:,} x {nA}")
s = np.zeros(nA); conv = []; damp = 1.0; prev = np.inf
def predict(s):
    es = np.exp(s - s.max()); den = E0 @ es; return es * ((nc / den) @ E0), es, den
for it in range(MAXIT + 1):
    pred, es, den = predict(s); dev = np.abs(pred / Da - 1)
    conv.append(dict(iteration=it, max_abs_dev=dev.max(), mean_abs_dev=dev.mean(), damping=damp))
    if it % 50 == 0 or dev.max() < TOL: log(f"shadow prices it {it}: max |pred/D-1| {dev.max():.2e}")
    if dev.max() < TOL: break
    if dev.max() > prev: damp = max(0.25, damp * 0.5)
    prev = dev.max(); s = s + damp * np.log(Da / pred)
CV = pd.DataFrame(conv); converged = bool(CV.max_abs_dev.iloc[-1] < TOL)
pred, es, den = predict(s); Pm = (E0 * es[None, :].astype(np.float32) / den[:, None].astype(np.float32)).astype(np.float32)
zone_of = np.full(len(W), -1, np.int64); order = rng.permutation(len(W)); Wc = W.cell.values
for c, ix in pd.Series(order).groupby(Wc[order]).indices.items():
    m = order[ix]; p = Pm[c].astype(float); k = rng.multinomial(len(m), p / p.sum()); zone_of[m] = np.repeat(np.arange(nA), k)
rounds = []
while True:
    assigned = np.where(zone_of >= 0)[0]; perm = assigned[rng.permutation(len(assigned))]; za = zone_of[perm]
    rank = pd.Series(np.ones(len(perm))).groupby(za).cumsum().values; drop = perm[rank > Da.astype(int)[za]]; zone_of[drop] = -1
    un = np.where(zone_of < 0)[0]; rounds.append(dict(round=len(rounds), released=len(drop), unassigned=len(un)))
    if len(un) == 0: break
    cap = Da.astype(int) - np.bincount(zone_of[zone_of >= 0], minlength=nA); open_ = cap > 0
    for c, ix in pd.Series(un).groupby(Wc[un]).indices.items():
        m = un[ix]; p = Pm[c].astype(float) * open_
        if p.sum() <= 0: u = np.where(open_, U[c].astype(float) + s, -np.inf); p = np.exp(u - u.max())
        k = rng.multinomial(len(m), p / p.sum()); zone_of[m] = np.repeat(np.arange(nA), k)
    if len(rounds) > 200: raise RuntimeError("capacity repair did not finish")
assert (np.bincount(zone_of, minlength=nA) == Da.astype(int)).all(); W["w_new"] = az[zone_of]
log(f"draw: {rounds[0]['released']:,} released after the first draw, {len(rounds)} rounds; workers by zone = D_j exactly")
pj = jj[jj.pool].copy(); pj["r"] = rng.random(len(pj)); pj = pj.sort_values(["zi", "r"]); pj["rk"] = pj.groupby("zi").cumcount(); pj = pj[pj.rk < D[pj.zi.values]]
W["r"] = rng.random(len(W)); Ws = W.sort_values(["w_new", "r"]); assert (pj.zi.values == Ws.w_new.values).all()
W["job_new"] = pd.Series(pj.id.values, index=Ws.id.values).reindex(W.id.values).values
maxp = int(pp.id.max()); wp_new = np.full(maxp + 1, -2, np.int64); wp_new[W.id.values] = W.job_new.values
maxj = int(jj.id.max()); pid_new = np.full(maxj + 1, -2, np.int64); pid_new[jj.id[jj.pool].values] = -1; pid_new[W.job_new.values] = W.id.values


def rewrite(src, dst, col, newval):
    with open(src, "r", newline="") as fi, open(dst + ".tmp", "w", newline="") as fo:
        head = fi.readline(); fo.write(head); ic = head.rstrip("\r\n").split(",").index(col); nch = 0
        for line in fi:
            body = line.rstrip("\r\n"); end = line[len(body):]; f = body.split(","); v = newval[int(f[0])]
            if v != -2 and f[ic] != str(v): f[ic] = str(v); nch += 1; fo.write(",".join(f) + end)
            else: fo.write(line)
    os.replace(dst + ".tmp", dst); return nch


n_pp = rewrite(f"{SRC}/pp_2016.csv", OUT_PP, "workplace", wp_new); n_jj = rewrite(f"{SRC}/jj_2016.csv", OUT_JJ, "personId", pid_new)
log(f"written {OUT_PP} ({n_pp:,} fields changed), {OUT_JJ} ({n_jj:,})")
# ---------------------------------------------------------------- checks and metrics
p0 = pd.read_csv(f"{SRC}/pp_2016.csv"); p1 = pd.read_csv(OUT_PP); j0 = pd.read_csv(f"{SRC}/jj_2016.csv"); j1 = pd.read_csv(OUT_JJ)
chk = [("pp: all fields except workplace identical", len(p0) == len(p1) and p0.drop(columns="workplace").equals(p1.drop(columns="workplace"))),
       ("jj: id, zone, type identical", len(j0) == len(j1) and j0[["id", "zone", "type"]].equals(j1[["id", "zone", "type"]])),
       ("no person holds two jobs", j1.personId[j1.personId > 0].is_unique),
       ("every worker's job points back to the worker", (j1.set_index("id").personId.reindex(p1.workplace[p1.workplace > 0]).values == p1.id[p1.workplace > 0].values).all()),
       ("every employed person has a job", (p1.workplace[p1.occupation == 1] > 0).all()),
       ("vacant share 4.01 %", abs(float((j1.personId <= 0).mean()) - (1 - FILL)) < 1e-6),
       ("shadow prices converged", converged)]
CK = pd.DataFrame(chk, columns=["check", "ok"]); CK.to_csv(f"{T}/w01_checks.csv", index=False); print(CK.to_string(index=False)); assert CK.ok.all()


def metrics(pf, jf, lab):
    p = pd.read_csv(pf, usecols=["id", "hhID", "workplace"]); p = p[p.workplace > 0]
    j = pd.read_csv(jf, usecols=["id", "zone"]).set_index("id").zone; hz = p.hhID.map(hh.set_index("hhID").dwelling).map(dd.set_index("dwelling").hz)
    h = zi[hz].values; wz = zi[j.reindex(p.workplace).values].values; m = st[h] == 24
    return dict(base=lab, md_workers=int(m.sum()), md_share_work_dc=float((st[wz][m] == 11).mean()), md_share_work_md=float((st[wz][m] == 24).mean()),
                md_same_county=float((ct[wz][m] == ct[h][m]).mean()), md_mean_car_time=float(TT[h[m], wz[m]].mean()))


M_ = pd.DataFrame([metrics(f"{MD}/pp_2016_v4.csv", f"{MD}/jj_2016_v4.csv", "base_v4 (record rts3)"), metrics(OUT_PP, OUT_JJ, "base_v5_respec")])
M_.to_csv(f"{T}/w01_metrics.csv", index=False); CV.to_csv(f"{T}/w01_convergence.csv", index=False); print(M_.to_string(index=False))
os.makedirs(f"{B5}/microData", exist_ok=True)
for nm, tgt in (("input", I), ("skims", f"{I}/skims")):
    if not os.path.lexists(f"{B5}/{nm}"): os.symlink(tgt, f"{B5}/{nm}")
for nm, tgt in (("pp_2016.csv", OUT_PP), ("jj_2016.csv", OUT_JJ), ("hh_2016.csv", f"{MD}/hh_2016_v2.csv"), ("dd_2016.csv", f"{MD}/dd_2016.csv")):
    if not os.path.lexists(f"{B5}/microData/{nm}"): os.symlink(tgt, f"{B5}/microData/{nm}")
log("done")
