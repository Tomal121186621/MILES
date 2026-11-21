#!/usr/bin/env python3
"""Model 01: primary destination of discretionary tours, pooled model of shopping, recreation, accompanying and other tours
with purpose-specific scale (article table est_dc_pooled).

Multinomial logit over the full choice set of 1,588 zones, no sampling of alternatives.  Location mixture: the survey
traffic zones of the destination and of home are spread over the model zones (destination by jobs, home by housing units):
record n has candidate destination zones z_k with weights b_k and home configurations c (home zone h_c) with weights w_c:

    L_n = sum_c w_c [ sum_k b_k exp(U_c,z_k) ] / [ sum_j exp(U_c,j) ],     LL = sum_n ln L_n
    U_pj = SCALE_p * V_pj      (SCALE_SHOPPING = 1; recreation, accompanying, other free)
    V_pj = B_ln_x_p ln(1 + x_pj)        x = retail jobs (shopping, recreation, other) or school enrolment (accompanying)
           + sum_pieces B_dist_piece * piece(d_hj)  (knots 1, 2, 5, 10, 20, 50 km; > 50 km fixed at 0)
           + B_intrazonal_p [j = h] + area dummies, B_ln_zone_area_km2_p ln(area_j), land-use mix (purpose specific)
           + B_outside_home_county [county_j != county_h] + B_outside_home_state [state_j != state_h]
           + ln(d_hj) * (sum of B_lndist_x * flag_x)  (no car, cars < drivers, worker, < 18, 65+, children, male,
             one-person household, AM, PM, evening, tour with stops; all shared)
           + B_car_gen_time_p cgt_hj
SCALE_p multiplies every coefficient of V_p.  Coefficients are reported in V units (as in the
article); the effective coefficient of purpose p is SCALE_p times the reported one.  Shared coefficients (same value in V_p of
every purpose that has the variable): distance pieces, boundaries, all ln-distance interactions; car generalised time shared
by shopping and other (own for recreation and accompanying); all other coefficients, including the coefficient of
ln(1 + x), are purpose specific.  area_j = zone area (km2), at least 0.05.
Area dummies: Baltimore City, Washington DC, high job-density zone (at least 10,000 jobs per km2; parameters B_cbd_<purpose>),
Virginia, DE/PA/WV.
d = car distance (km), intrazonal 0.5 sqrt(area); cgt = car generalised time (min) home -> j.  Bounds as in the estimation:
SCALE in [0.01, 50].  Unweighted, robust s.e.
Implementation: one utility per zone with per-record coefficients (purpose dummies d_<PURPOSE> of the data select the
purpose's coefficient), so the expression has the size of one purpose's model.

    ~/.venvs/biogeme/bin/python estimate_primary_destination_pooled.py                 # estimate (results in ../output)
    ~/.venvs/biogeme/bin/python estimate_primary_destination_pooled.py --evaluate      # LL at the article estimates, no estimation
        [--half estimation|holdout] [--at article|full]                                  (nothing is written to ../output)
    option --outdir DIR: Biogeme output folder (default ../output)
"""
import argparse, json, os, tempfile, time
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

P = ["SHOPPING", "RECREATION", "ACCOMPANY", "OTHER"]
ATTR = {"SHOPPING": "ret", "RECREATION": "ret", "ACCOMPANY": "stu", "OTHER": "ret"}      # attraction variable x of each purpose
XNAME = {"ret": "retail_jobs", "stu": "school_enrolment"}

# ------------------------------------------------------------------------------------------------ parameters (V units)
PIECES = [(0, 1), (1, 2), (2, 5), (5, 10), (10, 20), (20, 50), (50, None)]
B_dist = {lo: Beta(f"B_dist_{lo}_{hi}km_shared" if hi else "B_dist_50km_plus_shared", 0.0, None, None, 1 if hi is None else 0)
          for lo, hi in PIECES}                                            # > 50 km fixed at 0 (status 1)
B_outside_home_county = Beta("B_outside_home_county_shared", 0.0, None, None, 0)
B_outside_home_state = Beta("B_outside_home_state_shared", 0.0, None, None, 0)
LND = {"car0": "no_car", "car1": "fewer_cars_than_drivers", "worker": "worker", "kid": "person_under18", "senior": "person_65plus",
       "child": "household_with_children", "male": "male", "hh1": "one_person_household", "am": "arrival_AM", "pm": "arrival_PM",
       "ev": "arrival_evening", "multi": "tour_with_stops"}
