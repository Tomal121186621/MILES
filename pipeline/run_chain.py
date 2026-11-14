#!/usr/bin/env python3
"""Orchestration of the integrated land-use / travel loop (see pipeline/README.md and the documentation site).

    skims(2016) <- MATSim 2016 base (ABIT on the 2016 population, network_2024, the earliest network built)
    for Y in 2018, 2020, 2022, 2024, 2026:
        silo-step  Y-2 -> Y   with skims(Y-2), restart from the Y-2 microdata of the previous step (hash-checked)
        abit  Y               activity plans of the Y population with skims(Y-2)
        matsim-pop Y          ABIT weekly plans -> one-weekday MATSim population of the study area
        matsim Y net seed     assignment on the network of year Y (2024 for Y <= 2024, 2026 for 2026); 5 seeds in 2024 and 2026
        skims Y               AM-peak congested zone-to-zone car times (mean over the seeds) and the transit times of the year's network
                              (SwissRailRaptor on the pt2matsim-mapped MTA schedule, once per network year) -> 2_silo/input/skims/<Y>, 3_abit/skims/<Y>
        inner iteration (2024, 2026): repeat the five stages with skims(Y) until max |d population by county| < 0.5 % and
            max |d auto accessibility by zone| < 2 % between two successive SILO results (at most --max-inner = 3 repeats)

Every stage is idempotent and resumable: it writes <stage dir>/.done.json (inputs and outputs with size and content hash, duration)
and is skipped when that marker exists (--force reruns).  Every completed stage is appended to <runs root>/registry.jsonl.  Logs:
pipeline/logs/run_chain.log (master) and pipeline/logs/<stage>_<tag>.log (stage output).  --test runs everything under
pipeline/test/ on a 1 % sample with 2 MATSim iterations and never starts SILO (it prints the SILO command instead).

Commands (run_chain.py [--test] [--force] [--dry-run] <command> ...):
  silo-step Y0 Y1 [--iter K] [--seed S] [--skims TAG] [--from-scen NAME]    SILO Y0 -> Y1 (scenario chain_<Y0>_<Y1>[_itK])
  abit Y [--iter K] [--skims TAG] [--sample F]                                ABIT on the SILO population of year Y
  matsim-pop Y [--iter K]                                                     ABIT plans -> MATSim population
  matsim Y NETWORK SEED [--iter K] [--iterations N] [--sample F] [--toll F]   MATSim run (NETWORK = 2024 | 2026 | path)
  skims Y [--iter K] [--seeds a,b,c]                                          car skims from the MATSim run(s) of year Y + transit skims of its network
  loop [--skip-2016-base] [--max-inner 3] [--seeds-validation 1,2,3,4,5]      the whole chain 2016 -> 2026
  test                                                                        the 1 % smoke test (implies --test)
  status                                                                      list the completed stages
Paths and run constants are at the top of the file; stage directories: <runs root>/{silo,abit,matsim_pop,matsim,skims}/."""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import argparse, os, sys, json, subprocess, time, hashlib, re, shutil, gzip, datetime, glob
ROOT = f"{PROJECT_ROOT}"
V = f"{WORKSPACE}"; P = f"{V}/pipeline"; S = f"{V}/2_silo"; A3 = f"{V}/3_abit"; M4 = f"{V}/4_matsim"
ABIT = f"{ABIT_HOME}"; MAT = f"{MATSIM_HOME}"; LOGS = f"{P}/logs"
JAVA_HOME = subprocess.run(["/usr/libexec/java_home", "-v", "21"], capture_output=True, text=True).stdout.strip(); JAVA = f"{JAVA_HOME}/bin/java"
# MATSim: the runner of the I-695 study (Updated MATSim/code/matsim-run, class RunBaltimoreToll, MATSim 2024.0), run as in
# I695_pricing/02_run/run_matsim.sh with the constants of I695_pricing/config.py (STRAT, JVM, ASCS); mode choice stays in ABIT (hybrid design).
MATSIM_JAR = f"{MAT}/code/matsim-run/target/baltimore-matsim-1.0.jar"; MATSIM_MAIN = "de.umd.matsim.RunBaltimoreToll"
NETWORKS = {2024: f"{M4}/network/network_2024.xml.gz", 2026: f"{M4}/network/network_2026.xml.gz"}
NETWORK_OF_YEAR = {2016: 2024, 2018: 2024, 2020: 2024, 2022: 2024, 2024: 2024, 2026: 2026}
# transit of a network year (4_matsim/transit/TRANSIT_BUILD.md, 2026-10-22): the MTA GTFS feeds of 2026-10-21 (weekday 2026-10-21) converted with
# pt2matsim 24.4 and mapped onto network_<Y>; the MATSim run uses the mapper's output network (network_<Y>_pt: the car links of network_<Y>
# unchanged plus the artificial transit links the schedule references); the transit skims of the year are routed on the same schedule.
TRANSIT = {y: {"schedule": f"{M4}/transit/transitSchedule_{y}.xml.gz", "vehicles": f"{M4}/transit/transitVehicles_{y}.xml.gz", "network": f"{M4}/transit/network_{y}_pt.xml.gz"} for y in (2024, 2026)}
TRANSIT_SKIM_ARGS = ["--peak", "7", "9", "--step", "15", "--radius", "1600", "--extension", "0", "--max-tt", "180"]   # transit_skim.py: AM peak, departures every 15 min, one-mile walk access/egress, 3 h cap
# value of time (2026-11-02, author decision for the validation study): the USDOT rule of ABIT's tour mode choice, VOT_n = 0.5 x max(hhIncome_n, $5,000)
# / 2,080 h ($/h; hhIncome = annual household income, person attribute written by activities_to_matsim.py as ABIT computes it); marginal utility of
# money = performing (0.78 utils/h) / VOT_n (RunBaltimoreToll -Dincome.vot.form=usdot).  Before: income.vot.form=power, elasticity 0.6, median 84216.
MATSIM_STRAT = {"reroute.weight": "0.15", "tam.weight": "0.10", "tam.range": "1800", "tam.affectduration": "false", "income.vot.form": "usdot", "vot.share": "0.5", "vot.hours": "2080", "vot.income.floor": "5000"}
MATSIM_JVM = {"modechoice": "false", "innovoff": "0.9", "plan.memory": "5", "write.outputs": "true"}
ASC_FILE = f"{PRICING_HOME}/02_run/ascs_frozen.json"; ASCS = {"car": "0.00", "pt": "0.75", "ride": "-0.60", "walk": "0.10", "bike": "-2.10"}
# SILO: the rebuilt engine (landuse/run/run_silo.sh), properties from landuse/run/write_properties.py with the calibrated parameters of
# WORKSPACE/2_silo/calibration/params.json
SILO_RUN = f"{MILES_HOME}/landuse/run/run_silo.sh"; SILO_PARAMS = f"{S}/calibration/params.json"; ZONES = f"{S}/input/zoneSystem.csv"
# ABIT: compiled with javac into WORKSPACE/3_abit/classes (compile_abit()); classpath activity/abit_classpath.txt (jar paths, $HOME expanded);
# native libs for the omx reader
ABIT_CLASSES = f"{A3}/classes"; ABIT_CP = f"{MILES_HOME}/activity/abit_classpath.txt"; ABIT_MAIN = "abm.RunAbitMarylandLos"; ABIT_LIB = f"{ABIT}/src/main/resources/lib/macosx64"
# coefficient set of the abit stage (2026-10-23): the model of record, the behavioural TASHA-style set 3_abit/coef_tasha (TASHA generation,
# estimated destination MNL, estimated anchored locations, return-home logit and work attendance; run_params.csv: tasha.generation = true,
# dest.choice.model = mnl); ABIT_COEF_DIR overrides it (3_abit/coef_tasha_cal: calibrated variant; 3_abit/coef_calibrated: the earlier
# weekly generator; pristine: ABIT/input/maryland/coef).  ABIT_ATTENDANCE_FILE (countyfips,p): the year's work-at-home shares for the
# attendance step instead of the set's base-year table (ACS 2017-19).
ABIT_COEF = os.environ.get("ABIT_COEF_DIR") or f"{A3}/coef_tasha"
ABIT_ATTENDANCE = os.environ.get("ABIT_ATTENDANCE_FILE")
ABIT_BASE_SKIMS = ["distance_auto", "distance_nmt1"]   # skims the loop does not refresh (distances); TRANSIT_SKIMS are refreshed per network year
TRANSIT_SKIMS = ["bus_tt", "rail_tt00"]
YEARS = [2018, 2020, 2022, 2024, 2026]; VALIDATION_YEARS = {2024, 2026}
CONV_POP, CONV_ACC = 0.005, 0.02   # FRAMEWORK.md: 0.5 % county population, 2 % zone accessibility

