#!/usr/bin/env python3
"""Regenerate the SILO base-year files (hh/pp/dd/jj 2016) from the CORRECTED synthetic population, using the VAE pipeline's
own steps 05 (workplaces and jobs) and 06 (dwellings, SILO schema; population/cvae/steps) unchanged, with their output
directory redirected to WORKSPACE/1_vae/vae_outputs (01_preprocessed linked from the original run, 04_generated = corrected hh/pp).
The workplace step needs the MSTM peak travel-time skim; the original OMX is not on this Mac, the equivalent 1,588-zone
skim of the activity model (traveltime_auto.omx, matrix mat1) is used.  Output: vae_outputs/06_silo_input/{hh,pp,dd,jj}_2016.csv"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys, shutil, runpy
from pathlib import Path
ROOT = Path(PROJECT_ROOT); VAE = Path(VAE_HOME); V = Path(WORKSPACE) / "1_vae"   # VAE = generator data (outputs/)
CODE = Path(MILES_HOME) / "population" / "cvae"                                    # generator code (vaelib, steps)
OUTS = V / "vae_outputs"; OUTS.mkdir(exist_ok=True)
for d in ["00_raw_analysis", "01_preprocessed", "02_targets"]:
    if not (OUTS / d).exists(): os.symlink(VAE / "outputs" / d, OUTS / d)
(OUTS / "04_generated").mkdir(exist_ok=True)
for f in ["hh.parquet", "pp.parquet"]: shutil.copy(V / "output" / f, OUTS / "04_generated" / f)
sys.path.insert(0, str(CODE)); os.chdir(VAE)
import vaelib.config as config
config.OUTPUTS_DIR = OUTS                                   # the steps read config.OUTPUTS_DIR at import
config.SKIM_OMX = Path(ABIT_HOME) / "input/mito_los/skims/traveltime_auto.omx"
config.FORECAST_CSV = V / "output" / "employment_2016_lodes.csv"      # LODES 2016 job inventory by zone (Maryland), JOLTS vacancies
import vaelib.workplace as W, inspect
for _name, _cls in inspect.getmembers(W, inspect.isclass):      # the skim reader class: its __init__ takes matrix_name
    if "matrix_name" in inspect.signature(_cls.__init__).parameters:
        _orig = _cls.__init__
        _cls.__init__ = (lambda o: (lambda self, path=config.SKIM_OMX, matrix_name="mat1": o(self, path, matrix_name)))(_orig)
        print("skim reader patched:", _name, "->", config.SKIM_OMX.name, "mat1")
# the forecast path is a default argument bound when vaelib.workplace was imported: rebind it to the LODES inventory
_f = W.load_employment_forecast; _sig = inspect.signature(_f); _defs = tuple(config.FORECAST_CSV if n == "path" else p.default for n, p in _sig.parameters.items() if p.default is not inspect._empty)
_f.__defaults__ = _defs; print("forecast default rebound:", _f.__defaults__)
STEPS = ["06_silo_export.py"] if "06only" in sys.argv else ["05_workplace.py", "06_silo_export.py"]   # 06only: workplaces from external_workplaces.py
for step in STEPS:
    print(f"===== running {step} on the corrected population", flush=True)
    runpy.run_path(str(CODE / "steps" / step), run_name="__main__")
print("done:", sorted(p.name for p in (OUTS / "06_silo_input").glob("*.csv")))
