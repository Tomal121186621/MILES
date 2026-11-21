#!/usr/bin/env python3
"""Residential location, dwelling level: choice of a dwelling within the destination PUMA (ACS PUMS movers 2014-2018,
estimation sample). Multinomial logit over the chosen dwelling (alternative 0) and the 29 dwellings sampled uniformly from the
dwellings of the same PUMA occupied by households that moved in within 12 months (the exact draws of the original estimation,
in the data). Uniform sampling: no correction term. Unweighted. Utility linear in the design columns <column>_<j> of the data
(j = 0..29). Start values = reference estimates (4 decimals).

    python estimate_residential_dwelling.py                 estimate; Biogeme writes its report to ../output
    python estimate_residential_dwelling.py --evaluate      log-likelihood at the start values only (nothing written); --check is the same
    python estimate_residential_dwelling.py --evaluate --holdout          same, on the hold-out sample (validation movers)
    python estimate_residential_dwelling.py --evaluate --start values.csv at other values (csv: parameter,value)"""
import os, sys, tempfile
import pandas as pd
import biogeme.biogeme as bio
from biogeme.database import Database
from biogeme.expressions import Beta, Variable
from biogeme.models import loglogit
from biogeme.parameters import Parameters
from biogeme.results_processing import get_pandas_estimated_parameters

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = f"{HERE}/../input/data/estimation/dwelling_estimation.parquet"
HOLDOUT = f"{HERE}/../input/data/holdout/dwelling_holdout.parquet"
OUT = os.path.abspath(f"{HERE}/../output")
J = 30

# design column of the data -> (parameter, reference estimate)
PARAMS = {
    "over30":            ("B_cost_share_above30", -4.5411),
    "over30_x_lninc":    ("B_cost_share_above30_x_lninc", -1.9322),
    "lncost":            ("B_ln_cost", 0.4398),
    "lncost_x_lninc":    ("B_ln_cost_x_lninc", 0.2652),
    "bed_short":         ("B_bedroom_shortfall", -0.6566),
    "bed_short_x_lninc": ("B_bedroom_shortfall_x_lninc", -0.1424),
    "bed_extra":         ("B_bedroom_excess", -0.5353),
    "bed_extra_x_lninc": ("B_bedroom_excess_x_lninc", 0.1621),
    "new5":              ("B_built_last5yrs", -0.0414),
    "new5_x_lninc":      ("B_built_last5yrs_x_lninc", 0.1306),
    "SFA":               ("ASC_SFA", 0.0314),
    "SFA_x_lninc":       ("B_SFA_x_lninc", -0.1641),
    "MF234":             ("ASC_MF2_4", -0.1255),
    "MF234_x_lninc":     ("B_MF2_4_x_lninc", -0.3343),
    "MF5plus":           ("ASC_MF5plus", -0.0781),
    "MF5plus_x_lninc":   ("B_MF5plus_x_lninc", -0.3099),
    "MH":                ("ASC_mobile_home", -0.2092),
    "MH_x_lninc":        ("B_mobile_home_x_lninc", -0.4727),
}


def model(start=None):
    df = pd.read_parquet(DATA)
    df = df.drop(columns=[c for c in df.columns if df[c].dtype == object])   # identifiers and type labels (text)
    database = Database("residential_dwelling", df)
    B = {c: Beta(n, (start or {}).get(n, v), None, None, 0) for c, (n, v) in PARAMS.items()}
    V = {j: sum((B[c] * Variable(f"{c}_{j}") for c in PARAMS), 0) for j in range(J)}
    av = {j: Variable(f"av_{j}") for j in range(J)}
    return database, loglogit(V, av, Variable("choice"))


def main():
    global DATA
    start = None
    if "--start" in sys.argv:
        s = pd.read_csv(sys.argv[sys.argv.index("--start") + 1]); start = dict(zip(s.parameter, s.value))
    if "--holdout" in sys.argv:
        DATA = HOLDOUT
    database, ll = model(start)
    if "--evaluate" in sys.argv or "--check" in sys.argv:
        os.chdir(tempfile.mkdtemp())
        p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "residential_dwelling_check"
        print(f"{'hold-out' if DATA == HOLDOUT else 'estimation'} sample: N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "residential_dwelling"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