B_lnd = {f: Beta(f"B_lndist_x_{n}_shared", 0.0, None, None, 0) for f, n in LND.items()}
ZTERMS = {"intra": "intrazonal", "bc": "baltimore_city", "dcz": "washington_dc", "cbd": "cbd", "va": "virginia",
          "othst": "de_pa_wv", "lnarea": "ln_zone_area_km2", "mix": "landuse_mix"}
B_z = {q: {p: Beta(f"B_{n}_{p}", 0.0, None, None, 0) for p in P} for q, n in ZTERMS.items()}
B_cgt_SO = Beta("B_car_gen_time_SO", 0.0, None, None, 0)
B_cgt = {"SHOPPING": B_cgt_SO, "OTHER": B_cgt_SO, "RECREATION": Beta("B_car_gen_time_RECREATION", 0.0, None, None, 0),
         "ACCOMPANY": Beta("B_car_gen_time_ACCOMPANY", 0.0, None, None, 0)}
B_attr = {p: Beta(f"B_ln_{XNAME[ATTR[p]]}_{p}", 0.8, None, None, 0) for p in P}      # coefficient of ln(1 + x_p)
SCALE = {"SHOPPING": 1.0, **{p: Beta(f"SCALE_{p}", 1.0, 0.01, 50.0, 0) for p in P[1:]}}


def all_betas():
    out = list(B_dist.values()) + [B_outside_home_county, B_outside_home_state] + list(B_lnd.values())
    out += [b for d in B_z.values() for b in d.values()] + [B_cgt_SO, B_cgt["RECREATION"], B_cgt["ACCOMPANY"]]
    out += [B_attr[p] for p in P] + [SCALE[p] for p in P[1:]]
    return out


def set_values(vals):
    """start values of the Beta objects before the expression is built (faster than BIOGEME.change_init_values on this
    very large expression; same result)"""
    names = {b.name: b for b in all_betas()}
    miss = set(vals) - set(names)
    if miss: raise KeyError(f"unknown parameters: {miss}")
    for k, v in vals.items(): names[k].init_value = float(v)


def D(p):
    return Variable(f"d_{p}")


def per_record(coef):
    """coefficient of the record's purpose: sum_p d_p coef[p] (purposes sharing one Beta are grouped)"""
    groups = {}
    for p, b in coef.items(): groups.setdefault(id(b), (b, []))[1].append(p)
    terms = []
    for b, ps in groups.values():
        dd = D(ps[0]) if len(ps) == 1 else MultipleSum([D(p) for p in ps])
        terms.append(dd if (isinstance(b, float) and b == 1.0) else dd * b)
    return MultipleSum(terms) if len(terms) > 1 else terms[0]


class At:
    """the variables of zone j (alternative of the denominator) or of candidate k (numerator) under configuration c"""
    def __init__(self, c, j=None, k=None):
        self.c, self.j, self.k = c, j, k

    def z(self, a):
        return ZA[a][self.j] if self.k is None else Variable(f"cand_{a}_{self.k}")

    def x(self, var):
        return Variable(f"{var}_{self.c}_{self.j}") if self.k is None else Variable(f"c{var}_{self.c}_{self.k}")

    def zone(self):
        return self.j if self.k is None else Variable(f"cz_{self.k}")


def zero(x):
    return isinstance(x, float) and x == 0.0


def utility(g):
    c = g.c; d = g.x("imp"); terms = []
    # attraction: per-record coefficient of ln(1 + x), x = the purpose's attraction variable
    for x in sorted(set(ATTR.values())):
        v = g.z(x)
        if zero(v): continue
        terms.append(per_record({p: B_attr[p] for p in P if ATTR[p] == x}) * (float(np.log1p(v)) if isinstance(v, float) else log(1 + v)))
    # distance pieces (shared)
    for lo, hi in PIECES:
        piece = BinaryMax(d - lo, 0.0) if hi is None else BinaryMin(BinaryMax(d - lo, 0.0), float(hi - lo))
        terms.append(B_dist[lo] * piece)
    terms.append(per_record(B_z["intra"]) * (Variable(f"za_{c}") == g.zone()))
    for q in ["bc", "dcz", "cbd", "va", "othst", "lnarea", "mix"]:
        x = g.z(q)
        if not zero(x): terms.append(per_record(B_z[q]) * x)
    terms.append(B_outside_home_county * (Variable(f"cnty_a_{c}") != g.z("cnty")))
    terms.append(B_outside_home_state * (Variable(f"st_a_{c}") != g.z("st")))
    terms.append(log(d) * MultipleSum([B_lnd[f] * Variable(f"f_{f}") for f in LND]))
    terms.append(per_record(B_cgt) * g.x("cgt"))
    return per_record(SCALE) * MultipleSum(terms)


