#!/usr/bin/env python3
"""Car ownership of Maryland households (ACS PUMS 2014-2018, estimation sample): multinomial logit, 4 alternatives
(0, 1, 2, 3 or more cars), 0 cars = reference (utility 0). Every household variable has its own coefficient in each of the
alternatives 1, 2, 3+ (51 parameters). Unweighted. Start values = the article estimates (Table est_cars).

    python estimate_car_ownership.py            estimate; Biogeme writes its report to ../output
    python estimate_car_ownership.py --check    log-likelihood at the start values only (nothing written)
    python estimate_car_ownership.py --check --start values.csv   same, at other values (csv: parameter,value)"""
import os, sys, tempfile
import pandas as pd
import biogeme.biogeme as bio
from biogeme.database import Database
from biogeme.expressions import Beta, Variable
from biogeme.models import loglogit
from biogeme.parameters import Parameters
from biogeme.results_processing import get_pandas_estimated_parameters

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = f"{HERE}/../input/data/estimation/car_ownership_estimation.csv"
OUT = os.path.abspath(f"{HERE}/../output")

# variable of the data -> parameter stem; start values (article) for alternatives 1, 2, 3+ cars
START = {   #                       1 car     2 cars   3+ cars
    "ASC":                       (1.5342, 0.8291, -3.0365),
    "B_workers":                 (-0.5910, -0.1209, 1.0537),
    "B_nonworking_adults16":     (-0.7173, -0.4847, 0.3677),
    "B_children_under16":        (-0.1733, -0.2778, -0.4315),
    "B_single_person":           (-0.3179, -2.2801, -1.7009),
    "B_age_oldest":              (-0.0613, -0.1115, 0.0468),
    "B_age_oldest_sq":           (-0.0341, -0.0430, -0.1010),
    "B_lninc_under25k":          (0.5075, 0.4565, 0.1754),
    "B_lninc_25_50k":            (1.7727, 2.4088, 2.4995),
    "B_lninc_50_100k":           (0.4458, 1.4280, 1.5995),
    "B_lninc_above100k":         (-0.3512, 0.1358, 0.2591),
    "B_single_family_detached":  (0.3662, 0.9722, 1.6895),
    "B_multifamily":             (-0.2275, -0.6951, -1.1689),
    "B_bedrooms":                (0.3465, 0.4924, 0.6110),
    "B_ln_density_puma":         (-0.1135, -0.2619, -0.4176),
    "B_acc_gain_car":            (1.4236, 1.8495, 2.2972),
    "B_lninc_x_ln_density":      (0.0605, 0.0241, -0.0352),
}
COLUMN = {"B_workers": "workers", "B_nonworking_adults16": "nonworking_adults", "B_children_under16": "children",
          "B_single_person": "single_person", "B_age_oldest": "age10", "B_age_oldest_sq": "age10_sq", "B_lninc_under25k": "inc_lt25",
          "B_lninc_25_50k": "inc_25_50", "B_lninc_50_100k": "inc_50_100", "B_lninc_above100k": "inc_gt100",
          "B_single_family_detached": "sfd", "B_multifamily": "multifamily", "B_bedrooms": "bedrooms", "B_ln_density_puma": "ln_density",
          "B_acc_gain_car": "acc_gain", "B_lninc_x_ln_density": "inc_x_dens"}
ALTS = {1: "1car", 2: "2cars", 3: "3pluscars"}


def model(start=None):
    df = pd.read_csv(DATA, dtype={"serial": str}).drop(columns=["serial"])
    database = Database("car_ownership", df)
    V = {0: 0}
    for a, suf in ALTS.items():
        terms = []
        for stem, vals in START.items():
            name = f"{stem}_{suf}"; v0 = (start or {}).get(name, vals[a - 1])
            b = Beta(name, v0, None, None, 0)
            terms.append(b if stem == "ASC" else b * Variable(COLUMN[stem]))
        V[a] = sum(terms[1:], terms[0])
    av = {k: 1 for k in V}
    return database, loglogit(V, av, Variable("cars"))


def main():
    start = None
    if "--start" in sys.argv:
        s = pd.read_csv(sys.argv[sys.argv.index("--start") + 1]); start = dict(zip(s.parameter, s.value))
    database, ll = model(start)
    if "--check" in sys.argv:
        os.chdir(tempfile.mkdtemp())
        p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "car_ownership_check"
        print(f"N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "car_ownership"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
