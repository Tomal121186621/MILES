#!/usr/bin/env python3
"""Schools step of the chain (between SILO and ABIT): assigns every student of a SILO population to a school record with the estimated
school location choice (write_inputs.py -> apply/), with shadow prices per school record so that the students match the
enrolment.  No SILO engine change; the original files are not modified, new files are written.

Student alignment (--align 1, default; user decision 2026-10-29): before the assignment, each year, persons are flagged as students
(occupation 3) at random within state x sex x age cells up to the ACS enrolment rate of the year (apply/school_enrolment_rates.csv):
ages 5-17: every employed person under 18 is first recoded as a student (school first; the job record stays in the
SILO files, ABIT builds jobs only for occupation 1), then non-workers (occupation 0 or 2) are added, ages 18+ from non-workers (occupation 2 or 4) up
to the ACS rate of enrolled NON-workers; a cell already above the rate is left as it is (reported in school_alignment_<year>.csv).
Students and bands: SILO occupation 3 (STUDENT); band by age as SchoolDataMd.bandForAge / assign_base_students.py: < 11 elementary
(younger students go with elementary), 11-13 middle, 14-17 high, 18+ post-secondary.  Model segment: elementary and middle -> k8 (size of
the student's own band), high -> hs, post-secondary -> col.
Person variables: household income group (2016 $: <40k, 40-75k, 75-125k, >=125k), cars (hh autos), drivers (household members with
driversLicense), car availability 0 = no car / 1 = fewer cars than drivers / 2 = otherwise, gender 2 = female; home zone from the
dwelling.
Utility of school record s in zone j for a student of type k at home zone h (the estimated nested form: zone, then record by weighted
seats):  P(s | h, k) = P(j | h, k) w_hks / S_hkj,  w_hks = exp(g_c(s) + h_c' x_k + lambda_s) N_s (1 + (e^g_pub_in - 1) a_hs [public K-12]),
S_hkj = sum_{s in j} w_hks,  V_hkj = mu ln S_hkj + sum_m b_m x_m,hkj (+ fixed logsum), N_s = enrolment, a_hs = SABS in-boundary share.
--capacity upper (default, user decision 2026-10-29): capacity = the record's real enrolment as an UPPER limit; lambda_s <= 0, a price
only where the model's demand would exceed it (floor at 0, no price elsewhere); targets are scaled as below only if the band's students
exceed its seats.  --capacity exact: shadow prices lambda_s, targets D_s = N_s scaled to the students of the band: K-12 by the county of the school (students of the band
living in the county / enrolment of the band in the county; then re-scaled to the band total), post-secondary over the region; lambda_s += ln(D_s / pred_s) /
eps_s, eps_s = 1 - (1 - mu) r_s (r_s = the record's share of its zone's seats),
with a per-record step multiplier (x1.1 while the error keeps its sign, max 5; back to 1 when it
flips; each change of lambda clipped to +-1), until max |pred / D - 1| < TOL (1e-4).
Draw (seed): students grouped by (home zone, type) draw records from P(s | h, k); then integer capacities (D_s rounded by largest
remainder, sum = students of the band) are enforced: surplus students of a full record (random) are redrawn over the records with free
seats with their own probabilities, until no record exceeds its capacity.
Outputs in --out: pp_<year>.csv (the input person file, schoolId replaced for students; other columns byte-identical), schools_<year>.csv
(the input school file, occupancy = students assigned), school_assignment_<year>.parquet (one row per student: id, home zone, band,
schoolId, school zone, P of the in-boundary record), school_convergence_<year>.csv, school_records_check_<year>.csv.
Simulated-year files (scenOutput/<run>/microData): hhid column accepted, household income = sum of person incomes when hh has none,
schoolId appended when missing; --lam-in: shadow prices of the previous year (warm start); --schools-template: the school file whose
structure is written (e.g. SILO's futureYears/schools_2024.csv), occupancy replaced.
Usage: python3 landuse/schools/assign_schools.py --pp PP --hh HH --dd DD --schools SCHOOLS --skim auto_peak_time.csv.gz --year 2016 --out DIR [--seed 1]
--coefficients FILE (default WORKSPACE/2_silo/schoolchoice/apply/school_choice_coefficients.csv; the re-estimated models:
apply/school_choice_coefficients_respec.csv, written by landuse/coefficients/write_school_location.py); --dump-utilities FILE writes V_hkj = mu ln S_hkj + sum_m b_m x_m (no shadow prices) for the
students' (type, home zone) and every school zone of the band, then exits without assigning (verification)."""
import os as _os, sys as _sys  # ORIOLE: configured locations (oriole.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from oriole_env import ORIOLE_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, argparse, time, numpy as np, pandas as pd
import scipy.sparse as sps
S_ = f"{WORKSPACE}/2_silo"; AP = f"{S_}/schoolchoice/apply"   # school-choice application files (data, workspace)
ap = argparse.ArgumentParser(); ap.add_argument("--pp"); ap.add_argument("--hh"); ap.add_argument("--dd"); ap.add_argument("--schools")
ap.add_argument("--skim", default=f"{S_}/input/skims/auto_peak_time.csv.gz"); ap.add_argument("--zones", default=f"{S_}/input/zoneSystem.csv")
ap.add_argument("--year", type=int, default=2016); ap.add_argument("--out"); ap.add_argument("--seed", type=int, default=1); ap.add_argument("--tol", type=float, default=1e-4)
ap.add_argument("--capacity", choices=["upper", "exact"], default="upper")
ap.add_argument("--coefficients", default=f"{AP}/school_choice_coefficients.csv"); ap.add_argument("--dump-utilities")
ap.add_argument("--align", type=int, default=1); ap.add_argument("--lam-in"); ap.add_argument("--write-pp", type=int, default=1); ap.add_argument("--schools-template"); ap.add_argument("--rates", default=f"{AP}/school_enrolment_rates.csv")
a = ap.parse_args(); LAM_OUT = []
os.makedirs(a.out, exist_ok=True); T0 = time.time()
def log(*m): print(f"[{time.time() - T0:7.1f}s]", *m, flush=True)
BAND_SEG = {"elementary": "k8", "middle": "k8", "high": "hs", "postsec": "col"}; SEGI = {"k8": 0, "hs": 1, "col": 2}
# ---- zones, skim
zs = pd.read_csv(a.zones).sort_values("ZoneId"); ZID = zs.ZoneId.values; NZ = len(ZID); zi = pd.Series(np.arange(NZ), index=ZID)
LAM0 = {b: g.set_index('id').lam for b, g in pd.read_csv(a.lam_in).groupby('band')} if a.lam_in and os.path.exists(a.lam_in) else {}
CT = zs.COUNTYFIPS.values; ST = zs.STFIPS.values
sk = pd.read_csv(a.skim); TT = np.full((NZ, NZ), np.nan); TT[zi[sk.FROM].values, zi[sk.TO].values] = sk.VALUE.values; assert np.isfinite(TT).all()
# ---- coefficients, records, SABS
cf = pd.read_csv(a.coefficients); log("school choice coefficients", a.coefficients); DUMP = []
sch = pd.read_csv(a.schools); rec = pd.read_csv(f"{AP}/school_records.csv").set_index("id")
sch["component"] = sch.id.map(rec.component)
sch.loc[sch.component.isna(), "component"] = sch.sector.map({"public": "pub", "private": "priv", "postsec": "cc"})
R = sch[sch.capacity > 0][["id", "zone", "band", "component", "capacity"]].reset_index(drop=True); R["j"] = zi[R.zone].values
SAB = pd.read_csv(f"{AP}/school_sabs_inboundary.csv")
# ---- students
pp = pd.read_csv(a.pp, usecols=lambda c: c in ("id", "hhID", "hhid", "age", "gender", "occupation", "driversLicense", "income")).rename(columns={"hhid": "hhID"})
hh = pd.read_csv(a.hh, usecols=lambda c: c in ("id", "dwelling", "autos", "income")).set_index("id")
if "income" not in hh: hh["income"] = pp.groupby("hhID").income.sum().reindex(hh.index).fillna(0).values   # simulated years: household income = sum of person incomes
pp = pp.drop(columns="income"); dz = pd.read_csv(a.dd, usecols=["id", "zone"]).set_index("id").zone
lic = pp.driversLicense.astype(str).str.lower().eq("true"); drivers = lic.groupby(pp.hhID).sum()
newstud = set()
if a.align:   # student alignment to the ACS enrolment rates of the year (enrolment_rates.py), before the assignment
    RT = pd.read_csv(a.rates); RT = RT[RT.year == min(max(a.year, RT.year.min()), RT.year.max())].set_index(["state", "sex", "cell"]).rate
    hz_ = zi.reindex(pp.hhID.map(hh.dwelling).map(dz).values).values; ok = ~np.isnan(hz_); pp["state"] = -1; pp.loc[ok, "state"] = ST[hz_[ok].astype(int)]
    ed = [18, 19, 20, 21, 22, 23, 24, 25, 30, 35, 45, 55, 65, 200]; lab = ["18", "19", "20", "21", "22", "23", "24", "25-29", "30-34", "35-44", "45-54", "55-64", "65+"]
    pp["cell"] = np.where(pp.age < 18, pp.age.astype(str), pd.cut(pp.age.clip(lower=18), ed, right=False, labels=lab).astype(str))
    w18 = (pp.age < 18) & (pp.occupation == 1); pp.loc[w18, "occupation"] = 3; newstud.update(pp.id.values[w18.values])   # school first (user 2026-10-29): employed minors become students; their job record stays in the SILO files, ABIT's reader (MarylandLosDataReader) builds a job only for occupation 1
    log(f"alignment: {int(w18.sum()):,} employed persons under 18 recoded as students")
    rng0 = np.random.default_rng(a.seed + 1000); al = []
    for (sta, sex, c), g in pp[(pp.age >= 5) & (pp.state > 0)].groupby(["state", "gender", "cell"]):
        r = RT.get((sta, sex, c), np.nan)
        if np.isnan(r): continue
        target = int(round(r * len(g))); have = int((g.occupation == 3).sum())
        cand = g.index[(g.occupation.isin([0, 2]) if c.isdigit() and int(c) < 18 else g.occupation.isin([2, 4])).values]   # non-workers only
        add = rng0.choice(cand, size=min(max(target - have, 0), len(cand)), replace=False) if target > have else np.array([], int)
        pp.loc[add, "occupation"] = 3; newstud.update(pp.id.values[add])
        al.append(dict(state=sta, sex=sex, cell=c, persons=len(g), students_before=have, acs_rate=r, target=target, added=len(add), students_after=have + len(add),
                       over_rate=int(have > target), short_of_candidates=int(target - have > len(cand))))
    AL = pd.DataFrame(al); AL.to_csv(f"{a.out}/school_alignment_{a.year}.csv", index=False)
    log(f"alignment: {len(newstud):,} persons flagged as students; cells over the ACS rate {int(AL.over_rate.sum())}, short of non-worker candidates {int(AL.short_of_candidates.sum())}")
