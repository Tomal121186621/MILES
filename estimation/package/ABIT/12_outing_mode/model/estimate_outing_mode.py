#!/usr/bin/env python3
"""Model 12: outings from the usual workplace, mode (walk against the mode of the work tour) (article table est_subtour (tab:est_subtour_mode)).

Binary logit, y = 1: walk (0: the mode of the work tour); alternative 0 has utility 0.
    V1 = ASC + ln(1 + km workplace -> first stop) + work tour as car driver / car passenger + more than one stop + workplace zone >= 10,000 jobs/km2 + no car
    The fewer-cars-than-drivers term is not included: it is not significant (likelihood-ratio test p = 0.34) and BIC is lower without it.
Data: input/data/estimation/estimation_table.parquet (one row per observation, built by input/code/build_estimation_tables.py).
Estimated with Biogeme 3.3.5; coefficients used by MAST: 3_abit/tasha_estimation/results/tasha_subtour_1120i.csv (mode.*). Unweighted; robust (sandwich) standard errors are Biogeme's "Robust std err.".

    ~/.venvs/biogeme/bin/python estimate_outing_mode.py                    # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_outing_mode.py --evaluate         # LL at the reference estimates, no estimation
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
NAME = "outing_mode"

# data column -> parameter (descriptive names; reference_estimates.csv lists the article labels)
TERMS = {'const': 'ASC_walk',
 'lnkm': 'B_ln_distance_workplace_first_stop',
 'cbd_w': 'B_workplace_zone_10000_jobs_per_km2',
 'car0': 'B_no_car',
 'tm_cd': 'B_work_tour_car_driver',
 'tm_cp': 'B_work_tour_car_passenger',
 'multi': 'B_more_than_one_stop'}


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
