#!/usr/bin/env python3
"""Out-of-sample land-use runs 2016-2024 with the calibrated parameters (calibrated on 2016-2020 only) and several random seeds,
followed by the validation of every year (landuse/validation/validate_landuse.py; 2021-2024 are the test years).
Usage: python landuse/run/run_seeds.py <n_seeds> [parallel=2] [end_year=2024]
Scenarios oos_s<seed> with WORKSPACE/2_silo/calibration/params.json (earlier models); OOS_SPEC=respec runs the re-estimated models
with landuse/calibration/calibrated_parameters.json (scenarios oos_respec_s<seed>).  Runs and logs: WORKSPACE/2_silo/run.
Environment: OOS_PARAMS = parameter file (default as above); OOS_TAG=<t> names the scenarios oos_<spec><t>_s<seed>;
OOS_SET="key=value;key=value" sets further properties (the adopted setup: landuse/run/adopted_settings.sh); OOS_SEEDS="1,2" runs
only these seeds (default 1..n_seeds)."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import subprocess, sys, os, re, json
from concurrent.futures import ThreadPoolExecutor
S = f"{WORKSPACE}/2_silo"; R = f"{S}/run"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 5; par = int(sys.argv[2]) if len(sys.argv) > 2 else 2; y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2024
SPEC = os.environ.get("OOS_SPEC", "record"); assert SPEC in ("record", "respec"), SPEC
P = json.load(open(os.environ.get("OOS_PARAMS") or (f"{MILES_HOME}/landuse/calibration/calibrated_parameters.json" if SPEC == "respec" else f"{S}/calibration/params.json")))
TAG = os.environ.get("OOS_TAG", ""); EXTRA = dict(kv.split("=", 1) for kv in os.environ.get("OOS_SET", "").split(";") if kv.strip())
def run(seed):
    name = f"oos_s{seed}" if SPEC == "record" and not TAG else f"oos_{'' if SPEC == 'record' else SPEC}{TAG}_s{seed}"
    if not os.path.exists(f"{R}/base/scenOutput/{name}/microData/futureYears/pp_{y1}.csv"):
        subprocess.run(["python3", f"{MILES_HOME}/landuse/run/write_properties.py", name, "2016", str(y1), "-1", str(seed)] + (["respec"] if SPEC == "respec" else []), check=True, capture_output=True)
        p = f"{R}/{name}.properties"; t = open(p).read()
        for k, v in P.items(): t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
        for k, v in EXTRA.items():
            t, n_ = re.subn(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M); assert n_ <= 1, k
            if n_ == 0: t += f"\n{k} = {v}\n"   # a key the template does not have is appended
        open(p, "w").write(t)
        rc = subprocess.run(["bash", f"{MILES_HOME}/landuse/run/run_silo.sh", p, os.environ.get("SILO_XMX", "24g")], env=dict(os.environ, MILES_WORKSPACE=WORKSPACE)).returncode   # 2026-10-29: heap from SILO_XMX
        if rc != 0: return f"{name}: SILO failed ({rc})"
    v = subprocess.run(["python3", f"{MILES_HOME}/landuse/validation/validate_landuse.py", name, "2016", str(y1)], capture_output=True, text=True)
    return f"{name}: validated" if v.returncode == 0 else f"{name}: validation failed\n{v.stderr[-2000:]}"
with ThreadPoolExecutor(par) as ex:
    for msg in ex.map(run, [int(x) for x in os.environ["OOS_SEEDS"].split(",")] if os.environ.get("OOS_SEEDS") else range(1, n + 1)): print(msg, flush=True)