st = pp[pp.occupation == 3].copy(); del pp
st["h"] = zi.reindex(st.hhID.map(hh.dwelling).map(dz).values).values; nz_ = st.h.isna().sum(); st = st.dropna(subset=["h"]); st["h"] = st.h.astype(int)
st["band"] = np.select([st.age < 11, st.age < 14, st.age < 18], ["elementary", "middle", "high"], "postsec")
inc = st.hhID.map(hh.income).values; st["g"] = np.digitize(inc, [40000, 75000, 125000]) + 1
cars = st.hhID.map(hh.autos).values; drv = st.hhID.map(drivers).fillna(0).values; st["cs"] = np.select([cars == 0, cars < drv], [0, 1], 2); st["female"] = (st.gender == 2).astype(int)
log(f"{len(st):,} students ({nz_:,} without a home zone left at -1); by band", st.band.value_counts().to_dict())
def pv(name, k):   # person variable of a type tuple k = (cs, g, female)
    cs, g, fe = k
    return {"car0": float(cs == 0), "carlow": float(cs == 1), "g1": float(g == 1), "g3": float(g == 3), "g4": float(g == 4), "female": float(fe)}[name]
out_s = np.full(len(st), -1, np.int64); conv, chk = [], []
rng = np.random.default_rng(a.seed); st = st.reset_index(drop=True)
for band in ["elementary", "middle", "high", "postsec"]:
    seg = BAND_SEG[band]; c = cf[cf.segment == seg]; par = dict(zip(c.parameter, c.value)); mu = par["mu_size"]
    util = c[c.kind == "utility"]; fixed = c[c.kind == "fixed"]; sinter = c[c.kind == "size_inter"]
    terms = list(util.term) + list(fixed.term); need = " ".join(terms + list(sinter.term))
    ls = np.load(f"{AP}/school_logsum_{seg}.npy", mmap_mode="r") if "ls" in need else None
    Rb = R[R.band == band].reset_index(drop=True); NS = len(Rb); N = Rb.capacity.values.astype(float)
    J = np.unique(Rb.j.values); jpos = np.searchsorted(J, Rb.j.values); NJ = len(J)
    sb = st[st.band == band]; stu = len(sb); D = N * stu / N.sum(); upper = a.capacity == "upper"
    if upper and stu <= N.sum(): D = N.copy()   # capacity = real enrolment, an upper limit
    elif band != "postsec":   # exact (or students > seats): enrolment scaled to the band's students in the school's county, then to the band total
        rc = CT[Rb.j.values]; f_c = pd.Series(CT[sb.h.values]).value_counts() / pd.Series(N).groupby(rc).sum()
        D = N * pd.Series(rc).map(f_c).fillna(stu / N.sum()).values; D *= stu / D.sum()
    scaled = not (upper and stu <= N.sum())
    shortc = (pd.Series(CT[sb.h.values]).value_counts() / pd.Series(N).groupby(CT[Rb.j.values]).sum()).dropna()
    for cty, v in shortc[shortc > 1].items(): conv.append(dict(band=band, note="county with more students than seats", county=cty, students_per_seat=v))
    usek = ("ls" in need) or ("car" in need); useg = ("ls" in need) or (":g" in need) or ("*g" in need); usef = "female" in need
    sb = sb.assign(k_cs=sb.cs if usek else 0, k_g=sb.g if useg else 0, k_f=sb.female if usef else 0)
    grp = sb.groupby(["k_cs", "k_g", "k_f", "h"]).size(); types = sorted(set((x[0], x[1], x[2]) for x in grp.index))
    H = np.unique(sb.h.values); hpos = pd.Series(np.arange(len(H)), index=H)
    n = {k: np.zeros(len(H)) for k in types}
    for (cs, g, fe, h), v in grp.items(): n[(cs, g, fe)][hpos[h]] = v
    # zone utility without the size term, by type: H x NJ
    t_ = TT[np.ix_(H, J)]; same = (H[:, None] == J[None]).astype(float); cc = (CT[H][:, None] != CT[J][None]).astype(float); cs_ = (ST[H][:, None] != ST[J][None]).astype(float)
    pub = Rb.component.eq("pub").values; zpub = np.bincount(jpos, N * pub, NJ) / np.bincount(jpos, N, NJ)
    basef = {"t": t_, "lt": np.log1p(t_), "intra": same, "cc": cc, "cs": cs_, "ccpub": cc * zpub[None]}
    Rk = {}
    for k in types:
        U = np.zeros((len(H), NJ))
        for tm, v in zip(list(util.term) + list(fixed.term), list(util.value) + list(fixed.value)):
            p_ = tm.split("*"); x = np.asarray(ls[k[0], k[1] - 1])[np.ix_(H, J)] if p_[0] == "ls" else basef[p_[0]]
            for q in p_[1:]: x = x * pv(q, k)
            U = U + v * x
        Rk[k] = U
    # component weights by type, in-boundary factor (sparse H x NS)
    gw = {k: np.array([np.exp(par.get(f"g_{cpt}", 0.0) + sum(r.value * pv(r.term.split(":")[1], k) for r in sinter.itertuples() if r.term.split(":")[0] == cpt)) for cpt in Rb.component]) for k in types}
    fin = np.exp(par["g_pub_in"]) - 1 if "g_pub_in" in par else 0.0
    sid = pd.Series(np.arange(NS), index=Rb.id.values); Sb = SAB[(SAB.band == band) & SAB.school_id.isin(Rb.id) & SAB.zone.isin(ZID[H])]
    Ah = sps.csr_matrix((Sb.a.values * fin * pub[sid[Sb.school_id].values], (hpos[zi[Sb.zone].values].values, sid[Sb.school_id].values)), shape=(len(H), NS))
    Zm = sps.csr_matrix((np.ones(NS), (np.arange(NS), jpos)), shape=(NS, NJ)); Ah_r, Ah_c = Ah.nonzero(); Ah_v = np.asarray(Ah[Ah_r, Ah_c]).ravel()
    if a.dump_utilities:   # verification: utilities without shadow prices, no assignment
        for k in types:
            w = gw[k] * N; S = np.bincount(jpos, w, NJ)[None] + (Ah @ sps.diags(w) @ Zm).toarray()
            Vd = np.where(S > 0, mu * np.log(np.maximum(S, 1e-300)) + Rk[k], -np.inf); hi, ji = np.nonzero(np.isfinite(Vd))
            DUMP.append(pd.DataFrame(dict(band=band, cs=k[0], g=k[1], female=k[2], home_zone=ZID[H[hi]], school_zone=ZID[J[ji]], V=Vd[hi, ji])))
        continue
    lam = np.array(LAM0.get(band, pd.Series(dtype=float)).reindex(Rb.id.values).fillna(0.0).values, dtype=float); step = np.ones(NS); g_prev = np.zeros(NS); r_s = N / np.bincount(jpos, N, NJ)[jpos]; eps = 1 - (1 - mu) * r_s
    def state(lam, want=False):
        pred = np.zeros(NS); keep = {}
        for k in types:
            w = gw[k] * np.exp(lam) * N; S = np.bincount(jpos, w, NJ)[None] + (Ah @ sps.diags(w) @ Zm).toarray()
            V = np.where(S > 0, mu * np.log(np.maximum(S, 1e-300)) + Rk[k], -np.inf); m = V.max(1, keepdims=True); E = np.exp(V - m); P = E / E.sum(1, keepdims=True)
            Q = n[k][:, None] * P / np.maximum(S, 1e-300)
            pred += w * (Q.sum(0)[jpos] + np.bincount(Ah_c, Ah_v * Q[Ah_r, jpos[Ah_c]], NS))
            if want: keep[k] = (P, S, w)
        return pred, keep
    for it in range(1, 5001):
        pred, _ = state(lam); rel = pred / D - 1
        err = (np.where(lam < 0, np.abs(rel), np.maximum(rel, 0)) if not scaled else np.abs(rel)).max()
        if it == 1 or it % 25 == 0 or err < a.tol: conv.append(dict(band=band, iteration=it, max_abs_rel_error=err, students=stu, enrolment=N.sum(), scale=stu / N.sum())); log(band, it, f"max |pred/D-1| {err:.2e}")
        if err < a.tol: break
        g_ = np.log(D / np.maximum(pred, 1e-12)); step = np.where(np.sign(g_) == np.sign(g_prev), np.minimum(step * 1.1, 5.0), 1.0); g_prev = g_
        lam += np.clip(step * g_ / eps, -1.0, 1.0)
        if scaled: lam -= lam.max()
        else: lam = np.minimum(lam, 0.0)   # inequality: a price only where demand would exceed the seats
    pred, keep = state(lam, True)
    # ---- draw
    cap = np.floor(D).astype(int); rem = int(stu - cap.sum())
    if rem > 0: cap[np.argsort(-(D - cap), kind="stable")[:rem]] += 1
    choice = np.full(len(sb), -1); idx_b = sb.index.values; gk = sb.groupby(["k_cs", "k_g", "k_f", "h"]).indices; prob = {}
    def probs(k, hi):
        P, S, w = keep[k]; f = np.ones(NS); row = Ah.getrow(hi); f[row.indices] += row.data
        return P[hi, jpos] * w * f / S[hi, jpos]
    for (cs, g, fe, h), ii in gk.items():
        pr = probs((cs, g, fe), hpos[h]); pr = pr / pr.sum(); prob[(cs, g, fe, h)] = pr; choice[ii] = rng.choice(NS, size=len(ii), p=pr)
    redrawn = 0; cnt = np.bincount(choice, minlength=NS)
    for rnd in range(200):
        over = np.flatnonzero(cnt > cap)
        if not len(over): break
        mv = np.concatenate([rng.choice(np.flatnonzero(choice == s), size=cnt[s] - cap[s], replace=False) for s in over])
        cnt[over] = cap[over]; choice[mv] = -1; redrawn += len(mv)
        for i in rng.permutation(mv):
            free = cnt < cap; pr = prob[(sb.k_cs.values[i], sb.k_g.values[i], sb.k_f.values[i], sb.h.values[i])] * free
            if pr.sum() <= 0: pr = free.astype(float)
            s_ = rng.choice(NS, p=pr / pr.sum()); choice[i] = s_; cnt[s_] += 1
    cnt = np.bincount(choice, minlength=NS); assert (cnt <= cap).all() and cnt.sum() == stu
    out_s[idx_b] = Rb.id.values[choice]
    LAM_OUT.append(pd.DataFrame(dict(band=band, id=Rb.id.values, lam=lam)))
    chk.append(pd.DataFrame(dict(band=band, id=Rb.id.values, zone=Rb.zone.values, component=Rb.component.values, enrolment=N, target=D, capacity_int=cap, expected=pred, assigned=cnt)))
    conv.append(dict(band=band, iteration=it, max_abs_rel_error=err, students=stu, enrolment=N.sum(), scale=stu / N.sum(), redrawn_for_capacity=redrawn, redraw_share=redrawn / stu, scaled_targets=scaled, records_with_price=int((lam < 0).sum()) if not scaled else np.nan, final=True))
    log(band, f"done: {it} iterations, {redrawn:,} students redrawn for capacity ({redrawn / stu:.2%})")
