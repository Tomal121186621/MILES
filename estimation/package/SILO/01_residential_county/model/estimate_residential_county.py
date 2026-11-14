#!/usr/bin/env python3
"""Residential location, county level: choice of the destination county (44 SILO regions = Maryland counties and county
groups of the neighbouring states) of moving households (ACS PUMS movers 2014-2018, estimation sample), upper level of the
sequentially estimated nested logit. All 44 counties (no sampling); availability av_j.

Observed outcome: the destination PUMA, which can span several counties (chosen_set_j = 1 for each of them). The likelihood
is the probability of the set:
    log P_n = log( sum_j chosen_set_j * exp(V_j) ) - log( sum_j av_j * exp(V_j) )
written with Biogeme's WeightedLogSumExp (the same expression as the original estimator, mnl.py in input/code).
Weight: expected in-area share of destination and origin divided by its mean (column 'weight'); robust standard errors (WESML sandwich, as in the article; see the note above model()).
Inclusive values IV_B (zone x structure type, lambda_B) and IV_A (dwelling, lambda_A) are data columns, computed with the
final lower-level models (run 03 and 02 first if you want to recompute them; see README).
Car time under 20 min: coefficient fixed at 0 (as in the article). Start values = article estimates (Table est_region).

    python estimate_residential_county.py            estimate; Biogeme writes its report to ../output
    python estimate_residential_county.py --check    log-likelihood at the start values only (nothing written)
    python estimate_residential_county.py --check --start values.csv   same, at other values (csv: parameter,value)"""
import os, sys, tempfile
import pandas as pd
import biogeme.biogeme as bio
from biogeme.database import Database
from biogeme.expressions import Beta, Variable, WeightedLogSumExp
from biogeme.parameters import Parameters
from biogeme.results_processing import get_pandas_estimated_parameters

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = f"{HERE}/../input/data/estimation/county_estimation.parquet"
OUT = os.path.abspath(f"{HERE}/../output")
J = 44

# data column -> (parameter, article estimate, fixed)
PARAMS = {
    "d1":                ("B_cartime_under20", 0.0, True),
    "d2":                ("B_cartime_20_60", -0.0305, False),
    "d3":                ("B_cartime_over60", -0.0085, False),
    "d2_x_lninc":        ("B_cartime_20_60_x_lninc", 0.0047, False),
    "d3_x_lninc":        ("B_cartime_over60_x_lninc", 0.0032, False),
    "same_region":       ("B_previous_county", 2.1962, False),
    "adjacent":          ("B_bordering_previous_county", 0.9149, False),
    "same_state":        ("B_same_state", 0.9090, False),
    "IV_B":              ("LAMBDA_B_zone_structure_type", 0.3885, False),
    "IV_A":              ("LAMBDA_A_dwelling", 0.9240, False),
    "commute_log":       ("B_commute_sum_ln1p_time", -2.1432, False),
    "commute_log_x_inc": ("B_commute_x_lninc", 0.4514, False),
    "same_x_age":        ("B_previous_county_x_age_oldest", 0.0816, False),
    "growth":            ("B_school_learning_growth", 1.9934, False),
    "crime_x_child":     ("B_crime_x_children", -1.0535, False),
}


# Weighting. The article's robust (sandwich) covariance for the weighted (WESML) likelihood is H^-1 (sum_n w_n^2 g_n g_n') H^-1,
# with H the Hessian of sum_n w_n ln P_n (input/code/mnl.py). Biogeme's 'weight' formula gives the same estimates but a BHHH matrix
# sum_n w_n g_n g_n' (weight counted once), hence different robust s.e. Writing the weight inside the log-likelihood
# (log_like = w_n ln P_n, no 'weight' formula) gives the same log-likelihood, the same estimates and exactly the article's robust s.e.
# Default: that form. Option --biogeme-weight: Biogeme's 'weight' formula instead.
def model(start=None):
    df = pd.read_parquet(DATA).drop(columns=["household"])
    database = Database("residential_county", df)
    B = {c: Beta(n, (start or {}).get(n, v), None, None, int(fx)) for c, (n, v, fx) in PARAMS.items()}
    V = [sum((B[c] * Variable(f"{c}_{j}") for c in PARAMS), 0) for j in range(J)]
    log_num = WeightedLogSumExp(V, [Variable(f"chosen_set_{j}") for j in range(J)])
    log_den = WeightedLogSumExp(V, [Variable(f"av_{j}") for j in range(J)])
    ll = log_num - log_den
    if "--biogeme-weight" in sys.argv:
        return database, {"log_like": ll, "weight": Variable("weight")}
    return database, Variable("weight") * ll


def main():
    start = None
    if "--start" in sys.argv:
        s = pd.read_csv(sys.argv[sys.argv.index("--start") + 1]); start = dict(zip(s.parameter, s.value))
    database, ll = model(start)
    if "--check" in sys.argv:
        os.chdir(tempfile.mkdtemp())
        p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "residential_county_check"
        print(f"N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "residential_county"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
