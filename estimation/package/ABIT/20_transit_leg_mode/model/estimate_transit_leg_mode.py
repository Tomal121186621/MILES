#!/usr/bin/env python3
"""Model 20: mode of each leg (linked trip) of a transit tour (not in the article; coefficients used by the 2024 runs:
3_abit/coef_respec/tasha/tasha_transit_legs.csv, estimated by 3_abit/tasha_estimation/estimate_transit_legs.py).

Multinomial logit, alternatives 1 TR transit (reference, utility from its own terms only), 2 WK walk, 3 CP car passenger,
4 CD car driver, 5 BK bike.  Availability av_*: TR always (no path -> no_transit_path dummy), WK up to 8 km, BK up to 30 km, CP
always, CD only for a person with a licence, age 16+ and a household car (the estimation used only legs whose chosen mode is
available).  Variables: see input/data/estimation/data_dictionary.csv.  Unweighted; robust (sandwich) standard errors.

    ~/.venvs/biogeme/bin/python estimate_transit_leg_mode.py                    # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_transit_leg_mode.py --evaluate         # LL at the reference estimates, no estimation
        [--half estimation|holdout]                                              (nothing is written to ../output)
    option --outdir DIR: Biogeme output folder (default ../output)
"""
import argparse, os, tempfile
import pandas as pd
import biogeme.database as db
import biogeme.biogeme as bio
import biogeme.models as models
from biogeme.expressions import Beta, Variable

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "input", "data")
OUT = os.path.join(HERE, "..", "output")
NAME = "transit_leg_mode"
ALTS = ["TR", "WK", "CP", "CD", "BK"]

# (parameter, alternative, data column; None = alternative-specific constant)
TERMS = [
    ("ASC_walk", "WK", None),
    ("ASC_car_passenger", "CP", None),
    ("ASC_car_driver", "CD", None),
    ("ASC_bike", "BK", None),
    ("B_first_leg_walk", "WK", 'first'),
    ("B_first_leg_car_passenger", "CP", 'first'),
    ("B_first_leg_car_driver", "CD", 'first'),
    ("B_last_leg_walk", "WK", 'last'),
    ("B_last_leg_car_passenger", "CP", 'last'),
    ("B_leg_at_main_activity_walk", "WK", 'main'),
    ("B_leg_at_main_activity_car_passenger", "CP", 'main'),
    ("B_leg_at_main_activity_car_driver", "CD", 'main'),
    ("B_km_walk", "WK", 'km'),
    ("B_km_bike", "BK", 'km'),
    ("B_ln_1_plus_km_car_passenger", "CP", 'lnkm'),
    ("B_ln_1_plus_km_car_driver", "CD", 'lnkm'),
    ("B_transit_time_10min_transit", "TR", 'ttr'),
    ("B_no_transit_path_transit", "TR", 'nopath'),
    ("B_previous_leg_car_driver_car_driver", "CD", 'prevCD'),
    ("B_first_leg_car_driver_on_last_leg_car_driver", "CD", 'firstCD'),
    ("B_previous_leg_car_passenger_car_passenger", "CP", 'prevCP'),
    ("B_previous_leg_walk_walk", "WK", 'prevWK'),
    ("B_no_car_car_passenger", "CP", 'cars0'),
    ("B_fewer_cars_than_drivers_car_driver", "CD", 'carshort'),
    ("B_age_under_18_car_passenger", "CP", 'age_u18'),
    ("B_age_65_plus_car_passenger", "CP", 'age_65p'),
    ("B_driving_licence_car_passenger", "CP", 'lic'),
    ("B_work_tour_walk", "WK", 'work'),
    ("B_work_tour_car_passenger", "CP", 'work'),
    ("B_work_tour_car_driver", "CD", 'work'),
    ("B_school_tour_car_passenger", "CP", 'school'),
    ("B_peak_departure_car_passenger", "CP", 'peak'),
    ("B_peak_departure_walk", "WK", 'peak'),
    ("B_home_in_washington_region_walk", "WK", 'wash'),
    ("B_home_in_washington_region_car_driver", "CD", 'wash'),
]


def loglike():
    V = {i + 1: 0 for i in range(len(ALTS))}
    for p, a, v in TERMS:
        b = Beta(p, 0.0, None, None, 0); k = ALTS.index(a) + 1
        V[k] = V[k] + (b if v is None else b * Variable(v))
    AV = {i + 1: Variable(f"av_{a}") for i, a in enumerate(ALTS)}
    return models.loglogit(V, AV, Variable("y"))


def read(half):
    df = pd.read_parquet(os.path.join(DATA, "estimation" if half == "estimation" else "holdout", "estimation_table.parquet"))
    cols = sorted({v for _, _, v in TERMS if v} | {f"av_{a}" for a in ALTS} | {"y"})
    return df[cols].astype(float)


def reference():
    r = pd.read_csv(os.path.join(HERE, "reference_estimates.csv"))
    r = r[~r.parameter.isin(["LL0", "LL_beta", "LL_holdout", "N", "K"])].set_index("parameter")
    return r.coefficient.astype(float).to_dict()


def evaluate(half):
    df = read(half); cwd = os.getcwd(); os.chdir(tempfile.mkdtemp(prefix="bio_eval_"))
    try:
        m = bio.BIOGEME(db.Database(f"{NAME}_eval", df), loglike(), generate_html=False, generate_yaml=False, save_iterations=False)
        m.model_name = f"{NAME}_eval"; m.change_init_values(reference()); v = m.calculate_init_likelihood()
    finally:
        os.chdir(cwd)
    print(f"{half}: N {len(df)}  LL at the reference estimates = {v:.4f}")
    return v


def estimate(outdir):
    df = read("estimation"); os.makedirs(outdir, exist_ok=True); os.chdir(outdir)
    m = bio.BIOGEME(db.Database(NAME, df), loglike()); m.model_name = NAME
    r = m.estimate(); print(r.short_summary())
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))    # Biogeme 3.3.5 returns a dict of tables
    print(t.to_string())
    t.to_csv("estimated_parameters.csv", index=False)
    pd.DataFrame([dict(LL=float(r.final_loglikelihood), N=len(df), K=int(r.number_of_free_parameters))]).to_csv("estimated_fit.csv", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--evaluate", action="store_true")
    ap.add_argument("--half", default="estimation", choices=["estimation", "holdout"])
    ap.add_argument("--outdir", default=OUT, help="folder of the Biogeme output files (default ../output)")
    a = ap.parse_args()
    evaluate(a.half) if a.evaluate else estimate(os.path.abspath(a.outdir))