class Cfg:
    def __init__(self, a):
        self.test = a.test or a.command == "test"; self.force = a.force; self.dry = a.dry_run
        self.R = a.runs_root or (f"{P}/test" if self.test else f"{P}/runs"); self.prefix = "test_" if self.test else "chain_"
        self.sample = a.sample if a.sample is not None else (0.01 if self.test else 0.10)
        self.iterations = a.iterations if a.iterations is not None else (2 if self.test else 100)
        self.threads = a.threads or (6 if self.test else 12); self.xmx = a.xmx or ("8g" if self.test else "32g"); self.silo_xmx = a.silo_xmx or "28g"
        self.seed = a.seed if getattr(a, "seed", None) is not None else 1
        os.makedirs(LOGS, exist_ok=True)
        for d in ["silo", "abit", "matsim_pop", "matsim", "skims"]: os.makedirs(f"{self.R}/{d}", exist_ok=True)
    def tag(self, y, k=0): return f"{y}" if not k else f"{y}_it{k}"

# ---------------------------------------------------------------- bookkeeping
def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(msg):
    line = f"[{now()}] {msg}"; print(line, flush=True)
    with open(f"{LOGS}/run_chain.log", "a") as f: f.write(line + "\n")
def qhash(path):
    """Content fingerprint that stays cheap on multi-GB files: size + sha256 of the first and last MiB (whole file below 2 MiB)."""
    if not os.path.exists(path): return None
    st = os.stat(path); h = hashlib.sha256(); h.update(str(st.st_size).encode())
    with open(path, "rb") as f:
        if st.st_size <= 2 << 20: h.update(f.read())
        else: h.update(f.read(1 << 20)); f.seek(-(1 << 20), 2); h.update(f.read(1 << 20))
    return {"path": path, "size": st.st_size, "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"), "sha256_head_tail": h.hexdigest()[:16]}
def marker(d): return f"{d}/.done.json"
def is_done(cfg, d):
    if cfg.force or not os.path.exists(marker(d)): return False
    return True
def mark_done(cfg, stage, tag, d, inputs, outputs, t0, extra=None):
    rec = {"stage": stage, "tag": tag, "dir": d, "finished": now(), "duration_s": round(time.time() - t0, 1), "test": cfg.test,
           "inputs": [qhash(p) for p in inputs if p], "outputs": [qhash(p) for p in outputs if p], **(extra or {})}
    json.dump(rec, open(marker(d), "w"), indent=1)
    with open(f"{cfg.R}/registry.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    log(f"{stage} {tag}: done in {rec['duration_s']} s -> {d}")
def run(cfg, cmd, logfile, env=None, cwd=None, shell=False):
    """Run a stage command, stdout+stderr to logfile; returns the exit code (0 without running in --dry-run)."""
    shown = cmd if shell else " ".join(f"<classpath: {c.count(':') + 1} entries>" if len(c) > 400 else f'"{c}"' if " " in c else c for c in cmd)
    log(f"cmd: {shown}\n    log: {logfile}")
    if cfg.dry: return 0
    e = dict(os.environ); e.update(env or {}); t0 = time.time()
    with open(logfile, "a") as lf:
        lf.write(f"\n=== {now()} {shown}\n"); lf.flush(); rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=e, cwd=cwd, shell=shell).returncode
    log(f"exit {rc} after {time.time() - t0:.0f} s")
    return rc
def state_load(cfg): return json.load(open(f"{cfg.R}/state.json")) if os.path.exists(f"{cfg.R}/state.json") else {"silo": {}, "skims": {}}
def state_save(cfg, st): json.dump(st, open(f"{cfg.R}/state.json", "w"), indent=1)

# ---------------------------------------------------------------- locations
def skim_dirs(cfg, tag):
    """(SILO skim dir, ABIT skim dir) of a skim tag. 'base' = the MSTM-derived 2016 skims the stages start from."""
    # ABIT side of 'base' (2026-10-23): the base car skims with the 2024 door-to-door transit skims (3_abit/skims/base_transit2024),
    # the skims the destination MNL of the model of record was estimated and validated with; ABIT_BASE_SKIM_DIR overrides it
    if tag == "base": return f"{S}/input/skims", os.environ.get("ABIT_BASE_SKIM_DIR") or f"{A3}/skims/base_transit2024"
    if cfg.test: return f"{cfg.R}/skims/{tag}/silo", f"{cfg.R}/skims/{tag}/abit"
    return f"{S}/input/skims/{tag}", f"{A3}/skims/{tag}"
def silo_scen_name(cfg, y0, y1, k): return f"{cfg.prefix}{y0}_{y1}" + (f"_it{k}" if k else "")
def silo_scen_dir(cfg, scen): return f"{cfg.R}/silo/{scen}/scenOutput/{scen}"
def find_silo_scen(cfg, year, name=None):
    """Scenario (name, scenOutput dir) that produced the microdata of `year`: the one given, else state.json, else a scan."""
    if year == 2016: return None, None
    if name: return name, silo_scen_dir(cfg, name)
    st = state_load(cfg)
    if str(year) in st["silo"]: return st["silo"][str(year)], silo_scen_dir(cfg, st["silo"][str(year)])
    hits = sorted(glob.glob(f"{cfg.R}/silo/*/scenOutput/*/microData/futureYears/pp_{year}.csv"), key=os.path.getmtime)
    if not hits and cfg.dry: n = silo_scen_name(cfg, year - 2, year, 0); return n, silo_scen_dir(cfg, n)
    if not hits: raise SystemExit(f"no SILO output with pp_{year}.csv under {cfg.R}/silo (run silo-step {year - 2} {year} first)")
    d = os.path.dirname(os.path.dirname(os.path.dirname(hits[-1]))); return os.path.basename(d), d
