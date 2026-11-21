#!/usr/bin/env python3
"""Model 07: location of work-business episodes of workers with a usual workplace (article table est_loc_wbwork).

Multinomial logit over the full choice set of 1,588 zones, detour form with two anchors: home h (anchor a) and the usual
workplace w (anchor b); tract-to-zone measurement model of the destination (candidate zones z_k, weights b_k):

    L_n = sum_c w_c [ sum_k b_k exp(V_c,z_k) ] / [ sum_j exp(V_c,j) ]      (one configuration, w_0 = 1);  LL = sum_n ln L_n
    V_j = B_ln_office_jobs ln(1 + office_jobs_j)
          + sum_b B_detour_b piece_b(dt_j)           pieces 0-1, 1-2, 2-5, 5-10, 10-20, > 20 km (slope per km)
          + B_car_generalised_time cgt_j + B_home_zone [j = h] + B_workplace_zone [j = w]
          + B_ln_zone_area_km2 ln(area_j) + B_land_use_mix mix_j
          + B_outside_both_counties [county_j != county_h and county_j != county_w]
          + ln(1 + dt_j) (B_no_car + B_fewer_cars_than_drivers + B_AM + B_PM + B_evening, by the record's flags)

dt_j = max(0, d(h,j) + d(j,w) - d(h,w)), d = car distance (km, 2016 skim, intrazonal 0.5 sqrt(area)); cgt_j = the same detour
of car generalised time (min; dc_common.car_gt, >= 0).  Flags: no car, cars < drivers; arrival AM 6-9, PM 15-19, evening 19-6
(reference midday).  area_j = zone area (km2), at least 0.05.  No bounds.  Unweighted, robust (sandwich) standard errors.

    ~/.venvs/biogeme/bin/python estimate_work_business_usual_workplace.py                 # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_work_business_usual_workplace.py --evaluate      # LL at the article estimates, no estimation
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
LNAREA = np.log(ZONES.area_km2.clip(lower=0.05).to_numpy(float))       # ln(zone area, km2; at least 0.05, as in the retail density)
ZA["lnarea"] = LNAREA.tolist()


def add_lnarea(df):
    """candidate columns cand_lnarea_<k> from the candidate zone index cz_<k> (not stored in the Biogeme data)"""
    for k in range(sum(c.startswith("cz_") for c in df.columns)):
        df[f"cand_lnarea_{k}"] = LNAREA[df[f"cz_{k}"].to_numpy().astype(int)]
    return df


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

NAME = "work_business_usual_workplace"
B_dt01 = Beta("B_detour_0_1km", 0.0, None, None, 0)
B_dt12 = Beta("B_detour_1_2km", 0.0, None, None, 0)
B_dt25 = Beta("B_detour_2_5km", 0.0, None, None, 0)
B_dt510 = Beta("B_detour_5_10km", 0.0, None, None, 0)
B_dt1020 = Beta("B_detour_10_20km", 0.0, None, None, 0)
B_dt20 = Beta("B_detour_20km_plus", 0.0, None, None, 0)
B_cgt = Beta("B_car_generalised_time", 0.0, None, None, 0)
B_home_zone = Beta("B_home_zone", 0.0, None, None, 0)
B_workplace_zone = Beta("B_workplace_zone", 0.0, None, None, 0)
B_ln_zone_area = Beta("B_ln_zone_area_km2", 0.0, None, None, 0)
B_land_use_mix = Beta("B_land_use_mix", 0.0, None, None, 0)
B_outside_county = Beta("B_outside_counties_of_both_anchors", 0.0, None, None, 0)
B_lndt_no_car = Beta("B_ln_detour_x_no_car", 0.0, None, None, 0)
B_lndt_fewer_cars = Beta("B_ln_detour_x_fewer_cars_than_drivers", 0.0, None, None, 0)
B_lndt_am = Beta("B_ln_detour_x_AM", 0.0, None, None, 0)
B_lndt_pm = Beta("B_ln_detour_x_PM", 0.0, None, None, 0)
B_lndt_ev = Beta("B_ln_detour_x_evening", 0.0, None, None, 0)
B_ln_office_jobs = Beta("B_ln_office_jobs", 0.8, None, None, 0)         # attraction: ln(1 + office jobs)
# person / time-of-day coefficient of ln(1 + detour), one expression per record
LNDT_COEF = (B_lndt_no_car * Variable("f_car0") + B_lndt_fewer_cars * Variable("f_car1") + B_lndt_am * Variable("f_am")
             + B_lndt_pm * Variable("f_pm") + B_lndt_ev * Variable("f_ev"))


def utility(g):
    c = g.c; dt = g.x("imp"); cj = g.z("cnty")
    size = B_ln_office_jobs * ln_size(g.z("off"), [])
    terms = [size, B_dt01 * piece(dt, 0, 1), B_dt12 * piece(dt, 1, 2), B_dt25 * piece(dt, 2, 5), B_dt510 * piece(dt, 5, 10),
             B_dt1020 * piece(dt, 10, 20), B_dt20 * piece(dt, 20, None), B_cgt * g.x("cgt"),
             B_home_zone * (Variable(f"za_{c}") == g.zone()), B_workplace_zone * (Variable(f"zb_{c}") == g.zone()),
             times(B_ln_zone_area, g.z("lnarea")), times(B_land_use_mix, g.z("mix")),
             B_outside_county * ((Variable(f"cnty_a_{c}") != cj) * (Variable(f"cnty_b_{c}") != cj)),
             LNDT_COEF * log(1 + dt)]
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
    return add_lnarea(df.astype("float64")), meta


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
