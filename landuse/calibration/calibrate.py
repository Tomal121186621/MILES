#!/usr/bin/env python3
"""Component calibration of SILO on the 2016-2020 window. Each round: run SILO 2016->2020, validate every year
(landuse/validation/validate_landuse.py), compare each component's mean annual rate over 2017-2020 with its observed target, update the component's
parameter by the ratio target/model (damped), write the new properties, repeat. Nothing is tuned to traffic; all targets are
observed Maryland rates (Census components of change, ACS PUMS).  Log: WORKSPACE/2_silo/calibration/calibration_log.csv (round,
parameter, value, model rate, target). Usage: python landuse/calibration/calibrate.py <rounds> [start_round]
CALIB_SPEC=respec calibrates the re-estimated models (write_properties.py ... respec): scenarios calib_respec_r<k>, parameters
landuse/calibration/calibrated_parameters.json (started from WORKSPACE/2_silo/calibration/params.json when absent), log
landuse/calibration/calibration_log.csv, car-ownership county constants 2_silo/input/car_ownership_county_constants.csv; the files of
the earlier models (params.json, calibration_log.csv, car_ownership_region_constants.csv, labor_participation_adjusters.csv,
construction_region_scalers.csv in the workspace) are not written."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import pandas as pd, numpy as np, subprocess, sys, os, re, json
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; R = f"{S}/run"
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3; START = int(sys.argv[2]) if len(sys.argv) > 2 else 1; DAMP = 0.8
# component -> (validation table, properties key, update exponent sign)  parameter_new = parameter_old * (target/model)^DAMP
COMP = {"births": ("births per woman 15-50", "demographics.local.birth.rate.adjuster"),
        "marriages": ("new marriages share of adults", "demographics.local.marriage.rate.adjuster"),
        "divorces": ("divorces share of married", "demographics.local.divorce.rate.adjuster"),
        "moves": ("persons who moved share (persons aged 1+)", "move.or.not.binomial.log.shift.parameter"),
        "construction": ("new dwellings vs permitted units", "construct.dwelling.demand.scaler")}
# composition components (B composition, Maryland county average of the final year): parameter_new = parameter_old * (target/model)^DAMP on a share
COMPB = {"leaveParents": ("adults 18-34 living with parents", "0", "demographics.local.leave.parents.adjuster", -1)}   # share NOT living with parents (bin 0): leaving rate up when too many stay
# employment (2026-10-23): multipliers by age band x sex (input/labor_participation_adjusters.csv) on the statewide ACS employed share
# by age band and sex (validation section B2), mean 2017-2020; the single adjuster on the county mean is fixed at 1.0
ADJ = f"{S}/input/labor_participation_adjusters.csv"; LPR = pd.read_csv(f"{S}/input/laborParticipationRates.csv"); TOL = 0.02; SECANT = {"moves", "construction", "leaveParents"}
DEFAULTS = {"demographics.labor.participation.adjuster": 1.0, "demographics.local.birth.rate.adjuster": 1.0, "demographics.local.marriage.rate.adjuster": 1.1, "demographics.local.divorce.rate.adjuster": 1.0, "move.or.not.binomial.log.shift.parameter": 0.03,
            "construct.dwelling.demand.scaler": 1.0, "demographics.local.leave.parents.adjuster": 1.0, "demographics.labor.participation.adjuster": 1.0}
SPEC = os.environ.get("CALIB_SPEC", "record"); assert SPEC in ("record", "respec"), SPEC
RS = "_respec" if SPEC == "respec" else ""
if SPEC == "respec":   # calibrated parameters and log of the re-estimated models are kept in the repository
    PFILE = f"{MILES_HOME}/landuse/calibration/calibrated_parameters.json"; LOGF = f"{MILES_HOME}/landuse/calibration/calibration_log.csv"
    CARK = f"{S}/input/car_ownership_county_constants.csv"
else:
    PFILE = f"{S}/calibration/params.json"; LOGF = f"{S}/calibration/calibration_log.csv"; CARK = f"{S}/input/car_ownership_region_constants.csv"
PARAMS = dict(DEFAULTS); PARAMS.update(json.load(open(PFILE if os.path.exists(PFILE) else f"{S}/calibration/params.json")) if os.path.exists(f"{S}/calibration/params.json") else {})
def write_props(name, params):
    subprocess.run(["python3", f"{MILES_HOME}/landuse/run/write_properties.py", name, "2016", "2020"] + (["-1", "1", "respec"] if SPEC == "respec" else []), check=True, capture_output=True)
    p = f"{R}/{name}.properties"; t = open(p).read()
    for k, v in params.items(): t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
    open(p, "w").write(t)
log = []
for rnd in range(START, START + ROUNDS):
    name = f"calib{RS}{os.environ.get('CALIB_TAG', '')}_r{rnd}"; write_props(name, PARAMS)   # CALIB_TAG: scenario prefix (2026-11-10)
    print(f"round {rnd}: params {PARAMS}", flush=True)
    if os.path.exists(f"{R}/base/scenOutput/{name}/microData/futureYears/pp_2020.csv"): print(f"  {name}: SILO output exists, reusing", flush=True)
    else:
        rc = subprocess.run(["bash", f"{MILES_HOME}/landuse/run/run_silo.sh", f"{R}/{name}.properties", "24g"], env=dict(os.environ, MILES_WORKSPACE=WORKSPACE)).returncode   # at most 24 GB per run (51 GB machine)
        if rc != 0: print("SILO failed, see run/logs"); break
    vr = subprocess.run(["python3", f"{MILES_HOME}/landuse/validation/validate_landuse.py", name, "2016", "2020"], capture_output=True, text=True)
    if vr.returncode != 0: print(vr.stderr[-3000:]); break
    Rv = pd.read_parquet(f"{V}/data/silo_validation_{name}.parquet"); C = Rv[(Rv.section.isin(["C events", "D2 construction"])) & (Rv.year.between(2017, 2020))]
    new = dict(PARAMS)
    for comp, (table, key) in COMP.items():
        d = C[C.table == table]; m, o = (d.model.sum(), d.observed.sum()) if comp == "construction" else (d.model.mean(), d.observed.mean())
        if m > 0 and o > 0: new[key] = round(PARAMS[key] * (o / m) ** DAMP, 4)
        # 2026-10-23: log-secant step on the last two rounds when the response is not proportional (the estimated move-or-not
        # saturates): ln v' = ln v - ln(m/o) * (ln v - ln v_prev) / (ln r - ln r_prev), the step limited to a factor 2.5
        if comp in SECANT and m > 0 and o > 0 and os.path.exists(LOGF):
            Lp = pd.read_csv(LOGF); Lp = Lp[(Lp.component == comp) & (Lp["round"] == rnd - 1)]
            if len(Lp) and abs(np.log(Lp.value.iloc[-1]) - np.log(PARAMS[key])) > 1e-3 and abs(np.log(Lp.ratio.iloc[-1]) - np.log(m / o)) > 1e-3:
                el = (np.log(m / o) - np.log(Lp.ratio.iloc[-1])) / (np.log(PARAMS[key]) - np.log(Lp.value.iloc[-1]))
                if el > 0.05: new[key] = round(float(PARAMS[key] * np.clip(np.exp(-np.log(m / o) / el), 0.4, 2.5)), 4); print(f"  {comp}: secant step, elasticity {el:.2f}")
        log.append(dict(round=rnd, component=comp, parameter=key, value=PARAMS[key], model=m, target=o, ratio=m / o if o else np.nan, next_value=new.get(key)))
        print(f"  {comp:10s} model {m:.4f} target {o:.4f} ratio {m / o:.3f} -> {key} {PARAMS[key]} -> {new[key]}")
    B = Rv[(Rv.section == "B composition") & (Rv.year == 2020) & Rv.geo.astype(str).str.match(r"^24\d{3}$")].copy(); B["tbl"] = B.table.str.replace(r" \[PUMS \d+\]", "", regex=True)
    for comp, (table, bin_, key, sign) in COMPB.items():
        d = B[(B.tbl == table) & (B["bin"].astype(str) == bin_)]; m, o = d.model.mean(), d.observed.mean()
        if m > 0 and o > 0: new[key] = round(PARAMS[key] * (o / m) ** DAMP, 4)   # the bin is chosen so that the parameter moves the share in the same direction
        log.append(dict(round=rnd, component=comp, parameter=key, value=PARAMS[key], model=m, target=o, ratio=m / o if o else np.nan, next_value=new.get(key)))
        print(f"  {comp:12s} model {m:.4f} target {o:.4f} ratio {m / o:.3f} -> {key} {PARAMS[key]} -> {new[key]}")
    # employment cells: adjuster <- adjuster * (observed / model)^DAMP, statewide employed share by age band and sex 2017-2020
    E = Rv[(Rv.section == "B2 statewide") & (Rv.table == "employed share by age and sex") & Rv.year.between(2017, 2020)].groupby("bin")[["model", "observed"]].mean()
    A_ = pd.read_csv(ADJ); A_["bin"] = A_.sex + " " + A_.age_from.astype(str) + "-" + A_.age_to.astype(str); A_.loc[A_.age_to >= 99, "bin"] = A_.sex + " " + A_.age_from.astype(str) + "+"
    emp_ratio = {}
    for i, r_ in A_.iterrows():
        if r_["bin"] in E.index and E.at[r_["bin"], "model"] > 0:
            m, o = E.at[r_["bin"], "model"], E.at[r_["bin"], "observed"]; emp_ratio[r_["bin"]] = m / o
            # 2026-10-25: never above 1 / (highest employment rate of the band): beyond it the rate is capped at 1 and the
            # multiplier no longer binds (the teenage multipliers ran up to 4.3-5.5 while hires were blocked in rounds 21-29)
            col = "male" if r_.sex == "male" else "female"; mx = float(LPR[(LPR.age >= r_.age_from) & (LPR.age <= r_.age_to)][col].max())
            A_.at[i, "adjuster"] = round(float(min(r_.adjuster, 1 / mx) * (o / m) ** DAMP), 4)
            log.append(dict(round=rnd, component=f"employed {r_['bin']}", parameter="labor_participation_adjusters.csv", value=r_.adjuster, model=m, target=o, ratio=m / o, next_value=A_.at[i, "adjuster"]))
    if SPEC == "record": A_.drop(columns="bin").to_csv(ADJ, index=False)
    if emp_ratio: print(f"  employed by age x sex: ratios {min(emp_ratio.values()):.3f}-{max(emp_ratio.values()):.3f} (" + ", ".join(f"{k} {v:.3f}" for k, v in emp_ratio.items()) + ")")
    # car ownership: additive county constants (alternatives 1, 2, 3+ against 0 cars) from the final-year shares, input/car_ownership_region_constants.csv
    cars = B[B.tbl == "cars"]; K = pd.read_csv(CARK).set_index("region")
    for cty, g in cars.groupby("geo"):
        s = g.set_index(g["bin"].astype(int)); r = int(cty)
        if r in K.index and all(b in s.index for b in range(4)) and (s.model > 0).all() and (s.observed > 0).all():
            for k in (1, 2, 3): K.at[r, f"asc{k}"] = round(K.at[r, f"asc{k}"] + DAMP * (np.log(s.observed[k] / s.model[k]) - np.log(s.observed[0] / s.model[0])), 4)
    K.reset_index().to_csv(CARK, index=False)
    # construction by county: multiplicative region scalers on the construction demand (input/construction_region_scalers.csv),
    # from the 2017-2020 sum of new dwellings vs permitted units per county, damped log-ratio update
    D2 = Rv[(Rv.section == "D2 construction") & (Rv.year.between(2017, 2020)) & Rv.geo.astype(str).str.match(r"^24\d{3}$")].groupby("geo")[["model", "observed"]].sum()
    CS = pd.read_csv(f"{S}/input/construction_region_scalers.csv").set_index("region")
    within = ((D2.model / D2.observed).between(0.75, 1.25)).mean() if len(D2) else np.nan
    if "construct.dwelling.region.shares.file" in open(f"{R}/{name}.properties").read(): D2 = D2.iloc[0:0]   # 2026-10-23: counties by permit shares, scalers stay 1
    tot = D2.observed.sum() / D2.model.sum() if len(D2) and D2.model.sum() > 0 else 1.0   # the state total is the job of construct.dwelling.demand.scaler
    for cty, r in D2.iterrows():
        rr = int(cty)
        if rr in CS.index and r.model > 0 and r.observed > 0: CS.at[rr, "scaler"] = round(float(np.clip(CS.at[rr, "scaler"] * (r.observed / r.model / tot) ** DAMP, 0.05, 20)), 4)
    if SPEC == "record": CS.reset_index().to_csv(f"{S}/input/construction_region_scalers.csv", index=False)
    print(f"  construction by county: scalers updated; counties within ±25 % {within:.1%}")
    print(f"  cars: county constants updated; 0-car share model {cars[cars['bin'].astype(str) == '0'].model.mean():.4f} target {cars[cars['bin'].astype(str) == '0'].observed.mean():.4f}; cells within 5 pp {(cars.diff_pp.abs() <= 5).mean():.1%}")
    A = Rv[(Rv.section == "A totals") & (Rv.year == 2020)]
    print(f"  2020 totals by region median {A.ratio.median():.3f} ({A.ratio.min():.3f}-{A.ratio.max():.3f}); composition within ±5 pp {(B.diff_pp.abs() <= 5).mean():.1%}")
    lev = {l["component"]: l["ratio"] for l in log if not str(l["component"]).startswith("employed ")}; lev.update({f"employed {k}": v for k, v in emp_ratio.items()})
    off = {k: round(v, 3) for k, v in lev.items() if not (1 - TOL <= v <= 1 + TOL)}
    print(f"  round {rnd}: {len(lev) - len(off)}/{len(lev)} levers within ±{TOL:.0%}" + (f"; outside: {off}" if off else " - all levers within tolerance"), flush=True)
    PARAMS = new; json.dump(PARAMS, open(PFILE, "w"), indent=1)
    pd.DataFrame(log).to_csv(LOGF, mode="a", header=not os.path.exists(LOGF), index=False); log = []
print("final params:", PARAMS)
