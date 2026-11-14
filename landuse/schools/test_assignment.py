#!/usr/bin/env python3
"""Test of a school assignment (assign_schools.py output) against enrolment, the RTS survey and the current nearest-school assignment.
  records:   assigned vs target (enrolment scaled per band) and vs enrolment, by band record; summary by band and component
  distance:  car peak time and road km to school by segment (k8 = elementary + middle, hs, col), mean and distribution; KS against the
             RTS students (both halves, location weights x wtperfin); SILO students restricted to the RTS home counties (counties
             with >= 10 RTS students of the segment)
  shares:    school in the home county; in-boundary, record level (expected share a_hs of the assigned record) and zone level (the
             school zone holds the home's attendance-zone school, as observable in the RTS), homes with SABS coverage >= 0.5
  current:   the same statistics for the person file's existing schoolId (the nearest-school-with-a-seat rule)
Outputs tables/assignment_<year>_{convergence,records,records_summary,distance,tlfd,shares}.csv.
Usage: python3 landuse/schools/test_assignment.py --dir DIR --year 2016 [--current PP_WITH_SCHOOLID --hh HH --dd DD]"""
import os, sys, argparse, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import school_common as C   # noqa: E402
ap = argparse.ArgumentParser(); ap.add_argument("--dir"); ap.add_argument("--year", type=int); ap.add_argument("--current"); ap.add_argument("--hh"); ap.add_argument("--dd"); ap.add_argument("--tag", default="")
a = ap.parse_args(); P = f"{C.T}/assignment_{a.year}{a.tag}"
z = C.zones(); zi = C.zidx(); CT = z.county.values; TT = C.tt(); KM = C.km()
SEG = {"elementary": "k8", "middle": "k8", "high": "hs", "postsec": "col"}
pd.read_csv(f"{a.dir}/school_convergence_{a.year}.csv").to_csv(f"{P}_convergence.csv", index=False)
R = pd.read_csv(f"{a.dir}/school_records_check_{a.year}.csv"); R.to_csv(f"{P}_records.csv", index=False)
summ = R.groupby(["band", "component"]).apply(lambda q: pd.Series(dict(records=len(q), enrolment=q.enrolment.sum(), assigned=q.assigned.sum(), scale=q.assigned.sum() / q.enrolment.sum(),
    max_abs_assigned_minus_capacity=int((q.assigned - q.capacity_int).abs().max()), share_records_at_capacity=float((q.assigned == q.capacity_int).mean()),
    corr_assigned_enrolment=float(np.corrcoef(q.assigned, q.enrolment)[0, 1]) if len(q) > 1 else np.nan))).reset_index()
summ.to_csv(f"{P}_records_summary.csv", index=False)
# ---- SABS: record-level a and zone-level B
sab = pd.read_parquet(f"{C.W}/sabs_home_school.parquet"); cov = pd.read_parquet(f"{C.W}/sabs_zone_cov.parquet")
rec_a = sab.set_index(["zone", "school_id"]).a; covs = cov.set_index(["zone", "band"])["cov"]; zb = sab.groupby(["zone", "band", "school_zone"]).a.sum()
def stats(df, who):
    """df: home_zone, school_zone, schoolId, band; one row per student"""
    out, tl = [], []
    h = zi[df.home_zone].values; j = zi[df.school_zone].values
    df = df.assign(t=TT[h, j], km=KM[h, j], incounty=CT[h] == CT[j], seg=df.band.map(SEG))
    df["a_rec"] = rec_a.reindex(pd.MultiIndex.from_arrays([df.home_zone, df.schoolId])).fillna(0).values
    df["a_zone"] = zb.reindex(pd.MultiIndex.from_arrays([df.home_zone, df.band, df.school_zone])).fillna(0).values
    df["cov"] = covs.reindex(pd.MultiIndex.from_arrays([df.home_zone, df.band])).fillna(0).values
    for seg, q in df.groupby("seg"):
        q = q[q.home_county.isin(RTS_COUNTIES[seg])]; c = q[q["cov"] >= 0.5]
        out.append(dict(who=who, seg=seg, students=len(q), mean_car_min=q.t.mean(), median_car_min=q.t.median(), mean_km=q.km.mean(), in_county=q.incounty.mean(),
                        in_boundary_record=c.a_rec.mean() if seg != "col" else np.nan, in_boundary_zone=c.a_zone.mean() if seg != "col" else np.nan))
        tl.append((seg, q.t.values, np.ones(len(q))))
    return out, tl
