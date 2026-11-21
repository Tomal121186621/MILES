#!/usr/bin/env python3
"""Residential location, PUMA level: choice of the destination PUMA of moving households (ACS PUMS movers 2014-2018,
estimation sample), upper level of the two-level residential location model. Multinomial logit over the 97 PUMAs of the
zone-system area (no sampling; availability av_j). Observed outcome: the destination PUMA (exact in the PUMS).

    V_j = IV_j + sum_k beta_k x_kj
IV_j: inclusive value of the dwelling level (ln mean of exp(V_d) over 200 market dwellings of PUMA j, with the dwelling-level
estimates), a data column; its coefficient LAMBDA_dwelling is fixed at 1, so the two levels form one logit over the dwellings
of the area (in the specification search the free estimate, 1.43, was above the nested-logit bound).
Weight: expected in-area share of destination and origin (dest_cov x orig_cov) divided by its mean (column 'weight'), written
inside the log-likelihood (w ln P), which gives the WESML sandwich robust standard errors of the original estimator. The hold-out
table has weight 1 (the hold-out log-likelihood is unweighted). Start values = reference estimates (4 decimals).

    python estimate_residential_puma.py                 estimate; Biogeme writes its report to ../output
    python estimate_residential_puma.py --evaluate      log-likelihood at the start values only (nothing written); --check is the same
    python estimate_residential_puma.py --evaluate --holdout          same, on the hold-out sample (validation movers)
    python estimate_residential_puma.py --evaluate --start values.csv at other values (csv: parameter,value)
    --biogeme-weight    Biogeme's own 'weight' formula instead (same estimates, other robust s.e.)"""
import os, sys, tempfile
import pandas as pd
import biogeme.biogeme as bio
from biogeme.database import Database
from biogeme.expressions import Beta, Variable
from biogeme.models import loglogit
from biogeme.parameters import Parameters
from biogeme.results_processing import get_pandas_estimated_parameters

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = f"{HERE}/../input/data/estimation/puma_estimation.parquet"
HOLDOUT = f"{HERE}/../input/data/holdout/puma_holdout.parquet"
OUT = os.path.abspath(f"{HERE}/../output")
J = 97

# data column -> (parameter, reference estimate)
PARAMS = {
    "lnM":           ("B_ln_market_size", 0.8397),
    "d2":            ("B_cartime_20_60", -0.0339),
    "d3":            ("B_cartime_over60", -0.0087),
    "same":          ("B_previous_migration_area", 2.5267),
    "adjacent":      ("B_bordering_previous_area", 1.3297),
    "same_state":    ("B_same_state", 1.0820),
    "commute_log":   ("B_commute_sum_ln1p_time", -1.7408),
    "crime_x_child": ("B_crime_x_children", -1.1607),
    "lnddens":       ("B_ln_dwelling_density", -0.5466),
    "own_race":      ("B_own_race_share", 2.0759),
    "lnddens_x_single":  ("B_ln_density_x_single", 0.1698),
    "lnddens_x_young35": ("B_ln_density_x_oldest_under35", 0.2446),
    "lnddens_x_lninc":   ("B_ln_density_x_ln_income", -0.1153),
    "core_share":        ("B_core_city_share", 0.5055),
}


def model(start=None):
    df = pd.read_parquet(DATA)
    df = df.drop(columns=[c for c in df.columns if df[c].dtype == object or c in ("household", "weight_coverage")])
    database = Database("residential_puma", df)
    B = {c: Beta(n, (start or {}).get(n, v), None, None, 0) for c, (n, v) in PARAMS.items()}
    LAMBDA = Beta("LAMBDA_dwelling", 1.0, None, None, 1)            # inclusive value of the dwelling level, fixed at 1
    V = {j: LAMBDA * Variable(f"IV_{j}") + sum((B[c] * Variable(f"{c}_{j}") for c in PARAMS), 0) for j in range(J)}
    av = {j: Variable(f"av_{j}") for j in range(J)}
    ll = loglogit(V, av, Variable("choice"))
    if "--biogeme-weight" in sys.argv:
        return database, {"log_like": ll, "weight": Variable("weight")}
    return database, Variable("weight") * ll


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
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "residential_puma_check"
        print(f"{'hold-out' if DATA == HOLDOUT else 'estimation'} sample: N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "residential_puma"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
