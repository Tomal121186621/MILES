#!/usr/bin/env python3
"""School location choice, high school: writes the estimation and hold-out tables of model/estimate_school_location_high_school.py.

Same data, choice set and likelihood as l07_school.py (final model, full choice set): sc_03_engine.Design("hs", half, "full").
Every student has up to H possible home zones (weights w_h, location mixture of the survey home location) and up to C possible
school zones (weights w_c); the choice set of every home zone is all 719 zones with enrolment of the segment's bands, an
alternative being available when it has enrolment of the student's own band.  Values are those of the original estimator
(features in single precision, as sc_03_engine.Design.X computes them).
Tables (long format; the Biogeme script makes them wide):
  students   one row per student: person variables, and for each home slot h and school slot c the zone and the weight
             (missing slots: weight 0)
  alternatives  one row per student x home slot x alternative j: zone, car time t, ln(1+t), same zone, other county,
             other county x public share, other state, enrolment components nk0..nk2, availability
  candidates one row per student x home slot x school slot: the same variables at the student's school zone (its alternative j)
Check: log-likelihood at the estimates of l07_school_hs_coef.csv (step final) with the original estimator
(sc_03_engine.Model.scores) = l07_school_hs_fit.csv; and the same LL recomputed from the exported tables (numpy).
    python3 build_estimation_data.py   ->  ../data/estimation/*.parquet, ../data/holdout/*.parquet"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sc_03_engine as G   # noqa: E402
import sc_04_stepwise as S   # noqa: E402
OUT = os.path.abspath(f"{HERE}/../data"); RAWD = f"{OUT}/raw"
SEG, BAND = "hs", "hs"
BASES = ["t", "lt", "intra", "cc", "ccpub", "cs"]


def spec_of(names):
    """parameter names of the l07 coefficient file -> model terms (inverse of sc_04_stepwise.pname)"""
    terms, si, sabs = [], [], False
    for n in names:
        if n in ("mu_size",) or (n.startswith("g_") and n != "g_pub_in"): continue
        if n == "g_pub_in": sabs = True
        elif n.startswith("h_"): si.append(n[2:].replace("X", ":", 1))
        else: terms.append(n[2:].replace("X", "*"))
    return terms, si, sabs


def tables(D, M, th):
    LL, _ = M.scores(th)
    P = D.P; H = int(np.bincount(D.rec).max()); C = int((D.Sz >= 0).sum(1).max()); J = len(D.alts)
    slot = np.zeros(D.R, int)
    for r in range(1, D.R): slot[r] = slot[r - 1] + 1 if D.rec[r] == D.rec[r - 1] else 0
    st = pd.DataFrame({"student": np.arange(D.N), "person_id": P.person_id.values, "household_id": P.household_id.values, "band": P.band.values,
                       "age": P.age.values, "female": P.female.values, "income_group": P.g.values, "car0": P.car0.values, "carlow": P.carlow.values})
    for v in ["g1", "g3", "g4", "agec", "a25"]: st[v] = G.pvar(v, P, np.arange(D.N))
    for h in range(H):
        st[f"home_zone_{h}"] = -1; st[f"w_home_{h}"] = 0.0
    for c in range(C):
        st[f"school_zone_{c}"] = np.where(D.Sz[:, c] >= 0, G.z.zone.values[np.maximum(D.Sz[:, c], 0)], -1); st[f"w_school_{c}"] = D.Sw[:, c]
    for r in range(D.R):
        st.loc[D.rec[r], f"home_zone_{slot[r]}"] = G.z.zone.values[D.h[r]]; st.loc[D.rec[r], f"w_home_{slot[r]}"] = np.exp(D.lw[r])
    base = {b: D.base(b).astype(np.float32).astype(np.float64) for b in BASES if not (b == "ccpub" and SEG == "col")}
    alt = {"student": np.repeat(D.rec, J), "home_slot": np.repeat(slot, J), "j": np.tile(np.arange(J), D.R), "zone": G.z.zone.values[D.A].ravel()}
    for b, x in base.items(): alt[b] = x.ravel()
    for k in range(3): alt[f"nk{k}"] = D.NK[k].astype(np.float64).ravel()
    alt["av"] = D.av.astype(int).ravel()
    A = pd.DataFrame(alt)
    cand = []
    for c in range(C):
        ok = np.isfinite(D.lwc[:, c]); jj = D.cand[:, c]
        d = {"student": D.rec[ok], "home_slot": slot[ok], "school_slot": c, "j": jj[ok], "zone": G.z.zone.values[D.A[np.arange(D.R), jj]][ok]}
        for b, x in base.items(): d[b] = x[np.arange(D.R), jj][ok]
        for k in range(3): d[f"nk{k}"] = D.NK[k][np.arange(D.R), jj][ok].astype(np.float64)
        d["av"] = D.av[np.arange(D.R), jj][ok].astype(int); cand.append(pd.DataFrame(d))
    return st, A, pd.concat(cand).sort_values(["student", "home_slot", "school_slot"]), LL, (H, C, J)


def ll_numpy(st, A, cand, x, terms, gfree, H, C, J):
    """the likelihood of the Biogeme script, in numpy, from the exported tables (independent check of the export)"""
    comps = G.COMPS[SEG]; lw = np.zeros(3)
    for c in gfree: lw[comps.index(c)] = x[f"g_{c}"]

    def V(d):
        s = sum(np.exp(lw[k]) * d[f"nk{k}"].values for k in range(3)); v = x["mu_size"] * np.log(s + 1e-12)
        for t in terms:
            p = t.split("*"); f = d[p[0]].values.copy()
            for q in p[1:]: f = f * st[q].values[d.student.values]
            v = v + x["b_" + t.replace("*", "X")] * f
        return v
    A = A.assign(V=V(A)); A["e"] = np.where(A.av == 1, np.exp(A.V), 0.0)
    den = np.log(A.groupby(["student", "home_slot"]).e.sum())
    cand = cand.assign(V=V(cand)); cand["lden"] = den.reindex(pd.MultiIndex.from_arrays([cand.student, cand.home_slot])).values
    cand["wh"] = [st.at[s, f"w_home_{h}"] for s, h in zip(cand.student, cand.home_slot)]
    cand["wc"] = [st.at[s, f"w_school_{c}"] for s, c in zip(cand.student, cand.school_slot)]
    cand["p"] = cand.wh * cand.wc * np.exp(cand.V - cand.lden)
    return np.log(cand.groupby("student").p.sum()).sum()


def main():
    fit = pd.read_csv(f"{RAWD}/l07_school_{BAND}_fit.csv"); row = fit[fit.step == "final"].iloc[0]
    coef = pd.read_csv(f"{RAWD}/l07_school_{BAND}_coef.csv"); coef = coef[coef.step == "final"]
    x = dict(zip(coef.param, coef.coef)); terms, si, sabs = spec_of(coef.param.tolist()); assert not si
    for half, sub, ref in (("estimation", "estimation", row.LL), ("validation", "holdout", row.validation_LL)):
        D = G.Design(SEG, half, "full"); M = G.Model(D, terms, si, sabs); assert set(M.names) == set(x), (M.names, list(x))
        th = np.array([x[n] for n in M.names])
        st, A, cand, LL, (H, C, J) = tables(D, M, th)
        lln = ll_numpy(st, A, cand, x, terms, M.gfree, H, C, J)
        print(f"{half}: N {D.N}, J {J}, home slots {H}, school slots {C}, K {len(th)}; LL original estimator {LL.sum():.4f}, "
              f"from the exported tables {lln:.4f} (log {ref:.4f})")
        assert abs(LL.sum() - ref) < 1e-3 and abs(lln - ref) < 1e-3
        st.to_parquet(f"{OUT}/{sub}/school_{SEG}_{sub}_students.parquet", index=False)
        A.to_parquet(f"{OUT}/{sub}/school_{SEG}_{sub}_alternatives.parquet", index=False)
        cand.to_parquet(f"{OUT}/{sub}/school_{SEG}_{sub}_candidates.parquet", index=False)
    print("model terms:", terms, "free size weights:", M.gfree)


if __name__ == "__main__":
    main()
