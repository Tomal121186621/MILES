#!/usr/bin/env python3
"""Final school-choice models on the FULL choice set, second-draw check, and the hold-out tests against the current rule.

For each segment, the specification selected by school_stepwise.py (work/final_<seg>.json) is re-estimated on the estimation half with
the full choice set (school_likelihood.Design 'full'; model of record), robust s.e.; the sampled estimate and a second sampled draw are
compared in s.e. units.
Hold-out (validation half, full choice set, location weights x wtperfin on both sides):
  LL per student; share predicted exactly (mean probability of the observed school zone); mean car time and km to school; KS of the
  car-time distribution; share in the home county; share whose school zone holds the home's attendance-zone school (zone level,
  SABS a_hs; homes in covered districts).
Current rule (SchoolDataMd: nearest school with a seat of the band): its distribution P(j | home zone, band) is taken from the 2016 base
  assignment (input/microData/pp_2016.csv schoolId, landuse/schools/assign_base_students.py, the same rule with seats); a home zone / band
  without base students falls back to the nearest zone with enrolment of the band.
Outputs tables/final_<seg>_fullset.csv, cov_<seg>_FULLSET.csv, final_compare_sampled_full.csv, holdout.csv, holdout_tlfd_<seg>.csv;
work/final_<seg>.json updated with the full-set estimates.   Usage: python3 landuse/schools/school_final_model.py"""
import os, sys, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import school_likelihood as G; import school_common as C; import school_stepwise as S   # noqa: E402
TT = G.TT; KM = C.km(); CT = G.CT; zi = C.zidx()
# ---- the rule's distribution from the 2016 base assignment
pp = pd.read_csv(f"{C.S}/input/microData/pp_2016.csv", usecols=["hhID", "schoolId"]); pp = pp[pp.schoolId > 0]
hh = pd.read_csv(f"{C.S}/input/microData/hh_2016.csv", usecols=["id", "dwelling"]).set_index("id").dwelling
dd = pd.read_csv(f"{C.S}/input/microData/dd_2016.csv", usecols=["id", "zone"]).set_index("id").zone
sp = pd.read_parquet(f"{C.W}/school_points.parquet").set_index("id")
allrec = pd.read_csv(f"{C.S}/input/schools_2016.csv", usecols=["id", "zone", "band"]).set_index("id")
pp["h"] = zi[pp.hhID.map(hh).map(dd).values].values; pp["j"] = zi[pp.schoolId.map(allrec.zone).values].values; pp["band"] = pp.schoolId.map(allrec.band).values
RULE = {}
for b, g in pp.groupby("band"):
    M = np.zeros((G.NZ, G.NZ), np.float32); np.add.at(M, (g.h.values, g.j.values), 1.0); n = M.sum(1, keepdims=True)
    tot = sum(C.size()[b].values()); J = np.flatnonzero(tot > 0); near = J[np.argmin(TT[:, J], axis=1)]
    M[n[:, 0] == 0, near[n[:, 0] == 0]] = 1.0; RULE[b] = M / M.sum(1, keepdims=True)
