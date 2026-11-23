#!/usr/bin/env python3
"""One DAYMAP run on the 2016 base population with an isolated copy of a coefficient set (stage 3 calibration / validation runs).

    python3 activity/run_activity_model.py <name> --coef DIR [--seed N] [--sample 0.1] [--threads 6] [--xmx 8g] [--year 2016] [--skims base]

Same isolation as pipeline/run_chain.py (abit stage): the coefficient directory is copied to <run>/coef and modechoice.dir
points at the copy, because MarylandFullModeChoice re-anchors and rewrites modechoice_full_*.csv at every start.  Runs land
under <workspace>/3_abit/run/<name>/ (abit.log, output/{activities,legs}_<name>.csv, coef/).  The seed is passed as -Dabit.seed (AbitUtils,
2026-10-22); the household sample is deterministic (MarylandLosDataReader, seed 20240702), so seeds change only the model draws.
Importable: run(name, coef, seed, ...) -> run directory.
"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, os, re, shutil, subprocess, sys, time

ROOT = f"{PROJECT_ROOT}"; V = f"{WORKSPACE}"; A3 = f"{V}/3_abit"; ABIT = f"{ABIT_HOME}"
JAVA_HOME = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip()
CLASSES = f"{A3}/classes"; CP_FILE = f"{MILES_HOME}/activity/abit_classpath.txt"   # $HOME in it is expanded; MAIN = "abm.RunAbitMarylandLos"; LIB = f"{ABIT}/src/main/resources/lib/macosx64"


def run(name, coef, seed=1, sample=0.1, threads=6, xmx="8g", year=2016, skims="base", run_root=f"{A3}/run", force=False):
    d = f"{run_root}/{name}"; outs = [f"{d}/output/activities_{name}.csv", f"{d}/output/legs_{name}.csv"]
    if all(os.path.exists(o) for o in outs) and not force:
        print(f"{name}: output exists, skipped"); return d
    os.makedirs(d, exist_ok=True)
    rc = f"{d}/coef"; shutil.rmtree(rc, ignore_errors=True); shutil.copytree(coef, rc)
    env = dict(os.environ) | {"ABIT_RUN_ROOT": run_root, "ABIT_COEF_DIR": rc}
    sk = skims if os.path.isabs(skims) else (f"{A3}/skims" if skims == "base" else f"{A3}/skims/{skims}")
    r = subprocess.run([sys.executable, f"{MILES_HOME}/activity/write_properties.py", name, "base", str(year), str(sample), sk], capture_output=True, text=True, env=env)
    if r.returncode != 0: raise SystemExit(f"write_properties failed: {r.stdout}{r.stderr}")
    props = f"{run_root}/{name}.properties"; t = open(props).read()
    t = re.sub(r"^number.of.threads\s*=.*$", f"number.of.threads = {threads}", t, flags=re.M); open(props, "w").write(t)
    cp = f"{CLASSES}:{os.path.expandvars(open(CP_FILE).read().strip())}"
    cmd = [f"{JAVA_HOME}/bin/java", f"-Xmx{xmx}", f"-Dabit.seed={seed}", f"-Djava.library.path={LIB}", "-cp", cp, MAIN, props]
    t0 = time.time()
    with open(f"{d}/abit.log", "w") as log:
        log.write(f"# {name}: seed {seed}, sample {sample}, coef {coef}, started {time.ctime()}\n"); log.flush()
        rc_ = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=d).returncode
    ok = rc_ == 0 and all(os.path.exists(o) for o in outs)
    print(f"{name}: rc {rc_}, {time.time() - t0:.0f} s, outputs {'ok' if ok else 'MISSING'}")
    if not ok: raise SystemExit(f"ABIT {name} failed; see {d}/abit.log")
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("name"); ap.add_argument("--coef", required=True); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sample", type=float, default=0.1); ap.add_argument("--threads", type=int, default=6); ap.add_argument("--xmx", default="8g")
    ap.add_argument("--year", type=int, default=2016); ap.add_argument("--skims", default="base"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); run(a.name, a.coef, a.seed, a.sample, a.threads, a.xmx, a.year, a.skims, force=a.force)
