#!/usr/bin/env python3
"""Coefficient file of the re-specified school location choice for the schools step of the chain (landuse/schools/assign_schools.py
--coefficients), from the final models of the article table (estimation/development/tables/t_new_tables.py school() -> ESTIMATION_RESULTS/locations/
l07_school_{k8,hs,college}_coef.csv, step 'final'), in the format of write_inputs.py.  New file only:
  2_silo/schoolchoice/apply/school_choice_coefficients_respec.csv   segment,parameter,kind,term,value
No term of the final models uses the school-tour logsum (the logsum arrays of apply/ are not needed).
    python3 landuse/coefficients/write_school_location.py"""
import os as _os, sys as _sys  # TERP: configured locations (terp.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../..')))
from terp_env import TERP_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os
import pandas as pd
V = f"{WORKSPACE}"
L = f"{ESTIMATION_RESULTS}/locations"; OUT = f"{V}/2_silo/schoolchoice/apply/school_choice_coefficients_respec.csv"


def main():
    rows = []
    for seg, band in (("k8", "k8"), ("hs", "hs"), ("col", "college")):
        c = pd.read_csv(f"{L}/l07_school_{band}_coef.csv"); c = c[c.step == "final"].drop_duplicates("param", keep="last")
        f = pd.read_csv(f"{L}/l07_school_{band}_fit.csv").query("step == 'final'").iloc[0]; assert len(c) == int(f.K), (band, len(c), f.K)
        for n, v in zip(c.param, c.coef):
            kind = "size" if n.startswith(("mu_", "g_")) else "size_inter" if n.startswith("h_") else "utility"
            term = n[2:].replace("X", "*") if kind == "utility" else n[2:].replace("X", ":") if kind == "size_inter" else n
            rows.append(dict(segment=seg, parameter=n, kind=kind, term=term, value=v))
    assert not os.path.exists(OUT)
    pd.DataFrame(rows).to_csv(OUT, index=False); print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
