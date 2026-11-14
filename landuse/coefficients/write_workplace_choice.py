#!/usr/bin/env python3
"""Engine coefficient file of the re-specified workplace choice (job.choice.model = respec), from the final model of the article table
(estimation/development/tables/t_new_tables.py workplace() -> ESTIMATION_RESULTS/workplace/w04_coef.csv, step 'final').  New file only:
  2_silo/input/workplace_choice_coefficients_unanchored.csv   parameter,estimate   (engine names of JobDataManagerImpl.rtsCoefficients)
Centring: the estimation's time interactions are t x (x - m_x), m_x = estimation-half mean (wdc.MEAN); the engine has t x x, so
b_t(engine) = b_t - sum_x b_tx m_x (exact reparametrisation; the interaction coefficients are unchanged).
Names: t*x_c -> b_tX<x>; lt, intra, cc, cs -> b_lt, b_intra, b_cc, b_cs; dcw -> b_dc; accw -> b_accw; reg_<r> -> b_reg_<r> (oth -> other;
the engine's zones file labels DC 'dc', the base with 'bmc'); z_<s>*<x> -> b_<s>X<x>; mu -> mu_size; g_<type> unchanged.
No ACS anchoring of the DC term (the record model's file *_dcacs has one): that is a calibration step to redo.
    python3 landuse/coefficients/write_workplace_choice.py"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
V = f"{WORKSPACE}"
W = f"{ESTIMATION_RESULTS}/workplace"; INP = f"{V}/2_silo/input"
sys.path.insert(0, f"{TERP_HOME}/estimation/development/workplace_choice"); import wdc   # noqa: E402  (MEAN: centring constants)


def engine_name(p):
    if p.startswith("t*") and p.endswith("_c"): return "b_tX" + p[2:-2]
    if p in ("t", "lt", "intra", "cc", "cs", "accw"): return "b_" + p
    if p == "dcw": return "b_dc"
    if p.startswith("reg_"): return "b_reg_" + {"oth": "other"}.get(p[4:], p[4:])
    if p.startswith("z_"): b, *x = p[2:].split("*"); return "b_" + b + "".join("X" + q for q in x)
    if p == "mu": return "mu_size"
    if p.startswith("g_"): return p
    raise KeyError(p)


def main():
    c = pd.read_csv(f"{W}/w04_coef.csv"); c = c[c.step == "final"].drop_duplicates("param", keep="last").set_index("param").coef
    f = pd.read_csv(f"{W}/w04_fit.csv").query("step == 'final'").iloc[0]; assert len(c) == int(f.K)
    out = {engine_name(p): v for p, v in c.items()}
    shift = sum(v * wdc.MEAN[p[2:-2]] for p, v in c.items() if p.startswith("t*") and p.endswith("_c"))
    out["b_t"] = c["t"] - shift
    print("b_t centred", c["t"], "-> engine", out["b_t"], "(shift", shift, ")")
    p = f"{INP}/workplace_choice_coefficients_unanchored.csv"; assert not os.path.exists(p)
    pd.DataFrame({"parameter": list(out), "estimate": list(out.values())}).to_csv(p, index=False)
    print(pd.read_csv(p).to_string(index=False))


if __name__ == "__main__":
    main()
