#!/usr/bin/env python3
"""Model 19_tour_mode_joint_other: tour mode choice, joint recreation and other tours (article table est_mc_joint.tex, label tab:est_mc_other_joint).

Joint household recreation and other tours: one observation per joint household group (m11_joint_group.groups).
Nested logit as the individual other model (auto nest {car driver, car passenger}, transit nest {bus, train},
mu >= 1).  Alternatives chosen by fewer than 20 groups keep only their constant and level-of-service terms.
Alternatives (choice code y): 1 car driver, 2 walk, 3 bike, 4 car passenger, 5 bus, 6 train.  Availability: columns av_<mode> of the estimation table (prep_tours / mc_common:
car driver needs a licence, a household car and age >= 16 and is blocked when the household's cars are in use by overlapping
car-driver tours of other members (TASHA car allocation, m10_car_availability.py); bus / train need a path in both halves;
walk <= 12 km and bike <= 50 km round trip).
Reference mode: car driver.  Licence is normalised to 0 on walk (car driver needs a licence, so a common shift of the licence
terms is not identified against the constants): walk has no licence term.  Unweighted.
Robust (sandwich) standard errors: Biogeme's 'Robust std err.'.

    ~/.venvs/biogeme/bin/python estimate_tour_mode_joint_other.py                  # estimate (Biogeme output in ../output)
    ~/.venvs/biogeme/bin/python estimate_tour_mode_joint_other.py --evaluate       # LL at the article estimates, no estimation, nothing written
        [--half estimation|holdout] [--at article|full]
    option --outdir DIR: Biogeme output folder (default ../output)
"""
import argparse, os, tempfile
import pandas as pd
import biogeme.database as db
import biogeme.biogeme as bio
import biogeme.models as models
from biogeme.expressions import Beta, Variable
from biogeme.nests import OneNestForNestedLogit, NestsForNestedLogit
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
B_recreation_tour_WALK = Beta("B_recreation_tour_WALK", 0.0, None, None, 0)        # project: rec_WK
B_round_trip_km_WALK = Beta("B_round_trip_km_WALK", 0.0, None, None, 0)        # project: km_WK
ASC_BIKE = Beta("ASC_BIKE", 0.0, None, None, 0)        # project: ASC_BK
B_round_trip_km_BIKE = Beta("B_round_trip_km_BIKE", 0.0, None, None, 0)        # project: km_BK
ASC_CAR_PASSENGER = Beta("ASC_CAR_PASSENGER", 0.0, None, None, 0)        # project: ASC_CP
B_age_CAR_PASSENGER = Beta("B_age_CAR_PASSENGER", 0.0, None, None, 0)        # project: age_CP
B_male_CAR_PASSENGER = Beta("B_male_CAR_PASSENGER", 0.0, None, None, 0)        # project: male_CP
B_licence_CAR_PASSENGER = Beta("B_licence_CAR_PASSENGER", 0.0, None, None, 0)        # project: lic_CP
B_household_size_CAR_PASSENGER = Beta("B_household_size_CAR_PASSENGER", 0.0, None, None, 0)        # project: hhsize_CP
B_cars_CAR_PASSENGER = Beta("B_cars_CAR_PASSENGER", 0.0, None, None, 0)        # project: autos_CP
B_member_under_18_CAR_PASSENGER = Beta("B_member_under_18_CAR_PASSENGER", 0.0, None, None, 0)        # project: kids_CP
B_recreation_tour_CAR_PASSENGER = Beta("B_recreation_tour_CAR_PASSENGER", 0.0, None, None, 0)        # project: rec_CP
ASC_BUS = Beta("ASC_BUS", 0.0, None, None, 0)        # project: ASC_BUS
ASC_TRAIN = Beta("ASC_TRAIN", 0.0, None, None, 0)        # project: ASC_TRAIN
MU_auto_nest = Beta("MU_auto_nest", 1.2, 1.0, 10.0, 0)        # project: mu_auto; mu >= 1 (Biogeme lognested)
MU_transit_nest = Beta("MU_transit_nest", 1.2, 1.0, 10.0, 0)        # project: mu_transit; mu >= 1 (Biogeme lognested)

# ------------------------------------------------------------------------------------------------ utilities
V_CAR_DRIVER = B_travel_time * Variable("t_CD") + B_travel_cost * Variable("c_CD") + B_paid_parking_share_CAR_DRIVER * Variable("park") + B_tour_with_stops_CAR_DRIVER * Variable("stops")        # reference mode: no constant
V_WALK = ASC_WALK + B_age_WALK * Variable("age") + B_male_WALK * Variable("male") + B_household_size_WALK * Variable("hhsize") + B_cars_WALK * Variable("autos") + B_member_under_18_WALK * Variable("kids") + B_recreation_tour_WALK * Variable("rec") + B_round_trip_km_WALK * Variable("km")
V_BIKE = ASC_BIKE + B_round_trip_km_BIKE * Variable("km")
V_CAR_PASSENGER = B_travel_time * Variable("t_CP") + B_travel_cost * Variable("c_CP") + ASC_CAR_PASSENGER + B_age_CAR_PASSENGER * Variable("age") + B_male_CAR_PASSENGER * Variable("male") + B_licence_CAR_PASSENGER * Variable("lic") + B_household_size_CAR_PASSENGER * Variable("hhsize") + B_cars_CAR_PASSENGER * Variable("autos") + B_member_under_18_CAR_PASSENGER * Variable("kids") + B_recreation_tour_CAR_PASSENGER * Variable("rec")
V_BUS = B_travel_time * Variable("t_BUS") + B_travel_cost * Variable("c_BUS") + ASC_BUS
V_TRAIN = B_travel_time * Variable("t_TRAIN") + B_travel_cost * Variable("c_TRAIN") + ASC_TRAIN

U = {1: V_CAR_DRIVER, 2: V_WALK, 3: V_BIKE, 4: V_CAR_PASSENGER, 5: V_BUS, 6: V_TRAIN}
AV = {1: Variable("av_CD"), 2: Variable("av_WK"), 3: Variable("av_BK"), 4: Variable("av_CP"), 5: Variable("av_BUS"), 6: Variable("av_TRAIN")}
NESTS = NestsForNestedLogit(choice_set=list(U), tuple_of_nests=(
    OneNestForNestedLogit(MU_auto_nest, [1, 4], name="auto"),
    OneNestForNestedLogit(MU_transit_nest, [5, 6], name="transit")))
LOGLIKE = models.lognested(U, AV, NESTS, Variable("y"))      # walk and bike: alone in their nests (mu = 1)


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
    m = bio.BIOGEME(db.Database("tour_mode_joint_other", df), formulas())
    m.model_name = "tour_mode_joint_other"
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
