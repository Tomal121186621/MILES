#!/usr/bin/env python3
"""Workplace choice of RTS 2017/18 workers with a usual workplace outside the home (estimation half): multinomial logit over
zones with a size term. Choice set: the chosen zone (alternative 0) and 99 zones sampled uniformly from the other 1,586 zones
with jobs (the exact draws of the original estimation, in the data); no sampling correction (uniform sampling). Unweighted.

    V_j = sum_k b_k x_jk + mu * ln( RET_j + exp(g_OFF) OFF_j + exp(g_IND) IND_j + exp(g_OTH) OTH_j ),   g fixed at 0,

so the size term is mu ln(total jobs of the zone): the four job types have equal weights (Beta status 1 for g). The person
variables of the time interactions are centred at their estimation-half means (columns <var>_c; centring_constants.csv), the
household without a car included (car0_c). Bound as in the original estimator: 0.01 <= mu <= 3 (not active). 24 estimated
parameters. Start values = reference estimates (4 decimals; Table est_jobchoice).

    python estimate_workplace_choice.py            estimate; Biogeme writes its report to ../output
    python estimate_workplace_choice.py --check    log-likelihood at the start values only (nothing written); --evaluate is the same
    python estimate_workplace_choice.py --check --start values.csv   same, at other values (csv: parameter,value)"""
import os, sys, tempfile
import pandas as pd
import biogeme.biogeme as bio
from biogeme.database import Database
from biogeme.expressions import Beta, Variable, exp, log
from biogeme.models import loglogit
from biogeme.parameters import Parameters
from biogeme.results_processing import get_pandas_estimated_parameters

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = f"{HERE}/../input/data/estimation/workplace_estimation.parquet"
OUT = os.path.abspath(f"{HERE}/../output")
J = 100

START = {
    "MU_size": 0.8369,
    "B_time": -0.0701,
    "B_ln1p_time": -0.4756,
    "B_time_x_woman": -0.0158,
    "B_time_x_age_under30": -0.0164,
    "B_time_x_age_55plus": -0.0057,
    "B_time_x_income_under40k": -0.0179,
    "B_time_x_income_75_125k": 0.0068,
    "B_time_x_income_125kplus": 0.0107,
    "B_time_x_licence": 0.0236,
    "B_time_x_hhsize": -0.0018,
    "B_time_x_rural_home": 0.0058,
    "B_time_x_no_car": -0.0203,
    "B_same_zone": 0.6814,
    "B_other_county": -0.2653,
    "B_other_state": -0.6772,
    "B_DC_workplace_home_outside_DC": 0.8340,
    "B_office_share_x_income_under40k": -0.7702,
    "B_retail_share_x_age_under30": 1.5432,
    "B_industrial_share_x_woman": -1.4910,
    "B_high_wage_share": 1.5238,
    "B_high_wage_share_x_income_under40k": -0.8870,
    "B_high_wage_share_x_income_75_125k": 1.1052,
    "B_high_wage_share_x_income_125kplus": 1.7629,
}
# time x person: parameter -> centred person column
TIME_X = {"B_time_x_woman": "female_c", "B_time_x_age_under30": "young_c", "B_time_x_age_55plus": "old_c",
          "B_time_x_income_under40k": "g1_c", "B_time_x_income_75_125k": "g3_c", "B_time_x_income_125kplus": "g4_c",
          "B_time_x_licence": "lic_c", "B_time_x_hhsize": "hhs_c", "B_time_x_rural_home": "rurh_c", "B_time_x_no_car": "car0_c"}
BOUNDS = {"MU_size": (0.01, 3.0)}


def model(start=None):
    df = pd.read_parquet(DATA)
    database = Database("workplace_choice", df)
    B = {n: Beta(n, (start or {}).get(n, v), *BOUNDS.get(n, (None, None)), 0) for n, v in START.items()}
    G = {n: Beta(n, 0.0, None, None, 1) for n in ("G_office_jobs", "G_industrial_jobs", "G_other_jobs")}   # job-type log weights, fixed at 0
    x = Variable
    time_coef = B["B_time"] + sum((B[p] * x(c) for p, c in TIME_X.items()), 0)          # car-time slope of the worker
    V = {}
    for j in range(J):
        size = (x(f"jobs_RET_{j}") + exp(G["G_office_jobs"]) * x(f"jobs_OFF_{j}") + exp(G["G_industrial_jobs"]) * x(f"jobs_IND_{j}")
                + exp(G["G_other_jobs"]) * x(f"jobs_OTH_{j}"))   # g fixed at 0: ln of total jobs
        V[j] = (time_coef * x(f"t_{j}") + B["B_ln1p_time"] * x(f"lt_{j}")
                + B["B_same_zone"] * x(f"intra_{j}") + B["B_other_county"] * x(f"cc_{j}") + B["B_other_state"] * x(f"cs_{j}")
                + B["B_DC_workplace_home_outside_DC"] * x(f"dcw_{j}")
                + B["B_office_share_x_income_under40k"] * x(f"z_off_sh_{j}") * x("g1")
                + B["B_retail_share_x_age_under30"] * x(f"z_ret_sh_{j}") * x("young")
                + B["B_industrial_share_x_woman"] * x(f"z_ind_sh_{j}") * x("female")
                + x(f"z_hiearn_{j}") * (B["B_high_wage_share"] + B["B_high_wage_share_x_income_under40k"] * x("g1")
                                        + B["B_high_wage_share_x_income_75_125k"] * x("g3") + B["B_high_wage_share_x_income_125kplus"] * x("g4"))
                + B["MU_size"] * log(size))
    av = {j: 1 for j in range(J)}
    return database, loglogit(V, av, Variable("choice"))


def main():
    start = None
    if "--start" in sys.argv:
        s = pd.read_csv(sys.argv[sys.argv.index("--start") + 1]); start = dict(zip(s.parameter, s.value))
    database, ll = model(start)
    if "--check" in sys.argv or "--evaluate" in sys.argv:
        os.chdir(tempfile.mkdtemp())
        p = Parameters(); p.set_value("generate_html", False); p.set_value("generate_yaml", False)
        b = bio.BIOGEME(database, ll, parameters=p); b.model_name = "workplace_choice_check"
        print(f"N {database.num_rows()}  LL at the start values: {b.calculate_init_likelihood():.4f}")
        return
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    b = bio.BIOGEME(database, ll); b.model_name = "workplace_choice"
    r = b.estimate()
    print(r.short_summary())
    t = get_pandas_estimated_parameters(estimation_results=r)["Estimated parameters"]   # robust s.e. by default
    print(t.to_string()); t.to_csv(f"{b.model_name}_estimates.csv", index=False)


if __name__ == "__main__":
    main()
