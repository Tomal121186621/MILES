#!/usr/bin/env python3
"""School location choice, high school (grades 9-12) (RTS 2017/18 students with a school record, estimation half): multinomial logit over
ALL 719 zones with enrolment of the segment (full choice set, no sampling), with a location mixture over the survey home and
school locations. Unweighted.

Utility of zone j for home zone h:
    V_hj = mu * ln( sum_k exp(g_k) N_k,hj + 1e-12 ) + sum_m b_m x_m,hj
Size components: nk0 public enrolment of the band outside the home's attendance boundary (reference, weight 1), nk1
public enrolment inside the boundary (SABS 2015-16; log weight G_in_boundary_public),
nk2 private enrolment: weight 1 (its log weight is fixed at 0, p = 0.37 when estimated).
Availability: enrolment of the student's own band in zone j (av_h_j). Likelihood of student n (exactly that of the original
estimator, sc_03_engine.Model.scores):
    L_n = sum_h sum_c w_h w_c exp(V_hc) / sum_j av_hj exp(V_hj)
    log L_n = WeightedLogSumExp_{h,c}( V_hc - WeightedLogSumExp_j(V_hj; av_hj) ; w_h w_c )
w_h: weight of possible home zone h (up to 3), w_c: weight of possible school zone c (up to 2); unused slots carry a copy of
slot 0 and weight 0. V_hc is the utility of the school zone c from home zone h (columns c<var>_h_c of the candidates table).
Variables (data_dictionary.csv): car time, other county x public share, charter-or-magnet share (cm), own-race share of
the zone's enrolment (own). The quality variables qpub and qnone are in the tables (tested, not in the model).
Bound as in the original estimator: mu >= 0.01. Start values = article estimates (Table est_school, column high school).

Memory / time: see README.md (the expression has 3 x 719 utilities).

    python estimate_school_location_high_school.py            estimate; Biogeme writes its report to ../output
    python estimate_school_location_high_school.py --check    log-likelihood at the start values only (nothing written)
    python estimate_school_location_high_school.py --check --start values.csv   same, at other values (csv: parameter,value)"""
import os, sys, tempfile
import numpy as np, pandas as pd
import biogeme.biogeme as bio
from biogeme.database import Database
from biogeme.expressions import Beta, Variable, WeightedLogSumExp, exp, log
from biogeme.parameters import Parameters
from biogeme.results_processing import get_pandas_estimated_parameters

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = f"{HERE}/../input/data/estimation/school_hs_estimation"
OUT = os.path.abspath(f"{HERE}/../output")

START = {
    'MU_size': 0.6637,
    'G_in_boundary_public': 4.2834,
    'B_time': -0.1028,
    'B_other_county_x_public_share': -2.5892,
    'B_charter_or_magnet_share': 0.7409,
    'B_own_race_share': 1.6429,
}
SIZE_W = [None, 'G_in_boundary_public', None]          # size components nk0, nk1, nk2: None = reference (weight 1), else the log-weight parameter
TERMS = {
    'B_time': ('t', None),
    'B_other_county_x_public_share': ('ccpub', None),
    'B_charter_or_magnet_share': ('cm', None),
    'B_own_race_share': ('own', None),
}           # parameter -> (alternative variable, person variable or None)
ALTVARS = sorted({v for v, _ in TERMS.values()} | {"nk0", "nk1", "nk2"})


def wide():
    """long tables -> one row per student; missing home / school slots: copy of slot 0 with weight 0"""
    st = pd.read_parquet(f"{DATA}_students.parquet"); A = pd.read_parquet(f"{DATA}_alternatives.parquet"); C = pd.read_parquet(f"{DATA}_candidates.parquet")
    H = sum(c.startswith("w_home_") for c in st.columns); NC = sum(c.startswith("w_school_") for c in st.columns); J = int(A.j.max()) + 1
    N = len(st); cols = {"student": st.student.values}
    for v in {p for _, p in TERMS.values() if p}: cols[v] = st[v].values.astype(float)
    a = A.set_index(["student", "home_slot", "j"]).sort_index()
    for h in range(H):
        cols[f"w_home_{h}"] = st[f"w_home_{h}"].fillna(0).values
        hh = np.where(st[f"w_home_{h}"].values > 0, h, 0)              # slot used for the values (slot 0 if missing)
        idx = pd.MultiIndex.from_arrays([np.repeat(st.student.values, J), np.repeat(hh, J), np.tile(np.arange(J), N)])
        sub = a.reindex(idx)
        for v in ALTVARS + ["av"]:
            M = sub[v].values.reshape(N, J)
            for j in range(J): cols[f"{v}_{h}_{j}"] = M[:, j]
        c = C.set_index(["student", "home_slot", "school_slot"]).sort_index()
        for k in range(NC):
            cols[f"w_school_{h}_{k}"] = np.where(st[f"w_home_{h}"].values > 0, st[f"w_school_{k}"].fillna(0).values, 0.0)
            kk = np.where(cols[f"w_school_{h}_{k}"] > 0, k, 0)
            sc = c.reindex(pd.MultiIndex.from_arrays([st.student.values, hh, kk]))
            for v in ALTVARS: cols[f"c{v}_{h}_{k}"] = sc[v].values
    df = pd.DataFrame(cols); assert df.notna().all().all()
    return df, H, NC, J


def utility(B, h, j=None, k=None):
    """utility from the columns <v>_h_j (alternatives) or c<v>_h_k (school zone k of home slot h)"""
    col = (lambda name: Variable(f"{name}_{h}_{j}")) if k is None else (lambda name: Variable(f"c{name}_{h}_{k}"))
    size = sum(((1.0 if g is None else exp(B[g])) * col(f"nk{i}") for i, g in enumerate(SIZE_W)), 0) + 1e-12
    u = B["MU_size"] * log(size)
    for p, (x, pv) in TERMS.items():
        u = u + (B[p] * col(x) * Variable(pv) if pv else B[p] * col(x))
    return u


def model(start=None):
    df, H, NC, J = wide()
    database = Database("school_location_high_school", df)
    B = {n: Beta(n, (start or {}).get(n, v), 0.01 if n == "MU_size" else None, None, 0) for n, v in START.items()}
    terms, weights = [], []
    for h in range(H):
        lse = WeightedLogSumExp([utility(B, h, j=j) for j in range(J)], [Variable(f"av_{h}_{j}") for j in range(J)])
        for k in range(NC):
            terms.append(utility(B, h, k=k) - lse); weights.append(Variable(f"w_home_{h}") * Variable(f"w_school_{h}_{k}"))
    return database, WeightedLogSumExp(terms, weights)


def main():
    start = None
    if "--start" in sys.argv:
        s = pd.read_csv(sys.argv[sys.argv.index("--start") + 1]); start = dict(zip(s.parameter, s.value))
    database, ll = model(start)
    if "--check" in sys.argv:
        os.chdir(tempfile.mkdtemp())
        p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "school_location_high_school_check"
        print(f"N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "school_location_high_school"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
