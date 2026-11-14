#!/usr/bin/env python3
"""Model 11: outings from the usual workplace, generation (article table est_subtour (tab:est_subtour_gen)).

Binary logit, y = 1: at least one outing during the work episode; alternative 0 has utility 0.
    V1 = ASC + work duration 0-4 h and 4-7 h (h; above 7 h: 0) + secondary work episode + arrival before 7:00 / from 10:00 + workplace zone >= 10,000 jobs/km2 + ln(1 + home-workplace km)
Data: input/data/estimation/estimation_table.parquet (one row per observation, built by input/code/build_estimation_tables.py).
The project estimated it with Biogeme 3.3.5 (estimate_subtours.biogeme_logit). Unweighted; robust (sandwich) standard errors are Biogeme's "Robust std err.".

    ~/.venvs/biogeme/bin/python estimate_outing_generation.py                    # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_outing_generation.py --evaluate         # LL at the reference estimates, no estimation
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
NAME = "outing_generation"

# data column -> parameter (descriptive names; reference_estimates.csv lists the article labels)
TERMS = {'const': 'ASC_outing',
 'lncomm': 'B_ln_home_workplace_distance',
 'cbd_w': 'B_workplace_zone_10000_jobs_per_km2',
 'sp_0_4': 'B_work_duration_0_4h',
 'sp_4_7': 'B_work_duration_4_7h',
 'sw': 'B_secondary_work_episode',
 'arr_early': 'B_arrival_before_7',
 'arr_late': 'B_arrival_from_10'}


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
