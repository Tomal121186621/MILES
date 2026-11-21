#!/usr/bin/env python3
"""Workplace choice for SILO (2026-11-18): export of the final model (w09_cars.py step C0, 25 terms) to the engine's coefficient file
and the inputs of the Java check.

  2_silo/input/workplace_choice_coefficients_25terms.csv  parameter,estimate in the naming of JobDataManagerImpl (job.choice.model = respec):
      b_<base>[X<var>]  base t, lt, intra, cc, cs, dc (workplace in DC, home outside DC = 'dcw' of wdc.py), hiearn, off_sh, ret_sh,
                        ind_sh; var female, young, old, g1, g3, g4, lic, hhs, rurh, car0 (Seeker / rtsVar of the engine)
      mu_size           coefficient of ln S, S = total jobs of the zone (equal size weights, g_ = 0, so no g_ rows; engine with
                        job.choice.size = jobs)
      The centred time interactions of the estimation, t x (x - mean_x), are written as b_tX<x> = b and b_t = b_t(est) - sum b mean_x
      (mean_x = the estimation-half means of wdc.MEAN), which is the same utility.
  Java check (python3 w11_export_silo.py check <java_out.csv>): workers file and zone-jobs file for JobDataManagerImpl.verifyRts
      (-Dsilo.jobchoice.verify=<workers>;<zone_jobs>;<out>), the zone attribute file with the estimation's zone shares
      (-Dsilo.jobchoice.verify.fileShares=true), and the Python utilities V_j = mu ln S_j + sum b x over all zones with jobs for the
      same workers; 'check' compares the Java output with them -> w11_java_check.csv.
    python3 w11_export_silo.py [export]   ->  2_silo/input/workplace_choice_coefficients_25terms.csv, w11_verify/ inputs + python_V.csv
    python3 w11_export_silo.py check <java.csv>"""
import os as _os, sys as _sys  # MILES: configured locations (miles.toml)
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../..')))
from miles_env import MILES_HOME, WORKSPACE, ESTIMATION_RESULTS, ABIT_HOME, MATSIM_HOME, VAE_HOME, PRICING_HOME, PROJECT_ROOT  # noqa: E402,F401
import os, sys
import numpy as np, pandas as pd
CODE = os.path.dirname(os.path.abspath(__file__)); HERE = f"{ESTIMATION_RESULTS}/workplace"; sys.path.insert(0, CODE)   # HERE: results of this step (data); CODE: this folder
os.environ.setdefault("WDC_LOGSUM", f"{HERE}/logsum_new.npy")
import wdc   # noqa: E402
S = f"{WORKSPACE}/2_silo"
OUT = f"{S}/input/workplace_choice_coefficients_25terms.csv"; VD = f"{HERE}/w11_verify"
BASE = {"t": "t", "lt": "lt", "intra": "intra", "cc": "cc", "cs": "cs", "dcw": "dc", "z_hiearn": "hiearn", "z_off_sh": "off_sh", "z_ret_sh": "ret_sh", "z_ind_sh": "ind_sh"}
c = pd.read_csv(f"{HERE}/w09_coef.csv"); c = c[c.step == "C0"].set_index("param").coef


def engine_coefficients():
    rows = {}; bt = c["t"]
    for p, v in c.items():
        if p == "mu": rows["mu_size"] = v; continue
        parts = p.split("*"); base = BASE[parts[0]]; xs = parts[1:]
        if any(x.endswith("_c") for x in xs):
            assert base == "t" and len(xs) == 1, p
            x = xs[0][:-2]; rows[f"b_tX{x}"] = v; bt -= v * wdc.MEAN[x]
        elif p != "t":
            rows["b_" + base + "".join("X" + x for x in xs)] = v
    rows["b_t"] = bt
    return rows


def export():
    rows = engine_coefficients(); assert len(rows) == 25, len(rows)
    with open(OUT, "w") as f:
        f.write("parameter,estimate\n")
        for k in ["b_t"] + [k for k in rows if k != "b_t"]: f.write(f"{k},{float(rows[k])!r}\n")
    print(f"{OUT}: {len(rows)} terms; b_t {rows['b_t']:.6f} (estimated {c['t']:.6f}, centring folded in)")
    # ---- Java check inputs: 300 estimation-half workers, all zones with jobs
    os.makedirs(VD, exist_ok=True)
    P = wdc.persons(True); rng = np.random.default_rng(20261118); idx = np.sort(rng.choice(len(P["g"]), 300, replace=False))
    Q = {k: v[idx] for k, v in P.items()}
    zid = pd.read_csv(f"{S}/input/zoneSystem.csv").sort_values("ZoneId").ZoneId.values
    hcap = np.minimum(Q["hhsize"], 8)
    if (Q["hhsize"] > 8).any(): print(f"note: {(Q['hhsize'] > 8).sum()} sampled workers with household size > 8 (engine caps at 8)")
    pd.DataFrame({"test_id": idx, "home_zone": zid[Q["hidx"]], "female": Q["female"], "age": Q["age"], "car_segment": Q["car_seg"],
                  "income_group": Q["g"], "driving_licence": Q["lic"], "hh_size_capped_8": hcap}).to_csv(f"{VD}/workers.csv", index=False)
    pd.DataFrame({"zone": zid[wdc.AZ], "RET": wdc.JOBS[wdc.AZ, 0], "OFF": wdc.JOBS[wdc.AZ, 1], "IND": wdc.JOBS[wdc.AZ, 2], "OTH": wdc.JOBS[wdc.AZ, 3]}).to_csv(f"{VD}/zone_jobs.csv", index=False)
    pd.DataFrame({"zone": zid, "hiearn": wdc.D["z_hiearn"], "off_sh": wdc.D["z_off_sh"], "ret_sh": wdc.D["z_ret_sh"], "ind_sh": wdc.D["z_ind_sh"],
                  "rural": wdc.D["z_rural"]}).to_csv(f"{VD}/zone_attributes_est.csv", index=False)
    # Python utilities: the estimation's feat() and coefficients (centred terms as estimated), size mu ln(total jobs)
    A = np.broadcast_to(wdc.AZ, (len(idx), len(wdc.AZ)))
    U = sum(v * wdc.feat(p, Q["hidx"], A, Q) for p, v in c.items() if p != "mu")
    U = U + c["mu"] * np.log(wdc.JOBS[wdc.AZ].sum(1))[None, :]
    pd.DataFrame({"test_id": np.repeat(idx, len(wdc.AZ)), "zone": np.tile(zid[wdc.AZ], len(idx)), "V_python": U.ravel()}).to_csv(f"{VD}/python_V.csv", index=False)
    print(f"Java check inputs in {VD}: 300 workers x {len(wdc.AZ)} zones")


def check(java):
    p = pd.read_csv(f"{VD}/python_V.csv"); j = pd.read_csv(java).rename(columns={"V": "V_java"})
    m = p.merge(j[["test_id", "zone", "V_java"]], on=["test_id", "zone"], how="outer", indicator=True)
    assert (m._merge == "both").all(), m._merge.value_counts()
    m["abs_diff"] = (m.V_java - m.V_python).abs(); m["rel_diff"] = m.abs_diff / np.maximum(1.0, m.V_python.abs())
    m.drop(columns="_merge").to_csv(f"{HERE}/w11_java_check.csv", index=False)
    print(f"workplace: {len(m)} worker x zone utilities; max abs diff {m.abs_diff.max():.3g}, max rel diff {m.rel_diff.max():.3g} -> {HERE}/w11_java_check.csv")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "check": check(sys.argv[2])
    else: export()
