#!/usr/bin/env python3
"""School-tour mode-choice logsums by zone pair (the method of jobchoice/rts_02_logsum.py for the school segment).

Model: the estimated ABIT tour mode choice for school tours (3_abit/mode_choice, model of record 'mnl' for school: MNL, generalised
cost GC = T + 60 C / VOT, VOT = 0.5 x household income / 2,080 h; coefficients results/gc_school_mnl.csv; LOS mc_common.tour_los2),
evaluated with mc_apply.utilities (no calibration shift); logsum = ln sum_m exp(V_m) over the available modes.
Segments: school segment (k8, hs, col) x car availability (0 = no car, 1 = fewer cars than drivers, 2 = at least as many) x land-use
income group (1 <40k, 2 40-75k, 3 75-125k, 4 >=125k).  Person and household variables are the segment's representative values from
the estimation-half students (school_data.py, weights wtperfin): mean age, household size and cars.  The logsum is averaged over sex
(mode-choice 'male' = SILO gender 1 = RTS gender 2, weighted by 1 - female share; the corrected coding of survey_population.py) and
over licence (share of licence holders; car driver available only with a licence, a car and age >= 16).  Household income for the
VOT: the median income of the 2016 base households of the group (2016 $) x 245.120 / 240.007 (2017 $ of the mode choice).
Time of day: the (outbound, return) period pairs of the estimation-half school tours with a share of at least 5 % (re-normalised).
Outputs work/logsum.npy (3 x 3 x 4 x 1588 x 1588 float32, zone index order), tables/logsum_segments.csv.   Usage: python3 landuse/schools/school_logsums.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import school_common as C   # noqa: E402
MC = f"{MILES_HOME}/activity/lib/mode_choice"; sys.path.insert(0, MC); import mc_common as M; import mc_apply as A   # noqa: E402
b = A.coef()["school"]
z = M.C.zones(); n = len(z); assert (z.id.values == C.zones().zone.values).all()
p = pd.read_parquet(f"{C.W}/students.parquet"); p = p[p.half == "estimation"]
p["car_seg"] = np.select([p.car0 == 1, p.carlow == 1], [0, 1], 2)
hh = pd.read_csv(f"{C.S}/input/microData/hh_2016.csv", usecols=["income"]); grp = np.digitize(hh.income.values, [40000, 75000, 125000])
med16 = [float(np.median(hh.income.values[grp == g])) for g in range(4)]
rows = []
for si, sg in enumerate(C.SEG):
    for c in range(3):
        q = p[(p.seg == sg) & (p.car_seg == c)]; q = q if len(q) >= 10 else p[p.seg == sg]   # thin cells: the segment's values
        w = q.wtperfin.values; avg = lambda x: float((np.asarray(x, float) * w).sum() / w.sum())
        for g in range(4):
            rows.append(dict(seg=sg, si=si, car_seg=c, inc_group=g + 1, n_records=int(((p.seg == sg) & (p.car_seg == c)).sum()), age=avg(q.age), female=avg(q.female),
                             lic=avg(q.lic * (q.age >= 16)), hhsize=avg(q.hhsize), autos=0.0 if c == 0 else avg(q.cars), inc16=med16[g], inc17=med16[g] * 245.120 / 240.007))
SEG = pd.DataFrame(rows)
tw = pd.read_parquet(f"{MC}/work/tours_estimation.parquet", columns=["segment", "pout", "pret"]); tw = tw[tw.segment == "school"]
pr = tw.groupby(["pout", "pret"]).size() / len(tw); pr = pr[pr >= 0.05]; pr /= pr.sum(); print("period pairs", pr.round(3).to_dict(), flush=True)
H, Mz = np.divmod(np.arange(n * n), n)
LS = np.zeros((3, 3, 4, n, n), np.float32)
def logsum(Vm, av):
    Vm = np.where(av, Vm, -np.inf); mx = Vm.max(1, keepdims=True); return (mx[:, 0] + np.log(np.where(av, np.exp(Vm - mx), 0.0).sum(1))).astype(np.float32)
for (po, pt), share in pr.items():
    v = M.tour_los2(H, Mz, np.full(n * n, po), np.full(n * n, pt))
    t = pd.DataFrame({k: v[k] for k in ["car_min", "km", "bus_ok", "bus_t", "bus_c", "train_ok", "train_t", "train_c"]}); t["h"] = H; t["m"] = Mz
    for r in SEG.itertuples():
        ls = np.zeros(n * n)
        for male, ws in ((1.0, 1 - r.female), (0.0, r.female)):
            for lic, wl in ((1.0, r.lic), (0.0, 1 - r.lic)):
                if wl <= 0: continue
                t["inc_year"] = r.inc17; t["age"] = r.age; t["male"] = male; t["lic"] = lic; t["hhsize"] = r.hhsize; t["autos"] = r.autos
                f = M.features2(t); Vm, av = A.utilities(f, b)
                av[:, 0] = (lic > 0) & (r.autos > 0) & (r.age >= 16)
                ls += ws * wl * logsum(Vm, av)
        LS[r.si, r.car_seg, r.inc_group - 1] += (share * ls).reshape(n, n).astype(np.float32)
    print(f"period pair {po},{pt} done", flush=True); del v, t
np.save(f"{C.W}/logsum.npy", LS)
for r in SEG.itertuples():
    L_ = LS[r.si, r.car_seg, r.inc_group - 1]; SEG.loc[r.Index, "ls_mean"] = float(L_.mean()); SEG.loc[r.Index, "ls_intrazonal_mean"] = float(np.diag(L_).mean())
    SEG.loc[r.Index, "ls_p05"] = float(np.percentile(L_, 5)); SEG.loc[r.Index, "ls_p95"] = float(np.percentile(L_, 95))
SEG.to_csv(f"{C.T}/logsum_segments.csv", index=False); print(SEG.round(3).to_string(index=False))
