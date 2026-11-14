"""Runs the MATSim validation scripts (assignment/validation) on the given run folders and writes everything into a work directory.
No file outside the work directory is written."""
import glob, os, re, subprocess, sys
from common import V, ROOT, ORIOLE_HOME

VAL = f"{V}/4_matsim/validation"                    # validation data (workspace): link hours of the runs
VALC = f"{ORIOLE_HOME}/assignment/validation"       # validation scripts (repository)


def link_hours_for(run, seed, workdir):
    """Hourly link volumes of a run: <run>/link_hours.csv.gz, else WORKSPACE/4_matsim/validation/data/link_hours/link_hours_<name>.csv.gz, else extracted from the events file."""
    lhd = "link_hours_respec" if "runs_respec" in run else "link_hours"
    cand = [f"{run}/link_hours.csv.gz", f"{VAL}/data/{lhd}/link_hours_{os.path.basename(run).replace('2024_', '')}.csv.gz"]
    for c in cand:
        if os.path.exists(c): return c
    ev = f"{run}/output_events.xml.gz"
    if os.path.exists(ev):
        out = f"{workdir}/link_hours_extracted_s{seed}.csv.gz"
        if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(ev):
            subprocess.run([sys.executable, f"{VALC}/extract_link_hours.py", ev, f"{run}/output_transitVehicles.xml.gz", out], check=True)
        return out
    raise SystemExit(f"no hourly link volumes for {run}")


def sh(cmd, env=None, log=None, cwd=VALC):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)
    if log: open(log, "w").write(r.stdout + "\n" + r.stderr)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-3000:]); raise SystemExit(f"failed: {' '.join(cmd)}")
    return r.stdout


def exec_patched(script, replacements, argv, env=None):
    """Runs a script with some constants replaced in memory (the file itself is not touched)."""
    src = open(f"{VALC}/{script}").read()
    for a, b in replacements:
        assert a in src, (script, a); src = src.replace(a, b)
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "_patched_" + script)
    code = f"import sys, os\n__file__ = {VALC + '/' + script!r}\nsys.argv = {[script] + argv!r}\nsys.path.insert(0, {VALC!r})\nexec(compile(open({tmp!r}).read(), {VALC + '/' + script!r}, 'exec'), {{'__name__': '__main__', '__file__': {VALC + '/' + script!r}}})\n"
    open(tmp, "w").write(src)
    return sh([sys.executable, "-c", code], env=env)


def compute(runs, work, reuse=False, regional_force=True):
    """runs: list of run folders. Returns dict of output folders."""
    os.makedirs(work, exist_ok=True)
    root = f"{work}/runs"; lh = f"{work}/link_hours"; os.makedirs(root, exist_ok=True); os.makedirs(lh, exist_ok=True)
    seeds = []
    for k, r in enumerate(runs, 1):
        r = os.path.abspath(r); seeds.append(k)
        for p, tgt in [(f"{root}/2024_s{k}", r), (f"{lh}/link_hours_s{k}.csv.gz", link_hours_for(r, k, work))]:
            if os.path.lexists(p): os.remove(p)
            os.symlink(tgt, p)
    S = ",".join(map(str, seeds)); cnt = f"{work}/counts"; reg = f"{work}/regional"; art = f"{work}/art"
    for d in (f"{art}/sections/supp", f"{art}/figures", f"{work}/screenlines", f"{work}/tmas", f"{work}/mode_share", cnt, reg): os.makedirs(d, exist_ok=True)
    if reuse and os.path.exists(f"{cnt}/data/tables_over_seeds.csv"):
        O = dict(counts=cnt, regional=reg, art=art, tmas=f"{work}/tmas", mode=f"{work}/mode_share", screen=f"{work}/screenlines", seeds=seeds)
        diagnostics(O, root, work, reuse=True); return O
    env = dict(RUN_ROOT=root, LINK_HOURS=lh, OUT=cnt, SEEDS=S)
    print("counts", flush=True); sh([sys.executable, "validate_counts.py"], env, f"{work}/counts.log")
    print("routes, scatter", flush=True)
    sh([sys.executable, "route_table.py", f"{cnt}/data", f"{art}/sections/supp/tab_net_routes.tex"], env)
    sh([sys.executable, "scatter_fig.py", f"{cnt}/data", f"{cnt}/figures/fig_net_scatter"], env)
    print("screenlines", flush=True); sh([sys.executable, "screenlines.py", f"{cnt}/data", lh, f"{work}/screenlines", "--article", art], env, f"{work}/screenlines.log")
    print("regional", flush=True)
    sh([sys.executable, "regional_validation.py", root, reg, "--seeds", S] + (["--force"] if regional_force else []), env, f"{work}/regional.log")
    print("tmas", flush=True)
    exec_patched("tmas_hourly.py", [('ART = f"{V}/5_reports/article"', f'ART = {art!r}')], [f"{work}/tmas"], env)
    print("mode share", flush=True); sh([sys.executable, "mode_share.py", root, f"{work}/mode_share"], env)
    O = dict(counts=cnt, regional=reg, art=art, tmas=f"{work}/tmas", mode=f"{work}/mode_share", screen=f"{work}/screenlines", seeds=seeds)
    diagnostics(O, root, work); return O


def diagnostics(O, root, work, reuse=False):
    """Diagnostics of the count comparison (validation_diagnostics.py), the coverage estimate (coverage_estimate.py) and the maps
    (validation_map.py), written to <work>/diagnostics. With reuse, steps whose outputs exist are skipped."""
    d = f"{work}/diagnostics"; os.makedirs(d, exist_ok=True)
    env = dict(COUNTS_DATA=f"{O['counts']}/data", TMAS_DATA=f"{O['tmas']}/data", REGIONAL_DATA=f"{O['regional']}/data", SCREEN_DATA=f"{O['screen']}/data", RUN_ROOT=root, LINK_HOURS=f"{work}/link_hours", OUT=d)
    if not reuse:      # the link caches belong to one set of runs
        for f in ("links_map.parquet", "links_seed_stats.parquet", "stations_direction_volumes.csv"):
            if os.path.exists(f"{d}/data/{f}"): os.remove(f"{d}/data/{f}")
    if not (reuse and os.path.exists(f"{d}/data/diagnostics.json")):
        print("diagnostics", flush=True); sh([sys.executable, "validation_diagnostics.py"], env, f"{d}/diagnostics.log")
    if not (reuse and os.path.exists(f"{d}/data/coverage_estimate.csv")):
        print("coverage", flush=True); sh([sys.executable, "coverage_estimate.py"], env, f"{d}/coverage.log")
    if not (reuse and os.path.exists(f"{d}/figures/validation_map.html")):
        print("maps", flush=True); sh([sys.executable, "validation_map.py"], env, f"{d}/maps.log")
    O["diag"] = d


if __name__ == "__main__":
    runs = sys.argv[2:]; print(compute(runs, sys.argv[1]))