if a.dump_utilities:
    pd.concat(DUMP).to_csv(a.dump_utilities, index=False); log("utilities written to", a.dump_utilities); sys.exit(0)
st["schoolId"] = out_s
pd.DataFrame(conv).to_csv(f"{a.out}/school_convergence_{a.year}.csv", index=False); C_ = pd.concat(chk); C_.to_csv(f"{a.out}/school_records_check_{a.year}.csv", index=False)
zid_s = sch.set_index("id").zone
st.assign(home_zone=ZID[st.h.values], school_zone=st.schoolId.map(zid_s).values)[["id", "hhID", "age", "band", "g", "cs", "home_zone", "schoolId", "school_zone"]].to_parquet(f"{a.out}/school_assignment_{a.year}.parquet", index=False)
# ---- person file: schoolId replaced for students (other columns as read, as text)
sid_of = pd.Series(st.schoolId.values, index=st.id.values); first = True
if a.write_pp:
  with open(f"{a.out}/pp_{a.year}.csv", "w") as fo:
      for ch in pd.read_csv(a.pp, dtype=str, chunksize=2_000_000, keep_default_na=False):
          ids = ch.id.astype(np.int64); m = ids.isin(sid_of.index).values
          if "schoolId" not in ch: ch["schoolId"] = "-1"   # simulated years without the column: appended (SILO format, -1 = none)
          ch.loc[m, "schoolId"] = sid_of.reindex(ids[m]).values.astype(np.int64).astype(str)
          if newstud: ch.loc[ids.isin(newstud).values, "occupation"] = "3"   # SILO Occupation.STUDENT = 3 (ABIT PersonReader: Occupation.valueOf)
          ch.to_csv(fo, index=False, header=first); first = False
pd.concat(LAM_OUT).to_csv(f"{a.out}/school_lambda_{a.year}.csv", index=False)
occ = st.schoolId[st.schoolId > 0].value_counts(); s2 = pd.read_csv(a.schools_template or a.schools, dtype=str, keep_default_na=False)
s2["occupancy"] = s2.id.astype(int).map(occ).fillna(0).astype(int).astype(str); s2.to_csv(f"{a.out}/schools_{a.year}.csv", index=False)
log("written", os.listdir(a.out))
