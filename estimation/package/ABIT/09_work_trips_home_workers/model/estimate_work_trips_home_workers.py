#!/usr/bin/env python3
"""Model 09: location of the work trips of workers whose usual workplace is home (article table est_loc_wahb).

Multinomial logit over the full choice set of 1,588 zones, anchor = home, with the tract-to-zone measurement model of the
destination (the survey records the destination census tract; the model zones overlapping it are the possible chosen zones,
weights b_k = overlap area / zone area):

    L_n  = sum_c w_c * [ sum_k b_k exp(V_c,z_k) ] / [ sum_j exp(V_c,j) ]          (one anchor configuration, w_0 = 1)
    LL   = sum_n ln L_n
    V_j  = MU_size ln(1 + office_jobs_j + exp(THETA_population) population_j)
           + B_distance d_hj + B_ln_distance ln d_hj + B_intrazonal [j = h] + B_outside_home_county [county_j != county_h]

d = car distance (km) of the 2016 car skim from the home zone h, intrazonal 0.5 sqrt(zone area).  Bounds as in the
estimation: THETA in [-30, 15], MU_size in [0, 3].  Unweighted, robust (sandwich) standard errors.

    ~/.venvs/biogeme/bin/python estimate_work_trips_home_workers.py                 # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_work_trips_home_workers.py --evaluate      # LL at the article estimates, no estimation
        [--half estimation|holdout] [--at article|full]                               (nothing is written to ../output)
    option --outdir DIR: Biogeme output folder (default ../output)
"""
import argparse, glob, json, os, sys, tempfile, time
import numpy as np, pandas as pd
import biogeme.database as db
import biogeme.biogeme as bio
from biogeme.expressions import Beta, Variable, exp, log, MultipleSum

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "input", "data")
OUT = os.path.join(HERE, "..", "output")
ZONES = pd.read_csv(os.path.join(HERE, "..", "..", "00_shared_data", "zones", "zones_model_attributes.csv")).sort_values("idx")
NZ = len(ZONES)
ZA = {a: ZONES[a].astype(float).tolist() for a in ["bc", "dcz", "cbd", "va", "othst", "lnretden", "mix", "pop", "ret", "off", "oth", "stu"]}
ZA["cnty"] = ZONES.countyfips.astype(float).tolist(); ZA["st"] = ZONES.state.astype(float).tolist()

# ------------------------------------------------------------------------------------------------ parameters (article names)
B_distance = Beta("B_distance_km", 0.0, None, None, 0)
B_ln_distance = Beta("B_ln_distance", 0.0, None, None, 0)
B_intrazonal = Beta("B_intrazonal", 0.0, None, None, 0)
B_outside_home_county = Beta("B_outside_home_county", 0.0, None, None, 0)
THETA_population = Beta("THETA_population", -2.0, -30.0, 15.0, 0)      # size base: office jobs (theta = 0)
MU_size = Beta("MU_size", 0.8, 0.0, 3.0, 0)


class At:
    """the variables of zone j (alternative of the denominator) or of candidate k (numerator) under configuration c"""
    def __init__(self, c, j=None, k=None):
        self.c, self.j, self.k = c, j, k

    def z(self, a):                     # zone attribute: a constant for zone j, a data column for candidate k
        return ZA[a][self.j] if self.k is None else Variable(f"cand_{a}_{self.k}")

    def x(self, var):                   # record x zone variable of configuration c
        return Variable(f"{var}_{self.c}_{self.j}") if self.k is None else Variable(f"c{var}_{self.c}_{self.k}")

    def zone(self):
        return self.j if self.k is None else Variable(f"cz_{self.k}")


def term(beta, x):
    """beta * x, left out when x is the constant 0 (exact)"""
    return None if (isinstance(x, float) and x == 0.0) else beta * x