def microdata(cfg, year, scen_dir):
    """Paths of hh/pp/dd/jj/schools of a year: the stage-1 base files for 2016, else the SILO output (microData/ or futureYears/)."""
    if year == 2016: return {k: f"{S}/input/microData/{k}_2016.csv" for k in ["hh", "pp", "dd", "jj"]} | {"schools": f"{S}/input/schools_2016.csv"}
    out = {}
    for k in ["hh", "pp", "dd", "jj", "schools"]:
        for d in [f"{scen_dir}/microData/futureYears", f"{scen_dir}/microData"]:
            if os.path.exists(f"{d}/{k}_{year}.csv"): out[k] = f"{d}/{k}_{year}.csv"; break
    missing = [k for k in ["hh", "pp", "dd", "jj"] if k not in out]
    if missing and cfg.dry: return {k: f"{scen_dir}/microData/futureYears/{k}_{year}.csv" for k in ["hh", "pp", "dd", "jj", "schools"]}
    if missing: raise SystemExit(f"microdata {missing} of {year} missing in {scen_dir}")
    if "schools" not in out: log(f"note: no schools_{year}.csv in {scen_dir}; the 2016 school inventory is used (ids are stable)"); out["schools"] = f"{S}/input/schools_2016.csv"
    return out
def check_restart_hash(cfg, scen, files):
    """FRAMEWORK: the restart files must be the ones the previous step produced -> compare with that step's done marker."""
    m = marker(f"{cfg.R}/silo/{scen}") if scen else None
    if not m or not os.path.exists(m): return
    rec = {o["path"]: o["sha256_head_tail"] for o in json.load(open(m))["outputs"] if o}
    for p in files.values():
        if p in rec and qhash(p)["sha256_head_tail"] != rec[p]: raise SystemExit(f"restart file changed since it was produced: {p} (use --force to override)")
def network_path(net): return NETWORKS[int(net)] if str(net) in ("2024", "2026") else net
def network_year(net):
    """2024 or 2026 for a network argument (year or a path whose name carries the year)."""
    if str(net) in ("2024", "2026"): return int(net)
    m = re.search(r"(2024|2026)", os.path.basename(str(net)))
    if not m: raise SystemExit(f"no transit set for network {net}: TRANSIT covers network_2024 and network_2026 (4_matsim/transit/TRANSIT_BUILD.md)")
    return int(m.group(1))
def link(src, dst):
    if os.path.lexists(dst): os.remove(dst)
    os.symlink(src, dst)

# ---------------------------------------------------------------- stage: SILO
def silo_step(cfg, y0, y1, k=0, seed=None, skims_tag=None, from_scen=None):
    scen = silo_scen_name(cfg, y0, y1, k); base = f"{cfg.R}/silo/{scen}"; out = silo_scen_dir(cfg, scen); t0 = time.time()
    if is_done(cfg, base): log(f"silo-step {scen}: done, skipped"); return scen
    skims_tag = skims_tag or state_load(cfg)["skims"].get(str(y0), "base"); seed = seed if seed is not None else cfg.seed
    prev, prev_dir = find_silo_scen(cfg, y0, from_scen); files = microdata(cfg, y0, prev_dir); check_restart_hash(cfg, prev, files)
    sk_silo, _ = skim_dirs(cfg, skims_tag); auto = f"{sk_silo}/auto_peak_time.csv.gz"
    transit = f"{sk_silo}/transit_peak_time.csv.gz" if os.path.exists(f"{sk_silo}/transit_peak_time.csv.gz") else f"{S}/input/skims/transit_peak_time.csv.gz"
    for f in [auto, transit]:
        if not os.path.exists(f) and not cfg.dry: raise SystemExit(f"skim missing: {f}")
    # run base directory of this step: input -> 2_silo/input, microData/ = the restart files, skims/ = skims(y0)
    os.makedirs(f"{base}/microData", exist_ok=True); os.makedirs(f"{base}/skims", exist_ok=True); link(f"{S}/input", f"{base}/input")
    for kind, p in files.items(): link(p, f"{base}/microData/{kind}_{y0}.csv")
    link(auto, f"{base}/skims/auto_peak_time.csv.gz"); link(transit, f"{base}/skims/transit_peak_time.csv.gz")
    # properties: write_properties.py (writes 2_silo/run/<scen>.properties) -> this base directory, calibrated parameters, start-year skim keys
    subprocess.run(["python3", f"{MILES_HOME}/landuse/run/write_properties.py", scen, str(y0), str(y1), "-1", str(seed)], check=True, capture_output=True)
    src = f"{S}/run/{scen}.properties"; t = open(src).read(); os.remove(src)
    params = json.load(open(SILO_PARAMS)) if os.path.exists(SILO_PARAMS) else {}
    subs = {"base.directory": f"{base}/", "school.file.ascii": "microData/schools", "number.of.threads": str(cfg.threads), **{kk: str(vv) for kk, vv in params.items()}}
    for kk, vv in subs.items(): t = re.sub(rf"^{re.escape(kk)}\s*=.*$", f"{kk} = {vv}", t, flags=re.M)
    t = t.replace("auto.peak.sov.skim.2016 ", f"auto.peak.sov.skim.{y0} ").replace("transit.peak.time.2016 ", f"transit.peak.time.{y0} ")
    props = f"{cfg.R}/silo/{scen}.properties"; open(props, "w").write(t)
    log(f"silo-step {scen}: {y0} -> {y1}, restart from {prev or '2016 base files'}, skims '{skims_tag}', seed {seed}, params {params}")
    if cfg.test and not cfg.dry: log(f"test mode: SILO not started. Command: bash {SILO_RUN} {props} {cfg.silo_xmx}   (engine log 2_silo/run/logs/{scen}.log)"); return scen
    rc = run(cfg, ["bash", SILO_RUN, props, cfg.silo_xmx], f"{LOGS}/silo_{scen}.log", env={"MILES_WORKSPACE": WORKSPACE, "MILES_HOME": MILES_HOME})
    if cfg.dry: st = state_load(cfg); st["silo"][str(y1)] = scen; state_save(cfg, st); return scen
    outs = [f"{out}/microData/futureYears/{kk}_{y1}.csv" for kk in ["hh", "pp", "dd", "jj", "schools"]]
    if rc != 0 or not all(os.path.exists(o) for o in outs[:4]): raise SystemExit(f"SILO {scen} failed (rc {rc}); see 2_silo/run/logs/{scen}.log")
    mark_done(cfg, "silo-step", scen, base, list(files.values()) + [auto, transit, props], outs + [f"{out}/resultFileSpatial.csv"], t0, {"y0": y0, "y1": y1, "skims": skims_tag, "seed": seed, "params": params})
    st = state_load(cfg); st["silo"][str(y1)] = scen; state_save(cfg, st); return scen

