#!/usr/bin/env python3
"""Residential location, zone x structure-type level: choice of a cell (zone, structure type) within the household's county
(Regional Travel Survey 2017/18, estimation half, households with the age of their members). Multinomial logit over the
observed cell (alternative 0) and 29 cells sampled uniformly from the county's cells with dwellings of that type (the exact
draws of the original estimation, in the data); no sampling correction (uniform sampling). Weighted exogenous sample maximum
likelihood: weight = RTS household weight / its mean (column 'weight'); robust standard errors (WESML sandwich, as in the article; see the note above model()). Utility linear in the design
columns <column>_<j> of the data (j = 0..29). Start values = article estimates (Table est_zone).

    python estimate_residential_zone_structure_type.py            estimate; Biogeme writes its report to ../output
    python estimate_residential_zone_structure_type.py --check    log-likelihood at the start values only (nothing written)
    python estimate_residential_zone_structure_type.py --check --start values.csv   same, at other values (csv: parameter,value)"""
import os, sys, tempfile
import pandas as pd
import biogeme.biogeme as bio
from biogeme.database import Database
from biogeme.expressions import Beta, Variable
from biogeme.models import loglogit
from biogeme.parameters import Parameters
from biogeme.results_processing import get_pandas_estimated_parameters

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = f"{HERE}/../input/data/estimation/zone_estimation.parquet"
OUT = os.path.abspath(f"{HERE}/../output")
J = 30

# design column of the data -> (parameter, article estimate)
PARAMS = {
    "lnD":             ("B_size_ln_dwellings_of_type_theta", 1.0875),
    "accN":            ("B_acc_nonwork", 0.5123),
    "accN_x_ageU35":   ("B_acc_nonwork_x_oldest_under35", 0.4388),
    "accN_x_age50_64": ("B_acc_nonwork_x_oldest_50_64", -0.3431),
    "accN_x_age65":    ("B_acc_nonwork_x_oldest_65plus", -0.1515),
    "accN_x_hhs":      ("B_acc_nonwork_x_hhsize_minus1", -0.1441),
    "commute_log":     ("B_commute_sum_ln1p_time", -1.3012),
    "lncost":          ("B_ln_zone_cost", -0.5048),
    "lncost_x_inc":    ("B_ln_zone_cost_x_lninc", 1.2163),
    "lncost_x_hhs":    ("B_ln_zone_cost_x_hhsize_minus1", -0.3643),
    "sim":             ("B_share_same_income_group", 1.7169),
    "lnddens":         ("B_ln_dwellings_per_acre", -0.3847),
    "lnddens_x_nocar": ("B_ln_dwellings_per_acre_x_nocar", 0.5085),
    "lnddens_x_child": ("B_ln_dwellings_per_acre_x_children", -0.0569),
    "lnretden":        ("B_ln1p_retail_jobs_per_km2", 0.0305),
}


# Weighting. The article's robust (sandwich) covariance for the weighted (WESML) likelihood is H^-1 (sum_n w_n^2 g_n g_n') H^-1,
# with H the Hessian of sum_n w_n ln P_n (input/code/mnl.py). Biogeme's 'weight' formula gives the same estimates but a BHHH matrix
# sum_n w_n g_n g_n' (weight counted once), hence different robust s.e. Writing the weight inside the log-likelihood
# (log_like = w_n ln P_n, no 'weight' formula) gives the same log-likelihood, the same estimates and exactly the article's robust s.e.
# Default: that form. Option --biogeme-weight: Biogeme's 'weight' formula instead.
def model(start=None):
    df = pd.read_parquet(DATA)
    df = df.drop(columns=[c for c in df.columns if df[c].dtype == object])   # identifiers and type labels (text)
    database = Database("residential_zone", df)
    B = {c: Beta(n, (start or {}).get(n, v), None, None, 0) for c, (n, v) in PARAMS.items()}
    V = {j: sum((B[c] * Variable(f"{c}_{j}") for c in PARAMS), 0) for j in range(J)}
    av = {j: Variable(f"av_{j}") for j in range(J)}
    ll = loglogit(V, av, Variable("choice"))
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
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "residential_zone_check"
        print(f"N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "residential_zone_structure_type"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
