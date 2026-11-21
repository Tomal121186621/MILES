#!/usr/bin/env python3
"""Car ownership of Maryland households (ACS PUMS 2014-2018, estimation sample): multinomial logit, 4 alternatives
(0, 1, 2, 3 or more cars), 0 cars = reference (utility 0). Every household variable has its own coefficient in each of the
alternatives 1, 2, 3+; four of them are fixed at 0 (single person for 2 and 3+ cars, density for 1 car, age for 3+ cars):
56 parameters. Persons aged 16+ enter as dummies for 2, 3 and 4+ (reference 0-1); Baltimore City (PUMA 2400801-2400805)
has its own term, estimated with the others. Unweighted. Start values = the article estimates (Table est_cars).

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

# variable of the data -> parameter stem; start values (article) for alternatives 1, 2, 3+ cars; None = fixed at 0 (not in the model)
START = {   #                       1 car     2 cars   3+ cars
    "ASC":                        (1.2652, -1.2532, -3.6183),
    "B_workers":                  (0.1062, 0.3319, 0.6294),
    "B_persons16_2":              (-0.6235, 2.0214, 2.1165),
    "B_persons16_3":              (-1.3456, 1.0266, 2.6169),
    "B_persons16_4plus":          (-1.6925, 0.3075, 2.3784),
    "B_children_under16":         (-0.2038, -0.1821, -0.3410),
    "B_single_person":            (-0.2501, None, None),
    "B_age_oldest":               (-0.0656, -0.1364, None),
    "B_age_oldest_sq":            (-0.0347, -0.0459, -0.0958),
    "B_lninc_under25k":           (0.5127, 0.3837, 0.1625),
    "B_lninc_25_50k":             (1.4038, 1.9106, 2.0388),
    "B_lninc_50_100k":            (0.3798, 1.2820, 1.4880),
    "B_lninc_above100k":          (-0.2813, 0.1458, 0.2811),
    "B_single_family_detached":   (0.2074, 0.7446, 1.4866),
    "B_multifamily":              (-0.3958, -0.9090, -1.3346),
    "B_bedrooms":                 (0.3471, 0.5272, 0.6396),
    "B_ln_density_puma":          (None, -0.1391, -0.3054),
    "B_acc_gain_car":             (0.4632, 0.6501, 1.1430),
    "B_lninc_x_ln_density":       (0.0616, 0.0285, -0.0299),
    "B_baltimore_city":           (-0.9227, -1.1812, -1.0775),
}
COLUMN = {"B_workers": "workers", "B_persons16_2": "p16_2", "B_persons16_3": "p16_3", "B_persons16_4plus": "p16_4p",
          "B_children_under16": "children", "B_single_person": "single_person", "B_age_oldest": "age10", "B_age_oldest_sq": "age10_sq",
          "B_lninc_under25k": "inc_lt25", "B_lninc_25_50k": "inc_25_50", "B_lninc_50_100k": "inc_50_100", "B_lninc_above100k": "inc_gt100",
          "B_single_family_detached": "sfd", "B_multifamily": "multifamily", "B_bedrooms": "bedrooms", "B_ln_density_puma": "ln_density",
          "B_acc_gain_car": "acc_gain", "B_lninc_x_ln_density": "inc_x_dens", "B_baltimore_city": "city"}
ALTS = {1: "1car", 2: "2cars", 3: "3pluscars"}


def model(start=None):
    df = pd.read_csv(DATA, dtype={"serial": str}).drop(columns=["serial"])
    database = Database("car_ownership", df)
    V = {0: 0}
    for a, suf in ALTS.items():
        terms = []
        for stem, vals in START.items():
            if vals[a - 1] is None:
                continue            # fixed at 0
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
