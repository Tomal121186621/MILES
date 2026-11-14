"""The `miles` command: one entry point for every step of the MILES chain.

    miles config                         show the configured locations and check them
    miles population train|generate|base-year|validate
    miles landuse coefficients|base-workplaces|calibrate|run|seeds|schools|validate
    miles activity parameters|distributions|run|replications|validate
    miles assignment network|transit|plans|run|seeds|validate
    miles chain ...                      the pipeline orchestrator (run_chain.py)
    miles estimate <model> [--check]     re-estimate one model of the estimation package
    miles docs serve|build               the documentation website

Every command accepts --dry-run (print what would run). Locations come from miles.toml (see miles.example.toml).
"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys

HOME = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ configuration
def load_config():
    path = os.environ.get("MILES_CONFIG") or os.path.join(HOME, "miles.toml")
    if not os.path.exists(path):
        return {}, path
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        import tomli as tomllib
    with open(path, "rb") as f:
        return tomllib.load(f), path


CFG, CFG_PATH = load_config()
JAVA = CFG.get("java", {})
PY = sys.executable
BIOGEME_PY = os.path.expanduser(CFG.get("python", {}).get("biogeme", "") or sys.executable)


def environment():
    """environment of every step: configured locations as MILES_* variables"""
    env = dict(os.environ)
    env["MILES_HOME"] = HOME
    env["MILES_CONFIG"] = CFG_PATH
    for k, v in CFG.get("paths", {}).items():
        env[f"MILES_{k.upper()}"] = os.path.abspath(os.path.expanduser(v))
    if JAVA.get("home"):
        env["JAVA_HOME"] = os.path.expanduser(JAVA["home"])
    env["PYTHONPATH"] = HOME + os.pathsep + env.get("PYTHONPATH", "")
    return env


DRY = False


def run(cmd, cwd=HOME, env=None, extra_env=None):
    e = environment() if env is None else env
    if extra_env:
        e.update({k: str(v) for k, v in extra_env.items()})
    shown = " ".join(f"{k}={v}" for k, v in (extra_env or {}).items())
    print(f"$ {shown + ' ' if shown else ''}{' '.join(shlex.quote(str(c)) for c in cmd)}", flush=True)
    if DRY:
        return 0
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=e)
    if r.returncode:
        sys.exit(r.returncode)
    return 0


def p(*parts):
    return os.path.join(HOME, *parts)


def workspace():
    w = environment().get("MILES_WORKSPACE")
    if not w:
        sys.exit("miles: set paths.workspace in miles.toml (copy miles.example.toml)")
    return w


# ------------------------------------------------------------------ config / sync
def cmd_config(a):
    print(f"configuration file: {CFG_PATH}{'' if os.path.exists(CFG_PATH) else '  (missing: copy miles.example.toml)'}")
    print(f"MILES_HOME         {HOME}")
    for k, v in CFG.get("paths", {}).items():
        v = os.path.abspath(os.path.expanduser(v))
        print(f"{k:<19} {v}  {'ok' if os.path.exists(v) else 'MISSING'}")
    java = shutil.which("java")
    print(f"java                {java or 'not found'}")
    print(f"biogeme python      {BIOGEME_PY}  {'ok' if os.path.exists(BIOGEME_PY) else 'MISSING'}")


def cmd_sync(a):
    """copy the land-use engine input files of the repository into the workspace (never overwrites without --force)"""
    src = p("landuse", "engine_inputs")
    dst = os.path.join(workspace(), "2_silo", "input")
    n = 0
    for f in sorted(os.listdir(src)):
        s, d = os.path.join(src, f), os.path.join(dst, f)
        if os.path.isfile(s) and (a.force or not os.path.exists(d)):
            print(f"copy {f}")
            if not DRY:
                os.makedirs(dst, exist_ok=True)
                shutil.copy2(s, d)
            n += 1
    print(f"{n} files copied to {dst}")


# ------------------------------------------------------------------ population
def cmd_population(a):
    cv = p("population", "cvae")
    if a.step == "train":
        run([PY, p("population", "cvae", "steps", "03_train.py"), "--tag", a.tag] + (["--smoke"] if a.smoke else []) + a.args, cwd=cv)
    elif a.step == "generate":
        run([PY, p("population", "cvae", "steps", "04_generate.py"), "--tag", a.tag] + a.args, cwd=cv)
    elif a.step == "all":
        run([PY, p("population", "cvae", "run_all.py")] + a.args, cwd=cv)
    elif a.step == "base-year":
        for s in ["fit_controls.py", "external_workplaces.py", "export_base_year.py"]:
            run([PY, p("population", "base_year", s)] + a.args)
    elif a.step == "validate":
        run([PY, p("population", "validation", "validate_population.py")] + a.args)
        run([PY, p("population", "validation", "validate_by_puma.py")])


# ------------------------------------------------------------------ land use
LANDUSE_ENV = {"CALIB_SPEC": "respec", "OOS_SPEC": "respec", "SCHOOL_SPEC": "respec"}   # the estimated models of MILES


def cmd_landuse(a):
    heap = a.heap or JAVA.get("silo_heap", "28g")
    if a.step == "coefficients":
        for s in ["write_residential_location.py", "write_car_ownership.py", "write_workplace_choice.py",
                  "write_school_location.py", "write_zone_attributes.py"]:
            run([PY, p("landuse", "coefficients", s)])
        cmd_sync(argparse.Namespace(force=True))
    elif a.step == "check":
        scratch = a.args[0] if a.args else os.path.join(workspace(), "2_silo", "engine_check", "scratch")
        for s in ["check_residential_location.py", "check_car_ownership.py", "check_workplace_choice.py",
                  "check_school_location.py"]:
            run([PY, p("landuse", "checks", s), scratch])
    elif a.step == "base-workplaces":
        run([PY, p("landuse", "inputs", "assign_base_workplaces.py")])
    elif a.step == "calibrate":
        run([PY, p("landuse", "calibration", "calibrate.py"), a.rounds, a.start_round],
            extra_env={**LANDUSE_ENV, "CALIB_TAG": a.tag, "SILO_XMX": heap})
    elif a.step == "run":
        name = a.name or f"landuse_{a.start}_{a.end}_seed{a.seed}"
        run([PY, p("landuse", "run", "write_properties.py"), name, a.start, a.end, "-1", a.seed, "respec"])
        run(["bash", p("landuse", "run", "run_silo.sh"), os.path.join(workspace(), "2_silo", "run", f"{name}.properties"), heap])
    elif a.step == "seeds":
        run([PY, p("landuse", "run", "run_seeds.py"), a.seeds, a.parallel, a.end], extra_env={**LANDUSE_ENV, "SILO_XMX": heap})
    elif a.step == "schools":
        run([PY, p("landuse", "schools", "assign_all_seeds.py")] + [str(s) for s in range(1, int(a.seeds) + 1)], extra_env=LANDUSE_ENV)
    elif a.step == "validate":
        if not a.args:
            sys.exit("miles landuse validate <scenario>")
        run([PY, p("landuse", "validation", "validate_landuse.py"), a.args[0], a.start, a.end])


# ------------------------------------------------------------------ activities
def cmd_activity(a):
    heap = a.heap or JAVA.get("activity_heap", "13g")
    if a.step == "parameters":
        run([PY, p("activity", "build_parameters.py"), "--force"])
    elif a.step == "distributions":
        run([PY, p("activity", "distributions", "build_distributions.py")],
            extra_env={"TASHA_JOINT_PB": "1", "TASHA_LIC_TYPES": "IO_ACC,IS,IO_REC,IO_OTH"})
    elif a.step == "run":
        run([PY, p("activity", "run_activity_model.py"), a.name or f"activities_{a.year}_seed{a.seed}", "--coef", p("activity", "parameters"),
             "--seed", a.seed, "--sample", a.sample, "--threads", a.threads, "--xmx", heap, "--year", a.year])
    elif a.step == "replications":
        script = p("activity", "run_replications.py")
        run([PY, script, "snapshot"])
        run([PY, script, "run", "--jobs", a.jobs, "--seeds", a.seeds])
        run([PY, script, "choose"])
    elif a.step == "validate":
        run([PY, p("activity", "validation", "validate_survey.py")] + a.args)


# ------------------------------------------------------------------ assignment
def cmd_assignment(a):
    heap = a.heap or JAVA.get("matsim_heap", "32g")
    if a.step == "network":
        run([PY, p("assignment", "network", "build_networks.py")] + a.args)
    elif a.step == "transit":
        run(["bash", p("assignment", "transit", "build_transit.sh")] + a.args)
    elif a.step == "plans":
        need = ["activities", "legs", "pp", "hh", "out"]
        if not all(getattr(a, k) for k in need):
            sys.exit("miles assignment plans --activities A --legs L --pp pp_2024.csv --hh hh_2024.csv --out population.xml.gz")
        raw = a.out.replace(".xml.gz", "_raw.xml.gz")
        run([PY, p("pipeline", "activities_to_matsim.py"), "--activities", a.activities, "--legs", a.legs, "--pp", a.pp, "--hh", a.hh,
             "--out", raw, "--no-gateways"])
        run([PY, p("pipeline", "snap_to_network.py"), a.network, raw, a.out])
    elif a.step == "run":
        cmd = [PY, p("pipeline", "run_chain.py"), "--sample", a.sample, "--iterations", a.iterations, "--threads",
               str(JAVA.get("threads", 12)), "--xmx", heap, "matsim", a.year, a.network_year, a.seed]
        if a.toll:
            cmd += ["--toll", a.toll]
        if a.plans:
            cmd += ["--plans", a.plans]
        run(cmd)
    elif a.step == "seeds":
        run(["bash", p("assignment", "run_seeds.sh"), a.first, a.last])
    elif a.step == "validate":
        run([PY, p("assignment", "validation", "validate_counts.py")] + a.args)
        run([PY, p("assignment", "validation", "screenlines.py")] + a.args)


# ------------------------------------------------------------------ chain, estimation, docs
def cmd_chain(a):
    run([PY, p("pipeline", "run_chain.py")] + a.args)


def cmd_estimate(a):
    pkg = p("estimation", "package")
    hits = [os.path.join(st, m) for st in ("SILO", "ABIT") for m in sorted(os.listdir(os.path.join(pkg, st)))
            if os.path.isdir(os.path.join(pkg, st, m)) and a.model in m]
    if a.model == "list" or not hits:
        for st in ("SILO", "ABIT"):
            for m in sorted(os.listdir(os.path.join(pkg, st))):
                if m[:2].isdigit():
                    print(f"{st}/{m}")
        return
    if len(hits) > 1:
        sys.exit("several models match: " + ", ".join(hits))
    model_dir = os.path.join(pkg, hits[0], "model")
    script = next(f for f in os.listdir(model_dir) if f.startswith("estimate_"))
    flags = ["--check"] if a.check and hits[0].startswith("SILO") else (["--evaluate"] if a.check else [])
    run([BIOGEME_PY, script] + flags, cwd=model_dir)
    if not a.check:
        run([BIOGEME_PY, "compare_with_reference.py"], cwd=model_dir)


def cmd_docs(a):
    run([PY, "-m", "mkdocs", a.action] + (["--strict"] if a.action == "build" else []))


# ------------------------------------------------------------------ parser
def main(argv=None):
    global DRY
    ap = argparse.ArgumentParser(prog="miles", description="MILES: population, land use, activities and traffic for Maryland")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("config", help="show and check the configured locations"); s.set_defaults(f=cmd_config)
    s = sub.add_parser("sync", help="copy the land-use engine inputs into the workspace")
    s.add_argument("--force", action="store_true"); s.set_defaults(f=cmd_sync)

    s = sub.add_parser("population", help="synthetic population (CVAE)")
    s.add_argument("step", choices=["train", "generate", "all", "base-year", "validate"])
    s.add_argument("--tag", default="full"); s.add_argument("--smoke", action="store_true")
    s.add_argument("args", nargs=argparse.REMAINDER); s.set_defaults(f=cmd_population)

    s = sub.add_parser("landuse", help="land use (SILO) and school location")
    s.add_argument("step", choices=["coefficients", "check", "base-workplaces", "calibrate", "run", "seeds", "schools", "validate"])
    s.add_argument("--start", default="2016"); s.add_argument("--end", default="2024"); s.add_argument("--seed", default="1")
    s.add_argument("--name"); s.add_argument("--seeds", default="5"); s.add_argument("--parallel", default="2")
    s.add_argument("--rounds", default="4"); s.add_argument("--start-round", default="1"); s.add_argument("--tag", default="miles")
    s.add_argument("--heap"); s.add_argument("args", nargs=argparse.REMAINDER); s.set_defaults(f=cmd_landuse)

    s = sub.add_parser("activity", help="activities (MILES-Day)")
    s.add_argument("step", choices=["parameters", "distributions", "run", "replications", "validate"])
    s.add_argument("--name"); s.add_argument("--year", default="2024"); s.add_argument("--seed", default="1")
    s.add_argument("--sample", default="0.1"); s.add_argument("--threads", default="6"); s.add_argument("--heap")
    s.add_argument("--seeds", default="1-10"); s.add_argument("--jobs", default="2")
    s.add_argument("args", nargs=argparse.REMAINDER); s.set_defaults(f=cmd_activity)

    s = sub.add_parser("assignment", help="traffic assignment (MATSim)")
    s.add_argument("step", choices=["network", "transit", "plans", "run", "seeds", "validate"])
    s.add_argument("--activities"); s.add_argument("--legs"); s.add_argument("--pp"); s.add_argument("--hh"); s.add_argument("--out")
    s.add_argument("--network", default="network_2024.xml.gz"); s.add_argument("--year", default="2024"); s.add_argument("--network-year", default="2024")
    s.add_argument("--seed", default="1"); s.add_argument("--iterations", default="100"); s.add_argument("--sample", default="0.1")
    s.add_argument("--toll"); s.add_argument("--plans"); s.add_argument("--first", default="1"); s.add_argument("--last", default="5")
    s.add_argument("--heap"); s.add_argument("args", nargs=argparse.REMAINDER); s.set_defaults(f=cmd_assignment)

    s = sub.add_parser("chain", help="the pipeline orchestrator (all stages, resumable)")
    s.add_argument("args", nargs=argparse.REMAINDER); s.set_defaults(f=cmd_chain)

    s = sub.add_parser("estimate", help="re-estimate a model of the estimation package with Biogeme")
    s.add_argument("model", help="folder name or part of it, e.g. car_ownership; 'list' to list the models")
    s.add_argument("--check", action="store_true", help="log-likelihood at the published estimates only")
    s.set_defaults(f=cmd_estimate)

    s = sub.add_parser("docs", help="the documentation website")
    s.add_argument("action", choices=["serve", "build"]); s.set_defaults(f=cmd_docs)

    a = ap.parse_args(argv)
    DRY = a.dry_run
    a.f(a)


if __name__ == "__main__":
    main()
