#!/usr/bin/env python3
"""Model 03: stop location, recreation stops (article table est_stop_RECREATION_stop).

Multinomial logit over the full choice set of 1,588 zones with sequential anchors: a = the location the person comes from,
b = the next anchor of the tour (primary destination or home).  Location mixture (survey traffic zones spread over model
zones): each record has up to 4 anchor configurations c (zones of a and b, weight w_c) and up to 4 possible zones z_k of the
stop (weight b_k).  The likelihood is

    L_n = sum_c w_c * [ sum_k b_k exp(V_c,z_k) ] / [ sum_j exp(V_c,j) ]          LL = sum_n ln L_n

    V_c,j = MU_size ln(1 + S_j) + sum of the terms below, S_j = retail_jobs_j + exp(THETA_population) population_j + exp(THETA_office_jobs) office_jobs_j + exp(THETA_school_pupils) school_pupils_j
    detour t = max(0, d(a,j) + d(j,b) - d(a,b)), d = car distance of the 2016 skim (km, intrazonal 0.5 sqrt(area))
    piecewise-linear detour (pieces clip(t - lo, 0, hi - lo)) 1-2 km, 2-5 km, 5-10 km, 10-20 km, 20-inf km (no 0-1 km piece: the slope below 1 km is 0)
    stop in the zone of a / of b; area dummies; ln(1 + retail jobs / km2); land-use mix;
    outside the counties (states) of BOTH anchors;
    ln(1 + t) x tour mode not car, inbound stop
    mode-choice logsum of the detour: LS(a,j) + LS(j,b) - LS(a,b) (tour mode models of the run, see README)
MU_size is held at 1 (the estimate was on the bound and the bound was adopted).  Bounds as in the estimation: THETA in [-30, 15], MU_size in [0, 3].  Unweighted; robust (sandwich) standard errors.

    ~/.venvs/biogeme/bin/python estimate_stop_recreation.py                 # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_stop_recreation.py --evaluate      # LL at the article estimates, no estimation
        [--half estimation|holdout] [--at article|full]            (nothing is written to ../output)
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

# ------------------------------------------------------------------------------------------------ specification
SIZE_BASE = "ret"                                     # size component with theta = 0
SIZE_COMPS = ['pop', 'off', 'stu']                                     # components with a free weight exp(theta)
PIECES = [(1, 2), (2, 5), (5, 10), (10, 20), (20, None)]                                        # detour pieces (lo, hi km; None = open)
FLAGS = ['nonauto', 'inbound']                                          # ln(1 + detour) x chooser flag (data column f_<flag>)
ZONE_TERMS = ["bc", "dcz", "cbd", "va", "othst", "lnretden", "mix"]
CGT = False                                              # car generalised detour time in the model
MU_FIXED = 1.0                                     # value at which MU_size is held (None: estimated)

# ------------------------------------------------------------------------------------------------ parameters (article names)
def B(name, start=0.0, lo=None, hi=None, fixed=0):
    return Beta(name, start, lo, hi, fixed)


PIECE_NAME = {(0, 1): "B_detour_0_1km", (1, 2): "B_detour_1_2km", (2, 5): "B_detour_2_5km", (5, 10): "B_detour_5_10km",
              (10, 20): "B_detour_10_20km", (20, None): "B_detour_over_20km"}
B_piece = {p: B(PIECE_NAME[p]) for p in PIECES}
B_logsum = B("B_mode_choice_logsum_detour")
B_cgt = B("B_car_generalised_time_detour_min") if CGT else None
B_zone_previous = B("B_stop_in_zone_of_previous_location")
B_zone_next = B("B_stop_in_zone_of_next_anchor")
ZONE_NAME = {"bc": "B_baltimore_city", "dcz": "B_washington_dc", "cbd": "B_central_business_district", "va": "B_virginia",
             "othst": "B_delaware_pennsylvania_west_virginia", "lnretden": "B_ln_retail_jobs_per_km2", "mix": "B_land_use_mix"}
B_zone = {a: B(ZONE_NAME[a]) for a in ZONE_TERMS}
B_outside_counties = B("B_outside_counties_of_both_anchors")
B_outside_states = B("B_outside_states_of_both_anchors")
FLAG_NAME = {"car0": "B_ln_detour_x_no_car", "car1": "B_ln_detour_x_fewer_cars_than_drivers", "hhsize": "B_ln_detour_x_household_size",
             "nonauto": "B_ln_detour_x_tour_mode_not_car", "inbound": "B_ln_detour_x_inbound_stop"}
B_flag = {f: B(FLAG_NAME[f]) for f in FLAGS}
THETA_NAME = {"pop": "THETA_population", "ret": "THETA_retail_jobs", "off": "THETA_office_jobs", "oth": "THETA_other_jobs",
              "stu": "THETA_school_pupils"}
THETA = {c: B(THETA_NAME[c], -2.0, -30.0, 15.0) for c in SIZE_COMPS}
MU_size = B("MU_size", 1.0, None, None, 1) if MU_FIXED is not None else B("MU_size", 0.8, 0.0, 3.0)


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


def is0(x):
    return isinstance(x, float) and x == 0.0


def size_term(g):
    s = g.z(SIZE_BASE); parts = [] if is0(s) else [s]
    for c in SIZE_COMPS:
        x = g.z(c)
        if not is0(x): parts.append(exp(THETA[c]) * x)
    if not parts: return None                                            # ln(1 + 0) = 0
    if all(isinstance(p, float) for p in parts): return MU_size * float(np.log1p(sum(parts)))
    return MU_size * log(1 + MultipleSum(parts) if len(parts) > 1 else 1 + parts[0])


FLAG_COEF = MultipleSum([B_flag[f] * Variable(f"f_{f}") for f in FLAGS]) if len(FLAGS) > 1 else (B_flag[FLAGS[0]] * Variable(f"f_{FLAGS[0]}") if FLAGS else None)


def utility(g):
    c = g.c; t = g.x("imp"); terms = [size_term(g)]
    for (lo, hi), b in B_piece.items():
        piece = BinaryMax(t - lo, 0.0) if hi is None else (BinaryMin(t, float(hi)) if lo == 0 else BinaryMin(BinaryMax(t - lo, 0.0), float(hi - lo)))
        terms.append(b * piece)
    terms.append(B_logsum * g.x("ls"))
    if CGT: terms.append(B_cgt * g.x("cgt"))
    terms.append(B_zone_previous * (Variable(f"za_{c}") == g.zone()))
    terms.append(B_zone_next * (Variable(f"zb_{c}") == g.zone()))
    for a in ZONE_TERMS:
        x = g.z(a)
        if not is0(x): terms.append(B_zone[a] * x)
    terms.append(B_outside_counties * ((Variable(f"cnty_a_{c}") != g.z("cnty")) * (Variable(f"cnty_b_{c}") != g.z("cnty"))))
    terms.append(B_outside_states * ((Variable(f"st_a_{c}") != g.z("st")) * (Variable(f"st_b_{c}") != g.z("st"))))
    if FLAG_COEF is not None: terms.append(FLAG_COEF * log(1 + t))
    return MultipleSum([x for x in terms if x is not None])


def loglike(n_cfg, n_cand):
    L = []
    for c in range(n_cfg):
        den = MultipleSum([exp(utility(At(c, j=j))) for j in range(NZ)])
        num = MultipleSum([Variable(f"b_{k}") * exp(utility(At(c, k=k))) for k in range(n_cand)]) if n_cand > 1 else Variable("b_0") * exp(utility(At(c, k=0)))
        L.append(Variable(f"w_{c}") * num / den)
    return log(MultipleSum(L) if len(L) > 1 else L[0])


def parts(half):
    folder = os.path.join(DATA, "estimation" if half == "estimation" else "holdout")
    return json.load(open(os.path.join(folder, "biogeme_meta.json"))), sorted(glob.glob(os.path.join(folder, "biogeme_part*.parquet")))


def read(half):
    meta, files = parts(half)
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True).astype("float64"), meta


def reference(at):
    r = pd.read_csv(os.path.join(HERE, "reference_estimates.csv"))
    r = r[~r.parameter.isin(["LL0", "LL_beta", "N", "K"])].set_index("parameter")
    return (r.article_coefficient if at == "article" else r.coefficient).astype(float).to_dict()


def evaluate(half, at):
    """LL at the reference values without estimating: eager evaluation (use_jit=False, small memory).  The rows are grouped
    by their number of anchor configurations g over all parts; each group uses the expression with exactly g configurations
    and only the columns of those configurations (the padding configurations have weight 0, so this is the same likelihood).
    The cost of an eager evaluation depends mostly on the size of the expression, not on the number of rows."""
    meta, files = parts(half); vals = reference(at); tot = 0.0; n = 0; t0 = time.time()
    cnt = pd.concat([pd.read_parquet(f, columns=["n_cfg"]) for f in files]).n_cfg
    cwd = os.getcwd(); tmp = tempfile.mkdtemp(prefix="bio_eval_")
    os.chdir(tmp)
    try:
        for g in sorted(cnt.unique()):
            g = int(g); dfs = []
            for f in files:
                d = pd.read_parquet(f); d = d[d.n_cfg == g]
                drop = [c for c in d.columns if any(c.startswith(p) for p in ("w_", "za_", "zb_", "cnty_a_", "cnty_b_", "st_a_", "st_b_", "imp_", "cgt_", "ls_", "cimp_", "ccgt_", "cls_"))
                        and int(c.split("_")[2 if c.startswith(("cnty_", "st_")) else 1]) >= g]
                dfs.append(d.drop(columns=drop).astype("float64"))
            part = pd.concat(dfs, ignore_index=True); del dfs
            m = bio.BIOGEME(db.Database(f"eval{g}", part), loglike(g, meta["n_cand_max"]), use_jit=False, generate_html=False,
                            generate_yaml=False, save_iterations=False)
            m.model_name = f"eval_{g}"; m.change_init_values(vals)
            v = m.calculate_init_likelihood(); tot += v; n += len(part)
            print(f"  configurations {g}: N {len(part)} LL {v:.4f} ({time.time() - t0:.0f} s)", flush=True)
            del m, part
    finally:
        os.chdir(cwd)
    print(f"{half}: N {n}  LL at the {at} estimates = {tot:.4f}", flush=True)
    return tot


def estimate(outdir=OUT):
    df, meta = read("estimation")
    os.makedirs(outdir, exist_ok=True); os.chdir(outdir)
    m = bio.BIOGEME(db.Database("stop_recreation", df), loglike(meta["n_cfg_max"], meta["n_cand_max"]))
    m.model_name = "stop_recreation"
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
