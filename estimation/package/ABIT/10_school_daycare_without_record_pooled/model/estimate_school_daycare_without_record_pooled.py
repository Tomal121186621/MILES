#!/usr/bin/env python3
"""Model 10: location of school episodes of persons without a school record (purpose N, scale 1) and of daycare / pre-school
episodes of children under 5 (purpose D), pooled with a purpose-specific scale (article table est_loc_edu).

Multinomial logit over the full choice set of 1,588 zones, anchor = home h, tract-to-zone measurement model of the destination
(candidate zones z_k, weights b_k).  For a record of purpose p:

    L_n = sum_c w_c [ sum_k b_k exp(U_c,z_k) ] / [ sum_j exp(U_c,j) ]      (one configuration, w_0 = 1);  LL = sum_n ln L_n
    U_pj = mu_p (B_ln_distance ln d_hj + B_car_generalised_time cgt_hj + B_retail_density lnretden_j + B_land_use_mix mix_j
                 + B_outside_home_county [county_j != county_h] + B_outside_home_state [state_j != state_h])
           + 1 x ln(1 + S_pj)
    S_Nj = school_pupils_j + exp(THETA_N_population) population_j + exp(THETA_N_office) office_jobs_j
    S_Dj = retail_j + exp(THETA_D_school) school_pupils_j + exp(THETA_D_population) population_j
    mu_N = 1 (normalised), mu_D = SCALE_daycare.

The six linear coefficients are shared by the two purposes.  The size coefficient is held at its bound 1 for both purposes; as in
the project estimator (pool_core.ParEngine, dc_model.Spec mu_fixed), a size coefficient held at a value is a constant and is NOT
multiplied by the purpose scale, so the size term enters U_D as 1 x ln(1 + S_Dj).  Size weights (theta) are never scaled.
Bounds: THETA in [-30, 15], SCALE_daycare in [0.01, 50].  The interaction terms that the pooling held at 0 (ln distance x cars,
age, children, worker, time of day: pool_core Structure.fixed) are left out.  Unweighted, robust (sandwich) standard errors.

    ~/.venvs/biogeme/bin/python estimate_school_daycare_without_record_pooled.py                 # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_school_daycare_without_record_pooled.py --evaluate      # LL at the article estimates, no estimation
        [--half estimation|holdout] [--at article|full]       (nothing is written to ../output)
    option --outdir DIR: Biogeme output folder (default ../output)
"""
import argparse, glob, json, os, sys, tempfile, time
import numpy as np, pandas as pd
import biogeme.database as db
import biogeme.biogeme as bio
from biogeme.expressions import Beta, Variable, exp, log, MultipleSum, BinaryMin, BinaryMax

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "input", "data")
OUT = os.path.join(HERE, "..", "output")
ZONES = pd.read_csv(os.path.join(HERE, "..", "..", "00_shared_data", "zones", "zones_model_attributes.csv")).sort_values("idx")
NZ = len(ZONES)
ZA = {a: ZONES[a].astype(float).tolist() for a in ["bc", "dcz", "cbd", "va", "othst", "lnretden", "mix", "pop", "ret", "off", "oth", "stu"]}
ZA["cnty"] = ZONES.countyfips.astype(float).tolist(); ZA["st"] = ZONES.state.astype(float).tolist()


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


def zero(x):
    return isinstance(x, float) and x == 0.0


def times(beta, x):
    """beta * x, left out when x is the constant 0 (exact)"""
    return None if zero(x) else beta * x


def ln_size(base, comps):
    """ln(1 + S), S = base + sum exp(theta) x (components with x = 0 left out, exact); a float for a constant S"""
    s = base
    for th, v in comps:
        if not zero(v): s = s + exp(th) * v
    return float(np.log1p(s)) if isinstance(s, float) else log(1 + s)


def piece(d, lo, hi):
    """piecewise-linear segment: the part of d in [lo, hi] (hi None: [lo, inf))"""
    return BinaryMax(d - lo, 0.0) if hi is None else BinaryMin(BinaryMax(d - lo, 0.0), float(hi - lo))

NAME = "school_daycare_without_record_pooled"
B_ln_distance = Beta("B_ln_distance", 0.0, None, None, 0)
B_cgt = Beta("B_car_generalised_time", 0.0, None, None, 0)
B_retail_density = Beta("B_retail_density", 0.0, None, None, 0)
B_land_use_mix = Beta("B_land_use_mix", 0.0, None, None, 0)
B_outside_county = Beta("B_outside_home_county", 0.0, None, None, 0)
B_outside_state = Beta("B_outside_home_state", 0.0, None, None, 0)
THETA_N_population = Beta("THETA_nonstudent_school_population", -2.0, -30.0, 15.0, 0)   # base: school pupils
THETA_N_office = Beta("THETA_nonstudent_school_office_jobs", -2.0, -30.0, 15.0, 0)
THETA_D_school = Beta("THETA_daycare_school_pupils", -2.0, -30.0, 15.0, 0)               # base: retail jobs
THETA_D_population = Beta("THETA_daycare_population", -2.0, -30.0, 15.0, 0)
SCALE_daycare = Beta("SCALE_daycare", 1.0, 0.01, 50.0, 0)
DAYCARE = Variable("purpose_id")                       # 0 non-student school, 1 daycare
SCALE = (1 - DAYCARE) + DAYCARE * SCALE_daycare


def utility(g):
    c = g.c; d = g.x("imp")
    lin = [B_ln_distance * log(d), B_cgt * g.x("cgt"), times(B_retail_density, g.z("lnretden")), times(B_land_use_mix, g.z("mix")),
           B_outside_county * (Variable(f"cnty_a_{c}") != g.z("cnty")), B_outside_state * (Variable(f"st_a_{c}") != g.z("st"))]
    sN = ln_size(g.z("stu"), [(THETA_N_population, g.z("pop")), (THETA_N_office, g.z("off"))])
    sD = ln_size(g.z("ret"), [(THETA_D_school, g.z("stu")), (THETA_D_population, g.z("pop"))])
    return SCALE * MultipleSum([t for t in lin if t is not None]) + (1 - DAYCARE) * sN + DAYCARE * sD


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
    m = bio.BIOGEME(db.Database(NAME, df), loglike(meta["n_cfg_max"], meta["n_cand_max"]))
    m.model_name = NAME
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
