#!/usr/bin/env python3
"""Model 06: destination of the first stop of an outing from the usual workplace (article table est_subtour_dest, in est_subtour.tex).

Multinomial logit over the full choice set of 1,588 zones, anchor = the usual workplace zone w, with the tract-to-zone
measurement model of the destination (candidate zones z_k of the destination tract, weights b_k = overlap area / zone area):

    L_n = sum_c w_c [ sum_k b_k exp(V_c,z_k) ] / [ sum_j exp(V_c,j) ]      (one configuration, w_0 = 1);  LL = sum_n ln L_n
    V_j = MU_size ln(1 + retail_j + exp(THETA_office) office_j + exp(THETA_population) population_j + exp(THETA_other) other_jobs_j)
          + sum_b B_distance_b piece_b(d_wj)        pieces 0-1, 1-2, 2-5, 5-10, 10-20, 20-50 km (slope per km; > 50 km: 0)
          + B_car_generalised_time cgt_wj + B_intrazonal [j = w] + B_outside_workplace_county [county_j != county_w]

d = car distance (km, 2016 skim, intrazonal 0.5 sqrt(area)); cgt = car generalised time (min): time + 0.12 $/km x km x 60 / VOT,
VOT = 30 $/h x household income factor (dc_common.car_gt).  The distance piece above 50 km was fixed at 0 (final stage, rule C:
dropped with car generalised time in the model).  Bounds as in the estimation: THETA in [-30, 15], MU_size in [0, 3].
Unweighted, robust (sandwich) standard errors.

    ~/.venvs/biogeme/bin/python estimate_outing_first_stop_destination.py                 # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_outing_first_stop_destination.py --evaluate      # LL at the article estimates, no estimation
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

NAME = "outing_first_stop_destination"
B_d01 = Beta("B_distance_0_1km", 0.0, None, None, 0)
B_d12 = Beta("B_distance_1_2km", 0.0, None, None, 0)
B_d25 = Beta("B_distance_2_5km", 0.0, None, None, 0)
B_d510 = Beta("B_distance_5_10km", 0.0, None, None, 0)
B_d1020 = Beta("B_distance_10_20km", 0.0, None, None, 0)
B_d2050 = Beta("B_distance_20_50km", 0.0, None, None, 0)
B_cgt = Beta("B_car_generalised_time", 0.0, None, None, 0)
B_intrazonal = Beta("B_intrazonal_workplace_zone", 0.0, None, None, 0)
B_outside_county = Beta("B_outside_workplace_county", 0.0, None, None, 0)
THETA_population = Beta("THETA_population", -2.0, -30.0, 15.0, 0)      # size base: retail jobs (theta = 0)
THETA_office = Beta("THETA_office_jobs", -2.0, -30.0, 15.0, 0)
THETA_other = Beta("THETA_other_jobs", -2.0, -30.0, 15.0, 0)
MU_size = Beta("MU_size", 0.8, 0.0, 3.0, 0)


def utility(g):
    c = g.c; d = g.x("imp")
    size = MU_size * ln_size(g.z("ret"), [(THETA_office, g.z("off")), (THETA_population, g.z("pop")), (THETA_other, g.z("oth"))])
    terms = [size, B_d01 * piece(d, 0, 1), B_d12 * piece(d, 1, 2), B_d25 * piece(d, 2, 5), B_d510 * piece(d, 5, 10),
             B_d1020 * piece(d, 10, 20), B_d2050 * piece(d, 20, 50), B_cgt * g.x("cgt"),
             B_intrazonal * (Variable(f"za_{c}") == g.zone()),
             B_outside_county * (Variable(f"cnty_a_{c}") != g.z("cnty"))]
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