def loglike(n_cfg, n_cand):
    L = []
    for c in range(n_cfg):
        den = MultipleSum([exp(utility(At(c, j=j))) for j in range(NZ)])
        num = MultipleSum([Variable(f"b_{k}") * exp(utility(At(c, k=k))) for k in range(n_cand)]) if n_cand > 1 else Variable("b_0") * exp(utility(At(c, k=0)))
        L.append(Variable(f"w_{c}") * num / den)
    return log(MultipleSum(L) if len(L) > 1 else L[0])


def pad(df, n_cfg, n_cfg_max):
    """configurations n_cfg..n_cfg_max-1 of a part: copies of configuration 0 with weight 0 (exact)"""
    new = {}
    for c in range(n_cfg, n_cfg_max):
        for col in df.columns:
            if col.endswith("_0") and not col.startswith(("cz_", "b_", "cand_")) and (col.count("_") == 1 or col.startswith(("cnty_", "st_"))):
                new[col[:-1] + str(c)] = df[col]
        for col in df.columns:
            if col.startswith(("imp_0_", "cgt_0_", "cimp_0_", "ccgt_0_")):
                new[col.replace("_0_", f"_{c}_", 1)] = df[col]
        new[f"w_{c}"] = 0.0
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1) if new else df


def read(half, n_cfg=None):
    """all parts of the half (n_cfg None: padded to the largest number of configurations) or the parts with n_cfg configurations"""
    folder = os.path.join(DATA, "estimation" if half == "estimation" else "holdout")
    meta = json.load(open(os.path.join(folder, "biogeme_meta.json")))
    parts = [q for q in meta["parts"] if n_cfg is None or q["n_cfg"] == n_cfg]
    K = meta["n_cfg_max"] if n_cfg is None else n_cfg
    dfs = [pad(pd.read_parquet(os.path.join(folder, q["file"])).astype("float64"), q["n_cfg"], K) for q in parts]
    return add_lnarea(pd.concat(dfs, ignore_index=True)), meta


def reference(at):
    r = pd.read_csv(os.path.join(HERE, "reference_estimates.csv"))
    r = r[~r.parameter.isin(["LL0", "LL_beta", "N", "K"])].set_index("parameter")
    return (r.article_coefficient if at == "article" else r.coefficient).astype(float).to_dict()


def evaluate(half, at, groups=None):
    """LL at the reference values without estimating (eager evaluation, use_jit=False: small memory), records grouped by
    their number of home configurations (each group with the expression of exactly that many)"""
    vals = reference(at); tot = 0.0; t0 = time.time(); N = 0
    set_values(vals)
    meta = json.load(open(os.path.join(DATA, "estimation" if half == "estimation" else "holdout", "biogeme_meta.json")))
    cwd = os.getcwd(); tmp = tempfile.mkdtemp(prefix="bio_eval_"); os.chdir(tmp)
    try:
        for g in sorted({q["n_cfg"] for q in meta["parts"]}):
            if groups and g not in groups: continue
            part, _ = read(half, g)
            m = bio.BIOGEME(db.Database(f"eval{g}", part), loglike(g, meta["n_cand_max"]), use_jit=False, generate_html=False,
                            generate_yaml=False, save_iterations=False)
            m.model_name = f"eval_{g}"
            v = m.calculate_init_likelihood(); tot += v; N += len(part)
            by = {p: int((part[f"d_{p}"] > 0).sum()) for p in P}
            print(f"  configurations {g}: N {len(part)} {by} LL {v:.4f} ({time.time() - t0:.0f} s)", flush=True)
            del m, part
    finally:
        os.chdir(cwd)
    print(f"{half}: N {N}  LL at the {at} estimates = {tot:.4f}", flush=True)
    return tot


def estimate(outdir=OUT):
    df, meta = read("estimation")
    os.makedirs(outdir, exist_ok=True); os.chdir(outdir)
    m = bio.BIOGEME(db.Database("primary_destination_pooled", df), loglike(meta["n_cfg_max"], meta["n_cand_max"]))
    m.model_name = "primary_destination_pooled"
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
    ap.add_argument("--groups", default="", help="evaluate only these numbers of configurations, e.g. 2,3,4")
    ap.add_argument("--outdir", default=OUT, help="folder of the Biogeme output files (default ../output)")
    a = ap.parse_args()
    if a.evaluate: evaluate(a.half, a.at, [int(x) for x in a.groups.split(",") if x])
    else: estimate(os.path.abspath(a.outdir))