def silo_metrics(scen_dir, year):
    """County population and zone auto accessibility of `year` from resultFileSpatial.csv (block 'Year <year>')."""
    import pandas as pd
    lines = open(f"{scen_dir}/resultFileSpatial.csv").read().split("\n"); i = lines.index(f"Year {year}") + 1; j = i + 1
    while j < len(lines) and lines[j] and not lines[j].startswith("Year "): j += 1
    df = pd.read_csv(__import__("io").StringIO("\n".join(lines[i:j]))); df = df.rename(columns={df.columns[0]: "zone"})
    cty = pd.read_csv(ZONES, usecols=["ZoneId", "COUNTYFIPS"]).set_index("ZoneId").COUNTYFIPS
    df["county"] = df.zone.map(cty); return df.groupby("county").population.sum(), df.set_index("zone").autoAccessibility
def acc_file(cfg, tag, year, seed=None):
    """logsum accessibility file (pipeline/accessibility.py) of a skim tag: <SILO skim dir>/accessibility_<year>[_seed<k>].csv,
    then <runs root>/skims/<tag>/, then data/accessibility_<year>.csv for the base skims; None if none exists."""
    nm = f"accessibility_{year}" + (f"_seed{seed}" if seed is not None else "") + ".csv"
    c = [f"{skim_dirs(cfg, tag)[0]}/{nm}", f"{cfg.R}/skims/{tag}/{nm}"] + ([f"{V}/data/{nm}"] if tag == "base" else [])
    return next((f for f in c if os.path.exists(f)), None)
def acc_change(cfg, prev_tag, cur_tag, year):
    """Change of the logsum accessibility A (utils) by zone x segment x purpose between the skims of two iterations, in utils and in
    $ (A / |beta_cost|, beta_cost in utils per $ from accessibility_<year>.json, key beta_cost), against the seed noise of A:
    threshold = 2 x the seed standard deviation (root mean square over the cells of the per-cell s.d. across the seed files
    accessibility_<year>_seed<k>.csv of the current skims).  Criterion: 95th percentile of |dA| below the threshold.
    Returns None if the logsum files are not there (then the Hansen criterion applies)."""
    import pandas as pd, numpy as np
    f0, f1 = acc_file(cfg, prev_tag, year), acc_file(cfg, cur_tag, year)
    if not f0 or not f1 or f0 == f1: return None
    key = ["zone", "segment", "purpose"]
    a0 = pd.read_csv(f0).set_index(key).A; a1 = pd.read_csv(f1).set_index(key).A
    d = (a1 - a0.reindex(a1.index)).abs().dropna()
    seeds = sorted(glob.glob(os.path.join(os.path.dirname(f1), f"accessibility_{year}_seed*.csv")))
    sd = None
    if len(seeds) >= 2:
        S_ = pd.concat([pd.read_csv(x).set_index(key).A for x in seeds], axis=1)
        sd = float(np.sqrt((S_.std(axis=1, ddof=1) ** 2).mean()))
    side = os.path.splitext(f1)[0] + ".json"
    bc = json.load(open(side)).get("beta_cost") if os.path.exists(side) else None
    thr = 2 * sd if sd else None
    rec = {"acc_files": [f0, f1], "acc_dA_max_utils": float(d.max()), "acc_dA_p95_utils": float(d.quantile(.95)), "acc_dA_mean_utils": float(d.mean()),
           "acc_seed_sd_utils": sd, "acc_threshold_utils": thr, "acc_beta_cost": bc,
           "acc_dA_p95_dollars": float(d.quantile(.95) / abs(bc)) if bc else None, "acc_threshold_dollars": float(thr / abs(bc)) if (bc and thr) else None,
           "acc_converged": bool(d.quantile(.95) < thr) if thr else None}
    return rec
