#!/usr/bin/env python3
"""Residential location, dwelling level: choice of a dwelling within the destination PUMA (ACS PUMS movers 2014-2018,
estimation sample). Multinomial logit over the chosen dwelling (alternative 0) and the 29 dwellings sampled uniformly from
the PUMA's market of the year (the exact draws of the original estimation, in the data). Uniform sampling: no correction term.
Unweighted. Utility linear in the design columns <column>_<j> of the data (j = 0..29). Start values = article estimates
(Table est_dwelling).

    python estimate_residential_dwelling.py            estimate; Biogeme writes its report to ../output
    python estimate_residential_dwelling.py --check    log-likelihood at the start values only (nothing written)
    python estimate_residential_dwelling.py --check --start values.csv   same, at other values (csv: parameter,value)"""
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
OUT = os.path.abspath(f"{HERE}/../output")
J = 30

# design column of the data -> (parameter, article estimate)
PARAMS = {
    "bur_lo":            ("B_cost_share_below30", 2.2014),
    "bur_mid":           ("B_cost_share_30_50", -6.7986),
    "bur_mid_x_lninc":   ("B_cost_share_30_50_x_lninc", -4.6584),
    "bur_hi":            ("B_cost_share_above50", -2.7052),
    "bur_hi_x_lninc":    ("B_cost_share_above50_x_lninc", -1.1702),
    "lncost":            ("B_ln_cost", 0.1868),
    "lncost_x_lninc":    ("B_ln_cost_x_lninc", 0.3830),
    "bed_short":         ("B_bedroom_shortfall", -0.8743),
    "bed_short_x_lninc": ("B_bedroom_shortfall_x_lninc", -0.2195),
    "bed_extra":         ("B_bedroom_excess", -0.2528),
    "bed_extra_x_lninc": ("B_bedroom_excess_x_lninc", 0.1543),
    "new5":              ("B_built_last5yrs", -0.0274),
    "new5_x_lninc":      ("B_built_last5yrs_x_lninc", 0.1153),
    "SFA":               ("ASC_SFA", 0.1309),
    "SFA_x_child":       ("B_SFA_x_children", -0.2164),
    "SFA_x_ageU35":      ("B_SFA_x_oldest_under35", 0.1610),
    "SFA_x_age50_64":    ("B_SFA_x_oldest_50_64", -0.1778),
    "SFA_x_age65":       ("B_SFA_x_oldest_65plus", -0.1530),
    "SFA_x_lninc":       ("B_SFA_x_lninc", -0.1220),
    "MF234":             ("ASC_MF2_4", 0.0780),
    "MF234_x_size":      ("B_MF2_4_x_hhsize_minus1", -0.1011),
    "MF234_x_child":     ("B_MF2_4_x_children", -0.1970),
    "MF234_x_ageU35":    ("B_MF2_4_x_oldest_under35", 0.2743),
    "MF234_x_age50_64":  ("B_MF2_4_x_oldest_50_64", -0.2671),
    "MF234_x_age65":     ("B_MF2_4_x_oldest_65plus", -0.3780),
    "MF234_x_lninc":     ("B_MF2_4_x_lninc", -0.3138),
    "MF5plus":           ("ASC_MF5plus", -0.0494),
    "MF5plus_x_size":    ("B_MF5plus_x_hhsize_minus1", -0.1557),
    "MF5plus_x_child":   ("B_MF5plus_x_children", -0.1819),
    "MF5plus_x_ageU35":  ("B_MF5plus_x_oldest_under35", 0.4494),
    "MF5plus_x_age50_64": ("B_MF5plus_x_oldest_50_64", -0.0327),
    "MF5plus_x_age65":   ("B_MF5plus_x_oldest_65plus", 0.4850),
    "MF5plus_x_lninc":   ("B_MF5plus_x_lninc", -0.2448),
    "MH":                ("ASC_mobile_home", -0.2142),
    "MH_x_ageU35":       ("B_mobile_home_x_oldest_under35", -0.0801),
    "MH_x_age50_64":     ("B_mobile_home_x_oldest_50_64", 0.2580),
    "MH_x_age65":        ("B_mobile_home_x_oldest_65plus", 0.1130),
    "MH_x_lninc":        ("B_mobile_home_x_lninc", -0.4740),
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
    start = None
    if "--start" in sys.argv:
        s = pd.read_csv(sys.argv[sys.argv.index("--start") + 1]); start = dict(zip(s.parameter, s.value))
    database, ll = model(start)
    if "--check" in sys.argv:
        os.chdir(tempfile.mkdtemp())
        p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "residential_dwelling_check"
        print(f"N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "residential_dwelling"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
