"""Configured locations of an MILES installation.

MILES_HOME   this repository (code, coefficients, parameters)
WORKSPACE     the folder with data and runs
The other locations are optional external checkouts. Values come from environment variables (set by the `miles`
command) or from miles.toml at the repository root.
"""
import os

MILES_HOME = os.path.dirname(os.path.abspath(__file__))


def _config():
    path = os.environ.get("MILES_CONFIG") or os.path.join(MILES_HOME, "miles.toml")
    if not os.path.exists(path):
        return {}
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        import tomli as tomllib
    with open(path, "rb") as f:
        return tomllib.load(f).get("paths", {})


_CFG = _config()


def _get(key, default=None):
    v = os.environ.get(f"MILES_{key.upper()}") or _CFG.get(key) or default
    return os.path.abspath(os.path.expanduser(v)) if v else None


WORKSPACE = _get("workspace")
if WORKSPACE is None:
    raise SystemExit("MILES: set paths.workspace in miles.toml (copy miles.example.toml) or MILES_WORKSPACE")
PROJECT_ROOT = _get("project_root", os.path.dirname(WORKSPACE))
ESTIMATION_RESULTS = _get("estimation_results", os.path.join(WORKSPACE, "side_experiments", "respec_2026-11", "step_by_step"))
ABIT_HOME = _get("abit_home", os.path.join(PROJECT_ROOT, "ABIT"))
MATSIM_HOME = _get("matsim_home", os.path.join(PROJECT_ROOT, "Updated MATSim"))
VAE_HOME = _get("vae_home", os.path.join(PROJECT_ROOT, "Updated VAE"))
PRICING_HOME = _get("pricing_home", os.path.join(PROJECT_ROOT, "I695_pricing"))