del pp
rows, cmp, tl = [], [], []
for seg in C.SEG:
    fj = json.load(open(f"{C.W}/final_{seg}.json")); spec, fixed = fj["spec"], fj.get("fixed", {})
    srch = S.Search.__new__(S.Search); srch.seg = seg
    Df = G.Design(seg, "estimation", "full"); Mf = srch.model(Df, spec, fixed); Mf.fit(Mf.at(fj["coef"])); Mf.robust(); assert Mf.n_bad == 0
    t = Mf.table(); t.to_csv(f"{C.T}/final_{seg}_fullset.csv", index=False); pd.DataFrame(Mf.V, index=Mf.names, columns=Mf.names).to_csv(f"{C.T}/cov_{seg}_FULLSET.csv")
    tsm = pd.read_csv(f"{C.T}/estimates_{seg}_SELECTED.csv").set_index("parameter")
    D2 = G.Design(seg, seed=20261030); M2 = srch.model(D2, spec, fixed); M2.fit(M2.at(fj["coef"]))
    for n, e, se in zip(Mf.names, Mf.th, Mf.se):
        cmp.append(dict(seg=seg, parameter=n, full_set=e, full_se=se, full_t=e / se, sampled=tsm.estimate[n], sampled_se=tsm.robust_se[n], diff_in_full_se=(tsm.estimate[n] - e) / se,
                        second_draw=M2.coef_dict()[n], second_draw_diff_in_sampled_se=(M2.coef_dict()[n] - tsm.estimate[n]) / tsm.robust_se[n]))
    K = len(Mf.th); N = Df.N; M0 = srch.model(Df, [], {}); ll0 = M0.scores(np.r_[0.0, np.zeros(len(M0.names) - 1)])[0].sum()
    fj.update(coef_fullset=Mf.coef_dict(), LL_fullset=Mf.ll, LL_equal_shares_fullset=float(ll0), names=Mf.names); json.dump(fj, open(f"{C.W}/final_{seg}.json", "w"), indent=1)
    # ---- hold-out
    F = G.Design(seg, "validation", "full"); MF = srch.model(F, spec, fixed); llv, p, _ = MF.scores(Mf.th, want_p=True)
    w = F.P.wtperfin.values; wr = np.exp(F.lw) * w[F.rec]; A = F.A; h = F.h
    R_ = np.zeros_like(p)
    for b in G.BANDS[seg]:
        m = F.band[F.rec] == b; R_[m] = RULE[b][h[m][:, None], A[m]]
    ex_m = np.zeros(F.N); ex_r = np.zeros(F.N)
    obs_t, obs_w, obs_km, obs_cc, obs_in = [], [], [], [], []
    inb = np.zeros_like(p, dtype=np.float32); covr = np.zeros(F.R)
    if seg != "col":
        for b in G.BANDS[seg]:
            m = F.band[F.rec] == b; Mi, Bi, cv = G.ain(b); inb[m] = Bi[h[m][:, None], A[m]]; covr[m] = cv[h[m]]
    for c in range(F.cand.shape[1]):
        wc = np.exp(F.lwc[:, c]); pc = F.cand[:, c]; ok = wc > 0
        ex_m += np.bincount(F.rec[ok], (np.exp(F.lw) * wc * p[np.arange(F.R), pc])[ok], F.N); ex_r += np.bincount(F.rec[ok], (np.exp(F.lw) * wc * R_[np.arange(F.R), pc])[ok], F.N)
        jz = A[np.arange(F.R), pc]; obs_t.append(TT[h, jz][ok]); obs_km.append(KM[h, jz][ok]); obs_w.append((wr * wc)[ok]); obs_cc.append((CT[jz] == CT[h])[ok]); obs_in.append(inb[np.arange(F.R), pc][ok])
    ot, ow, ok_, oc, oi = map(np.concatenate, (obs_t, obs_w, obs_km, obs_cc, obs_in))
    tm = TT[h[:, None], A]; kmm = KM[h[:, None], A]; same = CT[A] == CT[h][:, None]; grid = np.linspace(0, 120, 2401)
    def cdf(t_, w_): o = np.argsort(t_); return np.interp(grid, t_[o], np.cumsum(w_[o]) / w_.sum(), left=0.0)
    co = cdf(ot, ow); res = dict(seg=seg, N=F.N, LL_per_student=float(llv.mean()), obs_mean_car_min=float((ow * ot).sum() / ow.sum()), obs_mean_km=float((ow * ok_).sum() / ow.sum()),
                                 obs_in_county=float((ow * oc).sum() / ow.sum()), ks_crit=1.36 / np.sqrt(w.sum() ** 2 / (w ** 2).sum()))
    covw = wr[:, None] * (covr[:, None] >= 0.5)
    for lab, Q, ex in (("model", p, ex_m), ("rule", R_, ex_r)):
        W_ = wr[:, None] * Q; res[f"{lab}_share_exact"] = float((w * ex).sum() / w.sum()); res[f"{lab}_mean_car_min"] = float((W_ * tm).sum() / W_.sum()); res[f"{lab}_mean_km"] = float((W_ * kmm).sum() / W_.sum())
        res[f"{lab}_in_county"] = float((W_ * same).sum() / W_.sum())
        o = np.argsort(tm.ravel()); cm = np.interp(grid, tm.ravel()[o], np.cumsum(W_.ravel()[o]) / W_.sum(), left=0.0); res[f"{lab}_ks_car_time"] = float(np.abs(cm - co).max())
        if seg != "col": res[f"{lab}_in_boundary_zone"] = float((covw * Q * inb).sum() / (covw * Q).sum())
        tl.append(pd.DataFrame({"seg": seg, "who": lab, "minutes": grid[::20], "cdf": cm[::20]}))
    tl.append(pd.DataFrame({"seg": seg, "who": "observed", "minutes": grid[::20], "cdf": co[::20]}))
    if seg != "col":
        oc_ = np.concatenate([covr[np.exp(F.lwc[:, c]) > 0] for c in range(F.cand.shape[1])]) >= 0.5
        res["obs_in_boundary_zone"] = float((ow * oi * oc_).sum() / (ow * oc_).sum()); res["share_students_covered_home"] = float((wr * (covr >= 0.5)).sum() / wr.sum())
    res.update(LL_fullset_estimation=Mf.ll, LL_equal_shares_estimation=float(ll0), rho2_vs_equal_shares=1 - Mf.ll / ll0, K=K)
    rows.append(res); print(pd.Series(res).to_string(), flush=True); print(t.round(4).to_string(index=False), flush=True)
pd.DataFrame(rows).to_csv(f"{C.T}/holdout.csv", index=False); pd.DataFrame(cmp).to_csv(f"{C.T}/final_compare_sampled_full.csv", index=False)
pd.concat(tl).to_csv(f"{C.T}/holdout_tlfd.csv", index=False)
print(pd.DataFrame(cmp).round(3).to_string(index=False))
