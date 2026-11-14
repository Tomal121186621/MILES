#!/usr/bin/env python3
"""Out-of-sample land-use runs 2016-2024 with the calibrated parameters (calibration/params.json, calibrated on 2016-2020 only)
and several random seeds, followed by the validation of every year (validation/validate_silo.py; 2021-2024 are the test years).
Usage: run_oos.py <n_seeds> [parallel=2] [end_year=2024]   Scenarios: oos_s<seed>; log run/logs/oos.log
2026-11-09: OOS_SPEC=respec runs the re-specified models with calibration/params_respec.json (scenarios oos_respec_s<seed>)."""
import subprocess, sys, os, re, json
from concurrent.futures import ThreadPoolExecutor
S = "/Users/raassarkertomal/Documents/SILO MITO Chayan/VAE-SILO-MITO-MATSIM/Validation_2026/2_silo"; R = f"{S}/run"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 5; par = int(sys.argv[2]) if len(sys.argv) > 2 else 2; y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2024
SPEC = os.environ.get("OOS_SPEC", "record"); assert SPEC in ("record", "respec"), SPEC
P = json.load(open(f"{S}/calibration/params{'_respec' if SPEC == 'respec' else ''}.json"))
def run(seed):
    name = f"oos_respec_s{seed}" if SPEC == "respec" else f"oos_s{seed}"
    if not os.path.exists(f"{R}/base/scenOutput/{name}/microData/futureYears/pp_{y1}.csv"):
        subprocess.run(["python3", f"{R}/make_properties.py", name, "2016", str(y1), "-1", str(seed)] + (["respec"] if SPEC == "respec" else []), check=True, capture_output=True)
        p = f"{R}/{name}.properties"; t = open(p).read()
        for k, v in P.items(): t = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k} = {v}", t, flags=re.M)
        open(p, "w").write(t)
        rc = subprocess.run(["bash", f"{R}/run_silo.sh", p, os.environ.get("SILO_XMX", "24g")]).returncode   # 2026-10-29: heap from SILO_XMX
        if rc != 0: return f"{name}: SILO failed ({rc})"
    v = subprocess.run(["python3", f"{S}/validation/validate_silo.py", name, "2016", str(y1)], capture_output=True, text=True)
    return f"{name}: validated" if v.returncode == 0 else f"{name}: validation failed\n{v.stderr[-2000:]}"
with ThreadPoolExecutor(par) as ex:
    for msg in ex.map(run, range(1, n + 1)): print(msg, flush=True)
