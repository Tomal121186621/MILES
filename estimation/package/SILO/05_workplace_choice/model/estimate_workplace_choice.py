#!/usr/bin/env python3
"""Workplace choice of RTS 2017/18 workers with a usual workplace outside the home (estimation half): multinomial logit over
zones with a size term. Choice set: the chosen zone (alternative 0) and 99 zones sampled uniformly from the other 1,586 zones
with jobs (the exact draws of the original estimation, in the data); no sampling correction (uniform sampling). Unweighted.

    V_j = sum_k b_k x_jk + mu * ln( RET_j + exp(g_OFF) OFF_j + exp(g_IND) IND_j + exp(g_OTH) OTH_j )

(retail jobs = reference of the size weights). The person variables of the time interactions are centred at their
estimation-half means (columns <var>_c). Bounds as in the original estimator: 0.01 <= mu <= 3, |g| <= 10 (not active at the
estimates). Start values = article estimates (Table est_jobchoice).

    python estimate_workplace_choice.py            estimate; Biogeme writes its report to ../output
    python estimate_workplace_choice.py --check    log-likelihood at the start values only (nothing written)
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
    "MU_size": 0.8489, "G_office_jobs": -0.5350, "G_industrial_jobs": -0.6907, "G_other_jobs": -0.1777,
    "B_time": -0.0692, "B_ln1p_time": -0.4844,
    "B_time_x_woman": -0.0155, "B_time_x_age_under30": -0.0158, "B_time_x_age_55plus": -0.0049,
    "B_time_x_income_under40k": -0.0195, "B_time_x_income_75_125k": 0.0076, "B_time_x_income_125kplus": 0.0122,
    "B_time_x_licence": 0.0280, "B_time_x_hhsize": -0.0022, "B_time_x_children": 0.0031, "B_time_x_two_plus_workers": -0.0014,
    "B_time_x_rural_home": 0.0077,
    "B_same_zone": 0.6405, "B_other_county": -0.2794, "B_other_state": -0.7637, "B_DC_workplace_home_outside_DC": 1.0973,
    "B_acc_nonwork_workplace": -0.0889,
    "B_area_baltimore_city": -0.0830, "B_area_montgomery_prince_georges": 0.1126, "B_area_arlington_alexandria": 0.4285,
    "B_area_other_northern_virginia": 0.0478, "B_area_rest_of_maryland": 0.0822, "B_area_other_states": -0.1437,
    "B_office_share_x_income_under40k": -0.5725, "B_office_share_x_income_125kplus": 0.0903,
    "B_retail_share_x_age_under30": 1.2806, "B_industrial_share_x_woman": -1.3588,
    "B_high_wage_share": 1.8532, "B_high_wage_share_x_income_under40k": -1.0012, "B_high_wage_share_x_income_75_125k": 1.0819,
    "B_high_wage_share_x_income_125kplus": 1.6792,
}
# time x person: parameter -> centred person column
TIME_X = {"B_time_x_woman": "female_c", "B_time_x_age_under30": "young_c", "B_time_x_age_55plus": "old_c",
          "B_time_x_income_under40k": "g1_c", "B_time_x_income_75_125k": "g3_c", "B_time_x_income_125kplus": "g4_c",
          "B_time_x_licence": "lic_c", "B_time_x_hhsize": "hhs_c", "B_time_x_children": "kids_c",
          "B_time_x_two_plus_workers": "w2_c", "B_time_x_rural_home": "rurh_c"}
AREA = {"B_area_baltimore_city": "reg_bc", "B_area_montgomery_prince_georges": "reg_mopg", "B_area_arlington_alexandria": "reg_nvc",
        "B_area_other_northern_virginia": "reg_nvo", "B_area_rest_of_maryland": "reg_mdo", "B_area_other_states": "reg_oth"}
BOUNDS = {"MU_size": (0.01, 3.0), "G_office_jobs": (-10, 10), "G_industrial_jobs": (-10, 10), "G_other_jobs": (-10, 10)}


def model(start=None):
    df = pd.read_parquet(DATA)
    database = Database("workplace_choice", df)
    B = {n: Beta(n, (start or {}).get(n, v), *BOUNDS.get(n, (None, None)), 0) for n, v in START.items()}
    x = Variable
    time_coef = B["B_time"] + sum((B[p] * x(c) for p, c in TIME_X.items()), 0)          # car-time slope of the worker
    V = {}
    for j in range(J):
        size = (x(f"jobs_RET_{j}") + exp(B["G_office_jobs"]) * x(f"jobs_OFF_{j}") + exp(B["G_industrial_jobs"]) * x(f"jobs_IND_{j}")
                + exp(B["G_other_jobs"]) * x(f"jobs_OTH_{j}"))
        V[j] = (time_coef * x(f"t_{j}") + B["B_ln1p_time"] * x(f"lt_{j}")
                + B["B_same_zone"] * x(f"intra_{j}") + B["B_other_county"] * x(f"cc_{j}") + B["B_other_state"] * x(f"cs_{j}")
                + B["B_DC_workplace_home_outside_DC"] * x(f"dcw_{j}") + B["B_acc_nonwork_workplace"] * x(f"accw_{j}")
                + sum((B[p] * x(f"{c}_{j}") for p, c in AREA.items()), 0)
                + x(f"z_off_sh_{j}") * (B["B_office_share_x_income_under40k"] * x("g1") + B["B_office_share_x_income_125kplus"] * x("g4"))
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
    if "--check" in sys.argv:
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