def convergence(cfg, prev_scen, scen, year, prev_tag=None, cur_tag=None):
    """max relative change of county population and zone accessibility between two SILO results; the FRAMEWORK criteria.
    Baltimore 2026 (logsum accessibility): when the logsum accessibility files of the two iterations' skims exist (prev_tag, cur_tag),
    the accessibility criterion is the change of A in utils (and $) against two seed standard deviations of A (acc_change); otherwise
    the relative change of SILO's Hansen auto accessibility by zone < CONV_ACC."""
    p0, a0 = silo_metrics(silo_scen_dir(cfg, prev_scen), year); p1, a1 = silo_metrics(silo_scen_dir(cfg, scen), year)
    dp = ((p1 - p0).abs() / p0.clip(lower=1)); da = ((a1 - a0).abs() / a0.clip(lower=1e-6))[(a0 > 1e-3) | (a1 > 1e-3)]
    ac = acc_change(cfg, prev_tag, cur_tag, year) if (prev_tag and cur_tag) else None
    acc_ok = ac["acc_converged"] if (ac and ac["acc_converged"] is not None) else bool(da.max() < CONV_ACC)
    rec = {"year": year, "previous": prev_scen, "current": scen, "max_rel_dpop_county": float(dp.max()), "county_max": str(dp.idxmax()),
           "max_rel_dacc_zone": float(da.max()), "zone_max": int(da.idxmax()), "converged": bool(dp.max() < CONV_POP and acc_ok),
           "criteria": {"pop": CONV_POP, "acc": ("logsum: p95 |dA| < 2 seed s.d." if ac and ac["acc_converged"] is not None else CONV_ACC)}}
    if ac: rec.update(ac)
    with open(f"{cfg.R}/convergence_{year}.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    msg = f"max |dA| p95 {ac['acc_dA_p95_utils']:.4f} utils" + (f" (${ac['acc_dA_p95_dollars']:.2f})" if ac.get("acc_dA_p95_dollars") is not None else "") + (f" vs 2 seed s.d. {ac['acc_threshold_utils']:.4f}" if ac.get("acc_threshold_utils") else " (no seed files: Hansen criterion)") if ac else f"max |dacc| by zone {rec['max_rel_dacc_zone']:.3%} (zone {rec['zone_max']})"
    log(f"convergence {year} {prev_scen} -> {scen}: max |dpop| by county {rec['max_rel_dpop_county']:.4%} ({rec['county_max']}), {msg} -> {'CONVERGED' if rec['converged'] else 'not converged'}")
    return rec

# ---------------------------------------------------------------- stage: ABIT
def abit_classpath():
    """Maven classpath of ABIT (activity/abit_classpath.txt); a literal $HOME in it stands for the user's home directory."""
    return open(ABIT_CP).read().strip().replace("$HOME", os.path.expanduser("~"))
def compile_abit(cfg):
    if os.path.exists(f"{ABIT_CLASSES}/abm/RunAbitMarylandLos.class") and not cfg.force: return
    os.makedirs(ABIT_CLASSES, exist_ok=True); srcs = subprocess.run(["find", f"{ABIT}/src/main/java", "-name", "*.java"], capture_output=True, text=True).stdout.split()
    rc = run(cfg, [f"{JAVA_HOME}/bin/javac", "-nowarn", "-d", ABIT_CLASSES, "-cp", abit_classpath()] + srcs, f"{LOGS}/abit_compile.log")
    if rc != 0: raise SystemExit("ABIT compilation failed, see logs/abit_compile.log")
def abit(cfg, y, k=0, skims_tag=None, silo_scen=None, sample=None):
    tag = cfg.tag(y, k); name = f"{cfg.prefix}abit_{tag}"; d = f"{cfg.R}/abit/{name}"; t0 = time.time()
    if is_done(cfg, d): log(f"abit {tag}: done, skipped"); return d
    sample = sample or cfg.sample; st = state_load(cfg)
    skims_tag = skims_tag or (st["skims"].get(str(y), None) if k else st["skims"].get(str(y - 2), "base")) or "base"
    scen, scen_dir = (find_silo_scen(cfg, y, silo_scen) if y != 2016 else (None, None)); files = microdata(cfg, y, scen_dir)
    _, sk_abit = skim_dirs(cfg, skims_tag); compile_abit(cfg)
    # coefficient set: ABIT_COEF (env ABIT_COEF_DIR; default the model of record 3_abit/coef_tasha, 2026-10-23; the pristine
    # reference ABIT/input/maryland/coef stays untouched).  write_properties.py reads run_params.csv and targets_education.csv of the set.
    env = {"ABIT_RUN_ROOT": f"{cfg.R}/abit", "ABIT_COEF_DIR": f"{d}/coef"} | ({"SILO_SCEN_DIR": scen_dir} if scen_dir else {}); props = f"{cfg.R}/abit/{name}.properties"; coef = f"{d}/coef"
    if cfg.dry: log(f"abit {tag}: properties by write_properties.py {name} {scen or 'base'} {y} {sample} {sk_abit} (env {env}); modechoice.dir -> {coef}")
    else:
        # the mode-choice re-anchoring (RunAbitMarylandLos -> writeReanchored) rewrites modechoice_full_*.csv in modechoice.dir: give every run
        # its own copy of the coefficient directory so the shared inputs do not drift between runs (reproducibility)
        shutil.rmtree(coef, ignore_errors=True); shutil.copytree(ABIT_COEF, coef)
        r = subprocess.run(["python3", f"{MILES_HOME}/activity/write_properties.py", name, scen or "base", str(y), str(sample), sk_abit], capture_output=True, text=True, env=dict(os.environ) | env)
        if r.returncode != 0: raise SystemExit(f"write_properties failed: {r.stdout}{r.stderr}")
        t = open(props).read()
        t = re.sub(r"^modechoice.dir\s*=.*$", f"modechoice.dir = {coef}", t, flags=re.M); t = re.sub(r"^number.of.threads\s*=.*$", f"number.of.threads = {cfg.threads}", t, flags=re.M)
        if ABIT_ATTENDANCE: t += f"\ntasha.attendance.file = {ABIT_ATTENDANCE}\n"
        open(props, "w").write(t)
    log(f"abit {tag}: year {y}, population {scen or '2016 base'}, skims '{skims_tag}', sample {sample}")
    cp = f"{ABIT_CLASSES}:{abit_classpath()}"
    rc = run(cfg, [JAVA, f"-Xmx{cfg.xmx}", f"-Djava.library.path={ABIT_LIB}", "-cp", cp, ABIT_MAIN, props], f"{d}/abit.log", cwd=d)
    if cfg.dry: return d
    outs = [f"{d}/output/legs_{name}.csv", f"{d}/output/activities_{name}.csv"]
    if rc != 0 or not all(os.path.exists(o) for o in outs): raise SystemExit(f"ABIT {name} failed (rc {rc}); see {d}/abit.log")
    done = [l for l in open(f"{d}/abit.log") if "DONE. persons=" in l]; persons = int(done[-1].split("persons=")[1]) if done else None
    shutil.copy(f"{d}/abit.log", f"{LOGS}/abit_{tag}.log")
    mark_done(cfg, "abit", tag, d, list(files.values()) + [props] + [f"{sk_abit}/{s}.csv.gz" for s in ["traveltime_auto"] + ABIT_BASE_SKIMS + TRANSIT_SKIMS], outs, t0, {"year": y, "skims": skims_tag, "sample": sample, "persons": persons, "silo_scen": scen})
    return d

# ---------------------------------------------------------------- stage: ABIT plans -> MATSim population
def matsim_pop(cfg, y, k=0, silo_scen=None, src=None, residents_only=False, no_gateways=False):
    """src (optional, validation study 2026-11-02): {"activities", "legs", "pp", "hh"} of an ABIT run outside the chain (e.g. the final 2024
    replication, parquet); residents_only: activities_to_matsim.py --residents-only (BMR residents, no cordon gateways)."""
    tag = cfg.tag(y, k); d = f"{cfg.R}/matsim_pop/{tag}"; out = f"{d}/population_{tag}.xml.gz"; t0 = time.time()
    if is_done(cfg, d): log(f"matsim-pop {tag}: done, skipped"); return out
    name = f"{cfg.prefix}abit_{tag}"; ad = f"{cfg.R}/abit/{name}"; acts, legs = f"{ad}/output/activities_{name}.csv", f"{ad}/output/legs_{name}.csv"
    if src: acts, legs = src["activities"], src["legs"]
    if not os.path.exists(legs) and not cfg.dry: raise SystemExit(f"ABIT output missing: {legs} (run abit {y} first)")
    if src: files = {"pp": src["pp"], "hh": src["hh"]}
    else: scen, scen_dir = (find_silo_scen(cfg, y, silo_scen) if y != 2016 else (None, None)); files = microdata(cfg, y, scen_dir)
    os.makedirs(d, exist_ok=True)
    cmd = ["python3", f"{MILES_HOME}/pipeline/activities_to_matsim.py", "--activities", acts, "--legs", legs, "--pp", files["pp"], "--hh", files["hh"], "--out", out, "--expansion", str(1.0 / cfg.sample)] + (["--residents-only"] if residents_only else []) + (["--no-gateways"] if no_gateways else [])
    rc = run(cfg, cmd, f"{LOGS}/matsim_pop_{tag}.log")
    if cfg.dry: return out
    if rc != 0 or not os.path.exists(out): raise SystemExit(f"population conversion failed; see logs/matsim_pop_{tag}.log")
    stats = [l.strip() for l in open(f"{LOGS}/matsim_pop_{tag}.log") if l.startswith("MATSim population:")]
    mark_done(cfg, "matsim-pop", tag, d, [acts, legs, files["pp"], files["hh"]], [out], t0, {"year": y, "summary": stats[-1] if stats else None, "residents_only": residents_only, "no_gateways": no_gateways}); return out

# ---------------------------------------------------------------- stage: MATSim
def check_transit(cfg, net, sched):
    """The mapped schedule references network links by id: every route link and stop link must exist in the network."""
    c = f"{cfg.R}/matsim/transit_check_{os.path.basename(net).replace('.xml.gz', '')}_{os.path.basename(sched).replace('.xml.gz', '')}.json"
    if os.path.exists(c) and not cfg.force: return json.load(open(c))
    ids = set(); refs = set()
    with gzip.open(net, "rt") as f:
        for line in f:
            if "<link " in line: ids.add(re.search(r'id="([^"]+)"', line).group(1))
    with gzip.open(sched, "rt") as f:
        for line in f:
            if "<link refId=" in line: refs.add(re.search(r'refId="([^"]+)"', line).group(1))
            elif "<stopFacility " in line:
                m = re.search(r'linkRefId="([^"]+)"', line)
                if m: refs.add(m.group(1))
    rec = {"network": net, "schedule": sched, "network_links": len(ids), "schedule_link_refs": len(refs), "missing": sorted(refs - ids)[:50], "n_missing": len(refs - ids)}
    json.dump(rec, open(c, "w"), indent=1); log(f"transit check {os.path.basename(net)}: {len(refs):,} schedule link refs, {rec['n_missing']} missing in the network"); return rec
def matsim(cfg, y, net, seed, k=0, iterations=None, sample=None, toll="NONE", plans=None):
    tag = cfg.tag(y, k); d = f"{cfg.R}/matsim/{tag}_s{seed}"; t0 = time.time(); net_year = network_year(net); net_base = network_path(net); iterations = iterations or cfg.iterations; sample = sample or cfg.sample
    if is_done(cfg, d): log(f"matsim {tag} seed {seed}: done, skipped"); return d
    plans = plans or f"{cfg.R}/matsim_pop/{tag}/population_{tag}.xml.gz"
    tr = TRANSIT[net_year]; net = tr["network"]; SCHED, VEH_FULL = tr["schedule"], tr["vehicles"]   # the run network = the mapper's output of network_<year> (car links unchanged, transit links added)
    VEH = f"{d}/transitVehicles_scaled.xml.gz"   # vehicle capacity and PCE times the sample (assignment/transit/vehicle_types.py --scale): a bus of a 10 % run takes 10 % of a bus's road space
    for f in [MATSIM_JAR, net_base, net, plans, SCHED, VEH_FULL]:
        if not os.path.exists(f) and not cfg.dry: raise SystemExit(f"missing: {f}" + ("" if not f.startswith(f"{M4}/transit") else " (build the transit set: 4_matsim/transit/TRANSIT_BUILD.md)"))
    if not cfg.dry and check_transit(cfg, net, SCHED)["n_missing"]: raise SystemExit("transit schedule links missing in the network; re-map the schedule (4_matsim/transit/TRANSIT_BUILD.md)")
    if not cfg.dry:
        os.makedirs(d, exist_ok=True); r = subprocess.run(["python3", "-I", f"{MILES_HOME}/assignment/transit/vehicle_types.py", SCHED, VEH, "--scale", str(sample)], capture_output=True, text=True)
        if r.returncode != 0: raise SystemExit(f"vehicle_types.py failed: {r.stdout}{r.stderr}")
        log(f"transit vehicles scaled to the sample: {r.stdout.strip()}")
    asc = json.load(open(ASC_FILE)) if os.path.exists(ASC_FILE) else ASCS; flow = sample; stor = round(sample ** 0.75, 4)   # storage = flow^0.75 (I695_pricing/config.py rule)
    # disk (2026-11-02): events and plans written only at iteration 0 and the last one; link stats at the last one, averaged over its last 5 iterations
    opts = [f"-Dseed={seed}", f"-Dthreads={cfg.threads}", f"-Dwrite.events.interval={iterations}", f"-Dwrite.plans.interval={iterations}", f"-Dlinkstats.interval={iterations}", f"-Dlinkstats.average={min(5, iterations)}"] + [f"-D{kk}={vv}" for kk, vv in {**MATSIM_JVM, **MATSIM_STRAT}.items()] + [f"-Dasc.{m}={asc[m]}" for m in ["car", "pt", "ride", "walk", "bike"]]
    # extra JVM properties of a variant run (2026-11-14, transit routing test): MATSIM_EXTRA_D="key=value,key=value"; unset = no change
    extra = [kv.strip() for kv in os.environ.get("MATSIM_EXTRA_D", "").split(",") if kv.strip()]
    opts += [f"-D{kv}" for kv in extra]
    if extra: log(f"matsim extra properties: {extra}")
    cmd = [JAVA, f"-Xmx{cfg.xmx}"] + opts + ["-cp", MATSIM_JAR, MATSIM_MAIN, net, plans, SCHED, VEH, d, str(iterations), str(flow), str(stor), toll]
    log(f"matsim {tag} seed {seed}: network {os.path.basename(net)} (car links of {os.path.basename(net_base)}), {iterations} iterations, sample {sample} (flow {flow}, storage {stor}), transit {os.path.basename(SCHED)}, toll {toll}")
    rc = run(cfg, cmd, f"{LOGS}/matsim_{tag}_s{seed}.log")
    if cfg.dry: return d
    ev = f"{d}/output_events.xml.gz"
    if rc != 0 or not os.path.exists(ev): raise SystemExit(f"MATSim {tag} seed {seed} failed (rc {rc}); see logs/matsim_{tag}_s{seed}.log")
    mark_done(cfg, "matsim", f"{tag}_s{seed}", d, [net, plans, SCHED, VEH, MATSIM_JAR], [ev, f"{d}/output_plans.xml.gz"], t0, {"year": y, "seed": seed, "iterations": iterations, "sample": sample, "network": net, "network_base": net_base, "network_year": net_year, "schedule": SCHED, "vehicles": VEH, "vehicles_unscaled": VEH_FULL, "vehicle_scale": sample, "toll": toll, "jvm": {**MATSIM_JVM, **MATSIM_STRAT}, "extra": os.environ.get("MATSIM_EXTRA_D", ""), "asc": asc})
    return d

# ---------------------------------------------------------------- stage: skims
def transit_skims(cfg, net_year):
    """AM-peak transit skims of a network year (once per year: they depend on the schedule, not on the assignment seed):
    transit_skim.py (SwissRailRaptor on the pt2matsim-mapped MTA schedule of network_<year>) -> <runs root>/skims/transit_<year>/
    {transit_peak_time,bus_tt,rail_tt00}.csv.gz; the base skims are the prior for pairs with an endpoint beyond the network."""
    d = f"{cfg.R}/skims/transit_{net_year}"; t0 = time.time(); tr = TRANSIT[net_year]
    if is_done(cfg, d): return d
    os.makedirs(d, exist_ok=True)
    cmd = ["python3", f"{MILES_HOME}/pipeline/transit_skim.py", tr["network"], tr["schedule"], tr["vehicles"], d] + TRANSIT_SKIM_ARGS + ["--threads", str(min(cfg.threads, 6)), "--xmx", "6g"]
    rc = run(cfg, cmd, f"{LOGS}/skims_transit_{net_year}.log")
    if cfg.dry: return d
    outs = [f"{d}/{f}.csv.gz" for f in ["transit_peak_time"] + TRANSIT_SKIMS]
    if rc != 0 or not all(os.path.exists(o) for o in outs): raise SystemExit(f"transit_skim.py failed for network {net_year}; see logs/skims_transit_{net_year}.log")
    st = json.load(open(f"{d}/transit_skim_stats.json"))
    log(f"transit skims {net_year}: reachable on-network pairs all {st['reachable_share_on_network']['all']:.1%} / bus {st['reachable_share_on_network']['bus']:.1%}, mean {st['mean_min_reachable']['all']:.1f} min, prior {st['pairs_from_prior']:.1%}")
    mark_done(cfg, "transit-skims", str(net_year), d, [tr["network"], tr["schedule"], tr["vehicles"], f"{MILES_HOME}/pipeline/transit_skim.py", f"{MILES_HOME}/pipeline/TransitSkim.java"], outs, t0,
              {"network_year": net_year, "args": TRANSIT_SKIM_ARGS, "stats": {kk: st[kk] for kk in ["off_network_zones", "pairs_from_prior", "reachable_share_on_network", "mean_min_reachable", "compare_base_bmr_internal"]}})
    return d
def skims(cfg, y, k=0, seeds=None, net=None):
    import numpy as np, pandas as pd
    tag = cfg.tag(y, k); d = f"{cfg.R}/skims/{tag}"; t0 = time.time()
    if is_done(cfg, d): log(f"skims {tag}: done, skipped"); return tag
    runs = sorted(glob.glob(f"{cfg.R}/matsim/{tag}_s*")) if not seeds else [f"{cfg.R}/matsim/{tag}_s{s}" for s in seeds]
    runs = [r for r in runs if os.path.exists(f"{r}/output_events.xml.gz")]
    if not runs:
        if cfg.dry:
            log(f"skims {tag}: would run skims_from_matsim.py on every <runs root>/matsim/{tag}_s*/output_events.xml.gz, average the seeds, transit_skim.py on the schedule of network_{NETWORK_OF_YEAR.get(y, 2024)} and install the skims")
            st = state_load(cfg); st["skims"][str(y)] = tag; state_save(cfg, st); return tag
        raise SystemExit(f"no finished MATSim run for {tag} under {cfg.R}/matsim")
    net = network_path(net or json.load(open(marker(runs[0])))["network"]); net_year = network_year(net); os.makedirs(d, exist_ok=True); per_seed = []
    for r in runs:
        s = r.rsplit("_s", 1)[1]; pre = f"{d}/seed{s}/auto_peak_time"
        if not os.path.exists(pre + ".csv.gz") or cfg.force:
            # prior for zone pairs beyond the network or without a path: the 2016 base skim (the MSTM zone system covers six states, the network the Baltimore region)
            rc = run(cfg, ["python3", f"{MILES_HOME}/pipeline/skims_from_matsim.py", net, f"{r}/output_events.xml.gz", pre, "7", "9", f"{S}/input/skims/auto_peak_time.csv.gz"], f"{LOGS}/skims_{tag}.log")
            if cfg.dry: continue
            if rc != 0: raise SystemExit(f"matsim_to_skim failed for seed {s}; see logs/skims_{tag}.log")
        per_seed.append(pre + ".csv.gz")
    if cfg.dry: return tag
    # mean over the seeds (one seed: a copy); the seed spread is logged for the report
    M = [pd.read_csv(f).set_index(["FROM", "TO"]).VALUE for f in per_seed]; mean = pd.concat(M, axis=1).mean(axis=1)
    spread = (pd.concat(M, axis=1).max(axis=1) - pd.concat(M, axis=1).min(axis=1)) / mean if len(M) > 1 else None
    out = f"{d}/auto_peak_time"; mean.rename("VALUE").reset_index().to_csv(out + ".csv.gz", index=False, float_format="%.3f", compression="gzip")
    import openmatrix as omx
    z = np.array(sorted(set(mean.index.get_level_values(0)))); mat = mean.unstack().reindex(index=z, columns=z).values.astype(np.float32)
    with omx.open_file(out + ".omx", "w") as fo: fo["mat1"] = mat; fo.create_mapping("origins", z.astype(np.int32)); fo.create_mapping("destinations", z.astype(np.int32))
    sk_silo, sk_abit = skim_dirs(cfg, tag); os.makedirs(sk_silo, exist_ok=True); os.makedirs(sk_abit, exist_ok=True)
    td = transit_skims(cfg, net_year)   # transit of the year's network (schedule of that network), cached per network year
    link(out + ".csv.gz", f"{sk_silo}/auto_peak_time.csv.gz"); link(f"{td}/transit_peak_time.csv.gz", f"{sk_silo}/transit_peak_time.csv.gz")
    link(out + ".csv.gz", f"{sk_abit}/traveltime_auto.csv.gz"); link(out + ".omx", f"{sk_abit}/traveltime_auto.omx")
    for s in ABIT_BASE_SKIMS: link(f"{A3}/skims/{s}.csv.gz", f"{sk_abit}/{s}.csv.gz")
    for s in TRANSIT_SKIMS: link(f"{td}/{s}.csv.gz", f"{sk_abit}/{s}.csv.gz")
    log(f"skims {tag}: {len(per_seed)} seed(s), mean {mean[mean < 999].mean():.1f} min" + (f", seed spread median {spread.median():.2%}, p95 {spread.quantile(0.95):.2%}" if spread is not None else "") + f" -> {sk_silo}, {sk_abit}")
    mark_done(cfg, "skims", tag, d, [f"{r}/output_events.xml.gz" for r in runs] + [net] + [f"{td}/{f}.csv.gz" for f in ["transit_peak_time"] + TRANSIT_SKIMS], [out + ".csv.gz", out + ".omx"], t0,
              {"year": y, "seeds": [r.rsplit('_s', 1)[1] for r in runs], "silo_dir": sk_silo, "abit_dir": sk_abit, "mean_min": float(mean[mean < 999].mean()), "seed_spread_median": float(spread.median()) if spread is not None else None,
               "transit_skim": {"network_year": net_year, "dir": td, "schedule": TRANSIT[net_year]["schedule"], "files": ["transit_peak_time"] + TRANSIT_SKIMS}, "distance_skims": "base"})
    st = state_load(cfg); st["skims"][str(y)] = tag; state_save(cfg, st); return tag

# ---------------------------------------------------------------- the loop
def year_block(cfg, y, k, seeds, skims_tag_in):
    """ABIT, population, MATSim (all seeds) and skims of one year / inner iteration."""
    abit(cfg, y, k, skims_tag=skims_tag_in); matsim_pop(cfg, y, k)
    for s in seeds: matsim(cfg, y, NETWORK_OF_YEAR[y], s, k)
    return skims(cfg, y, k)
def loop(cfg, a):
    seeds_val = [int(s) for s in a.seeds_validation.split(",")]; seeds_other = seeds_val[:1]; st = state_load(cfg)
    if a.skip_2016_base: st["skims"]["2016"] = "base"; state_save(cfg, st); log("loop: 2016 skims = the MSTM base skims (MATSim 2016 base skipped)")
    elif st["skims"].get("2016") != "2016": year_block(cfg, 2016, 0, seeds_other, "base")
    for y in YEARS:
        y0 = y - 2; st = state_load(cfg); seeds = seeds_val if y in VALIDATION_YEARS else seeds_other
        scen = silo_step(cfg, y0, y, 0, skims_tag=st["skims"][str(y0)])
        if cfg.test and not cfg.dry: log("loop in test mode stops before the first SILO run"); return
        year_block(cfg, y, 0, seeds, st["skims"][str(y0)])
        if y in VALIDATION_YEARS:
            prev = scen; prev_tag = st["skims"][str(y0)]
            for k in range(1, a.max_inner + 1):
                st = state_load(cfg); cur_tag = st["skims"][str(y)]; cur = silo_step(cfg, y0, y, k, skims_tag=cur_tag)
                conv = convergence(cfg, prev, cur, y, prev_tag, cur_tag) if not cfg.dry else {"converged": False}
                year_block(cfg, y, k, seeds, st["skims"][str(y)]); prev = cur; prev_tag = cur_tag
                if conv["converged"]: log(f"inner iteration {y}: converged after repeat {k}"); break
            else: log(f"inner iteration {y}: not converged after {a.max_inner} repeats (criteria {CONV_POP:.1%} / {CONV_ACC:.0%}); last state kept")
    log("loop finished: " + json.dumps(state_load(cfg)))

def status(cfg):
    for f in sorted(glob.glob(f"{cfg.R}/*/*/.done.json") + glob.glob(f"{cfg.R}/*/*/*/.done.json")):
        r = json.load(open(f)); print(f"{r['stage']:11s} {r['tag']:14s} {r['finished']}  {r['duration_s']:8.0f} s  {r['dir']}")
    print("state:", json.dumps(state_load(cfg)))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="1 %% sample, 2 MATSim iterations, everything under pipeline/test/, SILO never started")
    ap.add_argument("--force", action="store_true", help="rerun stages whose done marker exists"); ap.add_argument("--dry-run", action="store_true", help="print the commands only")
    ap.add_argument("--runs-root"); ap.add_argument("--sample", type=float); ap.add_argument("--iterations", type=int); ap.add_argument("--threads", type=int)
    ap.add_argument("--xmx", help="java heap of ABIT and MATSim"); ap.add_argument("--silo-xmx"); ap.add_argument("--seed", type=int, help="SILO random seed")
    sp = ap.add_subparsers(dest="command", required=True)
    p = sp.add_parser("silo-step"); p.add_argument("y0", type=int); p.add_argument("y1", type=int); p.add_argument("--iter", type=int, default=0); p.add_argument("--skims"); p.add_argument("--from-scen")
    p = sp.add_parser("abit"); p.add_argument("y", type=int); p.add_argument("--iter", type=int, default=0); p.add_argument("--skims"); p.add_argument("--silo-scen")
    p = sp.add_parser("matsim-pop"); p.add_argument("y", type=int); p.add_argument("--iter", type=int, default=0); p.add_argument("--silo-scen")
    p.add_argument("--residents-only", action="store_true", help="BMR residents only, no cordon gateways (activities_to_matsim.py --residents-only)")
    p.add_argument("--no-gateways", action="store_true", help="all chain persons touching the BMR, cordon gateways and inflow cap off (activities_to_matsim.py --no-gateways)")
    for o in ["--activities", "--legs", "--pp", "--hh"]: p.add_argument(o, help="ABIT/SILO input outside the chain (all four together)")
    p = sp.add_parser("matsim"); p.add_argument("y", type=int); p.add_argument("network"); p.add_argument("seed", type=int); p.add_argument("--iter", type=int, default=0); p.add_argument("--toll", default="NONE"); p.add_argument("--plans")
    p.add_argument("--iterations", type=int, default=argparse.SUPPRESS, help="also accepted after the stage (same as the global option)"); p.add_argument("--sample", type=float, default=argparse.SUPPRESS)
    p = sp.add_parser("skims"); p.add_argument("y", type=int); p.add_argument("--iter", type=int, default=0); p.add_argument("--seeds"); p.add_argument("--network")
    p = sp.add_parser("loop"); p.add_argument("--skip-2016-base", action="store_true"); p.add_argument("--max-inner", type=int, default=3); p.add_argument("--seeds-validation", default="1,2,3,4,5")
    sp.add_parser("test"); sp.add_parser("status")
    a = ap.parse_args(); cfg = Cfg(a); log(f"run_chain {a.command} {'TEST ' if cfg.test else ''}runs root {cfg.R}" + (" (dry run)" if cfg.dry else ""))
    if a.command == "silo-step": silo_step(cfg, a.y0, a.y1, a.iter, skims_tag=a.skims, from_scen=a.from_scen)
    elif a.command == "abit": abit(cfg, a.y, a.iter, skims_tag=a.skims, silo_scen=a.silo_scen)
    elif a.command == "matsim-pop":
        src = {kk: getattr(a, kk) for kk in ["activities", "legs", "pp", "hh"]}
        if any(src.values()) and not all(src.values()): raise SystemExit("matsim-pop: --activities, --legs, --pp and --hh go together")
        matsim_pop(cfg, a.y, a.iter, silo_scen=a.silo_scen, src=src if all(src.values()) else None, residents_only=a.residents_only, no_gateways=a.no_gateways)
    elif a.command == "matsim": matsim(cfg, a.y, a.network, a.seed, a.iter, toll=a.toll, plans=a.plans)
    elif a.command == "skims": skims(cfg, a.y, a.iter, [int(s) for s in a.seeds.split(",")] if a.seeds else None, a.network)
    elif a.command == "loop": loop(cfg, a)
    elif a.command == "status": status(cfg)
    elif a.command == "test":   # the smoke test of the framework: ABIT 1 % of the 2016 base population, MATSim 2 iterations, skims; SILO command printed
        t0 = time.time(); abit(cfg, 2016, 0, skims_tag="base"); matsim_pop(cfg, 2016); matsim(cfg, 2016, 2024, 1); skims(cfg, 2016, net=2024)
        silo_step(cfg, 2016, 2018, 0, skims_tag="2016"); log(f"test finished in {time.time() - t0:.0f} s; stages: `run_chain.py --test status`")

if __name__ == "__main__": main()
