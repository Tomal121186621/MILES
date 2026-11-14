#!/usr/bin/env python3
"""Summary of the schools step over the SILO seeds and years (outputs of assign_all_seeds.py).
  students vs ACS: alignment cells summed by age band (5-10, 11-13, 14-17, 18+), all states of the zone area; ACS target = rate x persons
  capacity: by band, students assigned / seats, share of records at capacity, records priced
  survey: by segment, mean car time, KS against the RTS, in-county, in-boundary (zone level) of the model assignment
Each is given per seed and year, and as the mean / min / max over the seeds by year.
Outputs WORKSPACE/2_silo/schoolchoice/tables/seeds_students_vs_acs.csv, seeds_capacity.csv, seeds_survey.csv (+ _byyear).
Usage: python landuse/schools/summarize_seeds.py"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, glob, numpy as np, pandas as pd
PFX = os.environ.get("SILO_SEEDS", "oos_s"); SUF = os.environ.get("SILO_OUT_SUFFIX", "")   # seed-run prefix and output suffix
HERE = f"{WORKSPACE}/2_silo/schoolchoice"; T = f"{HERE}/tables"; R = f"{HERE}/runs"   # outputs of assign_all_seeds.py (workspace)
def ageband(c): a = int(c.split("-")[0].rstrip("+")); return "5-10" if a <= 10 else "11-13" if a <= 13 else "14-17" if a <= 17 else "18+"
A, Cp, Sv = [], [], []
for d in sorted(glob.glob(f"{R}/{PFX}[0-9]*/20*")):
    k = d.split("/")[-2]; y = int(d.split("/")[-1])
    f = f"{d}/school_alignment_{y}.csv"
    if not os.path.exists(f): continue
    al = pd.read_csv(f); al["band"] = al.cell.map(ageband); al["target_all"] = al.acs_rate * al.persons
    g = al.groupby("band")[["persons", "students_before", "target_all", "students_after"]].sum().reset_index(); A.append(g.assign(seed=k, year=y))
    rc = pd.read_csv(f"{d}/school_records_check_{y}.csv"); cv = pd.read_csv(f"{d}/school_convergence_{y}.csv"); cv = cv[cv.final == True]
    for b, q in rc.groupby("band"):
        c = cv[cv.band == b].iloc[0]
        Cp.append(dict(seed=k, year=y, band=b, students=q.assigned.sum(), seats=q.enrolment.sum(), students_per_seat=q.assigned.sum() / q.enrolment.sum(),
                       records_at_capacity=float((q.assigned >= q.capacity_int).mean()), scaled_targets=c.scaled_targets, iterations=c.iteration, max_error=c.max_abs_rel_error))
    sh = f"{T}/assignment_{y}_{k}_shares.csv"
    if os.path.exists(sh):
        s = pd.read_csv(sh); Sv.append(s[s.who == "model assignment"].assign(seed=k, year=y))
out = {}
for name, L, key in (("students_vs_acs", A, ["year", "band"]), ("capacity", Cp, ["year", "band"]), ("survey", Sv, ["year", "seg"])):
    if not L: continue
    D = pd.concat(L) if isinstance(L[0], pd.DataFrame) else pd.DataFrame(L); D.to_csv(f"{T}/seeds_{name}{SUF}.csv", index=False)
    num = [c for c in D.columns if c not in key + ["seed", "who", "scaled_targets"] and np.issubdtype(D[c].dtype, np.number)]
    B = D.groupby(key)[num].agg(["mean", "min", "max"]); B.columns = [f"{a}_{b}" for a, b in B.columns]; B.reset_index().to_csv(f"{T}/seeds_{name}_byyear{SUF}.csv", index=False); out[name] = D
pd.set_option("display.width", 250)
if "students_vs_acs" in out: print(out["students_vs_acs"].groupby(["year", "band"])[["persons", "students_before", "target_all", "students_after"]].mean().round(0).to_string())
if "capacity" in out: print(out["capacity"].groupby(["year", "band"])[["students_per_seat", "records_at_capacity"]].agg(["mean", "min", "max"]).round(3).to_string())
if "survey" in out: print(out["survey"].groupby(["year", "seg"])[["mean_car_min", "ks_vs_rts", "in_county", "in_boundary_zone"]].agg(["mean", "min", "max"]).round(3).to_string())