# ---- RTS observed (both halves)
S = pd.read_parquet(f"{C.W}/students.parquet"); LH = pd.read_parquet(f"{C.W}/loc_home.parquet"); LS = pd.read_parquet(f"{C.W}/loc_school.parquet")
O = LH.merge(LS, on="person_id", suffixes=("_h", "_s")).merge(S[["person_id", "seg", "band", "wtperfin"]], on="person_id")
O["w"] = O.w_h * O.w_s * O.wtperfin; h = zi[O.zone_h].values; j = zi[O.zone_s].values
O = O.assign(t=TT[h, j], km=KM[h, j], incounty=CT[h] == CT[j], home_county=CT[h])
O["a_zone"] = zb.reindex(pd.MultiIndex.from_arrays([O.zone_h, O.band, O.zone_s])).fillna(0).values; O["cov"] = covs.reindex(pd.MultiIndex.from_arrays([O.zone_h, O.band])).fillna(0).values
RTS_COUNTIES = {s: set(c[c >= 10].index) for s, c in ((s, S.assign(c=CT[zi[S.hz].values])[S.seg == s].c.value_counts()) for s in C.SEG)}
rows, TL = [], []
for seg, q in O.groupby("seg"):
    c = q[q["cov"] >= 0.5]; w = q.w
    rows.append(dict(who="RTS observed", seg=seg, students=int(S.seg.eq(seg).sum()), mean_car_min=(w * q.t).sum() / w.sum(), mean_km=(w * q.km).sum() / w.sum(),
                     in_county=(w * q.incounty).sum() / w.sum(), in_boundary_zone=(c.w * c.a_zone).sum() / c.w.sum() if seg != "col" else np.nan))
    TL.append(("RTS observed", seg, q.t.values, w.values))
A = pd.read_parquet(f"{a.dir}/school_assignment_{a.year}.parquet"); A = A[A.schoolId > 0]; A["home_county"] = CT[zi[A.home_zone].values]
o, tl = stats(A, "model assignment"); rows += o; TL += [("model assignment",) + x for x in tl]
if a.current:
    pp = pd.read_csv(a.current, usecols=["id", "schoolId"]); cur = A[["id", "home_zone", "band", "home_county"]].merge(pp, on="id", suffixes=("_m", ""))
    sch = pd.read_csv(f"{C.S}/input/schools_2016.csv", usecols=["id", "zone", "band"]).set_index("id")
    cur = cur[cur.schoolId > 0]; cur["school_zone"] = cur.schoolId.map(sch.zone).values; cur = cur.dropna(subset=["school_zone"]); cur["school_zone"] = cur.school_zone.astype(int)
    o, tl = stats(cur, "current rule (nearest with a seat)"); rows += o; TL += [("current rule (nearest with a seat)",) + x for x in tl]
grid = np.linspace(0, 120, 241)
def cdf(t, w): o_ = np.argsort(t); return np.interp(grid, t[o_], np.cumsum(w[o_]) / w.sum(), left=0.0)
obs = {s: cdf(t, w) for who, s, t, w in TL if who == "RTS observed"}; tlo = []
for who, s, t, w in TL:
    c_ = cdf(t, w); tlo.append(pd.DataFrame(dict(who=who, seg=s, minutes=grid, cdf=c_)))
    for r in rows:
        if r["who"] == who and r["seg"] == s: r["ks_vs_rts"] = float(np.abs(c_ - obs[s]).max())
D = pd.DataFrame(rows); D.to_csv(f"{P}_shares.csv", index=False); pd.concat(tlo).to_csv(f"{P}_tlfd.csv", index=False)
D[["who", "seg", "students", "mean_car_min", "mean_km", "ks_vs_rts"]].to_csv(f"{P}_distance.csv", index=False)
pd.set_option("display.width", 220); print(summ.round(4).to_string(index=False)); print(D.round(4).to_string(index=False))
