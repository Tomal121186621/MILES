#!/usr/bin/env python3
"""Model 13: return home between two consecutive out-of-home episodes (article table est_return).

Binary logit, y = 1: return home between the two episodes; alternative 0 has utility 0.
    V1 = ASC + detour via home (km, ln(1 + km)) + distance from home + person type, female, licence + household size, children, cars, income + purposes of the preceding / following episode + joint terms + number of out-of-home episodes + end-time bands
Data: input/data/estimation/estimation_table.parquet (one row per observation, built by input/code/build_estimation_tables.py).
The project estimated this model with statsmodels Logit (HC0 robust covariance), the same likelihood and the same sandwich estimator. Unweighted; robust (sandwich) standard errors are Biogeme's "Robust std err.".

    ~/.venvs/biogeme/bin/python estimate_return_home.py                    # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_return_home.py --evaluate         # LL at the reference estimates, no estimation
        [--half estimation|holdout] [--at article|full]                  (nothing is written to ../output)
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
NAME = "return_home"

# data column -> parameter (descriptive names; reference_estimates.csv lists the article labels)
TERMS = {'const': 'ASC_return_home',
 'detour_km': 'B_detour_via_home_km',
 'lndetour': 'B_ln_detour_via_home',
 'dhome_km': 'B_distance_from_home_km',
 'worker': 'B_worker',
 'stud_k12': 'B_student_k12',
 'stud_ps': 'B_student_postsecondary',
 'retiree': 'B_retiree',
 'toddler': 'B_child_under_5',
 'female': 'B_female',
 'lic': 'B_driving_licence',
 'hhsize': 'B_household_size',
 'kids': 'B_child_under_16_in_household',
 'car0': 'B_no_car',
 'carshort': 'B_fewer_cars_than_drivers',
 'inc_low': 'B_income_below_50k',
 'inc_high': 'B_income_100k_or_more',
 'a_work': 'B_preceding_work',
 'a_school': 'B_preceding_school',
 'a_acc': 'B_preceding_accompanying',
 'a_shop': 'B_preceding_shopping',
 'a_joint': 'B_preceding_joint',
 'e_work': 'B_following_work',
 'e_school': 'B_following_school',
 'e_acc': 'B_following_accompanying',
 'e_shop': 'B_following_shopping',
 'e_joint': 'B_following_joint',
 'jj': 'B_both_episodes_joint',
 'jmand': 'B_joint_next_to_work_or_school',
 'nep': 'B_number_of_out_of_home_episodes',
 'am': 'B_end_before_9',
 'pm': 'B_end_15_19',
 'ev': 'B_end_after_19'}


def loglike():
    V1 = sum((Beta(p, 0.0, None, None, 0) * (1.0 if c == "const" else Variable(c)) for c, p in TERMS.items()), start=0)
    return models.loglogit({1: V1, 0: 0}, {1: 1, 0: 1}, Variable("y"))


def read(half):
    df = pd.read_parquet(os.path.join(DATA, "estimation" if half == "estimation" else "holdout", "estimation_table.parquet"))
    cols = [c for c in TERMS if c != "const"] + ["y"]
    return df[cols].astype(float)


def reference(at):
    r = pd.read_csv(os.path.join(HERE, "reference_estimates.csv"))
    r = r[~r.parameter.isin(["LL0", "LL_beta", "N", "K"])].set_index("parameter")
    return (r.article_coefficient if at == "article" else r.coefficient).astype(float).to_dict()


def evaluate(half, at):
    df = read(half); cwd = os.getcwd(); os.chdir(tempfile.mkdtemp(prefix="bio_eval_"))
    try:
        m = bio.BIOGEME(db.Database(f"{NAME}_eval", df), loglike(), generate_html=False, generate_yaml=False, save_iterations=False)
        m.model_name = f"{NAME}_eval"; m.change_init_values(reference(at)); v = m.calculate_init_likelihood()
    finally:
        os.chdir(cwd)
    print(f"{half}: N {len(df)}  LL at the {at} estimates = {v:.4f}")
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
    ap.add_argument("--half", default="estimation", choices=["estimation", "holdout"]); ap.add_argument("--at", default="article", choices=["article", "full"])
    ap.add_argument("--outdir", default=OUT, help="folder of the Biogeme output files (default ../output)")
    a = ap.parse_args()
    evaluate(a.half, a.at) if a.evaluate else estimate(os.path.abspath(a.outdir))
