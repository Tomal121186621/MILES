#!/usr/bin/env python3
"""Recalibration of the move-or-not shift (move.or.not.binomial.log.shift.parameter) for the two-level residential location model
(PUMA, then dwelling), with the procedure of calibrate.py for the component 'moves'.
Target: ACS PUMS 1-year Maryland share of persons aged 1+ who moved within the last year (MIG != 1), mean of the survey years
2017-2020 (the calibration window of calibrate.py; not the test years 2021-2024); validation table 'persons who moved share
(persons aged 1+)'.  Each round runs SILO 2016 -> 2020 and validates 2016-2020.  Update: shift' = shift (target / model)^0.8, with the
log-secant step of calibrate.py once two rounds exist (step limited to a factor 2.5).  Only the shift changes; the other adjusters
stay at landuse/calibration/calibrated_parameters.json.  Each round also prints the other targets of calibrate.py that the location
model can move (leaving the parental home, construction), without changing their levers.
Env: CAL_SET (properties key=value;..., e.g. $ADOPTED_SET of run/adopted_settings.sh), MOVE_SHIFT_START (first value, default 1.6363),
SILO_XMX.  Output: landuse/calibration/calibrated_parameters.json (shift of the round closest to the target),
landuse/calibration/calibration_log_moveshift.csv.
    python landuse/calibration/calibrate_moveshift.py [max_rounds=5]"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, re, json, subprocess, numpy as np, pandas as pd
V = f"{WORKSPACE}"; S = f"{V}/2_silo"; R = f"{S}/run"; C = f"{MILES_HOME}/landuse/calibration"
KEY = "move.or.not.binomial.log.shift.parameter"; TABLE = "persons who moved share (persons aged 1+)"; YEARS = (2017, 2020); Y1 = 2020; DAMP = 0.8; TOL = 0.005
P0 = json.load(open(f"{C}/calibrated_parameters.json")); OUTP = f"{C}/calibrated_parameters.json"; LOGF = f"{C}/calibration_log_moveshift.csv"
EXTRA = dict(kv.split("=", 1) for kv in os.environ.get("CAL_SET", "").split(";") if kv.strip())
TARGET = 0.1239   # mean 2017-2020 of the ACS share
MAXR = int(sys.argv[1]) if len(sys.argv) > 1 else 5
log = pd.read_csv(LOGF).to_dict("records") if os.path.exists(LOGF) else []
shift = log[-1]["next_value"] if log else float(os.environ.get("MOVE_SHIFT_START", "1.6363"))
for rnd in range(len(log) + 1, MAXR + 1):
    name = f"calib_moveshift_r{rnd}"
    if not os.path.exists(f"{R}/base/scenOutput/{name}/microData/futureYears/pp_{Y1}.csv"):
        subprocess.run(["python3", f"{MILES_HOME}/landuse/run/write_properties.py", name, "2016", str(Y1), "-1", "1", "respec"], check=True, capture_output=True)
        p = f"{R}/{name}.properties"; t = open(p).read()
        for k, v in dict(P0, **{KEY: shift}).items(): t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
        for k, v in EXTRA.items():
            t, n = re.subn(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
            if n == 0: t += f"\n{k} = {v}\n"
        open(p, "w").write(t)
        rc = subprocess.run(["bash", f"{MILES_HOME}/landuse/run/run_silo.sh", p, os.environ.get("SILO_XMX", "24g")], env=dict(os.environ, MILES_WORKSPACE=WORKSPACE)).returncode
        if rc != 0: sys.exit(f"SILO failed in round {rnd}")
    vr = subprocess.run(["python3", f"{MILES_HOME}/landuse/validation/validate_landuse.py", name, "2016", str(Y1)], capture_output=True, text=True)
    if vr.returncode != 0: sys.exit(vr.stderr[-2000:])
    Rv = pd.read_parquet(f"{V}/data/silo_validation_{name}.parquet"); d = Rv[(Rv.table == TABLE) & Rv.year.between(*YEARS)]
    assert sorted(d.year.unique()) == list(range(YEARS[0], YEARS[1] + 1)), f"window years {sorted(d.year.unique())}"
    m, o = float(d.model.mean()), float(d.observed.mean()); new = shift * (o / m) ** DAMP
    if abs(o - TARGET) > 5e-4: sys.exit(f"target {o:.5f} differs from {TARGET} (2017-2020 mean): abort")
    # diagnostics of the other levers the location model can move (definitions of calibrate.py; levers not changed here)
    c = Rv[(Rv.section == "D2 construction") & (Rv.table == "new dwellings vs permitted units") & Rv.year.between(*YEARS)]
    B = Rv[(Rv.section == "B composition") & (Rv.year == Y1) & Rv.geo.astype(str).str.match(r"^24\d{3}$")].copy(); B["tbl"] = B.table.str.replace(r" \[PUMS \d+\]", "", regex=True)
    lp = B[(B.tbl == "adults 18-34 living with parents") & (B["bin"].astype(str) == "0")]
    print(f"  construction: model {c.model.sum():.0f} / permitted {c.observed.sum():.0f} = {c.model.sum() / c.observed.sum():.3f}; "
          f"leave parents (share not living with parents, 18-34, county mean {Y1}): model {lp.model.mean():.4f} / ACS {lp.observed.mean():.4f} = {lp.model.mean() / lp.observed.mean():.3f}", flush=True)
    if len(log) and abs(np.log(log[-1]["value"]) - np.log(shift)) > 1e-3 and abs(np.log(log[-1]["ratio"]) - np.log(m / o)) > 1e-3:
        el = (np.log(m / o) - np.log(log[-1]["ratio"])) / (np.log(shift) - np.log(log[-1]["value"]))
        if el > 0.05: new = float(shift * np.clip(np.exp(-np.log(m / o) / el), 0.4, 2.5)); print(f"  secant step, elasticity {el:.3f}")
    log.append(dict(round=rnd, parameter=KEY, value=shift, model=m, target=o, ratio=m / o, next_value=round(new, 4)))
    pd.DataFrame(log).to_csv(LOGF, index=False)
    print(f"round {rnd}: shift {shift} -> persons moved share {m:.4f} (ACS mean 2017-2020 {o:.4f}, ratio {m / o:.4f}) -> next {new:.4f}", flush=True)
    if abs(m / o - 1) < TOL: break
    shift = round(new, 4)
final = min(log, key=lambda r: abs(r["ratio"] - 1))["value"]
json.dump(dict(P0, **{KEY: final}), open(OUTP, "w"), indent=1)
print(f"move shift {final} (round closest to the target) -> {OUTP}")