def utility(g):
    c = g.c; d = g.x("imp")
    size = g.z("off")
    pop = g.z("pop")
    size = size + (exp(THETA_population) * pop if not (isinstance(pop, float) and pop == 0.0) else 0.0)
    if isinstance(size, float): size_term = MU_size * float(np.log1p(size))
    else: size_term = MU_size * log(1 + size)
    terms = [size_term, B_distance * d, B_ln_distance * log(d),
             B_intrazonal * (Variable(f"za_{c}") == g.zone()),
             B_outside_home_county * (Variable(f"cnty_a_{c}") != g.z("cnty"))]
    return MultipleSum([t for t in terms if t is not None])


def loglike(n_cfg, n_cand):
    L = []
    for c in range(n_cfg):
        den = MultipleSum([exp(utility(At(c, j=j))) for j in range(NZ)])
        num = MultipleSum([Variable(f"b_{k}") * exp(utility(At(c, k=k))) for k in range(n_cand)]) if n_cand > 1 else Variable("b_0") * exp(utility(At(c, k=0)))
        L.append(Variable(f"w_{c}") * num / den)
    return log(MultipleSum(L) if len(L) > 1 else L[0])


def read(half):
    folder = os.path.join(DATA, "estimation" if half == "estimation" else "holdout")
    meta = json.load(open(os.path.join(folder, "biogeme_meta.json")))
    df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(folder, "biogeme_part*.parquet")))], ignore_index=True)
    return df.astype("float64"), meta


def reference(at):
    r = pd.read_csv(os.path.join(HERE, "reference_estimates.csv"))
    r = r[~r.parameter.isin(["LL0", "LL_beta", "N", "K"])].set_index("parameter")
    return (r.article_coefficient if at == "article" else r.coefficient).astype(float).to_dict()


def evaluate(half, at):
    """LL at the reference values without estimating (eager evaluation, use_jit=False: small memory); rows grouped by their
    number of configurations so that each group uses the expression with exactly that many."""
    df, meta = read(half); vals = reference(at); tot = 0.0; t0 = time.time()
    cwd = os.getcwd(); tmp = tempfile.mkdtemp(prefix="bio_eval_")
    os.chdir(tmp)
    try:
        for g, part in df.groupby("n_cfg"):
            ll = loglike(int(g), meta["n_cand_max"])
            m = bio.BIOGEME(db.Database(f"eval{g}", part.reset_index(drop=True)), ll, use_jit=False, generate_html=False,
                            generate_yaml=False, save_iterations=False)
            m.model_name = f"eval_{g}"; m.change_init_values(vals)
            v = m.calculate_init_likelihood(); tot += v
            print(f"  configurations {g}: N {len(part)} LL {v:.4f} ({time.time() - t0:.0f} s)", flush=True)
    finally:
        os.chdir(cwd)
    print(f"{half}: N {len(df)}  LL at the {at} estimates = {tot:.4f}", flush=True)
    return tot


def estimate(outdir=OUT):
    df, meta = read("estimation")
    os.makedirs(outdir, exist_ok=True); os.chdir(outdir)
    m = bio.BIOGEME(db.Database("work_trips_home_workers", df), loglike(meta["n_cfg_max"], meta["n_cand_max"]))
    m.model_name = "work_trips_home_workers"
    r = m.estimate()
    print(r.short_summary())
    from biogeme.results_processing import get_pandas_estimated_parameters
    t = get_pandas_estimated_parameters(estimation_results=r)
    if isinstance(t, dict): t = next(iter(t.values()))
    print(t.to_string())
    t.to_csv("estimated_parameters.csv", index=False)
    pd.DataFrame([dict(LL=float(r.final_loglikelihood), N=len(df), K=int(r.number_of_free_parameters))]).to_csv("estimated_fit.csv", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--evaluate", action="store_true")
    ap.add_argument("--half", default="estimation", choices=["estimation", "holdout"]); ap.add_argument("--at", default="article", choices=["article", "full"])
    ap.add_argument("--outdir", default=OUT, help="folder of the Biogeme output files (default ../output)")
    a = ap.parse_args()
    evaluate(a.half, a.at) if a.evaluate else estimate(os.path.abspath(a.outdir))
