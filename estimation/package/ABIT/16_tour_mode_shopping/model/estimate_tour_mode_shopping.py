#!/usr/bin/env python3
"""Model 16_tour_mode_shopping: tour mode choice, shopping tours (article table est_mc_shopping.tex, label tab:est_mc_shopping).

Multinomial logit.  Level of service: travel time (min) and cost ($) of the round trip on car driver, car passenger, bus and
train; round-trip km on walk and bike.  Household size is not on car passenger (dropped by BIC, rule H of m08).
Alternatives (choice code y): 1 car driver, 2 walk, 3 bike, 4 car passenger, 5 bus, 6 train.  Availability: columns av_<mode> of the estimation table (prep_tours / mc_common:
car driver needs a licence, a household car and age >= 16 and is blocked when the household's cars are in use by overlapping
car-driver tours of other members (TASHA car allocation, m10_car_availability.py); bus / train need a path in both halves;
walk <= 12 km and bike <= 50 km round trip).
Reference mode: car driver.  Licence is normalised to 0 on walk (car driver needs a licence, so a common shift of the licence
terms is not identified against the constants): walk has no licence term.  Unweighted.
Robust (sandwich) standard errors: Biogeme's 'Robust std err.'.

    ~/.venvs/biogeme/bin/python estimate_tour_mode_shopping.py                  # estimate (Biogeme output in ../output)
    ~/.venvs/biogeme/bin/python estimate_tour_mode_shopping.py --evaluate       # LL at the article estimates, no estimation, nothing written
        [--half estimation|holdout] [--at article|full]
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

# ------------------------------------------------------------------------------------------------ parameters
B_travel_time = Beta("B_travel_time", 0.0, None, None, 0)        # project: time
B_travel_cost = Beta("B_travel_cost", 0.0, None, None, 0)        # project: cost
B_paid_parking_share_CAR_DRIVER = Beta("B_paid_parking_share_CAR_DRIVER", 0.0, None, None, 0)        # project: park_CD
B_tour_with_stops_CAR_DRIVER = Beta("B_tour_with_stops_CAR_DRIVER", 0.0, None, None, 0)        # project: stops_CD
ASC_WALK = Beta("ASC_WALK", 0.0, None, None, 0)        # project: ASC_WK
B_age_WALK = Beta("B_age_WALK", 0.0, None, None, 0)        # project: age_WK
B_male_WALK = Beta("B_male_WALK", 0.0, None, None, 0)        # project: male_WK
B_household_size_WALK = Beta("B_household_size_WALK", 0.0, None, None, 0)        # project: hhsize_WK
B_cars_WALK = Beta("B_cars_WALK", 0.0, None, None, 0)        # project: autos_WK
B_member_under_18_WALK = Beta("B_member_under_18_WALK", 0.0, None, None, 0)        # project: kids_WK
B_joint_tour_WALK = Beta("B_joint_tour_WALK", 0.0, None, None, 0)        # project: joint_WK
B_round_trip_km_WALK = Beta("B_round_trip_km_WALK", 0.0, None, None, 0)        # project: km_WK
ASC_BIKE = Beta("ASC_BIKE", 0.0, None, None, 0)        # project: ASC_BK
B_age_BIKE = Beta("B_age_BIKE", 0.0, None, None, 0)        # project: age_BK
B_male_BIKE = Beta("B_male_BIKE", 0.0, None, None, 0)        # project: male_BK
B_licence_BIKE = Beta("B_licence_BIKE", 0.0, None, None, 0)        # project: lic_BK
B_household_size_BIKE = Beta("B_household_size_BIKE", 0.0, None, None, 0)        # project: hhsize_BK
B_cars_BIKE = Beta("B_cars_BIKE", 0.0, None, None, 0)        # project: autos_BK
B_member_under_18_BIKE = Beta("B_member_under_18_BIKE", 0.0, None, None, 0)        # project: kids_BK
B_joint_tour_BIKE = Beta("B_joint_tour_BIKE", 0.0, None, None, 0)        # project: joint_BK
B_round_trip_km_BIKE = Beta("B_round_trip_km_BIKE", 0.0, None, None, 0)        # project: km_BK
ASC_CAR_PASSENGER = Beta("ASC_CAR_PASSENGER", 0.0, None, None, 0)        # project: ASC_CP
B_age_CAR_PASSENGER = Beta("B_age_CAR_PASSENGER", 0.0, None, None, 0)        # project: age_CP
B_male_CAR_PASSENGER = Beta("B_male_CAR_PASSENGER", 0.0, None, None, 0)        # project: male_CP
B_licence_CAR_PASSENGER = Beta("B_licence_CAR_PASSENGER", 0.0, None, None, 0)        # project: lic_CP
B_cars_CAR_PASSENGER = Beta("B_cars_CAR_PASSENGER", 0.0, None, None, 0)        # project: autos_CP
B_member_under_18_CAR_PASSENGER = Beta("B_member_under_18_CAR_PASSENGER", 0.0, None, None, 0)        # project: kids_CP
B_joint_tour_CAR_PASSENGER = Beta("B_joint_tour_CAR_PASSENGER", 0.0, None, None, 0)        # project: joint_CP
ASC_BUS = Beta("ASC_BUS", 0.0, None, None, 0)        # project: ASC_BUS
B_age_BUS = Beta("B_age_BUS", 0.0, None, None, 0)        # project: age_BUS
B_male_BUS = Beta("B_male_BUS", 0.0, None, None, 0)        # project: male_BUS
B_licence_BUS = Beta("B_licence_BUS", 0.0, None, None, 0)        # project: lic_BUS
B_household_size_BUS = Beta("B_household_size_BUS", 0.0, None, None, 0)        # project: hhsize_BUS
B_cars_BUS = Beta("B_cars_BUS", 0.0, None, None, 0)        # project: autos_BUS
B_member_under_18_BUS = Beta("B_member_under_18_BUS", 0.0, None, None, 0)        # project: kids_BUS
B_joint_tour_BUS = Beta("B_joint_tour_BUS", 0.0, None, None, 0)        # project: joint_BUS
ASC_TRAIN = Beta("ASC_TRAIN", 0.0, None, None, 0)        # project: ASC_TRAIN
B_age_TRAIN = Beta("B_age_TRAIN", 0.0, None, None, 0)        # project: age_TRAIN
B_male_TRAIN = Beta("B_male_TRAIN", 0.0, None, None, 0)        # project: male_TRAIN
B_licence_TRAIN = Beta("B_licence_TRAIN", 0.0, None, None, 0)        # project: lic_TRAIN
B_household_size_TRAIN = Beta("B_household_size_TRAIN", 0.0, None, None, 0)        # project: hhsize_TRAIN
B_cars_TRAIN = Beta("B_cars_TRAIN", 0.0, None, None, 0)        # project: autos_TRAIN
B_member_under_18_TRAIN = Beta("B_member_under_18_TRAIN", 0.0, None, None, 0)        # project: kids_TRAIN
B_joint_tour_TRAIN = Beta("B_joint_tour_TRAIN", 0.0, None, None, 0)        # project: joint_TRAIN

# ------------------------------------------------------------------------------------------------ utilities
V_CAR_DRIVER = B_travel_time * Variable("t_CD") + B_travel_cost * Variable("c_CD") + B_paid_parking_share_CAR_DRIVER * Variable("park") + B_tour_with_stops_CAR_DRIVER * Variable("stops")        # reference mode: no constant
V_WALK = ASC_WALK + B_age_WALK * Variable("age") + B_male_WALK * Variable("male") + B_household_size_WALK * Variable("hhsize") + B_cars_WALK * Variable("autos") + B_member_under_18_WALK * Variable("kids") + B_joint_tour_WALK * Variable("joint") + B_round_trip_km_WALK * Variable("km")
V_BIKE = ASC_BIKE + B_age_BIKE * Variable("age") + B_male_BIKE * Variable("male") + B_licence_BIKE * Variable("lic") + B_household_size_BIKE * Variable("hhsize") + B_cars_BIKE * Variable("autos") + B_member_under_18_BIKE * Variable("kids") + B_joint_tour_BIKE * Variable("joint") + B_round_trip_km_BIKE * Variable("km")
V_CAR_PASSENGER = B_travel_time * Variable("t_CP") + B_travel_cost * Variable("c_CP") + ASC_CAR_PASSENGER + B_age_CAR_PASSENGER * Variable("age") + B_male_CAR_PASSENGER * Variable("male") + B_licence_CAR_PASSENGER * Variable("lic") + B_cars_CAR_PASSENGER * Variable("autos") + B_member_under_18_CAR_PASSENGER * Variable("kids") + B_joint_tour_CAR_PASSENGER * Variable("joint")
V_BUS = B_travel_time * Variable("t_BUS") + B_travel_cost * Variable("c_BUS") + ASC_BUS + B_age_BUS * Variable("age") + B_male_BUS * Variable("male") + B_licence_BUS * Variable("lic") + B_household_size_BUS * Variable("hhsize") + B_cars_BUS * Variable("autos") + B_member_under_18_BUS * Variable("kids") + B_joint_tour_BUS * Variable("joint")
V_TRAIN = B_travel_time * Variable("t_TRAIN") + B_travel_cost * Variable("c_TRAIN") + ASC_TRAIN + B_age_TRAIN * Variable("age") + B_male_TRAIN * Variable("male") + B_licence_TRAIN * Variable("lic") + B_household_size_TRAIN * Variable("hhsize") + B_cars_TRAIN * Variable("autos") + B_member_under_18_TRAIN * Variable("kids") + B_joint_tour_TRAIN * Variable("joint")

U = {1: V_CAR_DRIVER, 2: V_WALK, 3: V_BIKE, 4: V_CAR_PASSENGER, 5: V_BUS, 6: V_TRAIN}
AV = {1: Variable("av_CD"), 2: Variable("av_WK"), 3: Variable("av_BK"), 4: Variable("av_CP"), 5: Variable("av_BUS"), 6: Variable("av_TRAIN")}
LOGLIKE = models.loglogit(U, AV, Variable("y"))


def read(half):
    df = pd.read_parquet(os.path.join(DATA, "estimation" if half == "estimation" else "holdout", "tours.parquet"))
    return df.drop(columns=["choice"])


def formulas():
    return LOGLIKE


def reference(at):
    r = pd.read_csv(os.path.join(HERE, "reference_estimates.csv"))
    r = r[~r.parameter.isin(["LL0", "LL_beta", "N", "K", "LL_holdout"])].set_index("parameter")
    return (r.article_coefficient if at == "article" else r.coefficient).astype(float).to_dict()


def evaluate(half, at):
    df = read(half); cwd = os.getcwd(); os.chdir(tempfile.mkdtemp(prefix="bio_eval_"))
    try:
        m = bio.BIOGEME(db.Database("eval", df), formulas(), generate_html=False, generate_yaml=False, save_iterations=False)
        m.model_name = "eval"; m.change_init_values(reference(at))
        v = m.calculate_init_likelihood()
    finally:
        os.chdir(cwd)
    print(f"{half}: N {len(df)}  LL at the {at} estimates = {v:.4f}")
    return v


def estimate(outdir):
    df = read("estimation"); os.makedirs(outdir, exist_ok=True); os.chdir(outdir)
    m = bio.BIOGEME(db.Database("tour_mode_shopping", df), formulas())
    m.model_name = "tour_mode_shopping"
    r = m.estimate()
    print(r.short_summary())
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))          # Biogeme 3.3.5 returns {table name: DataFrame}
    print(t.to_string())
    t.to_csv("estimated_parameters.csv", index=False)
    pd.DataFrame([dict(LL=float(r.final_loglikelihood), N=len(df), K=int(r.number_of_free_parameters))]).to_csv("estimated_fit.csv", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--evaluate", action="store_true")
    ap.add_argument("--half", default="estimation", choices=["estimation", "holdout"]); ap.add_argument("--at", default="article", choices=["article", "full"])
    ap.add_argument("--outdir", default=OUT, help="folder of the Biogeme output files (default ../output)")
    a = ap.parse_args()
    evaluate(a.half, a.at) if a.evaluate else estimate(os.path.abspath(a.outdir))
